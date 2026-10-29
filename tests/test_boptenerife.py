"""BOP de Santa Cruz de Tenerife con sumarios reales (28/10/2026, 03/01/2022 y un martes sin boletín)."""
from pathlib import Path

from motor.provinciales import boptenerife as t

F = Path(__file__).parent / "fixtures"


def test_sumarios():
    s = t.parsear_dia((F / "boptenerife_20261028.html").read_bytes())
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == ("129", "2026-10-28", 48)
    assert s["url_boletin"] == "http://www.bopsantacruzdetenerife.es/boletines/2026/28-10-26/28-10-26.pdf"
    sel = t.seleccionar(s["anuncios"])
    tipos = {x["tipo_acto"] for x in sel}
    assert {"tribunal", "admitidos", "nombramiento"} <= tipos and "oferta_empleo" not in tipos
    assert any(x["convocante"]["nombre"] == "Tenerife" and x["convocante"]["tipo"] == "Cabildo Insular" for x in sel)
    s = t.parsear_dia((F / "boptenerife_20220103.html").read_bytes())
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == ("1", "2022-01-03", 16)
    s = t.parsear_dia((F / "boptenerife_20261027.html").read_bytes())
    assert (s["numero"], s["fecha"], s["anuncios"]) == (None, "2026-10-27", [])
