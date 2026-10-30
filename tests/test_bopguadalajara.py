"""BOP de Guadalajara: lista por fecha y ficha del boletín (páginas reales del 29/10/2026 y del 03/01/2022, recortadas)."""

from datetime import date
from pathlib import Path

from motor.provinciales import bopguadalajara as g

FIX = Path(__file__).parent / "fixtures"


def test_lista_por_fecha():
    assert g.url_fecha(date(2026, 10, 29)).endswith("/buscar-k2-menu/date/2026/10/29?catid=9")
    f = g.fichas((FIX / "bopguadalajara_fecha_20261029.html").read_bytes())
    assert [(x["numero"], x["fecha"]) for x in f] == [("207", "2026-10-29")]
    assert f[0]["url"].endswith("/9-general/66406-Boletin-Oficial-de-la-Provincia-de-Guadalajara-num-207-de-jueves-29-de-"
                                "Octubre-de-2026")
    f = g.fichas((FIX / "bopguadalajara_fecha_20220103.html").read_bytes())
    assert [(x["numero"], x["fecha"]) for x in f] == [("1", "2022-01-03")]  # «Boletín … núm. 1»


def test_sumario():
    s = g.sumario((FIX / "bopguadalajara_boletin_20261029.html").read_bytes(), 2026)
    assert len(s) == 7
    assert (s[3]["numero_anuncio"], s[3]["entidad"]) == ("2820", "AYUNTAMIENTO DE CIFUENTES")
    assert s[3]["url_pdf"].endswith("/boletin/pdf/pdf2026_2820.pdf")
    assert not g.es_local(s[0])  # la Junta de Comunidades no es administración local
    filas = [{"id": "x", "entidad": "AYUNTAMIENTO DE SIGÜENZA", "titulo": "BASES PARA LA PROVISIÓN EN PROPIEDAD DE UNA PLAZA "
              "DE AGENTE DE POLICÍA LOCAL POR OPOSICIÓN LIBRE"}]
    sel = g.seleccionar(filas)
    assert (sel[0]["convocante"]["nombre"], sel[0]["convocante"]["provincia"]) == ("Sigüenza", "Guadalajara")
