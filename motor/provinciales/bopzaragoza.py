"""BOP de Zaragoza (BOPZ): el boletín del día desde su portada.

Formato verificado el 30/10/2026 desde el servidor de España (desde GitHub no responde): https://bop.dpz.es/BOPZ/
trae el sumario del último boletín: sección (h3 «Sección quinta»), entidad (p.parrafo «AYUNTAMIENTO DE ZARAGOZA») y,
por anuncio, el asunto (a.enlaceEdicto, abreVentanaDetalleEdicto('N')). El número sale de la ruta del boletín completo
(Boletines\\AAAA\\NNN\\bop.pdf) y la fecha, de la cabecera.

Uso: python -m motor.provinciales.bopzaragoza --salida ruta/
"""

from __future__ import annotations

import html
import re
import sys

from motor.extraccion.texto_es import fecha_texto
from motor.provinciales.portadas import Portada, main as main_portada, seleccionar as sel_portada

BASE = "https://bop.dpz.es/BOPZ/"
RE_NUMERO = re.compile(r"UploadServlet\?ruta=Boletines\\+(?P<a>\d{4})\\+(?P<n>\d+)\\+bop\.pdf")
RE_FECHA = re.compile(r"\b(?P<d>\d{1,2}) de (?P<m>[a-záéíóú]+) de (?P<a>\d{4})\b")
RE_TOKEN = re.compile(r"<h3>(?P<sec>[^<]+)</h3>"
                      r'|<div class="small-12 columns">\s*<p class="parrafo"[^>]*>(?P<ent>[^<]+)</p>'
                      r"|<a class=\"enlaceEdicto\"[^>]*abreVentanaDetalleEdicto\('(?P<id>\d+)'\)\">(?P<tit>.*?)</a>", re.DOTALL)


def _t(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())


def leer(contenido: bytes) -> dict:
    h = contenido.decode("latin-1", errors="replace")
    n, f = RE_NUMERO.search(h), RE_FECHA.search(h)
    seccion = entidad = None
    anuncios = []
    for m in RE_TOKEN.finditer(h):
        if m.group("sec") is not None:
            sec = _t(m.group("sec"))
            if sec.lower().startswith(("sección", "seccion", "parte")):
                seccion, entidad = sec, None
        elif m.group("ent") is not None:
            entidad = re.sub(r"\s*\((?:DPZ)\)", "", _t(m.group("ent"))).split(".-")[0].strip()
        elif seccion:
            anuncios.append({"numero_anuncio": m.group("id"), "seccion": seccion, "entidad": entidad,
                             "titulo": _t(m.group("tit")), "url_pdf": None})
    return {"numero": n.group("n") if n else None,
            "fecha": fecha_texto(f.group("d"), f.group("m"), f.group("a")) if f else None, "anuncios": anuncios}


def es_local(x: dict) -> bool:
    """En el BOPZ: tercera, la Diputación; quinta, el Ayuntamiento de Zaragoza; sexta, las demás entidades locales."""
    return (x.get("seccion") or "").lower().replace("ó", "o").startswith(
        ("seccion tercera", "seccion quinta", "seccion sexta"))


PORTADA = Portada(fuente="bopzaragoza", siglas="BOP-ZARAGOZA", provincia="Zaragoza", url=BASE,
                  nombres=("Boletín Oficial de la Provincia de Zaragoza",), leer=leer)
FUENTE, SIGLAS, NOMBRES = PORTADA.fuente, PORTADA.siglas, PORTADA.nombres


def seleccionar(filas: list[dict]) -> list[dict]:
    filas = [{**x, "seccion": f"{x['seccion']} (administración local)" if es_local(x) else x["seccion"]} for x in filas]
    return sel_portada(PORTADA, filas)


def main(argv: list[str] | None = None) -> int:
    return main_portada(PORTADA, argv)


if __name__ == "__main__":
    sys.exit(main())
