"""BOG (Gipuzkoa): sumario del día, selección y texto (páginas reales del 03/01/2022 y del 29/10/2026)."""

from pathlib import Path

from motor.provinciales import bopgipuzkoa as g

FIX = Path(__file__).parent / "fixtures"


def test_url_dia():
    from datetime import date
    assert g.url_dia(date(2026, 10, 29)).endswith("/castell/bog/2026/10/29/bc261029.htm")


def test_sumario_2022():
    s = g.parsear_dia((FIX / "bopgipuzkoa_20220103.html").read_bytes())
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == ("1", "2022-01-03", 31)
    a = s["anuncios"][0]
    assert (a["seccion"], a["organismo"], a["numero_anuncio"]) == (
        "ADMINISTRACIÓN DEL TERRITORIO HISTÓRICO DE GIPUZKOA", "DEPARTAMENTO DE GOBERNANZA", "c2107928")
    assert a["url_html"].endswith("/castell/bog/2022/01/03/c2107928.htm")
    sel = g.seleccionar([{**x, "id": x["numero_anuncio"]} for x in s["anuncios"]])
    assert ("local", "oferta_empleo", "Aretxabaleta") in [(x["ambito"], x["tipo_acto"], (x["convocante"] or {}).get("nombre"))
                                                          for x in sel]


def test_sumario_2026():
    s = g.parsear_dia((FIX / "bopgipuzkoa_20261029.html").read_bytes())
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == ("207", "2026-10-29", 45)
    sel = g.seleccionar([{**x, "id": x["numero_anuncio"]} for x in s["anuncios"]])
    locales = [x for x in sel if x["ambito"] == "local"]
    assert len(locales) >= 6 and all(x["convocante"]["provincia"] == "Gipuzkoa" for x in locales)
    assert {"Irun", "Hondarribia", "San Sebastián"} <= {x["convocante"]["nombre"] for x in locales}


def test_texto():
    c = (FIX / "bopgipuzkoa_c2107928.html").read_bytes()
    assert "Real Decreto 128/2018" in g.texto_disposicion(c, {"tipo_acto": "convocatoria"})["texto"]
    t = g.texto_disposicion(c, {"tipo_acto": "nombramiento"})  # nombra a la persona: solo se cuenta
    assert t["texto"] is None and t["solo_recuento"]
