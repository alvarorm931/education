"""BOP de Burgos: boletín por número y selección (página real del 29/10/2026)."""

from pathlib import Path

from motor.provinciales import bopburgos as b

FIX = Path(__file__).parent / "fixtures"


def test_boletin():
    h = (FIX / "bopburgos_2026_206.html").read_text(encoding="utf-8")
    assert b.cabecera(h) == (206, "2026-10-29")
    filas = b.parsear_boletin(h)
    assert len(filas) == 27 and filas[0]["entidad"] == "Ayuntamiento de Aranda de Duero"
    assert filas[0]["url_pdf"].endswith("bopbur-2026-206-anuncio-202604581.pdf")
    sel = b.seleccionar([{**x, "id": x["numero_anuncio"]} for x in filas])
    hontoria = sel[0]
    assert (hontoria["convocante"]["nombre"], hontoria["convocante"]["provincia"], hontoria["tipo_acto"]) == (
        "Hontoria del Pinar", "Burgos", "convocatoria")
    assert b.url_boletin(2022, 1) == "http://bopbur.diputaciondeburgos.es/bopbur-2022-001"
