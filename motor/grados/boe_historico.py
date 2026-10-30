"""Planes de estudios de grado y máster publicados en el BOE antes de 2022.

El motor del BOE tiene el sumario desde el 01/01/2022. El 62 % de los grados activos tiene su plan vigente
publicado antes (medido el 30/10/2026: 1.252 de 3.265 con plan o modificación en 2022-2026). Este módulo recorre
el sumario de un rango de fechas con la misma API (boe.es/datosabiertos/api/boe/sumario/AAAAMMDD) y guarda solo
las disposiciones de planes de estudios, modificaciones, cambios de denominación y acuerdos de carácter oficial
de grado y de máster. No guarda el resto del sumario.

Uso:
  python -m motor.grados.boe_historico --desde 2008-01-01 --hasta 2011-12-31 --salida ruta/
Escribe datos/estudios/grados/boe_historico/AAAA.jsonl (filas como las de datos/boe/sumarios, con «tipo» y
«nivel») y un resumen.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.boe.sumario import ACCEPT, ErrorSumario, parsear, url_sumario
from motor.estudios.boe_masters import tipo_acto as tipo_master
from motor.grados.boe_grados import tipo_acto as tipo_grado
from motor.http import obtener

FUENTE = "boe-sumario"


def clasificar(titulo: str) -> tuple[str, str] | None:
    """(nivel, tipo) de una disposición de plan de estudios o de oficialidad de grado o máster."""
    t = tipo_grado(titulo)
    if t:
        return "grado", t
    t = tipo_master(titulo)
    if t:
        return "master", {"plan_modificacion": "modificacion"}.get(t, t)
    return None


def dias(desde: date, hasta: date):
    d = desde
    while d <= hasta:
        if d.weekday() != 6:  # el BOE no se publica en domingo
            yield d
        d += timedelta(days=1)


def ejecutar(desde: date, hasta: date, raiz: Path, pausa: float, max_minutos: float) -> dict:
    archivo = Archivo(raiz / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    destino = raiz / "datos" / "estudios" / "grados" / "boe_historico"
    destino.mkdir(parents=True, exist_ok=True)
    fin = time.time() + max_minutos * 60
    leidos, sin_boe, errores, seleccion, ultimo = 0, 0, [], [], None
    seguidos = 0
    for d in dias(desde, hasta):
        if time.time() > fin:
            break
        time.sleep(pausa)
        url = url_sumario(d)
        try:
            r = obtener(url, accept=ACCEPT)
        except ConnectionError as e:
            errores.append(f"{d}: {str(e)[:120]}")
            seguidos += 1
            if seguidos >= 5:
                print("ALERTA BOE histórico: cinco errores seguidos; ejecución detenida", file=sys.stderr)
                break
            continue
        seguidos = 0
        ultimo = d
        if r.status == 404:
            sin_boe += 1
            continue
        if r.status != 200:
            errores.append(f"{d}: HTTP {r.status}")
            continue
        try:
            s = parsear(r.contenido)
        except (ErrorSumario, Exception) as e:  # noqa: BLE001 - un día ilegible no para el recorrido
            if b"<code>404</code>" in r.contenido or b'"code":"404"' in r.contenido:
                sin_boe += 1
            else:
                errores.append(f"{d}: {type(e).__name__}: {str(e)[:100]}")
            continue
        cap = archivo.guardar(FUENTE, d, r.contenido, url, "xml", r.status, r.cabeceras)
        leidos += 1
        for it in s.items:
            c = clasificar(it.get("titulo") or "")
            if c:
                seleccion.append({**it, "fecha": d.isoformat(), "nivel": c[0], "tipo": c[1],
                                  "captura_sha256": cap["sha256"]})
    por_anio: dict[str, list[dict]] = {}
    for x in seleccion:
        por_anio.setdefault(x["fecha"][:4], []).append(x)
    for anio, filas in por_anio.items():
        with (destino / f"{anio}_{desde:%m%d}_{hasta:%m%d}.jsonl").open("w", encoding="utf-8") as f:
            for x in filas:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
    res = {"desde": desde.isoformat(), "hasta": hasta.isoformat(), "ultimo_dia_leido": ultimo and ultimo.isoformat(),
           "sumarios": leidos, "dias_sin_boe": sin_boe, "errores": len(errores), "primeros_errores": errores[:10],
           "seleccionadas": len(seleccion),
           "por_nivel_y_tipo": {f"{k[0]} · {k[1]}": v for k, v in sorted(Counter((x["nivel"], x["tipo"]) for x in seleccion).items())}}
    (destino / f"resumen_{desde:%Y%m%d}_{hasta:%Y%m%d}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1),
                                                                         encoding="utf-8")
    return res


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--desde", required=True, type=date.fromisoformat)
    p.add_argument("--hasta", required=True, type=date.fromisoformat)
    p.add_argument("--pausa", type=float, default=1.0)
    p.add_argument("--max-minutos", type=float, default=52)
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    print(json.dumps(ejecutar(a.desde, a.hasta, Path(a.salida), a.pausa, a.max_minutos), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
