"""Relaciones entre carreras: carreras parecidas, dobles grados que incluyen cada una y buscador por asignatura.

Todo sale de lo ya capturado (fichas.jsonl y genericos.jsonl), sin pedir nada a ninguna fuente:

- parecidas: para cada grado genérico con página, los genéricos más cercanos por campo ISCED-F, ámbito, área y
  rama del SIIU, por las palabras del nombre, por los dobles grados que los combinan y, cuando hay planes
  comprobados en los dos, por las asignaturas básicas y obligatorias que comparten. Cada relación lleva sus motivos (para explicarla en la página, no una caja negra);
- dobles: los dobles grados con página que incluyen cada genérico, y los genéricos que forman cada doble;
- asignaturas: índice «asignatura → carreras donde se estudia», desde los planes comprobados.

Uso:
  python -m motor.grados.relaciones --fichas …/fichas.jsonl --genericos …/genericos.jsonl --salida ruta/
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from motor.grados.asignaturas import NUMERACION, clave_asignatura

MAX_PARECIDAS = 8
MIN_PUNTOS = 2.0
MIN_ASIGNATURAS = 8  # para comparar asignaturas, cada genérico necesita al menos estas claves


def _leer(ruta: Path) -> list[dict]:
    return [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines() if x.strip()]


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def asignaturas_por_generico(fichas: list[dict]) -> dict[str, set[str]]:
    """Genérico → claves de sus asignaturas básicas y obligatorias en planes comprobados."""
    salida: dict[str, set[str]] = defaultdict(set)
    for f in fichas:
        g, p = f.get("generico"), f.get("plan")
        if g and p and p.get("comprobado"):
            for a in p.get("asignaturas") or []:
                if a.get("tipo") in ("basica", "obligatoria") and a.get("nombre"):
                    salida[g["id"]].add(clave_asignatura(a["nombre"]))
    return salida


def rasgos_por_generico(genericos: list[dict], catalogo: list[dict]) -> dict[str, dict]:
    """Genérico → código ISCED-F (4 cifras) y ámbito más frecuentes entre sus títulos (catálogo del SIIU)."""
    por_codigo = {t["codigo"]: t for t in catalogo}
    salida = {}
    for g in genericos:
        isced = Counter(por_codigo[c].get("isced_codigo") for c in g["titulos"] if c in por_codigo)
        ambito = Counter(por_codigo[c].get("ambito") for c in g["titulos"] if c in por_codigo)
        isced.pop(None, None)
        ambito.pop(None, None)
        salida[g["id"]] = {"isced": isced.most_common(1)[0][0] if isced else None,
                           "ambito": ambito.most_common(1)[0][0] if ambito else None}
    return salida


def parecidas(genericos: list[dict], asig: dict[str, set[str]], rasgos: dict[str, dict] | None = None) -> dict[str, list[dict]]:
    """Puntos por cercanía: mismo campo ISCED-F detallado (3) o estrecho (1,5), mismo ámbito (1,5), misma área del
    SIIU (2), misma rama (0,5), nombre parecido (hasta 2), dobles grados que los combinan (de 1 a 2 según cuántos) y
    asignaturas básicas y obligatorias en común (hasta 10)."""
    rasgos = rasgos or {}
    simples = [g for g in genericos if g["tipo"] == "grado" and g["pagina_propia"]]
    palabras = {g["id"]: set(g["clave"].split()) for g in simples}
    juntos: Counter = Counter()
    for d in genericos:
        if d["tipo"] == "doble":
            partes = sorted(d["clave"].split("+"))
            for i in range(len(partes)):
                for j in range(i + 1, len(partes)):
                    juntos[(partes[i], partes[j])] += len(d["titulos"])
    salida = {}
    for g in simples:
        rg = rasgos.get(g["id"], {})
        candidatos = []
        for h in simples:
            if h["id"] == g["id"]:
                continue
            rh = rasgos.get(h["id"], {})
            puntos, motivos = 0.0, []
            if rg.get("isced") and rg["isced"] == rh.get("isced"):
                puntos += 3
                motivos.append(f"mismo campo de estudio (ISCED {rg['isced']})")
            elif rg.get("isced") and rh.get("isced") and rg["isced"][:3] == rh["isced"][:3]:
                puntos += 1.5
                motivos.append(f"campo de estudio cercano (ISCED {rg['isced'][:3]})")
            if rg.get("ambito") and rg["ambito"] == rh.get("ambito"):
                puntos += 1.5
                motivos.append(f"mismo ámbito: {rg['ambito']}")
            if g.get("area") and g.get("area") == h.get("area"):
                puntos += 2
                motivos.append(f"misma área: {g['area']}")
            if g.get("rama") and g.get("rama") == h.get("rama"):
                puntos += 0.5
            jn = _jaccard(palabras[g["id"]], palabras[h["id"]])
            if jn:
                puntos += 2 * jn
                motivos.append("nombre parecido")
            n_dobles = juntos[tuple(sorted((g["clave"], h["clave"])))]
            if n_dobles:
                puntos += min(2.0, 1 + n_dobles / 20)
                motivos.append(f"se estudian juntas en {n_dobles} doble{'s' if n_dobles > 1 else ''} grado{'s' if n_dobles > 1 else ''}")
            a, b = asig.get(g["id"], set()), asig.get(h["id"], set())
            if len(a) >= MIN_ASIGNATURAS and len(b) >= MIN_ASIGNATURAS:
                comunes = a & b
                if comunes:
                    puntos += 10 * _jaccard(a, b)
                    motivos.append(f"{len(comunes)} asignaturas básicas u obligatorias en común")
            if puntos >= MIN_PUNTOS:
                candidatos.append({"generico": h["id"], "nombre": h["nombre"], "puntos": round(puntos, 2),
                                   "motivos": motivos, "titulos": len(h["titulos"])})
        candidatos.sort(key=lambda x: (-x["puntos"], -x["titulos"], x["nombre"]))
        salida[g["id"]] = candidatos[:MAX_PARECIDAS]
    return salida


def dobles(genericos: list[dict]) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    """(genérico simple → dobles con página que lo incluyen, doble → genéricos que lo forman)."""
    por_clave = {g["clave"]: g for g in genericos if g["tipo"] == "grado"}
    incluye: dict[str, list[dict]] = defaultdict(list)
    forman: dict[str, list[dict]] = {}
    for d in genericos:
        if d["tipo"] != "doble":
            continue
        partes = [por_clave[k] for k in d["clave"].split("+") if k in por_clave]
        forman[d["id"]] = [{"generico": p["id"], "nombre": p["nombre"], "pagina_propia": p["pagina_propia"]}
                           for p in partes]
        if d["pagina_propia"]:
            for p in partes:
                incluye[p["id"]].append({"generico": d["id"], "nombre": d["nombre"], "titulos": len(d["titulos"])})
    for k in incluye:
        incluye[k].sort(key=lambda x: -x["titulos"])
    return dict(incluye), forman


def indice_asignaturas(fichas: list[dict]) -> list[dict]:
    """Asignatura (clave normalizada) → carreras con planes comprobados donde se estudia, con su tipo y curso."""
    nombres: dict[str, Counter] = defaultdict(Counter)
    donde: dict[str, dict] = defaultdict(dict)
    for f in fichas:
        p = f.get("plan")
        if not (p and p.get("comprobado")):
            continue
        for a in p.get("asignaturas") or []:
            if not a.get("nombre"):
                continue
            k = clave_asignatura(a["nombre"])
            if not k:
                continue
            nombres[k][NUMERACION.sub("", a["nombre"].strip())] += 1
            donde[k].setdefault(f["codigo"], {"codigo": f["codigo"], "nombre": f["nombre"],
                                              "universidad": f["universidades"][0]["nombre"],
                                              "generico": (f.get("generico") or {}).get("id"),
                                              "tipo": a.get("tipo"), "curso": a.get("curso"),
                                              "creditos": a.get("creditos")})
    salida = []
    for k, filas in donde.items():
        genericos = Counter(x["generico"] for x in filas.values() if x["generico"])
        salida.append({"clave": k, "nombre": nombres[k].most_common(1)[0][0], "titulos": len(filas),
                       "genericos": [{"generico": g, "titulos": n} for g, n in genericos.most_common()],
                       "donde": sorted(filas.values(), key=lambda x: (x["generico"] or "", x["universidad"]))})
    salida.sort(key=lambda x: (-x["titulos"], x["clave"]))
    return salida


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--fichas", required=True)
    p.add_argument("--genericos", required=True)
    p.add_argument("--catalogo", help="catálogo del SIIU (ISCED y ámbito de cada título)")
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    fichas, genericos = _leer(Path(a.fichas)), _leer(Path(a.genericos))
    asig = asignaturas_por_generico(fichas)
    rasgos = rasgos_por_generico(genericos, _leer(Path(a.catalogo))) if a.catalogo else {}
    par = parecidas(genericos, asig, rasgos)
    incluye, forman = dobles(genericos)
    destino = Path(a.salida) / "datos" / "estudios" / "grados"
    destino.mkdir(parents=True, exist_ok=True)
    with (destino / "relaciones.jsonl").open("w", encoding="utf-8") as f:
        for g in genericos:
            if not g["pagina_propia"]:
                continue
            f.write(json.dumps({"generico": g["id"], "nombre": g["nombre"], "tipo": g["tipo"],
                                "parecidas": par.get(g["id"], []), "dobles_que_lo_incluyen": incluye.get(g["id"], []),
                                "lo_forman": forman.get(g["id"], [])}, ensure_ascii=False) + "\n")
    indice = indice_asignaturas(fichas)
    with (destino / "asignaturas_indice.jsonl").open("w", encoding="utf-8") as f:
        for x in indice:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    res = {"genericos_con_pagina": sum(1 for g in genericos if g["pagina_propia"]),
           "con_parecidas": sum(1 for v in par.values() if v),
           "parecidas_por_asignaturas": sum(1 for v in par.values() for x in v if any("asignaturas" in m for m in x["motivos"])),
           "simples_con_dobles": len(incluye), "genericos_con_asignaturas": len(asig),
           "asignaturas_distintas": len(indice), "asignaturas_en_2_o_mas_titulos": sum(1 for x in indice if x["titulos"] >= 2)}
    (destino / "relaciones_resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
