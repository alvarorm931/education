"""BOP de Palencia: lista de boletines y sumario del PDF (página real de la lista y texto de las dos primeras páginas
del boletín del 28/10/2026, tal como lo extrae pypdf)."""

from pathlib import Path

from motor.provinciales import boppalencia as p

FIX = Path(__file__).parent / "fixtures"


def test_lista():
    l = p.boletines_lista((FIX / "boppalencia_lista.html").read_bytes())
    assert len(l) == 10 and (l[0]["numero"], l[0]["fecha"], l[0]["extraordinario"]) == (129, "2026-10-28", False)
    assert l[0]["url_pdf"].endswith("/system/files/bop/2026/20261028-bop-129-Ordinario.pdf")
    assert sum(x["extraordinario"] for x in l) == 1


def test_sumario():
    s = p.parsear_sumario((FIX / "boppalencia_sumario_20261028.txt").read_text(encoding="utf-8"))
    assert len(s) == 23  # las dos páginas del sumario, sin cabeceras ni pies
    assert (s[1]["entidad"], s[1]["servicio"], s[1]["pagina"]) == ("DIPUTACIÓN PROVINCIAL DE PALENCIA",
                                                                   "Servicio de Personal", 4)
    assert s[1]["titulo"].startswith("Lista definitiva de admitidos y excluidos de la convocatoria para el ingreso")
    assert s[1]["titulo"].endswith("Tribunal y fecha realización del examen")
    assert (s[8]["entidad"], s[8]["servicio"]) == ("Palencia", "Patronato Municipal de Deportes")
    assert s[-1]["grupo"] == "ANUNCIOS PARTICULARES"
    sel = p.seleccionar([{**x, "id": str(i)} for i, x in enumerate(s)])
    assert len(sel) == 5 and all(x["tipo_acto"] == "admitidos" for x in sel)
    assert sel[-1]["convocante"]["organismo"] == "Ayuntamiento de Palencia - Patronato Municipal de Deportes"
    assert all(x["convocante"]["provincia"] == "Palencia" for x in sel)
