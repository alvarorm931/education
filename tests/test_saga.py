"""BOP de Granada y de Sevilla (plataforma SAGA) con sumarios reales del 29/10/2026."""
from pathlib import Path

from motor.provinciales import bopgranada, bopsevilla, saga

F = Path(__file__).parent / "fixtures"


def test_granada():
    b = bopgranada.BOLETIN
    s = saga.parsear_dia(b, (F / "bopgranada_20261029.html").read_text(encoding="utf-8"))
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == ("210", "2026-10-29", 23)
    assert b.url_dia(__import__("datetime").date(2026, 10, 29)) == \
        "https://bop.dipgra.es/publica/consulta-de-bops/buscador/BOP-29-10-2026/"
    sel = saga.seleccionar(b, s["anuncios"])
    assert all(x["ambito"] == "local" and x["convocante"]["provincia"] == "Granada" for x in sel)
    assert {x["convocante"]["nombre"] for x in sel} >= {"Motril", "La Peza", "Granada", "Picena"}
    # Lo de la Junta (delegaciones territoriales) llega por el BOJA
    assert not any("Delegación" in (x["organismo"] or "") for x in sel)
    d = saga.datos_detalle((F / "bopgranada_detalle.html").read_bytes())
    assert d["pdf"].endswith(".pdf") and d["subsección"] == "CONSORCIOS"


def test_sevilla_municipio_sin_tipo():
    b = bopsevilla.BOLETIN
    s = saga.parsear_dia(b, (F / "bopsevilla_20261029.html").read_text(encoding="utf-8"))
    assert len(s["anuncios"]) == 36
    sel = {x["convocante"]["nombre"]: x for x in saga.seleccionar(b, s["anuncios"])}
    assert sel["Paradas"]["convocante"]["tipo"] == "Ayuntamiento"
    assert "Oferta de empleo público" in next(x["titulo"] for x in saga.seleccionar(b, s["anuncios"])
                                              if x["tipo_acto"] == "oferta_empleo")
    # Subvenciones de la Diputación y empresas de vivienda no son empleo público
    assert not any("subvenciones" in x["titulo"] for x in sel.values())
