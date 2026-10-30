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
CUERPO = ["NÚMERO 380\nJUNTA DE ANDALUCÍA\nDELEGACIÓN TERRITORIAL DE ECONOMÍA, HACIENDA, FONDOS EUROPEOS Y DE "
          "POLÍTICA INDUSTRIAL Y ENERGÍA EN GRANADA\nEDICTO\nResolución de utilidad pública.",
          "NÚMERO 381\nAYUNTAMIENTO DE ALBUÑOL\nPresupuesto.\nNÚMERO 382\nAYUNTAMIENTO DE CHURRIANA DE LA VEGA\n"
          "Padrón.\nNÚMERO 383\nAYUNTAMIENTO DE CHURRIANA DE LA VEGA\nLista de admitidos:\n1 GARCIA LOPEZ, MARIA "
          "***1234**\nBases publicadas en el Boletín Oficial de la Provincia de Granada número 20, de 1 de febrero de 2023.",
          "NÚMERO 1.384\nAYUNTAMIENTO DE MOTRIL\nBases de la convocatoria de una plaza de Electricista.\n"
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
    trozos = g.bloques([SUMARIO] + CUERPO, cuerpo)
    assert [(t["registro"], t["pagina"]) for t in trozos] == [("380", 2), ("381", 3), ("382", 3), ("383", 3),
                                                               ("1.384", 4)]
    assert g.emparejar(e, trozos) == {0: 0, 1: 1, 2: 2, 3: 3, 4: 4}


# Boletín nº 7 de 12/01/2023 (sonda del 30/10/2026): registros con el año («NÚMERO 5.852/22»), dos asuntos de la misma
# entidad en la misma página y el sumario de Granada capital por áreas, en otro orden que el cuerpo
SUMARIO_2023 = """ADMINISTRACIÓN DE JUSTICIA                                        Pág.
JUZGADO DE INSTRUCCIÓN NÚMERO UNO
DE GRANADA.-Autos nº 68/2022........................................     2
Autos nº 238/2022.................................................................     2
AYUNTAMIENTOS
ALBOLOTE.-Operación JCA complementaria
reparcelación C-4, manzana 14............................................     2
GRANADA. DELEGACIÓN DE PARTICIPACIÓN
CIUDADANA, TURISMO, COMERCIO Y RECURSOS
HUMANOS.-Nombramiento personal eventual,
grupo municipal VOX............................................................     3
Convocatoria proceso selectivo bolsa de trabajo de
Médico/a.................................................................................   4
ÁREA DE CIENCIA, INNOVACIÓN Y TRANSFORMACIÓN
DIGITAL.-Numeración en Carril
de los Coches.........................................................................     3
GUADIX.-Concesión administrativa de uso privativo
de un bien de dominio público.............................................   4
"""
CUERPO_2023 = [
    "NÚMERO 5.852/22\nJUZGADO DE INSTRUCCIÓN NÚMERO UNO DE\nGRANADA\nAutos nº 68/2022\nEDICTO\nSentencia.\n"
    "NÚMERO 6.170/22\nJUZGADO DE INSTRUCCIÓN NÚMERO UNO DE\nGRANADA\nAutos nº 238/2022\nEDICTO\nSentencia.\n"
    "NÚMERO 6.668/22\nAYUNTAMIENTO DE ALBOLOTE (Granada)\nOperación JCA complementaria reparcelación C-4\n"
    "manzana 14\nEDICTO\nAprobación definitiva.",
    "NÚMERO 6.700/22\nAYUNTAMIENTO DE GRANADA\nDELEGACIÓN DE PARTICIPACIÓN CIUDADANA, TURISMO, COMERCIO Y\n"
    "RECURSOS HUMANOS\nNombramiento personal eventual\nEDICTO\nTexto del nombramiento.\n"
    "NÚMERO 6.701/22\nAYUNTAMIENTO DE GRANADA\nÁREA DE CIENCIA, INNOVACIÓN Y TRANSFORMACIÓN DIGITAL\n"
    "Numeración en Carril de los Coches\nEDICTO\nNumeración.",
    "NÚMERO 6.702/22\nAYUNTAMIENTO DE GRANADA\nDELEGACIÓN DE PARTICIPACIÓN CIUDADANA, TURISMO, COMERCIO Y\n"
    "RECURSOS HUMANOS\nConvocatoria bolsa de trabajo de Médico/a\nEDICTO\nBases de la bolsa de Médico/a.\n"
    "NÚMERO 6.703/22\nAYUNTAMIENTO DE OTURA (Granada)\nAnuncio que no está en el sumario\nEDICTO\nOtro.\n"]


def test_registros_con_anio_y_emparejamiento_por_entidad():
    e, cuerpo = g.sumario([SUMARIO_2023] + CUERPO_2023)
    assert cuerpo == 1 and len(e) == 7
    assert e[5]["entidad"] == "GRANADA. ÁREA DE CIENCIA, INNOVACIÓN Y TRANSFORMACIÓN DIGITAL"
    assert g.organismo(e[5]) == "Ayuntamiento de Granada"
    trozos = g.bloques([SUMARIO_2023] + CUERPO_2023, cuerpo)
    assert [t["registro"] for t in trozos] == ["5.852/22", "6.170/22", "6.668/22", "6.700/22", "6.701/22",
                                                "6.702/22", "6.703/22"]
    par = g.emparejar(e, trozos)
    # Médico/a (4.º del sumario) va con su anuncio de la página 4, no con el 4.º del cuerpo; Guadix no está en el
    # cuerpo y se queda sin texto, y el anuncio de Otura, sin asunto
    assert {i: trozos[j]["registro"] for i, j in par.items()} == {
        0: "5.852/22", 1: "6.170/22", 2: "6.668/22", 3: "6.700/22", 4: "6.702/22", 5: "6.701/22"}


def test_sin_entidad_que_case_no_hay_texto():
    e = [{"seccion": "AYUNTAMIENTOS", "entidad": "MOTRIL", "titulo": "Bases de una plaza de Electricista",
          "pagina": 2}]
    trozos = g.bloques(["sumario", "NÚMERO 12\nAYUNTAMIENTO DE ALMUÑÉCAR (Granada)\nBases de una plaza de "
                        "Electricista\nEDICTO\nBases."], 1)
    assert g.emparejar(e, trozos) == {}


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


def test_primer_anuncio_en_la_pagina_del_sumario():
    """Boletín nº 16 de 25/01/2022 (sonda del 30/10/2026): el último asunto del sumario está en la página 1, tras él."""
    p1 = """ANUNCIOS OFICIALES                                                         Pág.
DIPUTACIÓN DE GRANADA. 
PATRONATO FEDERICO GARCÍA LORCA-
Modificación del Catálogo de Puestos de Trabajo.............   2
AYUNTAMIENTOS
ALMUÑÉCAR.-Delegación de funciones de Alcaldía.........     2
ANUNCIOS NO OFICIALES
COMUNIDAD DE REGANTES DE LA ACEQUIA DE
ARABULEILA.-Junta general ordinaria................................     1
NÚMERO 178
COMUNIDAD DE REGANTES DE LA ACEQUIA DE
ARABULEILA
EDICTO
Se convoca a todos los partícipes."""
    p2 = ("NÚMERO 138\nAYUNTAMIENTO DE ALMUÑÉCAR (Granada)\nDelegación de funciones de Alcaldía\nEDICTO\nTexto.\n"
          "NÚMERO 140\nDIPUTACIÓN DE GRANADA\nPATRONATO FEDERICO GARCÍA LORCA\nModificación del Catálogo\nEDICTO\n")
    e, cuerpo = g.sumario([p1, p2])
    assert cuerpo == 0
    assert [(x["entidad"], x["pagina"]) for x in e] == [
        ("PATRONATO FEDERICO GARCÍA LORCA", 2), ("ALMUÑÉCAR", 2),
        ("COMUNIDAD DE REGANTES DE LA ACEQUIA DE ARABULEILA", 1)]
    trozos = g.bloques([p1, p2], cuerpo)
    assert [(t["registro"], t["pagina"]) for t in trozos] == [("178", 1), ("138", 2), ("140", 2)]
    assert g.emparejar(e, trozos) == {0: 2, 1: 1, 2: 0}
