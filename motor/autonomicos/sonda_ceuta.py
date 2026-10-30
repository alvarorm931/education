"""Sonda del BOCCE (Ceuta, solo responde desde España): boletines de un mes en jDownloads y texto de las primeras
páginas del PDF de uno (el sumario). Imprime el texto (que se anonimiza al subir); no guarda el PDF.

Uso: python -m motor.autonomicos.sonda_ceuta [CATEGORIA_MES]   (p. ej. 1982-octubre)
"""

from __future__ import annotations

import html
import io
import logging
import re
import sys
import time

import requests

from motor.http import USER_AGENT, comprobar_robots

BASE = "https://www.ceuta.es"



def _seguro(texto: str) -> str:
    """Texto para imprimir en una sonda (rama pública): sin líneas con documentos de identidad ni con nombres."""
    from motor.limpieza import RE_DOCUMENTO, tiene_nombre_de_persona
    return "\n".join("[línea omitida: datos de personas]" if RE_DOCUMENTO.search(l) or tiene_nombre_de_persona(l) else l
                     for l in texto.splitlines())


def main(argv: list[str] | None = None) -> int:
    cat = ((argv if argv is not None else sys.argv[1:]) or ["1982-octubre"])[0]
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    url = f"{BASE}/ceuta/component/jdownloads/viewcategory/{cat}?Itemid=534"
    comprobar_robots(url, s)
    r = s.get(url, timeout=60)
    h = r.text
    items = sorted(set(re.findall(r'href="(/ceuta/component/jdownloads/viewdownload/[^"?]+)', h)))
    print("mes", cat, r.status_code, len(r.content), "boletines:", len(items))
    for u in items[:40]:
        print("  ", u)
    print("paginacion:", sorted(set(re.findall(r'(limitstart=\d+|start=\d+)', h)))[:10])
    fin = [u.replace("/viewdownload/", "/finish/") for u in items if "bocce" in u.lower()]
    if not fin:
        return 0
    time.sleep(1)
    p = s.get(BASE + fin[0] + "?Itemid=0", timeout=120)
    print("pdf", fin[0], p.status_code, p.headers.get("content-type"), len(p.content), p.content[:5])
    if p.content[:4] == b"%PDF":
        from pypdf import PdfReader
        logging.getLogger("pypdf").setLevel(logging.ERROR)
        lector = PdfReader(io.BytesIO(p.content))
        print("paginas", len(lector.pages))
        for n in range(min(3, len(lector.pages))):
            print(f"----- página {n + 1}")
            print(_seguro(lector.pages[n].extract_text() or "")[:3000])
    else:
        print(html.unescape(p.text[:500]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
