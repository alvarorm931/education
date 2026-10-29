"""Rastreador de oferta de posgrado por web: robots.txt, sitemaps y páginas de programa.

Para cada dominio de un centro (universidad, centro adscrito, escuela de negocio...):
  1. lee robots.txt, respeta sus prohibiciones para nuestro agente y toma las líneas «Sitemap:»;
  2. recorre los sitemaps (índices, gzip) hasta un tope de URL;
  3. marca las URL que parecen programas de posgrado (máster, MBA, experto, especialista, título propio,
     formación permanente, postgrado) y descarta noticias, eventos, blog y ficheros;
  4. abre una muestra de esas páginas y mide qué enseñan sin pedir datos: datos estructurados (Course,
     EducationalOccupationalProgram, Offer con precio), importes en euros, menciones a plazas, becas,
     metodología o evaluación, enlaces a guía docente o folleto en PDF y formularios que piden correo o
     teléfono (el «déjanos tus datos»).

No reproduce ni guarda texto para publicar: guarda los originales en el archivo privado y las medidas.
Peticiones identificadas, una por segundo como máximo en cada dominio, varios dominios a la vez.

Uso:
  python -m motor.estudios.rastreador --dominios https://www.upm.es,https://www.esic.edu --salida ruta/
  python -m motor.estudios.rastreador --censo ruta/datos/estudios/centros --salida ruta/
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import threading
import time
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

from motor.archivo import Archivo
from motor.http import USER_AGENT

AGENTE = "PortalEstudiosOposiciones"
FUENTE = "web-centros"

PROGRAMA = re.compile(
    r"m[aá]ster|masters?\b|mba\b|maestr[ií]a|postgrado|posgrado|t[ií]tulos?[-_ ]propios?|formaci[oó]n[-_ ]permanente|"
    r"experto[-_ ]universitario|especialista[-_ ]universitario|diploma[-_ ]de[-_ ]especializaci[oó]n|executive|"
    r"estudios[-_ ]propios|postgraduate|master-?s?-?degree", re.I)
RUIDO = re.compile(
    r"/(noticias?|news|actualidad|agenda|eventos?|events?|blog|prensa|press|tag|etiqueta|categor[ií]a|category|"
    r"author|autor|wp-content|feed|comment|search|buscar|page/\d+|sala-de-prensa|convocatorias?-de-empleo)/"
    r"|\.(pdf|jpe?g|png|gif|svg|webp|docx?|xlsx?|zip|mp4)$", re.I)
EURO = re.compile(r"(\d{1,3}(?:[.\s]\d{3})+|\d{3,6})(?:,\d{2})?\s?(?:€|euros?\b|EUR\b)", re.I)
TEMAS = {
    "precio": re.compile(r"\bprecio|\bimporte|\bcoste\b|\btasas?\b|\bmatr[ií]cula\b|\bfee", re.I),
    "plazas": re.compile(r"\bplazas\b", re.I),
    "becas": re.compile(r"\bbecas?\b|\bayudas?\b|\bdescuentos?\b|\bfinanciaci[oó]n", re.I),
    "metodologia": re.compile(r"metodolog[ií]a", re.I),
    "evaluacion": re.compile(r"\bevaluaci[oó]n\b|sistema de evaluaci", re.I),
    "asignaturas": re.compile(r"asignaturas?|m[oó]dulos?|plan de estudios|programa acad[eé]mico|temario", re.I),
    "admision": re.compile(r"admisi[oó]n|requisitos de acceso|preinscripci[oó]n", re.I),
    "horario": re.compile(r"\bhorario|\bcalendario", re.I),
}
FOLLETO = re.compile(r'href="([^"]+\.pdf)"[^>]*>([^<]{0,120})', re.I)
TITULO_PROGRAMA = re.compile(r"m[aá]ster|\bmba\b|posgrado|postgrado|experto universitario|especialista universitario|"
                             r"diploma de especializaci|executive", re.I)
# Señales de ficha de programa (lo que tiene una página que vende o describe un programa concreto).
SENAL_PROGRAMA = re.compile(r"\bECTS\b|cr[ée]ditos|matr[ií]cula|\bprecio|plazas|titulaci[oó]n|admisi[oó]n|"
                            r"plan de estudios|inscr[ií]bete|solicita (m[aá]s )?informaci[oó]n|requisitos de acceso|"
                            r"salidas profesionales|programa acad[eé]mico|temario|modalidad", re.I)
NOTICIA = re.compile(r"/(19|20)\d{2}/\d{1,2}/|/(blog|noticias?|news|actualidad|articulos?|opinion|prensa|revista|"
                     r"magazine|tag|etiquetas?|author|autor)/", re.I)
GUIA = re.compile(r"gu[ií]a|folleto|brochure|dossier|programa|plan de estudios|syllabus", re.I)


class Dominio:
    """Lector cortés de un dominio: robots.txt, una petición por segundo, originales archivados."""

    def __init__(self, base: str, archivo: Archivo | None, pausa: float = 1.0, max_peticiones: int = 80):
        p = urlparse(base if base.startswith("http") else "https://" + base)
        self.base = f"{p.scheme or 'https'}://{p.netloc}"
        self.host = p.netloc
        self.archivo = archivo
        self.pausa = pausa
        self.max_peticiones = max_peticiones
        self.peticiones = 0
        self.ultimo = 0.0
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": f"{USER_AGENT}", "Accept-Language": "es-ES,es;q=0.9"})
        self.robots = RobotFileParser()
        self.robots_ok = True

    def get(self, url: str, timeout: float = 25, guardar: bool = True, sin_robots: bool = False) -> requests.Response | None:
        """guardar=False registra solo la huella (sitemaps: grandes y se pueden volver a pedir).
        sin_robots=True solo para pedir el propio robots.txt."""
        if self.peticiones >= self.max_peticiones:
            return None
        if not sin_robots and not self.robots_ok_para(url):
            return None
        espera = self.pausa - (time.time() - self.ultimo)
        if espera > 0:
            time.sleep(espera)
        self.ultimo = time.time()
        self.peticiones += 1
        try:
            r = self.s.get(url, timeout=timeout, allow_redirects=True)
        except requests.RequestException:
            return None
        if self.archivo is not None and r.status_code == 200 and not guardar:
            self.archivo.registrar(FUENTE, date.today(), r.content, url, r.status_code)
        elif self.archivo is not None and r.status_code == 200 and len(r.content) < 15_000_000:
            ext = "xml" if "xml" in r.headers.get("content-type", "") or url.endswith((".xml", ".gz")) else "html"
            self.archivo.guardar(FUENTE, date.today(), r.content, url, ext, r.status_code,
                                 {k: v for k, v in r.headers.items() if k.lower() in {"content-type", "last-modified", "date"}})
        return r

    def robots_ok_para(self, url: str) -> bool:
        if not self.robots.last_checked:  # aún sin leer: no se pide nada salvo el propio robots.txt
            return False
        try:
            return self.robots.can_fetch(AGENTE, url)
        except Exception:
            return True

    def leer_robots(self) -> list[str]:
        r = self.get(self.base + "/robots.txt", sin_robots=True)
        sitemaps = []
        if r is not None and r.status_code == 200 and "text" in r.headers.get("content-type", "text"):
            lineas = r.text.splitlines()
            self.robots.parse(lineas)
            sitemaps = [l.split(":", 1)[1].strip() for l in lineas if l.lower().startswith("sitemap:")]
        else:
            self.robots.parse([])
        return sitemaps


def _xml(contenido: bytes) -> ET.Element | None:
    if contenido[:2] == b"\x1f\x8b":
        try:
            contenido = gzip.decompress(contenido)
        except OSError:
            return None
    try:
        return ET.fromstring(contenido)
    except ET.ParseError:
        return None


def urls_de_sitemap(raiz: ET.Element) -> tuple[list[str], list[str]]:
    """(sitemaps hijos, URL de páginas) de un sitemap o índice de sitemaps."""
    hijos, paginas = [], []
    for elem in raiz.iter():
        if elem.tag.endswith("loc") and elem.text:
            loc = elem.text.strip()
            (hijos if raiz.tag.endswith("sitemapindex") else paginas).append(loc)
    return hijos, paginas


def es_programa(url: str) -> bool:
    u = urlparse(url)
    ruta = u.path + ("?" + u.query if u.query else "")
    return bool(PROGRAMA.search(ruta)) and not RUIDO.search(u.path)


def prioridad_sitemap(url: str) -> int:
    """Primero los sitemaps que por su nombre pueden traer programas."""
    u = url.lower()
    if PROGRAMA.search(u) or re.search(r"course|curso|program|estudio|titulaci|oferta|formacion", u):
        return 0
    if re.search(r"post|news|noticia|blog|tag|categor|author|image|video|event", u):
        return 2
    return 1


def medir_pagina(html: str, url: str) -> dict:
    """Qué enseña una página de programa sin pedir datos."""
    texto = re.sub(r"(?is)<script(?![^>]*ld\+json).*?</script>|<style.*?</style>", " ", html)
    visible = re.sub(r"<[^>]+>", " ", texto)
    ld = []
    for bloque in re.findall(r'(?is)<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html):
        try:
            d = json.loads(bloque.strip())
        except (ValueError, TypeError):
            continue
        for x in (d if isinstance(d, list) else d.get("@graph", [d]) if isinstance(d, dict) else []):
            if isinstance(x, dict):
                ld.append(x)
    tipos = sorted({str(t) for x in ld for t in (x.get("@type") if isinstance(x.get("@type"), list) else [x.get("@type")]) if t})
    precio_ld = None
    for x in ld:
        ofertas = x.get("offers") or x.get("hasCourseInstance") or []
        for o in ofertas if isinstance(ofertas, list) else [ofertas]:
            if isinstance(o, dict) and (o.get("price") or o.get("lowPrice")):
                precio_ld = {"precio": o.get("price") or o.get("lowPrice"), "moneda": o.get("priceCurrency")}
    formularios = re.findall(r"(?is)<form\b.*?</form>", html)
    pide_datos = any(re.search(r'type="email"|name="[^"]*(email|correo|mail)[^"]*"', f, re.I) for f in formularios)
    pide_tel = any(re.search(r'type="tel"|name="[^"]*(tel|phone|movil)[^"]*"', f, re.I) for f in formularios)
    pdfs = [(urljoin(url, h), " ".join(t.split())) for h, t in FOLLETO.findall(html)]
    titulo = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    h1 = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", html)
    cabecera = " ".join(re.sub(r"<[^>]+>", " ", (titulo.group(1) if titulo else "") + " " + (h1.group(1) if h1 else "")).split())
    senales = {m.group(0).lower() for m in SENAL_PROGRAMA.finditer(visible)}
    return {
        "es_programa": bool(TITULO_PROGRAMA.search(cabecera)) and len(senales) >= 4 and not NOTICIA.search(urlparse(url).path),
        "senales": sorted(senales)[:12],
        "titulo": " ".join(titulo.group(1).split())[:200] if titulo else None,
        "jsonld_tipos": tipos,
        "precio_jsonld": precio_ld,
        "importes_euros": len(EURO.findall(visible)),
        "temas": {k: bool(p.search(visible)) for k, p in TEMAS.items()},
        "formulario_pide_correo": pide_datos,
        "formulario_pide_telefono": pide_tel,
        "pdf_guia_o_folleto": [u for u, t in pdfs if GUIA.search(t) or GUIA.search(u)][:10],
        "bytes": len(html),
    }


def rastrear(base: str, archivo: Archivo | None, max_urls: int = 60000, muestra: int = 6,
             max_peticiones: int = 80, semillas: list[str] | None = None) -> dict:
    d = Dominio(base, archivo, max_peticiones=max_peticiones)
    res: dict = {"dominio": d.host, "base": d.base}
    try:
        sitemaps = d.leer_robots()
        res["robots_sitemaps"] = len(sitemaps)
        if not sitemaps:
            sitemaps = [d.base + "/sitemap.xml", d.base + "/sitemap_index.xml"]
        cola = sorted(dict.fromkeys(sitemaps), key=prioridad_sitemap)
        vistos, paginas, leidos = set(), [], 0
        while cola and len(paginas) < max_urls and d.peticiones < max_peticiones - muestra:
            sm = cola.pop(0)
            if sm in vistos:
                continue
            vistos.add(sm)
            r = d.get(sm, guardar=False)
            if r is None or r.status_code != 200:
                continue
            raiz = _xml(r.content)
            if raiz is None:
                continue
            leidos += 1
            hijos, urls = urls_de_sitemap(raiz)
            cola = sorted(dict.fromkeys(cola + [h for h in hijos if h not in vistos]), key=prioridad_sitemap)
            paginas.extend(urls)
        res["sitemaps_leidos"] = leidos
        res["sitemaps_pendientes"] = len(cola)
        res["urls"] = len(paginas)
        raiz_host = d.host.split(":")[0].removeprefix("www.")
        candidatas = sorted({u for u in paginas if es_programa(u) and urlparse(u).netloc.endswith(raiz_host)})
        res["urls_programa_sitemap"] = len(candidatas)
        if not candidatas and semillas:  # sin sitemap útil: las URL de programa vistas en Common Crawl
            candidatas = sorted({u for u in semillas if es_programa(u)})
        res["urls_programa"] = len(candidatas)
        res["programas"] = candidatas
        medidas = []
        for u in _muestra(candidatas, muestra):
            r = d.get(u)
            if r is None or r.status_code != 200 or "html" not in r.headers.get("content-type", ""):
                continue
            medidas.append({"url": u, **medir_pagina(r.text, u)})
        res["muestra"] = medidas
        validas = sum(1 for m in medidas if m.get("es_programa"))
        res["paginas_programa_validas"] = validas
        res["verificado"] = validas >= 2 or (validas == 1 and len(medidas) <= 2)
    except Exception as e:  # un dominio roto no para el resto
        res["error"] = f"{type(e).__name__}: {e}"[:300]
    res["peticiones"] = d.peticiones
    return res


def _muestra(urls: list[str], n: int) -> list[str]:
    """Muestra repartida a lo largo de la lista (evita coger solo la primera sección del sitio)."""
    if len(urls) <= n:
        return urls
    paso = len(urls) / n
    return [urls[int(i * paso)] for i in range(n)]


def objetivos_de_proveedores(fichero: Path, desde: int = 0, hasta: int | None = None,
                             estados: tuple = ("oficial", "candidato")) -> list[dict]:
    """Proveedores del censo único (motor/estudios/censo.py) en un tramo de la lista."""
    filas = [json.loads(l) for l in fichero.read_text(encoding="utf-8").splitlines() if l.strip()]
    filas = [p for p in filas if p["estado"] in estados][desde:hasta]
    return [{"web": "https://" + p["dominio"], "id": p["id"], "estado": p["estado"],
             "semillas": p.get("senales", {}).get("cc_ejemplos", [])} for p in filas]


def dominios_del_censo(carpeta: Path) -> list[dict]:
    """Webs de universidades y centros del censo del RUCT, sin repetir dominio."""
    salida, vistos = [], set()
    for f in sorted(carpeta.glob("[0-9][0-9][0-9].json")):
        u = json.loads(f.read_text(encoding="utf-8"))
        candidatos = [(u.get("web"), "universidad", u)] + [(c.get("web"), "centro", c) for c in u.get("centros", [])]
        for web, nivel, reg in candidatos:
            if not web:
                continue
            host = urlparse(web if web.startswith("http") else "https://" + web).netloc.lower().removeprefix("www.")
            if host and host not in vistos:
                vistos.add(host)
                salida.append({"web": web, "host": host, "nivel": nivel, "grupo": u.get("grupo"),
                               "universidad": u.get("codigo"), "nombre": reg.get("nombre"), "codigo": reg.get("codigo")})
    return salida


def ejecutar(objetivos: list[dict], raiz: Path, hilos: int, max_minutos: float, muestra: int,
             solo_huella: bool = False) -> dict:
    archivo = Archivo(raiz / "archivo")
    if solo_huella:  # medición masiva: se registra huella y URL de cada página; el original se vuelve a pedir
        archivo.guardar = lambda fuente, fecha, contenido, url, ext, status, cabeceras=None, comprimir=True: \
            archivo.registrar(fuente, fecha, contenido, url, status, cabeceras)
    destino = raiz / "datos" / "estudios" / "oferta_web"
    destino.mkdir(parents=True, exist_ok=True)
    fin = time.time() + max_minutos * 60
    cerrojo = threading.Lock()
    resumen = Counter()

    def uno(obj: dict) -> None:
        if time.time() > fin:
            return
        r = rastrear(obj["web"], archivo, muestra=muestra, semillas=obj.get("semillas"))
        r["centro"] = obj
        with cerrojo:
            (destino / f"{r['dominio'].replace(':', '_')}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
            resumen["dominios"] += 1
            resumen["con_sitemap"] += 1 if r.get("urls") else 0
            resumen["con_programas"] += 1 if r.get("urls_programa") else 0
            resumen["urls_programa"] += r.get("urls_programa", 0)
            resumen["errores"] += 1 if r.get("error") else 0
            resumen["verificados"] += 1 if r.get("verificado") else 0

    with ThreadPoolExecutor(max_workers=hilos) as ex:
        list(ex.map(uno, objetivos))
    return dict(resumen)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dominios", help="webs separadas por comas")
    p.add_argument("--censo", help="carpeta datos/estudios/centros del censo del RUCT")
    p.add_argument("--proveedores", help="proveedores.jsonl del censo único")
    p.add_argument("--tramo", default="0:", help="tramo de la lista de proveedores, p. ej. 0:800")
    p.add_argument("--hilos", type=int, default=8)
    p.add_argument("--muestra", type=int, default=6)
    p.add_argument("--max-minutos", type=float, default=27)
    p.add_argument("--solo-huella", action="store_true", help="no guardar originales, solo huella y URL")
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    if a.dominios:
        objetivos = [{"web": w.strip(), "nivel": "manual"} for w in a.dominios.split(",") if w.strip()]
    elif a.proveedores:
        d, _, h = a.tramo.partition(":")
        objetivos = objetivos_de_proveedores(Path(a.proveedores), int(d or 0), int(h) if h else None)
    elif a.censo:
        objetivos = dominios_del_censo(Path(a.censo))
    else:
        sys.exit("Falta --dominios o --censo")
    print(json.dumps(ejecutar(objetivos, Path(a.salida), a.hilos, a.max_minutos, a.muestra, a.solo_huella), ensure_ascii=False))


if __name__ == "__main__":
    main()
