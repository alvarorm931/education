from motor.grados import boe_grados as bg


def test_tipo_de_acto():
    t = "Resolución de 20 de diciembre de 2021, de la Universidad Europea de Madrid, por la que se publica el plan de estudios de Graduado o Graduada en Logopedia."
    assert bg.tipo_acto(t) == "plan"
    assert bg.tipo_acto(t.replace("el plan", "la modificación del plan")) == "modificacion"
    assert bg.tipo_acto("Resolución … por la que se corrigen errores en la de 17 de julio de 2019, por la que se publica la modificación del plan de estudios de Graduado en Podología.") == "correccion"
    assert bg.tipo_acto("Resolución … por la que se publica el Acuerdo del Consejo de Ministros … por el que se establece el carácter oficial de determinados títulos de Grado y su inscripción en el Registro de Universidades, Centros y Títulos.") == "oficialidad"
    assert bg.tipo_acto("Resolución … por la que se publica el plan de estudios de Máster Universitario en Abogacía.") is None


def test_actos_nombre_y_cambio_de_denominacion():
    filas = [
        {"identificador": "BOE-A-1", "fecha": "2022-01-05", "titulo": "Resolución de 20 de diciembre de 2021, de la Universidad Europea de Madrid, por la que se publica el plan de estudios de Graduado o Graduada en Logopedia."},
        {"identificador": "BOE-A-2", "fecha": "2022-02-10", "titulo": "Resolución de 10 de febrero de 2022, de la Universidad Complutense de Madrid, por la que se publica el cambio de denominación del título de Graduado o Graduada en Física por el de Graduado o Graduada en Física Aplicada y el plan de estudios actualizado."},
        {"identificador": "BOE-A-3", "fecha": "2022-09-06", "titulo": "Resolución de 6 de septiembre de 2022, de la Universidad Internacional Villanueva, por la que se publican planes de estudio de Graduado o Graduada."},
    ]
    a = {x["identificador"]: x for x in bg.actos(filas)}
    assert a["BOE-A-1"]["titulo_grado"] == "Graduado o Graduada en Logopedia"
    assert a["BOE-A-1"]["universidad"] == "Universidad Europea de Madrid"
    assert a["BOE-A-2"]["tipo"] == "denominacion" and a["BOE-A-2"]["titulo_grado"] == "Graduado o Graduada en Física Aplicada"
    assert a["BOE-A-3"]["varios_planes"] and a["BOE-A-3"]["titulo_grado"] is None


def test_altas_del_acuerdo():
    texto = "Universidad de Almería\n1500438 Graduado o Graduada en Inteligencia Artificial y Ciberseguridad por la Universidad de Almería.\nUniversidad de Granada\n1500500 Graduado o Graduada en Física por la Universidad de Granada"
    a = bg.altas(texto)
    assert [(x["codigo_ruct"], x["universidad"]) for x in a] == [("1500438", "Universidad de Almería"), ("1500500", "Universidad de Granada")]


def test_tipo_caracter():
    assert bg.tipo_caracter("FB. Ciencias Sociales y Jurídicas.") == "basica"
    assert bg.tipo_caracter("Formación básica (Ciencias Sociales y Jurídicas).") == "basica"
    assert bg.tipo_caracter("BS") == "basica"
    assert bg.tipo_caracter("Obligatoria .") == "obligatoria"
    assert bg.tipo_caracter("OP") == "optativa"
    assert bg.tipo_caracter("PAE") == "practicas"
    assert bg.tipo_caracter("Prácticas externas (obligatorias).") == "practicas"
    assert bg.tipo_caracter("Trabajo de Fin de Grado.") == "tfg"
    assert bg.tipo_caracter("6") is None


DISTRIBUCION = {"contenido": [["Tipo de materia", "Créditos"], ["Básicas (FB).", "60"], ["Obligatorias (OB).", "114"],
                              ["Optativas (OP).", "36"], ["Prácticas Externas (PE).", "24"],
                              ["Trabajo Fin de Grado (TFG).", "6"], ["Total.", "240"]]}


def test_distribucion_de_creditos():
    d = bg.distribucion_creditos([DISTRIBUCION])
    assert d == {"formacion_basica": 60, "obligatorias": 114, "optativas": 36, "practicas_externas": 24, "tfg": 6, "total": 240}
    sin_total = {"contenido": [["Tipo de asignatura", "Créditos"], ["Formación básica.", "60"], ["Obligatorias.", "156"],
                               ["Optativas.", "18"], ["Trabajo fin de grado.", "6"], ["Créditos totales.", "240"]]}
    assert bg.distribucion_creditos([sin_total])["total"] == 240
    # «Materias Obligatorias (excepto Prácticas y TFG)» es obligatoria, no TFG
    raro = {"contenido": [["Tipo", "Créditos"], ["Materias Básicas.", "60"],
                          ["Materias Obligatorias (excepto Prácticas y Trabajo Fin de Grado).", "150"], ["Total.", "240"]]}
    assert bg.distribucion_creditos([raro])["obligatorias"] == 150


def test_plan_dos_columnas_de_creditos_celdas_combinadas_y_sin_duplicados():
    por_rama = {"contenido": [["Rama de conocimiento", "Materia RD 1393/2007", "Asignatura", "Créditos"],
                              ["Ciencias Sociales y Jurídicas", "Educación.", "Teoría de la educación.", "6"],
                              ["Didáctica general.", "6"]]}
    completo = {"contenido": [["Materia", "ECTS", "Asignatura", "ECTS", "Carácter", "Curso", "Semestre"],
                              ["Fundamentos de la educación.", "60", "Teoría de la educación.", "6", "FB", "1", "1"],
                              ["Didáctica general.", "6", "FB", "1.º", "2.º"],
                              ["Pedagogía Social.", "32", "Procesos de inclusión social.", "6", "OB", "2", "1"],
                              ["Total", "", "", "72", "", "", ""]]}
    filas = bg.plan([DISTRIBUCION, por_rama, completo])
    assert [f["nombre"] for f in filas] == ["Teoría de la educación", "Didáctica general", "Procesos de inclusión social"]
    assert all(f["creditos"] == 6 for f in filas)  # la columna de la asignatura, no la de la materia (60, 32)
    assert [f["modulo"] for f in filas] == ["Fundamentos de la educación", "Fundamentos de la educación", "Pedagogía Social"]
    assert [(f["curso"], f["semestre"], f["tipo"]) for f in filas] == [(1, 1, "basica"), (1, 2, "basica"), (2, 1, "obligatoria")]
    assert all(f["tabla"] == 2 for f in filas)  # se queda la fila de la tabla más completa


def test_numero_orden():
    assert [bg.numero_orden(x) for x in ("1", "1.º", "Primero", "S2", "2.º cuatrimestre", "Anual", "")] == [1, 1, 1, 2, 2, None, None]


def test_menciones():
    assert bg.menciones("Mención en Educación Física. Mención en Lengua Extranjera: Inglés; otra") == \
        ["Educación Física", "Lengua Extranjera"]
