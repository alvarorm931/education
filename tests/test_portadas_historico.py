"""Histórico de los BOP leídos por su portada que tienen dirección por día (Jaén y Salamanca, 03/01/2022)."""

from datetime import date
from pathlib import Path

from motor.archivo import Archivo
from motor.http import Respuesta
from motor.provinciales import bopjaen, bopsalamanca, portadas

FIX = Path(__file__).parent / "fixtures"


def test_direcciones():
    assert bopjaen.PORTADA.url_dia(date(2022, 1, 3)) == "https://bop.dipujaen.es/bop/03-01-2022"
    assert bopsalamanca.PORTADA.url_dia(date(2022, 1, 3)).endswith("/sede/BOP/index.jsp?fechaBoletin=2022-01-03")


def test_historico(tmp_path, monkeypatch):
    paginas = {bopjaen.PORTADA.url_dia(date(2022, 1, 3)): (FIX / "bopjaen_dia_20220103.html").read_bytes(),
               bopsalamanca.PORTADA.url_dia(date(2022, 1, 3)): (FIX / "bopsalamanca_dia_20220103.html").read_bytes()}
    monkeypatch.setattr(portadas, "obtener", lambda url, accept=None: Respuesta(url, 200, paginas[url], {}))
    monkeypatch.setattr("time.sleep", lambda s: None)
    archivo = Archivo(tmp_path / "archivo", solo_huella=True)
    for p, n in ((bopjaen.PORTADA, 12), (bopsalamanca.PORTADA, 19)):
        assert portadas.historico(p, tmp_path, archivo, date(2022, 1, 1), date(2022, 1, 3)) == 0
        dia = portadas._ruta(p, tmp_path, "dias", date(2022, 1, 3), "json").read_text(encoding="utf-8")
        assert '"resultado": "ok"' in dia and f'"disposiciones": {n}' in dia
        assert portadas._ruta(p, tmp_path, "dias", date(2022, 1, 1), "json").exists()  # sábado: sin boletín
