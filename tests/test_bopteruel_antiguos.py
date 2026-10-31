"""BOP de Teruel anteriores: página del día que enlaza el PDF y cuerpo del boletín (formato de la sonda del 30/10/2026)."""
import json
from datetime import date

from motor.archivo import Archivo
from motor.http import Respuesta
from motor.provinciales import bopteruel_antiguos as t

PORTADA = """
BOP TE Número 7 12 de enero de 2023
B OLETÍN O FICIAL
 SUMARIO
ADMINISTRACIÓN LOCAL
Ayuntamientos
Villastar..................................................................................................................2
Ariño ......................................................................................................................7
"""
PAGINA2 = """
BOP TE Número 7 12 de enero de 2023  2

ADMINISTRACIÓN LOCAL
Núm. 2023-0057

VILLASTAR


Bases de la convocatoria para la elaboración de una bolsa de empleo en la categoría de educadora infantil
(A2), al objeto de cubrir con carácter temporal necesidades que se deriven de sustitución de titulares, plazas va-
cantes.
Primera. — Objeto de la convocatoria.
El objeto de la presente convocatoria es la elaboración de una bolsa de empleo.
"""
PAGINA3 = """
BOP TE Número 7 12 de enero de 2023  7
Núm. 2023-0061

ARIÑO

Lista provisional de admitidos y excluidos para la provisión de una plaza de Auxiliar Administrativo.
1. ***1234** PEREZ GARCIA, JUAN
NO OFICIAL
Núm. 2023-0070
COMUNIDAD DE REGANTES PAGO ALTO
Convocatoria de junta general ordinaria.
"""


def test_anuncios_del_cuerpo():
    a = t.anuncios([PORTADA, PAGINA2, PAGINA3])
    assert [x["numero_anuncio"] for x in a] == ["2023-0057", "2023-0061", "2023-0070"]
    assert (a[0]["entidad"], a[0]["seccion"]) == ("VILLASTAR", "Administración Local")
    assert a[0]["titulo"].startswith("Bases de la convocatoria para la elaboración de una bolsa de empleo")
    assert "vacantes" in a[0]["titulo"] and "Primera" not in a[0]["titulo"]
    assert a[2]["seccion"] == "No Oficial" and "NO OFICIAL" not in a[1]["texto"]
    assert t.entidad_local("VILLASTAR") == "Ayuntamiento de Villastar"
    assert t.entidad_local("COMUNIDAD DE REGANTES PAGO ALTO") == "Comunidad De Regantes Pago Alto" or \
        t.entidad_local("COMUNIDAD DE REGANTES PAGO ALTO").lower().startswith("comunidad")


def test_enlace_y_dia(tmp_path, monkeypatch):
    pagina = ('<html><body>El día 12/01/2023 no se publicó boletín.<a href="/estatico/boletines/2023/12enero.pdf">'
              'Boletín</a></body></html>').encode("latin-1")
    assert t.enlace_pdf(pagina, t.url_dia(date(2023, 1, 12))) == \
        "https://236ws.dpteruel.es/estatico/boletines/2023/12enero.pdf"
    assert t.enlace_pdf(b"<html>sin enlace</html>", t.url_dia(date(2023, 1, 14))) is None

    def falso(url, accept=None, **kw):
        if "Redireccion" in url:
            return Respuesta(url, 200, pagina, {})
        return Respuesta(url, 200, b"%PDF-1.4 falso", {})

    monkeypatch.setattr(t, "obtener", falso)
    monkeypatch.setattr(t, "paginas", lambda pdf: [PORTADA, PAGINA2, PAGINA3])
    monkeypatch.setattr(t.time, "sleep", lambda s: None)
    inf = t.procesar_dia(date(2023, 1, 12), tmp_path, Archivo(tmp_path / "a", indice_por_fuente=True, solo_huella=True), 0)
    assert inf["resultado"] == "ok" and inf["disposiciones"] == 3 and inf["empleo_publico"] == 2
    base = tmp_path / "datos" / "provinciales" / "bopteruel"
    opo = [json.loads(l) for l in (base / "oposiciones" / "2023" / "01" / "12.jsonl").read_text().splitlines()]
    assert {x["id"] for x in opo} == {"BOP-TERUEL-2023-01-12-2023-0057", "BOP-TERUEL-2023-01-12-2023-0061"}
    lista = json.loads((base / "textos" / "2023" / "01" / "BOP-TERUEL-2023-01-12-2023-0061.json").read_text())
    # Una lista de personas: solo el recuento, nunca el texto
    assert lista["texto"] is None and lista["lineas_con_documento_de_identidad"] == 1
    assert "PEREZ" not in json.dumps(lista, ensure_ascii=False)
