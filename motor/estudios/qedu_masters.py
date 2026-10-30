"""QEDU (Qué Estudiar y Dónde en la Universidad) para másteres: la misma fuente y el mismo lector que los grados.

Por máster y centro da plazas, créditos, modalidad, precio del crédito en primera matrícula (públicas), idioma
extranjero, enlace a la web del máster e inserción laboral del título (tasa de afiliación, autónomos, indefinidos,
cotización adecuada y base media). Las tarjetas son además la lista oficial de qué másteres se imparten este curso
y en qué centro.

Reutiliza sin modificarlo motor/grados/qedu.py (la consulta, la limpieza de campos y el archivo de originales); aquí
solo cambian el nivel («'MASTER','MASTERD'») y la carpeta de salida (datos/estudios/masters/qedu/).

Uso:
  python -m motor.estudios.qedu_masters tarjetas --salida ruta/
  python -m motor.estudios.qedu_masters detalles --tarjetas ruta/…/qedu_tarjetas_master.jsonl --desde 0 --hasta 900 --salida ruta/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from motor.grados import qedu

NIVEL = "master"


def _mover(raiz: Path, nombre: str, nuevo: str) -> Path | None:
    origen = raiz / "datos" / "estudios" / "grados" / "qedu" / nombre
    if not origen.exists():
        return None
    destino = raiz / "datos" / "estudios" / "masters" / "qedu" / nuevo
    destino.parent.mkdir(parents=True, exist_ok=True)
    origen.replace(destino)
    # no se deja una carpeta de grados vacía en los resultados de másteres
    for d in (origen.parent, origen.parent.parent):
        try:
            d.rmdir()
        except OSError:
            break
    return destino


def tarjetas(raiz: Path) -> dict:
    res = qedu.cmd_tarjetas(raiz, NIVEL)
    _mover(raiz, f"qedu_tarjetas_{NIVEL}.jsonl", f"qedu_tarjetas_{NIVEL}.jsonl")
    return res


def detalles(raiz: Path, fichero: Path, desde: int, hasta: int | None, max_minutos: float) -> dict:
    res = qedu.cmd_detalles(raiz, fichero, desde, hasta, max_minutos)
    nuevo = f"qedu_detalles_{NIVEL}_{desde}_{hasta or 'fin'}.jsonl"
    if _mover(raiz, res["fichero"], nuevo):
        res["fichero"] = nuevo
    return res


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="orden", required=True)
    a = sub.add_parser("tarjetas")
    d = sub.add_parser("detalles")
    d.add_argument("--tarjetas", required=True)
    d.add_argument("--desde", type=int, default=0)
    d.add_argument("--hasta", type=int)
    d.add_argument("--max-minutos", type=float, default=50)
    for s in (a, d):
        s.add_argument("--salida", required=True)
    x = p.parse_args()
    if x.orden == "tarjetas":
        res = tarjetas(Path(x.salida))
    else:
        res = detalles(Path(x.salida), Path(x.tarjetas), x.desde, x.hasta, x.max_minutos)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
