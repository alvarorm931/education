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
ORDEN_ESTADO = {"confirmado": 0, "probable_oficial": 1, "probable_sin_confirmar": 2, "otro_tipo": 3, "distinto": 3,
                "sin_nombre": 4, "no_es_ficha": 5, "sin_catalogo": 6}


# Palabras que dicen otro tipo de título: si están en el nombre de la página y no en el oficial, es otro programa
# («Experto Universitario en Big Data» no es el «Máster Universitario en Big Data»).
TIPO_DISTINTO = {"experto", "especialista", "especializacion", "curso", "cursos", "diploma", "diplomatura", "propio",
                 "permanente", "doble", "executive", "ejecutivo", "programa", "postgrado", "posgrado", "mba", "grado",
                 "certificado", "certificate", "titulo", "microcredencial"}


def es_tipo_oficial(tipo: str) -> bool:
    """«máster universitario oficial» sí; «título propio (no oficial)» o «formación permanente» no."""
    t = (tipo or "").lower()
    return "oficial" in t and not re.search(r"no[\s-]+oficial|propio|permanente|no universitari", t)


# Catalán, gallego y valenciano → raíz común con el castellano del RUCT («Investigació» / «Investigación»,
# «Ciutadania» / «Ciudadanía»): terminaciones habituales y raíz de 6 letras en las palabras largas.
TERMINACIONES = [("itzacio", "izacion"), ("acio", "acion"), ("ecio", "ecion"), ("icio", "icion"), ("ccio", "ccion"),
                 ("sio", "sion"), ("itat", "idad"), ("tat", "dad"), ("encia", "encia"), ("ncia", "ncia"),
                 ("cions", "ciones"), ("cion", "cion"), ("ions", "iones"), ("ais", "ales"), ("ns", "nes")]
# códigos de título que no cuentan como palabras («M2503», «3500004», «mu45»): con alguna cifra. Sin cifras son
# palabras de verdad («moda», «minas», «museos», «mundus»: «Gestión de la Moda» no es «Gestión de Museos»)
CODIGO = __import__("re").compile(r"^[a-z]?\d+[a-z0-9]*$|^m(?=[0-9a-z]*\d)[0-9a-z]{3,5}$")


def raiz(w: str) -> str:
    for a, b in TERMINACIONES:
        if w.endswith(a):
            w = w[: -len(a)] + b
            break
    return w[:6] if len(w) >= 6 else w


def raices(palabras: set[str]) -> set[str]:
    return {raiz(w) for w in palabras if not CODIGO.match(w)}


def ajuste(oficial: str, extraido: str | None) -> tuple[float, float]:
    """(parte del nombre oficial que está en el de la página, menos la parte de la página que sobra): para elegir
    entre dos másters que encajan («Derecho Penal» y «Derecho Penal Económico» ante «Derecho Penal Económico»)."""
    po, pe = raices(palabras_nombre(oficial)), raices(palabras_texto(extraido or ""))
    if not po or not pe:
        return (0.0, -1.0)
    return (round(len(po & pe) / len(po), 3), -round(len(pe - po) / len(pe), 3))


def comprobar_nombre(oficial: str, extraido: str | None) -> tuple[str, float]:
    """confirmado | probable | otro_tipo | distinto | sin_nombre, con la parte del nombre oficial que aparece.
    Se comparan raíces (vale el nombre en catalán, gallego o valenciano) y no cuentan los códigos («- M2503»)."""
    if not extraido:
        return "sin_nombre", 0.0
    po, pe = raices(palabras_nombre(oficial)), raices(palabras_texto(extraido))
    if not po:
        return "sin_nombre", 0.0
    if (palabras_texto(extraido) & TIPO_DISTINTO) - palabras_texto(oficial):
        return "otro_tipo", round(len(po & pe) / len(po), 3)
    cobertura = len(po & pe) / len(po)
    sobrante = len(pe - po) / max(len(pe), 1)
    if cobertura >= CONFIRMADO and sobrante <= 0.4:
        return "confirmado", round(cobertura, 3)
    if cobertura >= PROBABLE:
        return "probable", round(cobertura, 3)
    return "distinto", round(cobertura, 3)


def _jsonl(ruta: Path) -> list[dict]:
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").split("\n") if l.strip()] if ruta.exists() else []


def legible(p: dict) -> bool:
    """Extracción que sirve: respuesta legible y no cortada (las antiguas no lo anotaban: se dan por buenas)."""
    return p.get("json_legible", True) is not False and p.get("parada") != "max_tokens"


def leer_extracciones(carpetas: list[Path]) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    """(páginas por URL, hechos aceptados por URL), quedándose con la extracción más reciente de cada página."""
    paginas: dict[str, dict] = {}
    for c in carpetas:
        for f in sorted(c.rglob("paginas_extraidas.jsonl")):
            for p in _jsonl(f):
                previa = paginas.get(p["url"])
                if previa is None:
                    paginas[p["url"]] = p
                elif previa.get("grupo") == "oficial" and p.get("grupo") != "oficial":
                    continue  # la misma página pedida también como no oficial: manda su unión a un máster oficial
                else:
                    nueva_mejor = (p["extraido"] >= previa["extraido"] and legible(p)) or not legible(previa) \
                        or (p.get("grupo") == "oficial" and previa.get("grupo") != "oficial")
                    elegida = p if nueva_mejor else previa
                    if previa.get("grupo") == "oficial" and p.get("grupo") == "oficial":
                        # los códigos RUCT de las dos tandas, en cualquier orden de lectura
                        elegida = {**elegida, "codigos_ruct": sorted(set(previa.get("codigos_ruct") or [])
                                                                     | set(p.get("codigos_ruct") or []))}
                    paginas[p["url"]] = elegida
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
    campos, distintos, fuentes, indice = {}, [], [], {}
    for p in orden:
        for h in hechos.get(p["url"], []):
            if h["campo"] in NUMERICOS:
                n = como_numero(h["valor"])
                if n is None:  # hechos de antes de la comprobación de tipo («no indicado» como precio)
                    continue
                if h["campo"] in PRECIOS and n > PRECIO_MAXIMO:  # otra moneda (es-CO…) o mala lectura
                    continue
                h = {**h, "valor": n}
            if h["campo"] not in campos:
                # la fuente (URL, captura, fecha) va una vez por página en «fuentes»; cada campo apunta a la suya
                clave = (h["url"], h["captura_sha256"])
                if clave not in indice:
                    indice[clave] = len(fuentes)
                    fuentes.append({"url": h["url"], "captura_sha256": h["captura_sha256"], "extraido": h["extraido"],
                                    "pagina": p.get("pagina", "principal")})
                campos[h["campo"]] = {"valor": h["valor"], "fuente": indice[clave], "cita_sha256": h.get("cita_sha256")}
                if h.get("cita_nivel") not in (None, "literal"):  # sin tildes ni signos, o en trozos con «...»
                    campos[h["campo"]]["cita_nivel"] = h["cita_nivel"]
            elif campos[h["campo"]]["valor"] != h["valor"] and h["campo"] not in ("asignaturas", "nombre"):
                distintos.append(h["campo"])
    return {"campos": campos, "fuentes": fuentes, "campos_con_valores_distintos": sorted(set(distintos))}


# «Máster», «Màster», «Masters», «MBA»; no «Scrum Master», «Mastering», «MasterClass», «Masterchef», «Master Plan»
RE_ES_MASTER = __import__("re").compile(r"(?i)(?<!scrum )(?<!scrum-)\bm[aàá]ster(?:es|s)?\b(?!\s*(?:class|chef|plan|card)\b)|\bmba\b")
# noticias, agendas y planes antiguos: no son la ficha vigente del máster aunque lleven su nombre
URL_NO_VIGENTE = __import__("re").compile(r"(?i)/20\d\d/\d{1,2}/\d{1,2}/|/(noticias?|news|actualidad|agenda|eventos?|"
                                           r"blog|prensa|plansanteriors|planes?-anteriores?|historico|extinguid)")


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
        if p.get("grupo") == "oficial" or p.get("pagina") == "subpagina" or p.get("no_es_programa") \
                or URL_NO_VIGENTE.search(url):
            continue
        hs = {h["campo"]: h["valor"] for h in hechos.get(url, [])}
        nombre, tipo = str(hs.get("nombre") or ""), str(hs.get("tipo_titulo") or "").lower()
        if not nombre or not (es_tipo_oficial(tipo) or (not tipo and "universitari" in nombre.lower())):
            continue
        univs = {r.get("universidad") for r in (censo.get(p.get("proveedor") or "") or {}).get("ruct", [])}
        if not univs and hs.get("universidad_que_expide"):
            # centro sin registro propio en el RUCT (adscrito con web propia): la universidad que dice la página
            u = univ_de(str(hs["universidad_que_expide"]))
            univs = {u} if u else set()
        candidatos = []
        for u in univs:
            for t in por_univ.get(u or "", []):
                est, cob = comprobar_nombre(t["nombre_oficial"], nombre)
                if est == "confirmado":
                    candidatos.append((ajuste(t["nombre_oficial"], nombre), t["codigo_ruct"], cob))
        candidatos.sort(reverse=True)
        # sin empate: si dos másters encajan igual de bien, no se adivina
        if candidatos and (len(candidatos) == 1 or candidatos[0][0] > candidatos[1][0]):
            salida[url] = (candidatos[0][1], candidatos[0][2])
    return salida


def con_altas(cat: dict[str, dict], altas: list[dict]) -> int:
    """Añade al catálogo (de febrero) los másters aprobados después que publica el BOE (boe_masters.py), con la
    universidad por su nombre («Universidad Cardenal Herrera-CEU» → su código del catálogo)."""
    univs: dict[frozenset, dict] = {}
    for t in cat.values():
        if t.get("universidad") and t.get("universidad_codigo"):
            univs[frozenset(palabras_texto(t["universidad"]))] = t
    n = 0
    for a in altas:
        if a.get("codigo_ruct") in cat or not a.get("nombre"):
            continue
        pal = palabras_texto(a.get("universidad") or "")
        encajan = [(len(k), t) for k, t in univs.items() if k and k <= pal]
        u = max(encajan, key=lambda x: x[0])[1] if encajan else {}
        cat[a["codigo_ruct"]] = {
            "codigo_ruct": a["codigo_ruct"], "nombre_oficial": f"{a['nombre']} por la {a.get('universidad') or ''}".strip(),
            "situacion": "Activo", "universidad": u.get("universidad"), "universidad_codigo": u.get("universidad_codigo"),
            "universidad_tipo": u.get("universidad_tipo"), "rama": None,
            "fuente": {"url": f"https://www.boe.es/diario_boe/txt.php?id={a.get('boe')}", "capturado": a.get("fecha")},
            "origen": "boe_alta"}
        n += 1
    return n


CONCEPTO_A_CAMPO = {"total": "precio_total", "credito": "precio_credito", "reserva": "reserva_matricula"}


def aplicar_tarifas(fichas: list[dict], unidos: list[dict]) -> int:
    """Precios de las tarifas en PDF (tarifas.py unir) en las fichas que no los tienen en su página. La página
    manda: un precio de tarifa nunca sustituye al de la ficha. Queda la fuente (el PDF) como documento público."""
    por_clave = {f["clave"]: f for f in fichas}
    n = 0
    for u in unidos:
        f, campo = por_clave.get(u.get("ficha")), CONCEPTO_A_CAMPO.get(u.get("concepto"))
        if not f or not campo or campo in f.setdefault("campos", {}) or u.get("importe") is None:
            continue
        if f["grupo"] == "oficial" and f.get("comprobacion_nombre") not in ("confirmado", "probable_oficial",
                                                                             "confirmado_por_nombre"):
            continue
        fuentes = f.setdefault("fuentes", [])
        fuentes.append({"url": u["url"], "captura_sha256": u.get("captura_sha256"), "extraido": u.get("extraido"),
                        "pagina": "documento", "curso": u.get("curso")})
        f["campos"][campo] = {"valor": u["importe"], "fuente": len(fuentes) - 1, "cita_sha256": u.get("cita_sha256")}
        n += 1
    return n


def ejecutar(extracciones: list[Path], salida: Path, catalogo: Path | None = None,
             clasificacion: Path | None = None, censo: Path | None = None, altas: Path | None = None,
             tarifas: Path | None = None) -> dict:
    paginas, hechos = leer_extracciones(extracciones)
    cat = {}
    if catalogo:
        texto = catalogo.read_text(encoding="utf-8").strip()
        filas = json.loads(texto) if texto.startswith("[") else [json.loads(l) for l in texto.split("\n") if l.strip()]
        cat = {t["codigo_ruct"]: t for t in filas}
    clas = {c["id"]: c for c in _jsonl(clasificacion)} if clasificacion else {}
    res, fichas = Counter(), []
    if altas:
        res["altas_boe_en_catalogo"] = con_altas(cat, _jsonl(altas))

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
            if est == "confirmado" and t:
                propio_ajuste = ajuste(t.get("nombre_oficial", ""), nom)
                if any(ajuste(o["nombre_oficial"], nom) > propio_ajuste
                       for o in hermanos.get(t.get("universidad_codigo"), []) if o["codigo_ruct"] != codigo):
                    est = "probable_sin_confirmar"  # la página es de otro máster de la misma universidad
            if est == "probable":
                # nombre parecido pero no igual (doble máster, programa ejecutivo…): solo vale si la página
                # dice que es un máster universitario oficial y ningún otro máster de la misma universidad se
                # parece tanto o más a ese nombre
                tipo = next((str(h["valor"]) for h in hechos.get(p["url"], []) if h["campo"] == "tipo_titulo"), "")
                rival = max((comprobar_nombre(o["nombre_oficial"], nom)[1] for o in hermanos.get(t.get("universidad_codigo"), [])
                             if o["codigo_ruct"] != codigo), default=0.0)
                est = "probable_oficial" if es_tipo_oficial(tipo) and "doble" not in (nom or "").lower() \
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
            ficha.update({"campos": {}, "fuentes": [], "campos_con_valores_distintos": []})
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
        ficha["es_master"] = bool(RE_ES_MASTER.search(f"{tipo} {nombre}")) or \
            (not nombre and bool(re.search(r"(?i)m[aá]ster|\bmba\b", p["url"])))
        res["no_oficial_ficha"] += 1
        programas.add(ficha["programa"]) if ficha["programa"] else None
        if ficha["es_master"] and ficha["programa"]:
            programas_master.add(ficha["programa"])
        res["no_oficial_master" if ficha["es_master"] else "no_oficial_otro_titulo"] += 1
        fichas.append(ficha)

    if tarifas:
        res["campos_desde_tarifas_pdf"] = aplicar_tarifas(fichas, _jsonl(tarifas))

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
    p.add_argument("--altas", help="boe_altas.jsonl: másters aprobados después del catálogo")
    p.add_argument("--tarifas", help="precios_unidos.jsonl de tarifas.py unir: precios de PDF para las fichas sin ellos")
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    print(json.dumps(ejecutar([Path(x) for x in a.extraccion], Path(a.salida), Path(a.catalogo) if a.catalogo else None,
                              Path(a.clasificacion) if a.clasificacion else None, Path(a.censo) if a.censo else None,
                              Path(a.altas) if a.altas else None, Path(a.tarifas) if a.tarifas else None),
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
