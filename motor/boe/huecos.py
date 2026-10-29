"""Control de cobertura del BOE: números de diario que faltan y días sin procesar.

Uso:
  python -m motor.boe.huecos --salida ruta/ [--desde 2022-01-01]

Escribe datos/boe/huecos.json. Un hueco es:
  - un número de diario que falta en la serie de un año (1..máximo visto);
  - un día de lunes a sábado sin informe o con error;
  - un anuncio de oposiciones sin texto descargado.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from motor.boe.texto import pendientes


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--desde", type=date.fromisoformat, default=date(2022, 1, 1))
    p.add_argument("--hasta", type=date.fromisoformat, default=None)
    a = p.parse_args(argv)
    base = a.salida / "datos" / "boe" / "dias"

    informes = {}
    for f in base.glob("*/*/*.json"):
        i = json.loads(f.read_text(encoding="utf-8"))
        informes[i["fecha"]] = i
    if not informes:
        print("Sin informes diarios")
        return 1

    hasta = a.hasta or max(date.fromisoformat(x) for x in informes)
    numeros = defaultdict(set)
    sin_procesar, con_error, sin_boletin_laborable = [], [], []
    d = a.desde
    while d <= hasta:
        i = informes.get(d.isoformat())
        if i is None:
            if d.weekday() < 6:
                sin_procesar.append(d.isoformat())
        elif i.get("resultado") == "ok":
            for n in i.get("diarios", []):
                if str(n).isdigit():
                    numeros[d.year].add(int(n))
        elif i.get("resultado") == "sin_boletin":
            if d.weekday() < 6:
                sin_boletin_laborable.append(d.isoformat())
        else:
            con_error.append(d.isoformat())
        d += timedelta(days=1)

    faltan = {str(anio): sorted(set(range(1, max(ns) + 1)) - ns) for anio, ns in sorted(numeros.items())}
    resultado = {
        "periodo": [a.desde.isoformat(), hasta.isoformat()],
        "numeros_de_diario_que_faltan": {k: v for k, v in faltan.items() if v},
        "dias_sin_procesar": sin_procesar,
        "dias_con_error": con_error,
        "dias_lunes_a_sabado_sin_boletin": sin_boletin_laborable,
        "anuncios_sin_texto": len(pendientes(a.salida)),
        "diarios_por_anio": {str(k): len(v) for k, v in sorted(numeros.items())},
    }
    destino = a.salida / "datos" / "boe" / "huecos.json"
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: (v if not isinstance(v, list) or len(v) < 15 else f"{len(v)} días") for k, v in resultado.items()},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
