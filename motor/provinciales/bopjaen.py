"""BOP de Jaén: el boletín del día desde su portada.

Formato verificado el 30/10/2026 desde el servidor de España (desde GitHub no responde): https://bop.dipujaen.es/
trae el sumario del día: sección (p.seccion «Administración Local»), entidad (p.subseccion «AYUNTAMIENTO DE ALCAUDETE
(JAÉN)»), departamento (p.departamento) y, por anuncio, el asunto (p.edicto) y su PDF
(descargarws.dip?fechaBoletin=AAAA-MM-DD&numeroEdicto=N…). El número y la fecha salen del enlace al sumario.

Uso: python -m motor.provinciales.bopjaen --salida ruta/
"""

from __future__ import annotations

import html
import re
import sys

from motor.provinciales.portadas import Portada, main as main_portada, seleccionar as sel_portada

BASE = "https://bop.dipujaen.es"
RE_SUMARIO = re.compile(r"fechaBoletin=(?P<f>\d{4}-\d{2}-\d{2})&(?:amp;)?ejercicioBop=\d{4}&(?:amp;)?numeroBoletin=(?P<n>\d+)")
RE_TOKEN = re.compile(r"<p class='seccion'>(?P<sec>.*?)</p>|<p class='subseccion'>(?P<ent>.*?)</p>"
                      r"|<p class='departamento'>(?P<dep>.*?)</p>"
                      r"|<p class='edicto'>(?P<tit>.*?)</p>\s*<p[^>]*>\s*<a\s+href='(?P<pdf>[^']+numeroEdicto=(?P<id>\d+)[^']*)'", re.DOTALL)


def _t(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())


def leer(contenido: bytes) -> dict:
    h = contenido.decode("latin-1", errors="replace")
    c = RE_SUMARIO.search(h)
    seccion = entidad = dep = None
    anuncios = []
    for m in RE_TOKEN.finditer(h):
        if m.group("sec") is not None:
            seccion, entidad, dep = _t(m.group("sec")), None, None
        elif m.group("ent") is not None:
            entidad, dep = re.sub(r"\s*\(JA[EÉ]N\)$", "", _t(m.group("ent"))), None
        elif m.group("dep") is not None:
            dep = _t(m.group("dep"))
        else:
            anuncios.append({"numero_anuncio": m.group("id"), "seccion": seccion, "entidad": entidad, "organo": dep,
                             "titulo": _t(m.group("tit")), "url_pdf": html.unescape(m.group("pdf"))})
    return {"fecha": c.group("f") if c else None, "numero": c.group("n") if c else None, "anuncios": anuncios}


PORTADA = Portada(fuente="bopjaen", siglas="BOP-JAEN", provincia="Jaén", url=BASE + "/",
                  nombres=("Boletín Oficial de la Provincia de Jaén",), leer=leer)
FUENTE, SIGLAS, NOMBRES = PORTADA.fuente, PORTADA.siglas, PORTADA.nombres


def seleccionar(filas: list[dict]) -> list[dict]:
    return sel_portada(PORTADA, filas)


def main(argv: list[str] | None = None) -> int:
    return main_portada(PORTADA, argv)


if __name__ == "__main__":
    sys.exit(main())
