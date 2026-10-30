"""BOP de Ourense: boletín del día por la API y texto de un edicto (respuestas reales del 29/10/2026 y del 03/01/2022;
en el edicto de nombramiento se ha retirado el nombre de la persona)."""

from datetime import date
from pathlib import Path

from motor.provinciales import bopourense as o

FIX = Path(__file__).parent / "fixtures"


def test_urls():
    assert o.url_dia(date(2026, 10, 29)).endswith("/portalapi/api/boletin/getFecha/20261029")
    assert o.url_edicto(353077).endswith("/portalapi/api/edicto/descargar/html/353077/es")


def test_dia():
    b = o.leer_dia((FIX / "bopourense_20261029.json").read_bytes())[0]
    assert (b["numero"], b["fecha"], len(b["anuncios"]), b["extraordinario"]) == (208, "2026-10-29", 18, False)
    sel = o.seleccionar([{**x, "id": x["numero_anuncio"]} for x in b["anuncios"]])
    assert [x["tipo_acto"] for x in sel] == ["nombramiento", "nombramiento", "convocatoria", "convocatoria"]
    b = o.leer_dia((FIX / "bopourense_20220103.json").read_bytes())[0]
    assert (b["numero"], b["fecha"], len(b["anuncios"])) == (1, "2022-01-03", 8)
    assert o.seleccionar([{**x, "id": x["numero_anuncio"]} for x in b["anuncios"]]) == []  # un curso no es empleo


def test_edicto():
    t = o.leer_edicto((FIX / "bopourense_edicto_353077.html").read_bytes(), {"tipo_acto": "convocatoria"})
    assert t["entidad"] == "AYUNTAMIENTO DE SAN CIBRAO DAS VIÑAS" and "personal laboral fijo" in t["texto"]
    t = o.leer_edicto((FIX / "bopourense_edicto_353096.html").read_bytes(), {"tipo_acto": "nombramiento"})
    assert t["entidad"] == "AYUNTAMIENTO DE A ARNOIA" and t["texto"] is None and t["solo_recuento"]
    c = o.convocante(t["entidad"], "IV. ENTIDADES LOCALES")
    assert (c["nombre"], c["provincia"]) == ("A Arnoia", "Ourense")
    assert o.convocante(None, "I. DIPUTACIÓN PROVINCIAL DE OURENSE")["tipo"] == "Diputación Provincial"
