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

from motor.estudios.boe_masters import RE_UNIV
from motor.grados.catalogo import clave_union

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
    "creditos": re.compile(r"cr[ée]d(?:itos?)?\b|cr[èe]dits?\b|ects", re.I),
    "caracter": re.compile(r"car[áa]cter|^tipo|tipolog", re.I),
    "curso": re.compile(r"^\s*curso\b|\bcurso\s*$", re.I),
    "semestre": re.compile(r"semestre|cuatrimestre|trimestre|temporal|\btemp\b|periodo|duraci", re.I),
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
    # Con dos columnas de créditos («Materia | ECTS | Asignatura | ECTS») la buena es la primera a la derecha
    # del nombre; la otra es el total de la materia o del módulo.
    if "nombre" in cols:
        creditos = [i for i, c in enumerate(cabecera) if COL["creditos"].search(c or "")]
        derecha = [i for i in creditos if i > cols["nombre"]]
        if derecha:
            cols["creditos"] = derecha[0]
    return cols


RESUMEN = re.compile(r"^\s*(tipo|car[áa]cter) de (asignatura|materia|m[óo]dulo|cr[ée]dito|formaci)|^\s*tipo\s*$|"
                     r"^\s*distribuci[óo]n", re.I)
CODIGOS_CARACTER = {
    "basica": {"fb", "b", "bs", "ba", "fba", "bas", "fbr"},
    "obligatoria": {"ob", "o", "obl", "obg", "obli"},
    # «OBM», «OPM»: obligatoria u optativa de mención; en la tabla de créditos cuentan como optatividad
    "optativa": {"op", "opt", "ot", "optat", "obm", "opm", "om", "obme", "opme", "obmen"},
    "practicas": {"pe", "pae", "prt", "pr", "pex", "pext"},
    "tfg": {"tfg", "tfm", "tfg/tfm", "tf"},
}
PALABRAS_CARACTER = [  # por el comienzo del texto, una vez quitado «Materias», «Formación», «Créditos»
    ("optativa", re.compile(r"^obligatori\w* de (?:la )?menci[oó]n")),
    ("basica", re.compile(r"^b[áa]sic")),
    ("tfg", re.compile(r"^trabajo")),
    ("practicas", re.compile(r"^pr[áa]cticas")),
    ("obligatoria", re.compile(r"^obligatori")),
    ("optativa", re.compile(r"^optativ|^optatividad")),
]


def tipo_caracter(c: str | None) -> str | None:
    """«FB. Ciencias Sociales y Jurídicas.», «Básica», «OB», «PAE», «Prácticas externas (obligatorias)» →
    basica, obligatoria, optativa, practicas o tfg."""
    s = sin_acentos_min(c)
    # materias mixtas («Obligatoria / Optativa», «Formación básica (6)» de una materia de 36): sin un solo tipo
    if re.search(r"obligatori\w*\s*(?:/|y|o|,)\s*optativ|optativ\w*\s*(?:/|y|o|,)\s*obligatori|"
                 r"basica\w*\s*(?:/|y|,)\s*obligatori|^(?:formacion\s+)?basica\s*\(\d", s):
        return None
    codigo = re.split(r"[\s.(,;:-]+", s.strip())[0] if s.strip() else ""
    for clave, codigos in CODIGOS_CARACTER.items():
        if codigo in codigos:
            return clave
    s = s.strip()
    while True:  # «Asignaturas de Formación Básica», «Créditos de materias obligatorias»…
        nuevo = re.sub(r"^(materias?|formacion|creditos|asignaturas?|de|las|los|ects)\s+", "", s)
        if nuevo == s:
            break
        s = nuevo
    for clave, patron in PALABRAS_CARACTER:
        if patron.search(s):
            return clave
    return None


def sin_acentos_min(s: str | None) -> str:
    import unicodedata

    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(ch for ch in s if not unicodedata.combining(ch))


RE_TOTAL_DIST = re.compile(r"^(?:creditos\s+)?totale?s?\.?$|^total(?:\s+de)?(?:\s+creditos)?(?:\s+ects)?\.?$")
CLAVE_DIST = {"basica": "formacion_basica", "obligatoria": "obligatorias", "optativa": "optativas",
              "practicas": "practicas_externas", "tfg": "tfg"}


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
            etiqueta, valor = sin_acentos_min(f[0]).strip(" ."), _num(f[-1])
            if valor is None:
                continue
            if RE_TOTAL_DIST.match(etiqueta):
                res.setdefault("total", valor)
                continue
            tipo = tipo_caracter(f[0])
            if tipo and CLAVE_DIST[tipo] not in res:
                res[CLAVE_DIST[tipo]] = valor
        if len(res) >= 3 and ("obligatorias" in res or "formacion_basica" in res):
            if "total" not in res:
                res["total_calculado"] = sum(v for k, v in res.items())
            return res
    return None


def _es_cabecera(fila: list[str]) -> bool:
    return any(COL["nombre"].search(c or "") and not COL["creditos"].search(c or "") for c in fila) and \
        any(COL["creditos"].search(c or "") for c in fila)


def normalizar_tablas(tablas: list[dict]) -> list[dict]:
    """Prepara tablas con formas habituales en los planes del BOE:
      - la cabecera real en la segunda o tercera fila (encima, «Primer semestre | Segundo semestre»);
      - dos o más bloques iguales lado a lado («Asignatura | ECTS | Carácter | Asignatura | ECTS | Carácter»), que se
        separan en tablas, cada una con el periodo de su rótulo como columna «Semestre».
    Las demás tablas pasan igual."""
    salida = []
    for t in tablas:
        filas = t.get("contenido") or []
        if t.get("datos_personales") or len(filas) < 2:
            salida.append(t)
            continue
        i = next((k for k in range(min(3, len(filas))) if _es_cabecera(filas[k])), None)
        if i is None:
            # «| ECTS | Tipo» con la columna del nombre sin rótulo: se le pone «Asignatura»
            k = next((k for k in range(min(3, len(filas))) if len(filas[k]) >= 2 and not (filas[k][0] or "").strip()
                      and any(COL["creditos"].search(c or "") for c in filas[k][1:])), None)
            if k is None:
                salida.append(t)
                continue
            filas = filas[:k] + [["Asignatura"] + list(filas[k][1:])] + filas[k + 1:]
            t = {**t, "nombre_sin_rotulo": True}
            i = k
        # rótulos de una sola celda encima de la cabecera («Total de créditos de formación básica = 60»)
        rotulo_tabla = " ".join(c.strip() for f in filas[:i] for c in f if len([x for x in f if (x or "").strip()]) == 1
                                and (c or "").strip())
        if rotulo_tabla:
            t = {**t, "rotulo": rotulo_tabla}
        cab, rotulos = filas[i], (filas[i - 1] if i > 0 else [])
        inicios = [k for k, c in enumerate(cab) if COL["nombre"].search(c or "") and not COL["creditos"].search(c or "")
                   and not COL["modulo"].search(c or "")]
        ancho = len(cab) // len(inicios) if inicios else 0
        bloques = {tuple(" ".join((c or "").lower().split()) for c in cab[k:k + ancho]) for k in inicios} if ancho else set()
        if len(inicios) < 2 or len(cab) % len(inicios) or len(bloques) != 1:  # bloques repetidos de verdad
            salida.append({**t, "contenido": filas[i:]})
            continue
        for b, ini in enumerate(inicios):
            rotulo = rotulos[b] if b < len(rotulos) else ""
            sub = [cab[ini:ini + ancho] + (["Semestre"] if rotulo else [])]
            for f in filas[i + 1:]:
                trozo = f[ini:ini + ancho] if len(f) == len(cab) else []
                if trozo and any(x.strip() for x in trozo):
                    sub.append(trozo + ([rotulo] if rotulo else []))
            salida.append({**t, "contenido": sub})
    return salida


def _corregir_columnas(cols: dict[str, int], filas: list[list[str]]) -> dict[str, int]:
    """Si la columna de créditos trae textos y la de carácter números, la cabecera está cambiada de orden."""
    if "creditos" in cols and "caracter" in cols:
        cuerpo = [f for f in filas[1:] if len(f) > max(cols["creditos"], cols["caracter"])]
        num = lambda v: bool(re.fullmatch(r"\s*\d+(?:[.,]\d+)?\s*", v or ""))  # noqa: E731
        if cuerpo and sum(num(f[cols["caracter"]]) for f in cuerpo) > len(cuerpo) / 2 \
                and sum(num(f[cols["creditos"]]) for f in cuerpo) < len(cuerpo) / 4:
            cols["creditos"], cols["caracter"] = cols["caracter"], cols["creditos"]
    return cols


def tipo_de_rotulo(texto: str | None) -> str | None:
    """Tipo de las asignaturas de una tabla o de un tramo por su rótulo: «Total de créditos de formación básica
    = 60», «Asignaturas obligatorias», «Optatividad». Con más de un tipo en el rótulo, ninguno."""
    s = sin_acentos_min(texto)
    hallados = {clave for clave, patron in (
        ("basica", r"formacion basica|\bbasicas?\b"), ("obligatoria", r"obligatori"), ("optativa", r"optativ"),
        ("practicas", r"practicas (?:externas|academicas|curriculares)|\bpracticum\b"),
        ("tfg", r"trabajo (?:de )?fin")) if re.search(patron, s)}
    return hallados.pop() if len(hallados) == 1 else None


def _separador(texto: str, estado: dict) -> None:
    """Fila de una sola celda: «Primer curso», «Segundo semestre», «Curso 2.º - Semestre 1», «Formación básica»,
    «Módulo 3. Gestión»: actualiza el estado que heredan las filas siguientes."""
    for parte in re.split(r"[.,;:–—/-]\s+|\s+[–—-]\s+", texto):
        if re.search(r"semestre|cuatrimestre", parte, re.I):
            estado["semestre"] = numero_orden(parte)
        elif re.search(r"\bcurso\b", parte, re.I):
            estado["curso"], estado["semestre"] = numero_orden(parte), None
        elif tipo_de_rotulo(parte):
            estado["tipo"] = tipo_de_rotulo(parte)
        elif re.search(r"\bm[óo]dulo\b|\bmateria\b", parte, re.I):
            estado["modulo"] = texto.strip().rstrip(" .")


def _con_separadores(filas: list[list[str]], ancho: int) -> list[tuple[list[str], dict]]:
    """Filas del cuerpo con su estado (curso, semestre, tipo, módulo) heredado de las filas separadoras, y las
    celdas combinadas (rowspan) completadas por la izquierda con la fila anterior. Las separadoras no salen."""
    estado: dict = {"curso": None, "semestre": None, "tipo": None, "modulo": None}
    salida, previa = [], [""] * ancho
    for f in filas:
        llenas = [x for x in f if (x or "").strip()]
        if ancho >= 2 and len(llenas) == 1 and not re.fullmatch(r"\s*\d+(?:[.,]\d+)?\s*", llenas[0]):
            _separador(llenas[0], estado)
            continue
        if len(f) < ancho:
            f = previa[: ancho - len(f)] + list(f)
        f = list(f[:ancho]) + [""] * (ancho - len(f))
        salida.append((f, dict(estado)))
        previa = f
    return salida


def _curso_y_semestre(curso: int | None, semestre: int | None) -> tuple[int | None, int | None]:
    """«Semestre 5» sin curso o con su curso → curso 3, semestre 1 (dos semestres por curso)."""
    if semestre and semestre > 2:
        return curso or (semestre + 1) // 2, (semestre - 1) % 2 + 1
    return curso, semestre


RE_LISTA_CELDA = re.compile(r"asignaturas?\s*:\s*[–—-]", re.I)
RE_ITEM_CELDA = re.compile(r"[–—]\s*([^–—]+)")


def _plan_en_celdas(filas: list[list[str]], n: int) -> list[dict]:
    """Planes con las asignaturas escritas dentro de las celdas de un cuadro curso × semestre:
    «| Curso 1 | ECTS: 30. Asignaturas: – Álgebra Lineal (6 ECTS). – Inglés B2.1 (6 ECTS). |» o «– Mundo medieval
    (B).». El curso sale de la fila y el semestre de la cabecera de la columna."""
    cab, salida = filas[0], []
    for f in filas[1:]:
        curso_fila = numero_orden(f[0]) if f and re.search(r"curso", f[0] or "", re.I) else None
        for j, celda in enumerate(f):
            if not RE_LISTA_CELDA.search(celda or ""):
                continue
            semestre_col = numero_orden(cab[j]) if j < len(cab) and re.search(r"semestre|cuatrimestre", cab[j] or "", re.I) else None
            curso, semestre = _curso_y_semestre(curso_fila, semestre_col)
            lista = RE_LISTA_CELDA.split(celda, maxsplit=1)[-1]
            for m in RE_ITEM_CELDA.finditer("– " + lista):
                item = m.group(1).strip().rstrip(" .")
                parentesis = re.findall(r"\(([^)]*)\)", item)
                nombre = re.sub(r"\s*\([^)]*\)", "", item).strip().rstrip(" .")
                creditos = next((_num(x) for x in parentesis if re.search(r"ects|cr[ée]d", x, re.I)), None)
                codigo = next((x.strip() for x in parentesis if re.fullmatch(r"\s*[A-Za-z]{1,4}\s*", x)), None)
                if nombre:
                    salida.append({"nombre": nombre, "modulo": None, "caracter": codigo, "tipo": tipo_caracter(codigo),
                                   "creditos": creditos, "curso": curso, "semestre": semestre, "periodo_literal": None,
                                   "nivel": "asignatura", "tabla": n, "fila_literal": None})
    return salida


def _basicas_por_ambito(tablas: list[dict]) -> set[str]:
    """Nombres de las tablas «Asignatura | Ámbito de conocimiento»: en el RD 822/2021 la formación básica va
    vinculada a ámbitos, y esas tablas son su lista."""
    salida = set()
    for t in tablas:
        filas = t.get("contenido") or []
        if len(filas) >= 2 and len(filas[0]) == 2 and re.search(r"asignatura", filas[0][0] or "", re.I) \
                and re.search(r"[áa]mbito", filas[0][1] or "", re.I):
            salida |= {clave_union(f[0]) for f in filas[1:] if f and f[0]}
    return salida


def plan(tablas: list[dict], dist: dict | None = None) -> list[dict]:
    """Filas de asignatura o materia del plan, con carácter, créditos, curso y semestre cuando vienen.

    Un plan suele repetir asignaturas en varias tablas (la de formación básica por rama y la del plan completo):
    se leen todas y se queda, para cada nombre, la fila de la tabla más completa.

    El tipo (básica, obligatoria…) sale de la columna de carácter; si no la hay, del rótulo de la tabla o de su
    fila de total («Total de créditos de formación obligatoria»); y si tampoco, de la tabla de créditos por tipo
    (dist): cuando la suma de la tabla es exactamente la de un solo tipo, sus filas son de ese tipo.
    """
    por_tabla = []
    for n, t in enumerate(normalizar_tablas(tablas)):
        filas = t.get("contenido") or []
        if t.get("datos_personales") or len(filas) < 2:
            continue
        cab = filas[0]
        if RESUMEN.search(cab[0] or "") and len(cab) <= 3 or distribucion_creditos([t]) is not None:
            continue  # tabla de créditos por tipo: se lee aparte (distribucion_creditos)
        filas_estado = _con_separadores(filas[1:], len(cab))
        cuerpo = [f for f, _ in filas_estado]
        cols = _corregir_columnas(_columnas(cab), [cab] + cuerpo)
        if "nombre" not in cols and "modulo" in cols:
            cols["nombre"], cols["nivel"] = cols.pop("modulo"), "modulo"
        if "nombre" not in cols or "creditos" not in cols:
            if any(RE_LISTA_CELDA.search(c or "") for f in filas[1:] for c in f):
                salida = _plan_en_celdas(filas, n)
                if salida:
                    por_tabla.append((0, len(salida), n, salida))
            continue
        # rótulo encima de la tabla o en la propia cabecera de la columna del nombre («Asignaturas optativas»)
        tipo_tabla = tipo_de_rotulo(t.get("rotulo")) or tipo_de_rotulo(cab[cols["nombre"]])
        if not tipo_tabla:  # fila de total al pie: «Total de créditos de formación obligatoria. | 150»
            pies = {tipo_de_rotulo(f[cols["nombre"]]) for f in cuerpo if TOTAL.match((f[cols["nombre"]] or "").strip())}
            pies.discard(None)
            tipo_tabla = pies.pop() if len(pies) == 1 else None
        salida = []
        for f, estado in filas_estado:
            nombre = (f[cols["nombre"]] or "").strip().rstrip(" .")
            if not nombre or TOTAL.match(nombre) or nombre.lower() == (cab[cols["nombre"]] or "").lower():
                continue
            curso = numero_orden(f[cols["curso"]]) if "curso" in cols else None
            semestre = numero_orden(f[cols["semestre"]]) if "semestre" in cols else None
            if "curso_semestre" in cols:
                partes = re.findall(r"\d+", f[cols["curso_semestre"]] or "")
                curso = int(partes[0]) if partes else curso
                semestre = int(partes[1]) if len(partes) > 1 else semestre
            curso, semestre = _curso_y_semestre(curso or estado["curso"], semestre or estado["semestre"])
            nivel = "modulo" if cols.get("nivel") == "modulo" else (
                "asignatura" if re.search("asignatura", cab[cols["nombre"]], re.I) else "materia")
            caracter = f[cols["caracter"]].strip().rstrip(" .") if "caracter" in cols else None
            modulo = f[cols["modulo"]].strip().rstrip(" .") if "modulo" in cols and isinstance(cols["modulo"], int) else None
            salida.append({
                "nombre": nombre,
                "modulo": modulo or estado["modulo"],
                "caracter": caracter,
                "tipo": tipo_caracter(caracter) or estado["tipo"] or tipo_tabla,
                "tipo_por_rotulo": not tipo_caracter(caracter) and bool(estado["tipo"] or tipo_tabla),
                "creditos": _num(f[cols["creditos"]]),
                "curso": curso,
                "semestre": semestre,
                "periodo_literal": f[cols["semestre"]] if "semestre" in cols else None,
                "nivel": nivel,
                "tabla": n,
                "fila_literal": f,
            })
        if salida:
            por_tabla.append((0, len(salida), n, salida))
    # tablas sin ningún tipo: si su suma es la de un tipo que ninguna otra tabla trae, son de ese tipo
    presentes = {x["tipo"] for *_, sal in por_tabla for x in sal if x["tipo"]}
    for *_, sal in por_tabla:
        if dist and not any(x["tipo"] for x in sal):
            suma = sum(x["creditos"] or 0 for x in sal)
            iguales = [tipo for tipo, clave in CLAVE_DIST.items()
                       if tipo not in presentes and dist.get(clave) and abs(dist[clave] - suma) <= 0.5]
            if len(iguales) == 1:
                presentes.add(iguales[0])
                for x in sal:
                    x["tipo"], x["tipo_por_suma_de_tabla"] = iguales[0], True
    # riqueza: el tipo leído en su columna vale más que el deducido del rótulo o de la suma
    por_tabla = [(sum((0.5 if x.get("tipo_por_rotulo") or x.get("tipo_por_suma_de_tabla") else 1) * bool(x["tipo"])
                      + bool(x["curso"]) + bool(x["semestre"]) for x in sal) / len(sal), k, n, sal)
                 for _, k, n, sal in por_tabla]
    # la misma asignatura en varias tablas: se queda la de la tabla más completa; dentro de una misma tabla se
    # conservan las repetidas (una materia repartida en dos cursos, varias «Optativa» de 6 créditos)
    vistos: dict[tuple, int] = {}
    resultado = []
    for _, _, n, salida in sorted(por_tabla, key=lambda x: (-x[0], -x[1], x[2])):
        for x in salida:
            k = (clave_union(x["nombre"]) or x["nombre"].lower(), x["nivel"])  # «Trabajo de Fin de Grado» = «Trabajo Fin de Grado»
            if vistos.setdefault(k, n) == n:
                resultado.append(x)
    # filas aún sin tipo: el TFG, las prácticas y las optativas por su nombre; las básicas por la tabla de ámbitos;
    # y el resto, obligatorias solo si su suma es exactamente la de obligatorias de la tabla de créditos
    basicas = _basicas_por_ambito(tablas)
    for x in resultado:
        if not x["tipo"]:
            por_nombre = tipo_de_rotulo(x["nombre"])
            if por_nombre in ("tfg", "practicas", "optativa"):
                x["tipo"], x["tipo_por_nombre"] = por_nombre, True
            elif clave_union(x["nombre"]) in basicas:
                x["tipo"], x["tipo_por_tabla_de_ambitos"] = "basica", True
    resto = [x for x in resultado if not x["tipo"]]
    if dist and resto and dist.get("obligatorias") and \
            abs(sum(x["creditos"] or 0 for x in resto) - dist["obligatorias"]) <= 0.5:
        for x in resto:
            x["tipo"], x["tipo_por_suma_de_tabla"] = "obligatoria", True
    return resultado


def menciones(texto: str) -> list[str]:
    """«Mención en Educación Física», «Mención en …»: itinerarios de optatividad citados en el texto."""
    vistas = []
    for m in re.finditer(r"\bMenci[óo]n (?:en|de) ([A-ZÁÉÍÓÚ][^.;:\n]{3,90}?)(?=[.;:\n(]|\s+\d|$)", texto or ""):
        n = m.group(1).strip()
        if n not in vistas:
            vistas.append(n)
    return vistas


RE_ANEXO = re.compile(r"^ANEXO\b", re.I)
RE_CABECERA_PLAN = re.compile(r"^(?:\d{1,2}\.\s*)?(?:Plan(?:es)? de estudios?|ANEXO|Denominaci[oó]n del t[ií]tulo:)\s*"
                              r".*?\b((?:Graduad[oa]|Grado)\b.*?\ben\s+.+?)\.?$")
RE_SOLO_TITULO = re.compile(r"^((?:Graduad[oa]|Grado)\b.*?\ben\s+.+?)\.?$")


def cabeceras_de_plan(texto: str) -> list[tuple[int, str]]:
    """(posición, título) de cada plan en una resolución con varios: «Plan de estudios conducente al título de
    Graduado o Graduada en X», «ANEXO II. Grado en X» o la línea «Graduado o Graduada en X» tras «ANEXO II»."""
    salida, previa, pos = [], "", 0
    for linea in (texto or "").split("\n"):
        limpia = linea.strip()
        m = RE_CABECERA_PLAN.match(limpia) or (RE_SOLO_TITULO.match(limpia) if RE_ANEXO.match(previa) else None)
        if m:
            titulo = re.sub(r"\s+por la Universi.*$", "", m.group(1)).strip().rstrip(".")
            if not salida or salida[-1][1] != titulo:
                salida.append((pos, titulo))
        if limpia:
            previa = limpia
        pos += len(linea) + 1
    return salida


def separar_planes(doc: dict) -> list[dict]:
    """Una resolución con varios planes («por la que se publican planes de estudios») trae una tabla de créditos
    por tipo al comienzo de cada plan, en el orden de sus anexos. Si hay tantas como títulos de plan en el texto,
    se separa en un documento por plan con su «titulo_grado»; si no cuadran, se deja entero (sin título)."""
    tablas = doc.get("tablas") or []
    grupos: list[list[dict]] = []
    for t in tablas:
        es_dist = distribucion_creditos([t]) is not None
        if not grupos or es_dist and any(distribucion_creditos([x]) is None for x in grupos[-1]):
            grupos.append([])
        grupos[-1].append(t)
    cabeceras = cabeceras_de_plan(doc.get("texto", ""))
    if len(grupos) < 2 or len(grupos) != len(cabeceras):
        return [doc]
    texto = doc.get("texto", "")
    partes = []
    for k, (grupo, (pos, titulo)) in enumerate(zip(grupos, cabeceras)):
        fin = cabeceras[k + 1][0] if k + 1 < len(cabeceras) else len(texto)
        partes.append({**doc, "tablas": grupo, "texto": texto[pos:fin], "titulo_grado": titulo, "parte": k + 1,
                       "partes": len(grupos)})
    return partes


def medir_plan(doc: dict) -> dict:
    """Medidas del plan y su comprobación contra la tabla de créditos por tipo. Si los tipos deducidos por el
    nombre («Prácticas externas», «Trabajo fin de grado» sin columna de carácter) impiden cuadrar y sin ellos
    cuadra, se quitan: unas prácticas pueden ser optativas. «filas_plan» lleva las filas con que se midió."""
    dist = distribucion_creditos(doc.get("tablas", []))
    filas = plan(doc.get("tablas", []), dist)
    m = _medir(filas, dist, doc)
    if not m["comprobacion"]:
        for alt in _alternativas(filas, dist):
            m2 = _medir(alt, dist, doc)
            if m2["comprobacion"]:
                filas, m = alt, {**m2, "interpretacion": "alternativa"}
                break
    m["filas_plan"] = filas
    return m


def _alternativas(filas: list[dict], dist: dict | None = None):
    """Lecturas más prudentes del mismo plan, de menos a más recorte: sin los tipos deducidos por el nombre, por
    el rótulo o por la suma, y sin las tablas que repiten casi entera otra (listas resumen de la formación básica
    con nombres algo distintos que contarían dos veces)."""
    sin = lambda marca: [{**x, "tipo": None, marca: False} if x.get(marca) else x for x in filas]  # noqa: E731
    for marca in ("tipo_por_nombre", "tipo_por_rotulo", "tipo_por_suma_de_tabla", "tipo_por_tabla_de_ambitos"):
        if any(x.get(marca) for x in filas):
            yield sin(marca)
    por_tabla: dict = {}
    for x in filas:
        por_tabla.setdefault(x["tabla"], []).append(x)
    if dist and len(por_tabla) > 1:
        # un tipo repartido en varias tablas cuando una sola ya suma lo de la tabla de créditos (la lista de
        # formación básica completa y, en el plan por cursos, algunas básicas con otro nombre): vale esa tabla
        for tipo, clave in CLAVE_DIST.items():
            if not dist.get(clave):
                continue
            exactas = [n for n, xs in por_tabla.items()
                       if abs(sum(x["creditos"] or 0 for x in xs if x["tipo"] == tipo) - dist[clave]) <= 0.5]
            otras = [n for n, xs in por_tabla.items() if n not in exactas and any(x["tipo"] == tipo for x in xs)]
            if len(exactas) == 1 and otras:
                yield [x for x in filas if not (x["tipo"] == tipo and x["tabla"] != exactas[0])]
    if len(por_tabla) > 1:
        claves = {n: {clave_union(x["nombre"]) for x in xs} for n, xs in por_tabla.items()}
        # una tabla es «repetida» si la mitad o más de sus palabras clave están en otras tablas del plan
        palabras = {n: set().union(*(k.split() for k in ks)) for n, ks in claves.items()}
        repetidas = {n for n in por_tabla if palabras[n] and len(palabras[n] & set().union(
            *(palabras[m] for m in por_tabla if m != n))) >= 0.8 * len(palabras[n]) and len(por_tabla[n]) <= 15}
        for n in sorted(repetidas):
            yield [x for x in filas if x["tabla"] != n]


def _medir(filas: list[dict], dist: dict | None, doc: dict) -> dict:
    asig = [f for f in filas if f["nivel"] == "asignatura"]
    base = asig or filas
    suma = sum(f["creditos"] or 0 for f in base)
    fijos = sum(f["creditos"] or 0 for f in base if f["tipo"] in ("basica", "obligatoria", "practicas", "tfg"))
    esperado = sum(dist.get(k, 0) for k in ("formacion_basica", "obligatorias", "practicas_externas", "tfg")) \
        if dist else None
    # Básicas + obligatorias: lo que más importa del listado de asignaturas (prácticas y TFG a veces no van en tabla)
    bo = sum(f["creditos"] or 0 for f in base if f["tipo"] in ("basica", "obligatoria"))
    bo_esperado = (dist.get("formacion_basica", 0) + dist.get("obligatorias", 0)) if dist else None
    pe_tfg = sum(f["creditos"] or 0 for f in base if f["tipo"] in ("practicas", "tfg"))
    if esperado and abs(fijos - esperado) <= 0.5:
        comprobacion = "completo"
    elif bo_esperado and abs(bo - bo_esperado) <= 0.5 and pe_tfg == 0:
        # básicas y obligatorias cuadran y las prácticas y el TFG no van en tabla: se toman de la de créditos
        comprobacion = "basicas_y_obligatorias"
    else:
        comprobacion = None
    return {
        "comprobacion": comprobacion,
        "filas": len(filas),
        "asignaturas": len(asig),
        "con_creditos": sum(1 for f in base if f["creditos"]),
        "con_caracter": sum(1 for f in base if f["caracter"]),
        "con_curso": sum(1 for f in base if f["curso"]),
        "con_semestre": sum(1 for f in base if f["semestre"]),
        "suma_creditos": round(suma, 1),
        "suma_sin_optativas": round(fijos, 1),
        "esperado_sin_optativas": esperado,
        "basicas_obligatorias": round(bo, 1),
        "basicas_obligatorias_esperado": bo_esperado,
        "con_tipo": sum(1 for f in base if f["tipo"]),
        "distribucion": dist,
        "menciones": menciones(doc.get("texto", "")),
        "tablas": len(doc.get("tablas", [])),
        "tablas_del_plan_retenidas_por_privacidad": sum(
            1 for t in doc.get("tablas", []) if t.get("datos_personales")
            and re.search(r"asignatura|materia|cr[ée]ditos|ects", " ".join(t.get("cabecera") or []), re.I)),
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
        for parte in separar_planes(doc):
            m = medir_plan(parte)
            filas = m.pop("filas_plan")
            extra = {k: parte[k] for k in ("titulo_grado", "parte", "partes") if k in parte}
            planes.append({"identificador": doc["identificador"], "tipo": tipo, "titulo": doc.get("titulo"), **extra,
                           **m, "plan": filas})
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
            "con_tipo_en_casi_todas": cuenta(ps, lambda p: p["filas"] and p["con_tipo"] >= 0.9 * (p["asignaturas"] or p["filas"])),
            "cuadran_creditos_sin_optativas": cuenta(ps, lambda p: p["esperado_sin_optativas"]
                                                    and abs(p["suma_sin_optativas"] - p["esperado_sin_optativas"]) <= 0.5),
            "cuadran_basicas_y_obligatorias": cuenta(ps, lambda p: p["basicas_obligatorias_esperado"]
                                                    and abs(p["basicas_obligatorias"] - p["basicas_obligatorias_esperado"]) <= 0.5),
            "comprobados": cuenta(ps, lambda p: p["comprobacion"]),
            "comprobados_sin_practicas_ni_tfg_en_tabla": cuenta(ps, lambda p: p["comprobacion"] == "basicas_y_obligatorias"),
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
    t.add_argument("--ids", help="identificadores separados por comas")
    t.add_argument("--ids-fichero", help="fichero con un identificador por línea o planes_pendientes.json")
    t.add_argument("--desde", type=int, default=0)
    t.add_argument("--hasta", type=int)
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
        if x.ids_fichero:
            bruto = Path(x.ids_fichero).read_text(encoding="utf-8")
            ids = json.loads(bruto)["ids"] if bruto.lstrip().startswith("{") else bruto.split()
        else:
            ids = [i.strip() for i in (x.ids or "").split(",") if i.strip()]
        res = cmd_textos(ids[x.desde:x.hasta], salida, x.pausa, x.max_minutos)
    else:
        res = cmd_medir(Path(x.textos), Path(x.actos) if x.actos else None, salida)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
