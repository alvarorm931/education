"""Conector del Butlletí Oficial de la Província de Barcelona (BOPB): plataforma común en motor/provinciales/diba.py.

Desde el 30/10/2026, por su robots.txt, se lee el canal RSS de datos abiertos del boletín del día; los anuncios de
personal son los de tipo «Personal | …». Sin textos: los PDF están prohibidos a los programas.

Uso:
  python -m motor.provinciales.bopb --salida ruta/         # boletín del día
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

from motor.archivo import Archivo
from motor.provinciales import diba

BOLETIN = diba.Boletin(
    fuente="bopb", siglas="BOPB", base="https://bop.diba.cat", tipus_personal=60, provincia="Barcelona",
    feed="https://bop.diba.cat/dades-obertes/butlleti-del-dia/feed",
    nombres=("Butlletí Oficial de la Província de Barcelona", "Boletín Oficial de la Provincia de Barcelona"),
    cabecera_pdf=re.compile(
        r"^(?:[AB]|Butlletí Oficial de la Província de Barcelona|Data \d{2}-\d{2}-\d{4}|CVE \d+|Pàg\. \d+-\d+|"
        r"https://bop\.diba\.cat|\d+/\d+|Powered by TCPDF.*|Codi Validació:.*|Verificació:.*|"
        r"Document signat electrònicament.*)$"))
FUENTE, SIGLAS, NOMBRES, RE_CABECERA_PDF = BOLETIN.fuente, BOLETIN.siglas, BOLETIN.nombres, BOLETIN.cabecera_pdf


def url_dia(d: date, pagina: int = 1) -> str:
    return BOLETIN.url_dia(d, pagina)


def parsear_dia(contenido: str) -> dict:
    return diba.parsear_dia(BOLETIN, contenido)


def seleccionar(anuncios: list[dict]) -> list[dict]:
    return diba.seleccionar(BOLETIN, anuncios)


def procesar_dia(d: date, raiz: Path, archivo: Archivo, pausa: float = 1.0) -> dict:
    return diba.procesar_dia(BOLETIN, d, raiz, archivo, pausa)


def texto_disposicion(contenido: bytes, con_texto: bool = True) -> dict:
    return diba.texto_disposicion(BOLETIN, contenido, con_texto)


def main(argv: list[str] | None = None) -> int:
    return diba.main(BOLETIN, argv)


if __name__ == "__main__":
    sys.exit(main())
