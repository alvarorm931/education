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
    "ie.edu": {"web": "https://www.ie.edu", "listados": ["https://www.ie.edu/masters/sitemap/", "https://www.ie.edu/masters/",
                                                         "https://www.ie.edu/business-school/programs/"]},
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


CDX = "https://index.commoncrawl.org/{crawl}-index?url={host}/*&output=json&fl=url,status,mime&filter=status:200&page={page}"
MAX_PAGINAS_CDX = 8


def urls_de_common_crawl(host: str, crawls: int = 2) -> list[str]:
    """Las páginas de la web que Common Crawl tiene en sus dos últimos índices (solo la dirección: no se baja ni se
    reproduce nada). Las escuelas con poco sitemap (IE) tienen ahí sus fichas de programa."""
    from motor.estudios.commoncrawl import ultimo_crawl
    from motor.http import obtener

    out: set[str] = set()
    for n in range(crawls):
        try:
            crawl = ultimo_crawl(n)
        except Exception:  # noqa: BLE001
            break
        for page in range(MAX_PAGINAS_CDX):
            try:
                r = obtener(CDX.format(crawl=crawl, host=host, page=page), intentos=2, timeout=60, limite_total=120)
            except Exception:  # noqa: BLE001 - página fuera de rango o índice ocupado: se sigue con lo que hay
                break
            if r.status != 200 or not r.contenido.strip():
                break
            for linea in r.contenido.decode("utf-8", "replace").splitlines():
                try:
                    x = json.loads(linea)
                except ValueError:
                    continue
                if "html" in str(x.get("mime", "")) and str(x.get("status")) == "200":
                    out.add(x["url"].split("#")[0])
            time.sleep(1)
    return sorted(out)


def unir_common_crawl(res: dict, urls_cc: list[str]) -> dict:
    """Añade al rastreo las fichas de programa y las páginas de precio que solo ve Common Crawl."""
    from motor.estudios.rastreador import SUBPAGINA_PRECIO, es_programa

    progs = set(res.get("programas") or []) | {u for u in urls_cc if es_programa(u)}
    raices = {urlparse(u).path.rstrip("/") for u in progs}
    precio = set(res.get("subpaginas_precio") or [])
    for u in urls_cc:
        ruta = urlparse(u).path.rstrip("/")
        padre = ruta.rsplit("/", 1)[0]
        if SUBPAGINA_PRECIO.search(ruta.rsplit("/", 1)[-1]) and (padre in raices or padre.rsplit("/", 1)[0] in raices):
            precio.add(u)
    return {**res, "programas": sorted(progs), "subpaginas_precio": sorted(precio)}


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


def segunda_vuelta(destino: Path, dominio: str, max_paginas: int = 200) -> list[dict]:
    """Las páginas de precio y de plan enlazadas desde las fichas leídas a las que les falta el precio (en el
    original guardado): muchas escuelas no las ponen en el sitemap («/master-in-finance/admissions-fees»)."""
    from motor.estudios import extraer
    from motor.estudios.censo import dominio_registrado, id_proveedor

    guarda = extraer.Guarda()
    if not guarda.activa:
        return []
    leer = lambda n: [json.loads(l) for f in destino.glob(n) for l in f.read_text(encoding="utf-8").split("\n") if l.strip()]
    claves = {x["url"]: x["clave"] for x in leer("paginas_capturadas.jsonl") if x.get("clave")}
    hechos: dict[str, set] = {}
    for h in leer("hechos.jsonl"):
        if h.get("estado") == "aceptado":
            hechos.setdefault(h["url"], set()).add(h["campo"])
    fichas = [x["url"] for x in leer("paginas_extraidas.jsonl") if not x.get("no_es_programa")]
    prov = id_proveedor(dominio_registrado(dominio))
    ya, out = set(claves), []
    for u in fichas:
        faltan = [c for c, campos in (("precio", {"precio_total", "precio_credito"}), ("asignaturas", {"asignaturas"}))
                  if not hechos.get(u, set()) & campos]
        if not faltan or u not in claves:
            continue
        try:
            html = guarda.almacen.leer(claves[u]).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            continue
        for s_ in extraer.subpaginas_enlazadas(html, u, faltan):
            if s_ not in ya and len(out) < max_paginas:
                ya.add(s_)
                out.append({"url": s_, "grupo": "no_oficial", "proveedor": prov, "pagina": "principal",
                            "estado_emparejado": "escuela_enlazada"})
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
    urls_cc = urls_de_common_crawl(urlparse(res.get("base_final") or e["web"]).netloc) if e.get("common_crawl", True) else []
    res = unir_common_crawl(res, urls_cc)
    destino = salida / "datos" / "estudios" / "extraccion" / f"escuela_{dominio.replace('.', '_')}"
    destino.mkdir(parents=True, exist_ok=True)
    fs = filas(res, dominio, max_paginas)
    resumen = {"dominio": dominio, "rastreo": {k: res.get(k) for k in ("base_final", "error", "veto_robots", "urls",
                                                                        "urls_programa", "via", "peticiones")},
               "fichas_master": sum(1 for f in fs if RE_MASTER_URL.search(urlparse(f["url"]).path)),
               "paginas_precio": len(res.get("subpaginas_precio") or []), "urls_common_crawl": len(urls_cc), "filas": len(fs)}
    muestra = destino / "escuela.jsonl"
    muestra.write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in fs), encoding="utf-8")
    if fs:
        resumen["lote"] = extraer.lote(muestra, destino, esperar_min=20, hilos=4,
                                       max_minutos=max(10.0, (max_minutos - (time.time() - t0) / 60) * 0.55), navegador=navegador)
        # segunda vuelta: precio y plan enlazados desde las fichas leídas
        f2 = segunda_vuelta(destino, dominio)
        resumen["segunda_vuelta"] = len(f2)
        quedan = max_minutos - (time.time() - t0) / 60
        if f2 and quedan > 12:
            d2 = destino.parent / f"{destino.name}_enlazadas"
            d2.mkdir(parents=True, exist_ok=True)
            m2 = d2 / "escuela_enlazadas.jsonl"
            m2.write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in f2), encoding="utf-8")
            resumen["lote_enlazadas"] = extraer.lote(m2, d2, esperar_min=15, hilos=4, max_minutos=quedan - 2,
                                                     navegador=navegador)
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
