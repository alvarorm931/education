"""BOP de Toledo: sumario del día y selección (páginas reales del 29/10/2026 y del 03/01/2022)."""

from pathlib import Path

from motor.provinciales import boptoledo as t

FIX = Path(__file__).parent / "fixtures"


def test_sumario_2026():
    s = t.parsear_dia((FIX / "boptoledo_20261029.html").read_bytes())
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == ("208", "2026-10-29", 33)
    a = s["anuncios"][0]
    assert (a["entidad"], a["numero_anuncio"], a["titulo"]) == (
        "AYUNTAMIENTO DE CABAÑAS DE LA SAGRA", "4924", "OFERTA DE EMPLEO PUBLICO 2026")
    sel = t.seleccionar([{**x, "id": x["numero_anuncio"]} for x in s["anuncios"]])
    assert [(x["convocante"]["nombre"], x["tipo_acto"]) for x in sel[:3]] == [
        ("Cabañas de la Sagra", "oferta_empleo"), ("Carranque", "admitidos"), ("Navahermosa", "convocatoria")]
    assert all(x["convocante"]["provincia"] == "Toledo" for x in sel)


def test_sumario_2022():
    s = t.parsear_dia((FIX / "boptoledo_20220103.html").read_bytes())
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == ("1", "2022-01-03", 9)
    assert s["anuncios"][0]["anio_insercion"] == "2021"  # la inserción es del año anterior


def test_dia_sin_boletin():
    assert t.parsear_dia(b"<html><body>No hay boletines</body></html>")["fecha"] is None
