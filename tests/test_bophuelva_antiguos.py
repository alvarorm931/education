"""BOP de Huelva anterior al 20/06/2023: sumario y cuerpo del PDF del boletín entero (formato de la sonda del 31/10/2026;
textos y nombres inventados)."""
import json
from datetime import date

from motor.archivo import Archivo
from motor.http import Respuesta
from motor.provinciales import bophuelva_antiguos as h

SUMARIO1 = """Publicación de Lunes a Viernes, excepto festivos Nº de Reg. 1567/76 - Dep. Legal H-1-1958
Edita: Excma. Diputación Provincial
Información al público de 9 a 13h. Tlf. 959 49 47 04 - Fax: 959 494 700
TARIFA VIGENTE PUBLICADA EN EL B.O.P.
Lunes, 19 de Junio de 2023 Número 115
TA DE LA EXCMA. DIPUTACIÓN PRO VIN CIAL A TRAVÉS DEL REGISTRO GENERAL DE LA CORPORACIÓN
Continúa……
ADMINISTRACIÓN LOCAL
– Excma. Diputación Provincial de Huelva
Resolución de aprobación de las listas de ﬁ nitivas
de admitidos y excluidos en las pruebas selectivas
convocadas para cubrir varias plazas del turno libre ..........  5135
– Consorcio Provincial Contra Incendios y Salvamento
de Huelva
Nombramiento como funcionarios de carrera para
cubrir plazas como Bombero Conductor ........................  5137
– Ayuntamiento de El Almendro
Resolución de aprobación de las bases y convocatoria
del programa "Mi Primer empleo joven" ....................  5137
– Ayuntamiento de Ayamonte
Aprobación de la matrícula del impuesto sobre
actividades económicas del ejercicio 2023 .  5138
Diputación Provincial de Huelva. Boletín Oficial de la Provincia
Documento firmado electrónicamente (de acuerdo a la Ley 59/2003) el 19/06/2023 a las 00:00:13 - Nº BOP: 115/23
Autenticidad verificable mediante Código Seguro de Verificación BOPxs23115X= en https://verifirma.diphuelva.es
"""
SUMARIO2 = """– Ayuntamiento de Cartaya
Aprobación de la lista de ﬁ nitiva de admitidos y
excluidos para la provisión de una plaza de Ingeniero Industrial ......  5139
Convocatoria y bases para la provisión de una plaza de
Arquitecto Técnico .......................................................  5139
Diputación Provincial de Huelva. Boletín Oficial de la Provincia
"""
P5135 = """ BOLETIN OFICIAL HUELVA N.º 115 19 de Junio de 2023 5135
EXCMA. DIPUTACIÓN PROVINCIAL DE HUELVA
RESOLUCIÓN
Resolución nº: 1903/2023
Aprobar con carácter de ﬁ nitivo las listas de personas admitidas y excluidas.
Admitidas
1.Ruiz Prado, Ana Lucía
2.Gil Ferrer, Marta Del Mar
Diputación Provincial de Huelva. Boletín Oficial de la Provincia
Documento firmado electrónicamente (de acuerdo a la Ley 59/2003) el 19/06/2023 a las 00:00:13 - Nº BOP: 115/23
"""
P5136 = """5136 19 de Junio de 2023 BOLETIN OFICIAL HUELVA N.º 115
3.Mora Sáez, Pedro
Huelva, 14 de junio de 2023.
"""
P5137 = """ BOLETIN OFICIAL HUELVA N.º 115 19 de Junio de 2023 5137
CONSORCIO PROVINCIAL CONTRA INCENDIOS Y
SALVAMENTO DE HUELVA
ANUNCIO
Se hace público el nombramiento como funcionarios de carrera, Bombero Conductor.
AYUNTAMIENTO DE EL ALMENDRO
ANUNCIO
Por Resolución de Alcaldía se aprueban las bases y la convocatoria del programa Mi Primer Empleo Joven.
Primera. Objeto. Contratación de dos personas durante seis meses.
Segunda. Plazo de solicitudes: diez días hábiles.
"""
P5138 = """5138 19 de Junio de 2023 BOLETIN OFICIAL HUELVA N.º 115
AYUNTAMIENTO DE AYAMONTE
EDICTO
Aprobada la matrícula del impuesto sobre actividades económicas del ejercicio 2023.
"""
P5139 = """ BOLETIN OFICIAL HUELVA N.º 115 19 de Junio de 2023 5139
AYUNTAMIENTO DE CARTAYA
ANUNCIO
Aprobación de la lista definitiva de admitidos y excluidos de la plaza de Ingeniero Industrial.
AYUNTAMIENTO DE CARTAYA
ANUNCIO
Bases para la provisión de una plaza de Arquitecto Técnico, grupo A2, por concurso-oposición.
Tasa: 30 euros. Plazo: veinte días naturales desde el extracto en el BOE.
"""
PAGINAS = [SUMARIO1, SUMARIO2, P5135, P5136, P5137, P5138, P5139]


def test_cabecera_de_pagina_par_e_impar():
    assert h.numero_de_pagina(P5135) == 5135
    assert h.numero_de_pagina(P5136) == 5136
    assert h.numero_de_pagina(SUMARIO1) is None


def test_ligaduras():
    assert h.sin_ligaduras("listas de ﬁ nitivas") == "listas definitivas"
    assert h.sin_ligaduras("modi ﬁ cación de créditos") == "modificación de créditos"
    assert h.sin_ligaduras("con la ﬁ nalidad") == "con la finalidad"
    assert h.sin_ligaduras("Garﬁ as") == "Garfias"


def test_sumario():
    s = h.sumario(PAGINAS)
    assert [(x["entidad"], x["pagina"]) for x in s] == [
        ("Excma. Diputación Provincial de Huelva", 5135),
        ("Consorcio Provincial Contra Incendios y Salvamento de Huelva", 5137),
        ("Ayuntamiento de El Almendro", 5137), ("Ayuntamiento de Ayamonte", 5138),
        ("Ayuntamiento de Cartaya", 5139), ("Ayuntamiento de Cartaya", 5139)]
    assert s[0]["titulo"].startswith("Resolución de aprobación de las listas definitivas de admitidos")
    assert s[0]["seccion"] == "Administración Local"
    assert s[3]["titulo"] == "Aprobación de la matrícula del impuesto sobre actividades económicas del ejercicio 2023"


def test_cuerpo_y_casado():
    asuntos = h.sumario(PAGINAS)
    lineas, comienzos = h.cuerpo(PAGINAS)
    assert [c["pagina"] for c in comienzos] == [5135, 5137, 5137, 5138, 5139, 5139]
    assert comienzos[1]["entidad"] == "CONSORCIO PROVINCIAL CONTRA INCENDIOS Y SALVAMENTO DE HUELVA"
    assert not any("BOLETIN OFICIAL" in l or "firmado electr" in l for _, l in lineas)
    assert h.casar(asuntos, comienzos) == {i: i for i in range(6)}
    # si en una página no se ve uno de los comienzos, los demás casan por la entidad y el que falta queda sin texto
    sin_almendro = [c for c in comienzos if "ALMENDRO" not in c["entidad"]]
    casados = h.casar(asuntos, sin_almendro)
    assert 2 not in casados and casados[1] == 1 and casados[3] == 2


def test_dia_completo(tmp_path):
    from motor.provinciales import bophuelva_antiguos as mod
    d = date(2023, 6, 19)
    html = (b'<html><body><iframe src="/visor/?file=/portalweb/bop/boletines/20230619-1.pdf"></iframe>'
            b'<a href="https://s2.diphuelva.es/portalweb/bop/boletines/20230619-1.pdf">PDF</a></body></html>')
    assert mod.enlaces_pdf(html, d) == ["https://s2.diphuelva.es/portalweb/bop/boletines/20230619-1.pdf"]
    # como lo da el portal: la dirección codificada en el visor
    visor = (b'<iframe id="iFramePDF" name="boletin.pdf" src="/comunJS/pdfjs/web/viewer.html?file=%2Fportalweb%2Fbop'
             b'%2Fboletines%2F20230619-1.pdf" width="650px">')
    assert mod.enlaces_pdf(visor, d) == ["https://s2.diphuelva.es/portalweb/bop/boletines/20230619-1.pdf"]

    def obtener(url, **k):
        if "busqueda" in url:
            return Respuesta(url, 200, html, {"content-type": "text/html"})
        return Respuesta(url, 200, b"%PDF-falso", {"content-type": "application/pdf"})

    mod.obtener, antes = obtener, mod.obtener
    import motor.pdf
    paginas_antes = motor.pdf.paginas
    motor.pdf.paginas = lambda c, layout=False: PAGINAS
    try:
        inf = mod.procesar_dia(d, tmp_path, Archivo(tmp_path / "archivo", indice_por_fuente=True), 0)
    finally:
        mod.obtener, motor.pdf.paginas = antes, paginas_antes
    assert inf["resultado"] == "ok" and inf["numero"] == "115" and inf["disposiciones"] == 6 and inf["casados"] == 6
    base = tmp_path / "datos" / "provinciales" / "bophuelva"
    filas = [json.loads(l) for l in (base / "disposiciones" / "2023" / "06" / "19.jsonl").read_text().splitlines()]
    assert filas[0]["id"] == "BOPHUELVA-2023-06-19-001" and filas[0]["url_pdf_boletin"].endswith("20230619-1.pdf")
    empleo = [json.loads(l) for l in (base / "oposiciones" / "2023" / "06" / "19.jsonl").read_text().splitlines()]
    ids = {x["id"]: x for x in empleo}
    # la lista de admitidos de la Diputación: solo el recuento, nunca los nombres
    lista = json.loads((base / "textos" / "2023" / "06" / "BOPHUELVA-2023-06-19-001.json").read_text())
    assert lista["texto"] is None and lista["solo_recuento"] and "Ruiz" not in json.dumps(lista)
    # las bases de El Almendro, con su texto hasta el anuncio siguiente
    if "BOPHUELVA-2023-06-19-003" in ids:
        bases = json.loads((base / "textos" / "2023" / "06" / "BOPHUELVA-2023-06-19-003.json").read_text())
        assert "Plazo de solicitudes" in bases["texto"] and "Ayamonte" not in bases["texto"]
    arquitecto = json.loads((base / "textos" / "2023" / "06" / "BOPHUELVA-2023-06-19-006.json").read_text())
    assert "Tasa: 30 euros" in arquitecto["texto"] and "Ingeniero Industrial" not in arquitecto["texto"]
    assert arquitecto["paginas"] == [5139]


def test_texto_sin_el_del_asunto_siguiente_que_no_se_vio():
    asuntos = h.sumario(PAGINAS)
    lineas, comienzos = h.cuerpo(PAGINAS)

    def texto(tramos, i):
        ini, fin = tramos[i]
        return "\n".join(l for _, l in lineas[ini:fin])
    todos = h.tramos_de_texto(asuntos, comienzos, lineas, h.casar(asuntos, comienzos))
    assert "Plazo de solicitudes" in texto(todos, 2) and "Ayamonte" not in texto(todos, 2)
    # sin el comienzo de Ayamonte (página siguiente), las bases de El Almendro acaban con su página
    sin_ayamonte = [c for c in comienzos if "AYAMONTE" not in c["entidad"]]
    tramos = h.tramos_de_texto(asuntos, sin_ayamonte, lineas, h.casar(asuntos, sin_ayamonte))
    assert "Plazo de solicitudes" in texto(tramos, 2) and "matrícula" not in texto(tramos, 2)
    # sin el de El Almendro (en la misma página que el Consorcio), el Consorcio se queda sin texto
    sin_almendro = [c for c in comienzos if "ALMENDRO" not in c["entidad"]]
    tramos = h.tramos_de_texto(asuntos, sin_almendro, lineas, h.casar(asuntos, sin_almendro))
    assert 1 not in tramos and 2 not in tramos and 0 in tramos
