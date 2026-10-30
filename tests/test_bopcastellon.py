"""BOP de Castellón: sumario del último boletín y carrusel del buscador (página real del 29/10/2026)."""

from pathlib import Path

from motor.provinciales import bopcastellon as c
from motor.provinciales.sonda_dival import campos_formulario

FIX = Path(__file__).parent / "fixtures"
H = (FIX / "bopcastellon_buscador_20261029.html").read_text(encoding="utf-8")


def test_sumario():
    s = c.parsear_sumario(H)
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == (131, "2026-10-29", 50)
    a = s["anuncios"][1]
    assert (a["numero_anuncio"], a["seccion"], a["grupo"]) == ("168724", "ADMINISTRACIÓN LOCAL",
                                                                  "Diputación Provincial de Castellón")
    assert a["url_pdf"] == "https://bop.dipcas.es/PortalBOP/api/descargarAnuncio?idAnuncio=168724&idioma=es"
    sel = c.seleccionar([{**x, "id": x["numero_anuncio"]} for x in s["anuncios"]])
    assert [x["convocante"]["organismo"] for x in sel] == ["AJUNTAMENT DE BORRIANA/BURRIANA",
                                                            "AJUNTAMENT DE CASTELLÓ DE LA PLANA",
                                                            "AJUNTAMENT DE L'ALCORA"]
    assert {x["convocante"]["provincia"] for x in sel} == {"Castellón"}


def test_carrusel_y_formulario():
    b = c.carrusel(H)
    assert len(b) == 30
    assert b[0] == {"fuente_jsf": "busquedaBoletinesForm:j_idt74:0:j_idt75", "numero": 131, "fecha": "2026-10-29"}
    assert (b[-1]["numero"], b[-1]["fecha"]) == (102, "2026-08-25")
    accion, campos = campos_formulario(H, "busquedaBoletinesForm")
    assert accion.startswith("/PortalBOP/") and campos.get("javax.faces.ViewState")
