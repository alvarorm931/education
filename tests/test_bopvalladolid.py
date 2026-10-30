"""BOP de Valladolid: boletín por fecha y calendario (páginas reales del 29 y 30/10/2026, recortadas; enero de 2022)."""

import json
from datetime import date
from pathlib import Path

from motor.provinciales import bopvalladolid as v

FIX = Path(__file__).parent / "fixtures"


def test_url_dia():
    assert v.url_dia(date(2026, 10, 29)).endswith("_BOPVisualizaBoletin_WAR_BOPVisualizaBoletin_fecha=2026-10-29")


def test_boletin():
    s = v.parsear_boletin((FIX / "bopvalladolid_20261029.html").read_bytes())
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == ("2026/208", "2026-10-29", 9)
    a = s["anuncios"][-1]
    assert (a["numero_anuncio"], a["entidad"], a["seccion"]) == (
        "BOPVA-A-2026-03144", "AYUNTAMIENTO DE SIETE IGLESIAS DE TRABANCOS", "III.-ADMINISTRACIÓN LOCAL")
    sel = v.seleccionar([{**x, "id": x["numero_anuncio"]} for x in s["anuncios"]])
    assert ("Siete Iglesias de Trabancos", "admitidos") in [(x["convocante"]["nombre"], x["tipo_acto"]) for x in sel]
    assert all(x["convocante"]["provincia"] == "Valladolid" for x in sel)


def test_otro_dia_y_calendario(tmp_path):
    s = v.parsear_boletin((FIX / "bopvalladolid_20261030.html").read_bytes())
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == ("2026/209", "2026-10-30", 15)
    fechas = json.loads((FIX / "bopvalladolid_calendario_202201.json").read_text())
    assert "2022-01-03" in fechas and "2022-01-06" not in fechas  # Reyes


def test_pagina_sin_boletin():
    assert v.parsear_boletin(b"<html><body>error</body></html>")["fecha"] is None
