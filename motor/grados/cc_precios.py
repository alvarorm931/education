"""Páginas y PDF de precios de las universidades privadas en el índice de Common Crawl.

El rastreo de cada web (web_privadas.py) solo ve lo que enlazan su sitemap y sus páginas de grado. Common Crawl
guarda además documentos que la web ya no enlaza o que cuelgan de otros dominios suyos (listas de precios en
PDF de la Universidad Europea o la Alfonso X, por ejemplo: docs/estrategia-informacion-cerrada.md §3.2). Aquí se
buscan, en el índice en columnas de Common Crawl, las URL de los dominios de las universidades privadas cuya ruta
habla de precios. Solo se leen metadatos de URL (dominio y ruta), como en motor/estudios/commoncrawl.py, cuyas
funciones de índice se usan sin tocarlas. Las páginas se piden después con tarifas_grado.py, con robots.txt.

Uso:
  python -m motor.grados.cc_precios --rastreos carpeta_web_privadas --archivos 0:75 --salida ruta/
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from motor.estudios.commoncrawl import CONSULTA_URLS, ficheros, sin_secretos, ultimo_crawl

# Precios de grado: tarifas, honorarios, precios de matrícula, tasas… en PDF o en página; no másters ni cursos
PATRON = (r"(?i)(tarifa|precio|preu|prezo|honorario|importe|tasas|fees|tuition|coste|cuota|matr[ií]cula|"
          r"condiciones-economicas|financiaci)")
EXCLUIR = (r"(?i)(m[aá]ster|postgrado|posgrado|doctorad|/blog|noticia|/news|actualidad|curso-de|/cursos?/|"
           r"idioma|residencia|colegio-mayor|deporte|parking|/en/|/ca/|/eu/|\.(jpe?g|png|gif|webp|svg|css|js)$)")


def dominio_registrado(web: str) -> str | None:
    from motor.estudios.rastreador import dominio_registrado as registrado

    host = urlparse(web if web.startswith("http") else "https://" + web).netloc.lower()
    return registrado(host) if host else None


def dominios(rastreos: Path) -> dict[str, dict]:
    """Dominio registrado → universidad (código y nombre), desde los rastreos de web_privadas."""
    salida = {}
    for f in sorted(rastreos.rglob("web_privadas/[0-9]*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        uni = {"codigo": d.get("codigo"), "universidad": d.get("universidad"), "web": d.get("web")}
        # el dominio del RUCT y los de sus páginas de grado (universidadeuropea.es → universidadeuropea.com)
        for web in [d.get("web") or ""] + [f.get("url") or "" for f in (d.get("fichas") or {}).values()]:
            dom = dominio_registrado(web)
            if dom and dom not in salida:
                salida[dom] = uni
    return salida


def consultar(fichero: str, doms: list[str]) -> list[dict]:
    import duckdb

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; SET http_retries=6; SET http_retry_wait_ms=2000;")
    lista = ",".join("'" + d.replace("'", "") + "'" for d in doms)
    filas = con.execute(CONSULTA_URLS.format(fichero=fichero, dominios=lista, patron=PATRON.replace("'", "''"),
                                             excluir=EXCLUIR.replace("'", "''"))).fetchall()
    return [{"dominio": d, "url": sin_secretos(u)} for d, u in filas]


def ejecutar(rastreos: Path, crawl: str | None, desde: int, hasta: int, salida: Path, max_minutos: float) -> dict:
    doms = dominios(rastreos)
    crawl = crawl or ultimo_crawl()
    lista = ficheros(crawl)[desde:hasta]
    fin = time.time() + max_minutos * 60
    urls, hechos, errores = {}, 0, []
    for f in lista:
        if time.time() > fin:
            break
        try:
            for x in consultar(f, sorted(doms)):
                urls.setdefault(x["url"], {**x, **doms.get(x["dominio"], {})})
            hechos += 1
        except Exception as e:  # noqa: BLE001 - un fichero que falla no para el resto
            errores.append(f"{f.rsplit('/', 1)[-1]}: {type(e).__name__}: {str(e)[:100]}")
    destino = salida / "datos" / "estudios" / "grados" / "cc_precios"
    destino.mkdir(parents=True, exist_ok=True)
    with (destino / f"urls_{crawl}_{desde}_{hasta}.jsonl").open("w", encoding="utf-8") as fh:
        for x in urls.values():
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")
    res = {"crawl": crawl, "ficheros": len(lista), "leidos": hechos, "errores": errores[:10], "dominios": len(doms),
           "urls": len(urls), "pdf": sum(1 for u in urls if re.search(r"\.pdf($|\?)", u, re.I)),
           "por_universidad": {}}
    for x in urls.values():
        res["por_universidad"][x.get("universidad") or x["dominio"]] = res["por_universidad"].get(
            x.get("universidad") or x["dominio"], 0) + 1
    (destino / f"resumen_{crawl}_{desde}_{hasta}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1),
                                                                   encoding="utf-8")
    return res


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--rastreos", required=True, help="carpeta con …/web_privadas/{código}.json")
    p.add_argument("--crawl", help="por defecto, el último")
    p.add_argument("--archivos", default="0:2", help="tramo de ficheros del índice, p. ej. 0:75")
    p.add_argument("--max-minutos", type=float, default=50)
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    d, h = (int(x) for x in a.archivos.split(":"))
    print(json.dumps(ejecutar(Path(a.rastreos), a.crawl, d, h, Path(a.salida), a.max_minutos), ensure_ascii=False,
                     indent=1))


if __name__ == "__main__":
    main()
