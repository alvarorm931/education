"""Procesos de oposición a partir de los actos extraídos (primera versión: BOE).

Uso:
  python -m motor.procesos --salida ruta/ [--hoy 2026-10-29]

Lee datos/boe/actos/ y escribe:
  datos/oposiciones/procesos.jsonl   un proceso por convocatoria de acceso, con sus actos posteriores enlazados
  datos/oposiciones/resumen.json     cifras del día: plazos abiertos por provincia y por puesto

Reglas:
  - Nace un proceso por cada anuncio de apertura de plazo (local) o convocatoria (resto) de acceso abierto.
  - Se le enlazan los actos que lo citan por su identificador del BOE (correcciones, anulaciones, modificaciones).
  - Estado: «anulado» si hay anulación; «plazo_abierto» si la fecha de fin estimada es hoy o posterior;
    «plazo_cerrado» si ya pasó (el proceso sigue en curso, sin novedades conocidas);
    «sin_datos_de_plazo» si aún no se ha extraído el plazo. Nunca se inventa un estado.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")


def leer_actos(raiz: Path) -> list[dict]:
    actos = []
    for f in sorted((raiz / "datos" / "boe" / "actos").glob("*/*.jsonl")):
        actos += [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    return actos


def es_origen(a: dict) -> bool:
    if a.get("alcance") not in (None, "acceso"):
        return False
    return a.get("tipo_acto") == "apertura_plazo" or (a.get("ambito") != "local" and a.get("tipo_acto") == "convocatoria")


def construir(actos: list[dict], hoy: date) -> list[dict]:
    citados_por: dict[str, list[dict]] = defaultdict(list)
    for a in actos:
        for ref in a.get("refiere_a") or []:
            citados_por[ref].append(a)

    procesos = []
    for a in actos:
        if not es_origen(a):
            continue
        posteriores = sorted(citados_por.get(a["id"], []), key=lambda x: x["fecha"])
        plazo = a.get("plazo") or {}
        fin = plazo.get("fin_estimado")
        if any(x.get("tipo_acto") == "anulacion" for x in posteriores):
            estado = "anulado"
        elif fin:
            estado = "plazo_abierto" if fin >= hoy.isoformat() else "plazo_cerrado"
        else:
            estado = "sin_datos_de_plazo"
        conv = a.get("convocante") or {}
        procesos.append({
            "id": f"boe:{a['id']}",
            "estado": estado,
            "ambito": a.get("ambito"),
            "convocante": conv,
            "provincia": conv.get("provincia") or (conv.get("nombre") if conv.get("tipo") in ("Ayuntamiento", "Diputación Provincial") else None),
            "titulo": a.get("titulo"),
            "plazas": [{k: p.get(k) for k in ("numero", "puesto_clave", "puesto", "especialidad", "denominacion", "grupo",
                                              "regimen", "sistema", "turno")} for p in a.get("plazas") or []],
            "total_plazas": a.get("total_plazas"),
            "plazo": {k: plazo.get(k) for k in ("dias", "tipo", "fin_estimado", "calendario")} if plazo else None,
            "apertura_plazo": a["fecha"],
            "bases": [b for b in a.get("boletines_citados") or [] if b.get("papel") in ("bases", "extracto", "rectificacion")],
            "actos": [{"id": a["id"], "fecha": a["fecha"], "tipo": a.get("tipo_acto"), "url": a.get("url")}] +
                     [{"id": x["id"], "fecha": x["fecha"], "tipo": x.get("tipo_acto"), "url": x.get("url")} for x in posteriores],
            "actualizado": max([a["fecha"]] + [x["fecha"] for x in posteriores]),
            "fuente": "Agencia Estatal Boletín Oficial del Estado",
            "pendiente": a.get("pendiente") or [],
        })
    return procesos


def resumen(procesos: list[dict], hoy: date) -> dict:
    abiertos = [p for p in procesos if p["estado"] == "plazo_abierto"]
    por_provincia, por_puesto = Counter(), Counter()
    for p in abiertos:
        por_provincia[p.get("provincia") or "sin provincia"] += p.get("total_plazas") or 0
        for pl in p["plazas"]:
            por_puesto[pl.get("puesto_clave") or "sin puesto"] += pl.get("numero") or 0
    return {
        "fecha": hoy.isoformat(),
        "procesos": len(procesos),
        "por_estado": dict(Counter(p["estado"] for p in procesos)),
        "plazo_abierto": {"procesos": len(abiertos), "plazas": sum(p.get("total_plazas") or 0 for p in abiertos),
                          "por_provincia": dict(por_provincia.most_common()), "por_puesto": dict(por_puesto.most_common(50))},
        "aviso": "Fechas de fin estimadas con festivos nacionales; comprobar siempre en el boletín oficial.",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--hoy", type=date.fromisoformat, default=datetime.now(MADRID).date())
    a = p.parse_args(argv)
    procesos = construir(leer_actos(a.salida), a.hoy)
    destino = a.salida / "datos" / "oposiciones"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "procesos.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in procesos),
                                            encoding="utf-8")
    r = resumen(procesos, a.hoy)
    (destino / "resumen.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: r[k] for k in ("procesos", "por_estado")}, ensure_ascii=False))
    print("Plazo abierto hoy:", r["plazo_abierto"]["procesos"], "procesos,", r["plazo_abierto"]["plazas"], "plazas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
