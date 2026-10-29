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


def puntuacion(nombre: set[str], url: set[str]) -> float:
    """Parte del nombre recogida en la URL, penalizando URL con muchas palabras ajenas."""
    if not nombre or not url:
        return 0.0
    comunes = len(nombre & url)
    return round(comunes / len(nombre) * (comunes / max(len(url), comunes)) ** 0.25, 3)


def emparejar(titulos: list[dict], urls: list[str]) -> list[dict]:
    raices = sorted({raiz_programa(u) for u in urls})
    pals = [(u, palabras_url(sin_modalidad(u))) for u in raices]
    salida = []
    for t in titulos:
        pn = palabras_nombre(t["nombre_oficial"])
        puntos = sorted(((puntuacion(pn, pu), u) for u, pu in pals), reverse=True)[:3]
        mejor = puntos[0] if puntos else (0.0, None)
        # la misma ficha en varias modalidades no es un empate: son ofertas del mismo título
        rivales = [p for p, u in puntos[1:] if sin_modalidad(u) != sin_modalidad(mejor[1] or "")]
        segundo = rivales[0] if rivales else 0.0
        modalidades = [u for p, u in puntos if p == mejor[0] and sin_modalidad(u) == sin_modalidad(mejor[1] or "")]
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
    for f in oferta.glob("*.json"):
        r = json.loads(f.read_text(encoding="utf-8"))
        webs.setdefault(dominio_registrado(r["dominio"]), []).extend(r.get("programas", []))
    res, filas = Counter(), []
    por_univ: dict[str, list[dict]] = {}
    for t in titulos:
        por_univ.setdefault(t.get("universidad_web") or "", []).append(t)
    for dominio, urls in webs.items():
        for t_univ in (v for k, v in por_univ.items() if k and dominio_registrado(k) == dominio):
            for e in emparejar(t_univ, sorted(set(urls))):
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
