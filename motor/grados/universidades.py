"""Datos de cada universidad para su página (/universidad/{universidad}/), desde lo ya capturado.

Une las fichas de grado (motor/grados/fichas.py), la ficha de la universidad en el RUCT (web, tipo, comunidad,
domicilio, norma de creación; censo de motor/estudios/centros_ruct.py) y los indicadores del SIIU del conjunto de
la universidad («Todos los ámbitos»). No pide nada a ninguna fuente.

Uso:
  python -m motor.grados.universidades --fichas …/fichas.jsonl --centros carpeta [--indicadores carpeta] --salida ruta/
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

from motor.grados.fichas import clave_universidad, indexar_indicadores


def _leer(ruta: Path) -> list[dict]:
    return [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines() if x.strip()]


def construir(fichas: list[dict], ruct: dict[str, dict], ind: dict) -> list[dict]:
    por_u: dict[str, list[dict]] = defaultdict(list)
    info: dict[str, dict] = {}
    for f in fichas:
        for u in f["universidades"]:
            por_u[u["nombre"]].append(f)
            info.setdefault(u["nombre"], u)
    salida = []
    for nombre, fs in por_u.items():
        u = info[nombre]
        r = ruct.get(u.get("codigo") or "", {})
        centros = {c["codigo"]: c for f in fs for c in f["centros"]}
        # nota de corte de cada oferta (título × centro) con selección real (por encima de 5)
        notas = [c["nota_corte"] for f in fs for c in f["centros"] if c.get("nota_corte") and c["nota_corte"] > 5]
        plazas = sum(c["plazas"] for f in fs for c in f["centros"] if c.get("plazas"))
        total = (ind.get((clave_universidad(nombre), "Todos los ámbitos")) or {})
        # precio por curso que publica la propia universidad (privadas) o primera matrícula de todo el grado (públicas)
        cursos = sorted(f["precio_web"]["precio_curso"] for f in fs if (f.get("precio_web") or {}).get("precio_curso"))
        primeras = sorted(f["precio_primera_matricula"] for f in fs if f.get("precio_primera_matricula"))
        salida.append({
            "nombre": nombre,
            "nombre_oficial": r.get("nombre"),
            "codigo": u.get("codigo"),
            "tipo": u.get("tipo"),
            "comunidad": u.get("comunidad"),
            "web": r.get("web"),
            "municipio_sede": r.get("municipio"),
            "acronimo": r.get("acronimo"),
            "norma_creacion": r.get("norma_creacion"),
            "grados": sum(1 for f in fs if f["clase"] == "grado"),
            "dobles": sum(1 for f in fs if f["clase"] == "doble"),
            "ramas": dict(Counter(f["rama"] for f in fs if f["clase"] == "grado" and f.get("rama"))),
            "modalidades": dict(Counter(m for f in fs for m in f["modalidades"])),
            "centros_con_oferta": len(centros),
            "plazas_nuevo_ingreso": plazas or None,
            "nota_corte_mediana": round(median(notas), 2) if notas else None,
            "ofertas_con_nota_de_corte_mayor_de_5": len(notas),
            "indicadores_todos_los_ambitos": {k: v for k, v in total.items()} or None,
            "precio_curso_web": {"desde": cursos[0], "hasta": cursos[-1], "grados_con_precio": len(cursos)} if cursos else None,
            "precio_grado_completo_primera_matricula": {"desde": primeras[0], "hasta": primeras[-1],
                                                         "grados_con_precio": len(primeras)} if primeras else None,
            "fuente": {"cita": "Ministerio de Ciencia, Innovación y Universidades: SIIU, QEDU y RUCT"},
        })
    return sorted(salida, key=lambda x: (-x["grados"], x["nombre"]))


def leer_ruct(carpeta: Path) -> dict[str, dict]:
    salida = {}
    for f in sorted(carpeta.rglob("*.json")):
        if re.fullmatch(r"\d{3}\.json", f.name):
            d = json.loads(f.read_text(encoding="utf-8"))
            salida[d.get("codigo")] = d
    return salida


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--fichas", required=True)
    p.add_argument("--centros", required=True)
    p.add_argument("--indicadores")
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    unis = construir(_leer(Path(a.fichas)), leer_ruct(Path(a.centros)),
                     indexar_indicadores(Path(a.indicadores)) if a.indicadores else {})
    destino = Path(a.salida) / "datos" / "estudios" / "grados"
    destino.mkdir(parents=True, exist_ok=True)
    with (destino / "universidades.jsonl").open("w", encoding="utf-8") as f:
        for u in unis:
            f.write(json.dumps(u, ensure_ascii=False) + "\n")
    print(json.dumps({"universidades": len(unis), "con_web": sum(1 for u in unis if u["web"]),
                      "con_plazas": sum(1 for u in unis if u["plazas_nuevo_ingreso"]),
                      "con_indicadores": sum(1 for u in unis if u["indicadores_todos_los_ambitos"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
