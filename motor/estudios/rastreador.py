"""Rastreador de oferta de posgrado por web: robots.txt, sitemaps y páginas de programa.

Para cada dominio de un centro (universidad, centro adscrito, escuela de negocio...):
  0. parte de la web real del registro; si no responde prueba con «www.» y, si redirige a otro dominio
     (ub.es → ub.edu, uab.es → uab.cat), adopta el destino y lo cuenta como propio;
  1. lee robots.txt de cada servidor que visita (no solo del principal), respeta sus prohibiciones para
     nuestro agente y toma las líneas «Sitemap:»; si robots.txt da error de servidor, no se rastrea (RFC 9309);
  2. recorre los sitemaps (índices, gzip) hasta un tope de URL;
  3. marca las URL que parecen programas de posgrado (máster, MBA, experto, especialista, título propio,
     formación permanente, postgrado, en castellano, catalán, euskera, gallego e inglés) y descarta noticias,
     eventos, blog, preguntas frecuentes, doctorados y ficheros; sin sitemap útil, recorre la portada y sus
     páginas de listado (másteres, posgrado, estudios, oferta) y toma los enlaces a programas;
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
from motor.estudios.censo import dominio_registrado
from motor.http import USER_AGENT

AGENTE = "PortalEstudiosOposiciones"
FUENTE = "web-centros"

PROGRAMA = re.compile(
    r"m[aàá]ster|m%c3%a[01]ster|mba\b|maestr[ií]a|postgrado|posgrado|postgrau|masterra|mestrado|"
    r"t[ií]tulos?[-_ ]propios?|estudis[-_]propis|formaci[oó]n?[-_ ]permanente|formacio[-_]continua|"
    r"experto[-_ ]universitario|especialista[-_ ]universitario|diploma[-_ ]de[-_ ]especializaci[oó]n|executive|"
    r"estudios[-_ ]propios|postgraduate|\bmsc\b|\bllm\b", re.I)
RUIDO = re.compile(
    r"/(noticias?|noticies|news|our-news|actualidad|actualitat|agenda|eventos?|events?|blog|prensa|premsa|press|"
    r"sala-de-prensa|sala-de-premsa|tag|etiqueta|categor[ií]a|category|author|autor|wp-content|feed|comment|"
    r"search|buscar|page/\d+|convocatorias?-de-empleo|faq|preguntas-frecuentes|pmf|contacto|contact|"
    r"experiencias|experiences|testimonios|asignaturas?|assignatures|subjects|becas?|beques|scholarships?|ayudas|"
    r"normativas?|normatives)/"
    r"|masterclass|master-class|mastercard|trabajo[-_]fin[-_]de[-_]m[aá]ster|treball[-_]fi[-_]de[-_]m[aà]ster|"
    r"master-?s?-?(dissertation|thesis)"
    r"|\.(pdf|jpe?g|png|gif|svg|webp|docx?|xlsx?|zip|mp4)$", re.I)
DOCTORADO = re.compile(r"doctorad|doctorat|doktore|\bph\.?d\b", re.I)
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
TITULO_PROGRAMA = re.compile(r"m[aàá]ster|\bmba\b|posgrado|postgrado|postgrau|masterra|mestrado|maestr[ií]a|"
                             r"experto universitario|especialista universitario|diploma de especializaci|executive|"
                             r"\bmsc\b|\bllm\b", re.I)
# Título o enlace que empieza por el tipo de programa («Máster Universitario en…»), no por un plural de listado.
EMPIEZA_PROGRAMA = re.compile(r"^\s*(m[aàá]ster|mba\b|executive|experto universitario|especialista universitario|"
                              r"diploma de especializaci|postgrado en|posgrado en|postgrau en|msc\b|llm\b|masterra)", re.I)
PLURAL_LISTADO = re.compile(r"^\s*(m[aàá]steres|m[aàá]sters|masters\b|postgrados|posgrados|masterrak)", re.I)
# Señales de ficha de programa, por grupos (cuenta cada grupo una vez, en cualquiera de los idiomas).
SENALES = {k: re.compile(v, re.I) for k, v in {
    "creditos": r"\bECTS\b|cr[eé]ditos|cr[eè]dits|\bcredits\b|kreditu",
    "matricula": r"matr[ií]cula|enrol?lment|izen[- ]?ematea",
    "precio": r"\bprecios?\b|\bpreus?\b|\bprices?\b|tuition|\bfees?\b|\bimporte\b|\bcoste\b|prezioa",
    "plazas": r"\bplazas\b|\bplaces\b|\bseats\b|\bprazas\b",
    "titulacion": r"titulaci[oó]n?\b|\btitulación\b|\bdegree\b",
    "admision": r"admisi[oó]n|admissi[oó]|admission|preinscripci[oó]n?|requisitos de acceso|requisits d.acc[eé]s|"
                r"entry requirements|onarpen",
    "plan": r"plan de estudios|pla d.estudis|study plan|curriculum|syllabus|programa acad[eé]mico|temario|"
            r"asignaturas|assignatures|\bsubjects\b|ikasgaiak|materias",
    "salidas": r"salidas profesionales|sortides professionals|career (opportunities|prospects|outcomes)|sa[ií]das profesionais",
    "modalidad": r"modalidad|modalitat|semipresencial|mode of study|study mode|a distancia|distance learning",
    "duracion": r"duraci[oó]n?\b|\bdurada\b|\bduration\b|iraupena",
    "informacion": r"inscr[ií]bete|solicita (m[aá]s )?informaci[oó]n|sol.licita informaci[oó]|request information|"
                   r"apply now|solicitar informaci[oó]n",
    "horario": r"\bhorarios?\b|\bhorari\b|\bschedule\b|\btimetable\b",
}.items()}
NOTICIA = re.compile(r"/(19|20)\d{2}/\d{1,2}/|/(blog|noticias?|news|actualidad|articulos?|opinion|prensa|revista|"
                     r"magazine|tag|etiquetas?|author|autor)/", re.I)
# Señal de oferta en España (descarta centros de otros países con web en español).
ESPANA = re.compile(r"\bECTS\b|€|\beuros?\b|Espa[ñn]a|\+34|\bMadrid\b|\bBarcelona\b|\bValencia\b|\bSevilla\b|"
                    r"\bM[aá]laga\b|\bBilbao\b|\bZaragoza\b|\bMurcia\b|\bGranada\b|\bSalamanca\b|\bValladolid\b|"
                    r"\bAlicante\b|\bC[oó]rdoba\b|\bPalma\b|\bLas Palmas\b|\bTenerife\b|\bA Coru[ñn]a\b|\bVigo\b|"
                    r"\bOviedo\b|\bSantander\b|\bPamplona\b|\bLogro[ñn]o\b|\bC[aá]diz\b|\bHuelva\b|\bJa[eé]n\b|"
                    r"\bAlmer[ií]a\b|\bLe[oó]n\b|\bBurgos\b|\bTarragona\b|\bGirona\b|\bLleida\b|\bCastell[oó]n\b")
COLABORADORES = re.compile(r"entidades?[-_]colaboradoras?|centros?[-_]colaboradores|titulos[-_]propios[-_]entidades|"
                           r"centros?[-_]adscritos|centres?[-_]adscrits|socios[-_]academicos|convenios?[-_]academicos|"
                           r"red[-_]de[-_]centros|centros[-_]asociados|academic[-_]partners|partner[-_](schools|institutions)|"
                           r"escuelas?[-_](asociadas|colaboradoras)|entitats[-_]col[-_.]?laboradores", re.I)
DOC_PRECIO = re.compile(r"(tarifa|precio|honorario|tasas|fees|tuition|matricula|condiciones[-_]economicas|"
                        r"normativa[-_]economica|importe)[^/]*\.(pdf|xlsx?)$", re.I)
ENLACE = re.compile(r'(?is)<a\b[^>]*?href\s*=\s*["\']([^"\'#]+)["\'][^>]*>(.*?)</a>')
LISTADO = re.compile(r"m[aàá]ster|posgrad|postgrad|postgrau|masterra|mestrado|estudios|estudis|ikasketak|oferta|"
                     r"titulaci|formaci|programas|programmes|programs|studies|study|degrees|t[ií]tulos", re.I)
MAX_LISTADOS = 8
MAX_COLABORADORES = 4  # páginas de centros colaboradores que se abren para ver a quién enlazan
RESERVA_PORTADA = 14  # peticiones que el recorrido de sitemaps deja libres para la portada y sus listados
GUIA = re.compile(r"gu[ií]a|folleto|brochure|dossier|programa|plan de estudios|syllabus", re.I)


def _origen(url: str) -> str:
    u = urlparse(url)
    return f"{u.scheme or 'https'}://{u.netloc}".lower()


def texto_de(r) -> str:
    """Texto de una respuesta con la codificación correcta: la de la cabecera, la de <meta charset> o UTF-8.
    (requests supone ISO-8859-1 si la cabecera no la dice y deja «MÃ¡ster» donde pone «Máster».)"""
    ctype = (r.headers.get("content-type") or "").lower()
    if "charset=" in ctype:
        return r.text
    cabeza = r.content[:4096].decode("ascii", "ignore")
    m = re.search(r"(?i)<meta[^>]+charset=[\"']?([\w-]+)", cabeza) or re.search(r'(?i)encoding=["\']([\w-]+)', cabeza)
    for cod in ([m.group(1)] if m else []) + ["utf-8", "cp1252"]:
        try:
            return r.content.decode(cod)
        except (LookupError, UnicodeDecodeError):
            continue
    return r.content.decode("utf-8", "replace")


class Dominio:
    """Lector cortés de un dominio: robots.txt de cada servidor, una petición por segundo, originales archivados."""

    def __init__(self, base: str, archivo: Archivo | None, pausa: float = 1.0, max_peticiones: int = 80):
        p = urlparse(base if base.startswith("http") else "https://" + base)
        self.base = f"{p.scheme or 'https'}://{p.netloc}"
        self.host = p.netloc
        self.propios = {dominio_registrado(p.netloc)}  # dominios registrados que cuentan como web del centro
        self.archivo = archivo
        self.pausa = pausa
        self.max_peticiones = max_peticiones
        self.peticiones = 0
        self.ultimo = 0.0
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": f"{USER_AGENT}", "Accept-Language": "es-ES,es;q=0.9"})
        self.robots: dict[str, RobotFileParser] = {}
        self.ultima_robots = None
        self.estados: Counter = Counter()  # códigos HTTP y errores de conexión, para diagnosticar

    def propio(self, url: str) -> bool:
        return dominio_registrado(urlparse(url).netloc) in self.propios

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
        except requests.RequestException as e:
            self.estados[type(e).__name__] += 1
            return None
        self.estados[str(r.status_code)] += 1
        if self.archivo is not None and r.status_code == 200 and not guardar:
            self.archivo.registrar(FUENTE, date.today(), r.content, url, r.status_code)
        elif self.archivo is not None and r.status_code == 200 and len(r.content) < 15_000_000:
            ext = "xml" if "xml" in r.headers.get("content-type", "") or url.endswith((".xml", ".gz")) else "html"
            self.archivo.guardar(FUENTE, date.today(), r.content, url, ext, r.status_code,
                                 {k: v for k, v in r.headers.items() if k.lower() in {"content-type", "last-modified", "date"}})
        return r

    def robots_ok_para(self, url: str) -> bool:
        """robots.txt es de cada servidor: antes de la primera página de un servidor se lee el suyo."""
        clave = _origen(url)
        if clave not in self.robots:
            if self.peticiones >= self.max_peticiones:
                return False
            self.leer_robots(clave)
        try:
            return self.robots[clave].can_fetch(AGENTE, url)
        except Exception:
            return True

    def leer_robots(self, origen: str | None = None) -> list[str]:
        """Lee y guarda las reglas de un servidor. Devuelve sus líneas «Sitemap:».
        Error de servidor o sin respuesta: no se rastrea; 4xx o fichero que no es de texto: sin restricciones."""
        origen = (origen or self.base).rstrip("/").lower()
        r = self.get(origen + "/robots.txt", sin_robots=True)
        rp, sitemaps = RobotFileParser(), []
        if r is None or r.status_code >= 500:
            rp.disallow_all = True
        elif r.status_code == 200 and "html" not in (r.headers.get("content-type") or "text/plain").lower():
            lineas = texto_de(r).splitlines()
            rp.parse(lineas)
            sitemaps = [l.split(":", 1)[1].strip() for l in lineas if l.lower().startswith("sitemap:")]
        else:
            rp.parse([])
        self.robots[origen] = rp
        final = getattr(r, "url", "") if r is not None else ""
        if final and _origen(final) != origen and urlparse(final).path.endswith("/robots.txt"):
            self.robots.setdefault(_origen(final), rp)  # redirigido al robots.txt de otro servidor: vale para él
        self.ultima_robots = r
        return sitemaps

    def resolver_base(self) -> tuple[list[str], bool]:
        """Encuentra el servidor que responde: la web dada, si no con «www.»; adopta el destino de las
        redirecciones (y su dominio registrado como propio). Devuelve (sitemaps de robots.txt, responde)."""
        u = urlparse(self.base)
        otro = u.netloc[4:] if u.netloc.startswith("www.") else "www." + u.netloc
        # la web dada, con y sin www., y por http (certificados que no cubren el nombre antiguo)
        candidatos = list(dict.fromkeys([self.base, f"https://{otro}", f"http://{u.netloc}", f"http://{otro}"]))
        for c in candidatos:
            sitemaps = self.leer_robots(c)
            r = self.ultima_robots
            if r is None or r.status_code >= 500:
                continue
            final = _origen(getattr(r, "url", "") or c)
            if final != c.lower():
                if not urlparse(r.url).path.endswith("/robots.txt"):  # redirigió a una página: robots del destino
                    sitemaps = self.leer_robots(final)
                self.propios.add(dominio_registrado(final))
            self.base = final
            return sitemaps, True
        return [], False


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


def fechas_de_sitemap(raiz: ET.Element) -> dict[str, str]:
    """URL → lastmod de un sitemap (para saber qué fichas han cambiado sin descargarlas)."""
    fechas = {}
    for url in raiz.iter():
        if url.tag.endswith("}url") or url.tag == "url":
            loc = next((c.text.strip() for c in url if c.tag.endswith("loc") and c.text), None)
            mod = next((c.text.strip() for c in url if c.tag.endswith("lastmod") and c.text), None)
            if loc and mod:
                fechas[loc] = mod
    return fechas


def reserva_tdm(cabeceras: dict, html: str) -> bool:
    """Reserva expresa de minería de textos y datos (art. 4 Directiva 2019/790; TDMRep)."""
    if str(cabeceras.get("tdm-reservation", cabeceras.get("TDM-Reservation", ""))).strip() == "1":
        return True
    return bool(re.search(r'(?is)<meta[^>]+name="tdm-reservation"[^>]+content="1"', html or ""))


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
    tramos = [t for t in u.path.split("/") if t]
    return bool(PROGRAMA.search(ruta)) and not RUIDO.search(u.path) and not DOCTORADO.search(tramos[-1] if tramos else "")


FICHA_URL = re.compile(r"m[aàá]ster[-_](universitari[oa]?|en|in|de|of|oficial)[-_]|\bmba[-_]|experto[-_]|especialista[-_]|"
                       r"postgrado[-_]en|posgrado[-_]en|postgrau[-_]en|/mu[-_]|master-of|msc[-_]", re.I)
BAJO_LISTADO = re.compile(r"/(m[aàá]steres|masters?|masters-universitarios|postgrados?|posgrados?|programas)/[^/]+/?$", re.I)
GENERICA = re.compile(r"normativa|admisi|admissi|matr[ií]cula|precios?|tasas|becas?|calendario|preguntas|faq|acceso|"
                      r"requisitos|informaci|idiomas|oferta|listado|buscador|preinscrip|ayudas|erasmus|ranking|"
                      r"portada|home|index", re.I)


def prioridad_url(url: str) -> int:
    """Más alto cuanto más parece la ficha de un programa concreto (y no un listado o una página general)."""
    ruta = urlparse(url).path.lower()
    tramos = [t for t in ruta.split("/") if t]
    ultimo = tramos[-1] if tramos else ""
    puntos = (2 if FICHA_URL.search(ruta) else 0) + (1 if BAJO_LISTADO.search(ruta) else 0)
    puntos += 1 if len(tramos) >= 2 and len(ultimo) > 12 else 0
    return puntos - (3 if GENERICA.search(ultimo) else 0)


def enlaces(html: str, base_url: str) -> list[tuple[str, str]]:
    """(URL absoluta, texto del enlace) de una página."""
    salida = []
    for h, t in ENLACE.findall(html):
        u = urljoin(base_url, h.strip()).split("#")[0]
        if u.startswith("http"):
            salida.append((u, " ".join(re.sub(r"<[^>]+>", " ", t).split())[:200]))
    return salida


def nombra_programa(texto: str) -> bool:
    """«Máster Universitario en X», «MBA Executive»…; no «Másteres» ni «Postgrados» (listados)."""
    return bool(EMPIEZA_PROGRAMA.match(texto or "")) and not PLURAL_LISTADO.match(texto or "")


def enlace_a_programa(url: str, texto: str) -> bool:
    """Por la URL, o por un texto de enlace que nombra un programa concreto («Máster Universitario en…»)."""
    if es_programa(url):
        return True
    ruta = urlparse(url).path
    return (nombra_programa(texto) and len(texto.split()) >= 3
            and not DOCTORADO.search(texto) and not RUIDO.search(ruta) and not NOTICIA.search(ruta))


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
    senales = {k for k, pat in SENALES.items() if pat.search(visible)}
    nombre = " ".join(re.sub(r"<[^>]+>", " ", h1.group(1)).split()) if h1 else (titulo.group(1) if titulo else "")
    fuerte = nombra_programa(nombre) or nombra_programa(titulo.group(1) if titulo else "")
    caracteres = len(" ".join(visible.split()))
    poco_texto = caracteres < 2000  # contenido cargado con JavaScript: el HTML trae poco más que el menú
    motivo = None
    if not NOTICIA.search(urlparse(url).path) and not DOCTORADO.search(cabecera):
        if TITULO_PROGRAMA.search(cabecera) and (len(senales) >= 4 or (fuerte and len(senales) >= 3)):
            motivo = "titulo_y_senales"
        elif es_programa(url) and len(senales) >= 5:
            motivo = "url_y_senales"  # p. ej. uji.es/estudis/base/2026/masters/historia-art/, título sin «Máster»
        elif fuerte and poco_texto:
            motivo = "titulo_con_contenido_en_js"
    es_prog = motivo is not None
    return {
        "espana": bool(ESPANA.search(visible)),
        "es_programa": es_prog,
        "motivo": motivo,
        "caracteres_visibles": caracteres,
        "senales": sorted(senales)[:12],
        "titulo": " ".join(titulo.group(1).split())[:200] if titulo else None,
        "jsonld_tipos": tipos,
        "precio_jsonld": precio_ld,
        "importes_euros": len(EURO.findall(visible)),
        "temas": {k: bool(p.search(visible)) for k, p in TEMAS.items()},
        "formulario_pide_correo": pide_datos,
        "formulario_pide_telefono": pide_tel,
        "pdf_guia_o_folleto": [u for u, t in pdfs if GUIA.search(t) or GUIA.search(u)][:10],
        "pdf_precio": [u for u, t in pdfs if DOC_PRECIO.search(u) or re.search(r"tarifa|precio|honorario|tasas", t, re.I)][:10],
        "bytes": len(html),
    }


def _html(r) -> str | None:
    if r is None or r.status_code != 200 or "html" not in (r.headers.get("content-type") or ""):
        return None
    return texto_de(r)


def desde_portada(d: Dominio, semillas: list[str] | None, tope: int) -> tuple[list[str], list[str]]:
    """Sin sitemap útil: enlaces a programas de la portada y de sus páginas de listado (másteres, posgrado,
    estudios, oferta), más las semillas de Common Crawl. Devuelve (programas, listados visitados)."""
    programas = {u for u in (semillas or []) if es_programa(u) and d.propio(u)}
    r0 = d.get(d.base + "/")
    html0 = _html(r0)
    listados: list[tuple[int, int, str]] = []
    if html0:
        for u, t in enlaces(html0, r0.url):
            if not d.propio(u):
                continue
            ruta = urlparse(u).path
            if enlace_a_programa(u, t):
                programas.add(u)
            if (LISTADO.search(ruta) or LISTADO.search(t)) and not RUIDO.search(ruta) and not NOTICIA.search(ruta) \
                    and ruta.count("/") <= 4:
                prioridad = 0 if re.search(r"m[aàá]ster|posgrad|postgrad|postgrau|masterra", ruta + " " + t, re.I) else 1
                listados.append((prioridad, len(u), u))
    visitados = []
    for _, _, u in sorted(set(listados))[:MAX_LISTADOS]:
        if d.peticiones >= tope:
            break
        r1 = d.get(u)
        html1 = _html(r1)
        if not html1:
            continue
        visitados.append(u)
        hallados = {v for v, t in enlaces(html1, r1.url) if d.propio(v) and enlace_a_programa(v, t)}
        programas |= hallados
        if len(hallados) >= 5:  # es un listado, no una ficha: no se cuenta como programa
            programas.discard(u)
    return sorted(programas), visitados


def enlaces_externos(d: Dominio, paginas: list[str], tope: int) -> list[str]:
    """Dominios ajenos enlazados desde las páginas de colaboradores (academias que venden sus títulos)."""
    from motor.estudios.censo import AGREGADORES  # redes sociales, medios y directorios no son colaboradores
    externos = set()
    for u in paginas[:MAX_COLABORADORES]:
        if d.peticiones >= tope:
            break
        r = d.get(u)
        html = _html(r)
        if not html:
            continue
        for v, _ in enlaces(html, r.url):
            dom = dominio_registrado(urlparse(v).netloc)
            if "." in dom and dom not in d.propios and not AGREGADORES.search(dom) and \
                    not re.search(r"google|apple|microsoft|whatsapp|t\.me|tiktok|x\.com|gob\.es|europa\.eu|w3\.org", dom):
                externos.add(dom)
    return sorted(externos)[:300]


def medir_muestra(d: Dominio, urls: list[str], n: int) -> list[dict]:
    medidas = []
    for u in _muestra(urls, n):
        r = d.get(u)
        html = _html(r)
        if not html:
            continue
        m = medir_pagina(html, u)
        m["reserva_tdm"] = reserva_tdm(dict(r.headers), html)
        medidas.append({"url": u, **m})
    return medidas


def _verificado(medidas: list[dict]) -> bool:
    validas = sum(1 for m in medidas if m.get("es_programa"))
    return validas >= 2 or (validas == 1 and len(medidas) <= 2)


def rastrear(base: str, archivo: Archivo | None, max_urls: int = 60000, muestra: int = 6,
             max_peticiones: int = 80, semillas: list[str] | None = None, pausa: float = 1.0) -> dict:
    d = Dominio(base, archivo, pausa=pausa, max_peticiones=max_peticiones)
    res: dict = {"dominio": d.host, "base": d.base}
    try:
        sitemaps, responde = d.resolver_base()
        res["base_final"] = d.base
        res["dominios_propios"] = sorted(d.propios)
        if not responde:
            res["error"] = "sin_respuesta"
            res["peticiones"] = d.peticiones
            res["estados_http"] = dict(d.estados)
            return res
        res["veto_robots"] = not d.robots_ok_para(d.base + "/")
        res["robots_sitemaps"] = len(sitemaps)
        rt = d.get(d.base + "/.well-known/tdmrep.json", guardar=False)
        res["tdmrep"] = bool(rt is not None and rt.status_code == 200 and '"tdm-reservation": 1' in rt.text.replace("'", '"'))
        if not sitemaps:
            sitemaps = [d.base + "/sitemap.xml", d.base + "/sitemap_index.xml"]
        cola = sorted(dict.fromkeys(sitemaps), key=prioridad_sitemap)
        vistos, paginas, leidos, fechas = set(), [], 0, {}
        tope_sitemaps = max_peticiones - muestra - RESERVA_PORTADA
        while cola and len(paginas) < max_urls and d.peticiones < tope_sitemaps:
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
            fechas.update(fechas_de_sitemap(raiz))
            cola = sorted(dict.fromkeys(cola + [h for h in hijos if h not in vistos]), key=prioridad_sitemap)
            paginas.extend(urls)
        res["sitemaps_leidos"] = leidos
        res["sitemaps_pendientes"] = len(cola)
        res["urls"] = len(paginas)
        candidatas = sorted({u for u in paginas if es_programa(u) and d.propio(u)})
        res["urls_programa_sitemap"] = len(candidatas)
        # Páginas que nombran a centros colaboradores (p. ej. ucavila.es/titulos-propios-entidades/...):
        # sirven para descubrir escuelas que venden títulos propios de la universidad.
        res["urls_colaboradores"] = sorted({u for u in paginas if COLABORADORES.search(urlparse(u).path)
                                            and not NOTICIA.search(urlparse(u).path)})[:200]
        res["via"] = "sitemap" if candidatas else "portada"
        listados: list[str] = []
        if not candidatas:
            candidatas, listados = desde_portada(d, semillas, max_peticiones - muestra)
        medidas = medir_muestra(d, candidatas, muestra)
        if not _verificado(medidas) and res["via"] == "sitemap":
            # el sitemap trae URL de programa pero la muestra no convence (noticias, listados): se mira la portada
            medidas_urls = {m["url"] for m in medidas}
            extra, listados = desde_portada(d, semillas, max_peticiones - muestra)
            extra = [u for u in extra if u not in medidas_urls and u not in set(candidatas)]
            if extra:
                res["via"] = "sitemap+portada"
                medidas += medir_muestra(d, extra, muestra)
                candidatas = sorted(set(candidatas) | set(extra))
        res["listados_visitados"] = listados
        res["urls_programa"] = len(candidatas)
        res["programas"] = candidatas
        res["programas_lastmod"] = {u: fechas[u] for u in candidatas if u in fechas}
        res["documentos_precio"] = sorted({u for u in paginas if DOC_PRECIO.search(u) and d.propio(u)
                                           and not NOTICIA.search(urlparse(u).path)})[:100]
        res["muestra"] = medidas
        res["enlaces_colaboradores"] = enlaces_externos(d, res["urls_colaboradores"], max_peticiones)
        res["paginas_programa_validas"] = sum(1 for m in medidas if m.get("es_programa"))
        res["verificado"] = _verificado(medidas)
        res["espana"] = any(m.get("espana") for m in medidas if m.get("es_programa"))
        res["reserva_tdm"] = res.get("tdmrep", False) or any(m.get("reserva_tdm") for m in medidas)
    except Exception as e:  # un dominio roto no para el resto
        res["error"] = f"{type(e).__name__}: {e}"[:300]
    res["peticiones"] = d.peticiones
    res["estados_http"] = dict(d.estados)
    return res


def _repartida(urls: list[str], n: int) -> list[str]:
    if len(urls) <= n:
        return urls
    paso = len(urls) / n
    return [urls[int(i * paso)] for i in range(n)]


def _muestra(urls: list[str], n: int) -> list[str]:
    """Muestra repartida a lo largo de la lista, primero entre las URL con más pinta de ficha concreta
    (evita coger solo listados, normativas o la primera sección del sitio)."""
    if len(urls) <= n:
        return urls
    mejores = sorted({prioridad_url(u) for u in urls}, reverse=True)
    elegidas: list[str] = []
    for nivel in mejores:
        grupo = [u for u in urls if prioridad_url(u) == nivel]
        elegidas += _repartida(grupo, n - len(elegidas))
        if len(elegidas) >= n:
            break
    return elegidas


def objetivos_de_proveedores(fichero: Path, desde: int = 0, hasta: int | None = None,
                             estados: tuple = ("oficial", "candidato")) -> list[dict]:
    """Proveedores del censo único (motor/estudios/censo.py) en un tramo de la lista."""
    filas = [json.loads(l) for l in fichero.read_text(encoding="utf-8").splitlines() if l.strip()]
    filas = [p for p in filas if p["estado"] in estados][desde:hasta]
    return [{"web": web_principal(p), "id": p["id"], "estado": p["estado"],
             "semillas": p.get("senales", {}).get("cc_ejemplos", [])} for p in filas]


def web_principal(p: dict) -> str:
    """La web real del registro (p. ej. https://www.ub.edu) antes que el dominio desnudo, que a veces no
    responde; entre varias, la del propio dominio y más corta (la de la universidad, no la de un centro)."""
    webs = p.get("webs") or []
    if not webs:
        return "https://" + p["dominio"]

    def clave(w: str) -> tuple:
        u = urlparse(w)
        return (u.netloc.lower().removeprefix("www.") != p["dominio"], len([t for t in u.path.split("/") if t]), len(w))
    return min(webs, key=clave)


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
            resumen["sin_respuesta"] += 1 if r.get("error") == "sin_respuesta" else 0
            resumen["veto_robots"] += 1 if r.get("veto_robots") else 0
            resumen["redirigidos_a_otro_dominio"] += 1 if len(r.get("dominios_propios", [])) > 1 else 0
            resumen["verificados"] += 1 if r.get("verificado") else 0
            resumen["verificados_espana"] += 1 if r.get("verificado") and r.get("espana") else 0

    with ThreadPoolExecutor(max_workers=hilos) as ex:
        list(ex.map(uno, objetivos))
    return dict(resumen)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dominios", help="webs separadas por comas")
    p.add_argument("--censo", help="carpeta datos/estudios/centros del censo del RUCT")
    p.add_argument("--proveedores", help="proveedores.jsonl del censo único")
    p.add_argument("--tramo", default="0:", help="tramo de la lista de proveedores, p. ej. 0:800")
    p.add_argument("--estados", default="oficial,candidato", help="estados del censo a rastrear")
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
        objetivos = objetivos_de_proveedores(Path(a.proveedores), int(d or 0), int(h) if h else None,
                                             tuple(a.estados.split(",")))
    elif a.censo:
        objetivos = dominios_del_censo(Path(a.censo))
    else:
        sys.exit("Falta --dominios o --censo")
    print(json.dumps(ejecutar(objetivos, Path(a.salida), a.hilos, a.max_minutos, a.muestra, a.solo_huella), ensure_ascii=False))


if __name__ == "__main__":
    main()
