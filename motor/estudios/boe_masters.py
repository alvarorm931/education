"""Másters en el BOE: altas de títulos (acuerdos de carácter oficial) y planes de estudios publicados.

Se apoya en lo que ya captura el motor del BOE (no vuelve a pedir sumarios):
  - datos/boe/sumarios/AAAA/MM/DD.jsonl  → selección de disposiciones sobre másters;
  - motor.boe.texto                      → texto y tablas de cada disposición (sin datos personales).

Qué se obtiene:
  1. actos: cada disposición de máster con su tipo (plan, modificación de plan, oficialidad), universidad y
     nombre del título tal como lo publica el BOE;
  2. altas: de los acuerdos del Consejo de Ministros, el código RUCT de 7 cifras, el nombre y la universidad
     de cada título nuevo (es el aviso oficial más temprano de que un máster existe);
  3. asignaturas: de las tablas del plan, nombre, carácter, créditos y periodo, con la fila literal de origen.

La unión con el catálogo se hace por el identificador BOE del plan que da la ficha del RUCT
(«Publicación Plan Estudios en el BOE»), no por parecido de nombres.

Uso:
  python -m motor.estudios.boe_masters --sumarios ruta/datos/boe/sumarios --salida ruta/
  python -m motor.estudios.boe_masters --sumarios ... --textos ruta/datos/boe/textos --salida ruta/
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

CITA = "Fuente: Agencia Estatal Boletín Oficial del Estado"
RE_UNIV = re.compile(r",\s+de\s+(?:la\s+)?(Universi[^,]+?|Mondragon[^,]*|IE Universidad|CUNEF[^,]*|ESIC[^,]*),\s+por la que", re.I)
RE_TITULO = re.compile(r"(M[áa]ster Universitario en .+?)(?:\.\s*$|, de la Universidad|$)")
RE_ALTA = re.compile(r"^\s*(\d{7})\s+(M[áa]ster Universitario .+?)\.?\s*$")


def tipo_acto(titulo: str) -> str | None:
    t = titulo.lower()
    if "máster" not in t and "master" not in t:
        return None
    if "carácter oficial" in t or "caracter oficial" in t:
        return "oficialidad"
    if re.search(r"plan(?:es)? de estudios?", t):
        if re.search(r"modifica|corrección|correccion|rectifica", t):
            return "plan_modificacion"
        return "plan"
    return None


def actos(filas_sumario: list[dict]) -> list[dict]:
    salida = []
    for f in filas_sumario:
        tipo = tipo_acto(f.get("titulo") or "")
        if not tipo:
            continue
        titulo = f["titulo"]
        u = RE_UNIV.search(titulo)
        m = RE_TITULO.search(titulo)
        salida.append({
            "identificador": f["identificador"],
            "fecha": f.get("fecha"),
            "tipo": tipo,
            "universidad": u.group(1).strip() if u and tipo != "oficialidad" else None,
            "titulo_master": m.group(1).strip().rstrip(".") if m and tipo != "oficialidad" else None,
            "titulo_disposicion": titulo,
            "url_html": f.get("url_html"),
            "url_pdf": f.get("url_pdf"),
            "fuente": CITA,
        })
    return salida


def altas(texto: str) -> list[dict]:
    """Títulos de un acuerdo de carácter oficial: código RUCT, nombre y universidad (encabezado previo)."""
    universidad = None
    salida = []
    for linea in texto.split("\n"):
        linea = linea.strip()
        m = RE_ALTA.match(linea)
        if m:
            salida.append({"codigo_ruct": m.group(1), "nombre": m.group(2).strip(), "universidad": universidad, "linea": linea})
        elif re.match(r"^(Universi|IE Universidad|CUNEF|ESIC|Mondrag)", linea) and len(linea) < 120:
            universidad = linea.rstrip(".:")
    return salida


# ------------------------------------------------------------------------------------- tablas del plan

COL = {
    "nombre": re.compile(r"asignatura|materia|denominaci", re.I),
    "modulo": re.compile(r"m[óo]dulo|bloque", re.I),
    "creditos": re.compile(r"cr[ée]ditos|ects", re.I),
    "caracter": re.compile(r"car[áa]cter|^tipo$|tipolog", re.I),
    "periodo": re.compile(r"semestre|cuatrimestre|trimestre|curso|temporal|periodo|duraci", re.I),
}
RESUMEN = re.compile(r"^tipo de (asignatura|materia|m[óo]dulo|cr[ée]dito)|^tipo$", re.I)
TOTAL = re.compile(r"^(total|suma)", re.I)


def _columnas(cabecera: list[str]) -> dict[str, int]:
    cols: dict[str, int] = {}
    for i, c in enumerate(cabecera):
        for clave, patron in COL.items():
            if clave not in cols and patron.search(c or ""):
                if clave == "nombre" and COL["creditos"].search(c):
                    continue
                cols[clave] = i
                break
    # Si hay columna de asignatura y otra de materia, la asignatura es el nombre y la materia agrupa.
    asig = [i for i, c in enumerate(cabecera) if re.search(r"asignatura", c or "", re.I) and not COL["creditos"].search(c)]
    if asig and cols.get("nombre") != asig[0]:
        if "modulo" not in cols:
            cols["modulo"] = cols["nombre"]
        cols["nombre"] = asig[0]
    return cols


def rellenar(filas: list[list[str]], ancho: int) -> list[list[str]]:
    """Las celdas combinadas (rowspan) llegan como filas más cortas: se completan por la izquierda
    con los valores de la fila anterior."""
    salida, previa = [], [""] * ancho
    for f in filas:
        if len(f) < ancho:
            f = previa[: ancho - len(f)] + f
        f = f[:ancho]
        salida.append(f)
        previa = f
    return salida


def _num(s: str) -> float | None:
    m = re.search(r"\d+(?:[.,]\d+)?", s or "")
    return float(m.group(0).replace(",", ".")) if m else None


def asignaturas(tablas: list[dict]) -> list[dict]:
    """Filas de asignatura (o materia) de las tablas de un plan; descarta las de resumen por tipo."""
    salida = []
    for n, t in enumerate(tablas):
        filas = t.get("contenido") or []
        if t.get("datos_personales") or len(filas) < 2:
            continue
        cab = filas[0]
        if RESUMEN.search(cab[0] or "") and len(cab) <= 3:
            continue
        cols = _columnas(cab)
        if "nombre" not in cols and "modulo" in cols:
            cols["nombre"], cols["nivel"] = cols.pop("modulo"), "modulo"
        if "nombre" not in cols or "creditos" not in cols:
            continue
        for f in rellenar(filas[1:], len(cab)):
            nombre = (f[cols["nombre"]] or "").strip().rstrip(".")
            if not nombre or TOTAL.match(nombre):
                continue
            salida.append({
                "nombre": nombre,
                "modulo": f[cols["modulo"]].rstrip(".") if "modulo" in cols and isinstance(cols["modulo"], int) else None,
                "caracter": f[cols["caracter"]].rstrip(".") if "caracter" in cols else None,
                "creditos": _num(f[cols["creditos"]]),
                "periodo": f[cols["periodo"]] if "periodo" in cols else None,
                "nivel": "modulo" if cols.get("nivel") == "modulo" else ("asignatura" if re.search("asignatura", cab[cols["nombre"]], re.I) else "materia"),
                "tabla": n,
                "fila_literal": f,
            })
    return salida


# ---------------------------------------------------------------------------------------- ejecución


def ejecutar(sumarios: Path, salida: Path, textos: Path | None) -> dict:
    filas = []
    for fichero in sorted(sumarios.glob("*/*/*.jsonl")):
        for linea in fichero.read_text(encoding="utf-8").splitlines():
            filas.append(json.loads(linea))
    lista = actos(filas)
    destino = salida / "datos" / "estudios" / "masters"
    destino.mkdir(parents=True, exist_ok=True)
    res = {"disposiciones_leidas": len(filas), "actos": dict(Counter(a["tipo"] for a in lista))}
    altas_todas, planes = [], []
    if textos:
        for a in lista:
            ruta = textos / a["fecha"][:4] / a["fecha"][5:7] / f"{a['identificador']}.json"
            if not ruta.exists():
                continue
            doc = json.loads(ruta.read_text(encoding="utf-8"))
            if a["tipo"] == "oficialidad":
                for x in altas(doc.get("texto", "")):
                    altas_todas.append({**x, "boe": a["identificador"], "fecha": a["fecha"]})
            else:
                asig = asignaturas(doc.get("tablas", []))
                planes.append({"identificador": a["identificador"], "tipo": a["tipo"], "asignaturas": asig})
        res["altas"] = len(altas_todas)
        res["planes_leidos"] = len(planes)
        res["planes_con_asignaturas"] = sum(1 for p in planes if any(x["nivel"] == "asignatura" for x in p["asignaturas"]))
        res["planes_con_periodo"] = sum(1 for p in planes if any(x["periodo"] for x in p["asignaturas"]))
        res["planes_sin_filas"] = sum(1 for p in planes if not p["asignaturas"])
    for nombre, datos in (("boe_actos.jsonl", lista), ("boe_altas.jsonl", altas_todas), ("boe_planes.jsonl", planes)):
        if datos:
            with (destino / nombre).open("w", encoding="utf-8") as f:
                for d in datos:
                    f.write(json.dumps(d, ensure_ascii=False) + "\n")
    (destino / "boe_resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sumarios", required=True)
    p.add_argument("--textos")
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    print(json.dumps(ejecutar(Path(a.sumarios), Path(a.salida), Path(a.textos) if a.textos else None), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
