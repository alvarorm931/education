"""BOP de Pontevedra: boletín del día desde la portada (robots.txt prohíbe fichas, descargas y PDF)."""

from pathlib import Path

from motor.provinciales import boppontevedra as b

FIX = Path(__file__).parent / "fixtures"


def test_portada():
    s = b.parsear_portada((FIX / "boppontevedra_portada_20261029.html").read_bytes())
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == ("209", "2026-10-29", 22)
    sel = b.seleccionar(s["anuncios"])
    assert [(x["convocante"]["nombre"], x["tipo_acto"]) for x in sel] == [("Pontevedra", "admitidos"), ("Tomiño", "admitidos")]
    assert all(x["url_html"].startswith("https://boppo.depo.gal/web/boppo/detalle/-/boppo/2026/10/29/") for x in sel)
