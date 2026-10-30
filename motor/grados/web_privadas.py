"""Páginas de grado de las universidades privadas: dónde está cada grado en su web y qué enseña sin registrarse.

QEDU no da el precio de las privadas («N/D») y casi nunca su nota de corte, así que su precio y su información
salen de la web de cada universidad. Para cada una de las 45 privadas con grado activo:
  1. robots.txt de cada servidor y sitemaps (piezas de motor/estudios/rastreador.py, sin modificarlas);
  2. URL que parecen de grado o doble grado (no másteres, posgrados, noticias ni blog);
  3. cada grado del catálogo se une con la URL cuyo camino contiene todas las palabras de su nombre;
  4. de cada página unida se mide lo que enseña sin dar datos (precio en datos estructurados, importes en
     euros con su tipo: por crédito, por curso, total, mensual, reserva; formulario que pide correo o teléfono;
     PDF de tarifas o precios enlazados).

En la rama pública no se guardan textos de las páginas: solo URL, medidas, importes y la huella del fragmento del
que sale cada importe. Los originales enteros van al almacén privado (MOTOR_ORIGINALES=s3).

Uso:
  python -m motor.grados.web_privadas --catalogo …/catalogo.jsonl --centros carpeta/centros --salida ruta/
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_mod
import json
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote, urlparse

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.estudios.rastreador import Dominio, _xml, medir_pagina, texto_de, urls_de_sitemap
from motor.grados.catalogo import clave, clave_union
from motor.grados.generico import nombre_base

GRADO_URL = re.compile(r"\bgrados?\b|\bgraus?\b|\bcarreras?\b|\bdegrees?\b|\bbachelors?\b|undergraduate|titulaciones|"
                       r"estudios-universitarios|\bdobles?-", re.I)
NO_GRADO = re.compile(r"m[aá]ster|masters?\b|postgrado|posgrado|postgrau|doctorad|/blog|noticia|news|actualidad|evento|"
                      r"agenda|/tag/|/category/|/autor|/author|/wp-content/|\.pdf$|\.jpe?g$|\.png$|curso-de-|cursos/|"
                      r"formacion-permanente|experto|especialista|executive|mba|lanza|nuevo-grado|trabajo-fin|tfg|"
                      r"salidas|que-estudiar|requisitos|becas?[-/]|preguntas|faq|opiniones|testimonio|entrevista|"
                      r"jornada|webinar|open-day|puertas-abiertas|premio|convenio|acuerdo|calendario|horario|"
                      r"profesor|docente|investigaci|departamento|/prensa|comunicado|sala-de-prensa|notici|formacion-profesional|"
                      r"grado-superior|grado-medio|ciclos?-formativ|prestec|prestamo|financiaci|extinguir|alumni", re.I)
# Páginas con los precios de todos los grados (no las de un máster, un curso o una noticia)
PRECIO_URL = re.compile(r"precios?\b|tarifas?\b|\btasas\b|honorarios|fees\b|tuition|preus|matricula-y-precios|"
                        r"financiacion-y-precios|precios-y-becas|coste", re.I)
NO_PRECIO = re.compile(r"m[aá]ster|postgrado|posgrado|doctorad|noticia|/blog|curso-de|cursos/|idioma|residencia|"
                       r"colegio-mayor|alojamiento|deporte|parking|biblioteca|/en/|/ca/|/eu/", re.I)
# Palabras que acompañan al nombre en la ruta de una ficha de grado sin cambiar de qué grado se trata
MARCADORES = {"grado", "grados", "grau", "graus", "doble", "dobles", "oficial", "oficiales", "estudios", "estudis",
              "universitario", "universitarios", "bachelor", "degree", "online", "distancia", "presencial",
              "semipresencial", "titulacion", "titulaciones", "carrera", "carreras", "in", "of", "and", "the", "en",
              "es", "html", "htm", "php", "aspx", "presentacion", "informacion", "general"}
# Más palabras ajenas al nombre en el último tramo de la ruta: es una noticia o una página de otra cosa
MAX_SOBRA_TRAMO = 3
# Sedes y ciudades: una URL de otra sede (universidades con un sitemap para varias) no es de esta universidad
SEDES = {"madrid", "valencia", "canaria", "canarias", "andalucia", "sevilla", "malaga", "barcelona", "alicante",
         "castellon", "elche", "murcia", "bilbao", "donostia", "vitoria", "zaragoza", "salamanca", "valladolid",
         "palma", "tenerife", "granada", "cordoba", "almeria", "marbella", "santander", "oviedo", "leon"}
# Provincias (dos primeras cifras del código de centro del SIIU) de cada sede: una página de grado cuya dirección
# nombra una sede de otra provincia que las de los centros del grado es de otro centro (ESIC Zaragoza frente a Pozuelo)
SEDE_PROVINCIAS = {"madrid": {"28"}, "valencia": {"46"}, "canaria": {"35", "38"}, "canarias": {"35", "38"},
                   "andalucia": {"04", "11", "14", "18", "21", "23", "29", "41"}, "sevilla": {"41"},
                   "malaga": {"29"}, "marbella": {"29"}, "barcelona": {"08"}, "alicante": {"03"}, "elche": {"03"},
                   "castellon": {"12"}, "murcia": {"30"}, "bilbao": {"48"}, "donostia": {"20"}, "vitoria": {"01"},
                   "zaragoza": {"50"}, "salamanca": {"37"}, "valladolid": {"47"}, "palma": {"07"}, "tenerife": {"38"},
                   "granada": {"18"}, "cordoba": {"14"}, "almeria": {"04"}, "santander": {"39"}, "oviedo": {"33"},
                   "leon": {"24"}}
# Importes verosímiles por tipo (€): fuera de rango se guardan como «fuera_de_rango» (sueldos, cifras de otra cosa)
RANGO = {"credito": (40, 450), "curso": (2500, 30000), "mensual": (200, 3500), "reserva": (100, 3500),
         "total": (8000, 160000)}
IDIOMA_EXTRANJERO = re.compile(r"/(en|ca|eu|gl|fr|de|it|pt|va)(/|$)|/english/", re.I)
# «9.990 €», «9.990,00 euros» y, en las páginas en inglés, «€9,990» o «€ 9,990.00»
IMPORTE = re.compile(r"(?:(?P<e>\d{1,3}(?:[.\s]\d{3})+|\d{3,6})(?:,(?P<d>\d{2}))?\s?(?:€|euros?\b|EUR\b))|"
                     r"(?:(?:€|EUR)\s?(?P<e2>\d{1,3}(?:[.,]\d{3})+|\d{3,6})(?:\.(?P<d2>\d{2}))?(?![\d.,]\d))", re.I)


def valor_importe(m: re.Match) -> float:
    entero = int(re.sub(r"[.,\s]", "", m.group("e") or m.group("e2")))
    dec = m.group("d") or m.group("d2")
    return entero + int(dec) / 100 if dec else entero
TIPO_IMPORTE = [
    # sueldos y salidas («un sueldo medio de 28.000 € al año»): no son precios; sin rango, nunca verosímiles
    ("sueldo", re.compile(r"salari|sueldo|retribuci|cobra[nr]?\b|ganar|brutos?\b|n[óo]mina|empleabilidad", re.I)),
    ("credito", re.compile(r"cr[ée]dito|ects", re.I)),
    ("mensual", re.compile(r"mensual|al mes|/mes|cuotas?|plazos?", re.I)),
    ("reserva", re.compile(r"reserva|preinscripci|matr[íi]cula de plaza", re.I)),
    ("total", re.compile(r"total|grado completo|todo el grado|programa completo", re.I)),
    ("curso", re.compile(r"curso|\banual\b|por año|al año|/año|año acad", re.I)),  # «anuales»: sueldos
]
MAX_URLS = 80000
PAUSA = 1.0


def palabras(texto: str) -> set[str]:
    return set(clave_union(texto).split())


def palabras_url(url: str) -> set[str]:
    p = unquote(urlparse(url).path)
    return set(clave_union(re.sub(r"[/_\-.]+", " ", p)).split())


def sobra_tramo(url: str, objetivo: set[str]) -> int:
    """Palabras del último tramo de la ruta que no son del nombre ni marcadores («grado», «online»…)."""
    tramos = [t for t in unquote(urlparse(url).path).split("/") if t]
    if not tramos:
        return 0
    return len(set(clave_union(re.sub(r"[_\-.]+", " ", tramos[-1])).split()) - objetivo - MARCADORES)


def objetivos_nombre(g: dict) -> list[set[str]]:
    """Conjuntos de palabras que identifican el grado en una URL: el nombre en castellano y, si el título es
    bilingüe («Diseño de Moda / Bachelor in Fashion Design»), también el nombre en el otro idioma."""
    if g["clase"] == "doble":
        if g.get("componentes"):
            return [set().union(*(palabras(nombre_base(c["nombre"])) for c in g["componentes"]))]
        return [palabras(g["nombre"])]
    salida = [palabras(nombre_base(g["nombre"]))]
    for parte in g["nombre"].split(" / ")[1:]:
        otro = palabras(parte) - MARCADORES
        if otro:
            salida.append(otro)
    return [o for o in salida if o]


# abreviaturas que las universidades usan en el título de la página
ABREVIATURAS = {"cafyd": "ciencias actividad fisica deporte", "cafd": "ciencias actividad fisica deporte",
                "ade": "administracion direccion empresas", "ia": "inteligencia artificial",
                "rrii": "relaciones internacionales"}
GENERICAS_NOMBRE = {"grado", "ciencia", "estudio", "bachelor", "degree", "doble", "en", "de", "y"}
NOMBRA_PROGRAMA = re.compile(r"\bgrados?\b|\bdobles?\b|\bdegrees?\b|\bbachelors?\b|\bgraus?\b|titulaci", re.I)
OTRO_ESTUDIO = re.compile(r"\bfp\b|formaci[oó]n profesional|reconocimientos?\b|\bdouble\b|\bdobles?\b", re.I)


def titulo_contradice(g: dict, titulo: str | None) -> bool:
    """El título de la página dice que es de otro estudio: un doble grado o una FP para un grado simple, o un
    título que nombra un programa sin ninguna palabra propia del grado (en un doble, de alguno de sus dos grados).
    Un título genérico («Admisión», «Presentación») no contradice nada: entonces vale la dirección."""
    if not titulo:
        return False
    t = html_mod.unescape(html_mod.unescape(titulo))
    pal = palabras(t)
    for abr, exp in ABREVIATURAS.items():
        if abr in set(re.findall(r"[a-z]+", t.lower())):
            pal |= palabras(exp)
    if g["clase"] != "doble" and OTRO_ESTUDIO.search(t):
        return True
    if g["clase"] == "doble" and re.search(r"\bfp\b|formaci[oó]n profesional|reconocimientos?\b", t, re.I):
        return True
    if not NOMBRA_PROGRAMA.search(t):
        return False
    if g["clase"] == "doble" and g.get("componentes"):
        partes = [palabras(nombre_base(c["nombre"])) - GENERICAS_NOMBRE for c in g["componentes"]]
    else:
        partes = [set().union(*objetivos_nombre(g)) - GENERICAS_NOMBRE] if objetivos_nombre(g) else []
    return any(p and not (p & pal) for p in partes)


def sede_ajena(t: dict, url: str | None) -> str | None:
    """La sede que nombra la dirección de una página si no es la de ningún centro activo del grado (por provincia o
    municipio) ni sale en el nombre de su universidad: esa página es de otro centro. None si no nombra ninguna o
    si es suya."""
    if not url:
        return None
    imp = [i for i in t.get("imparticiones") or [] if i.get("situacion", "Activo") == "Activo"]
    provincias = {str(i["unidad_codigo"])[:2] for i in imp if i.get("unidad_codigo")}
    municipios = {w for i in imp for w in clave(i.get("municipio") or "").split()}
    universidad = {w for u in t.get("universidades") or [] for w in clave(u.get("nombre") or "").split()}
    for w in sorted(palabras_url(url) & SEDES):
        if w in municipios or w in universidad or provincias & SEDE_PROVINCIAS.get(w, set()):
            continue
        return w
    return None


def es_url_grado(url: str) -> bool:
    ruta = unquote(urlparse(url).path)
    return bool(GRADO_URL.search(ruta)) and not NO_GRADO.search(ruta)


def unir(grados: list[dict], urls: list[str], propias: set[str] | None = None) -> dict[str, dict]:
    """código → {url, alternativas}: la URL de grado cuyo camino contiene todas las palabras del nombre.

    Entre varias, la que no está en otro idioma y tiene el camino más corto. Los dobles grados exigen además «doble»
    en la URL; los simples, no tenerlo. Se descarta la URL cuyo último tramo trae más de MAX_SOBRA_TRAMO palabras
    ajenas al nombre (noticias del tipo «alumnos-del-grado-en-x-visitan-…»)."""
    ajenas = SEDES - (propias or set())
    candidatas = [(u, pu) for u in urls if es_url_grado(u) for pu in [palabras_url(u)] if not (pu & ajenas)]
    salida = {}
    for g in grados:
        objetivos = objetivos_nombre(g)
        if not objetivos:
            continue
        buenas = []
        for u, pu in candidatas:
            if g.get("imparticiones") and sede_ajena(g, u):
                continue  # página de otro centro de la misma universidad
            doble = "doble" in pu or "dobles" in pu
            if g["clase"] == "doble" and not doble or g["clase"] != "doble" and doble:
                continue
            for objetivo in objetivos:
                if objetivo <= pu and sobra_tramo(u, objetivo) <= MAX_SOBRA_TRAMO:
                    sobra = len(pu - objetivo)
                    buenas.append((bool(IDIOMA_EXTRANJERO.search(urlparse(u).path)), sobra, len(u), u))
                    break
        if buenas:
            buenas.sort()
            salida[g["codigo"]] = {"url": buenas[0][3], "alternativas": [b[3] for b in buenas[1:4]]}
    return salida


def tipo_cercano(antes: str, despues: str) -> str | None:
    """El tipo cuya palabra está más cerca del importe: primero lo que va justo antes, luego lo que va después."""
    previos = [(max(m.end() for m in p.finditer(antes)), t) for t, p in TIPO_IMPORTE if p.search(antes)]
    if previos:
        return max(previos)[1]
    siguientes = [(p.search(despues).start(), t) for t, p in TIPO_IMPORTE if p.search(despues)]
    return min(siguientes)[1] if siguientes else None


def importes(html: str) -> list[dict]:
    """Importes en euros del texto visible con su tipo (por el contexto cercano) y la huella del contexto."""
    texto = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", html)
    visible = " ".join(re.sub(r"<[^>]+>", " ", texto).split())
    salida = []
    hallados = list(IMPORTE.finditer(visible))
    for n, m in enumerate(hallados):
        valor = valor_importe(m)
        # contexto: lo que hay entre el importe anterior y el siguiente (como mucho 90 caracteres antes y 40 después)
        inicio = max(hallados[n - 1].end() if n else 0, m.start() - 90)
        fin = min(hallados[n + 1].start() if n + 1 < len(hallados) else len(visible), m.end() + 40)
        antes, despues = visible[inicio:m.start()], visible[m.end():fin]
        tipo = tipo_cercano(antes, despues)
        contexto = visible[inicio:fin]
        rango = RANGO.get(tipo)
        verosimil = bool(rango and rango[0] <= valor <= rango[1])
        salida.append({"valor": valor, "tipo": tipo, "verosimil": verosimil,
                       "contexto_sha256": hashlib.sha256(contexto.encode()).hexdigest()[:16]})
    return salida[:40]


LISTADO = re.compile(r"grados?|graus?|estudios|estudis|titulaciones|titulacions|carreras|oferta|degrees?|bachelor|"
                     r"undergraduate|estudia", re.I)


def desde_portada(d: Dominio, max_listados: int = 10) -> list[str]:
    """Enlaces de la portada y de sus páginas de listado de estudios (para webs sin sitemap útil)."""
    from motor.estudios.rastreador import enlaces

    vistos, salida = set(), []
    r = d.get(d.base + "/")
    if r is None or r.status_code != 200:
        return salida
    cola = []
    for u, t in enlaces(texto_de(r), r.url):
        if d.propio(u) and u not in vistos:
            vistos.add(u)
            salida.append(u)
            if LISTADO.search(urlparse(u).path + " " + (t or "")) and not NO_GRADO.search(urlparse(u).path):
                cola.append(u)
    for u in cola[:max_listados]:
        r = d.get(u)
        if r is None or r.status_code != 200 or "html" not in (r.headers.get("content-type") or ""):
            continue
        for v, _ in enlaces(texto_de(r), r.url):
            if d.propio(v) and v not in vistos:
                vistos.add(v)
                salida.append(v)
    return salida


def recorrer(universidad: dict, grados: list[dict], archivo: Archivo | None, max_paginas: int) -> dict:
    d = Dominio(universidad["web"], archivo, pausa=PAUSA, max_peticiones=max_paginas + 60)
    res: dict = {"universidad": universidad["nombre"], "codigo": universidad["codigo"], "web": universidad["web"],
                 **({"centro": universidad["centro"], "centro_adscrito": universidad.get("centro_adscrito")}
                    if universidad.get("centro") else {}),
                 "grados_catalogo": len(grados)}
    sitemaps, responde = d.resolver_base()
    res["base"] = d.base
    if not responde:
        res["error"] = "sin_respuesta"
        return res
    if not d.robots_ok_para(d.base + "/"):
        res["veto_robots"] = True
    cola = list(dict.fromkeys(sitemaps or [d.base + "/sitemap.xml", d.base + "/sitemap_index.xml"]))
    vistos, urls, leidos = set(), [], 0
    while cola and len(urls) < MAX_URLS and d.peticiones < 50:
        sm = cola.pop(0)
        if sm in vistos:
            continue
        vistos.add(sm)
        r = d.get(sm, guardar=False)
        if r is None or r.status_code != 200:
            continue
        raiz = _xml(r.content)
        if raiz is None:
            continue
        leidos += 1
        hijos, paginas = urls_de_sitemap(raiz)
        # primero los sitemaps que suenan a estudios o páginas, luego el resto
        hijos = sorted((h for h in hijos if h not in vistos), key=lambda h: (not re.search(r"grado|estudio|titulac|page|pagina|programa", h, re.I), h))
        cola = list(dict.fromkeys(hijos + cola))
        urls.extend(u for u in paginas if d.propio(u))
    res["sitemaps_leidos"] = leidos
    if sum(1 for u in urls if es_url_grado(u)) < 3:  # sin sitemap útil: portada y páginas de listado de grados
        urls += desde_portada(d)
        res["via"] = "portada"
    res["urls"] = len(urls)
    res["urls_grado"] = sum(1 for u in urls if es_url_grado(u))
    # páginas de precios de toda la universidad («/precios», «/tasas-y-becas»): las lee tarifas_grado.py
    res["urls_precio"] = [u for u in dict.fromkeys(urls) if PRECIO_URL.search(unquote(urlparse(u).path))
                          and not NO_PRECIO.search(unquote(urlparse(u).path))][:20]
    propias = set(clave(universidad["nombre"]).split()) | {w for g in grados for i in g["imparticiones"]
                                                         for w in clave(i.get("municipio") or "").split()}
    union = unir(grados, urls, propias)
    res["grados_con_url"] = len(union)
    # para revisar por qué no se unen: URL de grado que no son de ningún grado del catálogo (solo direcciones)
    unidas = {u["url"] for u in union.values()} | {a for u in union.values() for a in u["alternativas"]}
    res["muestra_urls_grado_sin_unir"] = [u for u in dict.fromkeys(urls) if es_url_grado(u) and u not in unidas][:40]
    fichas, pdfs = {}, Counter()
    for codigo, u in list(union.items())[:max_paginas]:
        r = d.get(u["url"])
        if r is None or r.status_code != 200 or "html" not in (r.headers.get("content-type") or ""):
            fichas[codigo] = {**u, "estado": r.status_code if r is not None else None}
            continue
        html = texto_de(r)
        m = medir_pagina(html, u["url"])
        imp = importes(html)
        for p in m.get("pdf_precio") or []:
            pdfs[p] += 1
        fichas[codigo] = {**u, "estado": 200, "precio_jsonld": m.get("precio_jsonld"),
                          "importes": imp, "formulario_pide_correo": m.get("formulario_pide_correo"),
                          "formulario_pide_telefono": m.get("formulario_pide_telefono"),
                          "temas": m.get("temas"), "pdf_precio": m.get("pdf_precio"), "titulo": m.get("titulo"),
                          "caracteres_visibles": m.get("caracteres_visibles")}
    res["fichas"] = fichas
    res["pdf_precio"] = [p for p, _ in pdfs.most_common(20)]
    res["peticiones"] = d.peticiones
    res["estados_http"] = dict(d.estados)
    return res


def resumen(resultados: list[dict]) -> dict:
    fichas = [f for r in resultados for f in (r.get("fichas") or {}).values()]
    leidas = [f for f in fichas if f.get("estado") == 200]
    con_importe = [f for f in leidas if f.get("importes")]
    return {
        "universidades": len(resultados),
        "sin_respuesta": sum(1 for r in resultados if r.get("error")),
        "veto_robots": sum(1 for r in resultados if r.get("veto_robots")),
        "grados_catalogo": sum(r.get("grados_catalogo", 0) for r in resultados),
        "grados_con_url": sum(r.get("grados_con_url", 0) for r in resultados),
        "paginas_leidas": len(leidas),
        "con_precio_jsonld": sum(1 for f in leidas if f.get("precio_jsonld")),
        "con_algun_importe": len(con_importe),
        "con_importe_verosimil": sum(1 for f in leidas if any(i.get("verosimil") for i in f.get("importes") or [])),
        "con_precio_curso_o_credito_verosimil": sum(1 for f in leidas if any(
            i.get("verosimil") and i["tipo"] in ("curso", "credito", "total") for i in f.get("importes") or [])),
        "via_portada": sum(1 for r in resultados if r.get("via") == "portada"),
        "con_importe_por_tipo": dict(Counter(i["tipo"] for f in con_importe for i in f["importes"])),
        "formulario_pide_correo": sum(1 for f in leidas if f.get("formulario_pide_correo")),
        "pide_correo_y_sin_importe": sum(1 for f in leidas if f.get("formulario_pide_correo") and not f.get("importes")),
        "universidades_con_pdf_precio": sum(1 for r in resultados if r.get("pdf_precio")),
    }


def objetivos(catalogo: list[dict], centros: Path) -> list[tuple[dict, list[dict]]]:
    fichas_u = {}
    for f in sorted(centros.rglob("*.json")):  # puede haber varias ejecuciones del censo: gana la última
        if re.fullmatch(r"\d{3}\.json", f.name):
            d = json.loads(f.read_text(encoding="utf-8"))
            fichas_u[d.get("codigo")] = d
    por_u: dict[str, list[dict]] = defaultdict(list)
    nombres = {}
    for t in catalogo:
        if t["situacion"] != "Activo" or t["clase"] not in ("grado", "doble"):
            continue
        for u in t["universidades"]:
            if u["tipo"] == "Privada" and u.get("codigo"):
                por_u[u["codigo"]].append(t)
                nombres[u["codigo"]] = u["nombre"]
    salida = []
    for cod, gs in sorted(por_u.items(), key=lambda x: -len(x[1])):
        web = (fichas_u.get(cod) or {}).get("web") or ""
        if not re.match(r"https?://[^/]+\.[a-z]{2,}", web):
            continue  # sin web o con una web mal escrita en el registro: no se adivina
        salida.append(({"codigo": cod, "nombre": nombres[cod], "web": web}, gs))
    return salida


def _host(web: str) -> str:
    return urlparse(web if web.startswith("http") else "https://" + web).netloc.lower().removeprefix("www.")


def objetivos_centros(catalogo: list[dict], centros: Path) -> list[tuple[dict, list[dict]]]:
    """Webs propias de centros, con los grados que se imparten en cada uno: los centros de las privadas cuya web no
    es la de su universidad (Ramón Llull: Esade, IQS, La Salle, Blanquerna…) y los centros adscritos de las
    públicas, que fijan su propio precio. Cada objetivo se llama «{universidad}{centro}» para no pisar el de la
    universidad, y lleva la marca de adscrito si lo es."""
    fichas_u = {}
    for f in sorted(centros.rglob("*.json")):
        if re.fullmatch(r"\d{3}\.json", f.name):
            d = json.loads(f.read_text(encoding="utf-8"))
            fichas_u[d.get("codigo")] = d
    por_centro: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for t in catalogo:
        if t["situacion"] != "Activo" or t["clase"] not in ("grado", "doble"):
            continue
        for u in t["universidades"]:
            for i in t["imparticiones"]:
                if i.get("situacion") == "Activo" and i.get("unidad_codigo") and i.get("universidad") == u["nombre"]:
                    por_centro[(u.get("codigo") or "", i["unidad_codigo"])].append(t)
    salida = []
    for (cu, cc), gs in sorted(por_centro.items()):
        u = fichas_u.get(cu) or {}
        centro = next((c for c in u.get("centros") or [] if c.get("codigo") == cc), None)
        web = (centro or {}).get("web") or ""
        if not re.match(r"https?://[^/]+\.[a-z]{2,}", web):
            continue
        adscrito = (centro.get("vinculacion") or "").lower().startswith("adscrit")
        privada = (u.get("tipo") or "").lower().startswith("priv") or any(
            x["universidad_tipo"] == "Privada" for x in gs)
        propia = _host(web) != _host(u.get("web") or "")  # otro host (iqs.url.edu sí; url.edu/centro no)
        if (privada and propia) or (not privada and adscrito):
            nombre = f"{u.get('nombre') or cu} · {(centro.get('nombre') or cc)[:60]}"
            salida.append(({"codigo": f"{cu}{cc}", "nombre": nombre, "web": web, "centro": cc,
                            "centro_adscrito": adscrito}, list({g["codigo"]: g for g in gs}.values())))
    # un mismo dominio para varios centros (Esade: Empresa y Derecho): un solo rastreo con todos sus grados
    por_web: dict[str, tuple[dict, list[dict]]] = {}
    for obj, gs in salida:
        h = _host(obj["web"])
        if h in por_web:
            por_web[h][1].extend(g for g in gs if g not in por_web[h][1])
        else:
            por_web[h] = (obj, list(gs))
    return list(por_web.values())


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--catalogo", required=True)
    p.add_argument("--centros", required=True, help="carpeta con las fichas de universidad del RUCT ({código}.json)")
    p.add_argument("--desde", type=int, default=0)
    p.add_argument("--hasta", type=int)
    p.add_argument("--hilos", type=int, default=4)
    p.add_argument("--max-paginas", type=int, default=120, help="páginas de grado por universidad")
    p.add_argument("--max-minutos", type=float, default=50)
    p.add_argument("--por-centros", action="store_true",
                   help="webs propias de centros (de privadas y adscritos de públicas) en vez de la de la universidad")
    p.add_argument("--solo", help="códigos de universidad separados por comas (p. ej. 033,054)")
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    cat = [json.loads(x) for x in Path(a.catalogo).read_text(encoding="utf-8").splitlines() if x.strip()]
    trabajo = (objetivos_centros if a.por_centros else objetivos)(cat, Path(a.centros))
    if a.solo:
        solo = set(a.solo.split(","))
        trabajo = [x for x in trabajo if x[0]["codigo"][:3] in solo]
    trabajo = trabajo[a.desde:a.hasta]
    archivo = Archivo(Path(a.salida) / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    destino = Path(a.salida) / "datos" / "estudios" / "grados" / "web_privadas"
    destino.mkdir(parents=True, exist_ok=True)
    fin = time.time() + a.max_minutos * 60
    resultados = []

    def uno(par):
        if time.time() > fin:
            return {"universidad": par[0]["nombre"], "error": "tiempo_agotado"}
        try:
            return recorrer(par[0], par[1], archivo, a.max_paginas)
        except Exception as e:  # noqa: BLE001 - una web rara no para el resto
            return {"universidad": par[0]["nombre"], "error": f"{type(e).__name__}: {str(e)[:150]}"}

    with ThreadPoolExecutor(max_workers=a.hilos) as ex:
        for r in ex.map(uno, trabajo):
            resultados.append(r)
            (destino / f"{r.get('codigo', 'x')}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    res = resumen(resultados)
    (destino / f"resumen_{a.desde}_{a.hasta}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
