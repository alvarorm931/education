"""BOP da Coruña (solo títulos: robots.txt prohíbe el texto de cada anuncio)."""

from pathlib import Path

from motor.provinciales import bopcoruna as b

FIX = Path(__file__).parent / "fixtures"


def test_dia_2026():
    s = b.parsear_dia((FIX / "bopcoruna_20261028.html").read_bytes())
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == ("206", "2026-10-28", 28)
    pobra = [x for x in s["anuncios"] if x["numero_anuncio"] == "2026/6932"][0]
    assert pobra["entidad"] == "A Pobra do Caramiñal"
    assert pobra["url_html"] == "https://bop.dacoruna.gal/bopportal/publicado/2026/10/28/2026_0000006932.html"
    sel = b.seleccionar(s["anuncios"])
    assert {x["convocante"]["nombre"] for x in sel} == {"Abegondo", "Ares", "Cabanas", "Carballo", "Coirós", "Culleredo"}


def test_dia_2022():
    s = b.parsear_dia((FIX / "bopcoruna_20220103.html").read_bytes())
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == ("1", "2022-01-03", 9)
    assert [x["tipo_acto"] for x in b.seleccionar(s["anuncios"])] == ["oferta_empleo", "nombramiento", "nombramiento"]
