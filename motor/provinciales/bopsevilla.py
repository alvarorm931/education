"""Conector del Boletín Oficial de la Provincia de Sevilla: plataforma SAGA (motor/provinciales/saga.py),
en https://bopsevilla.dipusevilla.es.

Uso:
  python -m motor.provinciales.bopsevilla --salida ruta/                                   # ayer y hoy
  python -m motor.provinciales.bopsevilla --desde 2022-01-01 --max-minutos 30 --salida ruta/
  python -m motor.provinciales.bopsevilla --textos --max-minutos 30 --salida ruta/
"""

from __future__ import annotations

import re
import sys
from datetime import date

from motor.provinciales import saga

BOLETIN = saga.Boletin(
    fuente="bopsevilla", siglas="BOP-SEVILLA", base="https://bopsevilla.dipusevilla.es", provincia="Sevilla",
    nombres=("Boletín Oficial de la Provincia de Sevilla",), inicio=date(2022, 1, 1),
    cabecera_pdf=re.compile(r"^(?:Boletín Oficial de la Provincia de Sevilla|Número \d+ .*|Página \d+.*|"
                            r"BOP-SE-\d{4}-\d+|.*Pág\. \d+|CVE: BOP-SE-\d{4}-\d+.*)$", re.IGNORECASE))


def main(argv: list[str] | None = None) -> int:
    return saga.main(BOLETIN, argv)


if __name__ == "__main__":
    sys.exit(main())
