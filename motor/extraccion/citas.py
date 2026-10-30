"""Citas a otras publicaciones dentro del texto de un anuncio: el boletín, su número y su fecha («bases publicadas en
el Boletín Oficial de la Provincia de Huesca n.º 123, de 2 de julio de 2025», «BOE núm. 162, de 7 de julio de
2026», «BOP n.º 45 de 06/03/2024»). No son datos de personas: se guardan también de las listas, cuyo texto no se
guarda, para poder unir cada lista con su convocatoria (motor/union.py).
"""

from __future__ import annotations

import re
from datetime import date

from motor.boe.clasificar import normalizar
from motor.extraccion.texto_es import MESES

_SIGLAS = (r"B\.?\s?O\.?\s?E\.?|B\.?\s?O\.?\s?P\.?(?:\s?[A-Z]{1,3}\b)?|BOPA|BOPV|BOPB|BOPZ|BOTHA|BOJA|BOCM|BOCYL|BOA|DOE|"
           r"BORM|BOC|BOIB|DOCM|BOME|BON|BOR|DOGV|DOGC|DOG|BOB|BOG|BOCCE|BOPPO|DOCV")
RE_CITA = re.compile(
    rf"(?P<boletin>Bolet[ií]n Oficial (?:de la Provincia|da Provincia|del Estado|de la Comunidad|de la Regi[oó]n|del "
    rf"Principado|del Pa[ií]s|de la Junta|de Castilla|de Arag[oó]n|de Canarias|de Cantabria|de Navarra|de La Rioja|"
    rf"de las Illes|de Bizkaia|de Gipuzkoa|del Territorio)[^,;:()«»\n]{{0,60}}?|Butllet[ií] Oficial[^,;:()«»\n]{{0,60}}?|"
    rf"Diari[oa]? Oficial[^,;:()«»\n]{{0,60}}?|{_SIGLAS})"
    rf"[»\"”]?\s*,?\s*(?:(?:n[úu]m(?:ero)?\.?|n\.?\s?[º°o]\.?|nº|no\.)\s*(?P<numero>\d{{1,4}}))?\s*,?\s*"
    rf"(?:\(|de\s+(?:fecha\s+|data\s+)?|del\s+(?:d[ií]a\s+)?|del\s+|do\s+(?:d[ií]a\s+)?|el\s+d[ií]a\s+|,\s*)?"
    rf"(?P<fecha>\d{{1,2}}\s+(?:de\s+|d'|d’)?[a-záéíóúç]+\s+(?:de\s+|del\s+)?\d{{4}}|\d{{1,2}}[/.-]\d{{1,2}}[/.-]\d{{2,4}})",
    re.IGNORECASE)


def _fecha(texto: str) -> str | None:
    t = normalizar(texto)
    m = re.match(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})$", t)
    try:
        if m:
            a = int(m.group(3))
            return date(a + 2000 if a < 100 else a, int(m.group(2)), int(m.group(1))).isoformat()
        m = re.match(r"(\d{1,2})\s+(?:de\s+|d'|d’)?([a-zç]+)\s+(?:de\s+|del\s+)?(\d{4})$", t)
        if m and MESES.get(m.group(2)):
            return date(int(m.group(3)), MESES[m.group(2)], int(m.group(1))).isoformat()
    except ValueError:
        return None
    return None


def boletin_citado(nombre: str) -> str:
    """Nombre del boletín tal como se cita, recortado («Boletín Oficial de la Provincia de Huesca»); las siglas sin
    puntos («B.O.P.» -> «BOP»)."""
    n = " ".join(nombre.split()).strip(" ,»\"”")
    if len(n) <= 12:
        return re.sub(r"[.\s]", "", n).upper()
    return re.sub(r"\s+(?:n[úu]m|n\.?\s?[º°o]|de fecha|de\s+\d).*$", "", n, flags=re.IGNORECASE).strip()


def citas(texto: str | None, maximo: int = 8) -> list[dict]:
    """Citas a boletines con fecha (las que permiten localizar la publicación citada), sin repetir."""
    out, vistas = [], set()
    for m in RE_CITA.finditer(texto or ""):
        f = _fecha(m.group("fecha"))
        if not f:
            continue
        b = boletin_citado(m.group("boletin"))
        clave = (normalizar(b), f)
        if clave in vistas:
            continue
        vistas.add(clave)
        out.append({"boletin": b, "numero": m.group("numero"), "fecha": f})
        if len(out) >= maximo:
            break
    return out
