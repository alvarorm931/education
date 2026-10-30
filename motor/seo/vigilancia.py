"""Vigilancia diaria del sitio publicado (`docs/ley-seo.md`, «Comprobaciones diarias»).

Uso:
    python -m motor.seo.vigilancia --base https://dominio.es [--generado web/] [--muestra 40] [--informe x.json]

Lo que mira, de más a menos grave:
1. **Una sola versión del dominio**: http, www y http+www redirigen en un salto permanente a https sin www.
2. **robots.txt servido** (no el del repositorio): responde 200, deja pasar a todos los robots de
   `reglas.ROBOTS_PERMITIDOS` y, si se da `--generado`, es idéntico al generado. Cloudflare puede anteponer el suyo
   («managed robots.txt», con `Content-signal` y `Disallow` para robots de entrenamiento).
3. **Sitemaps servidos**: el índice y cada sitemap responden y se leen.
4. **Muestra de páginas** sacadas de los sitemaps: 200 sin redirección, sin `noindex` (cabecera o HTML), canónica
   a sí misma, sin desafío de Cloudflare (`cf-mitigated`), sin código inyectado por Cloudflare (ofuscación de
   correos, Rocket Loader, Web Analytics) y, con `--generado`, idénticas a las generadas.
5. **Robots de búsqueda y de IA**: portada y robots.txt pedidos con su nombre de agente. Si la respuesta cambia
   (bloqueo o contenido distinto), alerta. Ojo: desde GitHub no somos el robot de verdad (Cloudflare reconoce a los
   buenos por su IP); un 403 con `cf-mitigated` puede ser solo eso, y se anota como aviso.
6. **404 de verdad** para una dirección que no existe (sin respuestas 200 que Google cuenta como «soft 404»).
7. **Respuestas 304** a peticiones condicionales (ahorran rastreo; guía de Google sobre el presupuesto de rastreo).
8. **Certificado** con más de 14 días de vida.
9. Con claves (secretos de GitHub, los crea Álvaro):
   - `CRUX_API_KEY`: datos reales de velocidad (percentil 75 de LCP, INP y CLS, móvil y ordenador).
   - `GSC_CREDENCIALES` (JSON de una cuenta de servicio con acceso a la propiedad): errores de los sitemaps y
     estado de la muestra en el índice de Google (canónica elegida por Google, cobertura, rastreo).
   - `BING_WEBMASTER_KEY`: problemas de rastreo en Bing (sin probar hasta que exista la clave).

Sale con código 1 si hay alguna alerta. El flujo `seo.yml` abre o actualiza una incidencia en GitHub, que avisa por
correo, hasta que esté el bot de Telegram.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import socket
import ssl
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import lxml.html
import requests

from motor.robots import Robots
from motor.seo import sitemaps as sm
from motor.seo.reglas import ROBOTS_PERMITIDOS

AGENTE = "PortalEstudiosOposiciones-Vigilancia/0.1 (comprobacion diaria del sitio propio)"
# Nombres de agente con la forma que publica cada empresa; lo que miran las reglas de Cloudflare y de robots.txt es
# el nombre del producto.
AGENTES = {
    "Googlebot": "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) "
                 "Chrome/137.0.0.0 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Bingbot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; bingbot/2.0; "
               "+http://www.bing.com/bingbot.htm) Chrome/137.0.0.0 Safari/537.36",
    "OAI-SearchBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.0; "
                     "+https://openai.com/searchbot",
    "ChatGPT-User": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; "
                    "+https://openai.com/bot",
    "Claude-SearchBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-SearchBot/1.0)",
    "Claude-User": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-User/1.0)",
    "PerplexityBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; "
                     "+https://perplexity.ai/perplexitybot)",
}
INYECCIONES = {
    "/cdn-cgi/l/email-protection": "ofuscación de correos de Cloudflare (cambia el HTML y añade JavaScript)",
    "email-decode.min.js": "ofuscación de correos de Cloudflare",
    "static.cloudflareinsights.com": "Web Analytics de Cloudflare insertado automáticamente",
    "text/rocketscript": "Rocket Loader de Cloudflare (reescribe los scripts)",
    "rocket-loader": "Rocket Loader de Cloudflare",
    "/cdn-cgi/challenge-platform": "script de detección de robots de Cloudflare",
}
UMBRALES_CRUX = {"largest_contentful_paint": 2500, "interaction_to_next_paint": 200, "cumulative_layout_shift": 0.1}


@dataclass
class Hallazgo:
    comprobacion: str
    nivel: str  # alerta | aviso | info
    detalle: str
    url: str = ""


@dataclass
class Informe:
    fecha: str
    base: str
    hallazgos: list[Hallazgo] = field(default_factory=list)
    metricas: dict = field(default_factory=dict)

    @property
    def alertas(self) -> list[Hallazgo]:
        return [h for h in self.hallazgos if h.nivel == "alerta"]

    def como_dict(self):
        return {"fecha": self.fecha, "base": self.base, "alertas": len(self.alertas),
                "avisos": sum(h.nivel == "aviso" for h in self.hallazgos), "metricas": self.metricas,
                "hallazgos": [asdict(h) for h in self.hallazgos]}


class Vigilancia:
    def __init__(self, base: str, generado: Path | None = None, muestra: int = 40, sesion=None,
                 hoy: date | None = None, certificado: bool = True, entorno: dict | None = None):
        self.base = base.rstrip("/")
        self.host = urlparse(self.base).netloc
        self.generado = generado
        self.n_muestra = muestra
        self.sesion = sesion or requests.Session()
        self.hoy = hoy or date.today()
        self.con_certificado = certificado
        self.entorno = os.environ if entorno is None else entorno
        self.informe = Informe(self.hoy.isoformat(), self.base)

    def anotar(self, comprobacion, nivel, detalle, url=""):
        self.informe.hallazgos.append(Hallazgo(comprobacion, nivel, detalle, url))

    def pedir(self, url, agente=AGENTE, seguir=False, cabeceras=None):
        return self.sesion.get(url, headers={"User-Agent": agente, **(cabeceras or {})}, allow_redirects=seguir,
                               timeout=30)

    # -------------------------------------------------------------- 1. dominio
    def dominio(self):
        desnudo = self.host[4:] if self.host.startswith("www.") else self.host
        if self.host.startswith("www."):
            self.anotar("dominio", "alerta", "la dirección canónica lleva www; la ley fija una sola versión sin www")
        for variante in (f"http://{desnudo}/", f"http://www.{desnudo}/", f"https://www.{desnudo}/"):
            try:
                r = self.pedir(variante)
            except requests.RequestException as e:
                self.anotar("dominio", "aviso", f"{variante} no responde ({type(e).__name__})", variante)
                continue
            destino = r.headers.get("Location", "")
            if r.status_code not in (301, 308):
                self.anotar("dominio", "alerta", f"{variante} responde {r.status_code}: tiene que redirigir con 301 o "
                            f"308 a {self.base}/", variante)
            elif destino.rstrip("/") != self.base:
                self.anotar("dominio", "alerta", f"{variante} redirige a «{destino}» y no directamente a {self.base}/",
                            variante)
        r = self.pedir(self.base + "/")
        if r.status_code != 200:
            self.anotar("dominio", "alerta", f"la portada responde {r.status_code}", self.base + "/")

    # -------------------------------------------------------------- 2. robots.txt
    def robots(self, muestra: list[str]) -> str:
        url = self.base + "/robots.txt"
        r = self.pedir(url)
        if r.status_code != 200:
            nivel = "alerta"
            self.anotar("robots", nivel, f"robots.txt responde {r.status_code}"
                        + (" (con 5xx Google deja de rastrear todo el sitio)" if r.status_code >= 500 else ""), url)
            return ""
        texto = r.text
        if "content-signal" in texto.lower():
            self.anotar("robots", "alerta", "robots.txt lleva «Content-signal»: Cloudflare está anteponiendo su "
                        "robots.txt gestionado (Seguridad › Robots de IA: todo en «Permitir»)", url)
        for robot in ROBOTS_PERMITIDOS:
            rb = Robots(texto, agente=robot)
            vetadas = [u for u in muestra + [self.base + "/"] if not rb.permite(u)]
            if vetadas:
                self.anotar("robots", "alerta", f"el robots.txt servido prohíbe a {robot} {len(vetadas)} direcciones "
                            f"(por ejemplo {vetadas[0]}: {rb.regla(vetadas[0])[1]})", url)
        if self.generado and (self.generado / "robots.txt").exists():
            propio = (self.generado / "robots.txt").read_text(encoding="utf-8")
            if texto.strip() != propio.strip():
                self.anotar("robots", "alerta", "el robots.txt servido no es el generado (alguien lo cambia por el "
                            "camino: comparar con el de la web generada)", url)
        return texto

    # -------------------------------------------------------------- 3. sitemaps
    def sitemaps(self, robots_txt: str) -> list[str]:
        mapas = [l.split(":", 1)[1].strip() for l in robots_txt.splitlines() if l.lower().startswith("sitemap:")]
        if not mapas:
            mapas = [self.base + "/sitemap.xml"]
            self.anotar("sitemaps", "aviso", "robots.txt no declara el sitemap; se prueba /sitemap.xml")
        urls: list[str] = []
        pendientes, vistos = list(mapas), set()
        while pendientes and len(vistos) < 600:
            m = pendientes.pop(0)
            if m in vistos:
                continue
            vistos.add(m)
            try:
                r = self.pedir(m)
            except requests.RequestException as e:
                self.anotar("sitemaps", "alerta", f"{m} no responde ({type(e).__name__})", m)
                continue
            if r.status_code != 200:
                self.anotar("sitemaps", "alerta", f"{m} responde {r.status_code}", m)
                continue
            tipo, entradas, problemas = _leer_xml(r.content)
            for p in problemas:
                self.anotar("sitemaps", "alerta", f"{m}: {p}", m)
            if tipo == "sitemapindex":
                pendientes += [e["loc"] for e in entradas if e.get("loc")]
            else:
                urls += [e["loc"] for e in entradas if e.get("loc")]
        self.informe.metricas["urls_en_sitemaps"] = len(urls)
        if not urls:
            self.anotar("sitemaps", "alerta", "los sitemaps servidos no tienen ninguna dirección")
        return urls

    # -------------------------------------------------------------- 4. muestra de páginas
    def paginas(self, urls: list[str]):
        for url in urls:
            try:
                r = self.pedir(url)
            except requests.RequestException as e:
                self.anotar("paginas", "alerta", f"no responde ({type(e).__name__})", url)
                continue
            if r.headers.get("cf-mitigated"):
                self.anotar("paginas", "alerta", f"Cloudflare responde con un desafío (cf-mitigated: "
                            f"{r.headers['cf-mitigated']})", url)
                continue
            if r.status_code != 200:
                self.anotar("paginas", "alerta", f"responde {r.status_code}" + (
                    f" hacia {r.headers.get('Location')}" if r.status_code in (301, 302, 307, 308) else "") +
                            " y está en el sitemap", url)
                continue
            xrt = r.headers.get("X-Robots-Tag", "").lower()
            if re.search(r"noindex|none|nosnippet", xrt):
                self.anotar("paginas", "alerta", f"cabecera X-Robots-Tag: {xrt}", url)
            html = r.content
            try:
                arbol = lxml.html.document_fromstring(html)
            except Exception:
                self.anotar("paginas", "alerta", "el HTML servido no se puede leer", url)
                continue
            robots = " ".join(m.get("content", "").lower() for m in arbol.xpath("//meta[@name]")
                              if m.get("name", "").lower() in ("robots", "googlebot"))
            if re.search(r"noindex|none", robots):
                self.anotar("paginas", "alerta", f"está en el sitemap y lleva <meta robots «{robots}»>", url)
            canonicas = [l.get("href") for l in arbol.xpath("//link[@rel]") if "canonical" in l.get("rel", "").split()]
            if canonicas != [url]:
                self.anotar("paginas", "alerta", f"canónica servida {canonicas or 'ninguna'} en vez de sí misma", url)
            texto = html.decode("utf-8", errors="replace")
            for huella, que in INYECCIONES.items():
                if huella in texto:
                    self.anotar("paginas", "alerta", f"HTML modificado al servirlo: {que}", url)
            if self.generado:
                archivo = self.generado / (urlparse(url).path.lstrip("/") + "index.html")
                if archivo.exists() and hashlib.sha256(archivo.read_bytes()).digest() != hashlib.sha256(html).digest():
                    self.anotar("paginas", "aviso", "el HTML servido no es idéntico al generado "
                                f"({_primera_diferencia(archivo.read_text(encoding='utf-8'), texto)})", url)
            validador = {k: r.headers[k] for k in ("ETag", "Last-Modified") if k in r.headers}
            if url == urls[0]:
                if not validador:
                    self.anotar("rastreo", "aviso", "sin ETag ni Last-Modified: los robots no pueden pedir solo lo "
                                "cambiado", url)
                else:
                    cond = {"If-None-Match": validador["ETag"]} if "ETag" in validador else \
                        {"If-Modified-Since": validador["Last-Modified"]}
                    r2 = self.pedir(url, cabeceras=cond)
                    if r2.status_code != 304:
                        self.anotar("rastreo", "aviso", f"una petición condicional responde {r2.status_code} en vez de "
                                    "304", url)

    # -------------------------------------------------------------- 5. robots con su nombre
    def agentes(self):
        referencia = {}
        for ruta in ("/", "/robots.txt"):
            r = self.pedir(self.base + ruta)
            referencia[ruta] = (r.status_code, hashlib.sha256(r.content).hexdigest())
        for nombre, ua in AGENTES.items():
            for ruta in ("/", "/robots.txt"):
                url = self.base + ruta
                try:
                    r = self.pedir(url, agente=ua)
                except requests.RequestException as e:
                    self.anotar("agentes", "alerta", f"{nombre}: sin respuesta ({type(e).__name__})", url)
                    continue
                if r.status_code != 200:
                    nivel = "aviso" if r.headers.get("cf-mitigated") else "alerta"
                    extra = (" (desafío de Cloudflare a un robot falso: comprobar que con su IP real pasa)"
                             if nivel == "aviso" else "")
                    self.anotar("agentes", nivel, f"{nombre} recibe {r.status_code}{extra}", url)
                elif hashlib.sha256(r.content).hexdigest() != referencia[ruta][1]:
                    self.anotar("agentes", "alerta", f"{nombre} recibe un contenido distinto del que ve una persona "
                                "(encubrimiento o reglas por agente)", url)

    # -------------------------------------------------------------- 6. 404
    def no_existe(self):
        url = f"{self.base}/no-existe-{random.randrange(10**8, 10**9)}/"
        r = self.pedir(url)
        if r.status_code not in (404, 410):
            self.anotar("404", "alerta", f"una dirección que no existe responde {r.status_code} (Google lo cuenta como "
                        "«soft 404»)", url)

    # -------------------------------------------------------------- 8. certificado
    def certificado(self):
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((self.host, 443), timeout=15) as s:
                with ctx.wrap_socket(s, server_hostname=self.host) as t:
                    fin = datetime.strptime(t.getpeercert()["notAfter"], "%b %d %H:%M:%S %Y %Z")
        except Exception as e:
            self.anotar("certificado", "alerta", f"no se puede comprobar el certificado ({type(e).__name__}: {e})")
            return
        dias = (fin.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).days
        self.informe.metricas["certificado_dias"] = dias
        if dias < 14:
            self.anotar("certificado", "alerta", f"el certificado caduca en {dias} días")

    # -------------------------------------------------------------- 9. con claves
    def crux(self):
        clave = self.entorno.get("CRUX_API_KEY")
        if not clave:
            self.anotar("crux", "info", "sin CRUX_API_KEY: sin datos reales de velocidad")
            return
        for forma in ("PHONE", "DESKTOP"):
            r = self.sesion.post(f"https://chromeuxreport.googleapis.com/v1/records:queryRecord?key={clave}",
                                 json={"origin": self.base, "formFactor": forma}, timeout=30)
            if r.status_code == 404:
                self.anotar("crux", "info", f"{forma}: CrUX aún no tiene datos del sitio (hace falta tráfico real)")
                continue
            if r.status_code != 200:
                self.anotar("crux", "aviso", f"{forma}: CrUX responde {r.status_code}")
                continue
            metricas = r.json().get("record", {}).get("metrics", {})
            for nombre, maximo in UMBRALES_CRUX.items():
                p75 = metricas.get(nombre, {}).get("percentiles", {}).get("p75")
                if p75 is None:
                    continue
                valor = float(p75)
                self.informe.metricas[f"crux_{forma.lower()}_{nombre}"] = valor
                if valor > maximo:
                    self.anotar("crux", "alerta", f"{forma}: {nombre} p75 = {p75} (máximo {maximo}) con datos reales")

    def search_console(self, muestra: list[str]):
        credenciales = self.entorno.get("GSC_CREDENCIALES")
        if not credenciales:
            self.anotar("search_console", "info", "sin GSC_CREDENCIALES: sin datos de Search Console")
            return
        try:
            from google.auth.transport.requests import AuthorizedSession
            from google.oauth2 import service_account
        except ImportError:
            self.anotar("search_console", "aviso", "falta la librería google-auth (pip install google-auth)")
            return
        cuenta = service_account.Credentials.from_service_account_info(
            json.loads(credenciales), scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
        api = AuthorizedSession(cuenta)
        propiedad = self.entorno.get("GSC_PROPIEDAD") or f"sc-domain:{self.host}"
        prop = requests.utils.quote(propiedad, safe="")
        r = api.get(f"https://www.googleapis.com/webmasters/v3/sites/{prop}/sitemaps", timeout=30)
        if r.status_code != 200:
            self.anotar("search_console", "alerta", f"Search Console responde {r.status_code} a la lista de sitemaps")
            return
        for m in r.json().get("sitemap", []):
            if int(m.get("errors", 0)):
                self.anotar("search_console", "alerta", f"{m['path']}: {m['errors']} errores en Search Console")
            elif int(m.get("warnings", 0)):
                self.anotar("search_console", "aviso", f"{m['path']}: {m['warnings']} advertencias en Search Console")
        estados: dict[str, int] = {}
        for url in muestra[:20]:  # el límite es 2.000 al día por propiedad
            r = api.post("https://searchconsole.googleapis.com/v1/urlInspection/index:inspect",
                         json={"inspectionUrl": url, "siteUrl": propiedad, "languageCode": "es-ES"}, timeout=60)
            if r.status_code != 200:
                self.anotar("search_console", "aviso", f"inspección de URL responde {r.status_code}", url)
                continue
            ind = r.json().get("inspectionResult", {}).get("indexStatusResult", {})
            estados[ind.get("coverageState", "?")] = estados.get(ind.get("coverageState", "?"), 0) + 1
            if ind.get("googleCanonical") and ind.get("userCanonical") and ind["googleCanonical"] != ind["userCanonical"]:
                self.anotar("search_console", "alerta", f"Google elige otra canónica: {ind['googleCanonical']} (la "
                            "nuestra es la propia página; suele ser contenido casi igual a otra)", url)
            if ind.get("robotsTxtState") == "DISALLOWED" or ind.get("pageFetchState") not in (None, "SUCCESSFUL"):
                self.anotar("search_console", "alerta", f"Google no puede leerla: robots {ind.get('robotsTxtState')}, "
                            f"descarga {ind.get('pageFetchState')}", url)
        self.informe.metricas["gsc_cobertura_muestra"] = estados

    def bing(self):
        clave = self.entorno.get("BING_WEBMASTER_KEY")
        if not clave:
            self.anotar("bing", "info", "sin BING_WEBMASTER_KEY: sin datos de Bing Webmaster Tools")
            return
        r = self.sesion.get("https://ssl.bing.com/webmaster/api.svc/json/GetCrawlIssues",
                            params={"apikey": clave, "siteUrl": self.base + "/"}, timeout=30)
        if r.status_code != 200:
            self.anotar("bing", "aviso", f"la API de Bing responde {r.status_code}")
            return
        problemas = r.json().get("d", []) or []
        self.informe.metricas["bing_problemas_rastreo"] = len(problemas)
        if problemas:
            self.anotar("bing", "aviso", f"Bing anota {len(problemas)} direcciones con problemas de rastreo")

    # -------------------------------------------------------------- ejecución
    def ejecutar(self) -> Informe:
        self.dominio()
        robots_txt = self.pedir(self.base + "/robots.txt").text
        urls = self.sitemaps(robots_txt)
        semilla = random.Random(self.hoy.toordinal())  # misma muestra en todo el día, distinta cada día
        muestra = sorted(semilla.sample(urls, min(self.n_muestra, len(urls)))) if urls else []
        self.robots(muestra)
        self.paginas(muestra)
        self.agentes()
        self.no_existe()
        if self.con_certificado:
            self.certificado()
        self.crux()
        self.search_console(muestra)
        self.bing()
        return self.informe


def _leer_xml(contenido: bytes):
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".xml") as f:
        f.write(contenido)
        f.flush()
        return sm.leer(Path(f.name))


def _primera_diferencia(a: str, b: str) -> str:
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return f"desde el carácter {i}: «{a[max(0, i - 20):i + 40]}» → «{b[max(0, i - 20):i + 40]}»"
    return f"longitudes {len(a)} y {len(b)}"


def resumen(informe: Informe) -> str:
    d = informe.como_dict()
    lineas = [f"Vigilancia SEO {d['fecha']} · {d['base']} · {d['alertas']} alertas · {d['avisos']} avisos"]
    for h in informe.hallazgos:
        if h.nivel != "info":
            lineas.append(f"- [{h.nivel}] {h.comprobacion}: {h.detalle}" + (f" ({h.url})" if h.url else ""))
    return "\n".join(lineas)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Vigilancia diaria del sitio publicado")
    p.add_argument("--base", required=True)
    p.add_argument("--generado", type=Path)
    p.add_argument("--muestra", type=int, default=40)
    p.add_argument("--informe", type=Path)
    a = p.parse_args(argv)
    informe = Vigilancia(a.base, a.generado, a.muestra).ejecutar()
    if a.informe:
        a.informe.parent.mkdir(parents=True, exist_ok=True)
        a.informe.write_text(json.dumps(informe.como_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
    print(resumen(informe))
    return 1 if informe.alertas else 0


if __name__ == "__main__":
    sys.exit(main())
