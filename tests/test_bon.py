"""Boletín Oficial de Navarra: sumario, selección de empleo público y texto (páginas reales del 30/10/2026)."""

from pathlib import Path

from motor.autonomicos import bon

FIX = Path(__file__).parent / "fixtures"


def _html(nombre):
    return (FIX / nombre).read_text(encoding="utf-8")


def test_cabecera_y_sumario():
    assert bon.cabecera(_html("bon_inicio_2026_218.html")) == (218, "2026-10-30", False)
    assert bon.cabecera(_html("bon_sumario_2026_217.html")) == (217, "2026-10-29", True)
    assert bon.cabecera(_html("bon_sumario_2022_001.html"))[:2] == (1, "2022-01-03")
    assert bon.cabecera(_html("bon_sumario_inexistente.html"))[0] is None
    assert bon.RE_SIN_BOLETIN.search(_html("bon_sumario_inexistente.html"))
    filas = bon.parsear_boletin(_html("bon_inicio_2026_218.html"))
    assert len(filas) == 67 and filas[0]["id"] == "BON-2026-218-000" and filas[-1]["orden"] == 66
    huarte = next(x for x in filas if x["orden"] == 35)
    assert (huarte["entidad"], huarte["seccion"]) == ("HUARTE", "2.1. Oposiciones y concursos. Oferta Pública de Empleo")
    assert len(bon.parsear_boletin(_html("bon_sumario_2022_001.html"))) == 80


def test_seleccion():
    sel = bon.seleccionar(bon.parsear_boletin(_html("bon_inicio_2026_218.html")))
    ordenes = {x["orden"] for x in sel}
    assert {15, 16, 17, 18, 19, 35, 36} <= ordenes          # oposiciones y concursos, autonómico y local
    assert {11, 12, 13} <= ordenes                            # nombramientos de personal funcionario
    assert not ordenes & {0, 1, 20, 25, 33, 37, 40, 49, 59}   # orden foral, alto cargo, ayudas, granja, subasta…
    huarte = next(x for x in sel if x["orden"] == 35)
    assert huarte["ambito"] == "local" and huarte["convocante"]["nombre"] == "Huarte"
    assert huarte["convocante"]["tipo"] == "Ayuntamiento" and huarte["convocante"]["provincia"] == "Navarra"
    assert huarte["tipo_acto"] == "convocatoria"
    assert next(x for x in sel if x["orden"] == 19)["ambito"] == "autonomico"


def test_convocante_entidades():
    c = bon.convocante({"entidad": "CONCEJO DE LARUNBE"})
    assert (c["tipo"], c["nombre"], c["organismo"]) == ("Concejo", "Larunbe", "CONCEJO DE LARUNBE")
    assert bon.convocante({"entidad": "VALLE DE YERRI"})["nombre"] == "Valle de Yerri"
    assert bon.convocante({"entidad": "ESTELLA-LIZARRA"})["nombre"] == "Estella-Lizarra"


def test_texto():
    t = bon.texto_disposicion((FIX / "bon_anuncio_2026_218_35.html").read_bytes())
    assert t["titulo"] == "Concurso-oposición de dos plazas de animador/a en régimen laboral fijo"
    assert "dos plazas a jornada parcial" in t["texto"] and t["codigo_anuncio"]
