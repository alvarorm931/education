"""BOP de Soria: boletines del día y sumario de la ficha (páginas reales del 28/10/2026 y del 03/01/2022)."""

from datetime import date
from pathlib import Path

from motor.provinciales import bopsoria as s

FIX = Path(__file__).parent / "fixtures"


def test_dia():
    assert s.url_dia(date(2026, 10, 28)).endswith("/mod.boloficial/mem.listadodia/fecha.28-10-2026")
    assert [(f["id_ficha"], f["numero"], f["fecha"]) for f in s.fichas((FIX / "bopsoria_dia_20261028.html").read_bytes())] \
        == [("55780", 124, "2026-10-28")]
    assert [(f["numero"], f["fecha"]) for f in s.fichas((FIX / "bopsoria_dia_20220103.html").read_bytes())] == [
        (1, "2022-01-03")]


def test_sumario():
    x = s.sumario((FIX / "bopsoria_detalle_55780.html").read_bytes())
    assert len(x) == 25
    a = x[2]  # niveles vacíos: repiten sección, grupo y entidad del anterior
    assert (a["numero_anuncio"], a["grupo"], a["entidad"]) == ("2021", "AYUNTAMIENTOS", "SORIA")
    assert a["titulo"] == "Lista definitiva de admitidos y excluidos Trabajador Social"
    assert a["url_pdf"].startswith("https://bop.dipsoria.es/") and a["url_pdf"].endswith("%232E%23pdf")
    sel = s.seleccionar([{**y, "id": y["numero_anuncio"]} for y in x])
    assert sel[0]["convocante"]["tipo"] == "Diputación Provincial"  # «Bases Convocatoria Jefatura de Proyectos…»
    assert sel[0]["convocante"]["organismo"] == "DIPUTACIÓN PROVINCIAL DE SORIA - RECURSOS HUMANOS"
    assert [y["convocante"]["nombre"] for y in sel[1:]] == ["Soria"] * 4
