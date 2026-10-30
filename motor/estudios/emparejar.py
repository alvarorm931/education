"""Une cada máster oficial (código RUCT) con su página en la web de su universidad.

Con el nombre oficial del RUCT y las URL de programa del sitemap de la universidad (rastreador), se busca la
página cuyo último tramo de ruta mejor recoge las palabras significativas del nombre. Se acepta solo si la
coincidencia es alta y no hay empate; lo demás queda «sin página» o «dudoso» para revisión. Nada se une por
aproximación sin dejar constancia de la puntuación.

Uso:
  python -m motor.estudios.emparejar --catalogo catalogo.jsonl --censo proveedores.jsonl --rastreo carpeta \\
         [--commoncrawl carpeta_urls] --salida ruta/
"""

from __future__ import annotations

import argparse
import html
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlparse

from motor.estudios.censo import dominio_registrado

VACIAS = set("""de del la las el los en y e o u a por para con sin su sus al lo un una uno unos unas
master masters master's universitario universitaria universidad university oficial online presencial
semipresencial distancia mu mba degree in of and the by""".split())
SUBPAGINAS = re.compile(r"^(acceso|admision|admisiones|profesorado|claustro|plan-de-estudios|programa|temario|salidas|"
                        r"salidas-profesionales|precio|precios|becas|financiacion|metodologia|titulacion|investigacion|"
                        r"practicas|calidad|horarios?|calendario|requisitos|matricula|preinscripcion|faq|opiniones|"
                        r"presentacion|competencias|objetivos|informacion|contacto|documentacion|guias?-docentes?|"
                        r"asignaturas|estructura|plan-estudios|profesores|docentes|equipo-docente|noticias)$")
# Parámetros de la URL que no distinguen un programa de otro (paginación, idioma, seguimiento): se quitan. Los demás
# se conservan: en muchas webs el programa solo cambia en la consulta (uab.cat/…-1096480962610.html?param1=…).
QUERY_FUERA = re.compile(r"^(utm_\w*|lang|language|idioma|hl|locale|start|limitstart|page|pagina|pag|sort|order|"
                         r"orderby|ref|fbclid|gclid|mc_\w*|_ga|print|share|tab|s)$", re.I)  # «p» no: en WordPress es la entrada
# Tramos finales que son el contenedor de la ficha (/titulacion?id=…, /programa.php?cod=…): su consulta identifica
# el programa y no se quita al quitar el tramo
CONTENEDOR = re.compile(r"^(programa|titulacion|presentacion|informacion|estudio|estudios|ver|detalle|ficha)$")
EXTENSION = re.compile(r"\.(html?|php|aspx?|jsp)$", re.I)
# Subpáginas con lo que más falta en la ficha principal: precio, plan de estudios, acceso, horario…
SUBPAGINA_UTIL = re.compile(r"(precio|tasas|becas|financiacion|plan|asignaturas|estructura|programa|temario|acceso|"
                            r"admision|requisitos|preinscripcion|matricula|metodologia|evaluacion|horario|calendario|"
                            r"practicas|plazas)", re.I)
MAX_SUBPAGINAS = 6
MODALIDADES = re.compile(r"[-_](presencial|semipresencial|online|a-distancia|distancia|virtual|hibrido|blended)$")
UMBRAL = 0.75
MARGEN = 0.15


def _plano(s: str) -> str:
    s = unicodedata.normalize("NFKD", unquote(s).lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def palabras_nombre(nombre: str) -> set[str]:
    """Palabras significativas del nombre oficial, sin «Máster Universitario en» ni «por la Universidad…»."""
    n = re.split(r"\s+por\s+la\s+universi", _plano(nombre))[0]
    n = n.split(" / ")[0]  # nombre en inglés tras la barra
    return {w for w in re.findall(r"[a-z0-9]+", n) if w not in VACIAS and len(w) > 1}


def palabras_url(url: str) -> set[str]:
    partes = [EXTENSION.sub("", p) for p in urlparse(url).path.split("/") if p]
    tramo = " ".join(partes[-2:]) if partes else ""
    return {w for w in re.findall(r"[a-z0-9]+", _plano(tramo)) if w not in VACIAS and len(w) > 1}


def raiz_programa(url: str, quitar_subpaginas: bool = True) -> str:
    """Forma normalizada de la ficha para compararla: sin subpáginas habituales (/acceso, /profesorado,
    /asignaturas.html…), con «/» final y solo con los parámetros que distinguen un programa. Es una clave de
    comparación, no una dirección que exista: para pedir la página se usa `url_real`."""
    u = urlparse(url)
    partes = [p for p in u.path.split("/") if p]
    sub = False
    while quitar_subpaginas and len(partes) > 1 and SUBPAGINAS.match(EXTENSION.sub("", partes[-1].lower())):
        if u.query and CONTENEDOR.match(EXTENSION.sub("", partes[-1].lower())):
            break  # /estudios/titulacion?id=1 y ?id=2 son dos programas, no subpáginas de /estudios/
        partes.pop()
        sub = True
    q = "" if sub else "&".join(sorted(f"{k}={v}" for k, v in parse_qsl(u.query, keep_blank_values=True)
                                       if not QUERY_FUERA.match(k)))
    return f"{u.scheme}://{u.netloc}/" + "/".join(partes) + "/" + (f"?{q}" if q else "")


def url_real(raiz: str, originales: list[str]) -> tuple[str, bool]:
    """(URL, deducida). La de la ficha misma si se encontró; si solo se vieron sus subpáginas (/acceso,
    /plan-de-estudios…), la carpeta de la que cuelgan cuando es una carpeta (sin extensión ni consulta); si no,
    la subpágina más corta. Nunca una dirección con «/» añadida detrás de «.html»."""
    if not originales:
        return raiz, True
    exactas = [u for u in originales if raiz_programa(u, False) == raiz]
    if exactas:
        return min(exactas, key=lambda u: ("?" in u and "?" not in raiz, len(u), u)), False
    camino = urlparse(raiz).path.rstrip("/").rsplit("/", 1)[-1]
    if "?" not in raiz and not EXTENSION.search(camino):
        return raiz, True
    return min(originales, key=lambda u: (len(u), u)), False


def subpaginas_utiles(raiz: str, originales: list[str], principal: str | None) -> list[str]:
    """Subpáginas de la ficha con datos que la principal no suele traer (precio, plan, acceso, horario…)."""
    out = []
    for u in sorted(set(originales), key=lambda u: (len(u), u)):
        if u == principal or raiz_programa(u, False) == raiz:
            continue
        ultimo = EXTENSION.sub("", urlparse(u).path.rstrip("/").rsplit("/", 1)[-1])
        if SUBPAGINA_UTIL.search(ultimo) and not re.search(r"(?i)(cod)?asignatura=", u):
            out.append(u)
    return out[:MAX_SUBPAGINAS]


def sin_modalidad(url: str) -> str:
    return MODALIDADES.sub("", url.rstrip("/"))


IDIOMA = re.compile(r"/(es|en|ca|eu|gl|va|fr|de|it|pt|cas|cat|eng|esp)(?=/|$)", re.I)
# Subpáginas pegadas al nombre de la ficha (UCM: master-x-plan, master-x-plazas, master-x-acceso).
SUFIJO_SUBPAGINA = re.compile(r"-(plan|plazas|acceso|estructura|profesorado|salidas|calendario|horarios?|matricula|"
                              r"admision|precios?|becas|competencias|objetivos|presentacion|normativa|tfm|practicas|"
                              r"calidad|documentacion|resultados|guias?|movilidad|acreditacion|contacto)$", re.I)
# Sedes de otros países de la misma universidad (mexico.unir.net): no son la oferta española.
HOST_OTRO_PAIS = re.compile(r"^(mexico|colombia|peru|ecuador|chile|argentina|bolivia|paraguay|uruguay|venezuela|"
                            r"guatemala|panama|costarica|dominicana|latam|usa|us|mx|co|pe|ec|cl|ar)\.", re.I)


def sin_idioma(url: str) -> str:
    """La misma ficha en castellano, catalán o inglés es la misma ficha."""
    return IDIOMA.sub("", sin_modalidad(url))


def _tramo_ficha(url: str) -> set[str]:
    ultimo = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
    return palabras_url("/" + SUFIJO_SUBPAGINA.sub("", ultimo))


def misma_ficha(a: str, b: str) -> bool:
    """Dos URL de la misma ficha: iguales sin idioma ni modalidad, una cuelga de la otra, o mismo último
    tramo (con las mismas palabras, sin sufijos de subpágina) en el mismo dominio registrado
    (uchceu.es/master-x/ y uchceu.es/fr/master/master-x/; veterinaria.ucm.es/…/master-x-plan y
    odontologia.ucm.es/…/master-x-plazas)."""
    if not a or not b:
        return False
    x, y = EXTENSION.sub("", sin_idioma(a).rstrip("/")), EXTENSION.sub("", sin_idioma(b).rstrip("/"))
    if x == y or x.startswith(y + "/") or y.startswith(x + "/"):
        return True
    if dominio_registrado(a) != dominio_registrado(b):
        return False
    ta, tb = _tramo_ficha(x), _tramo_ficha(y)
    return bool(ta) and ta == tb and (len(ta) >= 2 or any(len(w) >= 10 for w in ta))


def _en(w: str, url: set[str]) -> bool:
    """La palabra está en la URL, sola o dentro de un tramo pegado («master-antropologiafisica», «masterlogic»)."""
    return w in url or (len(w) >= 4 and any(len(t) >= 9 and w in t for t in url))


def puntuacion(nombre: set[str], url: set[str]) -> float:
    """Parte del nombre recogida en la URL, penalizando URL con muchas palabras ajenas."""
    if not nombre or not url:
        return 0.0
    comunes = sum(1 for w in nombre if _en(w, url))
    if not comunes:
        return 0.0
    pegados = sum(1 for t in url if len(t) >= 9 and t not in nombre and any(w in t for w in nombre if len(w) >= 4))
    ajenas = max(len(url) - pegados, 0) + pegados  # un tramo pegado cuenta como una palabra de la URL
    return round(comunes / len(nombre) * (min(comunes, ajenas) / max(ajenas, comunes)) ** 0.25, 3)


def palabras_texto(texto: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", _plano(texto or "")) if w not in VACIAS and len(w) > 1}


def emparejar(titulos: list[dict], urls: list[str], textos: dict[str, str] | None = None) -> list[dict]:
    """textos: URL → texto del enlace que lleva a ella («Máster Universitario en …»). Cuando lo hay, se
    compara con el nombre oficial en vez de la URL (muchas webs usan URL opacas: ?id=3329, /1371206754147/)."""
    textos = textos or {}
    originales: dict[str, list[str]] = {}
    for u in urls:
        u = html.unescape(u)  # «&amp;» de los enlaces y sitemaps
        if not HOST_OTRO_PAIS.match(urlparse(u).netloc):
            originales.setdefault(raiz_programa(u), []).append(u)
    raices = sorted(originales)
    reales = {r: url_real(r, v) for r, v in originales.items()}
    real = {r: v[0] for r, v in reales.items()}
    textos = {html.unescape(u): t for u, t in textos.items()}
    texto_raiz: dict[str, str] = {}
    # el texto del enlace a la ficha misma antes que el de una subpágina («Plan de estudios»)
    for u, t in sorted(textos.items(), key=lambda ut: raiz_programa(ut[0], False) != raiz_programa(ut[0])):
        texto_raiz.setdefault(raiz_programa(u), t)
    pals = [(u, palabras_texto(texto_raiz[u]) if palabras_texto(texto_raiz.get(u, "")) else palabras_url(sin_modalidad(u)))
            for u in raices]
    salida = []
    for t in titulos:
        pn = palabras_nombre(t["nombre_oficial"])
        puntos = sorted(((puntuacion(pn, pu), u) for u, pu in pals), reverse=True)[:6]
        mejor = puntos[0] if puntos else (0.0, None)
        # la misma ficha en varias modalidades o idiomas no es un empate: son la misma oferta
        if puntos:
            iguales = [u for p, u in puntos if p == mejor[0] and misma_ficha(u, mejor[1])]
            # entre raíces empatadas, antes la que tiene página propia que la que solo se vio por sus subpáginas
            mejor = (mejor[0], min(iguales, key=lambda u: (reales.get(u, ("", True))[1],
                                                           raiz_programa(real.get(u, u), False) != u,
                                                           bool(SUFIJO_SUBPAGINA.search(urlparse(u).path.rstrip("/"))),
                                                           bool(IDIOMA.search(u)) and not re.search(r"/(es|cas|esp)(/|$)", u),
                                                           not urlparse(u).netloc.startswith("www."), len(u))))
        rivales = [p for p, u in puntos if not misma_ficha(u, mejor[1] or "")]
        segundo = rivales[0] if rivales else 0.0
        # una URL por modalidad (presencial, online…), la de castellano si hay varias lenguas
        por_modalidad: dict[str, list[str]] = {}
        for p_, u in puntos:
            if mejor[1] and p_ == mejor[0] and sin_idioma(u) == sin_idioma(mejor[1]):
                por_modalidad.setdefault(IDIOMA.sub("", u.rstrip("/")), []).append(u)
        modalidades = sorted(min(v, key=lambda u: (not re.search(r"/(es|cas|esp)/", u), len(u)))
                             for v in por_modalidad.values())
        if mejor[0] >= UMBRAL and mejor[0] - segundo >= MARGEN:
            estado = "unido"
        elif mejor[0] >= UMBRAL:
            estado = "dudoso"  # varias páginas igual de buenas (idiomas, modalidades): revisar
        else:
            estado = "sin_pagina"
        url = real.get(mejor[1], mejor[1]) if estado != "sin_pagina" else None
        salida.append({"codigo_ruct": t["codigo_ruct"], "nombre_oficial": t["nombre_oficial"], "estado": estado,
                       "url": url, "puntuacion": mejor[0],
                       "url_es_subpagina": bool(url) and raiz_programa(url, False) != mejor[1],
                       "url_deducida": bool(url) and reales.get(mejor[1], ("", True))[1],
                       # sin página: la mejor candidata igualmente, para que la extracción la compruebe por el nombre
                       "candidata": real.get(mejor[1], mejor[1]) if estado == "sin_pagina" and mejor[1] else None,
                       "subpaginas": subpaginas_utiles(mejor[1], originales.get(mejor[1], []), url) if url else [],
                       "urls_modalidad": [real.get(u, u) for u in modalidades] if estado == "unido" and len(modalidades) > 1 else [],
                       "alternativas": [{"url": real.get(u, u), "puntuacion": p} for p, u in puntos[1:]]})
    return salida


def _leer(ruta: Path) -> list[dict]:
    texto = ruta.read_text(encoding="utf-8").strip()
    return json.loads(texto) if texto.startswith("[") else [json.loads(l) for l in texto.splitlines() if l.strip()]


def ejecutar(catalogo: Path, censo: Path, rastreos: list[Path], salida: Path, cc_urls: Path | None = None) -> dict:
    """Une los másters activos del catálogo con las páginas de programa de las webs de su universidad y de
    sus centros (todos los proveedores del censo con referencia RUCT a esa universidad): las del rastreo y,
    si se dan, las de Common Crawl de esos dominios (`commoncrawl.py --urls-de`)."""
    from motor.estudios.rastreador import es_programa

    titulos = [t for t in _leer(catalogo) if t.get("situacion") == "Activo"]
    provs = _leer(censo)
    rastreo: dict[str, dict] = {}
    for c in rastreos:
        for f in c.rglob("oferta_web/*.json"):
            r = json.loads(f.read_text(encoding="utf-8"))
            rastreo[(r.get("centro") or {}).get("id")] = r
    de_cc: dict[str, set] = {}
    if cc_urls:
        for f in cc_urls.rglob("urls_*.jsonl"):
            for l in f.read_text(encoding="utf-8").splitlines():
                d = json.loads(l)
                de_cc.setdefault(d["dominio"], set()).update(u for u in d["urls"] if es_programa(u))
    urls_univ: dict[str, set] = {}
    textos: dict[str, str] = {}
    for p in provs:
        r = rastreo.get(p["id"]) or {}
        textos.update(r.get("textos_programa") or {})
        urls = set(r.get("programas", [])).union(*[de_cc.get(d, set()) for d in p.get("dominios", [])])
        for ref in p.get("ruct", []):
            urls_univ.setdefault(ref["universidad"], set()).update(urls)
    por_univ: dict[str, list[dict]] = {}
    for t in titulos:
        por_univ.setdefault(t.get("universidad_codigo") or "", []).append(t)
    res, filas = Counter(), []
    for u, ts in sorted(por_univ.items()):
        urls = sorted(urls_univ.get(u, set()))
        if not urls:
            res["sin_urls_de_la_universidad"] += len(ts)
            filas += [{"codigo_ruct": t["codigo_ruct"], "nombre_oficial": t["nombre_oficial"], "estado": "sin_urls",
                       "url": None} for t in ts]
            continue
        for e in emparejar(ts, urls, textos):
            res[e["estado"]] += 1
            filas.append(e)
    destino = salida / "datos" / "estudios" / "masters"
    destino.mkdir(parents=True, exist_ok=True)
    with (destino / "paginas_oficiales.jsonl").open("w", encoding="utf-8") as fh:
        for e in filas:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    return dict(res)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--catalogo", required=True, help="catalogo.jsonl (o lista JSON) de catalogo.py")
    p.add_argument("--censo", required=True, help="proveedores.jsonl de censo.py")
    p.add_argument("--rastreo", action="append", default=[], help="carpeta con resultados del rastreador")
    p.add_argument("--commoncrawl", help="carpeta con urls_*.jsonl de commoncrawl.py --urls-de")
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    print(json.dumps(ejecutar(Path(a.catalogo), Path(a.censo), [Path(x) for x in a.rastreo], Path(a.salida),
                              Path(a.commoncrawl) if a.commoncrawl else None), ensure_ascii=False))


if __name__ == "__main__":
    main()
