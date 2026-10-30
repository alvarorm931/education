"""BOP de Granada, boletines anteriores a julio de 2024: listado por año y mes y sumario del PDF entero."""

import json

from motor.provinciales import bopgranada_antiguos as g

SUMARIO = """Granada, viernes, 31 de marzo de 2023Granada, martes, 11 de septiembre de 2008B.O.P. número 63 Páginan n
 Año 2023
Viernes, 31 de marzo
62
Administración: Diputación de Granada.  Domicilio: c/ Periodista Barrios Talavera nº 1 (Granada 18014).
DL GR 1-1958. I.S.S.N.: 1699-6739. Edición digital. http:/www.dipgra.es/BOP/bop.asp
ANUNCIOS OFICIALES                                                         Pág.
JUNTA DE ANDALUCÍA. DELEGACIÓN TERRITORIAL DE
ECONOMÍA, HACIENDA, FONDOS EUROPEOS Y DE
POLÍTICA INDUSTRIAL Y ENERGÍA EN GRANADA.-
Expte.: E-4990; 14.248/AT....................................................     2
AYUNTAMIENTOS
ALBUÑOL.-Presupuesto 2023..............................................     3
CHURRIANA DE LA VEGA.-Padrón de agua potable
de diciembre de 2022............................................................     3
Admitidos y excluidos para plaza de Conserje
Encargado de Mantenimiento en Centro Municipal
de Cultura...............................................................................     3
MOTRIL.-Bases para una plaza 
de Electricista.........................................................................   4
"""
CUERPO = ["NÚMERO 380\nJUNTA DE ANDALUCÍA\nEDICTO\nResolución de utilidad pública.",
          "NÚMERO 381\nAYUNTAMIENTO DE ALBUÑOL\nPresupuesto.\nNÚMERO 382\nAYUNTAMIENTO DE CHURRIANA DE LA VEGA\n"
          "Padrón.\nNÚMERO 383\nAYUNTAMIENTO DE CHURRIANA DE LA VEGA\nLista de admitidos:\n1 GARCIA LOPEZ, MARIA "
          "***1234**\nBases publicadas en el Boletín Oficial de la Provincia de Granada número 20, de 1 de febrero de 2023.",
          "NÚMERO 384\nAYUNTAMIENTO DE MOTRIL\nBases de la convocatoria de una plaza de Electricista.\n"
          "Plazo: veinte días hábiles."]


def test_listado_y_parametros():
    h = ('<script>parametrosSagaListado["parametrosBase_SagaListado_x"] = {\n'
         "                urlAjax: '/system/modules/com.saga.listado/elements/SagaListado-element.jsp?__locale=es',\n"
         "                esOnline: true,\n                ResultadosPorPagina: '15',\n};</script>")
    assert g.parametros_base(h) == {"urlAjax": "/system/modules/com.saga.listado/elements/SagaListado-element.jsp"
                                               "?__locale=es", "esOnline": "true", "ResultadosPorPagina": "15"}
    lista = g.boletines(b'<a href="/export/sites/bop/publica/boletines-anteriores/.galleries/Boletines-Anteriores/'
                        b'20230331-2023062.pdf">x</a>')
    assert lista == [{"fecha": "2023-03-31", "numero": 62, "url_pdf": "https://bop.dipgra.es/export/sites/bop/"
                      "publica/boletines-anteriores/.galleries/Boletines-Anteriores/20230331-2023062.pdf"}]


def test_sumario_y_bloques():
    e, cuerpo = g.sumario([SUMARIO] + CUERPO)
    assert cuerpo == 1
    assert [(x["seccion"], x["entidad"], x["pagina"]) for x in e] == [
        ("ANUNCIOS OFICIALES", "JUNTA DE ANDALUCÍA. DELEGACIÓN TERRITORIAL DE ECONOMÍA, HACIENDA, FONDOS EUROPEOS Y "
                               "DE POLÍTICA INDUSTRIAL Y ENERGÍA EN GRANADA", 2),
        ("AYUNTAMIENTOS", "ALBUÑOL", 3), ("AYUNTAMIENTOS", "CHURRIANA DE LA VEGA", 3),
        ("AYUNTAMIENTOS", "CHURRIANA DE LA VEGA", 3), ("AYUNTAMIENTOS", "MOTRIL", 4)]
    assert e[3]["titulo"] == "Admitidos y excluidos para plaza de Conserje Encargado de Mantenimiento en Centro Municipal de Cultura"
    assert [n for n, _ in g.bloques([SUMARIO] + CUERPO, cuerpo)] == ["380", "381", "382", "383", "384"]


def test_procesar(tmp_path, monkeypatch):
    from motor.archivo import Archivo
    from motor.http import Respuesta
    monkeypatch.setattr(g, "obtener", lambda url, accept=None, **k: Respuesta(url, 200, b"%PDF-1.4", {}))
    monkeypatch.setattr("motor.provinciales.textos.paginas_pdf", lambda c: [SUMARIO] + CUERPO)
    b = {"fecha": "2023-03-31", "numero": 62, "url_pdf": "https://bop.dipgra.es/x.pdf"}
    inf = g.procesar(b, tmp_path, Archivo(tmp_path / "archivo"))
    assert (inf["resultado"], inf["disposiciones"], inf["empleo_publico"], inf["textos"]) == ("ok", 5, 2, 2)
    base = tmp_path / "datos" / "provinciales" / "bopgranada"
    op = [json.loads(l) for l in (base / "oposiciones" / "2023" / "03" / "31.jsonl").read_text().splitlines()]
    assert [x["convocante"]["nombre"] for x in op] == ["Churriana de la Vega", "Motril"]
    assert op[0]["numero_anuncio"] == "383"
    lista = json.loads((base / "textos" / "2023" / "03" / f"{op[0]['id']}.json").read_text(encoding="utf-8"))
    assert lista["texto"] is None and "GARCIA" not in json.dumps(lista, ensure_ascii=False)
    assert lista["citas"][0]["fecha"] == "2023-02-01"
    bases = json.loads((base / "textos" / "2023" / "03" / f"{op[1]['id']}.json").read_text(encoding="utf-8"))
    assert "veinte días hábiles" in bases["texto"]
