"""Piezas comunes de los conectores de boletines provinciales.

  - texto de un anuncio en PDF, limpio de cabeceras repetidas y de datos de personas;
  - de las listas de personas (admitidos, aprobados, nombramientos, tribunales) solo el recuento;
  - qué tipos de acto merecen guardar su texto.
"""

from __future__ import annotations

import io
import re

from motor.limpieza import RE_DOCUMENTO, limpiar_texto

# Tipos de acto con texto útil (plazo, plazas, requisitos); los demás traen listas de personas
CON_TEXTO = {"convocatoria", "bases", "modificacion", "correccion", "anulacion", "oferta_empleo", "otro"}


def texto_pdf(contenido: bytes, con_texto: bool = True, cabeceras: re.Pattern | None = None) -> dict:
    """Texto limpio de un anuncio en PDF. Con con_texto=False (listas de personas) solo se cuenta cuántas líneas
    traen un documento de identidad y no se guarda el texto."""
    from pypdf import PdfReader
    if contenido[:4] != b"%PDF":
        raise ValueError("no es un PDF")
    bruto = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(contenido)).pages)
    if not con_texto:
        return {"titulo": None, "texto": None, "tablas": [], "solo_recuento": True,
                "lineas_con_documento_de_identidad": sum(1 for l in bruto.splitlines() if RE_DOCUMENTO.search(l))}
    return {"titulo": None, **limpiar_texto(bruto, cabeceras)}
