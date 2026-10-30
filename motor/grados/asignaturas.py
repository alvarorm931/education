"""Asignaturas comparadas entre universidades del mismo grado genérico: qué se estudia en todas y qué solo en una.

Es un dato propio que no da nadie: para «Derecho», en cuántas de las universidades que lo imparten aparece cada
asignatura («Derecho Civil» en 52 de 53), qué parte de los créditos de cada universidad es común con la mayoría y
qué asignaturas solo tiene ella. Sale de los planes comprobados (la suma cuadra con su tabla de créditos).

Los nombres se comparan normalizados: sin numeración («Derecho Civil I», «Derecho Civil II» → «derecho civil»), sin
palabras vacías ni plurales. No se juntan nombres distintos: «Estadística» y «Estadística Aplicada» siguen siendo
dos asignaturas (mejor quedarse corto que inventar equivalencias).
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from motor.grados.catalogo import clave_union

NUMERACION = re.compile(r"\s+(?:[ivx]{1,4}|\d{1,2}|[abc])$")
COMUN = 0.5  # una asignatura es «común» si está en la mitad o más de las universidades del grado


def clave_asignatura(nombre: str) -> str:
    k = clave_union(nombre or "")
    anterior = None
    while k != anterior:  # «derecho civil ii», «estadistica 1»
        anterior = k
        k = NUMERACION.sub("", k)
    return k


def comparar(planes: dict[str, list[dict]]) -> dict:
    """planes: código del título → asignaturas [{nombre, creditos, tipo, curso}]. Devuelve el cuadro del genérico."""
    claves_por_titulo = {c: {clave_asignatura(a["nombre"]) for a in asig if a.get("nombre")} for c, asig in planes.items()}
    n = len(claves_por_titulo)
    frecuencia = Counter(k for ks in claves_por_titulo.values() for k in ks)
    nombre_visible: dict[str, Counter] = defaultdict(Counter)
    for asig in planes.values():
        for a in asig:
            nombre_visible[clave_asignatura(a["nombre"])][NUMERACION.sub("", (a["nombre"] or "").strip())] += 1
    por_titulo = {}
    for c, asig in planes.items():
        total = sum(a.get("creditos") or 0 for a in asig if a.get("tipo") != "optativa") or None
        comunes = sum(a.get("creditos") or 0 for a in asig if a.get("tipo") != "optativa"
                      and frecuencia[clave_asignatura(a["nombre"])] / n >= COMUN)
        exclusivas = sorted({NUMERACION.sub("", a["nombre"].strip()) for a in asig
                             if frecuencia[clave_asignatura(a["nombre"])] == 1 and a.get("tipo") != "optativa"})
        por_titulo[c] = {
            "creditos_no_optativos": total,
            "porcentaje_comun": round(100 * comunes / total, 1) if total else None,
            "asignaturas_solo_aqui": exclusivas if n >= 3 else [],  # con menos de tres planes no se dice «solo aquí»
            "primer_curso": [a["nombre"] for a in asig if a.get("curso") == 1],
        }
    mas = [{"asignatura": nombre_visible[k].most_common(1)[0][0], "titulos": v, "de": n}
           for k, v in frecuencia.most_common() if v / n >= COMUN]
    return {"planes_comparados": n, "asignaturas_comunes": mas, "por_titulo": por_titulo}
