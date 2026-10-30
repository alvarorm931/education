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
    assert c["modalidades"] == ["semipresencial"] and c["plazas_por_modalidad"] == {"semipresencial": 40.0}
    assert c["plazas_nuevo_ingreso"] == 40.0 and c["idiomas"] == ["INGLÉS"]


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


def test_centro_formato_anterior_plazas_por_ano():
    c = r.parsear_centro(L("centro_rd1393_4310193.html"))
    assert c["modalidades"] == ["presencial"]
    assert c["plazas_nuevo_ingreso"] == 20.0 and c["plazas_por_ano_implantacion"] == [20.0, 20.0]
    assert c["normas_permanencia"].startswith("https://www.um.es/")


# ------------------------------------------------------------------ ejecución (cortes, robots, ritmo)

import json  # noqa: E402

ruct = r


def test_ejecutar_espera_los_cortes_y_reintenta(monkeypatch, tmp_path):
    respuestas = {"A": ["ok"], "B": ["corte", "ok"], "C": ["corte", "ok"], "D": ["corte", "ok"], "E": ["ok"]}

    def ficha(lector, codigo, tipo="M"):
        r = respuestas[codigo].pop(0)
        return {"codigo": codigo, "error": "ficha no disponible (estado 0)"} if r == "corte" else {"codigo": codigo, "fuente": {}}

    monkeypatch.setattr(ruct, "leer_ficha", ficha)
    res = ruct.ejecutar(["A", "B", "C", "D", "E"], tmp_path, "ficha", 5, pausa_corte=0)
    assert res["hechos"] == 5 and res["alerta"] is None and not res["errores"] and res["sin_leer"] == 0
    assert sorted(p.name for p in (tmp_path / "datos/estudios/masters/ruct").glob("?.json")) == [
        "A.json", "B.json", "C.json", "D.json", "E.json"]


def test_ejecutar_para_si_el_servidor_no_vuelve_y_anota_lo_pendiente(monkeypatch, tmp_path):
    monkeypatch.setattr(ruct, "leer_ficha", lambda l, c, tipo="M": {"codigo": c, "error": "ficha no disponible (estado 0)"})
    monkeypatch.setattr(ruct, "PAUSAS_MAX", 1)
    res = ruct.ejecutar(list("ABCDEFG"), tmp_path, "ficha", 5, pausa_corte=0)
    assert res["hechos"] == 0 and "no responde" in res["alerta"] and res["sin_leer"] == 7
    resumen = json.loads(next((tmp_path / "datos/estudios/masters/ruct").glob("resumen-*.json")).read_text())
    assert sorted(resumen["sin_leer"]) == list("ABCDEFG")


def test_ejecutar_para_ante_una_prohibicion_escrita_de_robots(monkeypatch, tmp_path):
    from motor import http
    from motor.robots import Robots

    monkeypatch.setitem(http._ROBOTS, "https://www.educacion.gob.es", Robots("User-agent: *\nDisallow: /ruct/"))
    monkeypatch.setattr(ruct.Lector, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debe pedir")))
    res = ruct.ejecutar(["A", "B"], tmp_path, "ficha", 5, pausa_corte=0)
    assert res["hechos"] == 0 and res["alerta"].startswith("robots.txt") and res["sin_leer"] == 2


def test_registro_publico_con_robots_ilegible_se_lee(monkeypatch):
    from motor import http
    from motor.robots import Robots

    class R:
        status_code = 200
        content = b"<html></html>"
        headers = {}

    monkeypatch.setitem(http._ROBOTS, "https://www.educacion.gob.es", Robots(todo_prohibido=True))
    lector = ruct.LectorRegistro(archivo=None, pausa=0)
    monkeypatch.setattr(lector.s, "get", lambda url, timeout=0: R())
    assert lector.get(ruct.URL_FICHA.format(tipo="M", codigo="4310193"))[0] == 200 and lector.excepcion_registro == 1
    assert lector.get("https://www.educacion.gob.es/otra/cosa")[0] == 0


def test_una_peticion_por_segundo_desde_el_inicio_de_la_anterior(monkeypatch):
    reloj = {"t": 100.0}
    esperas = []
    monkeypatch.setattr(ruct.time, "monotonic", lambda: reloj["t"])
    monkeypatch.setattr(ruct.time, "sleep", lambda s: esperas.append(round(s, 2)) or reloj.__setitem__("t", reloj["t"] + s))
    lector = ruct.Lector(archivo=None, pausa=1.0)
    lector._esperar_turno()          # primera: no espera
    reloj["t"] += 0.4                # la respuesta tardó 0,4 s
    lector._esperar_turno()          # espera solo lo que falta para el segundo
    reloj["t"] += 1.5                # respuesta lenta: no se espera nada más
    lector._esperar_turno()
    assert esperas == [0.6]


def test_ejecutar_reintenta_al_final_los_cortes_sueltos(monkeypatch, tmp_path):
    respuestas = {"A": ["ok"], "B": ["corte", "ok"], "C": ["ok"]}

    def ficha(lector, codigo, tipo="M"):
        x = respuestas[codigo].pop(0)
        return {"codigo": codigo, "error": "ficha no disponible (estado 0)"} if x == "corte" else {"codigo": codigo, "fuente": {}}

    monkeypatch.setattr(ruct, "leer_ficha", ficha)
    res = ruct.ejecutar(["A", "B", "C"], tmp_path, "ficha", 5, pausa_corte=0)
    assert res["hechos"] == 3 and res["sin_leer"] == 0 and not res["errores"]


def test_el_ritmo_se_adapta_al_servidor(monkeypatch):
    import requests

    monkeypatch.setattr(ruct.time, "sleep", lambda s: None)
    lector = ruct.Lector(archivo=None, pausa=1.0)
    import itertools

    respuestas = itertools.chain([requests.Timeout()], itertools.repeat("ok"))

    class R:
        status_code, content, headers = 200, b"<html></html>", {}

    def get(url, timeout=0):
        x = next(respuestas)
        if isinstance(x, Exception):
            raise x
        return R()

    monkeypatch.setattr(lector.s, "get", get)
    assert lector.get("https://www.educacion.gob.es/ruct/x")[0] == 200
    assert lector.pausa == 2.0 and lector.errores["Timeout"] == 1
    for _ in range(ruct.SEGUIDAS_PARA_ACELERAR * 4):
        lector.get("https://www.educacion.gob.es/ruct/x")
    assert lector.pausa == 1.0 and lector.pausa_max_usada == 2.0  # vuelve a una por segundo, nunca menos


def test_429_frena_hasta_el_maximo(monkeypatch):
    monkeypatch.setattr(ruct.time, "sleep", lambda s: None)
    lector = ruct.Lector(archivo=None, pausa=1.0)

    class R:
        status_code, content, headers = 429, b"", {}

    monkeypatch.setattr(lector.s, "get", lambda url, timeout=0: R())
    for _ in range(5):
        lector.get("https://www.educacion.gob.es/ruct/x")
    assert lector.pausa == ruct.PAUSA_MAX


def test_codigos_ya_leidos_por_nivel_y_sello():
    rutas = ["20261029T172051/datos/estudios/masters/ruct/4310193.json",
             "20261030T111924-t0/datos/estudios/masters/ruct/3500004.json",
             "20261030T111924-t0/datos/estudios/masters/ruct/resumen-ficha-1.json",
             "20261031T010000-t5/datos/estudios/masters/ruct_memoria/3500005.json"]
    assert ruct.codigos_en_rutas(rutas, "ficha", "20261030T1100") == {"3500004"}
    assert ruct.codigos_en_rutas(rutas, "ficha") == {"4310193", "3500004"}
    assert ruct.codigos_en_rutas(rutas, "memoria") == {"3500005"}


def test_memoria_va_a_su_carpeta(monkeypatch, tmp_path):
    monkeypatch.setattr(ruct, "leer_ficha", lambda l, c, tipo="M": {"codigo": c, "fuente": {}})
    monkeypatch.setattr(ruct, "leer_memoria", lambda l, f, max_paginas=0: {"plan": []})
    ruct.ejecutar(["A"], tmp_path, "memoria", 5, pausa_corte=0)
    assert (tmp_path / "datos/estudios/masters/ruct_memoria/A.json").exists()
