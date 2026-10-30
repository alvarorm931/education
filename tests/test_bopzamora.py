"""BOP de Zamora: últimos boletines de la portada e índice de un boletín (páginas reales del 30/10/2026)."""

from pathlib import Path

from motor.provinciales import bopzamora as z

FIX = Path(__file__).parent / "fixtures"


def test_portada():
    bs = z.boletines_portada((FIX / "bopzamora_portada_20261030.html").read_text(encoding="utf-8"))
    assert [(b["numero"], b["fecha"], b["extraordinario"]) for b in (bs[0], bs[-1])] == [
        (127, "2026-10-28", False), (120, "2026-10-13", True)]
    assert len(bs) == 8


def test_indice():
    filas = z.parsear_indice((FIX / "bopzamora_indice_127_2026.html").read_text(encoding="utf-8"))
    assert len(filas) == 19 and filas[0]["numero_anuncio"] == "202602455"
    assert filas[0]["url_pdf"].endswith("/anuncios/2026/127/202602455.pdf")
    local = next(x for x in filas if x["organismo"] == "Ayuntamiento de Benavente")
    assert local["seccion"] == "III. ADMINISTRACIÓN LOCAL" and local["procedencia"] == "AYUNTAMIENTOS"
    assert z.convocante(local)["nombre"] == "Benavente"
    fila = {"titulo": "Bases para la provisión de una plaza de auxiliar administrativo", "seccion": local["seccion"],
            "organismo": "Ayuntamiento de Toro", "procedencia": "AYUNTAMIENTOS", "id": "x"}
    sel = z.seleccionar([fila])
    assert sel[0]["convocante"]["nombre"] == "Toro" and sel[0]["convocante"]["provincia"] == "Zamora"


def test_lista_total():
    from motor.provinciales import bopzamora as z
    h = (FIX / "bopzamora_total_p1.html").read_text(encoding="utf-8")
    b = z.boletines_portada(h)
    assert len(b) == 20
    assert (b[0]["numero"], b[0]["fecha"], b[-1]["numero"], b[-1]["fecha"]) == (127, "2026-10-28", 108, "2026-09-16")
    assert b[0]["url"].startswith("https://www.diputaciondezamora.es/opencms/servicios/BOP/indice-bop/")
    assert z.url_lista(3).endswith("/opencms/servicios/BOP/bop-total/index.html?reloaded&sort=date_desc&page=3")


def test_lugo_lista_con_errata_en_el_anio():
    """La lista del BOP de Lugo titula un boletín «BOP DE 29/12/8202»: se corrige por los vecinos (2023)."""
    from motor.provinciales import boplugo as lu
    fila = lambda cod, nodo, f: (f'<td class="views-field views-field-field-ail-codigo"> {cod} </td>'  # noqa: E731
                                 f'<td><a href="/gl/node/{nodo}">BOP DE {f}</a>')
    h = "".join([fila("1", "10", "02/01/2024"), fila("297", "9", "29/12/8202"), fila("296", "8", "28/12/2023")])
    assert [b["fecha"] for b in lu.boletines_lista(h.encode())] == ["2024-01-02", "2023-12-29", "2023-12-28"]
