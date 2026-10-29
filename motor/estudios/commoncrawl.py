"""Descubrimiento de centros con oferta de posgrado en el índice de Common Crawl.

Common Crawl publica cada mes un índice en columnas (Parquet) de todas las páginas rastreadas, con dominio,
TLD, ruta e idioma. Filtrando las rutas que parecen programas de posgrado en páginas españolas (TLD .es o
idioma español) sale la lista de dominios que venden másters, sean o no universidades. Solo se leen
metadatos de URL: no se descarga ni se reproduce contenido de terceros.

Lectura directa por HTTPS con DuckDB, archivo a archivo, para poder repartirla en tramos.

Uso:
  python -m motor.estudios.commoncrawl --archivos 0:4 --salida ruta/
  python -m motor.estudios.commoncrawl --crawl CC-MAIN-2026-40 --archivos 0:300 --salida ruta/
"""

from __future__ import annotations

import argparse
import gzip
import json
import time
from pathlib import Path

from motor.http import obtener

COLLINFO = "https://index.commoncrawl.org/collinfo.json"
PATHS = "https://data.commoncrawl.org/crawl-data/{crawl}/cc-index-table.paths.gz"
DATA = "https://data.commoncrawl.org/"

PATRON_RUTA = (r"(?i)(m[aá]ster|/mba|maestr[ií]a|postgrado|posgrado|titulos?-propios?|formacion-permanente|"
               r"experto-universitario|especialista-universitario|executive-education)")
CONSULTA = """
SELECT url_host_registered_domain AS dominio, url_host_name AS host,
       count(*) AS paginas,
       any_value(url) AS ejemplo,
       max(url_host_tld) AS tld,
       max(content_languages) AS idiomas
FROM read_parquet('{fichero}')
WHERE subset = 'warc' AND fetch_status = 200
  AND (url_host_tld = 'es' OR content_languages LIKE 'spa%')
  AND regexp_matches(url_path, '{patron}')
GROUP BY 1, 2
"""


def ultimo_crawl() -> str:
    r = obtener(COLLINFO)
    return json.loads(r.contenido)[0]["id"]


def ficheros(crawl: str) -> list[str]:
    r = obtener(PATHS.format(crawl=crawl))
    lineas = gzip.decompress(r.contenido).decode().splitlines()
    return [DATA + l for l in lineas if "subset=warc" in l]


def consultar(fichero: str) -> list[dict]:
    import duckdb

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; SET http_retries=6; SET http_retry_wait_ms=2000;")
    filas = con.execute(CONSULTA.format(fichero=fichero, patron=PATRON_RUTA.replace("'", "''"))).fetchall()
    cols = ["dominio", "host", "paginas", "ejemplo", "tld", "idiomas"]
    return [dict(zip(cols, f)) for f in filas]


def ejecutar(raiz: Path, crawl: str | None, desde: int, hasta: int, max_minutos: float) -> dict:
    crawl = crawl or ultimo_crawl()
    lista = ficheros(crawl)
    destino = raiz / "datos" / "estudios" / "commoncrawl" / crawl
    destino.mkdir(parents=True, exist_ok=True)
    fin = time.time() + max_minutos * 60
    hechos, filas_total, tiempos = 0, 0, []
    for i in range(desde, min(hasta, len(lista))):
        if time.time() > fin:
            break
        t0 = time.time()
        try:
            filas = consultar(lista[i])
        except Exception as e:
            (destino / f"{i:05d}.error.txt").write_text(f"{lista[i]}\n{e}", encoding="utf-8")
            continue
        with (destino / f"{i:05d}.jsonl").open("w", encoding="utf-8") as f:
            for fila in filas:
                f.write(json.dumps(fila, ensure_ascii=False) + "\n")
        hechos += 1
        filas_total += len(filas)
        tiempos.append(round(time.time() - t0, 1))
    return {"crawl": crawl, "ficheros_en_crawl": len(lista), "leidos": hechos, "filas": filas_total,
            "segundos_por_fichero": tiempos}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--crawl")
    p.add_argument("--archivos", default="0:2", help="tramo de ficheros del índice, p. ej. 0:50")
    p.add_argument("--max-minutos", type=float, default=50)
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    d, h = (int(x) for x in a.archivos.split(":"))
    print(json.dumps(ejecutar(Path(a.salida), a.crawl, d, h, a.max_minutos), ensure_ascii=False))


if __name__ == "__main__":
    main()
