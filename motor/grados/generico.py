"""Grado genérico: el mismo grado en distintas universidades («Derecho» de 79 universidades) y su área.

Dos niveles, los dos necesarios para las páginas y el comparador:
  - grado genérico: títulos con el mismo nombre una vez normalizado (sin la versión en inglés de los
    bilingües, sin notas como «(Plan nuevo)», con «Maestro en Educación Primaria» = «Educación Primaria»).
    Es la página /grado/{grado}/ y la base del comparador «el mismo grado en otra universidad».
  - área: el campo de estudio del SIIU (137 campos con grado activo), la clasificación del propio Ministerio.
    Agrupa títulos con nombres distintos («Ingeniería Informática», «Ingeniería en Sistemas de Información»).
    Sirve para «carreras parecidas» y para los grados de nombre único, que no tienen página genérica propia.

Ley SEO: un grado genérico con un solo título no tiene página propia (sería casi igual que la ficha). Con dos o
más títulos sí, porque reúne datos que no están juntos en otro sitio (asignaturas comparadas, precio, nota y
plazas de cada universidad).

Dobles grados: su genérico es la combinación de los genéricos de sus componentes, sin orden («Derecho y
Administración y Dirección de Empresas» = «ADE y Derecho»).

Uso:
  python -m motor.grados.generico --catalogo ruta/catalogo.jsonl --salida ruta/
Escribe datos/estudios/grados/genericos.jsonl y genericos_resumen.json.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from motor.grados.catalogo import clave, clave_union

# «Maestro en Educación Primaria», «Maestro o Maestra en…», «Magisterio de…», «Maestro/a de…» → «Educación Primaria»
RE_MAESTRO = re.compile(r"^(?:maestro(?:\s*/\s*a|\s+o\s+maestra)?|magisterio)\s+(?:en|de)\s+(?:la\s+)?", re.I)
RE_NOTA = re.compile(r"\s*\((?:plan\s+nuevo|plan\s+\d{4}|nuevo\s+plan|semipresencial|presencial|a\s+distancia|online|"
                     r"en\s+ingl[eé]s|ingl[eé]s|biling[uü]e|[^()]*\bsede\b[^()]*|[^()]*\bcampus\b[^()]*)\)\s*$", re.I)


def nombre_base(nombre: str) -> str:
    """Nombre en castellano sin versión inglesa ni notas: «Derecho / Bachelor in Law» → «Derecho»."""
    s = " ".join((nombre or "").split())
    s = re.split(r"\s*/\s*(?=Bachelor|Degree|BA\b|BSc\b|Grau\b)|\s+-\s+(?=Bachelor)|-(?=Bachelor)", s)[0]
    # «Economía / Economics»: la segunda mitad en inglés (sin acentos y con palabras inglesas habituales)
    partes = re.split(r"\s*/\s*", s)
    if len(partes) == 2 and re.search(r"\b(and|of|in|the|studies|science|engineering|management|business|law|economics|"
                                      r"design|psychology|mathematics|international|relations|marketing|data)\b",
                                      partes[1], re.I):
        s = partes[0]
    s = RE_NOTA.sub("", s)
    s = re.sub(r"\s*\((?:[A-Z]{2,5})\)\s*$", "", s)  # siglas al final: «(ADE)», «(BBA)», «(MIM)»
    s = RE_MAESTRO.sub("", s)
    return s.strip(" .")


def clave_generico(nombre: str) -> str:
    return clave_union(nombre_base(nombre))


def slug(texto: str) -> str:
    return "-".join(clave(texto).split())


def agrupar(catalogo: list[dict], situaciones: tuple[str, ...] = ("Activo",)) -> list[dict]:
    titulos = [t for t in catalogo if t["situacion"] in situaciones and t["clase"] in ("grado", "doble")]
    por_codigo = {t["codigo"]: t for t in catalogo}
    grupos: dict[str, list[dict]] = defaultdict(list)
    for t in titulos:
        if t["clase"] == "grado":
            grupos["g:" + clave_generico(t["nombre"])].append(t)
    # nombre visible de cada genérico simple: la forma base más frecuente
    visible = {}
    for k, ts in grupos.items():
        visible[k] = Counter(nombre_base(t["nombre"]) for t in ts).most_common(1)[0][0]
    for t in titulos:
        if t["clase"] != "doble":
            continue
        partes = []
        for c in t["componentes"]:
            nombre = por_codigo[c["codigo"]]["nombre"] if c.get("codigo") else c["nombre"]
            partes.append(clave_generico(nombre))
        grupos["d:" + "+".join(sorted(partes))].append(t)
    salida = []
    for k, ts in grupos.items():
        tipo = "doble" if k.startswith("d:") else "grado"
        if tipo == "grado":
            nombre = visible[k]
        else:
            nombres = []
            for parte in k[2:].split("+"):
                nombres.append(visible.get("g:" + parte) or next(
                    nombre_base(c["nombre"]) for t in ts for c in t["componentes"] if clave_generico(c["nombre"]) == parte))
            nombre = " y ".join(nombres)
        universidades = sorted({u["nombre"] for t in ts for u in t["universidades"]})
        campos = Counter(t.get("campo") for t in ts if t.get("campo"))
        salida.append({
            "id": ("doble-" if tipo == "doble" else "") + slug(k[2:].replace("+", " y ")),
            "tipo": tipo,
            "clave": k[2:],
            "nombre": nombre,
            "slug": slug(nombre),
            "titulos": sorted(t["codigo"] for t in ts),
            "universidades": len(universidades),
            "publicas": len({u["nombre"] for t in ts for u in t["universidades"] if u["tipo"] == "Pública"}),
            "privadas": len({u["nombre"] for t in ts for u in t["universidades"] if u["tipo"] == "Privada"}),
            "area": campos.most_common(1)[0][0] if campos else None,
            "rama": Counter(t.get("rama") for t in ts).most_common(1)[0][0],
            "nombres_oficiales": sorted({t["nombre"] for t in ts}),
            "pagina_propia": len(ts) >= 2,
        })
    return sorted(salida, key=lambda g: (-len(g["titulos"]), g["nombre"]))


def resumen(genericos: list[dict], catalogo: list[dict]) -> dict:
    simples = [g for g in genericos if g["tipo"] == "grado"]
    dobles = [g for g in genericos if g["tipo"] == "doble"]
    n_simples = sum(len(g["titulos"]) for g in simples)
    con_pagina = [g for g in simples if g["pagina_propia"]]
    return {
        "genericos_grado": len(simples),
        "genericos_grado_con_pagina": len(con_pagina),
        "titulos_en_genericos_con_pagina": sum(len(g["titulos"]) for g in con_pagina),
        "titulos_grado": n_simples,
        "genericos_un_solo_titulo": sum(1 for g in simples if not g["pagina_propia"]),
        "genericos_doble": len(dobles),
        "genericos_doble_con_pagina": sum(1 for g in dobles if g["pagina_propia"]),
        "areas_con_grado": len({g["area"] for g in simples if g["area"]}),
        "mas_ofertados": [(g["nombre"], len(g["titulos"])) for g in simples[:25]],
        "dobles_mas_ofertados": [(g["nombre"], len(g["titulos"])) for g in dobles[:15]],
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--catalogo", required=True)
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    catalogo = [json.loads(l) for l in Path(a.catalogo).read_text(encoding="utf-8").splitlines() if l.strip()]
    genericos = agrupar(catalogo)
    destino = Path(a.salida) / "datos" / "estudios" / "grados"
    destino.mkdir(parents=True, exist_ok=True)
    with (destino / "genericos.jsonl").open("w", encoding="utf-8") as f:
        for g in genericos:
            f.write(json.dumps(g, ensure_ascii=False) + "\n")
    res = resumen(genericos, catalogo)
    (destino / "genericos_resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
