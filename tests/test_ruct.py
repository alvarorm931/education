from pathlib import Path

from motor.estudios import ruct as r

F = Path(__file__).parent / "fixtures" / "ruct"


def L(nombre):
    return (F / nombre).read_bytes().decode("latin-1")


def test_ficha_titulo_nuevo():
    f = r.parsear_ficha(L("ficha_4318301.html"))
    assert f["codigo"] == "4318301"
    assert f["creditos"] == {"obligatorios": 35.0, "optativos": 9.0, "practicas_externas": 0.0, "tfm": 16.0,
                             "complementos_formativos": 0.0, "total": 60.0}
    assert f["boe"]["plan"]["identificador"] == "BOE-A-2026-1553"
    assert f["boe"]["acuerdo"]["identificador"] == "BOE-A-2025-20359"
    assert f["centros"] == [{"universidad": "Universidad Politécnica de Madrid", "codigo": "28026870",
                             "centro": "Escuela Técnica Superior de Arquitectura"}]
    assert f["curso_inicio"] == "2025/2026"
    assert f["autorizaciones_ccaa"][0]["fecha"] == "2025-09-14"


def test_ficha_con_historial_elige_ultima_memoria():
    f = r.parsear_ficha(L("ficha_4310193.html"))
    assert len(f["memorias"]) == 4
    assert r.memoria_vigente(f)["cod"] == "43101932024031301"
    assert f["acreditaciones"][0] == {"resultado": "Resolución Favorable Acreditacion Institucional", "fecha": "2026-02-25"}


def test_centro_modalidad_plazas_idioma():
    c = r.parsear_centro(L("centro_3500355.html"))
    assert c == {"modalidades": ["semipresencial"], "plazas_por_modalidad": {"semipresencial": 40.0},
                 "plazas_total": 40.0, "plazas_nuevo_ingreso": 40.0, "idiomas": ["INGLÉS"]}


def test_evaluacion_y_actividades_por_materia():
    s = r.parsear_tabla_materia(L("sistemas_materia_rd1393.html"), "sistemas")
    assert s[0] == {"id": "SE1", "sistema": "Prueba final oral y/o escrita.", "ponderacion_min": 40.0, "ponderacion_max": 70.0}
    a = r.parsear_tabla_materia(L("actividades_materia_rd1393.html"), "actividades")
    assert a[-1] == {"id": "AF6", "actividad": "Trabajo Autónomo del alumno.", "horas": 90.0, "presencialidad": 0.0}


def test_materia_y_asignatura():
    m = r.parsear_materia(L("materia_3500355.html"))
    assert (m["nombre"], m["caracter"], m["ects"], m["despliegue"]) == ("Negocios/Business", "Obligatoria", 3.0, {1: 3.0})
    assert m["hijos"] == [{"id": 1, "nombre": "Negocios Digitales/Digital Business"}]
    mods = r.parsear_materia(L("modulo_3500355.html"))["hijos"]
    assert len(mods) == 9 and mods[-1]["nombre"].startswith("Trabajo Fin de Máster")


def test_la_sesion_de_otro_titulo_se_rechaza():
    nombre = "Máster Universitario en Análisis de Negocio / Master in Business Analytics por la Universidad de Deusto"
    assert r._comprobar(L("asignatura_3500355.html"), nombre)
    # el servidor devolvió una página de un grado dentro de la sesión del máster de Murcia
    assert not r._comprobar(L("sistemas_materia_rd1393.html"), "Máster Universitario en Finanzas por la Universidad de Murcia")
