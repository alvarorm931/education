"""BOP de Girona: portada, boletín y selección (páginas reales del 28/10/2026 y del 03/01/2022, recortadas)."""

from pathlib import Path

from motor.provinciales import bopgirona as g

FIX = Path(__file__).parent / "fixtures"


def test_portada_y_url():
    assert g.ultimo((FIX / "bopgirona_portada.html").read_bytes()) == (2026, 209)
    assert g.url_boletin(2026, 208).endswith("/bop/mostra-bop/2026-01-01/2026/208")


def test_boletin_2026():
    s = g.parsear_boletin((FIX / "bopgirona_2026_208.html").read_bytes())
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == (208, "2026-10-28", 52)
    a = s["anuncios"][0]
    assert (a["numero_anuncio"], a["entidad"], a["seccion"]) == ("9083", "AJUNTAMENT DE CAMPDEVÀNOL",
                                                                "Administració local - Ajuntaments")
    sel = g.seleccionar([{**x, "id": x["numero_anuncio"]} for x in s["anuncios"]])
    nombres = {x["convocante"]["nombre"] for x in sel}
    assert {"Puigcerdà", "Peralada", "Sils"} <= nombres and "Celrà" not in nombres  # obra de urbanización, no empleo
    assert all(x["convocante"]["provincia"] == "Girona" for x in sel)


def test_boletin_2022():
    s = g.parsear_boletin((FIX / "bopgirona_2022_1.html").read_bytes())
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == (1, "2022-01-03", 18)
    assert {x["seccion"] for x in s["anuncios"]} == {"Administració local - Ajuntaments",
                                                     "Administració local - Consells comarcals",
                                                     "Administració local - Diputació"}


def test_lleida_misma_plataforma():
    from motor.provinciales import boplleida, mostrabop
    c = (FIX / "boplleida_portada_2026_208.html").read_bytes()
    assert mostrabop.ultimo(c) == (2026, 208)  # sin enlace «Últim número»: la cabecera de la portada
    s = mostrabop.parsear_boletin(c)
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == (208, "2026-10-30", 38)
    sel = boplleida.seleccionar([{**x, "id": x["numero_anuncio"]} for x in s["anuncios"]])
    nombres = {x["convocante"]["nombre"] for x in sel}
    assert {"Balaguer", "Tàrrega", "Ponts"} <= nombres  # «AJUNTAMENT DE TÀRREGA (TÀRREGA)»: sin el municipio detrás
    assert all(x["convocante"]["provincia"] == "Lleida" for x in sel)
    assert boplleida.url_boletin(2026, 208) == "https://ebop.diputaciolleida.cat/bop/mostra-bop/2026-01-01/2026/208"
