import json
from datetime import date
from pathlib import Path

import pytest

from motor.boe.extraer import construir_acto, extraer_local, numero
from motor.boe.texto import texto_plano
from motor.calendario import domingo_de_pascua, fin_de_plazo

REALES = {t["identificador"]: t for t in json.loads(
    (Path(__file__).parent / "fixtures" / "textos_locales_reales.json").read_text(encoding="utf-8"))}


def test_pascua():
    assert domingo_de_pascua(2026) == date(2026, 4, 5)
    assert domingo_de_pascua(2027) == date(2027, 3, 28)


@pytest.mark.parametrize("pub,dias,tipo,fin", [
    (date(2026, 10, 2), 10, "habiles", date(2026, 10, 19)),   # salta el 12 de octubre
    (date(2026, 10, 1), 20, "habiles", date(2026, 10, 30)),
    (date(2026, 10, 5), 20, "naturales", date(2026, 10, 26)),  # acaba en domingo: pasa al lunes
    (date(2026, 10, 21), 20, "habiles", date(2026, 11, 18)),
])
def test_fin_de_plazo(pub, dias, tipo, fin):
    assert fin_de_plazo(pub, dias, tipo) == fin


@pytest.mark.parametrize("txt,n", [("Tres", 3), ("veintitrés", 23), ("treinta y una", 31), ("12", 12), ("varias", None)])
def test_numero(txt, n):
    assert numero(txt) == n


def _acto(ident):
    t = REALES[ident]
    anuncio = {"identificador": ident, "fecha": t["fecha"], "titulo": t["titulo"], "ambito": "local",
               "tipo_acto": "convocatoria", "alcance": "acceso"}
    return construir_acto(anuncio, {"texto": t["texto"], "tablas": [], "referencias": []})


def test_mijas_dos_turnos_y_extracto_autonomico():
    a = _acto("BOE-A-2026-20494")
    assert a["extraccion"] == "plantilla_local_v1" and a["pendiente"] == []
    assert a["tipo_acto"] == "apertura_plazo"
    assert [(p["numero"], p["denominacion"], p["turno"], p["sistema"]) for p in a["plazas"]] == [
        (2, "Auxiliar Administrativo/a", "libre", "oposicion"),
        (1, "Auxiliar Administrativo/a", "discapacidad", "oposicion")]
    assert a["plazas"][0]["subescala"] == "Auxiliar"
    assert a["total_plazas"] == 3
    bases = [b for b in a["boletines_citados"] if b["papel"] == "bases"][0]
    assert (bases["boletin"], bases["numero"], bases["fecha"]) == ("Boletín Oficial de la Provincia de Málaga", "40", "2026-02-27")
    extracto = [b for b in a["boletines_citados"] if b["papel"] == "extracto"][0]
    assert extracto["boletin"] == "Boletín Oficial de la Junta de Andalucía" and extracto["numero"] == "172"
    assert a["plazo"]["dias"] == 10 and a["plazo"]["tipo"] == "habiles" and a["plazo"]["fin_estimado"] == "2026-10-19"


def test_santa_cruz_clase_media():
    a = _acto("BOE-A-2026-20436")
    p = a["plazas"][0]
    assert (p["numero"], p["denominacion"], p["escala"], p["subescala"], p["clase"]) == (
        3, "Trabajador/a Social", "Administración Especial", "Técnica", "Media")
    assert p["sistema"] == "concurso-oposicion" and p["turno"] == "libre"
    assert a["plazo"]["fin_estimado"] == "2026-10-30"


def test_pedraza_laboral_bases_en_autonomico_dias_naturales():
    a = _acto("BOE-A-2026-20631")
    p = a["plazas"][0]
    assert p["regimen"] == "laboral_fijo" and p["numero"] == 1
    assert a["boletines_citados"][0]["boletin"] == "Boletín Oficial de Castilla y León"
    assert a["plazo"]["tipo"] == "naturales" and a["plazo"]["fin_estimado"] == "2026-10-26"


def test_consorcio_alicante_mixto_es_acceso():
    a = _acto("BOE-A-2026-21264")
    assert a["total_plazas"] == 12
    assert {p["turno"] for p in a["plazas"]} == {"promocion_interna", "libre"}
    assert a["alcance"] == "acceso"


def test_olula_todo_promocion_interna_sale_del_alcance():
    a = _acto("BOE-A-2026-21902")
    assert a["alcance"] == "promocion_interna"
    assert a["plazo"]["fin_estimado"] == "2026-11-18"


def test_sin_texto_queda_pendiente():
    a = construir_acto({"identificador": "BOE-A-2026-1", "fecha": "2026-10-01", "ambito": "estatal"}, None)
    assert a["pendiente"] == ["texto"]


def test_texto_sin_datos_personales():
    xml = """<documento><metadatos><titulo>Lista</titulo><fecha_publicacion>20261001</fecha_publicacion></metadatos>
    <analisis><referencias><anteriores><anterior referencia="BOE-A-2026-100"><palabra>CORRECCIÓN</palabra>
    <texto>de errores de la Resolución</texto></anterior></anteriores></referencias></analisis>
    <texto><p>Se aprueba la lista provisional.</p><p>D. Fulano, con DNI ***1234**, queda nombrado.</p>
    <table><tr><td>Apellidos y nombre</td><td>DNI</td></tr><tr><td>Pérez, Ana</td><td>***5678**</td></tr>
    <tr><td>López, Juan</td><td>***9012**</td></tr></table>
    <table><tr><td>Especialidad</td><td>Plazas</td></tr><tr><td>Matemáticas</td><td>12</td></tr></table></texto></documento>"""
    d = texto_plano(xml.encode())
    assert "Fulano" not in d["texto"] and d["parrafos_omitidos_por_datos_personales"] == 1
    personal, plazas = d["tablas"]
    assert personal == {"filas": 2, "cabecera": ["Apellidos y nombre", "DNI"], "datos_personales": True}
    assert plazas["contenido"][1] == ["Matemáticas", "12"]
    assert d["referencias"][0]["referencia"] == "BOE-A-2026-100"
    assert "Pérez" not in json.dumps(d, ensure_ascii=False)


def test_bop_sin_numero_y_extracto_dogc():
    t = ("En el «Boletín Oficial de la Provincia de Barcelona», de 25 de junio de 2026, se han publicado las bases que han "
         "de regir la convocatoria para proveer:\nUna plaza de Arquitecto/a, perteneciente a la escala de Administración "
         "Especial, subescala Técnica y clase Superior, por el sistema de concurso-oposición, en turno libre.\n"
         "Se ha publicado, asimismo, un extracto de la convocatoria en el «Diari Oficial de la Generalitat de Catalunya» "
         "número 9698, de 2 de julio de 2026.\nEl plazo de presentación de solicitudes será de veinte días hábiles a contar "
         "desde el siguiente al de la publicación de esta resolución en el «Boletín Oficial del Estado».")
    r = extraer_local(t, "2026-07-10")
    assert r["pendiente"] == []
    bases = r["boletines_citados"][0]
    assert (bases["boletin"], bases["numero"], bases["fecha"], bases["papel"]) == (
        "Boletín Oficial de la Provincia de Barcelona", None, "2026-06-25", "bases")
    assert r["boletines_citados"][1]["papel"] == "extracto"
    assert all(b["boletin"] != "Boletín Oficial del Estado" for b in r["boletines_citados"])


def test_puesto_por_concurso_es_provision():
    t = ("En el «Boletín Oficial de la Provincia de Alicante» número 98, de 27 de mayo de 2026, se han publicado las bases "
         "que han de regir la convocatoria para proveer por concurso:\nUn puesto de Jefatura de Servicio de Recursos "
         "Humanos, perteneciente a la escala de Administración General, subescala Técnica.\nEl plazo de presentación de "
         "solicitudes será de quince días hábiles a contar desde el siguiente al de la publicación de esta resolución en el "
         "«Boletín Oficial del Estado».")
    a = construir_acto({"identificador": "X", "fecha": "2026-07-01", "ambito": "local", "tipo_acto": "convocatoria",
                        "alcance": "acceso"}, {"texto": t, "tablas": [], "referencias": []})
    assert a["pendiente"] == [] and a["alcance"] == "provision_puestos"
    assert a["plazas"][0]["tipo"] == "puesto" and a["plazas"][0]["numero"] == 1


def test_rectificacion_de_bases():
    t = ("En el «Boletín Oficial de la Provincia de Tarragona», de 4 de junio de 2026, se han publicado las bases que han de "
         "regir la convocatoria para proveer:\nDos plazas de Técnico/a de Administración General, pertenecientes a la escala "
         "de Administración General, subescala Técnica y clase Superior, por el sistema de concurso-oposición, en turno libre.\n"
         "Dichas bases fueron rectificadas en los términos publicados en el «Boletín Oficial de la Provincia de Tarragona», "
         "de 22 de junio de 2026.\nEl plazo de presentación de solicitudes será de veinte días hábiles a contar desde el "
         "siguiente al de la publicación de esta resolución en el «Boletín Oficial del Estado».")
    r = extraer_local(t, "2026-07-10")
    assert [b["papel"] for b in r["boletines_citados"]] == ["bases", "rectificacion"]


def test_correccion_apunta_al_anuncio_original():
    t = ("Advertido error en la inserción de la Resolución de 24 de junio de 2026, del Ayuntamiento de Zahara (Cádiz), "
         "referente a la convocatoria para proveer una plaza, publicada en el «Boletín Oficial del Estado» número 159, "
         "de 1 de julio de 2026 (BOE-A-2026-14275), se procede a su rectificación:")
    a = construir_acto({"identificador": "BOE-A-2026-15000", "fecha": "2026-07-06", "ambito": "local",
                        "tipo_acto": "correccion"}, {"texto": t, "tablas": [], "referencias": []})
    assert a["refiere_a"] == ["BOE-A-2026-14275"] and a["tipo_acto"] == "correccion"


def test_turno_restringido_no_es_acceso_libre():
    t = ("En el «Boletín Oficial de la Provincia de Salamanca» número 183, de 22 de septiembre de 2026, se han publicado "
         "las bases que han de regir la convocatoria para proveer:\nCinco plazas de Administrativo/a, pertenecientes a la "
         "escala de Administración General/Especial, subescala Administrativa, por el sistema de concurso-oposición, en "
         "turno restringido.\nEl plazo de presentación de solicitudes será de veinte días hábiles a contar desde el siguiente "
         "al de la publicación de esta resolución en el «Boletín Oficial del Estado».")
    a = construir_acto({"identificador": "X", "fecha": "2026-10-01", "ambito": "local", "tipo_acto": "convocatoria"},
                       {"texto": t, "tablas": [], "referencias": []})
    assert a["plazas"][0]["turno"] == "restringido" and a["alcance"] == "promocion_interna" and a["pendiente"] == []


def test_texto_desde_html_permitido():
    # robots.txt del BOE: XML prohibido, HTML permitido. El HTML debe dar lo mismo que el XML.
    from motor.boe.texto import texto_plano_html
    d = texto_plano_html((Path(__file__).parent / "fixtures" / "boe_txt_BOE-A-2026-21007.html").read_bytes())
    assert d["titulo"].startswith("Resolución de 2 de octubre de 2026, de la Diputación Foral de Álava")
    assert (d["fecha_publicacion"], d["departamento"], d["rango"]) == ("20261009", "Administración Local", "Resolución")
    assert "nuevo plazo de presentación de solicitudes de veinte días hábiles" in d["texto"]
    assert d["referencias"] == [{"sentido": "anteriores", "referencia": "BOE-A-2026-12456", "relacion": "AMPLÍA",
                                 "texto": "el plazo de presentación de solicitudes en el proceso selectivo convocado por "
                                          "Resolución de 22 de mayo de 2026"}]
