"""Páginas casi iguales: grupos de páginas cuyo contenido principal se parece por encima del umbral.

Es el control contra las páginas puerta («páginas casi iguales por pueblo o variante», ley SEO) y contra el
contenido en masa sin valor. Se compara el texto visible de `<main>` (sin cabecera, menú ni pie), en minúsculas
y en tejas de 5 palabras. Parecido = índice de Jaccard entre los conjuntos de tejas.

No se comparan todas con todas (con 500.000 páginas serían 125.000 millones de pares): MinHash (128
permutaciones) y LSH (16 bandas de 8) proponen candidatos a partir de un parecido de (1/16)^(1/8) ≈ 0,71, y cada
candidato se confirma con el Jaccard exacto. Los grupos se forman uniendo cada página con la primera de su cubo
(unión de conjuntos), así un cubo de 8.000 fichas iguales cuesta 8.000 comparaciones y no 32 millones.

Umbral por defecto 0,90; la ley lo deja «a calibrar». Para calibrarlo:
`python -m motor.seo.similitud --sitio web/ --umbral 0.7` y revisar a mano los grupos entre 0,7 y 0,9.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import numpy as np

PRIMO = (1 << 31) - 1
PERMUTACIONES = 128
BANDAS, FILAS = 16, 8
_rng = np.random.default_rng(20261030)
_A = _rng.integers(1, PRIMO, PERMUTACIONES, dtype=np.uint64)
_B = _rng.integers(0, PRIMO, PERMUTACIONES, dtype=np.uint64)
PALABRA = re.compile(r"\w+", re.UNICODE)


def tejas(texto: str, n: int = 5) -> np.ndarray:
    palabras = PALABRA.findall((texto or "").lower())
    if not palabras:
        return np.empty(0, dtype=np.uint64)
    grupos = [" ".join(palabras)] if len(palabras) < n else \
        [" ".join(palabras[i:i + n]) for i in range(len(palabras) - n + 1)]
    valores = {int.from_bytes(hashlib.blake2b(g.encode(), digest_size=4).digest(), "little") % PRIMO
               for g in grupos}
    return np.array(sorted(valores), dtype=np.uint64)


def firma(conjunto: np.ndarray) -> np.ndarray:
    if not len(conjunto):
        return np.full(PERMUTACIONES, PRIMO, dtype=np.uint64)
    return ((_A[:, None] * conjunto[None, :] + _B[:, None]) % PRIMO).min(axis=1)


def jaccard(a: np.ndarray, b: np.ndarray) -> float:
    if not len(a) and not len(b):
        return 1.0
    comun = len(np.intersect1d(a, b, assume_unique=True))
    return comun / (len(a) + len(b) - comun)


def grupos_parecidos(textos: dict[str, str], umbral: float = 0.9) -> list[dict]:
    """Grupos de rutas cuyo texto se parece al de la primera del grupo por encima del umbral.

    Devuelve [{"paginas": [ruta, …], "parecido_minimo": x}], de mayor a menor. Las páginas sin texto no se
    agrupan (de eso se encarga la comprobación de contenido)."""
    claves = sorted(k for k, t in textos.items() if PALABRA.search(t or ""))
    if len(claves) < 2:
        return []
    conjuntos = {k: tejas(textos[k]) for k in claves}
    firmas = {k: firma(conjuntos[k]) for k in claves}
    padre = {k: k for k in claves}

    def raiz(k):
        while padre[k] != k:
            padre[k] = padre[padre[k]]
            k = padre[k]
        return k

    for b in range(BANDAS):
        cubos: dict[bytes, list[str]] = {}
        for k in claves:
            cubos.setdefault(firmas[k][b * FILAS:(b + 1) * FILAS].tobytes(), []).append(k)
        for miembros in cubos.values():
            base = miembros[0]
            for otro in miembros[1:]:
                if raiz(otro) != raiz(base) and jaccard(conjuntos[base], conjuntos[otro]) >= umbral:
                    padre[raiz(otro)] = raiz(base)

    por_raiz: dict[str, list[str]] = {}
    for k in claves:
        por_raiz.setdefault(raiz(k), []).append(k)
    salida = []
    for miembros in por_raiz.values():
        if len(miembros) > 1:
            minimo = min(jaccard(conjuntos[miembros[0]], conjuntos[m]) for m in miembros[1:])
            salida.append({"paginas": miembros, "parecido_minimo": round(minimo, 3)})
    return sorted(salida, key=lambda g: (-len(g["paginas"]), g["paginas"][0]))


def main(argv=None):
    from motor.seo.control import cargar_sitio

    p = argparse.ArgumentParser(description="Grupos de páginas casi iguales (calibración del umbral)")
    p.add_argument("--sitio", type=Path, required=True)
    p.add_argument("--umbral", type=float, default=0.9)
    a = p.parse_args(argv)
    paginas = cargar_sitio(a.sitio)
    grupos = grupos_parecidos({r: pg.texto_main for r, pg in paginas.items() if pg.indexable}, a.umbral)
    print(json.dumps(grupos, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
