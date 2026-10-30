"""Control automático de cada página antes de publicar (`docs/ley-seo.md`, «Control automático de cada página»).

Uso:
    python -m motor.seo.control --sitio web/ --base https://dominio.es --manifiesto control/paginas.jsonl \
        [--revisiones control/revision_ia.jsonl] [--estado-anterior estado.json] [--estado-nuevo estado.json] \
        [--aplicar] [--generar-sitemaps] [--navegador] [--informe informe.json]

- `--sitio`: carpeta de la web generada, tal como se sube (cada dirección `/a/b/` es `a/b/index.html`; en la raíz
  `robots.txt`, `404.html` y, si los hay, `_redirects` y `_headers` de Cloudflare).
- `--manifiesto`: una línea JSON por página, fuera de la carpeta que se publica:
  `{"ruta": "/a/b/", "tipo": "proceso", "plantilla": "proceso", "lastmod": "2026-10-28", "textos_ia": ["…"]}`.
- `--revisiones`: textos escritos con IA ya aprobados: `{"huella": "<sha256>", "revisado_por": "…", "fecha": "…"}`.
- `--estado-anterior` / `--estado-nuevo`: huella del contenido y lastmod de cada página en la publicación anterior
  y en esta (para que la fecha solo cambie cuando cambian los datos).
- `--aplicar`: hace lo que la ley manda hacer sin parar la publicación: pone `noindex` a las páginas sin datos
  mínimos y quita el marcado que no vale.
- `--generar-sitemaps`: escribe los sitemaps de las páginas indexables antes de comprobarlos.
- `--navegador`: añade las comprobaciones con Chromium (contenido que añade JavaScript, ventanas al cargar y
  velocidad por plantilla); ver `motor/seo/renderizado.py`.

Sale con código 1 si algo impide publicar. El informe lleva cada fallo con su regla y su fuente.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

from motor.robots import Robots
from motor.seo import sitemaps as sm
from motor.seo.pagina import Pagina, leer, limpiar
from motor.seo.reglas import DATOS_MINIMOS, ENLACES_MINIMOS, MARCADO_SIN_EFECTO, REGLAS, ROBOTS_PERMITIDOS
from motor.seo.similitud import grupos_parecidos

FICHAS = {"proceso", "master", "grado", "fp", "nota_corte"}
HUECOS = re.compile(
    r"\{\{|\}\}|\{%|%\}|\$\{|\[object Object\]|\b(None|null|undefined|NaN|nan|TODO|FIXME)\b|lorem ipsum"
    r"|\(\s*\)|\[\s*\]|\s[,.;:](\s|$)|^\s*[|·–—:,-]|[|·–—:,-]\s*$|(?P<sep>[|·–—])\s*(?P=sep)", re.I)
SEGMENTO_CODIGO = re.compile(r"^\d{5,}$|^[a-z]*-?[0-9a-f]{8,}$|^[a-z]{2,4}-[a-z]-\d{4}-\d+$", re.I)
DIRECTIVAS_SIN_FRAGMENTO = {"nosnippet", "max-snippet:0"}
CODIGOS_PERMANENTES = {"301", "308"}
LIMITE_HTML = 2 * 1024 * 1024  # Googlebot lee los primeros 2 MB sin comprimir (documentación de 3/2/2026)
AVISO_HTML = 1536 * 1024  # margen propio para avisar antes de llegar
FORMATOS_ICONO = (".ico", ".png", ".gif", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".ppm")


@dataclass
class Fallo:
    regla: str
    ruta: str
    detalle: str
    consecuencia: str = ""

    def __post_init__(self):
        self.consecuencia = self.consecuencia or REGLAS[self.regla].consecuencia


@dataclass
class Informe:
    fecha: str
    base: str
    paginas: int = 0
    indexables: int = 0
    fallos: list[Fallo] = field(default_factory=list)
    acciones: dict[str, list[str]] = field(default_factory=lambda: {"noindex": [], "quitar_marcado": []})
    estado: dict[str, dict] = field(default_factory=dict)

    @property
    def bloquea(self) -> bool:
        return any(f.consecuencia in ("no_publicar", "plantilla") for f in self.fallos)

    def resumen(self) -> dict[str, dict[str, int]]:
        r: dict[str, Counter] = defaultdict(Counter)
        for f in self.fallos:
            r[f.regla][f.consecuencia] += 1
        return {k: dict(v) for k, v in sorted(r.items())}

    def como_dict(self) -> dict:
        return {
            "fecha": self.fecha, "base": self.base, "paginas": self.paginas, "indexables": self.indexables,
            "bloquea": self.bloquea, "resumen": self.resumen(), "acciones": self.acciones,
            "fallos": [asdict(f) | {"fuente": REGLAS[f.regla].fuente} for f in self.fallos],
        }


def cargar_sitio(sitio: Path) -> dict[str, Pagina]:
    paginas = {}
    for archivo in sorted(sitio.rglob("*.html")):
        if archivo.relative_to(sitio).as_posix() == "404.html":
            continue
        p = leer(archivo, sitio)
        paginas[p.ruta] = p
    return paginas


def cargar_jsonl(ruta: Path | None) -> list[dict]:
    if not ruta or not ruta.exists():
        return []
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]


def huella_texto(texto: str) -> str:
    return hashlib.sha256(unicodedata.normalize("NFC", limpiar(texto)).encode()).hexdigest()


def huella_contenido(p: Pagina) -> str:
    """Huella de lo que la página dice (datos y texto principal), sin la fecha de «actualizado» ni la plantilla."""
    datos = sorted((d.clave, d.valor, d.fuente or "", d.fecha or "") for d in p.datos)
    return hashlib.sha256(json.dumps([p.texto_huella, datos], ensure_ascii=False).encode()).hexdigest()


class Control:
    def __init__(self, sitio: Path, base: str, manifiesto: list[dict], revisiones: list[dict] | None = None,
                 estado_anterior: dict | None = None, hoy: date | None = None, umbral: float = 0.9):
        self.sitio = sitio
        self.base = base.rstrip("/")
        self.host = urlparse(self.base).netloc
        self.manifiesto = {m["ruta"]: m for m in manifiesto}
        self.aprobadas = {r["huella"] for r in (revisiones or [])}
        self.anterior = estado_anterior or {}
        self.hoy = hoy or date.today()
        self.umbral = umbral
        self.paginas = cargar_sitio(sitio)
        self.archivos = {"/" + p.relative_to(sitio).as_posix() for p in sitio.rglob("*") if p.is_file()}
        self.redirecciones = self._leer_redirecciones()
        self.informe = Informe(self.hoy.isoformat(), self.base)

    # ------------------------------------------------------------------ utilidades
    def fallo(self, regla, ruta, detalle, consecuencia=""):
        self.informe.fallos.append(Fallo(regla, ruta, detalle, consecuencia))

    def tipo(self, p: Pagina) -> str | None:
        m = self.manifiesto.get(p.ruta, {})
        if m.get("tipo"):
            return m["tipo"]
        return p.tipo_html

    def interna(self, href: str, desde: str) -> str | None:
        """Ruta interna del enlace (sin consulta ni fragmento) o None si es externo."""
        absoluto = urljoin(self.base + desde, href)
        u = urlparse(absoluto)
        if u.scheme not in ("http", "https") or u.netloc != self.host:
            return None
        return u.path or "/"

    def _leer_redirecciones(self) -> dict[str, tuple[str, str]]:
        archivo = self.sitio / "_redirects"
        salida = {}
        if archivo.exists():
            for linea in archivo.read_text(encoding="utf-8").splitlines():
                linea = linea.split("#", 1)[0].strip()
                if not linea:
                    continue
                partes = linea.split()
                origen, destino = partes[0], partes[1] if len(partes) > 1 else ""
                salida[origen] = (destino, partes[2] if len(partes) > 2 else "302")
        return salida

    # ------------------------------------------------------------------ comprobaciones por página
    def comprobar_pagina(self, p: Pagina, titulos: Counter, descripciones: Counter):
        r, tipo = p.ruta, self.tipo(p)

        # Dirección
        if r != "/":
            problemas = []
            if r != r.lower():
                problemas.append("mayúsculas")
            if "_" in r or " " in r or "%20" in r:
                problemas.append("guion bajo o espacio")
            if not r.isascii():
                problemas.append("caracteres no ASCII (tildes, eñes): usar su forma sin tilde")
            if not r.endswith("/"):
                problemas.append("no termina en barra")
            codigos = [s for s in r.strip("/").split("/") if SEGMENTO_CODIGO.match(s)]
            if codigos:
                problemas.append(f"códigos en vez de nombres: {', '.join(codigos)}")
            if problemas:
                self.fallo("direccion", r, "; ".join(problemas))

        # Tipo y datos mínimos
        if tipo is None:
            self.fallo("datos_minimos", r, "sin tipo de página (manifiesto o <main data-tipo>)", "no_publicar")
        elif tipo not in DATOS_MINIMOS:
            self.fallo("datos_minimos", r, f"tipo «{tipo}» sin datos mínimos declarados en motor/seo/reglas.py",
                       "no_publicar")
        else:
            claves = {d.clave for d in p.datos if d.valor and d.visible}
            faltan = [" o ".join(alt) for alt in DATOS_MINIMOS[tipo] if not claves & set(alt)]
            if tipo in ENLACES_MINIMOS:
                tipo_destino, minimo = ENLACES_MINIMOS[tipo]
                destinos = {self.interna(e.href, r) for e in p.enlaces if e.en_main}
                n = sum(1 for d in destinos if d in self.paginas and self.tipo(self.paginas[d]) == tipo_destino)
                if n < minimo:
                    faltan.append(f"al menos {minimo} enlace a una ficha de {tipo_destino}")
            if faltan and p.indexable:
                self.fallo("datos_minimos", r, f"le falta {', '.join(faltan)}: debe salir con noindex")
                self.informe.acciones["noindex"].append(r)

        # Contenido en el HTML
        if p.mains != 1:
            self.fallo("contenido_html", r, f"{p.mains} elementos <main> (tiene que haber uno)")
        elif not p.texto_main:
            self.fallo("contenido_html", r, "<main> vacío en el HTML servido")
        for d in p.datos:
            if not d.valor:
                self.fallo("contenido_html", r, f"dato «{d.clave}» vacío en el HTML servido")

        # Fuente y fecha
        for d in p.datos:
            if not d.visible:
                self.fallo("fuente_fecha", r, f"dato «{d.clave}» oculto")
                continue
            if not d.fuente or not d.fuente_visible:
                self.fallo("fuente_fecha", r, f"dato «{d.clave}» sin enlace visible a su fuente")
            elif urlparse(d.fuente).scheme not in ("http", "https"):
                self.fallo("fuente_fecha", r, f"dato «{d.clave}»: la fuente «{d.fuente}» no es una dirección web")
            if not d.fecha or not d.fecha_visible:
                self.fallo("fuente_fecha", r, f"dato «{d.clave}» sin fecha visible (<time datetime>)")
            else:
                motivo = sm.fecha_valida(d.fecha, self.hoy)
                if motivo:
                    self.fallo("fuente_fecha", r, f"dato «{d.clave}»: {motivo.replace('lastmod', 'fecha')}")

        # Título y descripción
        for regla, valores, contador, nombre in (("titulo", p.titulos, titulos, "título"),
                                                 ("descripcion", p.descripciones, descripciones, "descripción")):
            if len(valores) != 1:
                self.fallo(regla, r, f"{len(valores)} etiquetas de {nombre} (tiene que haber una)")
                continue
            v = valores[0]
            if not v:
                self.fallo(regla, r, f"{nombre} vacío")
            elif HUECOS.search(v):
                self.fallo(regla, r, f"hueco de plantilla en el {nombre}: «{v}»")
            elif p.indexable and contador[v] > 1:
                self.fallo(regla, r, f"{nombre} repetido en {contador[v]} páginas indexables: «{v}»")

        # Tamaño
        if p.bytes > LIMITE_HTML:
            self.fallo("tamano_html", r, f"{p.bytes} bytes: Googlebot solo lee los primeros 2 MB; partir el listado")
        elif p.bytes > AVISO_HTML:
            self.fallo("tamano_html", r, f"{p.bytes} bytes: cerca del límite de 2 MB de Googlebot", "aviso")

        # Huecos de plantilla en el contenido principal
        m = re.search(r"\{\{|\}\}|\{%|%\}|\$\{|\[object Object\]|\b(None|undefined|NaN)\b", p.texto_main)
        if m:
            self.fallo("contenido_html", r, f"hueco de plantilla en el contenido: «…{p.texto_main[max(0, m.start()-30):m.end()+30]}…»")

        # Canónica
        if len(p.canonicas) != 1:
            self.fallo("canonica", r, f"{len(p.canonicas)} etiquetas canónicas (tiene que haber una)")
        else:
            c = urlparse(p.canonicas[0])
            if c.scheme != "https" or c.netloc != self.host:
                self.fallo("canonica", r, f"canónica «{p.canonicas[0]}» fuera de {self.base}")
            elif (c.path or "/") != r or c.query or c.fragment:
                self.fallo("canonica", r, f"canónica «{p.canonicas[0]}» no apunta a sí misma")

        # Directivas de robots
        sin_fragmento = DIRECTIVAS_SIN_FRAGMENTO & p.directivas
        if p.indexable and sin_fragmento:
            self.fallo("indexacion", r, f"{', '.join(sorted(sin_fragmento))}: sin fragmento no sale en los "
                       "resultados con IA de Google (ley, regla 14)")
        if not p.indexable and p.canonicas and urlparse(p.canonicas[0]).path not in (r, ""):
            self.fallo("indexacion", r, "noindex con canónica a otra página: señales contradictorias")
        for d in p.datos:
            if d.sin_fragmento and p.indexable:
                self.fallo("indexacion", r, f"dato «{d.clave}» dentro de data-nosnippet: no sale en el fragmento ni "
                           "en las respuestas con IA")
        if p.hreflang:
            self.fallo("indexacion", r, "lleva hreflang y el sitio solo tiene versión en español", "aviso")

        # Móvil
        if not p.viewport:
            self.fallo("movil", r, "sin <meta name=\"viewport\">")

        # Enlaces
        for e in p.enlaces:
            h = e.href
            if h.lower().startswith("javascript:"):
                self.fallo("enlaces", r, f"enlace con JavaScript en vez de dirección: «{h[:60]}»")
            elif h == "#" or h.startswith("#!") or h.startswith("#/"):
                self.fallo("enlaces", r, f"enlace con almohadilla en vez de dirección real: «{h}» ({e.texto[:40]})")
            elif h.startswith("#"):
                if h[1:] not in p.ids:
                    self.fallo("enlaces", r, f"ancla «{h}» sin destino en la página", "aviso")
            elif h.lower().startswith(("mailto:", "tel:")):
                continue
            else:
                destino = self.interna(h, r)
                if destino is None:
                    continue
                u = urlparse(urljoin(self.base + r, h))
                if u.query:
                    self.fallo("enlaces", r, f"enlace interno con parámetros «{h}»: crea direcciones duplicadas",
                               "aviso")
                if destino in self.redirecciones:
                    self.fallo("enlaces", r, f"enlace a «{destino}», que redirige a «{self.redirecciones[destino][0]}»:"
                               " enlazar la dirección final")
                elif destino.endswith("/index.html"):
                    self.fallo("enlaces", r, f"enlace a «{destino}»: enlazar la dirección «{destino[:-10]}»")
                elif destino not in self.paginas and destino not in self.archivos:
                    if destino + "/" in self.paginas:
                        self.fallo("enlaces", r, f"enlace a «{destino}» sin la barra final (fuerza una redirección)")
                    else:
                        self.fallo("enlaces", r, f"enlace roto a «{destino}»")
                if "nofollow" in e.rel:
                    self.fallo("enlaces", r, f"enlace interno con nofollow a «{destino}»", "aviso")
        if p.sin_href:
            self.fallo("enlaces", r, f"{p.sin_href} elementos que navegan con onclick en vez de <a href>")

        # Ventanas
        for v in p.ventanas:
            self.fallo("ventanas", r, f"ventana visible al cargar (sin el atributo hidden): {v}")

        # Imágenes
        for img in p.imagenes:
            falta = [a for a in ("alt", "width", "height") if a not in img]
            if falta:
                self.fallo("imagenes", r, f"imagen «{img.get('src', '')[:60]}» sin {', '.join(falta)}")

        # Migas de pan en las fichas
        if tipo in FICHAS and p.indexable and len(p.migas) < 2:
            self.fallo("migas", r, f"{len(p.migas)} caminos de migas de pan (la ficha cuelga de dos padres)")

        # Datos estructurados
        self.comprobar_marcado(p, tipo)

        # Texto con IA
        for texto in self.manifiesto.get(r, {}).get("textos_ia", []):
            h = huella_texto(texto)
            if h not in self.aprobadas:
                self.fallo("ia_revisada", r, f"texto con IA sin aprobar ({h[:12]}): «{limpiar(texto)[:60]}»")
            elif not self._aparece(p, texto):
                self.fallo("ia_revisada", r, f"texto con IA aprobado que no está en la página: «{limpiar(texto)[:60]}»",
                           "aviso")

    def _aparece(self, p: Pagina, texto: str) -> bool:
        t = limpiar(texto)
        return (t in p.texto or t in p.titulos or t in p.descripciones
                or any(t == limpiar(i.get("alt", "")) for i in p.imagenes) or any(t in m.texto for m in p.marcados))

    # ------------------------------------------------------------------ datos estructurados
    def comprobar_marcado(self, p: Pagina, tipo: str | None):
        r = p.ruta
        empleos = 0
        for i, m in enumerate(p.marcados):
            problemas = []
            if m.error:
                problemas.append(m.error)
            else:
                elementos = _elementos(m.datos)
                contexto = m.datos.get("@context", "") if isinstance(m.datos, dict) else ""
                if not re.match(r"^https?://schema\.org/?$", str(contexto)):
                    problemas.append(f"@context «{contexto}» no es schema.org")
                for el in elementos:
                    t = el.get("@type")
                    tipos = t if isinstance(t, list) else [t]
                    if "JobPosting" in tipos:
                        empleos += 1
                        problemas += self._jobposting(p, el, tipo)
                    if "BreadcrumbList" in tipos:
                        problemas += self._migas(p, el)
                    for t_sin in set(tipos) & set(MARCADO_SIN_EFECTO):
                        if not (t_sin == "Dataset" and r.startswith("/datos/")):
                            self.fallo("datos_estructurados", r, f"{t_sin}: {MARCADO_SIN_EFECTO[t_sin]}", "aviso")
                    for clave in ("name", "headline", "title"):
                        v = el.get(clave)
                        if isinstance(v, str) and v and limpiar(v) not in p.texto and limpiar(v) not in p.titulos:
                            problemas.append(f"{t}.{clave} «{v[:50]}» no se ve en la página")
            if problemas:
                regla = "jobposting" if any("JobPosting" in x for x in problemas) else "datos_estructurados"
                self.fallo(regla, r, f"bloque {i + 1}: " + "; ".join(problemas))
                self.informe.acciones["quitar_marcado"].append(f"{r}#{i}")
        if empleos > 1:
            self.fallo("jobposting", r, f"{empleos} JobPosting en una página (solo uno, en la ficha del proceso)")
            self.informe.acciones["quitar_marcado"].append(f"{r}#*JobPosting")

    def _jobposting(self, p: Pagina, el: dict, tipo: str | None) -> list[str]:
        problemas = []
        if tipo != "proceso":
            problemas.append(f"JobPosting en una página de tipo «{tipo}» (solo en la ficha del proceso)")
        for clave in ("title", "description", "datePosted", "hiringOrganization", "jobLocation", "validThrough"):
            if not el.get(clave):
                problemas.append(f"JobPosting sin {clave}")
        fin = str(el.get("validThrough") or "")
        if fin:
            try:
                if date.fromisoformat(fin[:10]) < self.hoy:
                    problemas.append(f"JobPosting con plazo cerrado (validThrough {fin})")
            except ValueError:
                problemas.append(f"JobPosting con validThrough «{fin}» que no es una fecha")
        org = el.get("hiringOrganization")
        nombre = org.get("name") if isinstance(org, dict) else None
        if nombre and limpiar(nombre) not in p.texto:
            problemas.append(f"JobPosting: el convocante «{nombre}» no se ve en la página")
        return problemas

    def _migas(self, p: Pagina, el: dict) -> list[str]:
        visibles = {n for camino in p.migas for n in camino}
        problemas = []
        for item in el.get("itemListElement", []) or []:
            nombre = item.get("name") or (item.get("item") or {}).get("name") if isinstance(item, dict) else None
            if nombre and limpiar(nombre) not in visibles and limpiar(nombre) not in p.texto:
                problemas.append(f"miga «{nombre}» que no se ve en la página")
            destino = item.get("item") if isinstance(item, dict) else None
            destino = destino.get("@id") if isinstance(destino, dict) else destino
            if isinstance(destino, str):
                ruta = self.interna(destino, p.ruta)
                if ruta is None or ruta not in self.paginas:
                    problemas.append(f"miga que apunta a «{destino}», que no es una página del sitio")
        return problemas

    # ------------------------------------------------------------------ comprobaciones del sitio
    def comprobar_sitio(self):
        indexables = {r for r, p in self.paginas.items() if p.indexable and r not in self.informe.acciones["noindex"]}

        # Enlaces entrantes
        entrantes: Counter = Counter()
        for r, p in self.paginas.items():
            if r not in indexables:  # Google deja de seguir con el tiempo los enlaces de las páginas noindex
                continue
            for d in {self.interna(e.href, r) for e in p.enlaces} - {None, r}:
                entrantes[d] += 1
        for r in sorted(indexables - {"/"}):
            if not entrantes[r]:
                self.fallo("enlace_entrante", r, "ninguna página del sitio la enlaza")

        # Similitud
        textos = {r: self.paginas[r].texto_main for r in indexables}
        for g in grupos_parecidos(textos, self.umbral):
            muestra = ", ".join(g["paginas"][:5]) + (f" y {len(g['paginas']) - 5} más" if len(g["paginas"]) > 5 else "")
            self.fallo("similitud", g["paginas"][0], f"{len(g['paginas'])} páginas indexables casi iguales "
                       f"(parecido ≥ {g['parecido_minimo']}): {muestra}. Una indexable y el resto noindex, o fusionar")

        # Metodología
        if "/metodologia/" not in self.paginas:
            self.fallo("metodologia", "/metodologia/", "no existe la página de metodología")
        else:
            if "/metodologia/" not in indexables:
                self.fallo("metodologia", "/metodologia/", "la página de metodología no es indexable")
            inicio = self.paginas.get("/")
            if inicio and "/metodologia/" not in {self.interna(e.href, "/") for e in inicio.enlaces}:
                self.fallo("metodologia", "/", "la portada no enlaza la metodología")
            sin = [r for r, p in self.paginas.items() if r != "/metodologia/"
                   and "/metodologia/" not in {self.interna(e.href, r) for e in p.enlaces}]
            if sin:
                self.fallo("metodologia", sin[0], f"{len(sin)} páginas no enlazan la metodología (pie de página)",
                           "aviso")

        self.comprobar_portada()
        self.comprobar_rastreo(indexables)

        # 404
        if not (self.sitio / "404.html").exists():
            self.fallo("pagina_404", "/404.html", "falta 404.html: sin ella el alojamiento puede responder 200 a "
                       "direcciones que no existen")

        self.comprobar_robots(indexables)
        self.comprobar_redirecciones()
        self.comprobar_cabeceras(indexables)
        self.comprobar_sitemaps(indexables)
        self.comprobar_lastmod(indexables)

    def comprobar_portada(self):
        inicio = self.paginas.get("/")
        if inicio is None:
            self.fallo("portada", "/", "no hay portada (index.html en la raíz)", "no_publicar")
            return
        sitio_web = [e for m in inicio.marcados if m.datos for e in _elementos(m.datos)
                     if "WebSite" in (e.get("@type") if isinstance(e.get("@type"), list) else [e.get("@type")])]
        if not sitio_web or not sitio_web[0].get("name") or not sitio_web[0].get("url"):
            self.fallo("portada", "/", "sin WebSite con name y url: Google necesita ese marcado en la portada para "
                       "mostrar el nombre del sitio")
        validos = [i for i in inicio.iconos if urlparse(i).path.lower().endswith(FORMATOS_ICONO)]
        if not validos:
            self.fallo("portada", "/", "sin icono en un formato que Google admite (ICO, PNG, GIF, JPEG…; SVG no): "
                       + (", ".join(inicio.iconos) or "ninguno"))

    def comprobar_rastreo(self, indexables: set[str]):
        total = len(self.paginas)
        sin_indice = total - len(indexables)
        if total >= 50 and sin_indice / total > 0.2:
            self.fallo("rastreo", "/", f"{sin_indice} de {total} páginas son noindex: Google las sigue descargando "
                       "y gastan rastreo; mejor no generarlas hasta que tengan datos")
        por_plantilla: dict[str, list[list[str]]] = defaultdict(list)
        for r in indexables:
            p = self.paginas[r]
            plantilla = self.manifiesto.get(r, {}).get("plantilla") or self.tipo(p)
            if p.titulos:
                por_plantilla[plantilla].append(re.findall(r"\w+", p.titulos[0].lower()))
        for plantilla, titulos in por_plantilla.items():
            if len(titulos) < 20:
                continue
            frecuencia = Counter(t for ts in titulos for t in set(ts))
            fijas = {t for t, n in frecuencia.items() if n >= 0.9 * len(titulos)}
            variables = sorted(len([t for t in ts if t not in fijas]) for ts in titulos)
            if len(fijas) >= 5 and variables[len(variables) // 2] <= 2:
                self.fallo("rastreo", plantilla, f"títulos de la plantilla «{plantilla}» que solo cambian en uno o "
                           f"dos datos ({len(fijas)} palabras fijas): Google los trata como plantilla")

    def comprobar_robots(self, indexables: set[str]):
        archivo = self.sitio / "robots.txt"
        if not archivo.exists():
            self.fallo("robots_txt", "/robots.txt", "falta robots.txt")
            return
        datos = archivo.read_bytes()
        if len(datos) > 500 * 1024:
            self.fallo("robots_txt", "/robots.txt", f"{len(datos)} bytes: Google solo lee los primeros 500 KiB")
        texto = datos.decode("utf-8", errors="replace")
        muestra = sorted(indexables)
        recursos = sorted({urljoin(self.base + p.ruta, u) for p in self.paginas.values() for u in p.recursos
                           if self.interna(u, p.ruta)})
        for robot in ROBOTS_PERMITIDOS:
            rb = Robots(texto, agente=robot)
            prohibidas = [r for r in muestra if not rb.permite(self.base + r)]
            if prohibidas:
                self.fallo("robots_txt", "/robots.txt", f"{robot} no puede rastrear {len(prohibidas)} páginas "
                           f"indexables (por ejemplo {prohibidas[0]}: {rb.regla(self.base + prohibidas[0])[1]})")
            if robot == "Googlebot":
                vetados = [u for u in recursos if not rb.permite(u)]
                if vetados:
                    self.fallo("robots_txt", "/robots.txt", f"Googlebot no puede leer {len(vetados)} recursos "
                               f"(CSS, JS, imágenes) que necesita para ver la página, por ejemplo {vetados[0]}")
        lineas = [l.split("#", 1)[0].strip() for l in texto.splitlines()]
        mapas = [l.split(":", 1)[1].strip() for l in lineas if l.lower().startswith("sitemap:")]
        if not mapas:
            self.fallo("robots_txt", "/robots.txt", "no declara el sitemap (línea «Sitemap:»)")
        for m in mapas:
            u = urlparse(m)
            if u.scheme != "https" or u.netloc != self.host:
                self.fallo("robots_txt", "/robots.txt", f"Sitemap «{m}» no es una dirección absoluta de {self.base}")
            elif u.path not in self.archivos:
                self.fallo("robots_txt", "/robots.txt", f"Sitemap «{m}» no existe en la web generada")
        if any(l.lower().startswith("crawl-delay") for l in lineas):
            self.fallo("robots_txt", "/robots.txt", "Crawl-delay: Google lo ignora y frena a los que lo respetan",
                       "aviso")

    def comprobar_redirecciones(self):
        for origen, (destino, codigo) in sorted(self.redirecciones.items()):
            if codigo not in CODIGOS_PERMANENTES:
                self.fallo("redirecciones", origen, f"código {codigo} (sin código Cloudflare usa 302): tiene que "
                           "ser 301 o 308")
            if "*" in origen or ":" in origen:
                continue
            if origen in self.paginas or origen in self.archivos:
                self.fallo("redirecciones", origen, "redirige una dirección que sigue existiendo como página")
            visto, actual = {origen}, destino
            while actual in self.redirecciones:
                actual = self.redirecciones[actual][0]
                if actual in visto:
                    self.fallo("redirecciones", origen, "bucle de redirecciones")
                    break
                visto.add(actual)
            else:
                if len(visto) > 1:
                    self.fallo("redirecciones", origen, f"cadena de {len(visto)} saltos: redirigir directo a «{actual}»")
                if actual.startswith("/") and actual not in self.paginas and actual not in self.archivos:
                    self.fallo("redirecciones", origen, f"redirige a «{actual}», que no existe")

    def comprobar_cabeceras(self, indexables: set[str]):
        archivo = self.sitio / "_headers"
        if not archivo.exists():
            return
        patron, reglas = None, []
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            if not linea.strip() or linea.lstrip().startswith("#"):
                continue
            if not linea[0].isspace():
                patron = linea.strip()
            elif patron and ":" in linea:
                nombre, valor = (x.strip() for x in linea.split(":", 1))
                if nombre.lower() == "x-robots-tag":
                    reglas.append((patron, valor.lower()))
        for patron, valor in reglas:
            if not re.search(r"noindex|none|nosnippet|max-snippet\s*:\s*0", valor):
                continue
            rx = patron_cloudflare(patron)
            tocadas = sorted(r for r in indexables if rx.match(r))
            if tocadas:
                self.fallo("cabeceras", tocadas[0], f"_headers «{patron}» pone X-Robots-Tag: {valor} a "
                           f"{len(tocadas)} páginas indexables")

    def lastmod(self, p: Pagina) -> str | None:
        return self.manifiesto.get(p.ruta, {}).get("lastmod") or p.actualizado

    def comprobar_sitemaps(self, indexables: set[str]):
        indice = self.sitio / "sitemap.xml"
        if not indice.exists():
            self.fallo("sitemaps", "/sitemap.xml", "falta el índice de sitemaps")
            return
        tipo, entradas, problemas = sm.leer(indice)
        for x in problemas:
            self.fallo("sitemaps", "/sitemap.xml", x)
        archivos = [(indice, entradas)] if tipo == "urlset" else []
        if tipo == "sitemapindex":
            for e in entradas:
                ruta = sm.ruta_de(e.get("loc", ""), self.host)
                if ruta is None or ruta not in self.archivos:
                    self.fallo("sitemaps", "/sitemap.xml", f"sitemap «{e.get('loc')}» no existe en la web generada")
                    continue
                if ruta.count("/") > 1:
                    self.fallo("sitemaps", ruta, "sitemap fuera de la raíz: solo puede listar direcciones de su carpeta",
                               "aviso")
                t, ent, prob = sm.leer(self.sitio / ruta.lstrip("/"))
                for x in prob:
                    self.fallo("sitemaps", ruta, x)
                if t != "urlset":
                    self.fallo("sitemaps", ruta, "un índice dentro de otro índice: Google no lo admite")
                archivos.append((self.sitio / ruta.lstrip("/"), ent))
        vistas: Counter = Counter()
        for archivo, ent in archivos:
            nombre = "/" + archivo.relative_to(self.sitio).as_posix()
            for e in ent:
                loc = e.get("loc", "")
                ruta = sm.ruta_de(loc, self.host)
                if ruta is None:
                    self.fallo("sitemaps", nombre, f"«{loc}» no es una dirección absoluta de {self.base}")
                    continue
                vistas[ruta] += 1
                if ruta not in self.paginas:
                    self.fallo("sitemaps", nombre, f"«{ruta}» no es una página de la web generada")
                elif ruta not in indexables:
                    self.fallo("sitemaps", nombre, f"«{ruta}» está en el sitemap y no es indexable")
                motivo = sm.fecha_valida(e.get("lastmod", ""), self.hoy) if e.get("lastmod") else "sin lastmod"
                if motivo:
                    self.fallo("lastmod", ruta, motivo)
                elif ruta in self.paginas:
                    esperado = self.lastmod(self.paginas[ruta])
                    if esperado and e["lastmod"][:10] != esperado[:10]:
                        self.fallo("lastmod", ruta, f"lastmod {e['lastmod']} en el sitemap y {esperado} en la página")
        for r in sorted(indexables - set(vistas)):
            self.fallo("sitemaps", r, "página indexable que no está en ningún sitemap")
        for r, n in vistas.items():
            if n > 1:
                self.fallo("sitemaps", r, f"aparece {n} veces en los sitemaps", "aviso")

    def comprobar_lastmod(self, indexables: set[str]):
        for r, p in sorted(self.paginas.items()):
            huella, fecha = huella_contenido(p), self.lastmod(p)
            empleo = any("JobPosting" in m.texto for m in p.marcados) and \
                f"{r}#*JobPosting" not in self.informe.acciones["quitar_marcado"]
            self.informe.estado[r] = {"huella": huella, "lastmod": fecha, "indexable": r in indexables,
                                      "empleo": empleo}
            if r in indexables and not fecha:
                self.fallo("lastmod", r, "sin fecha de último cambio (manifiesto o elemento data-actualizado)")
            antes = self.anterior.get(r)
            if not antes or not fecha:
                continue
            if antes["huella"] == huella and antes["lastmod"] != fecha:
                self.fallo("lastmod", r, f"la fecha pasa de {antes['lastmod']} a {fecha} sin que cambie el contenido")
            elif antes["huella"] != huella and antes["lastmod"] == fecha:
                self.fallo("lastmod", r, f"el contenido cambió y la fecha sigue en {fecha}: si cambió un dato, la "
                           "fecha tiene que cambiar", "aviso")

    # ------------------------------------------------------------------ ejecución
    def ejecutar(self) -> Informe:
        if not self.manifiesto:
            self.fallo("ia_revisada", "/", "falta el manifiesto de páginas (tipo, plantilla, lastmod y textos con IA)"
                       ": sin él no se puede saber qué texto escribió la IA")
        titulos = Counter(p.titulos[0] for p in self.paginas.values() if p.indexable and len(p.titulos) == 1)
        descripciones = Counter(p.descripciones[0] for p in self.paginas.values()
                                if p.indexable and len(p.descripciones) == 1)
        for p in self.paginas.values():
            self.comprobar_pagina(p, titulos, descripciones)
        self.comprobar_sitio()
        self.informe.paginas = len(self.paginas)
        self.informe.indexables = sum(1 for p in self.paginas.values() if p.indexable) - len(
            set(self.informe.acciones["noindex"]))
        return self.informe


def patron_cloudflare(patron: str) -> re.Pattern:
    """Patrón de ruta de `_headers` o `_redirects` (`*` cualquier cosa, `:nombre` un tramo) como expresión regular."""
    ruta = urlparse(patron).path if patron.startswith("http") else patron
    partes = re.split(r"(\*|:[A-Za-z_]+)", ruta)
    cuerpo = "".join(".*" if x == "*" else "[^/]+" if x.startswith(":") and len(x) > 1 else re.escape(x)
                     for x in partes)
    return re.compile("^" + cuerpo + "$")


def _elementos(datos) -> list[dict]:
    if isinstance(datos, list):
        return [e for d in datos for e in _elementos(d)]
    if not isinstance(datos, dict):
        return []
    salida = [datos] if "@type" in datos else []
    for e in datos.get("@graph", []) or []:
        salida += _elementos(e)
    return salida


# ---------------------------------------------------------------------- correcciones que manda la ley
META_NOINDEX = '<meta name="robots" content="noindex">'


def poner_noindex(archivo: Path):
    html = archivo.read_text(encoding="utf-8")
    if re.search(r'<meta[^>]+name=["\']robots["\'][^>]*noindex', html, re.I):
        return
    html, n = re.subn(r"(<head[^>]*>)", r"\1" + META_NOINDEX, html, count=1, flags=re.I)
    if n:
        archivo.write_text(html, encoding="utf-8")


def quitar_marcado(archivo: Path, indices: set[int] | None, solo_empleo: bool = False):
    html = archivo.read_text(encoding="utf-8")
    patron = re.compile(r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>.*?</script>\s*", re.S | re.I)
    contador = iter(range(10_000))

    def cambiar(m):
        i = next(contador)
        if solo_empleo:
            return "" if "JobPosting" in m.group(0) else m.group(0)
        return "" if indices is None or i in indices else m.group(0)

    archivo.write_text(patron.sub(cambiar, html), encoding="utf-8")


def aplicar(sitio: Path, informe: Informe, paginas: dict[str, Pagina]):
    for r in sorted(set(informe.acciones["noindex"])):
        poner_noindex(paginas[r].archivo)
    por_pagina: dict[str, set] = defaultdict(set)
    for x in informe.acciones["quitar_marcado"]:
        r, i = x.rsplit("#", 1)
        por_pagina[r].add(i)
    for r, indices in por_pagina.items():
        if "*JobPosting" in indices:
            quitar_marcado(paginas[r].archivo, None, solo_empleo=True)
        numeros = {int(i) for i in indices if i.isdigit()}
        if numeros:
            quitar_marcado(paginas[r].archivo, numeros)


def resumen_texto(informe: Informe) -> str:
    d = informe.como_dict()
    lineas = [f"Control SEO {d['fecha']} · {d['paginas']} páginas · {d['indexables']} indexables · "
              + ("NO SE PUBLICA" if d["bloquea"] else "se puede publicar")]
    for regla, conteo in d["resumen"].items():
        lineas.append(f"- {regla}: " + ", ".join(f"{n} {c}" for c, n in sorted(conteo.items())))
    vistos = Counter()
    for f in informe.fallos:
        if vistos[f.regla] < 3:
            lineas.append(f"  · [{f.consecuencia}] {f.ruta}: {f.detalle}")
        vistos[f.regla] += 1
    return "\n".join(lineas)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Control SEO de la web generada (docs/ley-seo.md)")
    p.add_argument("--sitio", type=Path, required=True)
    p.add_argument("--base", required=True, help="Dirección del sitio, por ejemplo https://dominio.es")
    p.add_argument("--manifiesto", type=Path)
    p.add_argument("--revisiones", type=Path)
    p.add_argument("--estado-anterior", type=Path)
    p.add_argument("--estado-nuevo", type=Path)
    p.add_argument("--umbral", type=float, default=0.9)
    p.add_argument("--hoy", type=date.fromisoformat)
    p.add_argument("--aplicar", action="store_true")
    p.add_argument("--generar-sitemaps", action="store_true")
    p.add_argument("--navegador", action="store_true")
    p.add_argument("--informe", type=Path)
    a = p.parse_args(argv)

    manifiesto = cargar_jsonl(a.manifiesto)
    revisiones = cargar_jsonl(a.revisiones)
    anterior = json.loads(a.estado_anterior.read_text(encoding="utf-8")) if a.estado_anterior and \
        a.estado_anterior.exists() else {}

    def nuevo_control():
        return Control(a.sitio, a.base, manifiesto, revisiones, anterior, a.hoy, a.umbral)

    control = nuevo_control()
    informe = control.ejecutar()
    aplicadas, previos = {"noindex": [], "quitar_marcado": []}, []
    if a.aplicar and (informe.acciones["noindex"] or informe.acciones["quitar_marcado"]):
        aplicar(a.sitio, informe, control.paginas)
        aplicadas = informe.acciones
        previos = [f for f in informe.fallos if f.consecuencia in ("noindex", "sin_marcado")]
    if a.generar_sitemaps:
        control = nuevo_control()  # tras aplicar, el conjunto indexable puede haber cambiado
        indexables = {r: control.lastmod(pg) for r, pg in control.paginas.items() if pg.indexable}
        sm.generar({r: f for r, f in indexables.items() if f}, a.base, a.sitio)
    if a.aplicar or a.generar_sitemaps:
        control = nuevo_control()
        informe = control.ejecutar()
        informe.fallos = previos + informe.fallos  # lo que se corrigió queda en el informe
        if a.aplicar:
            informe.acciones = aplicadas
    if a.navegador:
        from motor.seo.renderizado import comprobar_con_navegador

        informe.fallos += comprobar_con_navegador(a.sitio, control)

    if a.informe:
        a.informe.parent.mkdir(parents=True, exist_ok=True)
        a.informe.write_text(json.dumps(informe.como_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
    if a.estado_nuevo:
        a.estado_nuevo.write_text(json.dumps(informe.estado, ensure_ascii=False, indent=0), encoding="utf-8")
    print(resumen_texto(informe))
    return 1 if informe.bloquea else 0


if __name__ == "__main__":
    sys.exit(main())
