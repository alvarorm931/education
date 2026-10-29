"""BOP de Valencia con respuestas reales del portal (28/10/2026): búsqueda, segunda página y formulario."""
import re
from datetime import date
from pathlib import Path

from motor.archivo import Archivo
from motor.http import Respuesta
from motor.provinciales import bopvalencia as v

F = Path(__file__).parent / "fixtures"
BUSQUEDA = (F / "bopvalencia_busqueda_20261028.xml").read_text(encoding="utf-8")
PAGINA2 = (F / "bopvalencia_pagina2_20261028.xml").read_text(encoding="utf-8")
PORTAL = (F / "bopvalencia_portal.html").read_text(encoding="utf-8")


def test_listado_y_seleccion():
    a, b = v.parsear_listado(BUSQUEDA), v.parsear_listado(PAGINA2)
    assert (len(a), len(b), v.RE_TOTAL.search(BUSQUEDA).group("n")) == (25, 16, "41")
    x = a[0]
    assert x["id"] == "BOPVALENCIA-2026-12998" and x["organismo"] == "Ajuntament d'Agullent" and x["seccion"] == "Municipis"
    assert x["url_pdf"] == "https://bop.dival.es/bop/downloads?anuncioNumReg=2026/12998&lang=va" and x["boletin"] == "207"
    sel = v.seleccionar(a + b)
    assert all(s["ambito"] == "local" and s["convocante"]["provincia"] == "Valencia" for s in sel)
    tipos = [s["tipo_acto"] for s in sel]
    assert tipos.count("admitidos") >= 5 and "nombramiento" in tipos and "tribunal" in tipos
    # Juez de paz y bases de un servicio municipal no son empleo público
    assert not any("jutge" in s["titulo"] or "servei de trans" in s["titulo"] for s in sel)


def test_sesion_busqueda_y_paginas(monkeypatch, tmp_path):
    llamadas = []

    def falso(url, accept=None, sesion=None, formulario=None, cabeceras_extra=None, **kw):
        llamadas.append(formulario)
        if formulario is None:
            return Respuesta(url, 200, PORTAL.encode())
        assert cabeceras_extra["Faces-Request"] == "partial/ajax"
        if formulario.get("javax.faces.source") == "buscarBtn":
            assert formulario["filtroCalendarioIni_input"] == "28/10/2026"
            return Respuesta(url, 200, BUSQUEDA.encode())
        assert formulario["list_first"] == "25" and formulario["j_idt235"] == "j_idt235"
        return Respuesta(url, 200, PAGINA2.encode())

    monkeypatch.setattr(v, "obtener", falso)
    portal = v.Portal(pausa=0)
    inf = v.procesar_dia(date(2026, 10, 28), tmp_path, Archivo(tmp_path / "a", indice_por_fuente=True, solo_huella=True),
                         portal)
    assert (inf["resultado"], inf["anuncios"], inf["disposiciones"]) == ("ok", 41, 41) and not inf["alertas"]
    assert len(llamadas) == 3 and re.match(r"-?\d+:-?\d+", llamadas[2]["javax.faces.ViewState"])
