"""BOP de Córdoba con páginas reales del portal (28/10/2026, 03/01/2022 y un sábado sin boletín)."""

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from motor.archivo import Archivo
from motor.provinciales import bopcordoba as b

FIX = Path(__file__).parent / "fixtures"


def test_dia_con_trozos_diferidos():
    s = b.parsear_dia((FIX / "bopcordoba_20261028.html").read_bytes())
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == ("209", "2026-10-28", 13)
    assert all(x["cve"] and x["url_pdf"].startswith("https://bop.dipucordoba.es/visor-pdf/28-10-2026/")
               for x in s["anuncios"])  # ninguno sin su PDF tras recolocar los trozos
    lucena = [x for x in s["anuncios"] if x["organismo"] == "Ayuntamiento de Lucena"]
    assert [x["cve"] for x in lucena] == ["BOP-A-2026-3568", "BOP-A-2026-3644"]
    sel = b.seleccionar(s["anuncios"])
    assert len(sel) == 3 and {x["convocante"]["nombre"] for x in sel} == {"Lucena", "Villaviciosa de Córdoba"}


def test_2022_y_siglas_entre_parentesis():
    s = b.parsear_dia((FIX / "bopcordoba_20220103.html").read_bytes())
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == ("1", "2022-01-03", 11)
    sel = b.seleccionar(s["anuncios"])
    assert [x["convocante"]["nombre"] for x in sel] == ["Montoro", "Villafranca de Córdoba"]
    imtur = [x for x in s["anuncios"] if "IMTUR" in (x["organismo"] or "")][0]
    assert b.convocante_de_organismo(imtur["organismo"])["provincia"] is None  # «(IMTUR)» no es una provincia


def test_sin_boletin(tmp_path, monkeypatch):
    cuerpo = (FIX / "bopcordoba_20240615_sin_boletin.html").read_bytes()
    monkeypatch.setattr(b, "obtener", lambda *a, **k: SimpleNamespace(status=200, contenido=cuerpo, cabeceras={}, url="u"))
    inf = b.procesar_dia(date(2024, 6, 15), tmp_path, Archivo(tmp_path / "archivo"))
    assert inf["resultado"] == "sin_boletin" and not inf["alertas"]
