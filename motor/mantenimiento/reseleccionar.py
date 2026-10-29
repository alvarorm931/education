"""Vuelve a seleccionar los anuncios de empleo público de lo ya capturado, con las reglas actuales.

Cada conector guarda todo lo que lee de un boletín en disposiciones/ y su selección de empleo público en
oposiciones/ (con el mismo nombre de fichero). Cuando mejoran las reglas (otra lengua, una exclusión nueva), esta
tarea rehace oposiciones/ a partir de disposiciones/ sin volver a pedir nada a las fuentes. Los textos que falten
para lo nuevo se descargan en la siguiente pasada de cada conector.

Uso: python -m motor.mantenimiento.reseleccionar --salida ruta/ [--fuentes dogv,dogc]
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

from motor.autonomicos.comun import escribir_jsonl, leer_jsonl

# fuente -> (carpeta de datos, función de selección)
def _selectores() -> dict:
    def mod(nombre):
        return importlib.import_module(nombre)

    sel = {}
    for f in ("boc", "bocyl", "boib", "bome", "bopv", "borm", "docm", "doe", "dog", "dogc", "dogv"):
        sel[f] = ("autonomicos", mod(f"motor.autonomicos.{f}").seleccionar)
    for f in ("bopalicante", "bopciudadreal", "bopvalencia", "boptenerife"):
        sel[f] = ("provinciales", mod(f"motor.provinciales.{f}").seleccionar)
    diba, saga = mod("motor.provinciales.diba"), mod("motor.provinciales.saga")
    for f in ("bopb", "bopt"):
        b = mod(f"motor.provinciales.{f}").BOLETIN
        sel[f] = ("provinciales", lambda filas, b=b: diba.seleccionar(b, filas))
    for f in ("bopgranada", "bopsevilla", "bophuesca"):
        b = mod(f"motor.provinciales.{f}").BOLETIN
        sel[f] = ("provinciales", lambda filas, b=b: saga.seleccionar(b, filas))
    return sel


def reseleccionar(raiz: Path, fuente: str, grupo: str, seleccionar) -> dict:
    base = raiz / "datos" / grupo / fuente
    antes = despues = ficheros = 0
    for f in sorted((base / "disposiciones").rglob("*.jsonl")):
        destino = base / "oposiciones" / f.relative_to(base / "disposiciones")
        previo = leer_jsonl(destino) if destino.exists() else []
        nuevo = seleccionar(leer_jsonl(f))
        antes, despues = antes + len(previo), despues + len(nuevo)
        if [x.get("id") for x in previo] != [x.get("id") for x in nuevo] or previo != nuevo:
            escribir_jsonl(destino, nuevo)
            ficheros += 1
    return {"antes": antes, "despues": despues, "ficheros_cambiados": ficheros}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--fuentes", default="")
    a = p.parse_args(argv)
    sel = _selectores()
    elegidas = [x for x in a.fuentes.split(",") if x] or list(sel)
    informe = {}
    for f in elegidas:
        grupo, funcion = sel[f]
        if (a.salida / "datos" / grupo / f / "disposiciones").exists():
            informe[f] = reseleccionar(a.salida, f, grupo, funcion)
    print(json.dumps(informe, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
