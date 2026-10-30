"""Boletín Oficial del Principado de Asturias: sumario, selección y texto (páginas reales del 30/10/2026, recortadas)."""

from datetime import date
from pathlib import Path

from motor.autonomicos import bopa

FIX = Path(__file__).parent / "fixtures"


def _html(nombre):
    return (FIX / nombre).read_text(encoding="utf-8")


def test_cabecera_y_dia_sin_boletin():
    assert bopa.cabecera(_html("bopa_sumario_20261029.html")) == (210, "2026-10-29", False)
    assert bopa.cabecera(_html("bopa_sumario_20220103.html")) == (1, "2022-01-03", False)
    # Pedido el domingo 25/10/2026: devuelve el último boletín publicado, que se reconoce por la fecha
    assert bopa.cabecera(_html("bopa_sumario_pedido_20261025.html"))[1] == "2026-10-30"


def test_sumario_y_seleccion():
    filas = bopa.parsear_sumario(_html("bopa_sumario_20261029.html"))
    assert len(filas) == 51 and filas[0]["codigo"] == "2026-08847"
    assert filas[0]["suborganismo"] == 'INSTITUTO ASTURIANO DE ADMINISTRACIÓN PÚBLICA "ADOLFO POSADA"'
    sel = {x["codigo"]: x for x in bopa.seleccionar(filas)}
    assert set(sel) == {"2026-08847", "2026-08567", "2026-08603", "2026-08770", "2026-08794", "2026-08581",
                        "2026-08598"}
    assert sel["2026-08847"]["tipo_acto"] == "convocatoria" and sel["2026-08847"]["ambito"] == "autonomico"
    aviles = sel["2026-08581"]
    assert aviles["ambito"] == "local" and aviles["convocante"]["nombre"] == "Avilés"
    assert aviles["convocante"]["provincia"] == "Asturias"


def test_direcciones():
    u = bopa.url_texto("2026-08847", date(2026, 10, 29))
    assert "p_r_p_dispositionReference=2026-08847" in u and "p_r_p_dispositionDate=29%2F10%2F2026" in u
    assert "p_r_p_summaryDate=03%2F01%2F2022" in bopa.url_dia(date(2022, 1, 3))


def test_texto():
    t = bopa.texto_disposicion((FIX / "bopa_disposicion_2026-08847.html").read_bytes())
    assert t["titulo"].startswith("Resolución de 23 de octubre de 2026, de la Directora del Instituto Asturiano")
    assert "provisión de 40 plazas del Cuerpo de Gestión" in t["texto"]
