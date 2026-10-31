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


def test_busqueda_que_sale_por_la_pagina_anterior(monkeypatch, tmp_path):
    """Tras un día de varias páginas, la búsqueda del siguiente salía por la segunda página («Mostrant del 26…») y se
    perdían los 25 primeros: ahora se pide también la primera. Y un día leído a medias se vuelve a leer."""
    import json
    desplazada = BUSQUEDA.replace("Mostrant del 1 al 25 de 41", "Mostrant del 26 al 41 de 41")
    pedidas = []

    def falso(url, accept=None, sesion=None, formulario=None, cabeceras_extra=None, **kw):
        if formulario is None:
            return Respuesta(url, 200, PORTAL.encode())
        if formulario.get("javax.faces.source") == "buscarBtn":
            return Respuesta(url, 200, desplazada.encode())
        pedidas.append(formulario["list_first"])
        return Respuesta(url, 200, (BUSQUEDA if formulario["list_first"] == "0" else PAGINA2).encode())

    monkeypatch.setattr(v, "obtener", falso)
    inf = v.procesar_dia(date(2026, 10, 28), tmp_path, Archivo(tmp_path / "a", indice_por_fuente=True, solo_huella=True),
                         v.Portal(pausa=0))
    assert pedidas == ["0", "25"] and (inf["anuncios"], inf["disposiciones"]) == (41, 41) and not inf["alertas"]
    r = tmp_path / "d.json"
    r.write_text(json.dumps({"resultado": "ok", "alertas": ["BOP Valencia 2022-01-19: 1 anuncios leídos de 26"]}))
    assert v.incompleto(r) and not v.incompleto(tmp_path / "no.json")


def test_reparar_dias_dados_por_sin_boletin(tmp_path):
    import json as _json
    from motor.provinciales import bopvalencia as v
    base = tmp_path / "datos" / "provinciales" / "bopvalencia"
    (base / "dias" / "2022" / "02").mkdir(parents=True)
    (base / "disposiciones" / "2022" / "02").mkdir(parents=True)
    for d in ("14", "16", "19"):
        (base / "dias" / "2022" / "02" / f"{d}.json").write_text(
            _json.dumps({"fecha": f"2022-02-{d}", "resultado": "sin_boletin", "alertas": []}))
    (base / "dias" / "2022" / "02" / "19.json").write_text(  # sábado
        _json.dumps({"fecha": "2022-02-19", "resultado": "sin_boletin", "nota": "fin de semana", "alertas": []}))
    (base / "disposiciones" / "2022" / "02" / "14.jsonl").write_text(_json.dumps({"id": "x", "boletin": "30"}) + "\n")
    assert v.reparar_dias(tmp_path) == (1, 1)
    assert _json.loads((base / "dias" / "2022" / "02" / "14.json").read_text())["resultado"] == "ok"
    assert v.restaurado(base / "dias" / "2022" / "02" / "14.json")  # se vuelve a leer entero
    assert not v.restaurado(base / "dias" / "2022" / "02" / "19.json")
    assert not (base / "dias" / "2022" / "02" / "16.json").exists()
    assert (base / "dias" / "2022" / "02" / "19.json").exists()


def test_dia_sin_resultados_confirmado_por_el_portal(tmp_path):
    import pytest

    class Falso:
        url = "https://example.org/bop"

        def __init__(self, cuerpo):
            self.cuerpo = cuerpo

        def buscar(self, desde, hasta):
            return [], 0, [Respuesta(self.url, 200, self.cuerpo)]
    archivo = Archivo(tmp_path / "a", indice_por_fuente=True, solo_huella=True)
    inf = v.procesar_dia(date(2022, 2, 16), tmp_path, archivo, Falso(b"<div class='ui-datagrid-empty'>No s'han trobat resultats</div>"))
    assert inf["resultado"] == "sin_boletin" and inf["confirmado"]
    with pytest.raises(v.ErrorPortal):
        v.procesar_dia(date(2022, 2, 17), tmp_path, archivo, Falso(b"<partial-response></partial-response>"))
