"""BOPB (Barcelona) con páginas reales del 28/10/2026, 12/10/2026 (festivo), 25/10/2026 (domingo) y 04/01/2022."""
from datetime import date
from pathlib import Path

from motor.archivo import Archivo
from motor.extraccion.plazas import extraer_plazas
from motor.extraccion.plazo import extraer_plazo
from motor.http import Respuesta
from motor.provinciales import bopb

F = Path(__file__).parent / "fixtures"


def _leer(n):
    return (F / n).read_text(encoding="utf-8")


def test_dia_paginado_y_seleccion():
    p1 = bopb.parsear_dia(_leer("bopb_personal_20261028_p1.html"))
    p2 = bopb.parsear_dia(_leer("bopb_personal_20261028_p2.html"))
    assert (p1["fecha"], p1["total"], len(p1["anuncios"]), len(p2["anuncios"])) == ("2026-10-28", 27, 20, 7)
    x = next(a for a in p1["anuncios"] if a["cve"] == "202610159101")
    assert x["anunciante"] == "Ajuntament de Bigues i Riells del Fai" and x["fecha"] == "2026-10-28"
    assert x["url_pdf"] == "https://bop.diba.cat/anunci/descarrega-pdf/4007221" and x["id"] == "BOPB-202610159101"
    sel = {s["cve"]: s for s in bopb.seleccionar(p1["anuncios"] + p2["anuncios"])}
    s = sel["202610159101"]
    assert (s["tipo_acto"], s["ambito"], s["convocante"]["tipo"], s["convocante"]["nombre"], s["convocante"]["provincia"]) \
        == ("convocatoria", "local", "Ayuntamiento", "Bigues i Riells del Fai", "Barcelona")
    tipos = {s["tipo_acto"] for s in sel.values()}
    assert {"admitidos", "nombramiento", "convocatoria"} <= tipos
    # El juez de paz cae en «Personal» pero no es empleo público
    assert not any("jutge" in s["titulo"].lower() for s in sel.values())


def test_festivo_domingo_y_2022():
    assert bopb.parsear_dia(_leer("bopb_festivo_20261012.html")) == {"fecha": "2026-10-12", "total": 0, "anuncios": []}
    assert len(bopb.parsear_dia(_leer("bopb_personal_20220104.html"))["anuncios"]) == 6


def test_procesar_dia_con_paginas_y_domingo(tmp_path, monkeypatch):
    paginas = {bopb.url_dia(date(2026, 10, 28), 1): _leer("bopb_personal_20261028_p1.html"),
               bopb.url_dia(date(2026, 10, 28), 2): _leer("bopb_personal_20261028_p2.html")}

    def falso(url, **kw):
        if url in paginas:
            return Respuesta(url, 200, paginas[url].encode(), {})
        return Respuesta(url, 500, _leer("bopb_domingo_20261025.html").encode(), {})

    monkeypatch.setattr(bopb, "obtener", falso)
    a = Archivo(tmp_path / "archivo", indice_por_fuente=True, solo_huella=True)
    inf = bopb.procesar_dia(date(2026, 10, 28), tmp_path, a, pausa=0)
    assert (inf["resultado"], inf["paginas"], inf["disposiciones"]) == ("ok", 2, 27) and not inf["alertas"]
    assert bopb.procesar_dia(date(2026, 10, 25), tmp_path, a, pausa=0)["resultado"] == "sin_boletin"
    assert bopb.procesar_dia(date(2026, 10, 27), tmp_path, a, pausa=0)["resultado"] == "error_http"


def test_texto_de_bases_en_catalan():
    # Texto real del PDF del anuncio 202610159101, ya extraído
    t = ("ANUNCI\nHavent-se aprovat per Resolució d’Alcaldia, les Bases reguladores i la convocatòria de les proves\n"
         "selectives per a la provisió en propietat d’una plaça de caporal/a de la policia local , es fa públic el\n"
         "present anunci i s’obre el termini de presentació de sol·licituds, que serà de 20 dies hàbils comptats a\n"
         "partir de l’endemà de la publicació d’aquest anunci en el Diari Oficial de la Generalitat de Catalunya:\n"
         "Butlletí Oficial de la Província de Barcelona\nData 28-10-2026\nCVE 202610159101\nPàg. 2-27\n")
    from motor.limpieza import limpiar_texto
    limpio = limpiar_texto(t, bopb.RE_CABECERA_PDF)["texto"]
    assert "CVE" not in limpio and "Pàg." not in limpio
    p = extraer_plazo(limpio, "2026-10-28", bopb.NOMBRES)
    assert p["dias"] == 20 and p["cuenta_desde"] == "Diari Oficial de la Generalitat de Catalunya"
    pl = extraer_plazas(limpio)
    assert pl["total"] == 1 and pl["plazas"][0]["denominacion"] == "caporal/a de la policia local"
