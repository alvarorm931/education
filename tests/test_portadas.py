"""BOP de Salamanca y de Albacete: el boletín del día desde su portada (páginas reales del 28 y 30/10/2026)."""

from pathlib import Path

from motor.provinciales import bopalbacete, bopsalamanca

FIX = Path(__file__).parent / "fixtures"


def _sel(m, r):
    return m.seleccionar([{**x, "id": x["numero_anuncio"]} for x in r["anuncios"]])


def test_salamanca():
    r = bopsalamanca.leer((FIX / "bopsalamanca_portada_20261030.html").read_bytes())
    assert (r["fecha"], len(r["anuncios"])) == ("2026-10-30", 13)
    a = r["anuncios"][1]
    assert (a["seccion"], a["grupo"], a["entidad"]) == ("IV. ADMINISTRACIÓN LOCAL", "Ayuntamientos", "Calvarrasa de Abajo")
    sel = _sel(bopsalamanca, r)
    assert [(x["convocante"]["nombre"], x["tipo_acto"]) for x in sel] == [("Monterrubio de la Armuña", "nombramiento")]
    # La formación para desempleados (certificado de profesionalidad, BDNS) no es empleo público


def test_albacete():
    r = bopalbacete.leer((FIX / "bopalbacete_portada_20261028.html").read_bytes())
    assert (r["numero"], r["fecha"], len(r["anuncios"])) == ("126", "2026-10-28", 16)
    sel = _sel(bopalbacete, r)
    assert [(x["convocante"]["nombre"], x["convocante"]["provincia"]) for x in sel] == [
        ("Ossa de Montiel", "Albacete"), ("Villamalea", "Albacete")]


def test_jaen():
    from motor.provinciales import bopjaen

    r = bopjaen.leer((FIX / "bopjaen_portada_20261030.html").read_bytes())
    assert (r["numero"], r["fecha"], len(r["anuncios"])) == ("213", "2026-10-30", 19)
    sel = _sel(bopjaen, r)
    assert sel[0]["convocante"]["nombre"] == "Alcaudete" and sel[0]["tipo_acto"] == "admitidos"
    assert {x["convocante"]["nombre"] for x in sel} == {"Alcaudete", "Canena", "Jaén", "Vilches"}


def test_zaragoza():
    from motor.provinciales import bopzaragoza

    r = bopzaragoza.leer((FIX / "bopzaragoza_portada_20261030.html").read_bytes())
    assert (r["numero"], r["fecha"], len(r["anuncios"])) == ("251", "2026-10-30", 55)
    sel = _sel(bopzaragoza, r)
    assert all(x["ambito"] == "local" for x in sel)  # secciones tercera, quinta y sexta
    assert sel[0]["convocante"]["tipo"] == "Diputación Provincial" and sel[0]["tipo_acto"] == "convocatoria"
    assert {x["convocante"]["nombre"] for x in sel} >= {"Zaragoza", "Cuarte de Huerva", "Zuera"}
