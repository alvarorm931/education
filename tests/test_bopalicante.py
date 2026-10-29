"""BOP de Alicante con respuestas reales del servicio JSON (28/10/2026, 04/01/2022 y un domingo sin boletín)."""
from datetime import date
from pathlib import Path

from motor.archivo import Archivo
from motor.catalogo.territorio import ubicar_convocante
from motor.http import Respuesta
from motor.provinciales import bopalicante as b

F = Path(__file__).parent / "fixtures"


def test_dia_y_seleccion():
    s = b.parsear_dia((F / "bopalicante_20261028.json").read_bytes())
    assert not s["sin_boletin"] and s["sumario"] == "Nº 205 del 28-10-2026" and len(s["edictos"]) == 38
    filas = [b.disposicion(e, date(2026, 10, 28)) for e in s["edictos"]]
    sel = {x["id"]: x for x in b.seleccionar(filas)}
    x = next(v for v in sel.values() if "CUATRO PLAZAS TRABAJADOR/A SOCIAL" in v["titulo"])
    assert x["tipo_acto"] == "convocatoria" and x["convocante"] == {
        "tipo": "Ayuntamiento", "nombre": "Dénia", "provincia": "Alicante", "organismo": "AYUNTAMIENTO DÉNIA"}
    assert ubicar_convocante(x["convocante"], ["BOP-ALICANTE"])["codigo_ine"] == "03063"
    assert x["url_pdf"].endswith(".pdf") and x["id"].startswith("BOPALICANTE-2026-")
    # Bonos de consumo y campañas de comercio no son empleo público
    assert not any("BONOS CONSUMO" in v["titulo"] or "COMERCIO LOCAL" in v["titulo"] for v in sel.values())
    assert any(v["tipo_acto"] == "admitidos" for v in sel.values())


def test_2022_y_sin_boletin(tmp_path, monkeypatch):
    s = b.parsear_dia((F / "bopalicante_20220104.json").read_bytes())
    assert len(s["edictos"]) == 11 and s["url_boletin"].endswith("/2022/01/04_2/bop.pdf")
    assert b.parsear_dia((F / "bopalicante_20261025.json").read_bytes())["sin_boletin"]
    monkeypatch.setattr(b, "obtener", lambda url, **kw: Respuesta(url, 200, (F / "bopalicante_20261025.json").read_bytes()))
    inf = b.procesar_dia(date(2026, 10, 25), tmp_path, Archivo(tmp_path / "a", indice_por_fuente=True, solo_huella=True))
    assert inf["resultado"] == "sin_boletin"
