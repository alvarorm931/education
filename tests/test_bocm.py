import json
from datetime import date
from pathlib import Path

from motor.autonomicos import bocm
from motor.http import Respuesta

F = Path(__file__).parent / "fixtures"


def test_url_por_fecha():
    assert bocm.url_sumario(date(2026, 10, 29)).endswith("/2026/10/29/BOCM-202610291.xml")


def test_sumario_real():
    s = bocm.parsear_sumario((F / "bocm_sumario_20261029.xml").read_bytes())
    assert s["numero"] == "260" and s["fecha"] == "2026-10-29"
    assert len(s["disposiciones"]) >= 90
    alc = [d for d in s["disposiciones"] if d["titulo"].startswith("Alcobendas. Ofertas de empleo")][0]
    assert bocm.es_empleo_publico(alc) and bocm.ambito(alc) == "local"
    assert bocm.municipio_y_materia(alc["titulo"]) == ("Alcobendas", "Ofertas de empleo", "Proceso selectivo")
    urbanismo = [d for d in s["disposiciones"] if "Urbanismo" in d["titulo"]][0]
    assert not bocm.es_empleo_publico(urbanismo)


def test_dia_real_extremo_a_extremo(tmp_path, monkeypatch):
    contenido = (F / "bocm_sumario_20261029.xml").read_bytes()
    monkeypatch.setattr(bocm, "obtener", lambda url, **kw: Respuesta(url, 200, contenido, {}))
    inf = bocm.procesar_dia(date(2026, 10, 29), tmp_path, bocm.Archivo(tmp_path / "archivo"))
    assert inf["resultado"] == "ok" and inf["numero"] == "260" and inf["empleo_publico"] > 20
    filas = [json.loads(l) for l in (tmp_path / "datos/autonomicos/bocm/oposiciones/2026/10/29.jsonl").read_text().splitlines()]
    assert {f["ambito"] for f in filas} <= {"local", "autonomico", "universidad", "otro"}
    assert any(f["municipio"] == "Alcobendas" for f in filas)


def test_fecha_equivocada_es_error(tmp_path, monkeypatch):
    contenido = (F / "bocm_sumario_20261029.xml").read_bytes()
    monkeypatch.setattr(bocm, "obtener", lambda url, **kw: Respuesta(url, 200, contenido, {}))
    inf = bocm.procesar_dia(date(2026, 10, 28), tmp_path, bocm.Archivo(tmp_path / "archivo"))
    assert inf["resultado"] == "error_formato"


def test_sin_boletin(tmp_path, monkeypatch):
    monkeypatch.setattr(bocm, "obtener", lambda url, **kw: Respuesta(url, 404, b"", {}))
    inf = bocm.procesar_dia(date(2026, 10, 25), tmp_path, bocm.Archivo(tmp_path / "archivo"))
    assert inf["resultado"] == "sin_boletin" and inf["alertas"] == []  # domingo


def test_texto_disposicion_real():
    d = bocm.texto_disposicion((F / "bocm_disposicion_72.xml").read_bytes())
    assert "13 de noviembre de 2026" in d["texto"]
    assert "Oferta de Empleo Público del Ayuntamiento de Alcobendas del año 2024" in d["texto"]
