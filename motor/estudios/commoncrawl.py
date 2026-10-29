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

# Rutas de programa de posgrado. «master» suelto da mucho ruido (masterclass, Mastercard, MasterChef,
# relojes, cartas...), así que se exige forma de programa: /master/, /masters/, master-en-, master-universitario...
PATRON_RUTA = (r"(?i)(/m[aá]ster(es|s)?(/|[-_](en|de|del|universitari[oa]|oficial|propio|online|executive|in|of|"
               r"profesional|avanzado|internacional)[-_/])|/mba([-_/]|$)|/executive-mba|postgrado|posgrado|"
               r"t[ií]tulos?[-_]propios?|formaci[oó]n[-_]permanente|experto[-_]universitario|especialista[-_]universitario|"
               r"diploma[-_]de[-_]especializaci)")
EXCLUIR = r"(?i)master-?class|mastercard|masterchef|yacht-?master|master-?mind|webmaster|masterpiece|/tag/|/etiqueta/"
CONSULTA = """
SELECT url_host_registered_domain AS dominio, url_host_name AS host,
       count(*) AS paginas,
       array_slice(list(url ORDER BY url), 1, 8) AS ejemplos,
       max(url_host_tld) AS tld,
       max(content_languages) AS idiomas
FROM read_parquet('{fichero}')
WHERE subset = 'warc' AND fetch_status = 200
  AND (url_host_tld = 'es' OR content_languages LIKE 'spa%')
  AND regexp_matches(url_path, '{patron}')
  AND NOT regexp_matches(url_path, '{excluir}')
GROUP BY 1, 2
"""


def ultimo_crawl(n: int = 0) -> str:
    """Identificador del crawl n-ésimo empezando por el más reciente (0)."""
    r = obtener(COLLINFO)
    return json.loads(r.contenido)[n]["id"]


def ficheros(crawl: str) -> list[str]:
    r = obtener(PATHS.format(crawl=crawl))
    lineas = gzip.decompress(r.contenido).decode().splitlines()
    return [DATA + l for l in lineas if "subset=warc" in l]


def consultar(fichero: str) -> list[dict]:
    import duckdb

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; SET http_retries=6; SET http_retry_wait_ms=2000;")
    filas = con.execute(CONSULTA.format(fichero=fichero, patron=PATRON_RUTA.replace("'", "''"),
                                        excluir=EXCLUIR.replace("'", "''"))).fetchall()
    cols = ["dominio", "host", "paginas", "ejemplos", "tld", "idiomas"]
    return [dict(zip(cols, f)) for f in filas]


def consolidar(carpeta: Path) -> list[dict]:
    """Une los ficheros de un crawl por dominio registrado: páginas de programa, hosts y ejemplos."""
    dominios: dict[str, dict] = {}
    for f in sorted(carpeta.glob("*.jsonl")):
        for linea in f.read_text(encoding="utf-8").splitlines():
            x = json.loads(linea)
            d = dominios.setdefault(x["dominio"], {"dominio": x["dominio"], "paginas": 0, "hosts": [], "ejemplos": [],
                                                   "tld": x["tld"], "idiomas": set()})
            d["paginas"] += x["paginas"]
            if x["host"] not in d["hosts"]:
                d["hosts"].append(x["host"])
            d["ejemplos"] = (d["ejemplos"] + list(x.get("ejemplos") or []))[:8]
            d["idiomas"].update((x.get("idiomas") or "").split(","))
    salida = []
    for d in dominios.values():
        d["idiomas"] = sorted(i for i in d["idiomas"] if i)
        salida.append(d)
    return sorted(salida, key=lambda d: -d["paginas"])


def ejecutar(raiz: Path, crawl: str | None, desde: int, hasta: int, max_minutos: float, n: int = 0) -> dict:
    crawl = crawl or ultimo_crawl(n)
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
    dominios = consolidar(destino)
    with (destino.parent / f"dominios_{crawl}_{desde}_{hasta}.jsonl").open("w", encoding="utf-8") as f:
        for d in dominios:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    return {"crawl": crawl, "ficheros_en_crawl": len(lista), "leidos": hechos, "filas": filas_total,
            "dominios": len(dominios), "dominios_es": sum(1 for d in dominios if d["tld"] == "es"),
            "segundos_media": round(sum(tiempos) / max(len(tiempos), 1), 1)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--crawl")
    p.add_argument("--anterior", type=int, default=0, help="0 = último crawl, 1 = el anterior...")
    p.add_argument("--archivos", default="0:2", help="tramo de ficheros del índice, p. ej. 0:50")
    p.add_argument("--max-minutos", type=float, default=50)
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    d, h = (int(x) for x in a.archivos.split(":"))
    print(json.dumps(ejecutar(Path(a.salida), a.crawl, d, h, a.max_minutos, a.anterior), ensure_ascii=False))


if __name__ == "__main__":
    main()
