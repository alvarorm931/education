"""Grados en el BOE: planes de estudios publicados, modificaciones y altas de títulos nuevos.

Se apoya en lo que ya captura el motor del BOE (no vuelve a pedir sumarios):
  - datos/boe/sumarios/AAAA/MM/DD.jsonl  → selección de disposiciones sobre grados;
  - motor.boe.texto.descargar()          → texto y tablas de cada disposición (versión HTML permitida por el
                                           robots.txt del BOE, sin datos personales).

Qué se obtiene:
  1. actos: cada disposición de grado con su tipo (plan, modificación, corrección, oficialidad), universidad y
     nombre del título tal como lo publica el BOE;
  2. altas: de los acuerdos del Consejo de Ministros, el código RUCT, el nombre y la universidad de cada grado
     nuevo (el aviso oficial más temprano de que un grado existe);
  3. plan: de las tablas, cada asignatura o materia con módulo, carácter, créditos, curso y semestre, con la
     fila literal de origen; y la distribución de créditos por tipo (formación básica, obligatorias,
     optativas, prácticas, TFG) para comprobar que la suma cuadra.

La unión con el catálogo se hace por el identificador BOE del plan que da la ficha del RUCT («Plan Estudios en
el BOE»), no por parecido de nombres.

Uso:
  python -m motor.grados.boe_grados actos --sumarios ruta/datos/boe/sumarios --salida ruta/
  python -m motor.grados.boe_grados textos --ids BOE-A-…,BOE-A-… --salida ruta/   (descarga y mide; en GitHub)
  python -m motor.grados.boe_grados medir --textos ruta/datos/boe/textos --actos ruta/…/boe_actos.jsonl --salida ruta/
"""

from __future__ import annotations

import argparse
import json
import random
import re
import time
from collections import Counter
from pathlib import Path

from motor.estudios.boe_masters import RE_UNIV, rellenar

CITA = "Fuente: Agencia Estatal Boletín Oficial del Estado"
RE_TITULO = re.compile(r"((?:Graduad[oa]|Grado)\b.*?\ben\s+.+?)(?:\.\s*$|, de la Universidad|$)")
RE_ALTA = re.compile(r"^\s*(\d{7})\s+((?:Graduad[oa]|Grado)\b.+?)\.?\s*$")


def tipo_acto(titulo: str) -> str | None:
    t = (titulo or "").lower()
    if not re.search(r"\bgrado\b|graduad", t):
        return None
    if re.search(r"car[áa]cter oficial", t) and re.search(r"t[íi]tulos? (?:universitarios oficiales )?de grado|grado", t):
        return "oficialidad"
    if not re.search(r"plan(?:es)? de estudios?", t):
        return None
    if re.search(r"corrigen? errores|correcci[óo]n de errores", t):
        return "correccion"
    if re.search(r"cambio de denominaci[óo]n", t):
        return "denominacion"
    if re.search(r"modifica", t):
        return "modificacion"
    return "plan"


def actos(filas_sumario: list[dict]) -> list[dict]:
    salida = []
    for f in filas_sumario:
        tipo = tipo_acto(f.get("titulo") or "")
        if not tipo:
            continue
        titulo = f["titulo"]
        u = RE_UNIV.search(titulo)
        # «… por la que se publica el plan de estudios de Graduado o Graduada en X.»
        if tipo == "denominacion":  # «cambio de denominación del título de A por el de B y el plan actualizado»
            cola = re.split(r"\bpor el de\s+", titulo, maxsplit=1)
            cola[-1] = re.sub(r"\s+y el plan de estudios.*$", "", cola[-1])
        else:
            cola = re.split(r"plan(?:es)? de estudios? de\s+", titulo, maxsplit=1)
        m = RE_TITULO.search(cola[-1]) if len(cola) > 1 else None
        varios = bool(re.search(r"planes de estudios?\b", titulo, re.I))
        salida.append({
            "identificador": f["identificador"],
            "fecha": f.get("fecha"),
            "tipo": tipo,
            "varios_planes": varios,
            "universidad": u.group(1).strip() if u and tipo != "oficialidad" else None,
            "titulo_grado": m.group(1).strip().rstrip(".") if m and tipo != "oficialidad" and not varios else None,
            "titulo_disposicion": titulo,
            "url_html": f.get("url_html"),
            "url_pdf": f.get("url_pdf"),
            "fuente": CITA,
        })
    return salida


def altas(texto: str) -> list[dict]:
    """Grados de un acuerdo de carácter oficial: código RUCT, nombre y universidad (encabezado previo)."""
    universidad = None
    salida = []
    for linea in texto.split("\n"):
        linea = linea.strip()
        m = RE_ALTA.match(linea)
        if m:
            salida.append({"codigo_ruct": m.group(1), "nombre": m.group(2).strip(), "universidad": universidad,
                           "linea": linea})
        elif re.match(r"^(Universi|IE Universidad|CUNEF|ESIC|Mondrag)", linea) and len(linea) < 120:
            universidad = linea.rstrip(".:")
    return salida


# --------------------------------------------------------------------------------------- tablas del plan

COL = {
    "nombre": re.compile(r"asignatura|materia|denominaci", re.I),
    "modulo": re.compile(r"m[óo]dulo|bloque", re.I),
    "creditos": re.compile(r"cr[ée]ditos|ects", re.I),
    "caracter": re.compile(r"car[áa]cter|^tipo|tipolog", re.I),
    "curso": re.compile(r"^\s*curso\b|\bcurso\s*$", re.I),
    "semestre": re.compile(r"semestre|cuatrimestre|trimestre|temporal|periodo|duraci", re.I),
}
TOTAL = re.compile(r"^(total|suma)", re.I)
TIPOS_CREDITO = [
    ("formacion_basica", re.compile(r"formaci[óo]n b[áa]sica|^b[áa]sic|^fb$", re.I)),
    ("obligatorias", re.compile(r"obligatori|^ob$|^o$", re.I)),
    ("optativas", re.compile(r"optativ|^op$", re.I)),
    ("practicas_externas", re.compile(r"pr[áa]cticas|^pe$", re.I)),
    ("tfg", re.compile(r"trabajo (?:de )?fin|^tfg$", re.I)),
    ("total", re.compile(r"^total", re.I)),
]
ORDINALES = {"primer": 1, "primero": 1, "segundo": 2, "tercer": 3, "tercero": 3, "cuarto": 4, "quinto": 5, "sexto": 6}


def _num(s: str | None) -> float | None:
    m = re.search(r"\d+(?:[.,]\d+)?", s or "")
    return float(m.group(0).replace(",", ".")) if m else None


def numero_orden(s: str | None) -> int | None:
    """«1», «1º», «1.º», «Primero», «S1», «C2», «2.º cuatrimestre» → número; «Anual» → None."""
    s = (s or "").strip().lower()
    if not s:
        return None
    m = re.search(r"\d+", s)
    if m and int(m.group(0)) <= 12:
        return int(m.group(0))
    for palabra, n in ORDINALES.items():
        if re.search(rf"\b{palabra}\b", s):
            return n
    return None


def _columnas(cabecera: list[str]) -> dict[str, int]:
    cols: dict[str, int] = {}
    for i, c in enumerate(cabecera):
        for clave, patron in COL.items():
            if clave not in cols and patron.search(c or ""):
                if clave == "nombre" and COL["creditos"].search(c):
                    continue
                if clave == "curso" and COL["semestre"].search(c):  # «Curso/Semestre»: una sola columna
                    cols.setdefault("curso_semestre", i)
                    break
                cols[clave] = i
                break
    asig = [i for i, c in enumerate(cabecera) if re.search(r"asignatura", c or "", re.I) and not COL["creditos"].search(c)]
    if asig and cols.get("nombre") != asig[0]:
        if "modulo" not in cols and "nombre" in cols:
            cols["modulo"] = cols["nombre"]
        cols["nombre"] = asig[0]
    return cols


def distribucion_creditos(tablas: list[dict]) -> dict | None:
    """Tabla resumen «tipo de materia → créditos» (FB, OB, OP, PE, TFG, total)."""
    for t in tablas:
        filas = t.get("contenido") or []
        if t.get("datos_personales") or not 3 <= len(filas) <= 12:
            continue
        res = {}
        for f in filas:
            if len(f) < 2:
                continue
            etiqueta, valor = f[0], _num(f[-1])
            for clave, patron in TIPOS_CREDITO:
                if clave not in res and patron.search(etiqueta.strip()) and valor is not None:
                    res[clave] = valor
                    break
        if len(res) >= 3 and ("obligatorias" in res or "formacion_basica" in res):
            return res
    return None


def plan(tablas: list[dict]) -> list[dict]:
    """Filas de asignatura o materia de las tablas de un plan, con curso y semestre cuando vienen."""
    salida = []
    for n, t in enumerate(tablas):
        filas = t.get("contenido") or []
        if t.get("datos_personales") or len(filas) < 2:
            continue
        cab = filas[0]
        cols = _columnas(cab)
        if "nombre" not in cols and "modulo" in cols:
            cols["nombre"], cols["nivel"] = cols.pop("modulo"), "modulo"
        if "nombre" not in cols or "creditos" not in cols:
            continue
        curso_actual = None
        for f in rellenar(filas[1:], len(cab)):
            nombre = (f[cols["nombre"]] or "").strip().rstrip(".")
            # filas separadoras «Primer curso», «Curso 2.º» dentro de la tabla
            if nombre and len([x for x in f if x.strip()]) == 1 and re.search(r"\bcurso\b", nombre, re.I):
                curso_actual = numero_orden(nombre)
                continue
            if not nombre or TOTAL.match(nombre) or nombre.lower() == (cab[cols["nombre"]] or "").lower():
                continue
            curso = numero_orden(f[cols["curso"]]) if "curso" in cols else None
            semestre = numero_orden(f[cols["semestre"]]) if "semestre" in cols else None
            if "curso_semestre" in cols:
                partes = re.findall(r"\d+", f[cols["curso_semestre"]] or "")
                curso = int(partes[0]) if partes else curso
                semestre = int(partes[1]) if len(partes) > 1 else semestre
            nivel = "modulo" if cols.get("nivel") == "modulo" else (
                "asignatura" if re.search("asignatura", cab[cols["nombre"]], re.I) else "materia")
            salida.append({
                "nombre": nombre,
                "modulo": f[cols["modulo"]].strip().rstrip(".") if "modulo" in cols and isinstance(cols["modulo"], int) else None,
                "caracter": f[cols["caracter"]].strip().rstrip(".") if "caracter" in cols else None,
                "creditos": _num(f[cols["creditos"]]),
                "curso": curso or curso_actual,
                "semestre": semestre,
                "periodo_literal": f[cols["semestre"]] if "semestre" in cols else None,
                "nivel": nivel,
                "tabla": n,
                "fila_literal": f,
            })
    return salida


def menciones(texto: str) -> list[str]:
    """«Mención en Educación Física», «Mención en …»: itinerarios de optatividad citados en el texto."""
    vistas = []
    for m in re.finditer(r"\bMenci[óo]n (?:en|de) ([A-ZÁÉÍÓÚ][^.;:\n]{3,90}?)(?=[.;:\n(]|\s+\d|$)", texto or ""):
        n = m.group(1).strip()
        if n not in vistas:
            vistas.append(n)
    return vistas


def medir_plan(doc: dict) -> dict:
    filas = plan(doc.get("tablas", []))
    asig = [f for f in filas if f["nivel"] == "asignatura"]
    base = asig or filas
    dist = distribucion_creditos(doc.get("tablas", []))
    suma = sum(f["creditos"] or 0 for f in base)
    return {
        "filas": len(filas),
        "asignaturas": len(asig),
        "con_creditos": sum(1 for f in base if f["creditos"]),
        "con_caracter": sum(1 for f in base if f["caracter"]),
        "con_curso": sum(1 for f in base if f["curso"]),
        "con_semestre": sum(1 for f in base if f["semestre"]),
        "suma_creditos": round(suma, 1),
        "distribucion": dist,
        "menciones": menciones(doc.get("texto", "")),
        "tablas": len(doc.get("tablas", [])),
    }


# ----------------------------------------------------------------------------------------- ejecución


def _leer_sumarios(carpeta: Path) -> list[dict]:
    filas = []
    for fichero in sorted(carpeta.glob("*/*/*.jsonl")):
        for linea in fichero.read_text(encoding="utf-8").splitlines():
            if linea.strip():
                filas.append(json.loads(linea))
    return filas


def _escribir(destino: Path, nombre: str, datos: list[dict]) -> None:
    with (destino / nombre).open("w", encoding="utf-8") as f:
        for d in datos:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")


def cmd_actos(sumarios: Path, salida: Path, muestra: int, semilla: int) -> dict:
    lista = actos(_leer_sumarios(sumarios))
    destino = salida / "datos" / "estudios" / "grados"
    destino.mkdir(parents=True, exist_ok=True)
    _escribir(destino, "boe_actos.jsonl", lista)
    res = {"actos": dict(Counter(a["tipo"] for a in lista)),
           "por_anio": dict(sorted(Counter((a["fecha"] or "")[:4] for a in lista).items())),
           "varios_planes": sum(1 for a in lista if a["varios_planes"]),
           "sin_universidad": sum(1 for a in lista if a["tipo"] != "oficialidad" and not a["universidad"]),
           "sin_titulo": sum(1 for a in lista if a["tipo"] != "oficialidad" and not a["titulo_grado"] and not a["varios_planes"])}
    if muestra:
        # muestra al azar con semilla fija: planes nuevos y modificaciones, más todas las altas
        rnd = random.Random(semilla)
        planes = [a for a in lista if a["tipo"] == "plan"]
        modif = [a for a in lista if a["tipo"] == "modificacion"]
        elegidos = rnd.sample(planes, min(muestra, len(planes))) + rnd.sample(modif, min(muestra // 2, len(modif)))
        elegidos += [a for a in lista if a["tipo"] == "oficialidad"]
        res["muestra_ids"] = ",".join(a["identificador"] for a in elegidos)
    (destino / "boe_resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def cmd_textos(ids: list[str], salida: Path, pausa: float, max_minutos: float) -> dict:
    """Descarga los textos (versión HTML del BOE, con robots.txt) y los mide."""
    from motor.archivo import Archivo, solo_huella_por_defecto
    from motor.boe.texto import descargar

    archivo = Archivo(salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    inicio, errores = time.monotonic(), []
    for ident in ids:
        if max_minutos and (time.monotonic() - inicio) / 60 > max_minutos:
            errores.append("tiempo agotado")
            break
        try:
            r = descargar(ident, salida, archivo)
        except ConnectionError as e:
            r = str(e)
        if r != "ok":
            errores.append(f"{ident}: {r}")
        time.sleep(pausa)
    res = cmd_medir(salida / "datos" / "boe" / "textos", None, salida)
    res["errores"] = errores[:50]
    return res


def cmd_medir(textos: Path, actos_fichero: Path | None, salida: Path) -> dict:
    tipos = {}
    if actos_fichero and actos_fichero.exists():
        for linea in actos_fichero.read_text(encoding="utf-8").splitlines():
            a = json.loads(linea)
            tipos[a["identificador"]] = a["tipo"]
    destino = salida / "datos" / "estudios" / "grados"
    destino.mkdir(parents=True, exist_ok=True)
    planes, altas_todas = [], []
    for ruta in sorted(textos.glob("*/*/*.json")):
        doc = json.loads(ruta.read_text(encoding="utf-8"))
        tipo = tipos.get(doc["identificador"]) or tipo_acto(doc.get("titulo") or "")
        if tipo == "oficialidad":
            for x in altas(doc.get("texto", "")):
                altas_todas.append({**x, "boe": doc["identificador"]})
            continue
        if tipo is None:
            continue
        m = medir_plan(doc)
        planes.append({"identificador": doc["identificador"], "tipo": tipo, "titulo": doc.get("titulo"), **m,
                       "plan": plan(doc.get("tablas", []))})
    _escribir(destino, "boe_planes.jsonl", planes)
    _escribir(destino, "boe_altas.jsonl", altas_todas)

    def cuenta(lista, cond):
        return sum(1 for p in lista if cond(p))

    res = {}
    for tipo in ("plan", "modificacion", "denominacion", "correccion"):
        ps = [p for p in planes if p["tipo"] == tipo]
        if not ps:
            continue
        res[tipo] = {
            "leidos": len(ps),
            "con_filas": cuenta(ps, lambda p: p["filas"]),
            "con_asignaturas": cuenta(ps, lambda p: p["asignaturas"]),
            "con_creditos_en_casi_todas": cuenta(ps, lambda p: p["filas"] and p["con_creditos"] >= 0.9 * (p["asignaturas"] or p["filas"])),
            "con_caracter": cuenta(ps, lambda p: p["con_caracter"]),
            "con_curso": cuenta(ps, lambda p: p["con_curso"]),
            "con_semestre": cuenta(ps, lambda p: p["con_semestre"]),
            "con_distribucion_creditos": cuenta(ps, lambda p: p["distribucion"]),
            "con_menciones": cuenta(ps, lambda p: p["menciones"]),
            "suma_cuadra_con_total": cuenta(ps, lambda p: p["distribucion"] and p["distribucion"].get("total")
                                           and abs(p["suma_creditos"] - p["distribucion"]["total"]) <= 6),
        }
    res["altas"] = len(altas_todas)
    res["altas_codigos_distintos"] = len({a["codigo_ruct"] for a in altas_todas})
    (destino / "boe_medicion.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="orden", required=True)
    a = sub.add_parser("actos")
    a.add_argument("--sumarios", required=True)
    a.add_argument("--muestra", type=int, default=0)
    a.add_argument("--semilla", type=int, default=20261030)
    t = sub.add_parser("textos")
    t.add_argument("--ids", required=True)
    t.add_argument("--pausa", type=float, default=1.0)
    t.add_argument("--max-minutos", type=float, default=50)
    m = sub.add_parser("medir")
    m.add_argument("--textos", required=True)
    m.add_argument("--actos")
    for s in (a, t, m):
        s.add_argument("--salida", required=True)
    x = p.parse_args()
    salida = Path(x.salida)
    if x.orden == "actos":
        res = cmd_actos(Path(x.sumarios), salida, x.muestra, x.semilla)
    elif x.orden == "textos":
        res = cmd_textos([i.strip() for i in x.ids.split(",") if i.strip()], salida, x.pausa, x.max_minutos)
    else:
        res = cmd_medir(Path(x.textos), Path(x.actos) if x.actos else None, salida)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
