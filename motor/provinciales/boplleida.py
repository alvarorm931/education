"""BOP de Lleida (Butlletí Oficial de la Província de Lleida), plataforma «mostra-bop» (motor/provinciales/mostrabop.py).

Solo responde desde España (servidor propio). Las entidades llevan el municipio detrás: «AJUNTAMENT D'AGRAMUNT (AGRAMUNT)».

Uso:
  python -m motor.provinciales.boplleida --salida ruta/                                  # lo nuevo
  python -m motor.provinciales.boplleida --desde 2022-01-01 --max-minutos 30 --salida ruta/
"""

from __future__ import annotations

import sys

from motor.provinciales import mostrabop as m
from motor.provinciales.mostrabop import parsear_boletin, ultimo  # noqa: F401  (las usan las pruebas)

PLATAFORMA = m.Plataforma(fuente="boplleida", siglas="BOP-LLEIDA", provincia="Lleida", web="https://ebop.diputaciolleida.cat",
                          nombres=("Boletín Oficial de la Provincia de Lleida",
                                   "Butlletí Oficial de la Província de Lleida"))
FUENTE, SIGLAS, NOMBRES = PLATAFORMA.fuente, PLATAFORMA.siglas, PLATAFORMA.nombres
url_boletin = PLATAFORMA.url_boletin


def seleccionar(filas: list[dict]) -> list[dict]:
    return m.seleccionar(PLATAFORMA, filas)


def main(argv: list[str] | None = None) -> int:
    return m.main(PLATAFORMA, argv)


if __name__ == "__main__":
    sys.exit(main())
