"""BOB (Bizkaia): portada, boletín, vecinos y selección (páginas reales del 03/01/2022 y del 29/10/2026, recortadas)."""

from pathlib import Path

from motor.provinciales import bopbizkaia as b

FIX = Path(__file__).parent / "fixtures"


def test_portada():
    assert b.ultimo((FIX / "bopbizkaia_portada.html").read_bytes()) == {"fecha": "2026-10-29", "numero": 208}


def test_url():
    u = b.url_boletin("2026-10-29", 208)
    assert u.endswith("_IYBIWBCC_bdate=20261029&_IYBIWBCC_bnum=208") and "%2Fdetail" in u


def test_boletin_2026():
    s = b.parsear_boletin((FIX / "bopbizkaia_20261029.html").read_bytes())
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == (208, "2026-10-29", 26)
    assert s["anterior"] == {"numero": 207, "fecha": "2026-10-28"} and s["siguiente"] is None
    a = s["anuncios"][1]  # sin h4 propio: el emisor es el del anuncio anterior
    assert (a["entidad"], a["numero_anuncio"]) == ("Departamento de Administración Pública y Relaciones Institucionales",
                                                   "2026-I-1213")
    sel = b.seleccionar([{**x, "id": x["numero_anuncio"]} for x in s["anuncios"]])
    assert not any("aptitud profesional" in x["titulo"] for x in sel)  # el CAP de conductores no es empleo público
    loc = [x for x in sel if x["ambito"] == "local"]
    assert loc and all(x["convocante"]["nombre"] == "Valle de Trápaga-Trapagaran" for x in loc)
    assert all(x["convocante"]["provincia"] == "Bizkaia" for x in loc)


def test_boletin_2022():
    s = b.parsear_boletin((FIX / "bopbizkaia_20220103.html").read_bytes())
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == (1, "2022-01-03", 22)
    assert s["anterior"] == {"numero": 251, "fecha": "2021-12-31"}
    assert s["siguiente"] == {"numero": 2, "fecha": "2022-01-04"}
    sel = b.seleccionar([{**x, "id": x["numero_anuncio"]} for x in s["anuncios"]])
    assert sel[0]["tipo_acto"] == "admitidos"  # «listas de admisiones, exclusiones y desistimientos»


def test_pagina_vacia():
    s = b.parsear_boletin(b"<html><body>sin resultados</body></html>")
    assert s["numero"] is None and s["anuncios"] == []
