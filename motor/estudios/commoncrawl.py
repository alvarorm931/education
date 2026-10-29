"""Descubrimiento de centros con oferta de posgrado en el índice de Common Crawl.

Common Crawl publica cada mes un índice en columnas (Parquet) de todas las páginas rastreadas, con dominio,
TLD, ruta e idioma. Filtrando las rutas que parecen programas de posgrado en páginas españolas (TLD .es o
idioma español) sale la lista de dominios que venden másters, sean o no universidades. Solo se leen
metadatos de URL: no se descarga ni se reproduce contenido de terceros.

Lectura directa por HTTPS con DuckDB, archivo a archivo, para poder repartirla en tramos.

Segundo uso: todas las URL de programa de unos dominios concretos (las webs de universidades y centros
oficiales), para unir cada máster oficial con su página aunque el rastreo de la web no llegue a todas.

Uso:
  python -m motor.estudios.commoncrawl --archivos 0:4 --salida ruta/
  python -m motor.estudios.commoncrawl --crawl CC-MAIN-2026-40 --archivos 0:300 --salida ruta/
  python -m motor.estudios.commoncrawl --urls-de censo/proveedores.jsonl --estados oficial --archivos 0:150 --salida ruta/
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import time
from pathlib import Path

from motor.http import obtener

COLLINFO = "https://index.commoncrawl.org/collinfo.json"
PATHS = "https://data.commoncrawl.org/crawl-data/{crawl}/cc-index-table.paths.gz"
DATA = "https://data.commoncrawl.org/"

# Descubrimiento amplio: basta con que el dominio tenga ALGUNA URL (ruta o parámetros) que hable de másters o
# posgrado, en cualquiera de las lenguas de España o en inglés. Common Crawl solo guarda una muestra de cada
# sitio, así que exigir la ficha del programa deja fuera a centros reales (medido el 29/10/2026: 15 de 18
# centros conocidos encontrados, 6 de 17 centros extranjeros autorizados). Quién vende de verdad lo decide
# después el rastreador en la web de cada dominio, que lee su sitemap completo.
PATRON_RUTA = (r"(?i)(m[aàá]ster|m%c3%a[01]ster|\bmba\b|\bmsc\b|\bllm\b|postgrad|posgrad|postgrau|t[ií]tulos?[-_ ]?propios?|"
               r"estudis[-_]propis|formaci[oó]n?[-_ ]?(permanente|continua)|formacio[-_]continua|experto[-_]universitario|"
               r"especialista[-_]universitario|executive[-_]education|masterra|mestrado)")
EXCLUIR = (r"(?i)master-?class|mastercard|masterchef|yacht-?master|master-?mind|webmaster|masterpiece|"
           r"masters?-of-the-universe|/(src|tree|blob|branch|-)/master|/master/(src|tree|blob|raw)/|renault|nissan|opel|movano|ducato|"
           r"master-?key|grand-?master|masterbuilt|mastercook|master-?system|paymaster|toastmaster")
LENGUAS = ("spa", "cat", "eus", "glg")
CONSULTA = """
SELECT url_host_registered_domain AS dominio, url_host_name AS host,
       count(*) AS paginas,
       array_slice(list(url ORDER BY url), 1, 8) AS ejemplos,
       max(url_host_tld) AS tld,
       string_agg(DISTINCT coalesce(content_languages, '-'), ',') AS idiomas
FROM read_parquet('{fichero}')
WHERE subset = 'warc'
  AND (url_host_tld = 'es' OR content_languages IS NULL
       OR regexp_matches(content_languages, '^(spa|cat|eus|glg)'))
  AND regexp_matches(coalesce(url_path, '') || '?' || coalesce(url_query, ''), '{patron}')
  AND NOT regexp_matches(coalesce(url_path, '') || '?' || coalesce(url_query, ''), '{excluir}')
GROUP BY 1, 2
"""


CONSULTA_URLS = """
SELECT url_host_registered_domain AS dominio, url
FROM read_parquet('{fichero}')
WHERE subset = 'warc' AND fetch_status = 200
  AND url_host_registered_domain IN ({dominios})
  AND regexp_matches(coalesce(url_path, '') || '?' || coalesce(url_query, ''), '{patron}')
  AND NOT regexp_matches(coalesce(url_path, '') || '?' || coalesce(url_query, ''), '{excluir}')
"""


def dominios_de_censo(fichero: Path, estados: tuple[str, ...]) -> list[str]:
    filas = [json.loads(l) for l in fichero.read_text(encoding="utf-8").splitlines() if l.strip()]
    return sorted({d for p in filas if p["estado"] in estados for d in p["dominios"]})


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


def consultar_urls(fichero: str, dominios: list[str]) -> list[dict]:
    import duckdb

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; SET http_retries=6; SET http_retry_wait_ms=2000;")
    lista = ",".join("'" + d.replace("'", "") + "'" for d in dominios)
    filas = con.execute(CONSULTA_URLS.format(fichero=fichero, dominios=lista, patron=PATRON_RUTA.replace("'", "''"),
                                             excluir=EXCLUIR.replace("'", "''"))).fetchall()
    return [{"dominio": d, "url": u} for d, u in filas]


def consolidar_urls(carpeta: Path) -> list[dict]:
    por_dom: dict[str, set] = {}
    for f in sorted(carpeta.glob("*.urls.jsonl")):
        for linea in f.read_text(encoding="utf-8").splitlines():
            x = json.loads(linea)
            por_dom.setdefault(x["dominio"], set()).add(x["url"])
    return [{"dominio": d, "urls": sorted(u)} for d, u in sorted(por_dom.items())]


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


def ejecutar(raiz: Path, crawl: str | None, desde: int, hasta: int, max_minutos: float, n: int = 0,
             solo: list[int] | None = None, urls_de: list[str] | None = None) -> dict:
    crawl = crawl or ultimo_crawl(n)
    lista = ficheros(crawl)
    destino = raiz / "datos" / "estudios" / "commoncrawl" / (crawl + ("-urls" if urls_de else ""))
    destino.mkdir(parents=True, exist_ok=True)
    fin = time.time() + max_minutos * 60
    hechos, filas_total, tiempos = 0, 0, []
    indices = solo if solo is not None else range(desde, min(hasta, len(lista)))
    for i in indices:
        if time.time() > fin:
            break
        t0 = time.time()
        filas, error = None, None
        for intento in range(6):  # 403/503 de CloudFront = «más despacio»: espera creciente y reintento
            try:
                filas = consultar_urls(lista[i], urls_de) if urls_de else consultar(lista[i])
                break
            except Exception as e:
                error = str(e)
                if not re.search(r"\b(403|429|503)\b", error) or time.time() + 60 * (intento + 1) > fin:
                    break
                time.sleep(60 * (intento + 1))
        if filas is None:
            (destino / f"{i:05d}.error.txt").write_text(f"{lista[i]}\n{error}", encoding="utf-8")
            continue
        with (destino / f"{i:05d}{'.urls' if urls_de else ''}.jsonl").open("w", encoding="utf-8") as f:
            for fila in filas:
                f.write(json.dumps(fila, ensure_ascii=False) + "\n")
        hechos += 1
        filas_total += len(filas)
        tiempos.append(round(time.time() - t0, 1))
    if urls_de:
        por_dom = consolidar_urls(destino)
        with (destino.parent / f"urls_{crawl}_{desde}_{hasta}.jsonl").open("w", encoding="utf-8") as f:
            for d in por_dom:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        return {"crawl": crawl, "modo": "urls", "dominios_pedidos": len(urls_de), "leidos": hechos,
                "urls": filas_total, "dominios_con_urls": len(por_dom),
                "segundos_media": round(sum(tiempos) / max(len(tiempos), 1), 1)}
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
    p.add_argument("--indices", help="solo estos ficheros (p. ej. los que fallaron): 3,7,9")
    p.add_argument("--urls-de", help="proveedores.jsonl del censo: todas las URL de programa de sus dominios")
    p.add_argument("--estados", default="oficial", help="estados del censo para --urls-de")
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    d, h = (int(x) for x in a.archivos.split(":"))
    doms = dominios_de_censo(Path(a.urls_de), tuple(a.estados.split(","))) if a.urls_de else None
    print(json.dumps(ejecutar(Path(a.salida), a.crawl, d, h, a.max_minutos, a.anterior,
                                [int(x) for x in a.indices.split(",")] if a.indices else None, doms), ensure_ascii=False))


if __name__ == "__main__":
    main()
