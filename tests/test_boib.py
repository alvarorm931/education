"""BOIB con páginas reales: calendario de 2026, sección II del boletín 138/2026 (29/10) y una disposición."""

from pathlib import Path
from types import SimpleNamespace

from motor.autonomicos import boib

FIX = Path(__file__).parent / "fixtures"
B = {"id": "12352", "fecha": "2026-10-29", "tipo": "ordinario"}


def _html(nombre):
    return (FIX / nombre).read_text(encoding="utf-8")


def test_calendario_anual():
    cal = boib.calendario(_html("boib_calendario_2026.html"), 2026)
    assert len(cal) == 138
    assert cal[0] == {"id": "12210", "fecha": "2026-01-01", "tipo": "ordinario"}
    assert cal[-1] == B
    assert sum(1 for b in cal if b["tipo"] == "extraordinario") == 8


def test_seccion_ii_y_seleccion():
    s = boib.parsear_seccion(_html("boib_seccion2_12352.html"), B)
    assert s["numero"] == 138 and len(s["disposiciones"]) == 41
    emp = boib.seleccionar(s["disposiciones"])
    assert len(emp) == 33
    menorca = [e for e in emp if e["organismo"] == "CONSEJO INSULAR DE MENORCA"]
    assert menorca and all(e["ambito"] == "local" for e in menorca)   # los consells insulars son entidades locales
    assert not any("juez de paz" in e["titulo"].lower() for e in emp)
    palma = next(e for e in emp if e["organismo"] == "AYUNTAMIENTO DE PALMA")
    assert palma["convocante"]["nombre"] == "Palma" and palma["url_html"].startswith("https://www.caib.es/eboibfront/es/2026/12352/")


def test_procesar_y_texto(tmp_path, monkeypatch):
    monkeypatch.setattr(boib, "obtener", lambda url, accept=None: SimpleNamespace(
        status=200, contenido=(FIX / "boib_seccion2_12352.html").read_bytes(), cabeceras={}, url=url))
    inf = boib.procesar_boletin(B, tmp_path, boib.Archivo(tmp_path / "archivo"))
    assert inf["resultado"] == "ok" and inf["empleo_publico"] == 33
    assert len(boib.textos_pendientes(tmp_path)) == 33
    t = boib.texto_disposicion((FIX / "boib_disposicion_721429.html").read_bytes())
    assert t["texto"].startswith("Antecedentes") and "Xarxes socials" not in t["texto"]
