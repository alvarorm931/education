from datetime import date
from pathlib import Path

from motor.grados import boe_historico as bh

F = Path(__file__).parent / "fixtures" / "sumario_ejemplo.xml"


def test_clasificar():
    assert bh.clasificar("Resolución … por la que se publica el plan de estudios de Graduado o Graduada en Derecho.") == ("grado", "plan")
    assert bh.clasificar("Resolución … por la que se publica la modificación del plan de estudios de Máster Universitario en Abogacía.") == ("master", "modificacion")
    assert bh.clasificar("Real Decreto 762/2026, de 30 de septiembre, por el que se regula una subvención.") is None


def test_sin_domingos():
    d = list(bh.dias(date(2010, 1, 1), date(2010, 1, 10)))
    assert date(2010, 1, 3) not in d and date(2010, 1, 10) not in d and len(d) == 8


def test_recorrido_guarda_solo_planes(monkeypatch, tmp_path):
    xml = F.read_bytes()

    class R:
        status = 200
        contenido = xml
        cabeceras = {}

    monkeypatch.setattr(bh, "obtener", lambda url, accept=None: R())
    monkeypatch.setattr(bh, "clasificar", lambda t: ("grado", "plan") if "Universidad" in t else None)
    res = bh.ejecutar(date(2010, 1, 4), date(2010, 1, 4), tmp_path, pausa=0, max_minutos=1)
    assert res["sumarios"] == 1 and res["errores"] == 0
    filas = list((tmp_path / "datos" / "estudios" / "grados" / "boe_historico").glob("2010_*.jsonl"))
    assert len(filas) == 1
