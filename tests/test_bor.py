"""Boletín Oficial de La Rioja: listado del buscador, selección, guardado sin repetir y texto (30/10/2026)."""

from pathlib import Path

from motor.autonomicos import bor

FIX = Path(__file__).parent / "fixtures"


def test_listado_y_seleccion(tmp_path):
    filas = bor.parsear_pagina((FIX / "bor_lista_20261030_p1.html").read_text(encoding="utf-8"))
    assert len(filas) == 19 and filas[0]["id"] == "BOR-anu-580514"  # el 20.º es el enlace al boletín del día; and filas[0]["fecha"] == "2026-10-30"
    assert filas[0]["titulo"] == "MÉDICO/A: convocatoria de pruebas selectivas (FA.11/25-26)"
    assert filas[0]["url_html"] == "https://web.larioja.org/bor-portada/boranuncio?n=anu-580514"
    sel = bor.seleccionar(filas)
    assert sel and all(x["ambito"] in {"autonomico", "local", "universidad"} for x in sel)
    assert bor.guardar(tmp_path, filas)[0] == 19 and bor.guardar(tmp_path, filas)[0] == 0  # sin repetir
    assert bor.conocida(tmp_path, filas[5])


def test_convocante_local():
    c = bor.convocante({"organismo": "AYUNTAMIENTO DE CALAHORRA"})
    assert (c["nombre"], c["provincia"]) == ("Calahorra", "La Rioja")
    assert bor.ambito({"organismo": "UNIVERSIDAD DE LA RIOJA"}) == "universidad"


def test_texto():
    t = bor.texto_disposicion((FIX / "bor_anuncio_580530.html").read_bytes())
    assert t["titulo"].startswith("AUXILIAR DE AG: convocatoria pruebas selectivas") and t["seccion"] == "II..1202"
    assert "Cuerpo Auxiliar de Administración General" in t["texto"]
