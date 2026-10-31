"""BOPB y BOPT: los festivos el servicio responde HTTP 500 en vez de una lista vacía (31/10/2026)."""
from datetime import date

from motor.archivo import Archivo
from motor.http import Respuesta
from motor.provinciales import bopb, bopt, diba


def test_festivos_sin_boletin(monkeypatch, tmp_path):
    assert diba.festivo(bopb.BOLETIN, date(2026, 9, 11)) and diba.festivo(bopb.BOLETIN, date(2026, 5, 25))
    assert diba.festivo(bopt.BOLETIN, date(2026, 9, 23)) and not diba.festivo(bopt.BOLETIN, date(2026, 10, 29))
    monkeypatch.setattr(diba, "obtener", lambda url, **k: Respuesta(url, 500, b"error"))
    archivo = Archivo(tmp_path / "a", indice_por_fuente=True, solo_huella=True)
    inf = diba.procesar_dia(bopb.BOLETIN, date(2026, 9, 11), tmp_path, archivo, 0)
    assert inf["resultado"] == "sin_boletin" and "festivo" in inf["nota"]
    assert diba.procesar_dia(bopb.BOLETIN, date(2026, 10, 29), tmp_path, archivo, 0)["resultado"] == "error_http"
