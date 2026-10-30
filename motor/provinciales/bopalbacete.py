"""BOP de Albacete: el boletín del día desde su portada.

Formato verificado el 30/10/2026 desde el servidor de España (desde GitHub no responde): https://bop.dipualba.es/
trae «Boletín Número 126 (28/10/2026)» y el sumario por secciones (p.h5 «Sección tercera. Administración Local»),
entidad o grupo («Ayuntamientos») y entidad («Ossa de Montiel») en span.fw-bold, y por anuncio el asunto
(div.col-12) con el PDF de su página (servicesajax/descargararchivopaginaBOP/N).

Uso: python -m motor.provinciales.bopalbacete --salida ruta/
"""

from __future__ import annotations

import html
import re
import sys

from motor.provinciales.portadas import Portada, main as main_portada, seleccionar as sel_portada

BASE = "https://bop.dipualba.es"
RE_CABECERA = re.compile(r"Bolet[ií]n\s+N[úu]mero\s+(?P<n>\d+)\s*\((?P<d>\d{2})/(?P<m>\d{2})/(?P<a>\d{4})\)")
RE_TOKEN = re.compile(r'<p class="h5">(?P<sec>[^<]+)</p>'
                      r'|<span class="fw-bold">(?P<ent>[^<]+)</span>(?P<tras></li>|<ul)'
                      r'|<div class="col-12">(?P<tit>[^<]+)</div>\s*<div class="col-12 text-end">\s*<a [^>]*href="(?P<pdf>[^"]+descargararchivopaginaBOP/(?P<id>\d+))"')


def _t(s: str) -> str:
    return " ".join(html.unescape(s or "").split())


def leer(contenido: bytes) -> dict:
    h = contenido.decode("utf-8", errors="replace")
    c = RE_CABECERA.search(h)
    seccion = grupo = entidad = None
    anuncios = []
    for m in RE_TOKEN.finditer(h):
        if m.group("sec"):
            seccion, grupo, entidad = _t(m.group("sec")), None, None
        elif m.group("ent"):
            if m.group("tras") == "<ul":
                grupo, entidad = _t(m.group("ent")), None
            else:
                entidad = _t(m.group("ent"))
        else:
            anuncios.append({"numero_anuncio": m.group("id"), "seccion": seccion, "grupo": grupo,
                             "entidad": entidad if grupo and grupo.lower() == "ayuntamientos" else grupo or entidad,
                             "organo": entidad if grupo and grupo.lower() != "ayuntamientos" else None,
                             "titulo": _t(m.group("tit")), "url_pdf": m.group("pdf")})
    return {"numero": c.group("n") if c else None,
            "fecha": f"{c.group('a')}-{c.group('m')}-{c.group('d')}" if c else None, "anuncios": anuncios}


PORTADA = Portada(fuente="bopalbacete", siglas="BOP-ALBACETE", provincia="Albacete", url=BASE + "/",
                  nombres=("Boletín Oficial de la Provincia de Albacete",), leer=leer)
FUENTE, SIGLAS, NOMBRES = PORTADA.fuente, PORTADA.siglas, PORTADA.nombres


def seleccionar(filas: list[dict]) -> list[dict]:
    return sel_portada(PORTADA, filas)


def main(argv: list[str] | None = None) -> int:
    return main_portada(PORTADA, argv)


if __name__ == "__main__":
    sys.exit(main())
