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


def textos_pdf_pendientes(base, campo: str = "url_pdf") -> list[dict]:
    """Anuncios de empleo guardados (oposiciones/AAAA/MM/*.jsonl bajo base) con PDF y sin texto todavía; primero los
    que tienen texto útil y los de acceso."""
    from motor.autonomicos.comun import leer_jsonl
    lista = []
    for f in sorted((base / "oposiciones").glob("*/*/*.jsonl"), reverse=True):
        lista += [x for x in leer_jsonl(f) if x.get(campo) and not ruta_texto_pdf(base, x).exists()]
    return sorted(lista, key=lambda x: (0 if x.get("tipo_acto") in CON_TEXTO else 1,
                                        0 if x.get("alcance") in (None, "acceso") else 1))


def ruta_texto_pdf(base, x: dict):
    return base / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id'].replace('/', '-')}.json"


def descargar_textos_pdf(base, fuente: str, archivo, max_minutos: float, pausa: float,
                         cabeceras: re.Pattern | None = None, campo: str = "url_pdf",
                         accept: str = "application/pdf") -> tuple[int, int, int]:
    """Descarga y limpia el PDF de cada anuncio de empleo pendiente. Devuelve (hechos, errores, pendientes)."""
    from motor.autonomicos.comun import descargar_textos
    pend = textos_pdf_pendientes(base, campo)
    hechos, errores = descargar_textos(
        pend, lambda x: ruta_texto_pdf(base, x), lambda x: x[campo],
        lambda c, x: {"titulo": x.get("titulo"), **{k: v for k, v in texto_pdf(c, x.get("tipo_acto") in CON_TEXTO,
                                                                                cabeceras).items() if k != "titulo"}},
        archivo, fuente, max_minutos, pausa, accept=accept, ext="pdf", por_registro=True)
    return hechos, errores, len(pend) - hechos
