"""Conector del Boletín Oficial de la Provincia de Huesca: plataforma SAGA (motor/provinciales/saga.py), en
https://bop.dphuesca.es. Verificado el 29/10/2026 desde GitHub: mismo sumario por día que Granada y Sevilla.

Uso:
  python -m motor.provinciales.bophuesca --salida ruta/                                   # ayer y hoy
  python -m motor.provinciales.bophuesca --desde 2022-01-01 --max-minutos 30 --salida ruta/
  python -m motor.provinciales.bophuesca --textos --max-minutos 30 --salida ruta/
"""

from __future__ import annotations

import re
import sys
from datetime import date

from motor.provinciales import saga

BOLETIN = saga.Boletin(
    fuente="bophuesca", siglas="BOP-HUESCA", base="https://bop.dphuesca.es", provincia="Huesca",
    nombres=("Boletín Oficial de la Provincia de Huesca",), inicio=date(2022, 1, 1),
    cabecera_pdf=re.compile(r"^(?:Boletín Oficial de la Provincia de Huesca|Número \d+ .*|Página \d+.*|"
                            r"BOP-HU-\d{4}-\d+|.*Pág\. \d+|CSV:.*|https?://bop\.dphuesca\.es\S*)$", re.IGNORECASE))


def main(argv: list[str] | None = None) -> int:
    return saga.main(BOLETIN, argv)


if __name__ == "__main__":
    sys.exit(main())
