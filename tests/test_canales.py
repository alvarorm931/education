"""BOP de Ávila y de Badajoz por su canal (RSS y Atom reales del 29 y 30/10/2026)."""

from pathlib import Path

from motor.provinciales import bopavila, bopbadajoz

FIX = Path(__file__).parent / "fixtures"


def _filas(m, s):
    return [{**x, "id": x["numero_anuncio"]} for x in s["anuncios"]]


def test_avila():
    s = bopavila.leer((FIX / "bopavila_rss_20261029.xml").read_text(encoding="utf-8"))
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == ("210", "2026-10-29", 9)
    a = s["anuncios"][0]
    assert (a["entidad"], a["numero_anuncio"]) == ("AYUNTAMIENTO DE VELAYOS", "2101/26")
    assert a["url_pdf"].endswith("29-10-2026_210126.pdf")
    assert bopavila.seleccionar(_filas(bopavila, s)) == []  # ese día no hubo anuncios de empleo


def test_badajoz():
    s = bopbadajoz.leer((FIX / "bopbadajoz_atom_20261030.xml").read_text(encoding="utf-8"))
    assert (s["fecha"], len(s["anuncios"])) == ("2026-10-30", 9)
    sel = bopbadajoz.seleccionar(_filas(bopbadajoz, s))
    assert [(x["convocante"]["nombre"], x["tipo_acto"]) for x in sel] == [
        ("Ahillones", "admitidos"), ("Puebla de la Calzada", "correccion"), ("Talarrubias", "convocatoria")]
    assert sel[0]["convocante"]["organismo"] == "Ahillones" and sel[0]["convocante"]["provincia"] == "Badajoz"


def test_badajoz_texto():
    t = bopbadajoz.texto_disposicion((FIX / "bopbadajoz_anuncio_165039.html").read_bytes())
    assert t["titulo"].startswith("Lista definitiva de aspirantes admitidos de la convocatoria de una plaza de Encargado")
    assert "decreto de Alcaldía número 171/2026" in t["texto"]


def test_lugo():
    from motor.provinciales import boplugo
    s = boplugo.leer((FIX / "boplugo_rss_20261029.xml").read_text(encoding="utf-8"))
    assert (s["fecha"], s["numero"], len(s["anuncios"])) == ("2026-10-29", "248", 11)
    a = s["anuncios"][4]
    assert (a["entidad"], a["numero_anuncio"], a["pagina"]) == ("CONCELLO DE MONFORTE DE LEMOS", "2026-2962", 5)
    assert a["titulo"] == "APROBACIÓN PROVISIONAL DA MODIFICACIÓN DAS ORDENANZAS FISCAIS E NON FISCAIS 2027"
    assert s["anuncios"][9]["entidad"] == "CONCELLO DE O VALADOURO"  # «O <strong>VALADOURO</strong>»
    assert s["anuncios"][0]["entidad"] == "Deputación Provincial de Lugo"
    assert boplugo.seleccionar(_filas(boplugo, s)) == []  # ese día no hubo anuncios de empleo
    filas = [{"id": "x", "entidad": "CONCELLO DE SARRIA", "titulo": "BASES E CONVOCATORIA PARA A PROVISIÓN DUNHA PRAZA "
              "DE AUXILIAR ADMINISTRATIVO"}]
    sel = boplugo.seleccionar(filas)
    assert (sel[0]["convocante"]["nombre"], sel[0]["convocante"]["provincia"], sel[0]["tipo_acto"]) == (
        "Sarria", "Lugo", "convocatoria")
