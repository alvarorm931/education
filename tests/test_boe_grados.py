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
    assert bg.tipo_caracter("Asignaturas de Formación Básica.") == "basica"
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


def test_semestres_lado_a_lado_y_cabecera_en_segunda_fila():
    t = {"contenido": [["Primer semestre", "Segundo semestre"],
                       ["Asignatura", "Ects", "Carácter", "Asignatura", "Ects", "Carácter"],
                       ["Fundamentos de Física I.", "6", "Básica.", "Fundamentos de Física II.", "6", "Básica."],
                       ["Cálculo I.", "6", "Básica.", "Óptica.", "6", "Obligatoria."]]}
    filas = bg.plan([t])
    assert [(f["nombre"], f["semestre"], f["tipo"]) for f in filas] == [
        ("Fundamentos de Física I", 1, "basica"), ("Cálculo I", 1, "basica"),
        ("Fundamentos de Física II", 2, "basica"), ("Óptica", 2, "obligatoria")]


def test_columnas_de_creditos_y_caracter_cambiadas():
    t = {"contenido": [["Materia", "Asignatura", "Carácter", "ECTS", "Curso"],
                       ["Marketing.", "Fundamentos de Marketing.", "6", "OB", "1.º"],
                       ["Política de Producto.", "6", "OB", "2.º"]]}
    filas = bg.plan([t])
    assert [(f["nombre"], f["creditos"], f["tipo"], f["curso"]) for f in filas] == [
        ("Fundamentos de Marketing", 6, "obligatoria", 1), ("Política de Producto", 6, "obligatoria", 2)]


def _t(filas):
    return {"filas": len(filas), "contenido": filas, "datos_personales": False}


def test_plan_tipo_por_rotulo_separadores_y_cabecera_sin_rotulo():
    from motor.grados.boe_grados import plan, tipo_de_rotulo
    assert tipo_de_rotulo("Total de créditos de formación básica = 60") == "basica"
    assert tipo_de_rotulo("Básicas y obligatorias") is None
    t1 = _t([["Total de créditos de formación básica = 60"], ["Asignatura", "Créditos", "Curso"],
             ["Cálculo.", "6", "1"], ["Física.", "6", "1"]])
    t2 = _t([["", "ECTS", "Tipo"], ["Primer semestre"], ["Química.", "6", "OB"], ["Segundo semestre"],
             ["Geología.", "6", "OB"]])
    t3 = _t([["Módulo", "Asignatura", "Créd.", "Carácter", "Curso", "Org. Temp."],
             ["Mates", "Álgebra.", "6", "Básica.", "1.º", "1S"]])
    p = {x["nombre"]: x for x in plan([t1, t2, t3])}
    assert p["Cálculo"]["tipo"] == "basica" and p["Cálculo"]["curso"] == 1
    assert p["Química"]["semestre"] == 1 and p["Geología"]["semestre"] == 2 and p["Geología"]["tipo"] == "obligatoria"
    assert p["Álgebra"]["creditos"] == 6 and p["Álgebra"]["semestre"] == 1 and p["Álgebra"]["tipo"] == "basica"


def test_plan_tipo_por_pie_y_por_suma_de_tabla():
    from motor.grados.boe_grados import plan
    obl = _t([["Asignatura", "Créditos", "Curso"], ["Sociedad.", "6", "2"], ["Penal.", "6", "2"],
              ["Total de créditos de formación obligatoria.", "12", ""]])
    fb = _t([["Ámbito de conocimiento", "Asignatura", "Créditos"], ["Derecho.", "Constitucional.", "6"],
             ["Derecho.", "Civil.", "6"]])
    dist = {"formacion_basica": 12, "obligatorias": 12, "optativas": 6, "total": 30}
    p = {x["nombre"]: x for x in plan([obl, fb], dist)}
    assert p["Sociedad"]["tipo"] == "obligatoria"
    # la suma de la tabla sin tipo (12) es la de básicas y obligatorias, pero obligatorias ya la trae otra tabla
    assert p["Civil"]["tipo"] == "basica" and p["Civil"]["tipo_por_suma_de_tabla"]


def test_separar_planes_de_una_resolucion_con_varios():
    from motor.grados.boe_grados import separar_planes
    dist = lambda b, o: _t([["Tipo de materia", "Créditos"], ["Formación básica.", str(b)], ["Obligatorias.", str(o)],  # noqa: E731
                            ["Optativas.", "30"], ["Total.", "240"]])
    asig = _t([["Asignatura", "ECTS"], ["Química.", "6"]])
    texto = ("Ha resuelto publicar los planes:\n2504437 Graduado o Graduada en Ciencias Ambientales.\nANEXO I\n"
             "Plan de estudios conducente al título de Graduado o Graduada en Ciencias Ambientales\nRama de Ciencias\n"
             "ANEXO II\nGraduado o Graduada en Farmacia por la Universidad de Alcalá\n")
    partes = separar_planes({"identificador": "X", "texto": texto, "tablas": [dist(60, 120), asig, dist(60, 150), asig]})
    assert [p["titulo_grado"] for p in partes] == ["Graduado o Graduada en Ciencias Ambientales",
                                                    "Graduado o Graduada en Farmacia"]
    assert len(partes[1]["tablas"]) == 2 and "Farmacia" in partes[1]["texto"]
    # si no cuadran tablas y títulos, el documento queda entero
    assert separar_planes({"identificador": "X", "texto": texto, "tablas": [dist(60, 120), asig]})[0].get("titulo_grado") is None


def test_comprobacion_y_materias_mixtas():
    from motor.grados.boe_grados import medir_plan, tipo_caracter
    assert tipo_caracter("Obligatoria / Optativa") is None and tipo_caracter("Formación básica (6) (Ciencias)") is None
    dist = _t([["Tipo de materia", "Créditos"], ["Formación básica.", "12"], ["Obligatorias.", "6"],
               ["Prácticas externas.", "6"], ["Trabajo fin de grado.", "6"], ["Total.", "30"]])
    asig = _t([["Asignatura", "Créditos", "Carácter"], ["Cálculo.", "6", "FB"], ["Álgebra.", "6", "FB"],
               ["Física.", "6", "OB"]])
    assert medir_plan({"tablas": [dist, asig], "texto": ""})["comprobacion"] == "basicas_y_obligatorias"
    asig2 = _t(asig["contenido"] + [["Prácticas.", "6", "PE"], ["Trabajo Fin de Grado.", "6", "TFG"]])
    assert medir_plan({"tablas": [dist, asig2], "texto": ""})["comprobacion"] == "completo"


def test_plan_con_asignaturas_dentro_de_las_celdas():
    from motor.grados.boe_grados import plan
    t = _t([["", "Semestre 3", "Semestre 4"],
            ["Curso 2", "ECTS: 12. Asignaturas: – Mundo medieval (6 ECTS). – Inglés B2.1 (6 ECTS).",
             "ECTS: 6. Asignaturas: – Mundo contemporáneo (O)."]])
    p = {x["nombre"]: x for x in plan([t])}
    assert p["Mundo medieval"]["creditos"] == 6 and p["Mundo medieval"]["curso"] == 2 and p["Mundo medieval"]["semestre"] == 1
    assert p["Inglés B2.1"]["creditos"] == 6
    assert p["Mundo contemporáneo"]["tipo"] == "obligatoria" and p["Mundo contemporáneo"]["semestre"] == 2


def test_cabecera_con_tipo_y_codigos_de_mencion_y_tabla_resumen_excluida():
    from motor.grados.boe_grados import plan, tipo_caracter
    assert tipo_caracter("OBM") == "optativa" and tipo_caracter("Obligatoria de mención") == "optativa"
    resumen = _t([["Materias", "Créditos"], ["Formación Básica.", "60"], ["Obligatorias.", "120"], ["Optativas.", "36"]])
    opt = _t([["Asignaturas optativas", "Créditos"], ["1. Psicología del deporte", "6"]])
    p = plan([resumen, opt])
    assert [(x["nombre"], x["tipo"]) for x in p] == [("1. Psicología del deporte", "optativa")]


def test_menciones_limpias_y_en_tablas():
    from motor.grados.boe_grados import menciones
    assert menciones("Mención en Turismo Digital y Mención en Sostenibilidad en Destinos. Mención en Psicología de la "
                     "Salud al superarse las asignaturas. Mención en Estudios Jurídicos / International Legal Studies.") == [
        "Turismo Digital", "Sostenibilidad en Destinos", "Psicología de la Salud", "Estudios Jurídicos"]
    assert menciones("", [_t([["Módulo", "x"], ["Módulo Optativo. Mención en Operación Náutica del Buque.", "6"]])]) == [
        "Operación Náutica del Buque"]


def test_distribucion_en_texto_y_tabla_de_asignaturas_que_no_es_distribucion():
    from motor.grados.boe_grados import distribucion_creditos, distribucion_de_texto
    d = distribucion_de_texto("Créditos de formación básica: 60.\nCréditos obligatorios: 126.\nCréditos optativos: 42.\n"
                              "Trabajo final de grado: 12.\nCréditos totales: 240.")
    assert d == {"formacion_basica": 60, "obligatorias": 126, "optativas": 42, "tfg": 12, "total": 240}
    asignaturas = _t([["Asignatura", "ECTS"], ["Prácticas tuteladas I.", "12"], ["Optativa.", "6"],
                      ["Trabajo fin de grado.", "6"], ["Obligatoria de enfermería.", "6"], ["Anatomía.", "6"],
                      ["Fisiología.", "6"], ["Bioquímica.", "6"]])
    assert distribucion_creditos([asignaturas]) is None
    con_obs = _t([["Tipo de materias", "Créditos", "Observaciones"], ["Formación Básica", "60", ""],
                  ["Obligatorias", "111", ""], ["Optativas", "9", ""], ["Total", "240", ""]])
    assert distribucion_creditos([con_obs])["obligatorias"] == 111


def test_tabla_sin_creditos_y_crd_y_erratas():
    from motor.grados.boe_grados import plan, tipo_acto
    assert tipo_acto("Corrección de erratas de la Resolución de 30 de noviembre de 2010, de la Universidad X, por la que "
                     "se publica el plan de estudios de Graduado en Arquitectura.") == "correccion"
    sin = _t([["Módulo", "Materia", "Asignatura", "Carácter"], ["Básico", "Sociología.", "Sociología.", "Formación básica."]])
    crd = _t([["Asignatura", "Carácter", "CRD"], ["Historia.", "Obligatoria.", "6"]])
    p = {x["nombre"]: x for x in plan([sin, crd])}
    assert p["Sociología"]["tipo"] == "basica" and p["Sociología"]["creditos"] is None
    assert p["Historia"]["creditos"] == 6


def test_lecturas_que_quitan_lo_que_sobra_o_ponen_lo_que_falta():
    from motor.grados.boe_grados import medir_plan
    dist = _t([["Tipo de materia", "Créditos"], ["Formación básica.", "12"], ["Obligatorias.", "12"],
               ["Optativas.", "6"], ["Total.", "30"]])
    plan_ = _t([["Asignatura", "Créditos", "Carácter"], ["A.", "6", "FB"], ["B.", "6", "FB"], ["C.", "6", "OB"],
                ["D.", "6", "OB"]])
    itinerario = _t([["Itinerario", "Asignatura", "Créditos", "Carácter"], ["Mención X", "E.", "6", "OB"]])
    m = medir_plan({"tablas": [dist, plan_, itinerario], "texto": ""})
    assert m["comprobacion"] == "completo" and m["interpretacion"] == "alternativa"
    sin = _t([["Asignatura", "Créditos"], ["F.", "6"], ["G.", "6"]])
    fb = _t([["Asignatura", "Créditos", "Carácter"], ["A.", "6", "FB"], ["B.", "6", "FB"]])
    m = medir_plan({"tablas": [dist, fb, sin], "texto": ""})
    assert m["comprobacion"] and {x["nombre"]: x["tipo"] for x in m["filas_plan"]}["F"] == "obligatoria"


def test_modulo_de_menciones_sin_caracter_cuenta_como_optativo():
    from motor.grados.boe_grados import medir_plan
    dist = _t([["Tipo de materia", "Créditos"], ["Formación básica.", "12"], ["Obligatorias.", "12"],
               ["Optativas.", "6"], ["Total.", "30"]])
    plan_ = _t([["Módulo", "Asignatura", "Créditos"], ["Formación Básica", "A.", "6"], ["Formación Básica", "B.", "6"],
                ["Didáctico", "C.", "6"], ["Didáctico", "D.", "6"], ["Menciones", "E.", "6"], ["Menciones", "F.", "6"],
                ["Optatividad", "G.", "6"]])
    m = medir_plan({"tablas": [dist, plan_], "texto": ""})
    assert m["comprobacion"] == "completo" and m["interpretacion"] == "alternativa"
    tipos = {x["nombre"]: x["tipo"] for x in m["filas_plan"]}
    assert tipos["C"] == "obligatoria" and tipos["E"] == "optativa"


def test_columnas_de_modulo_con_denominacion_y_ects():
    from motor.grados.boe_grados import _columnas
    assert _columnas(["Denominación Módulo", "ECTS", "Denominación materia", "ECTS", "Carácter", "Curso"]) == {
        "modulo": 0, "nombre": 2, "creditos": 3, "caracter": 4, "curso": 5}
    c = _columnas(["ECTS módulo", "Denominación módulo", "Denominación materia", "Carácter", "ECTS"])
    assert c["nombre"] == 2 and c["creditos"] == 4 and c["modulo"] == 1


def test_plan_por_materias_con_optativas_por_asignaturas_se_comprueba_por_materias():
    from motor.grados.boe_grados import medir_plan
    dist = _t([["Tipo de materia", "Créditos"], ["Formación básica.", "12"], ["Obligatorias.", "12"],
               ["Optativas.", "6"], ["Total.", "30"]])
    materias = _t([["Materia", "Créditos", "Carácter"], ["Matemáticas.", "12", "FB"], ["Física.", "12", "OB"]])
    optativas = _t([["Asignatura", "Créditos", "Carácter"], ["Astronomía.", "6", "OP"]])
    m = medir_plan({"tablas": [dist, materias, optativas], "texto": ""})
    assert m["comprobacion"] == "completo" and m["nivel_comprobado"] == "materia"


def test_leyenda_de_codigos_del_propio_plan():
    from motor.grados.boe_grados import distribucion_creditos, leyenda, plan
    doc = {"texto": "FB: Formación Básica, O: Obligatoria, OE: Obligatoria de la Especialidad, P: Optativa, "
                    "TF: Trabajo Fin de Grado, Cuat: Cuatrimestre.", "tablas": []}
    assert leyenda(doc) == {"fb": "basica", "o": "obligatoria", "oe": "obligatoria", "p": "optativa", "tf": "tfg"}
    dist = _t([["Tipo de materia", "Créditos"], ["F", "Formación Básica", "60"], ["O", "Obligatorias", "144"],
               ["P", "Optativas", "24"], ["T", "Trabajo fin de grado", "12"], ["", "Total", "240"]])
    assert distribucion_creditos([dist])["formacion_basica"] == 60
    codigos = leyenda({"texto": "", "tablas": [dist]})
    assert codigos["p"] == "optativa" and codigos["f"] == "basica"
    asig = _t([["Asignatura", "Tipo", "Créditos"], ["Economía.", "P", "6"]])
    assert plan([asig], None, codigos)[0]["tipo"] == "optativa"


def test_celdas_combinadas_a_izquierda_y_derecha():
    from motor.grados.boe_grados import plan
    t = _t([["Módulo", "Materia", "Asignaturas vinculadas", "ECTS", "Curso", "Organización temporal", "Carácter"],
            ["M1: Formación básica.", "Idioma moderno I.", "Alemán I.", "6", "1.º", "Semestre 1.º", "Básica."],
            ["Alemán II.", "6", "1.º", "Semestre 2.º"]])
    p = {x["nombre"]: x for x in plan([t])}
    assert p["Alemán II"]["creditos"] == 6 and p["Alemán II"]["tipo"] == "basica" and p["Alemán II"]["semestre"] == 2


def test_bloques_lado_a_lado_que_no_empiezan_por_el_nombre():
    from motor.grados.boe_grados import plan
    t = _t([["Curso", "Cuatrimestre", "Asignatura", "Tipo", "ECTS", "", "Curso", "Cuatrimestre", "Asignatura", "Tipo", "ECTS"],
            ["1.º", "1.º", "Lengua.", "FB", "6", "", "1.º", "2.º", "Historia.", "FB", "6"]])
    p = {x["nombre"]: x for x in plan([t])}
    assert p["Lengua"]["semestre"] == 1 and p["Historia"]["semestre"] == 2 and p["Historia"]["tipo"] == "basica"


def test_revision_independiente_tfg_totales_semestres_y_llamadas():
    from motor.grados.boe_grados import medir_plan, plan
    dist = _t([["Tipo de materia", "Créditos"], ["Formación básica.", "12"], ["Obligatorias.", "6"],
               ["Prácticas externas.", "6"], ["Trabajo fin de grado.", "6"], ["Total.", "30"]])
    tabla = _t([["Asignatura", "Créditos", "Carácter", "Semestre"],
                ["Álgebra (1)", "6", "Básica", "1"], ["Cálculo", "6", "Básica", "2"],
                ["Física", "6", "Obligatoria", "3"], ["Practicum", "6", "Obligatoria", "7 u 8"],
                ["Trabajo Fin de Grado", "6", "Obligatoria", "8"], ["Total", "30", "", ""]])
    m = medir_plan({"tablas": [dist, tabla], "texto": ""})
    filas = {x["nombre"]: x for x in m["filas_plan"]}
    assert set(filas) == {"Álgebra", "Cálculo", "Física", "Practicum", "Trabajo Fin de Grado"}  # sin «Total» ni «(1)»
    # el practicum y el TFG con carácter «Obligatoria» van a su tipo porque la tabla de créditos los separa
    assert filas["Practicum"]["tipo"] == "practicas" and filas["Trabajo Fin de Grado"]["tipo"] == "tfg"
    # semestres del 1 al 8: el 1 y el 2 son de primero; «7 u 8» es de cuarto, sin semestre
    assert (filas["Álgebra"]["curso"], filas["Álgebra"]["semestre"]) == (1, 1)
    assert (filas["Practicum"]["curso"], filas["Practicum"]["semestre"]) == (4, None)
    assert m["comprobacion"] == "completo"
    # una fila con la mitad de los créditos del grado no es una asignatura
    t2 = _t([["Asignatura", "Créditos", "Carácter"], ["A.", "6", "Básica"], ["–", "20", "Obligatoria"]])
    assert [x["nombre"] for x in plan([t2], {"total": 30.0, "formacion_basica": 6.0})] == ["A"]
