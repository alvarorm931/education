"""BOCYL con datos reales: exportación del conjunto de datos abiertos (27-28/10 y locales del 2/10/2026) y una
disposición en XML (ISO-8859-15)."""

import json
from datetime import date
from pathlib import Path
from urllib.parse import unquote

from motor.autonomicos import bocyl
from motor.autonomicos.comun import convocante_de_organismo, nombre_propio

FIX = Path(__file__).parent / "fixtures"


def _disposiciones():
    filas = json.loads((FIX / "bocyl_export_202610.json").read_text(encoding="utf-8"))
    return [bocyl.fila_a_disposicion(f) for f in filas]


def test_url_mes_cubre_el_mes_entero():
    u = unquote(bocyl.url_mes(2026, 12))
    assert "fecha_publicacion>=date'2026-12-01' and fecha_publicacion<date'2027-01-01'" in u
    assert u.startswith(bocyl.API + "/exports/json?")


def test_disposicion_desde_fila_real():
    d = _disposiciones()[0]
    assert d["id"].startswith("BOCYL-D-28102026-209-")
    assert d["boletin_numero"] == 209 and d["fecha"] == "2026-10-28"
    assert d["url_xml"].startswith("https://bocyl.jcyl.es/boletines/2026/10/28/xml/")


def test_seleccion_de_empleo_publico():
    emp = bocyl.seleccionar(_disposiciones())
    ambitos = {e["ambito"] for e in emp}
    assert ambitos == {"autonomico", "universidad", "local"}
    # Ningún anuncio urbanístico de la sección III entra como empleo público
    assert not any("suelo" in e["titulo"].lower() or "urbanística" in e["titulo"].lower() for e in emp)
    locales = [e for e in emp if e["ambito"] == "local"]
    assert len(locales) == 13
    nombres = {(e["convocante"]["tipo"], e["convocante"]["nombre"], e["convocante"]["provincia"]) for e in locales}
    assert ("Ayuntamiento", "Miranda de Ebro", "Burgos") in nombres
    assert ("Ayuntamiento", "Segovia", "Segovia") in nombres          # capital: el boletín no repite la provincia
    assert ("Diputación Provincial", "Palencia", "Palencia") in nombres
    # Una consejería con «Universidades» en su nombre no es una universidad
    iem = next(e for e in emp if "IEM/1101/2026" in e["titulo"])
    assert iem["ambito"] == "autonomico" and iem["alcance"] == "provision_puestos"


def test_control_de_ediciones():
    todas = _disposiciones()
    c = bocyl.control_ediciones([d for d in todas if d["fecha"] == "2026-10-28"])
    assert c["saltos"] == {} and c["ediciones"]["2026"] == [209, 209, 1]
    # La muestra salta del 2 al 28 de octubre: el control lo detecta como ediciones que faltan
    c = bocyl.control_ediciones(todas)
    assert c["saltos"]["2026"][0] == c["ediciones"]["2026"][0] + 1 and c["saltos"]["2026"][-1] == 208


def test_texto_de_disposicion_real():
    t = bocyl.texto_disposicion((FIX / "bocyl_disposicion_20200102.xml").read_bytes())
    assert t["titulo"].startswith("ORDEN SAN/1329/2019, de 17 de diciembre")
    assert t["organismo"] == "CONSEJERÍA DE SANIDAD"
    assert "Estatuto Marco del Personal Estatutario" in t["texto"]
    assert len(t["tablas"]) == 2


def test_procesar_mes_y_textos(tmp_path, monkeypatch):
    contenido = (FIX / "bocyl_export_202610.json").read_bytes()

    from types import SimpleNamespace
    r = SimpleNamespace(status=200, contenido=contenido, cabeceras={}, url="")
    monkeypatch.setattr(bocyl, "obtener", lambda url, accept=None: r)
    inf = bocyl.procesar_mes(2026, 10, tmp_path, bocyl.Archivo(tmp_path / "archivo"), date(2026, 10, 29))
    assert inf["resultado"] == "ok" and inf["empleo_publico"] == 19 and inf["completo"] is False
    pend = bocyl.textos_pendientes(tmp_path)
    assert len(pend) == 19 and pend[0]["alcance"] in (None, "acceso")


def test_convocante_y_nombres():
    assert nombre_propio("SAN ANDRÉS DEL RABANEDO") == "San Andrés del Rabanedo"
    c = convocante_de_organismo("COMUNIDAD DE VILLA Y TIERRA DE PEDRAZA (SEGOVIA)")
    assert c["tipo"] == "Comunidad de Villa y Tierra" and c["provincia"] == "Segovia"
    c = convocante_de_organismo("MANCOMUNIDAD PINODUERO (VALLADOLID)")
    assert c["tipo"] == "Mancomunidad" and c["nombre"] == "Pinoduero"
