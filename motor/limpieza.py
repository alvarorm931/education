"""Limpieza de textos oficiales: se conserva el contenido y se retiran los datos de personas.

Reglas (las mismas para todas las fuentes):
  - tabla con cabecera de datos personales (DNI, NIF, apellidos, nombre...) o con dos o más documentos
    de identidad: se guarda solo el número de filas y la cabecera;
  - párrafo con un documento de identidad: se cuenta y no se guarda;
  - el resto del texto se guarda íntegro.
"""

from __future__ import annotations

import html
import re

RE_DOCUMENTO = re.compile(
    r"(\b\d{8}\s?[A-Z]\b|\b[XYZ]\d{7}\s?[A-Z]\b|\*{2,}\d{3,5}\*{1,}|\b\d{3,4}\*{3,}|\*{3,}\d{4}[A-Z]?\b|\bX{3,}\d{3,}X*)"
)
CABECERA_PERSONAL = re.compile(r"\b(dni|nif|nie|apellidos|nombre|documento|pasaporte)\b", re.IGNORECASE)
RE_BLOQUE = re.compile(r"<table\b.*?</table>|<(p|li|h\d)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
RE_FILA = re.compile(r"<tr\b.*?</tr>", re.IGNORECASE | re.DOTALL)
RE_CELDA = re.compile(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)
RE_ETIQUETA = re.compile(r"<[^>]+>")


def texto_de(fragmento: str) -> str:
    return " ".join(html.unescape(RE_ETIQUETA.sub(" ", fragmento)).replace("\xa0", " ").split())


def tabla(filas: list[list[str]]) -> dict:
    filas = [f for f in filas if any(f)]
    cabecera = filas[0] if filas else []
    contenido = " ".join(" ".join(f) for f in filas)
    if CABECERA_PERSONAL.search(" ".join(cabecera)) or len(RE_DOCUMENTO.findall(contenido)) >= 2:
        return {"filas": max(len(filas) - 1, 0), "cabecera": cabecera, "datos_personales": True}
    return {"filas": len(filas), "contenido": filas, "datos_personales": False}


def parrafos_seguros(parrafos: list[str]) -> tuple[list[str], int]:
    guardados, omitidos = [], 0
    for p in parrafos:
        if not p:
            continue
        if RE_DOCUMENTO.search(p):
            omitidos += 1
        else:
            guardados.append(p)
    return guardados, omitidos


def limpiar_html(fragmento_html: str) -> dict:
    """Texto, tablas y recuento de omisiones a partir de HTML de un boletín."""
    parrafos, tablas = [], []
    for m in RE_BLOQUE.finditer(fragmento_html or ""):
        bloque = m.group(0)
        if bloque[:6].lower() == "<table":
            filas = [[texto_de(c) for c in RE_CELDA.findall(f)] for f in RE_FILA.findall(bloque)]
            tablas.append(tabla(filas))
        else:
            parrafos.append(texto_de(bloque))
    guardados, omitidos = parrafos_seguros(parrafos)
    return {"texto": "\n".join(guardados), "tablas": tablas, "parrafos_omitidos_por_datos_personales": omitidos}
