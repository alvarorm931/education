"""Une cada máster oficial (código RUCT) con su página en la web de su universidad.

Con el nombre oficial del RUCT y las URL de programa del sitemap de la universidad (rastreador), se busca la
página cuyo último tramo de ruta mejor recoge las palabras significativas del nombre. Se acepta solo si la
coincidencia es alta y no hay empate; lo demás queda «sin página» o «dudoso» para revisión. Nada se une por
aproximación sin dejar constancia de la puntuación.

Uso:
  python -m motor.estudios.emparejar --catalogo catalogo.jsonl --oferta carpeta/oferta_web --salida ruta/
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlparse

from motor.estudios.censo import dominio_registrado

VACIAS = set("""de del la las el los en y e o u a por para con sin su sus al lo un una uno unos unas
master masters master's universitario universitaria universidad university oficial online presencial
semipresencial distancia mu mba degree in of and the by""".split())
SUBPAGINAS = re.compile(r"^(acceso|admision|admisiones|profesorado|claustro|plan-de-estudios|programa|temario|salidas|"
                        r"salidas-profesionales|precio|precios|becas|financiacion|metodologia|titulacion|investigacion|"
                        r"practicas|calidad|horarios?|calendario|requisitos|matricula|preinscripcion|faq|opiniones|"
                        r"presentacion|competencias|objetivos|informacion|contacto|documentacion|guias?-docentes?)$")
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
    partes = [p for p in urlparse(url).path.split("/") if p]
    tramo = " ".join(partes[-2:]) if partes else ""
    return {w for w in re.findall(r"[a-z0-9]+", _plano(tramo)) if w not in VACIAS and len(w) > 1}


def raiz_programa(url: str) -> str:
    """Quita las subpáginas habituales de una ficha (/acceso, /profesorado, /plan-de-estudios…)."""
    u = urlparse(url)
    partes = [p for p in u.path.split("/") if p]
    while len(partes) > 1 and SUBPAGINAS.match(partes[-1].lower()):
        partes.pop()
    return f"{u.scheme}://{u.netloc}/" + "/".join(partes) + "/"


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
    x, y = sin_idioma(a).rstrip("/"), sin_idioma(b).rstrip("/")
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
    raices = sorted({raiz_programa(u) for u in urls if not HOST_OTRO_PAIS.match(urlparse(u).netloc)})
    texto_raiz: dict[str, str] = {}
    for u, t in textos.items():
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
            mejor = (mejor[0], min(iguales, key=lambda u: (bool(SUFIJO_SUBPAGINA.search(urlparse(u).path.rstrip("/"))),
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
        salida.append({"codigo_ruct": t["codigo_ruct"], "nombre_oficial": t["nombre_oficial"], "estado": estado,
                       "url": mejor[1] if estado != "sin_pagina" else None, "puntuacion": mejor[0],
                       "urls_modalidad": modalidades if estado == "unido" and len(modalidades) > 1 else [],
                       "alternativas": [{"url": u, "puntuacion": p} for p, u in puntos[1:]]})
    return salida


def ejecutar(catalogo: Path, oferta: Path, salida: Path) -> dict:
    titulos = [json.loads(l) for l in catalogo.read_text(encoding="utf-8").splitlines() if l.strip()]
    titulos = [t for t in titulos if t["situacion"] == "Activo"]
    webs: dict[str, list[str]] = {}
    textos: dict[str, str] = {}
    for f in oferta.glob("*.json"):
        r = json.loads(f.read_text(encoding="utf-8"))
        webs.setdefault(dominio_registrado(r["dominio"]), []).extend(r.get("programas", []))
        textos.update(r.get("textos_programa") or {})
    res, filas = Counter(), []
    por_univ: dict[str, list[dict]] = {}
    for t in titulos:
        por_univ.setdefault(t.get("universidad_web") or "", []).append(t)
    for dominio, urls in webs.items():
        for t_univ in (v for k, v in por_univ.items() if k and dominio_registrado(k) == dominio):
            for e in emparejar(t_univ, sorted(set(urls)), textos):
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
    p.add_argument("--catalogo", required=True)
    p.add_argument("--oferta", required=True)
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    print(json.dumps(ejecutar(Path(a.catalogo), Path(a.oferta), Path(a.salida)), ensure_ascii=False))


if __name__ == "__main__":
    main()
