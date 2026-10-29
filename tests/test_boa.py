"""BOA con la respuesta real de su servicio de datos abiertos (29/10/2026), en ISO-8859-1."""

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from motor.autonomicos import boa

FIX = Path(__file__).parent / "fixtures" / "boa_20261029.json"
DIA = date(2026, 10, 29)


def test_lectura_tolerante():
    filas = boa.leer_json(FIX.read_bytes())   # incluye una barra invertida que no es un escape JSON válido
    assert len(filas) == 32 and filas[0]["FechaPublicacion"] == "20261029"


def test_seleccion_y_texto():
    filas = boa.leer_json(FIX.read_bytes())
    disp = [boa.disposicion(f, DIA) for f in filas]
    assert disp[0]["id"].startswith("BOA-") and disp[0]["url_pdf"].startswith("https://www.boa.aragon.es/cgi-bin/")
    emp = [x for x in disp if boa.es_empleo_publico(x)]
    assert len(emp) == 5
    assert {boa.ambito(x) for x in emp} == {"autonomico", "universidad", "local"}
    texto, omitidos = boa.texto_limpio(filas[9]["Texto"])
    assert texto.startswith("La Junta de Gobierno Local") and "&quot;" not in texto and omitidos == 0
    assert len(texto.split("\n")) > 3   # los párrafos llegan separados por dos espacios


def test_procesar_dia(tmp_path, monkeypatch):
    monkeypatch.setattr(boa, "obtener", lambda url, accept=None, timeout=None: SimpleNamespace(
        status=200, contenido=FIX.read_bytes(), cabeceras={}, url=url))
    inf = boa.procesar_dia(DIA, tmp_path, boa.Archivo(tmp_path / "archivo"))
    assert inf["resultado"] == "ok" and inf["empleo_publico"] == 5 and inf["numero"] == "210"
    # El mismo contenido pedido para otro día se detecta (el servicio devolvió otra fecha)
    inf = boa.procesar_dia(date(2026, 10, 28), tmp_path, boa.Archivo(tmp_path / "archivo"))
    assert inf["resultado"] == "error_formato"
