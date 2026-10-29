import json
from pathlib import Path

from motor.autonomicos import boja
from motor.http import Respuesta
from motor.limpieza import limpiar_html

FIXTURE = Path(__file__).parent / "fixtures" / "boja_boletin_real.json"


def test_limpiar_html_quita_personas():
    h = ("<p>Se publica la lista.</p><p>Doña Ana, DNI ***1234**, admitida.</p>"
         "<table><tr><td>Apellidos y nombre</td><td>DNI</td></tr><tr><td>Pérez, Ana</td><td>***5678**</td></tr></table>"
         "<table><tr><td>Categoría</td><td>Plazas</td></tr><tr><td>Enfermería</td><td>300</td></tr></table>")
    r = limpiar_html(h)
    assert r["texto"] == "Se publica la lista."
    assert r["parrafos_omitidos_por_datos_personales"] == 1
    assert r["tablas"][0]["datos_personales"] and r["tablas"][0]["filas"] == 1
    assert r["tablas"][1]["contenido"][1] == ["Enfermería", "300"]
    assert "Pérez" not in json.dumps(r, ensure_ascii=False)


def test_ambito_y_seleccion():
    assert boja.ambito("Ayuntamientos", "Anuncio del Ayuntamiento de Maracena") == "local"
    assert boja.ambito("Universidades", "Resolución de la Universidad de Jaén") == "universidad"
    assert boja.ambito("Consejería de Presidencia, Sanidad y Emergencias", "Resolución del SAS") == "autonomico"
    assert boja.es_oposicion({"sectionN2": "2.2. Oposiciones, concursos y otras convocatorias"})
    assert boja.es_oposicion({"sectionN2": "5.2. Otros anuncios oficiales", "organisation": "Ayuntamientos",
                              "summaryNoHtml": "Anuncio del Ayuntamiento de Gibraleón, de bases de selección para una plaza"})
    assert not boja.es_oposicion({"sectionN2": "5.2. Otros anuncios oficiales", "organisation": "Ayuntamientos",
                                  "summaryNoHtml": "Anuncio del Ayuntamiento de X sobre licencia urbanística"})


def test_boletin_real_extremo_a_extremo(tmp_path, monkeypatch):
    contenido = FIXTURE.read_bytes()
    monkeypatch.setattr(boja, "obtener", lambda url, **kw: Respuesta(url, 200, contenido, {}))
    inf = boja.procesar_boletin(2026, 207, tmp_path, boja.Archivo(tmp_path / "archivo"), guardar_original=True)
    assert inf["resultado"] == "ok" and inf["disposiciones"] == 3 and inf["oposiciones"] == 2
    filas = [json.loads(x) for x in (tmp_path / "datos/autonomicos/boja/oposiciones/2026/000207.jsonl").read_text().splitlines()]
    sas, maracena = filas
    assert sas["ambito"] == "autonomico" and sas["url_pdf"].endswith(".pdf")
    assert maracena["ambito"] == "local" and "Boletín Oficial de la Provincia de Granada núm. 185" in maracena["texto"]
    assert maracena["fecha"] == "2026-10-26"
    todas = (tmp_path / "datos/autonomicos/boja/disposiciones/2026/000207.jsonl").read_text().splitlines()
    assert len(todas) == 3 and "body" not in todas[0]


def test_registrar_solo_huella(tmp_path):
    from datetime import date
    a = boja.Archivo(tmp_path)
    r = a.registrar("boja", date(2026, 1, 1), b"x", "u", 200, {})
    assert r["solo_huella"] and r["ruta"] is None and len(r["sha256"]) == 64
