"""BOP de Girona (Butlletí Oficial de la Província de Girona), plataforma «mostra-bop» (motor/provinciales/mostrabop.py).

robots.txt de www.ddgi.cat cierra /bop; se lee como boletín oficial (motor/http.py, decisión del 30/10/2026).

Uso:
  python -m motor.provinciales.bopgirona --salida ruta/                                  # lo nuevo
  python -m motor.provinciales.bopgirona --desde 2022-01-01 --max-minutos 30 --salida ruta/
"""

from __future__ import annotations

import sys

from motor.provinciales import mostrabop as m
from motor.provinciales.mostrabop import parsear_boletin, ultimo  # noqa: F401  (las usan las pruebas)

PLATAFORMA = m.Plataforma(fuente="bopgirona", siglas="BOP-GIRONA", provincia="Girona", web="https://www.ddgi.cat",
                          nombres=("Boletín Oficial de la Provincia de Girona",
                                   "Butlletí Oficial de la Província de Girona"))
FUENTE, SIGLAS, NOMBRES = PLATAFORMA.fuente, PLATAFORMA.siglas, PLATAFORMA.nombres
url_boletin = PLATAFORMA.url_boletin


def seleccionar(filas: list[dict]) -> list[dict]:
    return m.seleccionar(PLATAFORMA, filas)


def main(argv: list[str] | None = None) -> int:
    return m.main(PLATAFORMA, argv)


if __name__ == "__main__":
    sys.exit(main())
