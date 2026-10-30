"""Qué textos del BOE hay que leer para tener el plan vigente de cada grado activo.

Un grado tiene su plan publicado en el BOE (resolución de la universidad) y, después, cero o más modificaciones,
cambios de denominación y correcciones. El plan vigente es el de la última publicación que trae el plan completo.

Se juntan tres fuentes, sin pedir nada:
  - la ficha del RUCT de cada grado («Plan Estudios en el BOE»: identificador del plan publicado);
  - los actos del BOE de 2008-2021 (motor/grados/boe_historico.py) y de 2022-2026 (motor/grados/boe_grados.py actos),
    unidos al grado por universidad y nombre;
  - los textos ya descargados (para no volver a pedirlos).

Salida: datos/estudios/grados/planes_pendientes.json con la lista de identificadores BOE que faltan, ordenada por
prioridad (primero la publicación más reciente de cada grado) y el cuadro de cobertura.

Uso:
  python -m motor.grados.planes --catalogo … [--ruct carpeta] [--actos carpeta] [--textos carpeta] --salida ruta/
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from motor.grados.boe_grados import actos as actos_de_sumario
from motor.grados.catalogo import clave_union, nombre_corto
from motor.grados.fichas import clave_universidad
from motor.grados.generico import nombre_base


def _leer(ruta: Path) -> list[dict]:
    return [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines() if x.strip()]


def clave_grado(universidad: str, nombre: str) -> tuple[str, str]:
    return clave_universidad(universidad), clave_union(nombre_base(nombre_corto(nombre)))


def resolver_universidad(clave: str, conocidas: set[str]) -> str:
    """La universidad del catálogo a la que se refiere el BOE: igual, o la única que contiene o está contenida
    («pais vasco euskal herriko unibertsitatea» ↔ «pais vasco/euskal…»)."""
    if not conocidas or clave in conocidas:
        return clave
    def contiene(a: str, b: str) -> bool:  # b dentro de a, por palabras enteras y con al menos dos palabras
        return len(b.split()) >= 2 and f" {b} " in f" {a} "

    c = [k for k in conocidas if k and (contiene(clave, k) or contiene(k, clave))]
    return c[0] if len(c) == 1 else clave


def actos_por_grado(carpeta: Path | None, conocidas: set[str] | None = None) -> dict[tuple[str, str], list[dict]]:
    """(universidad, grado) → actos de plan del BOE, de todos los años, del más reciente al más antiguo."""
    salida: dict[tuple[str, str], list[dict]] = defaultdict(list)
    if not carpeta:
        return salida
    conocidas = conocidas or set()

    def clave_grado(universidad: str, nombre: str) -> tuple[str, str]:
        u, n = globals()["clave_grado"](universidad, nombre)
        return resolver_universidad(u, conocidas), n
    filas = []
    for f in carpeta.rglob("*.jsonl"):
        for x in _leer(f):
            if x.get("nivel", "grado") == "grado" and x.get("identificador") and x.get("titulo"):
                filas.append(x)
            elif x.get("titulo_grado") and x.get("identificador"):  # boe_actos.jsonl ya clasificado
                salida[clave_grado(x.get("universidad") or "", x["titulo_grado"])].append(x)
    for a in actos_de_sumario(filas):
        if a.get("titulo_grado") and a.get("universidad"):
            salida[clave_grado(a["universidad"], a["titulo_grado"])].append(a)
    for k in salida:
        vistos, unicos = set(), []
        for a in sorted(salida[k], key=lambda a: a.get("fecha") or "", reverse=True):
            if a["identificador"] not in vistos:
                vistos.add(a["identificador"])
                unicos.append(a)
        salida[k] = unicos
    return salida


def varios_planes(carpeta: Path | None) -> list[str]:
    """Resoluciones que publican varios planes a la vez («por la que se publican planes de estudios»): su título
    no dice de qué grados son, así que no se pueden unir por nombre antes de leerlas (boe_grados.separar_planes
    las separa por anexo). Se piden todas las de plan, modificación y cambio de denominación."""
    if not carpeta:
        return []
    filas, ids = [], []
    for f in carpeta.rglob("*.jsonl"):
        for x in _leer(f):
            if x.get("varios_planes") and x.get("tipo") in ("plan", "modificacion", "denominacion"):
                ids.append(x["identificador"])  # boe_actos.jsonl ya clasificado
            elif x.get("nivel", "grado") == "grado" and x.get("identificador") and x.get("titulo") and "varios_planes" not in x:
                filas.append(x)
    ids += [a["identificador"] for a in actos_de_sumario(filas)
            if a.get("varios_planes") and a["tipo"] in ("plan", "modificacion", "denominacion")]
    return list(dict.fromkeys(ids))


def plan_ruct(carpeta: Path | None) -> dict[str, dict]:
    """código → identificador BOE del plan según la ficha del RUCT (y del acuerdo)."""
    salida = {}
    if not carpeta:
        return salida
    for f in carpeta.rglob("*.json"):
        if not f.stem.isdigit():
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        boe = (d.get("boe") or {}).get("plan") or {}
        if boe.get("identificador"):
            salida[f.stem] = {"identificador": boe["identificador"], "fecha": boe.get("fecha")}
    return salida


def ya_descargados(carpeta: Path | None) -> set[str]:
    return {f.stem for f in carpeta.rglob("BOE-*.json")} if carpeta else set()


def calcular(catalogo: list[dict], ruct: dict, actos: dict, hechos: set[str], varios: list[str] | None = None) -> dict:
    grados = [t for t in catalogo if t["situacion"] == "Activo" and t["clase"] == "grado"]
    pendientes_1, pendientes_2 = [], []
    cobertura = Counter({k: 0 for k in ("con_publicacion_conocida", "sin_publicacion_conocida", "con_plan_en_ruct",
                                        "texto_mas_reciente_ya_leido")})
    for t in grados:
        ids = []
        for u in t["universidades"]:
            ids += [a["identificador"] for a in actos.get(clave_grado(u["nombre"], t["nombre"]), [])]
        if t["codigo"] in ruct:
            ids.append(ruct[t["codigo"]]["identificador"])
        ids = list(dict.fromkeys(ids))
        if not ids:
            cobertura["sin_publicacion_conocida"] += 1
            continue
        cobertura["con_publicacion_conocida"] += 1
        if t["codigo"] in ruct:
            cobertura["con_plan_en_ruct"] += 1
        if ids[0] in hechos:
            cobertura["texto_mas_reciente_ya_leido"] += 1
        else:
            pendientes_1.append(ids[0])
        pendientes_2 += [i for i in ids[1:] if i not in hechos]
    varios_pend = [i for i in (varios or []) if i not in hechos]
    lista = list(dict.fromkeys(pendientes_1 + varios_pend + pendientes_2))
    return {"grados_activos": len(grados), **cobertura, "textos_pendientes": len(lista),
            "pendientes_mas_recientes": len(dict.fromkeys(pendientes_1)),
            "resoluciones_con_varios_planes_pendientes": len(varios_pend), "ids": lista}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--catalogo", required=True)
    p.add_argument("--ruct", help="carpeta con las fichas del RUCT ({código}.json)")
    p.add_argument("--actos", help="carpeta con boe_historico/*.jsonl y boe_actos.jsonl")
    p.add_argument("--textos", help="carpeta con los textos ya descargados (datos/boe/textos)")
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    cat = _leer(Path(a.catalogo))
    conocidas = {clave_universidad(u["nombre"]) for t in cat for u in t["universidades"]}
    res = calcular(cat, plan_ruct(Path(a.ruct) if a.ruct else None),
                   actos_por_grado(Path(a.actos) if a.actos else None, conocidas),
                   ya_descargados(Path(a.textos) if a.textos else None),
                   varios_planes(Path(a.actos) if a.actos else None))
    destino = Path(a.salida) / "datos" / "estudios" / "grados"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "planes_pendientes.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "ids"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
