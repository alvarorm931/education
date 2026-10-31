"""Texto de los PDF de los boletines oficiales con pypdf.

Desde pypdf 6 hay límites contra PDF hechos para agotar la memoria o el tiempo. El de trabajo por página (2 millones de
elementos en `stream_parsing_work_maximum_count`) lo pasan páginas reales de boletines con dibujos vectoriales: el BOP
de Las Palmas del 30/10/2026 paraba en «Reached maximum number of tokens per stream», y el corte por boletín entero lo
contaba como error y dejaba sin texto todos sus anuncios sin decir por qué. GitHub instala la última versión de pypdf
en cada ejecución, y en local puede haber una 5 sin esos límites.

Solo para PDF de boletines oficiales (fuentes conocidas): los de webs de centros de estudios siguen con los límites
normales de pypdf.
"""
from __future__ import annotations

import contextlib
import io
import logging
from collections.abc import Iterator

LIMITES_BOLETIN = {
    "stream_parsing_work_maximum_count": 30_000_000,
    "xform_maximum_invocations_per_extraction": 50_000,
}


@contextlib.contextmanager
def limites_boletin() -> Iterator[None]:
    """Límites de pypdf ampliados mientras dura el bloque (sin efecto con pypdf 5, que no los tiene)."""
    try:
        from pypdf import apply_configuration, get_configuration
    except ImportError:
        yield
        return
    actual = get_configuration()
    cambios = {k: v for k, v in LIMITES_BOLETIN.items() if hasattr(actual, k) and getattr(actual, k) < v}
    if not cambios:
        yield
        return
    with apply_configuration(**cambios):
        yield


def paginas(contenido: bytes, layout: bool = False) -> list[str]:
    """Texto de cada página; con layout=True, en el orden de la página (modo «layout» de pypdf)."""
    from pypdf import PdfReader
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    with limites_boletin():
        lector = PdfReader(io.BytesIO(contenido))
        if layout:
            return [p.extract_text(extraction_mode="layout") or "" for p in lector.pages]
        return [p.extract_text() or "" for p in lector.pages]
