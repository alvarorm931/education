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



RE_PALABRA = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñÀÈÒÏÇàèòïç·'’]+")
RE_TRATAMIENTO_ROTO = re.compile(r"(?i)\b(?:d\s?[aª]|m\s?[aª]|d\.?\s?ñ?a|dña|doña|don|sr|sra|d)\b\.?\s+(?:m\s?[aª]\s+)?(?:del?\s+)?[A-ZÁÉÍÓÚÑ]")


def _con_nombre_de_pila(l: str) -> bool:
    """Algún nombre de pila frecuente en la línea, en mayúsculas o no («1 DANIEL APELLIDO»). Más estricto que la
    limpieza de los textos: en una sonda, mejor omitir de más («Virgen del Pilar») que publicar un nombre."""
    from motor.limpieza import _es_pila
    return any(len(w) > 2 and _es_pila(w) for w in RE_PALABRA.findall(l))


def _seguro(texto: str) -> str:
    """Texto para imprimir en una sonda (rama pública): sin líneas con documentos de identidad, con nombres o con
    algún nombre de pila (también partido entre líneas: tras una línea omitida, se omite la siguiente si es corta y
    en mayúsculas o con mayúscula inicial, como el resto de un apellido)."""
    from motor.limpieza import RE_DOCUMENTO, tiene_nombre_de_persona
    out, omitida = [], False
    for l in texto.splitlines():
        palabras = RE_PALABRA.findall(l)
        resto_de_nombre = omitida and 0 < len(palabras) <= 4 and all(w[:1].isupper() for w in palabras)
        principal = bool(RE_DOCUMENTO.search(l) or tiene_nombre_de_persona(l) or _con_nombre_de_pila(l) or
                         RE_TRATAMIENTO_ROTO.search(l))
        if principal or resto_de_nombre:
            out.append("[línea omitida: datos de personas]")
            omitida = principal  # el resto de un nombre ocupa como mucho una línea más
        else:
            out.append(l)
            omitida = False
    return "\n".join(out)


def _pdf(contenido: bytes, paginas: int, modo: str = "plain") -> None:
    from pypdf import PdfReader
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    from motor.pdf import limites_boletin
    with limites_boletin():
        lector = PdfReader(io.BytesIO(contenido))
        print("paginas", len(lector.pages))
        for n in range(min(paginas, len(lector.pages))):
            print(f"----- página {n + 1}")
            texto = lector.pages[n].extract_text(extraction_mode=modo) if modo == "layout" else lector.pages[n].extract_text()
            print(_seguro(texto or "")[:3500])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("--paginas", type=int, default=3)
    p.add_argument("--seguir", action="store_true")
    p.add_argument("--accept", default="application/pdf, text/html, */*")
    p.add_argument("--layout", action="store_true", help="texto con la disposición de la página (pypdf layout)")
    p.add_argument("--salida", default=None)  # la añade prueba.yml; no se guarda nada
    a = p.parse_args(argv)
    r = obtener(a.url, accept=a.accept, intentos=2)
    tipo = r.cabeceras.get("Content-Type") or r.cabeceras.get("content-type")
    print("respuesta", r.status, tipo, len(r.contenido), r.url)
    if r.contenido[:4] == b"%PDF":
        _pdf(r.contenido, a.paginas, "layout" if a.layout else "plain")
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
