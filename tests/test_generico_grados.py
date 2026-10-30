from motor.grados import generico as gen


def test_nombre_base():
    assert gen.nombre_base("Derecho / Bachelor in Law") == "Derecho"
    assert gen.nombre_base("Economía / Economics") == "Economía"
    assert gen.nombre_base("Maestro o Maestra en Educación Infantil") == "Educación Infantil"
    assert gen.nombre_base("Maestro/a de Educación Primaria") == "Educación Primaria"
    assert gen.nombre_base("Administración y Dirección de Empresas (ADE)") == "Administración y Dirección de Empresas"
    assert gen.nombre_base("Derecho (Plan Nuevo)") == "Derecho"
    # una barra que no separa una traducción no se corta
    assert gen.nombre_base("Gallego/Portugués: Estudios Lingüísticos") == "Gallego/Portugués: Estudios Lingüísticos"


def test_mismo_generico_con_otra_escritura():
    assert gen.clave_generico("Ingeniería de Diseño Industrial y Desarrollo de Productos") == \
        gen.clave_generico("Ingeniería en Diseño Industrial y Desarrollo del Producto")
    assert gen.clave_generico("Ingeniería en Tecnología Industrial") == gen.clave_generico("Ingeniería en Tecnologías Industriales")
    assert gen.clave_generico("Derecho") != gen.clave_generico("Derecho Canónico")


def _t(codigo, nombre, uni, clase="grado", componentes=(), tipo="Pública"):
    return {"codigo": codigo, "clase": clase, "nombre": nombre, "situacion": "Activo", "campo": "Derecho",
            "rama": "Ciencias Sociales y Jurídicas",
            "universidades": [{"nombre": uni, "tipo": tipo}], "componentes": list(componentes)}


def test_agrupar_y_pagina_propia():
    cat = [
        _t("1", "Derecho", "Granada"), _t("2", "Derecho / Bachelor in Law", "IE Universidad", tipo="Privada"),
        _t("3", "Derecho Canónico", "Navarra", tipo="Privada"),
        _t("4", "Administración y Dirección de Empresas", "Granada"),
        _t("5", "Derecho y ADE", "Granada", "doble", [{"nombre": "Derecho", "codigo": "1"},
                                                      {"nombre": "Administración y Dirección de Empresas", "codigo": "4"}]),
        _t("6", "ADE y Derecho", "Sevilla", "doble", [{"nombre": "Administración y Dirección de Empresas", "codigo": None},
                                                      {"nombre": "Derecho", "codigo": None}]),
    ]
    g = {x["id"]: x for x in gen.agrupar(cat)}
    assert g["derecho"]["titulos"] == ["1", "2"] and g["derecho"]["pagina_propia"]
    assert g["derecho"]["publicas"] == 1 and g["derecho"]["privadas"] == 1
    assert not g["derecho-canonico"]["pagina_propia"]  # un solo título: sin página genérica
    d = [x for x in g.values() if x["tipo"] == "doble"]
    assert len(d) == 1 and d[0]["titulos"] == ["5", "6"]  # el orden de los componentes no cuenta
