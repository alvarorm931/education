"""BOP de Cáceres: calendario del mes y anuncios del boletín con su texto (respuestas reales de octubre de 2026;
en el fichero de anuncios solo se conserva el texto de uno, que es lo que necesita la prueba)."""

from pathlib import Path

from motor.provinciales import bopcaceres as c

FIX = Path(__file__).parent / "fixtures"


def test_calendario():
    lista = c.boletines_del_mes((FIX / "bopcaceres_mes_202610.json").read_bytes(), 2026, 10)
    assert lista[:2] == [{"id_boletin": 6160, "fecha": "2026-10-01"}, {"id_boletin": 6161, "fecha": "2026-10-02"}]


def test_boletin_y_seleccion():
    s = c.leer_boletin((FIX / "bopcaceres_6180.json").read_bytes())
    assert (s["fecha"], s["numero"], len(s["anuncios"])) == ("2026-10-29", "208", 26)
    a = s["anuncios"][0]
    assert (a["numero_anuncio"], a["titulo"], a["entidad"]) == (
        "BOP-2026-5048", "Concurso-oposición de 21 plazas de Auxiliar Administrativo.", "Diputación Provincial de Cáceres")
    sel = c.seleccionar([{**x, "id": x["numero_anuncio"]} for x in s["anuncios"]])
    tipos = [(x["convocante"]["nombre"], x["tipo_acto"]) for x in sel]
    assert ("Cáceres", "convocatoria") in tipos and ("Zorita", "convocatoria") in tipos
    assert any(x["numero_anuncio"] == "BOP-2026-5067" for x in sel)  # «una plaza formador PALV curso 2026/2027»
    assert all(x["convocante"]["provincia"] == "Cáceres" for x in sel)
    t = c.texto_anuncio(sel[0])
    assert "concurso-oposición" in t["texto"] and "21 de Auxiliar Administrativo" in t["texto"]
    lista = next(x for x in sel if x["tipo_acto"] == "admitidos")
    assert c.texto_anuncio(lista)["texto"] is None  # las listas solo se cuentan


def test_meses():
    from datetime import date
    assert c.meses(date(2025, 11, 1), date(2026, 2, 3)) == [(2026, 2), (2026, 1), (2025, 12), (2025, 11)]
