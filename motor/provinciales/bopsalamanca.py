"""BOP de Salamanca: el boletín del día desde su portada (sede de la Diputación).

Formato verificado el 30/10/2026 desde el servidor de España (desde GitHub no responde):
https://sede.diputaciondesalamanca.gob.es/opencms/opencms/sede/BOP/ trae «Boletín del día 30/10/2026» y el sumario en
bloques sangrados: sección («IV. ADMINISTRACIÓN LOCAL»), grupo («Ayuntamientos»), entidad («Calvarrasa de Abajo») y,
por anuncio, el asunto y su PDF (/documentacion/bop/AAAA/AAAAMMDD/BOP-SA-AAAAMMDD-NNN.pdf).

Uso: python -m motor.provinciales.bopsalamanca --salida ruta/
     python -m motor.provinciales.bopsalamanca --historico --max-minutos 30 --salida ruta/
"""

from __future__ import annotations

import html
import re
import sys

from motor.provinciales.portadas import Portada, main as main_portada, seleccionar as sel_portada

BASE = "https://sede.diputaciondesalamanca.gob.es"
RE_FECHA = re.compile(r"<h2>\s*Bolet[ií]n del d[ií]a\s+(\d{2})/(\d{2})/(\d{4})\s*</h2>")
RE_BLOQUE = re.compile(r'<div style="margin-left:(?P<n>\d+)px;margin-top:\d+px">(?P<c>.*?)</div>', re.DOTALL)


def _t(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())


def leer(contenido: bytes) -> dict:
    h = contenido.decode("utf-8", errors="replace")
    f = RE_FECHA.search(h)
    titulos: dict[int, str] = {}
    anuncios = []
    for m in RE_BLOQUE.finditer(h, f.end() if f else 0):
        n, c = int(m.group("n")), m.group("c")
        pdf = re.search(r'href="(/documentacion/bop/[^"]+?-(\d{3})\.pdf)"', c)
        if not pdf:
            titulos = {k: v for k, v in titulos.items() if k < n}
            titulos[n] = _t(c)
            continue
        if pdf.group(2) in ("000", "999"):  # el sumario y el boletín completo
            continue
        niveles = [titulos[k] for k in sorted(titulos) if k < n]
        anuncios.append({"numero_anuncio": pdf.group(2), "seccion": niveles[0] if niveles else None,
                         "grupo": niveles[1] if len(niveles) > 2 else None, "entidad": niveles[-1] if len(niveles) > 1 else None,
                         "titulo": _t(c.split("<br")[0]), "url_pdf": BASE + pdf.group(1)})
    return {"fecha": f"{f.group(3)}-{f.group(2)}-{f.group(1)}" if f else None, "numero": None, "anuncios": anuncios}


PORTADA = Portada(fuente="bopsalamanca", siglas="BOP-SALAMANCA", provincia="Salamanca",
                  url=BASE + "/opencms/opencms/sede/BOP/", nombres=("Boletín Oficial de la Provincia de Salamanca",),
                  leer=leer,
                  # Boletín de cada día (el calendario de la portada lleva a index.jsp?fechaBoletin=AAAA-MM-DD; verificado
                  # desde España para el 28/10/2026 y el 03/01/2022)
                  url_dia=lambda d: f"{BASE}/opencms/opencms/sede/BOP/index.jsp?fechaBoletin={d:%Y-%m-%d}")
FUENTE, SIGLAS, NOMBRES = PORTADA.fuente, PORTADA.siglas, PORTADA.nombres


def seleccionar(filas: list[dict]) -> list[dict]:
    return sel_portada(PORTADA, filas)


def main(argv: list[str] | None = None) -> int:
    return main_portada(PORTADA, argv)


if __name__ == "__main__":
    sys.exit(main())
