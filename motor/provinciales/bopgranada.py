"""Conector del Boletín Oficial de la Provincia de Granada: plataforma SAGA (motor/provinciales/saga.py).

El calendario del portal empieza en julio de 2024 (constantes MES_INICIO_SAGA_CALENDARIO_BOP = '6',
ANIO_INICIO_SAGA_CALENDARIO_BOP = '2024' en su página); lo anterior está en el archivo histórico de la Diputación.

Uso:
  python -m motor.provinciales.bopgranada --salida ruta/                                   # ayer y hoy
  python -m motor.provinciales.bopgranada --desde 2024-07-01 --max-minutos 30 --salida ruta/
  python -m motor.provinciales.bopgranada --textos --max-minutos 30 --salida ruta/
"""

from __future__ import annotations

import re
import sys
from datetime import date

from motor.provinciales import saga

BOLETIN = saga.Boletin(
    fuente="bopgranada", siglas="BOP-GRANADA", base="https://bop.dipgra.es", provincia="Granada",
    nombres=("Boletín Oficial de la Provincia de Granada",), inicio=date(2024, 7, 1),
    cabecera_pdf=re.compile(r"^(?:Boletín Oficial de la Provincia de Granada|B\.O\.P\. número \d+.*|Página \d+.*|"
                            r"NÚMERO \d+ .*|BOP-GRA-\d{4}-\d+|.*Pág\. \d+)$", re.IGNORECASE))


def main(argv: list[str] | None = None) -> int:
    return saga.main(BOLETIN, argv)


if __name__ == "__main__":
    sys.exit(main())
