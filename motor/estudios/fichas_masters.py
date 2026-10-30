"""Ficha de cada máster a partir de los hechos extraídos de su página y sus subpáginas (docs/modelo-masters.md, §6).

Une, por máster, los hechos con cita comprobada de la página principal y de sus subpáginas (precio, plan de
estudios, acceso…), de una o varias tandas de extracción. Para cada campo elige el valor aceptado más reciente
de la página principal y, si no lo trae, el de una subpágina; si dos páginas dan valores distintos, lo anota.

Másters oficiales (clave: código RUCT): se comprueba que el nombre extraído de la página principal es el del RUCT
(si no, la página no se usa para ese máster) y se añaden como fuente oficial el tipo de título y la universidad
del catálogo del Ministerio. Másters no oficiales (clave: URL principal): se añade el centro de la clasificación.

Lo publicado lleva fuente (URL de la página), fecha de captura y huella; nunca la cita (texto ajeno).

Uso:
  python -m motor.estudios.fichas_masters --extraccion carpeta [--extraccion …] [--catalogo catalogo.json]
         [--clasificacion clasificacion.jsonl] --salida ruta/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

from motor.estudios.emparejar import palabras_nombre, palabras_texto
from motor.estudios.extraer import LOCALE_OTRO_PAIS, NUMERICOS, PRECIO_MAXIMO, PRECIOS, como_numero

CONFIRMADO, PROBABLE = 0.8, 0.5
ORDEN_ESTADO = {"confirmado": 0, "probable_oficial": 1, "probable_sin_confirmar": 2, "distinto": 3, "sin_nombre": 4,
                "no_es_ficha": 5, "sin_catalogo": 6}


def comprobar_nombre(oficial: str, extraido: str | None) -> tuple[str, float]:
    """confirmado | probable | distinto | sin_nombre, con la parte del nombre oficial que aparece."""
    if not extraido:
        return "sin_nombre", 0.0
    po, pe = palabras_nombre(oficial), palabras_texto(extraido)
    if not po:
        return "sin_nombre", 0.0
    cobertura = len(po & pe) / len(po)
    sobrante = len(pe - po) / max(len(pe), 1)
    if cobertura >= CONFIRMADO and sobrante <= 0.4:
        return "confirmado", round(cobertura, 3)
    if cobertura >= PROBABLE:
        return "probable", round(cobertura, 3)
    return "distinto", round(cobertura, 3)


def _jsonl(ruta: Path) -> list[dict]:
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()] if ruta.exists() else []


def leer_extracciones(carpetas: list[Path]) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    """(páginas por URL, hechos aceptados por URL), quedándose con la extracción más reciente de cada página."""
    paginas: dict[str, dict] = {}
    for c in carpetas:
        for f in sorted(c.rglob("paginas_extraidas.jsonl")):
            for p in _jsonl(f):
                if p["url"] not in paginas or p["extraido"] >= paginas[p["url"]]["extraido"]:
                    paginas[p["url"]] = p
    hechos: dict[str, list[dict]] = defaultdict(list)
    for c in carpetas:
        for f in sorted(c.rglob("hechos.jsonl")):
            for h in _jsonl(f):
                p = paginas.get(h["url"])
                if p and h.get("extraido") == p["extraido"] and h.get("estado") == "aceptado":
                    hechos[h["url"]].append(h)
    return paginas, hechos


def _valor(hs: list[dict], campo: str):
    for h in hs:
        if h["campo"] == campo:
            return h
    return None


def componer(paginas_master: list[dict], hechos: dict[str, list[dict]]) -> dict:
    """Campos de la ficha desde la principal y, si falta, las subpáginas; con su fuente y avisos de conflicto."""
    orden = sorted(paginas_master, key=lambda p: (p.get("pagina") == "subpagina", p["url"]))
    campos, distintos = {}, []
    for p in orden:
        for h in hechos.get(p["url"], []):
            if h["campo"] in NUMERICOS:
                n = como_numero(h["valor"])
                if n is None:  # hechos de antes de la comprobación de tipo («no indicado» como precio)
                    continue
                if h["campo"] in PRECIOS and n > PRECIO_MAXIMO:  # otra moneda (es-CO…) o mala lectura
                    continue
                h = {**h, "valor": n}
            v = {"valor": h["valor"], "url": h["url"], "captura_sha256": h["captura_sha256"],
                 "extraido": h["extraido"], "cita_sha256": h.get("cita_sha256"), "pagina": p.get("pagina", "principal")}
            if h["campo"] not in campos:
                campos[h["campo"]] = v
            elif campos[h["campo"]]["valor"] != h["valor"] and h["campo"] not in ("asignaturas", "nombre"):
                distintos.append(h["campo"])
    return {"campos": campos, "campos_con_valores_distintos": sorted(set(distintos))}


def rescatar_oficiales(paginas: dict[str, dict], hechos: dict[str, list[dict]], cat: dict[str, dict],
                       censo: dict[str, dict]) -> dict[str, tuple[str, float]]:
    """URL → (código RUCT, cobertura) de las páginas extraídas como no oficiales o títulos propios que son, por su
    nombre, la ficha de un máster oficial de las universidades de su proveedor (la unión por URL no las vio:
    otra dirección, otro idioma, otro centro). Solo con el nombre del RUCT confirmado y la página diciendo que
    es oficial."""
    por_univ: dict[str, list[dict]] = defaultdict(list)
    for t in cat.values():
        if t.get("situacion", "Activo") == "Activo":
            por_univ[t.get("universidad_codigo") or ""].append(t)
    nombres_univ = {}  # palabras del nombre corto de cada universidad del catálogo → código
    for t in cat.values():
        if t.get("universidad") and t.get("universidad_codigo"):
            nombres_univ[frozenset(palabras_texto(t["universidad"]))] = t["universidad_codigo"]

    def univ_de(texto: str) -> str | None:
        """«Universidad Rey Juan Carlos» → su código; entre varias que encajan, la de nombre más largo
        («Autònoma de Barcelona» antes que «Barcelona»)."""
        pal = palabras_texto(texto)
        encajan = [(len(k), c) for k, c in nombres_univ.items() if k and k <= pal]
        return max(encajan)[1] if encajan else None

    salida = {}
    for url, p in paginas.items():
        if p.get("grupo") == "oficial" or p.get("pagina") == "subpagina" or p.get("no_es_programa"):
            continue
        hs = {h["campo"]: h["valor"] for h in hechos.get(url, [])}
        nombre, tipo = str(hs.get("nombre") or ""), str(hs.get("tipo_titulo") or "").lower()
        if not nombre or not ("oficial" in tipo or "universitari" in nombre.lower()):
            continue
        univs = {r.get("universidad") for r in (censo.get(p.get("proveedor") or "") or {}).get("ruct", [])}
        if not univs and hs.get("universidad_que_expide"):
            # centro sin registro propio en el RUCT (adscrito con web propia): la universidad que dice la página
            u = univ_de(str(hs["universidad_que_expide"]))
            univs = {u} if u else set()
        mejor = None
        for u in univs:
            for t in por_univ.get(u or "", []):
                est, cob = comprobar_nombre(t["nombre_oficial"], nombre)
                if est == "confirmado" and (mejor is None or cob > mejor[1]):
                    mejor = (t["codigo_ruct"], cob)
        if mejor:
            salida[url] = mejor
    return salida


def ejecutar(extracciones: list[Path], salida: Path, catalogo: Path | None = None,
             clasificacion: Path | None = None, censo: Path | None = None) -> dict:
    paginas, hechos = leer_extracciones(extracciones)
    cat = {}
    if catalogo:
        texto = catalogo.read_text(encoding="utf-8").strip()
        filas = json.loads(texto) if texto.startswith("[") else [json.loads(l) for l in texto.splitlines() if l.strip()]
        cat = {t["codigo_ruct"]: t for t in filas}
    clas = {c["id"]: c for c in _jsonl(clasificacion)} if clasificacion else {}
    res, fichas = Counter(), []

    provs = {x["id"]: x for x in _jsonl(censo)} if censo else {}
    rescatadas = rescatar_oficiales(paginas, hechos, cat, provs) if cat and provs else {}
    res["paginas_rescatadas_como_oficiales"] = len(rescatadas)

    # oficiales: un máster por código RUCT, con su principal y sus subpáginas
    por_codigo: dict[str, list[dict]] = defaultdict(list)
    for p in paginas.values():
        if p.get("grupo") == "oficial":
            for c in p.get("codigos_ruct") or ([p["codigo_ruct"]] if p.get("codigo_ruct") else []):
                por_codigo[c].append(p)
    for u, (c, _) in rescatadas.items():
        por_codigo.setdefault(c, [])
    hermanos: dict[str, list[dict]] = defaultdict(list)  # másters activos de cada universidad
    for x in cat.values():
        if x.get("situacion", "Activo") == "Activo":
            hermanos[x.get("universidad_codigo")].append(x)
    for codigo, ps in sorted(por_codigo.items()):
        t = cat.get(codigo, {})
        principales = [p for p in ps if p.get("pagina", "principal") == "principal"]
        # cada página principal candidata (primera unión, segunda vuelta…) se juzga por separado; gana la mejor
        juicios = []
        for p in principales:
            nom = next((h["valor"] for h in hechos.get(p["url"], []) if h["campo"] == "nombre"), None)
            if p.get("no_es_programa"):
                est, cb = "no_es_ficha", 0.0
            else:
                est, cb = comprobar_nombre(t.get("nombre_oficial", ""), nom) if t else ("sin_catalogo", 0.0)
            if est == "probable":
                # nombre parecido pero no igual (doble máster, programa ejecutivo…): solo vale si la página
                # dice que es un máster universitario oficial y ningún otro máster de la misma universidad se
                # parece tanto o más a ese nombre
                tipo = next((str(h["valor"]) for h in hechos.get(p["url"], []) if h["campo"] == "tipo_titulo"), "")
                rival = max((comprobar_nombre(o["nombre_oficial"], nom)[1] for o in hermanos.get(t.get("universidad_codigo"), [])
                             if o["codigo_ruct"] != codigo), default=0.0)
                est = "probable_oficial" if "oficial" in tipo.lower() and "doble" not in (nom or "").lower() \
                    and rival < cb else "probable_sin_confirmar"
            juicios.append((ORDEN_ESTADO.get(est, 9), -cb, p["url"], est, cb, nom))
        if juicios:
            _, _, url_buena, estado, cob, nombre_ext = min(juicios)
            ps = [p for p in ps if p["url"] == url_buena or p.get("principal") == url_buena
                  or (p.get("pagina") == "subpagina" and not p.get("principal"))]
        else:
            estado, cob, nombre_ext = "sin_pagina", 0.0, None
        rescate = sorted((u for u, (c, _) in rescatadas.items() if c == codigo), key=lambda u: -rescatadas[u][1])
        if estado not in ("confirmado", "probable_oficial") and rescate:
            # la página propia no era la ficha (o no había): vale la rescatada por el nombre
            ps = [paginas[rescate[0]]]
            nombre_ext = next((h["valor"] for h in hechos.get(rescate[0], []) if h["campo"] == "nombre"), None)
            estado, cob = "confirmado_por_nombre", rescatadas[rescate[0]][1]
        res["oficial_" + estado] += 1
        ficha = {"clave": f"ruct:{codigo}", "grupo": "oficial", "codigo_ruct": codigo,
                 "nombre_oficial": t.get("nombre_oficial"), "nombre_en_pagina": nombre_ext,
                 "comprobacion_nombre": estado, "cobertura_nombre": cob,
                 "paginas": sorted(p["url"] for p in ps)}
        if estado in ("confirmado", "probable_oficial", "confirmado_por_nombre"):
            ficha.update(componer(ps, hechos))
        else:
            ficha.update({"campos": {}, "campos_con_valores_distintos": []})
        if t:  # fuente oficial: el catálogo del Ministerio (SIIU/RUCT)
            fuente = {"fuente": "catalogo_siiu", "url": (t.get("fuente") or {}).get("url"),
                      "capturado": (t.get("fuente") or {}).get("capturado")}
            ficha["oficiales"] = {"tipo_titulo": {"valor": "máster universitario oficial", **fuente},
                                  "universidad_que_expide": {"valor": t.get("universidad"), **fuente},
                                  "rama": {"valor": t.get("rama"), **fuente},
                                  "titularidad": {"valor": t.get("universidad_tipo"), **fuente}}
        fichas.append(ficha)

    # no oficiales: una ficha por página principal
    programas, programas_master = set(), set()
    subs: dict[str, list[dict]] = defaultdict(list)
    for q in paginas.values():
        if q.get("principal"):
            subs[q["principal"]].append(q)
    for p in sorted(paginas.values(), key=lambda p: p["url"]):
        if p.get("grupo") == "oficial" or p.get("pagina") == "subpagina" or p["url"] in rescatadas:
            continue
        if p.get("no_es_programa"):
            res["no_oficial_no_es_ficha"] += 1
            continue
        if LOCALE_OTRO_PAIS.search(urlparse(p["url"]).path + "/"):
            res["no_oficial_version_otro_pais"] += 1  # es-CO, es-MX…: oferta y precios de otro país
            continue
        c = clas.get(p.get("proveedor") or "", {})
        ficha = {"clave": f"url:{p['url']}", "grupo": "no_oficial", "url": p["url"], "proveedor": p.get("proveedor"),
                 "centro": c.get("nombre"), "tipo_centro": c.get("tipo_centro"), "dominio": c.get("dominio"),
                 **componer([p] + subs.get(p["url"], []), hechos)}
        tipo = (ficha["campos"].get("tipo_titulo") or {}).get("valor") or ""
        nombre = str((ficha["campos"].get("nombre") or {}).get("valor") or "")
        # programa (docs/modelo-masters.md §6): proveedor + nombre normalizado + tipo; la misma oferta en varias
        # URL (ciudades, idiomas, campañas) es un solo programa
        ficha["programa"] = "prog-" + hashlib.sha256(
            f"{p.get('proveedor')}|{' '.join(sorted(palabras_texto(nombre)))}|{tipo.lower()}".encode()).hexdigest()[:12] \
            if nombre else None
        ficha["es_master"] = bool(re.search(r"(?i)m[aá]ster|\bmba\b", f"{tipo} {nombre}")) or \
            (not nombre and bool(re.search(r"(?i)m[aá]ster|\bmba\b", p["url"])))
        res["no_oficial_ficha"] += 1
        programas.add(ficha["programa"]) if ficha["programa"] else None
        if ficha["es_master"] and ficha["programa"]:
            programas_master.add(ficha["programa"])
        res["no_oficial_master" if ficha["es_master"] else "no_oficial_otro_titulo"] += 1
        fichas.append(ficha)

    completitud = Counter()
    for f in fichas:
        for campo in f.get("campos", {}):
            completitud[(f["grupo"], campo)] += 1
    destino = salida / "datos" / "estudios" / "masters"
    destino.mkdir(parents=True, exist_ok=True)
    with (destino / "fichas.jsonl").open("w", encoding="utf-8") as fo:
        for f in fichas:
            fo.write(json.dumps(f, ensure_ascii=False) + "\n")
    res["no_oficial_programas"] = len(programas)
    res["no_oficial_programas_master"] = len(programas_master)
    resumen = {**res, "fichas": len(fichas),
               "campos_por_grupo": {g: {c: n for (g2, c), n in sorted(completitud.items()) if g2 == g}
                                    for g in ("oficial", "no_oficial")}}
    (destino / "fichas_resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    return resumen


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--extraccion", action="append", required=True)
    p.add_argument("--catalogo")
    p.add_argument("--clasificacion")
    p.add_argument("--censo", help="proveedores.jsonl: une a sus másters oficiales las páginas propias con su nombre")
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    print(json.dumps(ejecutar([Path(x) for x in a.extraccion], Path(a.salida), Path(a.catalogo) if a.catalogo else None,
                              Path(a.clasificacion) if a.clasificacion else None, Path(a.censo) if a.censo else None),
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
