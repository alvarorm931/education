"""Sitemaps: se generan desde las páginas indexables y se comprueban contra la ley.

- Uno o varios por sección (primer tramo de la dirección: `oposiciones`, `master`, …), con 50.000 URL como
  máximo cada uno, y un índice `sitemap.xml`. Todos en la raíz: según el protocolo, un sitemap solo puede listar
  direcciones que cuelgan de su carpeta (https://www.sitemaps.org/protocol.html#location).
- `lastmod` es la fecha real del último cambio de los datos de la página. Sin `changefreq` ni `priority`: Google
  los ignora (https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse
from xml.sax.saxutils import escape

from lxml import etree

NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
MAX_URL = 50_000
MAX_BYTES = 50 * 1024 * 1024
FECHA_W3C = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2}))?$")


def seccion(ruta: str) -> str:
    partes = [p for p in ruta.split("/") if p]
    return re.sub(r"[^a-z0-9-]", "", partes[0]) if partes else "inicio"


def generar(lastmod: dict[str, str], base: str, destino: Path, max_url: int = MAX_URL) -> list[str]:
    """Escribe los sitemaps de las rutas indexables con su lastmod (AAAA-MM-DD). Devuelve los archivos escritos."""
    base = base.rstrip("/")
    por_seccion: dict[str, list[str]] = {}
    for ruta in sorted(lastmod):
        por_seccion.setdefault(seccion(ruta), []).append(ruta)
    escritos, indice = [], []
    for nombre, rutas in sorted(por_seccion.items()):
        for n, i in enumerate(range(0, len(rutas), max_url), start=1):
            trozo = rutas[i:i + max_url]
            archivo = f"sitemap-{nombre}-{n}.xml"
            lineas = ['<?xml version="1.0" encoding="UTF-8"?>', f'<urlset xmlns="{NS}">']
            for r in trozo:
                lineas.append(f"<url><loc>{escape(base + r)}</loc><lastmod>{lastmod[r]}</lastmod></url>")
            lineas.append("</urlset>")
            (destino / archivo).write_text("\n".join(lineas) + "\n", encoding="utf-8")
            escritos.append(archivo)
            indice.append((archivo, max(lastmod[r] for r in trozo)))
    lineas = ['<?xml version="1.0" encoding="UTF-8"?>', f'<sitemapindex xmlns="{NS}">']
    for archivo, ultima in indice:
        lineas.append(f"<sitemap><loc>{escape(base)}/{archivo}</loc><lastmod>{ultima}</lastmod></sitemap>")
    lineas.append("</sitemapindex>")
    (destino / "sitemap.xml").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return ["sitemap.xml", *escritos]


def leer(archivo: Path) -> tuple[str, list[dict], list[str]]:
    """(tipo, entradas, problemas). tipo: «urlset», «sitemapindex» o «» si no se puede leer."""
    problemas: list[str] = []
    datos = archivo.read_bytes()
    if len(datos) > MAX_BYTES:
        problemas.append(f"{len(datos)} bytes: más de 50 MB sin comprimir")
    try:
        raiz = etree.fromstring(datos)
    except etree.XMLSyntaxError as e:
        return "", [], [f"XML no válido: {e}"]
    tipo = etree.QName(raiz).localname
    if etree.QName(raiz).namespace != NS:
        problemas.append(f"espacio de nombres «{etree.QName(raiz).namespace}» en vez de {NS}")
    hijo = "url" if tipo == "urlset" else "sitemap"
    entradas = []
    for e in raiz.findall(f"{{{NS}}}{hijo}"):
        entrada = {etree.QName(c).localname: (c.text or "").strip() for c in e}
        entradas.append(entrada)
        for prohibido in ("changefreq", "priority"):
            if prohibido in entrada:
                problemas.append(f"lleva <{prohibido}> (Google lo ignora; la ley no lo usa)")
    if len(entradas) > MAX_URL:
        problemas.append(f"{len(entradas)} entradas: más de 50.000")
    return tipo, entradas, sorted(set(problemas))


def fecha_valida(texto: str, hoy: date) -> str | None:
    """Motivo si el lastmod no vale; None si vale."""
    if not FECHA_W3C.match(texto or ""):
        return f"lastmod «{texto}» no está en formato W3C (AAAA-MM-DD)"
    try:
        dia = datetime.fromisoformat(texto.replace("Z", "+00:00")).date() if "T" in texto else \
            date.fromisoformat(texto)
    except ValueError:
        return f"lastmod «{texto}» no es una fecha"
    if dia > hoy:
        return f"lastmod {texto} en el futuro"
    return None


def ruta_de(loc: str, host: str) -> str | None:
    u = urlparse(loc)
    if u.scheme != "https" or u.netloc != host:
        return None
    return u.path or "/"
