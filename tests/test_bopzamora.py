"""BOP de Zamora: últimos boletines de la portada e índice de un boletín (páginas reales del 30/10/2026)."""

from pathlib import Path

from motor.provinciales import bopzamora as z

FIX = Path(__file__).parent / "fixtures"


def test_portada():
    bs = z.boletines_portada((FIX / "bopzamora_portada_20261030.html").read_text(encoding="utf-8"))
    assert [(b["numero"], b["fecha"], b["extraordinario"]) for b in (bs[0], bs[-1])] == [
        (127, "2026-10-28", False), (120, "2026-10-13", True)]
    assert len(bs) == 8


def test_indice():
    filas = z.parsear_indice((FIX / "bopzamora_indice_127_2026.html").read_text(encoding="utf-8"))
    assert len(filas) == 19 and filas[0]["numero_anuncio"] == "202602455"
    assert filas[0]["url_pdf"].endswith("/anuncios/2026/127/202602455.pdf")
    local = next(x for x in filas if x["organismo"] == "Ayuntamiento de Benavente")
    assert local["seccion"] == "III. ADMINISTRACIÓN LOCAL" and local["procedencia"] == "AYUNTAMIENTOS"
    assert z.convocante(local)["nombre"] == "Benavente"
    fila = {"titulo": "Bases para la provisión de una plaza de auxiliar administrativo", "seccion": local["seccion"],
            "organismo": "Ayuntamiento de Toro", "procedencia": "AYUNTAMIENTOS", "id": "x"}
    sel = z.seleccionar([fila])
    assert sel[0]["convocante"]["nombre"] == "Toro" and sel[0]["convocante"]["provincia"] == "Zamora"
