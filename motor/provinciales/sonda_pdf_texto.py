"""Sonda del texto de un boletín en PDF (para diseñar un conector): pide la URL con el cliente del motor (robots.txt,
identificación, reintentos) y, si es un PDF, imprime el texto de sus primeras páginas; si es HTML, sus enlaces a PDF
y, con --seguir, abre el primero. Lo impreso se anonimiza al subir (prueba.yml); el PDF no se guarda.

Uso (con prueba.yml): python -m motor.provinciales.sonda_pdf_texto URL [--paginas 3] [--seguir]
"""

from __future__ import annotations

import argparse
import html
import io
import logging
import re
import sys
from urllib.parse import urljoin

from motor.http import obtener


def _pdf(contenido: bytes, paginas: int) -> None:
    from pypdf import PdfReader
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    lector = PdfReader(io.BytesIO(contenido))
    print("paginas", len(lector.pages))
    for n in range(min(paginas, len(lector.pages))):
        print(f"----- página {n + 1}")
        print((lector.pages[n].extract_text() or "")[:3500])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("--paginas", type=int, default=3)
    p.add_argument("--seguir", action="store_true")
    a = p.parse_args(argv)
    r = obtener(a.url, accept="application/pdf, text/html, */*", intentos=2)
    tipo = r.cabeceras.get("Content-Type") or r.cabeceras.get("content-type")
    print("respuesta", r.status, tipo, len(r.contenido), r.url)
    if r.contenido[:4] == b"%PDF":
        _pdf(r.contenido, a.paginas)
        return 0
    h = r.contenido.decode("utf-8", errors="replace")
    enlaces = sorted(set(re.findall(r'(?:href|src|url)\s*=\s*["\']?([^"\'\s>]+\.pdf[^"\'\s>]*)', h, re.IGNORECASE)))
    print("enlaces a PDF:", len(enlaces))
    for u in enlaces[:30]:
        print("  ", html.unescape(u))
    refresco = re.search(r'http-equiv=["\']?refresh["\']?[^>]*url=([^"\'>]+)', h, re.IGNORECASE)
    if refresco:
        print("refresh:", html.unescape(refresco.group(1)))
    print("texto:", " ".join(html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>", " ", h, flags=re.S))).split())[:1500])
    destino = enlaces[0] if enlaces else (refresco.group(1) if refresco else None)
    if a.seguir and destino:
        u = urljoin(r.url or a.url, html.unescape(destino))
        r2 = obtener(u, accept="application/pdf, */*", intentos=2)
        print("sigo", u, r2.status, len(r2.contenido))
        if r2.contenido[:4] == b"%PDF":
            _pdf(r2.contenido, a.paginas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
