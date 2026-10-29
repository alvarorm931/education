"""Conector del Butlletí Oficial de la Província de Tarragona (BOPT): misma plataforma que el BOPB
(motor/provinciales/diba.py), en https://www.dipta.cat/bopt/web.

Verificado el 29/10/2026 desde GitHub (también para 2022): filtro «Personal: oferta pública, convocatòries,
nomenaments» = tipusAnunci 23. El servidor no envía su certificado intermedio (Sectigo OV R36): está en
motor/certificados/. Los anunciantes vienen en mayúsculas y con el artículo detrás («AJUNTAMENT ALDEA, L'»).

Uso:
  python -m motor.provinciales.bopt --salida ruta/                                   # ayer y hoy
  python -m motor.provinciales.bopt --desde 2022-01-01 --max-minutos 30 --salida ruta/
  python -m motor.provinciales.bopt --textos --max-minutos 30 --salida ruta/
"""

from __future__ import annotations

import re
import sys

from motor.provinciales import diba

BOLETIN = diba.Boletin(
    fuente="bopt", siglas="BOPT", base="https://www.dipta.cat/bopt/web", tipus_personal=23, provincia="Tarragona",
    nombres=("Butlletí Oficial de la Província de Tarragona", "Boletín Oficial de la Provincia de Tarragona"),
    cabecera_pdf=re.compile(
        r"^(?:[AB]|Butlletí Oficial de la Província de Tarragona|BOPT|Data \d{2}-\d{2}-\d{4}|CVE [\w-]+|"
        r"Pàg\. \d+-\d+|https?://(?:www\.)?dipta\.cat\S*|\d+/\d+|Powered by TCPDF.*|Codi Validació:.*|"
        r"Verificació:.*|Document signat electrònicament.*)$"))


def main(argv: list[str] | None = None) -> int:
    return diba.main(BOLETIN, argv)


if __name__ == "__main__":
    sys.exit(main())
