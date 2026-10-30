"""BOTHA (Álava): boletín bilingüe, versión en castellano y selección (página real del 30/10/2026)."""

from pathlib import Path

from motor.provinciales import bopalava as b

FIX = Path(__file__).parent / "fixtures"


def test_boletin():
    s = b.parsear_dia((FIX / "bopalava_20261030.html").read_bytes())
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == (124, "2026-10-28", 31)
    ult = s["anuncios"][-1]
    assert (ult["entidad"], ult["organo"]) == ("JUNTA ADMINISTRATIVA DE TUESTA", "Concejos")
    assert ult["url_pdf"] == "http://www.araba.eus/botha/Boletines/2026/124/2026_124_03028_C.pdf"
    sel = b.seleccionar([{**x, "id": x["numero_anuncio"]} for x in s["anuncios"]])
    vitoria = [x for x in sel if x["ambito"] == "local"]
    assert [x["convocante"]["nombre"] for x in vitoria] == ["Vitoria-Gasteiz"]
    assert not any("montes de utilidad" in x["titulo"] for x in sel)  # «Junta Administrativa» no es un puesto
