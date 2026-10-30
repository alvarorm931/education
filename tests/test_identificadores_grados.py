from motor.grados.identificadores import Tabla, asignar, nombre_url, slug


def _f(codigo, nombre, uni="Granada", ucod="008", centros=1, **extra):
    return {"codigo": codigo, "nombre": nombre, "universidades": [{"nombre": uni, "codigo": ucod}],
            "centros": [{}] * centros, **extra}


def test_slug_y_nombre():
    assert slug("Administración y Dirección de Empresas") == "administracion-y-direccion-de-empresas"
    assert nombre_url("Diseño de Moda / Bachelor in Fashion Design") == "Diseño de Moda"
    assert nombre_url("Maestro/a en Educación Primaria") == "Maestro/a en Educación Primaria"


def test_tabla_solo_crece_y_distingue_sin_codigos():
    cat = {"1": {"imparticiones": [{"situacion": "Activo", "municipio": "GRANADA", "presencialidad": "Estudio presencial"}]},
           "2": {"imparticiones": [{"situacion": "Activo", "municipio": "MELILLA", "presencialidad": "Estudio presencial"}]}}
    catalogo = [{"codigo": k, **v} for k, v in cat.items()]
    t = Tabla()
    asignar(t, [_f("1", "Enfermería", centros=2), _f("2", "Enfermería")], [], [], catalogo)
    assert t.rutas["titulo:1"] == "/universidad/granada/grado/enfermeria/"
    assert t.rutas["titulo:2"] == "/universidad/granada/grado/enfermeria-melilla/"
    # otra pasada con el nombre cambiado: la dirección no cambia; y una ruta usada no se da a otro
    t2 = Tabla(t.a_json())
    asignar(t2, [_f("1", "Enfermería (Plan nuevo) y algo"), _f("3", "Enfermería", centros=5)], [], [], catalogo)
    assert t2.rutas["titulo:1"] == "/universidad/granada/grado/enfermeria/"
    assert t2.rutas["titulo:3"] not in {"/universidad/granada/grado/enfermeria/",
                                        "/universidad/granada/grado/enfermeria-melilla/"}


def test_asignaturas_con_pagina():
    t = Tabla()
    asignar(t, [], [], [{"clave": "algebra", "nombre": "Álgebra Lineal", "titulos": 5},
                        {"clave": "x", "nombre": "2 optativas", "titulos": 9},
                        {"clave": "tfg", "nombre": "Trabajo Fin de Grado", "titulos": 900, "generica": True}], [])
    assert list(t.rutas.values()) == ["/carreras-con/algebra-lineal/"]
