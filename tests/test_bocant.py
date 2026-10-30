"""Boletín Oficial de Cantabria: sumario, extraordinarios, selección y textos del XML (páginas reales del 30/10/2026)."""

from pathlib import Path

from motor.autonomicos import bocant

FIX = Path(__file__).parent / "fixtures"


def _html(nombre):
    return (FIX / nombre).read_bytes().decode("iso-8859-1")


def test_cabeceras():
    assert bocant.cabecera(_html("bocant_sumario_20261029.html")) == (208, "2026-10-29", False)
    assert bocant.cabecera(_html("bocant_sumario_20220103.html")) == (1, "2022-01-03", False)
    assert bocant.cabecera(_html("bocant_extra_20261029.html")) == (29, "2026-10-29", True)
    assert bocant.cabecera(_html("bocant_extra_2022_001.html")) == (1, "2022-01-04", True)
    sin = _html("bocant_sin_boletin_20261025.html")
    assert bocant.cabecera(sin)[0] is None and bocant.RE_SIN_BOLETIN.search(sin)


def test_sumario_y_seleccion():
    filas = bocant.parsear_sumario(_html("bocant_sumario_20261029.html"))
    assert len(filas) == 59 and filas[0]["id"] == "BOC-2026-8422" and filas[0]["organismo"] == "Ayuntamiento de Camargo"
    assert filas[0]["url_pdf"].endswith("verAnuncioAction.do?idAnuBlob=442344")
    sel = {x["id"]: x for x in bocant.seleccionar(filas)}
    assert len(sel) == 23 and "BOC-2026-8430" in sel and "BOC-2026-8410" not in sel  # nombramiento sí; matrimonio no
    assert "BOC-2026-8284" not in sel                                                   # ficha de la RPT
    santander = sel["BOC-2026-8416"]
    assert santander["ambito"] == "local" and santander["convocante"]["nombre"] == "Santander"
    assert santander["convocante"]["provincia"] == "Cantabria" and santander["tipo_acto"] == "convocatoria"
    # Altos cargos en un extraordinario: no son empleo público
    assert bocant.seleccionar(bocant.parsear_sumario(_html("bocant_extra_20261029.html"))) == []


def test_textos_del_xml():
    t = bocant.textos_del_xml((FIX / "bocant_boletin_20261029_recorte.xml").read_bytes())
    assert set(t) == {"BOC-2026-8430", "BOC-2026-8471", "BOC-2026-8415", "BOC-2026-8416", "BOC-2026-8422"}
    assert t["BOC-2026-8416"]["titulo"].startswith("Bases y convocatoria para la cobertura de cuarenta y siete (47)")
    assert "Conductor" in t["BOC-2026-8416"]["texto"]


def test_direcciones():
    from datetime import date

    assert bocant.url_dia(date(2026, 10, 29)).endswith("fecBolString=29/10/2026&boletinBean.tipoBol=0")
    assert bocant.url_extraordinario(29, 2026).endswith("numBolString=29/2026&boletinBean.tipoBol=1")
