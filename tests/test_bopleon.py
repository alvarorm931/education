"""BOP de León: ficha del boletín del día y sumario en PDF (boletín 206 del 29/10/2026)."""

from datetime import date
from pathlib import Path

from motor.provinciales import bopleon as l

FIX = Path(__file__).parent / "fixtures"


def test_ficha():
    assert l.url_dia(date(2026, 10, 29)) == "https://bop.dipuleon.es/publica/consulta-de-bops/buscador/BOP-29-10-2026/"
    f = l.ficha((FIX / "bopleon_dia_20261029.html").read_bytes())
    assert (f["numero"], f["fecha"]) == (206, "2026-10-29")
    assert f["url_sumario"].endswith("/DOCUMENTOS-Sumarios-en-PDF/final-69db29ec.pdf")


def test_sumario():
    a, alertas = l.parsear_sumario((FIX / "bopleon_sumario_206_2026.pdf").read_bytes())
    assert (len(a), alertas) == (35, [])
    # asunto partido por el salto de página entre la 1 y la 2
    x = a[9]
    assert (x["seccion"], x["grupo"], x["entidad"]) == ("Administración Local", "Ayuntamientos", "Ayuntamiento de Páramo del Sil")
    assert x["titulo"].endswith("desempeño del puesto denominado Auxiliar Administrativo, Atención al Ciudadano y Contratación")
    assert x["url_anuncio"].startswith("https://bop.dipuleon.es/publica/buscador-anuncios/anuncio/Bases-y-Convocatoria-")
    assert (a[15]["seccion"], a[15]["grupo"]) == ("Administración Local", "Mancomunidades")  # encabezado al pie de página
    assert (a[24]["seccion"], a[24]["grupo"], a[24]["entidad"]) == (
        "Administración de Justicia", "Tribunal Superior de Justicia de Castilla y León", "Audiencia Provincial de León")
    sel = l.seleccionar([{**y, "id": str(i)} for i, y in enumerate(a)])
    assert [y["convocante"]["nombre"] for y in sel] == ["Bembibre", "Páramo del Sil", "Valderas"]
