"""DOCM con páginas reales: sumarios del 29/10/2026, 28/10/2026 y 3/1/2022 y una disposición en HTML (recortada)."""

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from motor.autonomicos import docm

FIX = Path(__file__).parent / "fixtures"


def _html(nombre):
    return (FIX / nombre).read_text(encoding="utf-8", errors="replace")


def test_sumario_2026():
    s = docm.parsear_sumario(_html("docm_sumario_20261029.html"))
    assert (s["fecha"], s["numero"], len(s["disposiciones"])) == ("2026-10-29", 208, 36)
    d = s["disposiciones"][0]
    assert d["id"] == "DOCM-2026-7798" and d["url_html"].endswith("2026/10/29/html/2026_7798.html&tipo=rutaDocm")
    assert d["titulo"].startswith("Urbanismo. Ley 7/2026, de 23 de octubre")
    emp = docm.seleccionar(s["disposiciones"])
    assert all(e["subseccion"] == "OPOSICIONES Y CONCURSOS" for e in emp) and len(emp) == 2


def test_sumario_2022_y_local():
    s = docm.parsear_sumario(_html("docm_sumario_20220103.html"))
    assert (s["fecha"], s["numero"], len(s["disposiciones"])) == ("2022-01-03", 1, 47)
    emp = docm.seleccionar(s["disposiciones"])
    toboso = next(e for e in emp if "El Toboso" in e["organismo"])
    assert toboso["ambito"] == "local" and toboso["convocante"]["provincia"] == "Toledo"
    assert toboso["tipo_acto"] == "oferta_empleo"


def test_dia_sin_diario_muestra_otro(tmp_path, monkeypatch):
    # Pedir un día sin diario devuelve el último publicado: se reconoce por la fecha y no se guarda como ese día
    monkeypatch.setattr(docm, "obtener", lambda url, accept=None, sesion=None: SimpleNamespace(
        status=200, contenido=(FIX / "docm_sumario_20261028.html").read_bytes(), cabeceras={}, url=url))
    monkeypatch.setattr(docm, "SESION", object())
    inf = docm.procesar_dia(date(2026, 10, 31), tmp_path, docm.Archivo(tmp_path / "a"))
    assert inf["resultado"] == "sin_boletin"
    inf = docm.procesar_dia(date(2026, 10, 28), tmp_path, docm.Archivo(tmp_path / "a"))
    assert inf["resultado"] == "ok" and inf["numero"] == 207


def test_texto():
    t = docm.texto_disposicion((FIX / "docm_disposicion_2026_7798.html").read_bytes())
    assert t["texto"].startswith("I.- DISPOSICIONES GENERALES")
    assert "Esta ley entrará en vigor a los veinte días siguientes" in t["texto"]
    assert "AÑO XLV" not in t["texto"]


def test_portada_del_dia(tmp_path, monkeypatch):
    # robots.txt prohíbe sumario.do y cambiarBoletin.do; la portada /docm/ trae el diario del día
    from motor.http import Respuesta
    cuerpo = (Path(__file__).parent / "fixtures" / "docm_portada_20261030.html").read_bytes()
    monkeypatch.setattr(docm, "obtener", lambda url, **k: Respuesta(url, 200, cuerpo, {}))
    monkeypatch.setattr(docm, "sesion", lambda nueva=False: None)
    inf = docm.procesar_portada(tmp_path, docm.Archivo(tmp_path / "archivo"))
    assert (inf["resultado"], inf["fecha"], inf["numero"], inf["disposiciones"]) == ("ok", "2026-10-30", 209, 62)
    assert (tmp_path / "datos/autonomicos/docm/dias/2026/10/30.json").exists()
