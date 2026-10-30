from motor.grados import catalogo as cat


def _t(codigo, nivel, nombre, universidad="Granada", unidad="Facultad de Derecho", situacion="Activo", **extra):
    return {"Nivel académico": nivel, "Código de la titulación": codigo, "Nombre de la titulación (RUCT)": nombre,
            "Situación": situacion, "Universidad": universidad, "Tipo de universidad": "Pública", "Unidad": unidad,
            "Tipo de unidad": "Público", "Presencialidad de la titulación": "Estudio presencial",
            "Idioma extranjero": "No", **extra}


UNIS = [{"Universidad": "Granada", "Código de la universidad": "008", "Comunidad autónoma": "Andalucía"},
        {"Universidad": "Málaga", "Código de la universidad": "011", "Comunidad autónoma": "Andalucía"}]
CENTROS = [{"Universidad": "Granada", "Unidad": "Facultad de Derecho", "Código de la unidad": "18012345",
            "Municipio de la unidad": "GRANADA", "Modalidad de la Unidad": "Centro propio"}]
RAMA = [{"Código de la titulación": "2500100", "Rama de la enseñanza": "Ciencias Sociales y Jurídicas",
         "Código ISCED 2013": "0421"}]


def _catalogo(titulaciones):
    return {t["codigo"]: t for t in cat.construir(titulaciones, RAMA, CENTROS, UNIS, "2025-2026")}


def test_nombre_corto():
    assert cat.nombre_corto("Graduado o Graduada en Sociología por la Universidad de A Coruña") == "Sociología"
    assert cat.nombre_corto("Graduado o Graduada en Física por la Universidad de Almería y la Universidad de Granada") == "Física"
    assert cat.nombre_corto("Graduado o Graduada en Gestión y Administración Pública") == "Gestión y Administración Pública"


def test_clases_de_titulo():
    c = _catalogo([
        _t("2500100", "Grado", "Graduado o Graduada en Derecho por la Universidad de Granada"),
        _t("1500200", "Grado", "Graduado o Graduada en Ciencia de Datos por la Universidad de Granada"),
        _t("0021115", "Grado", "Enginyeria de Sistemes de Telecomunicació / Enginyeria Telemàtica (agrupació)"),
        _t("7700001", "Grado", "Grado Abierto UC3M en Ingeniería"),
        _t("9000016", "Grado", "Baccalaureatus in Theología por la Facultad de Teología San Vicente Ferrer"),
        _t("7001000", "Programaciones Conjuntas de Estudios Oficiales", "PCEO Grado en Derecho / Grado en Economía"),
        _t("4318301", "Máster", "Máster Universitario en Algo"),
    ])
    assert "4318301" not in c
    assert c["2500100"]["clase"] == "grado" and c["2500100"]["regimen"] == "RD 1393/2007"
    assert c["1500200"]["regimen"] == "RD 822/2021"
    assert c["0021115"]["clase"] == "agrupacion" and c["0021115"]["codigo_ruct"] is None
    assert c["7700001"]["clase"] == "grado_abierto"
    assert c["9000016"]["clase"] == "eclesiastico"
    assert c["7001000"]["clase"] == "doble" and c["7001000"]["nombre"] == "Derecho y Economía"


def test_union_con_rama_universidad_y_centro():
    t = _catalogo([_t("2500100", "Grado", "Graduado o Graduada en Derecho por la Universidad de Granada")])["2500100"]
    assert t["rama"] == "Ciencias Sociales y Jurídicas" and t["isced_codigo"] == "0421"
    assert t["universidades"] == [{"nombre": "Granada", "codigo": "008", "tipo": "Pública", "comunidad": "Andalucía"}]
    assert t["imparticiones"][0]["unidad_codigo"] == "18012345"
    assert t["imparticiones"][0]["municipio"] == "GRANADA"


def test_doble_grado_unido_con_sus_grados():
    c = _catalogo([
        _t("2500100", "Grado", "Graduado o Graduada en Derecho por la Universidad de Granada"),
        _t("2500101", "Grado", "Graduado o Graduada en Derecho por la Universidad de Granada", situacion="En proceso de extinción"),
        _t("2500300", "Grado", "Graduado o Graduada en Ciencias Ambientales por la Universidad de Granada"),
        _t("2500400", "Grado", "Graduado o Graduada en Periodismo por la Universidad de Málaga", universidad="Málaga"),
        _t("2500500", "Grado", "Graduado o Graduada en Economía / Bachelor in Economics por la Universidad de Granada"),
        _t("7001000", "Programaciones Conjuntas de Estudios Oficiales",
           "PCEO Grado en Derecho/Grado en CC Ambientales"),
        _t("7001001", "Programaciones Conjuntas de Estudios Oficiales",
           "PCEO Grado en Derecho (Granada) / Grado en Periodismo (Málaga)"),
        _t("7001002", "Programaciones Conjuntas de Estudios Oficiales", "PCEO Grado en Economía / Grado en Derecho"),
    ])
    d = c["7001000"]["componentes"]
    # el plan en extinción no hace ambigua la unión: el doble activo va con el grado activo
    assert [x["codigo"] for x in d] == ["2500100", "2500300"]
    d = c["7001001"]["componentes"]
    assert [x["codigo"] for x in d] == ["2500100", "2500400"]
    assert d[1]["universidad"] == "Málaga"
    assert [x["codigo"] for x in c["7001002"]["componentes"]] == ["2500500", "2500100"]


def test_componente_del_doble_por_el_nombre_generico():
    c = _catalogo([
        _t("2500600", "Grado", "Graduado o Graduada en Maestro en Educación Primaria por la Universidad de Granada"),
        _t("2500700", "Grado", "Graduado o Graduada en Maestro en Educación Infantil por la Universidad de Granada"),
        _t("7001003", "Programaciones Conjuntas de Estudios Oficiales",
           "PCEO Grado en Educación Infantil / Grado en Educación Primaria"),
    ])
    assert [x["codigo"] for x in c["7001003"]["componentes"]] == ["2500700", "2500600"]


def test_componente_del_doble_por_contencion_del_nombre_solo_si_es_unico():
    c = _catalogo([
        _t("2500800", "Grado", "Graduado o Graduada en Ingeniería Informática por la Universidad de Granada"),
        _t("2500900", "Grado", "Graduado o Graduada en Matemáticas por la Universidad de Granada"),
        _t("2501000", "Grado", "Graduado o Graduada en Física por la Universidad de Granada"),
        _t("2501100", "Grado", "Graduado o Graduada en Ciencias de la Actividad Física y del Deporte por la Universidad de Granada"),
        _t("7001004", "Programaciones Conjuntas de Estudios Oficiales", "PCEO Grado en Informática / Grado en Matemáticas"),
        _t("7001005", "Programaciones Conjuntas de Estudios Oficiales",
           "PCEO Grado en Actividad Física / Grado en Matemáticas"),
    ])
    d = c["7001004"]["componentes"]
    assert d[0]["codigo"] == "2500800" and d[0]["union"] == "por_contencion_del_nombre"
    # «Actividad Física» cabe en dos grados (Física y CAFYD): no se une
    assert c["7001005"]["componentes"][0]["codigo"] is None


def test_clave_union_tolera_variantes_de_escritura():
    assert cat.clave_union("Ingeniería de Organización Industrial") == cat.clave_union("Ingeniería en Organización Industrial")
    assert cat.clave_union("Ciencia y Tecnología de Alimentos") == cat.clave_union("Ciencia y Tecnología de los Alimentos")
    assert cat.clave_union("CC Ambientales") == cat.clave_union("Ciencias Ambientales")
    assert cat.clave_union("Derecho") != cat.clave_union("Criminología")


def test_nombre_corto_de_los_planes_antiguos_del_boe():
    from motor.grados.catalogo import nombre_corto
    assert nombre_corto("Graduado en Contabilidad y Finanzas") == "Contabilidad y Finanzas"
    assert nombre_corto("Graduado/a en Derecho por la Universidad de Murcia") == "Derecho"
    assert nombre_corto("Graduado Maestro en Educación Infantil") == "Maestro en Educación Infantil"
