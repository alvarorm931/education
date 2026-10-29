from motor.estudios import boe_masters as b


def test_tipo_de_acto():
    assert b.tipo_acto("Resolución de 5 de noviembre de 2025, de la Universidad Europea de Madrid, por la que se publica "
                       "el plan de estudios de Máster Universitario en Descubrimiento de Fármacos.") == "plan"
    assert b.tipo_acto("Resolución de 4 de octubre de 2024, de la Universidad Internacional de Cataluña, por la que se publica "
                       "la modificación del plan de estudios de Máster Universitario en Fisioterapia.") == "plan_modificacion"
    assert b.tipo_acto("Resolución de 9 de octubre de 2025, de la Secretaría General de Universidades, por la que se publica el "
                       "Acuerdo de Consejo de Ministros, por el que se establece el carácter oficial de determinados títulos de "
                       "Máster y su inscripción en el Registro de Universidades, Centros y Títulos.") == "oficialidad"
    assert b.tipo_acto("Resolución por la que se publica el Convenio con la Universidad de Cádiz, para el Máster en Gestión Portuaria.") is None


def test_actos_universidad_y_titulo():
    a = b.actos([{"identificador": "BOE-A-2025-23365", "fecha": "2025-11-18",
                  "titulo": "Resolución de 5 de noviembre de 2025, de la Universidad Europea de Madrid, por la que se publica "
                            "el plan de estudios de Máster Universitario en Descubrimiento de Fármacos."}])[0]
    assert a["universidad"] == "Universidad Europea de Madrid"
    assert a["titulo_master"] == "Máster Universitario en Descubrimiento de Fármacos"


def test_altas_de_un_acuerdo():
    texto = ("ANEXO\nSección I\nCUNEF Universidad\n3500406 Máster Universitario en Gestión/Master in Management (MIM).\n"
             "Universidad Complutense de Madrid\n3500353 Máster Universitario en Inteligencia Artificial.")
    x = b.altas(texto)
    assert [(a["codigo_ruct"], a["universidad"]) for a in x] == [("3500406", "CUNEF Universidad"),
                                                                ("3500353", "Universidad Complutense de Madrid")]
    assert x[1]["nombre"] == "Máster Universitario en Inteligencia Artificial"


def test_tabla_con_celdas_combinadas():
    tabla = {"contenido": [["Módulo", "Asignatura", "Tipo", "Créditos"],
                           ["Metodología de investigación.", "Fundamentos y diseños de investigación.", "OBL", "5"],
                           ["Metodología cuantitativa.", "OBL", "6"],
                           ["Total.", "", "", "60"]]}
    filas = b.asignaturas([tabla])
    assert [(f["modulo"], f["nombre"], f["creditos"]) for f in filas] == [
        ("Metodología de investigación", "Fundamentos y diseños de investigación", 5.0),
        ("Metodología de investigación", "Metodología cuantitativa", 6.0)]


def test_tabla_resumen_se_descarta():
    assert b.asignaturas([{"contenido": [["Tipo de materia", "Créditos ECTS"], ["Obligatoria (OBL).", "21"]]}]) == []
