"""BOME (Melilla) con respuestas reales: calendario de octubre de 2026, un ordinario, un extraordinario y un artículo."""

import json
from pathlib import Path

from motor.autonomicos import bome

FIX = Path(__file__).parent / "fixtures"


def test_calendario():
    cal = bome.calendario((FIX / "bome_calendario_202610.json").read_bytes())
    assert cal[0] == {"id": "BOME-B-2026-6419", "fecha": "2026-10-02", "numero": "6419", "tipo": "ordinario"}
    assert any(b["tipo"] == "extraordinario" and b["id"] == "BOME-BX-2026-44" for b in cal)


def test_boletines_y_seleccion():
    b = {"id": "BOME-B-2026-6420", "fecha": "2026-10-06", "numero": "6420", "tipo": "ordinario"}
    filas = bome.parsear_boletin((FIX / "bome_6420.html").read_text(encoding="utf-8"), b)
    assert len(filas) == 7 and filas[0]["url_html"] == "https://bomemelilla.es/bome/BOME-B-2026-6420/articulo/1114"
    bx = {"id": "BOME-BX-2026-44", "fecha": "2026-10-07", "numero": "44", "tipo": "extraordinario"}
    filas = bome.parsear_boletin((FIX / "bome_BX_44.html").read_text(encoding="utf-8"), bx)
    assert filas and filas[0]["id"].startswith("BOME-AX-2026-")
    emp = bome.seleccionar(filas)
    assert any("Oficial Mecánico Conductor" in e["titulo"] and e["tipo_acto"] == "admitidos" for e in emp)
    assert all(e["convocante"]["nombre"] == "Melilla" for e in emp)


def test_texto_articulo():
    t = bome.texto_disposicion((FIX / "bome_articulo_6341_2.html").read_bytes())
    assert t["texto"].startswith("Esta Consejería, por acuerdo del órgano competente")
