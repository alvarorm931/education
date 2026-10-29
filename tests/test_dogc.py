"""DOGC con respuestas reales de su API (sumario del DOGC 9783 de 29/10/2026, calendario y un documento)."""

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from motor.autonomicos import dogc

FIX = Path(__file__).parent / "fixtures"
DIA = date(2026, 10, 29)


def _fix(nombre):
    return (FIX / nombre).read_bytes()


def _sumario():
    return json.loads(_fix("dogc_sumario_9783.json"))["sumaris"][0]


def test_documentos_aplanados():
    filas = dogc.documentos(_sumario(), DIA)
    assert len(filas) == 99 and all(f["id"] for f in filas)
    upf = [f for f in filas if f["organismo"] == "Universidad Pompeu Fabra"]
    assert len(upf) == 8 and upf[0]["grupo"] == "Universidades catalanas"
    assert filas[0]["url_html"] == "https://dogc.gencat.cat/es/document-del-dogc/?documentId=1057996"


def test_seleccion_real():
    emp = dogc.seleccionar(dogc.documentos(_sumario(), DIA))
    assert len(emp) == 43
    assert {e["ambito"] for e in emp} == {"autonomico", "universidad", "local"}
    titulos = " | ".join(e["titulo"] for e in emp)
    assert "remodelación de la plaza" not in titulos          # una plaza mayor no es una plaza de empleo
    assert "cese de la subdirectora" not in titulos           # ceses y designaciones de cargos no entran
    assert "oferta pública parcial de empleo" in titulos
    arbos = next(e for e in emp if e["organismo"] == "Ayuntamiento de L'Arboç")
    assert arbos["convocante"]["nombre"] == "L'Arboç"


def test_calendario(monkeypatch):
    monkeypatch.setattr(dogc, "obtener", lambda url, accept=None, formulario=None: SimpleNamespace(
        status=200, contenido=_fix("dogc_calendario_202610.json"), cabeceras={}, url=url))
    cal = dogc.calendario_mes(2026, 10)
    assert cal["2026-10-01"] == "9762" and "2026-10-10" not in cal


def test_procesar_dia(tmp_path, monkeypatch):
    llamadas = []

    def obtener(url, accept=None, formulario=None):
        llamadas.append((url, formulario))
        return SimpleNamespace(status=200, contenido=_fix("dogc_sumario_9783.json"), cabeceras={}, url=url)
    monkeypatch.setattr(dogc, "obtener", obtener)
    inf = dogc.procesar_dia(DIA, "9783", tmp_path, dogc.Archivo(tmp_path / "archivo"))
    assert inf["resultado"] == "ok" and inf["empleo_publico"] == 43
    assert llamadas == [(dogc.API + "/summaryDOGC", {"numDOGC": "9783", "language": "es"})]
    # El mismo sumario con otra fecha es un error de formato, no un día válido
    inf = dogc.procesar_dia(date(2026, 10, 28), "9783", tmp_path, dogc.Archivo(tmp_path / "archivo"))
    assert inf["resultado"] == "error_formato"


def test_texto_documento_real():
    t = dogc.texto_disposicion(_fix("dogc_documento_1057996.json"))
    assert t["cve"] == "CVE-DOGC-B-26300041-2026" and t["tipo_documento"] == "Corrección de erratas"
    assert t["texto"].startswith("Habiéndose detectado unos errores en el Decreto 190/2026")
    assert t["url_xml"].startswith("https://portaldogc.gencat.cat/utilsEADOP/AppJava/AkomaNtoso?")
