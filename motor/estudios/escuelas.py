"""Escuelas de negocio y universidades de referencia, a fondo: todas sus fichas de máster y sus páginas de precio.

Petición de Álvaro (31/10/2026): que estén IE, IESE y las demás escuelas de referencia con la información completa.
La lectura general (`extraer.py lista-no-oficiales`) toma una muestra de cada centro; aquí, para las escuelas de la
lista (en orden de reputación, `reputacion.py`), se recorre su sitemap y sus listados (`rastreador.rastrear`), se
toman todas las fichas de máster, MBA o MSc y las páginas de precio y admisión que cuelgan de ellas
(«/master-in-finance/admissions-fees»), y se extraen con el navegador (los precios de IE se pintan con
JavaScript) en la misma ejecución. robots.txt, una petición por segundo y servidor, originales al almacén privado.
Las webs que rechazan a nuestro lector (ESADE y EADA, 403) no se fuerzan: van en la carta de permiso.

Uso: python -m motor.estudios.escuelas --escuela ie.edu --navegador [--max-paginas 300] --salida ruta/
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

# dominio → web de partida y listados que conviene recorrer (en orden de reputación)
ESCUELAS = {
    "ie.edu": {"web": "https://www.ie.edu", "listados": ["https://www.ie.edu/masters/", "https://www.ie.edu/business-school/programs/"]},
    "iese.edu": {"web": "https://www.iese.edu", "listados": ["https://www.iese.edu/programs/"]},
    "cunef.edu": {"web": "https://www.cunef.edu", "listados": ["https://www.cunef.edu/estudios/"]},
    "comillas.edu": {"web": "https://www.comillas.edu", "listados": ["https://www.comillas.edu/postgrados/"]},
    "deusto.es": {"web": "https://www.deusto.es", "listados": ["https://www.deusto.es/es/inicio/estudia/estudios/master"]},
    "esic.edu": {"web": "https://www.esic.edu", "listados": ["https://www.esic.edu/postgrado"]},
    "eae.es": {"web": "https://www.eae.es", "listados": ["https://www.eae.es/masters"]},
    "eoi.es": {"web": "https://www.eoi.es", "listados": ["https://www.eoi.es/es/cursos"]},
    "isdi.education": {"web": "https://www.isdi.education", "listados": []},
    "unav.edu": {"web": "https://www.unav.edu", "listados": ["https://www.unav.edu/estudios/masteres"]},
}
BLOQUEADAS = {"esade.edu": "403 a nuestro lector", "eada.edu": "403 a nuestro lector"}

RE_SEGUIMIENTO = re.compile(r"(?i)[?&](_gl|utm_[a-z]+|gclid|fbclid|_ga)=")
RE_GENERICA = re.compile(r"(?i)/(admissions?|admision|admisiones|blog|news|noticias|events?|eventos|alumni|faculty|"
                         r"profesorado|stories|quiz)(/|$)")
RE_MASTER_URL = re.compile(r"(?i)m[aàá]ster|\bmba\b|[-_/]mba[-_/]|\bmsc\b|[-_/]msc[-_/]|[-_/]mim[-_/]|\bllm\b|[-_/]llm[-_/]")


def filas(res: dict, dominio: str, max_paginas: int = 300) -> list[dict]:
    """Las fichas de máster (primero) y sus páginas de precio, como filas de la extracción de no oficiales: si la
    página es la de un máster oficial, fichas_masters la une después por el nombre del RUCT."""
    from motor.estudios.censo import dominio_registrado, id_proveedor

    prov = id_proveedor(dominio_registrado(dominio))
    principal = urlparse(res.get("base_final") or f"https://www.{dominio}").netloc
    # fichas de la web principal (no subdominios de concursos o campañas), sin parámetros de seguimiento ni
    # páginas generales de admisión, noticias o profesorado
    progs = [u for u in res.get("programas") or [] if RE_MASTER_URL.search(urlparse(u).path)
             and urlparse(u).netloc == principal and not RE_SEGUIMIENTO.search(u) and not RE_GENERICA.search(urlparse(u).path)]
    precio = list(res.get("subpaginas_precio") or [])
    out, vistos = [], set()
    # cada ficha con sus páginas de precio detrás, para no quedarse con fichas sin precio si se llega al tope
    por_raiz: dict[str, list[str]] = {}
    raices = {urlparse(u).path.rstrip("/") for u in progs}
    for u in precio:
        padre = urlparse(u).path.rstrip("/").rsplit("/", 1)[0]
        raiz = padre if padre in raices else padre.rsplit("/", 1)[0]
        por_raiz.setdefault(raiz, []).append(u)
    for u in progs:
        for x in [u] + por_raiz.get(urlparse(u).path.rstrip("/"), []):
            if x not in vistos and len(out) < max_paginas:
                vistos.add(x)
                out.append({"url": x, "grupo": "no_oficial", "proveedor": prov, "pagina": "principal",
                            "estado_emparejado": "escuela_a_fondo"})
    return out


def ejecutar(dominio: str, salida: Path, max_paginas: int = 300, max_minutos: float = 52, navegador: bool = True) -> dict:
    from motor.estudios import extraer
    from motor.estudios.rastreador import rastrear

    t0 = time.time()
    if dominio in BLOQUEADAS:
        return {"dominio": dominio, "no_se_lee": BLOQUEADAS[dominio]}
    e = ESCUELAS[dominio]
    res = rastrear(e["web"], None, max_urls=60000, muestra=2, max_peticiones=220, profundo=True,
                   listados=e.get("listados") or [])
    destino = salida / "datos" / "estudios" / "extraccion" / f"escuela_{dominio.replace('.', '_')}"
    destino.mkdir(parents=True, exist_ok=True)
    fs = filas(res, dominio, max_paginas)
    resumen = {"dominio": dominio, "rastreo": {k: res.get(k) for k in ("base_final", "error", "veto_robots", "urls",
                                                                        "urls_programa", "via", "peticiones")},
               "fichas_master": sum(1 for f in fs if RE_MASTER_URL.search(urlparse(f["url"]).path)),
               "paginas_precio": len(res.get("subpaginas_precio") or []), "filas": len(fs)}
    muestra = destino / "escuela.jsonl"
    muestra.write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in fs), encoding="utf-8")
    if fs:
        resumen["lote"] = extraer.lote(muestra, destino, esperar_min=25, hilos=4,
                                       max_minutos=max(10.0, max_minutos - (time.time() - t0) / 60), navegador=navegador)
    (destino / "resumen_escuela.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    return resumen


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--escuela", required=True, choices=sorted(ESCUELAS) + sorted(BLOQUEADAS))
    a.add_argument("--max-paginas", type=int, default=300)
    a.add_argument("--max-minutos", type=float, default=52)
    a.add_argument("--navegador", action="store_true", help="pinta con Chromium las páginas sin texto (estudios.yml lo instala)")
    a.add_argument("--salida", required=True)
    x = a.parse_args()
    print(json.dumps(ejecutar(x.escuela, Path(x.salida), x.max_paginas, x.max_minutos, x.navegador), ensure_ascii=False))


if __name__ == "__main__":
    main()
