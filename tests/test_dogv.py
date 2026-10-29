"""DOGV con respuestas reales de su API (27/10/2026, extraordinario del mismo día y una disposición con texto)."""

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from motor.autonomicos import dogv

FIX = Path(__file__).parent / "fixtures"


def _fix(nombre):
    return (FIX / nombre).read_bytes()


def test_urls():
    assert dogv.url_calendario(2026, 2) == "https://dogv.gva.es/dogv-portal/dogv/calendar?startDate=2026-2-1&endDate=2026-2-28"
    assert dogv.url_dia(date(2026, 10, 27)).endswith("/dogv?date=2026-10-27&lang=es")
    assert dogv.url_orden(10480, 2).endswith("/dogv/10480?ordenSumario=2&lang=es")


def test_seleccion_dia_real():
    d = json.loads(_fix("dogv_dia_20261027.json"))
    filas = [dogv.disposicion(x, date(2026, 10, 27), 10480, 1) for x in d["disposiciones"]]
    emp = dogv.seleccionar(filas)
    assert len(filas) == 61 and len(emp) == 19
    assert all(e["seccion_id"] == dogv.SECCION_PERSONAL for e in emp)
    assert {e["ambito"] for e in emp} == {"autonomico", "local", "universidad"}
    # De «Nombramientos y ceses» solo entran los resultados de procesos (funcionarios de carrera, aspirantes...)
    betxi = next(e for e in emp if e["organismo"] == "Ayuntamiento de Betxí")
    assert betxi["tipo_acto"] == "nombramiento" and betxi["convocante"]["nombre"] == "Betxí"
    assert filas[0]["url_pdf"].startswith("https://dogv.gva.es/datos/2026/10/27/pdf/")


def test_procesar_dia_con_extraordinario(tmp_path, monkeypatch):
    respuestas = {
        dogv.url_dia(date(2026, 10, 27)): _fix("dogv_dia_20261027.json"),
        dogv.url_versiones(10480): b"[1,2]",
        dogv.url_orden(10480, 2): _fix("dogv_10480_orden2.json"),
    }
    monkeypatch.setattr(dogv, "obtener", lambda url, accept=None: SimpleNamespace(
        status=200, contenido=respuestas[url], cabeceras={}, url=url))
    inf = dogv.procesar_dia(date(2026, 10, 27), True, tmp_path, dogv.Archivo(tmp_path / "archivo"))
    assert inf["resultado"] == "ok" and inf["ordenes"] == [1, 2]
    assert inf["disposiciones"] == 62 and inf["empleo_publico"] == 19
    assert len(dogv.textos_pendientes(tmp_path)) == 19


def test_fecha_distinta_es_error(tmp_path, monkeypatch):
    monkeypatch.setattr(dogv, "obtener", lambda url, accept=None: SimpleNamespace(
        status=200, contenido=_fix("dogv_dia_20261027.json"), cabeceras={}, url=url))
    inf = dogv.procesar_dia(date(2026, 10, 28), False, tmp_path, dogv.Archivo(tmp_path / "archivo"))
    assert inf["resultado"] == "error_formato"


def test_calendario_real():
    cal = {x["fecha"]: x["esBis"] for x in json.loads(_fix("dogv_calendario_202610.json"))}
    assert cal["2026-10-27"] is True and "2026-10-24" not in cal


def test_texto_de_disposicion_real():
    t = dogv.texto_disposicion(_fix("dogv_disposicion_489455.json"))
    assert t["texto"].startswith("En el Boletín Oficial de la Provincia de Castellón núm. 101")
    assert "– Grupo: C1" in t["texto"]
    assert t["seccion"].startswith("II. AUTORIDADES Y PERSONAL - A)")
