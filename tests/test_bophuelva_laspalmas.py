"""BOP de Huelva (JSON del día) y de Las Palmas (sumario HTML): respuestas reales del 29/10/2026, 28/10/2026 y 03/01/2022."""

from pathlib import Path

from motor.provinciales import bophuelva, boplaspalmas

FIX = Path(__file__).parent / "fixtures"


def _filas(s):
    return [{**x, "id": str(x.get("numero_anuncio") or x.get("orden"))} for x in s["anuncios"]]


def test_huelva():
    s = bophuelva.leer((FIX / "bophuelva_20261029.json").read_bytes())
    assert (s["fecha"], s["numero"], len(s["anuncios"])) == ("2026-10-29", "209", 12)
    a = s["anuncios"][0]
    assert (a["numero_anuncio"], a["entidad"], a["seccion"]) == ("383630", "Diputación Provincial de Huelva",
                                                                "Administración Local")
    assert a["url_pdf"].endswith("/portalweb/bope/anuncios/Anuncio_383630_BOP-209_2026.pdf")
    sel = bophuelva.seleccionar(_filas(s))
    assert [(x["convocante"]["nombre"], x["tipo_acto"]) for x in sel] == [("Aroche", "bases"),
                                                                          ("Lucena del Puerto", "convocatoria")]
    assert all(x["convocante"]["provincia"] == "Huelva" for x in sel)  # los jueces de paz no son empleo público


def test_huelva_sin_boletin():
    assert bophuelva.leer((FIX / "bophuelva_sin_boletin.json").read_bytes())["fecha"] is None


def test_las_palmas_2026():
    s = boplaspalmas.parsear_sumario((FIX / "boplaspalmas_20261028.html").read_bytes())
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == ("129", "2026-10-28", 42)
    assert s["url_pdf"].endswith("/boletines/2026/28-10-26/28-10-26.pdf")
    sel = boplaspalmas.seleccionar(_filas(s))
    tipos = {(x["convocante"]["nombre"], x["tipo_acto"]) for x in sel}
    assert ("Gran Canaria", "tribunal") in tipos and ("Lanzarote", "convocatoria") in tipos
    assert ("Telde", "nombramiento") not in tipos and ("Tías", "admitidos") in tipos
    assert all(x["convocante"]["provincia"] == "Las Palmas" for x in sel)


def test_las_palmas_2022_y_dia_sin_boletin():
    s = boplaspalmas.parsear_sumario((FIX / "boplaspalmas_20220103.html").read_bytes())
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == ("1", "2022-01-03", 22)  # «3-1-22»
    assert boplaspalmas.parsear_sumario((FIX / "boplaspalmas_sin_boletin.html").read_bytes())["fecha"] is None
