"""DOE (Extremadura) con sumarios reales (29/10/2026, 3/1/2022, día sin boletín) y una disposición en HTML."""

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from motor.autonomicos import doe

FIX = Path(__file__).parent / "fixtures"


def _html(nombre):
    return (FIX / nombre).read_bytes().decode("latin-1")


def test_sumario_2026():
    s = doe.parsear_sumario(_html("doe_sumario_20261029.html"))
    assert (s["numero"], s["fecha"], s["no_encontrado"]) == (209, "2026-10-29", False)
    assert len(s["disposiciones"]) == 34
    d = s["disposiciones"][0]
    assert d["url_html"].startswith("https://doe.juntaex.es/otrosFormatos/html.php?xml=2026050122")
    emp = doe.seleccionar(s["disposiciones"])
    assert len(emp) == 5 and all(e["subseccion"] == "OPOSICIONES Y CONCURSOS" for e in emp)
    assert {e["ambito"] for e in emp} == {"autonomico", "universidad"}


def test_sumario_2022_solo_pdf():
    s = doe.parsear_sumario(_html("doe_sumario_20220103.html"))
    assert s["numero"] == 1 and len(s["disposiciones"]) == 26
    d = s["disposiciones"][0]
    assert d["id"] == "DOE-21040194" and d["edicion"] == "10o" and d["url_html"] is None
    emp = doe.seleccionar(s["disposiciones"])
    assert len(emp) == 1 and emp[0]["ambito"] == "local" and emp[0]["tipo_acto"] == "nombramiento"


def test_sin_boletin_y_procesar(tmp_path, monkeypatch):
    s = doe.parsear_sumario(_html("doe_sin_boletin_20261025.html"))
    assert s["no_encontrado"] is True and s["disposiciones"] == []
    paginas = {doe.url_dia(date(2026, 10, 29), "o"): (FIX / "doe_sumario_20261029.html").read_bytes(),
               doe.url_dia(date(2026, 10, 29), "e"): (FIX / "doe_sin_boletin_20261025.html").read_bytes()}
    monkeypatch.setattr(doe, "obtener", lambda url, accept=None: SimpleNamespace(
        status=200, contenido=paginas[url], cabeceras={}, url=url))
    monkeypatch.setattr(doe.time, "sleep", lambda s: None)
    inf = doe.procesar_dia(date(2026, 10, 29), tmp_path, doe.Archivo(tmp_path / "archivo"), extraordinario=True)
    assert inf["resultado"] == "ok" and inf["empleo_publico"] == 5 and [e["tipo"] for e in inf["ediciones"]] == ["o"]
    assert len(doe.textos_pendientes(tmp_path)) == 5


def test_texto_disposicion():
    t = doe.texto_disposicion((FIX / "doe_disposicion_2026050120.html").read_bytes())
    assert "Por Orden de 17 de diciembre de 2025, publicada en el Diario Oficial de Extremadura" in t["texto"]
