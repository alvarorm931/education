import gzip
import json

from motor.estudios import conjunto_masters as cm


def _escribir(tmp_path):
    cat = [{"codigo_ruct": "4310193", "nombre_oficial": "Máster Universitario en Finanzas por la Universidad de Murcia",
            "situacion": "Activo", "universidad": "Murcia", "universidad_codigo": "036", "universidad_tipo": "Pública",
            "universidad_comunidad": "Región de Murcia", "rama": "Ciencias Sociales y Jurídicas",
            "imparticiones": [{"unidad": "Facultad de Economía y Empresa", "unidad_codigo": "30013645",
                               "municipio": "MURCIA", "presencialidad": "Estudio presencial"}],
            "fuente": {"curso": "2025-2026"}},
           {"codigo_ruct": "4399999", "nombre_oficial": "Máster Universitario en Nada", "situacion": "Extinguido",
            "universidad": "Murcia", "imparticiones": []}]
    (tmp_path / "cat.json").write_text(json.dumps(cat))
    r = tmp_path / "ruct" / "datos" / "estudios" / "masters" / "ruct"
    r.mkdir(parents=True)
    ficha = {"codigo": "4310193", "nombre": cat[0]["nombre_oficial"],
             "creditos": {"obligatorios": 48.0, "optativos": 0.0, "practicas_externas": 6.0, "tfm": 6.0, "total": 60.0},
             "fecha_verificacion": "2009-05-13", "acreditaciones": [{"resultado": "Favorable", "fecha": "2019-06-05"}],
             "boe": {"plan": {"identificador": "BOE-A-2011-1220", "fecha": "2011-01-22"}},
             "fuente": {"url": "https://www.educacion.gob.es/ruct/estudio.action?CodigoEstudio=4310193",
                        "capturado": "2026-10-30T11:00:00+00:00"},
             "memoria": {"basicos": {"habilita_profesion_regulada": "No"},
                         "centros": [{"codigo": "30013645", "modalidades": ["presencial"], "plazas_total": 30.0,
                                      "idiomas": ["CASTELLANO"]}],
                         "catalogos": {"metodologias": ["1 Método expositivo", "MD2 Estudio de casos"],
                                       "sistemas": ["1 Examen"]},
                         "acceso": {"textos": ["Grado en Economía o ADE."]},
                         "plan": [{"modulo": 1, "nombre": "Obligatorio", "materias": [
                             {"nombre": "Finanzas Corporativas", "caracter": "Obligatoria", "ects": 6.0,
                              "despliegue": {"1": 6.0}, "asignaturas": [],
                              "evaluacion": [{"sistema": "Examen:", "ponderacion_min": 50.0, "ponderacion_max": 70.0}],
                              "actividades": [{"actividad": "Clases", "horas": 45, "presencialidad": 100.0},
                                              {"actividad": "Estudio", "horas": 105, "presencialidad": 0.0}]},
                             {"nombre": "Valoración de Empresas", "caracter": "Obligatoria", "ects": 6.0},
                             {"nombre": "Mercados Financieros", "caracter": "Obligatoria", "ects": 6.0}]}]}}
    (r / "4310193.json").write_text(json.dumps(ficha))
    (r / "resumen-memoria-1.json").write_text("{}")
    q = tmp_path / "qedu"
    q.mkdir()
    (q / "qedu_tarjetas_master.jsonl").write_text(json.dumps(
        {"codTitula": "4310193", "codCentro": "30013645", "codUniv": "036", "nombreUniversidad": "Universidad de Murcia",
         "nombreCentro": "Facultad de Economía y Empresa", "modalidad": "1", "anio": "2025-2026",
         "fuente": {"capturado": "2026-10-30T10:28:39+00:00"}}) + "\n")
    (q / "qedu_detalles_master_0_fin.jsonl").write_text(json.dumps(
        {"codTitula": "4310193", "codCentro": "30013645", "codUniv": "036",
         "detalle": {"plazas": 40, "precio_credito": 33.62, "curso": "2025-2026", "modalidad": "Presencial",
                     "enlace": "https://www.um.es/web/estudios/masteres/finanzas"},
         "insercion": {"tasa_afiliacion": 80.5}, "fuente": {"capturado": "2026-10-30T12:00:00+00:00"}}) + "\n")
    fichas = [{"clave": "ruct:4310193", "grupo": "oficial", "codigo_ruct": "4310193", "comprobacion_nombre": "confirmado",
               "paginas": ["https://www.um.es/m/finanzas"],
               "fuentes": [{"url": "https://www.um.es/m/finanzas", "extraido": "2026-10-30T02:00:00+00:00", "pagina": "principal"}],
               "campos": {"plazas": {"valor": 35, "fuente": 0}, "horario": {"valor": "de tarde", "fuente": 0},
                          "modalidad": {"valor": "presencial", "fuente": 0}}},
              {"clave": "url:https://esc.es/m", "grupo": "no_oficial", "programa": "prog-1", "es_master": True,
               "url": "https://esc.es/m", "centro": "Escuela", "fuentes": [
                   {"url": "https://esc.es/m", "extraido": "2026-10-30T03:00:00+00:00", "pagina": "principal"},
                   {"url": "https://esc.es/tarifas.pdf", "extraido": "2026-10-30T04:00:00+00:00", "pagina": "documento", "curso": "2026-2027"}],
               "campos": {"nombre": {"valor": "Máster en Marketing", "fuente": 0},
                          "asignaturas": {"valor": "Marketing digital; Analítica; Comercio electrónico", "fuente": 0},
                          "precio_total": {"valor": 9800, "fuente": 1},
                          "fecha_inicio": {"valor": "octubre de 2022", "fuente": 0}}}]
    (tmp_path / "fichas.jsonl").write_text("".join(json.dumps(f) + "\n" for f in fichas))
    return tmp_path


def _leer(ruta):
    return [json.loads(x) for x in gzip.decompress(ruta.read_bytes()).decode().split("\n") if x.strip()]


def test_conjunto_une_fuentes_con_prioridad_oficial(tmp_path):
    t = _escribir(tmp_path)
    res = cm.ejecutar(t / "cat.json", t / "out", ruct=[t / "ruct"], qedu=[t / "qedu"], fichas=t / "fichas.jsonl",
                      fecha_catalogo="2026-10-29")
    assert res["oficiales"] == 1 and res["oficiales_con_ruct_memoria"] == 1 and res["oficiales_en_qedu"] == 1
    o = _leer(t / "out" / "masters_oficiales.jsonl.gz")[0]
    c = o["campos"]
    assert o["universidad"] == "Universidad de Murcia" and c["universidad_que_expide"]["capturado"] == "2026-10-29"
    assert c["plazas"]["valor"] == 40 and c["plazas"]["fuente"] == "qedu"                   # QEDU manda en plazas
    assert c["plazas"]["alternativas"] == [{"valor": 35, "fuente": "web", "url": "https://www.um.es/m/finanzas"}]
    assert c["plazas_verificadas"]["valor"] == 30 and c["modalidad"]["fuente"] == "ruct"
    assert c["precio_credito"]["valor"] == 33.62
    assert c["precio_total"]["fuente"] == "calculado" and c["precio_total"]["valor"] == 2017.2
    assert c["practicas"]["valor"] == "Sí, 6 ECTS" and c["tfm"]["valor"] == "6 ECTS" and c["habilita_profesion"]["valor"] == "No"
    assert c["asignaturas"]["valor"][0]["nombre"] == "Finanzas Corporativas"
    assert c["evaluacion"]["valor"]["sistemas"][0] == {"sistema": "Examen", "min": 50.0, "max": 70.0, "materias": 1}
    assert c["metodologia"]["valor"] == ["Método expositivo", "Estudio de casos"]
    assert c["presencialidad_horas"]["valor"] == 30.0 and c["presencialidad_horas"]["fuente"] == "calculado"
    assert c["horario"]["fuente"] == "web" and c["insercion_laboral"]["valor"]["tasa_afiliacion"] == 80.5
    assert c["plan_en_boe"]["url"].endswith("BOE-A-2011-1220")
    assert o["indexable"] and o["en_oferta_del_curso"]
    p = _leer(t / "out" / "programas_no_oficiales.jsonl.gz")[0]
    assert p["campos"]["precio_total"]["fuente"] == "tarifa" and p["campos"]["precio_total"]["curso"] == "2026-2027"
    assert p["indexable"] and p["pagina_web_antigua"]  # solo habla de 2022


def test_la_fecha_solo_cambia_si_cambia_el_dato(tmp_path):
    t = _escribir(tmp_path)
    cm.ejecutar(t / "cat.json", t / "v1", ruct=[t / "ruct"], qedu=[t / "qedu"], fichas=t / "fichas.jsonl",
                fecha_catalogo="2026-10-29")
    # nueva pasada: QEDU vuelve a dar lo mismo con otra fecha y la web cambia el horario
    d = t / "qedu" / "qedu_detalles_master_0_fin.jsonl"
    d.write_text(d.read_text().replace("2026-10-30T12:00:00+00:00", "2026-11-06T12:00:00+00:00"))
    f = t / "fichas.jsonl"
    f.write_text(f.read_text().replace("de tarde", "de mañana").replace("2026-10-30T02:00:00", "2026-11-06T02:00:00"))
    res = cm.ejecutar(t / "cat.json", t / "v2", ruct=[t / "ruct"], qedu=[t / "qedu"], fichas=f, anterior=t / "v1",
                      fecha_catalogo="2026-11-06")
    c = _leer(t / "v2" / "masters_oficiales.jsonl.gz")[0]["campos"]
    assert c["precio_credito"]["capturado"] == "2026-10-30T12:00:00+00:00"       # mismo dato: misma fecha
    assert c["universidad_que_expide"]["capturado"] == "2026-10-29"
    assert c["horario"]["valor"] == "de mañana" and c["horario"]["capturado"] == "2026-11-06T02:00:00+00:00"
    assert res["fechas"]["cambiados"] == 1 and "revisado" not in c["horario"]
    # sin cambios, el mismo fichero
    cm.ejecutar(t / "cat.json", t / "v3", ruct=[t / "ruct"], qedu=[t / "qedu"], fichas=f, anterior=t / "v2",
                fecha_catalogo="2026-11-07")
    assert (t / "v3" / "masters_oficiales.jsonl.gz").read_bytes() == (t / "v2" / "masters_oficiales.jsonl.gz").read_bytes()


def test_limpia_numero_de_catalogo():
    assert cm._limpia_id("3 Clases teóricas") == "Clases teóricas"
    assert cm._limpia_id("SE1 Asistencia") == "Asistencia" and cm._limpia_id("MD3. Seminarios") == "Seminarios"
    assert cm._limpia_id("Estudio de casos") == "Estudio de casos"


def test_textos_del_ruct_sin_datos_de_personas():
    t = ("Requisitos: grado en Economía.\nCoordinadora: Dra. Ana Ruiz Gómez\nDudas: ana.ruiz@um.es\n"
         "Solicitudes a admisiones@escuela.es\nSe valora el inglés.")
    assert cm.seguro(t) == ("Requisitos: grado en Economía.\nDudas: [correo]\nSolicitudes a admisiones@escuela.es\n"
                            "Se valora el inglés.")


def test_asignaturas_del_boe_si_no_hay_memoria(tmp_path):
    t = _escribir(tmp_path)
    f = t / "ruct" / "datos" / "estudios" / "masters" / "ruct" / "4310193.json"
    d = json.loads(f.read_text())
    d.pop("memoria")
    f.write_text(json.dumps(d))
    b = t / "boe"
    b.mkdir()
    (b / "boe_planes_masters.jsonl").write_text(json.dumps({
        "identificador": "BOE-A-2011-1220", "codigos_ruct": ["4310193"], "url": "https://www.boe.es/x",
        "fecha_publicacion": "20110122", "capturado": "2026-10-30T13:00:00+00:00",
        "planes": [{"comprobacion": "completo", "filas_plan": [{"nombre": "Finanzas", "tipo": "obligatoria", "creditos": 6},
                                                              {"nombre": "Contabilidad", "tipo": "obligatoria", "creditos": 6},
                                                              {"nombre": "Fiscalidad", "tipo": "optativa", "creditos": 6},
                                                              {"nombre": "1", "tipo": "optativa", "creditos": 6}]}]}) + "\n")
    cm.ejecutar(t / "cat.json", t / "out", ruct=[t / "ruct"], qedu=[t / "qedu"], fichas=t / "fichas.jsonl",
                fecha_catalogo="2026-10-29", boe=[b])
    c = _leer(t / "out" / "masters_oficiales.jsonl.gz")[0]["campos"]
    assert c["asignaturas"]["fuente"] == "boe" and c["asignaturas"]["valor"][0]["caracter"] == "Obligatoria"
    assert c["asignaturas"]["comprobado"] == "completo" and "2011" in c["asignaturas"]["nota"]


def test_evaluacion_de_las_guias_si_la_memoria_no_la_pondera(tmp_path):
    t = _escribir(tmp_path)
    f = t / "ruct" / "datos" / "estudios" / "masters" / "ruct" / "4310193.json"
    d = json.loads(f.read_text())
    d["memoria"]["plan"][0]["materias"][0]["evaluacion"] = []  # formato RD 822/2021: solo el catálogo
    f.write_text(json.dumps(d))
    gd = t / "guias"
    gd.mkdir()
    (gd / "guias.jsonl").write_text(json.dumps({
        "url": "https://www.um.es/guia/1.pdf", "codigos_ruct": ["4310193"], "asignatura": "Finanzas Corporativas",
        "creditos": 6, "extraido": "2026-10-30T14:00:00+00:00", "metodologia": ["Clases"],
        "evaluacion": [{"sistema": "Examen", "min": 60, "max": 60}, {"sistema": "Trabajos", "min": 40, "max": 40}]}) + "\n")
    cm.ejecutar(t / "cat.json", t / "out", ruct=[t / "ruct"], qedu=[t / "qedu"], fichas=t / "fichas.jsonl",
                fecha_catalogo="2026-10-29", guias=[gd])
    c = _leer(t / "out" / "masters_oficiales.jsonl.gz")[0]["campos"]
    assert c["evaluacion"]["fuente"] == "guia" and c["evaluacion"]["valor"]["sistemas"][0]["sistema"] == "Examen"
    assert c["evaluacion_por_asignatura"]["valor"][0]["sistemas"][1] == {"sistema": "Trabajos", "min": 40, "max": 40}


def test_privacidad_en_listas_lineas_partidas_y_cargos():
    assert cm.seguro("Coordinación: Ana Ruiz Gil") is None and cm.seguro("A cargo de Juan Pérez") is None
    assert cm.seguro("Dr. Pérez imparte la asignatura") is None and cm.seguro("Dra. M. López") is None
    assert cm.seguro("Prof. Titular de Universidad") == "Prof. Titular de Universidad"
    assert cm.seguro("Coordinador Académico") == "Coordinador Académico"
    assert cm.seguro("El máster lo coordina el\nDr.\nPérez y otros\nPlazas: 30") == "El máster lo coordina el\nPlazas: 30"
    assert cm.seguro("Escribe a master.juan@ucm.es") == "Escribe a [correo]"
    assert cm.seguro("Escribe a master.biologia@ucm.es") == "Escribe a master.biologia@ucm.es"
    assert cm.seguro_valor([["Dr. Gómez", 3], ["Álgebra", 6]]) == [["Álgebra", 6]]
    assert cm.seguro_valor([{"sistema": "Examen", "min": 50}, {"sistema": "Profesora Ana Ruiz", "min": 50}]) == \
        [{"sistema": "Examen", "min": 50}]


def test_asignaturas_validas_y_precios_imposibles():
    assert cm.asignaturas_validas([["No se indica", None], ["TFM", 12], ["Prácticas externas", 6]]) is None
    assert cm.asignaturas_validas(["Obligatorias (OB)", "Optativas (OP)", "Prácticas Académicas Externas", "Módulo I"]) is None
    # módulos con nombre de contenido sí cuentan (así presentan su plan muchos títulos propios)
    assert cm.asignaturas_validas(["Módulo 1. Fundamentos de ecografía", "Módulo 2. Ecografía abdominal",
                                   "Módulo de Robótica", "MÓDULO 7. PROYECTO FIN DE MASTER"])
    assert not cm.es_asignatura_real("Módulo común (conocimientos teóricos)") and cm.es_asignatura_real("Optativa: Marketing")
    assert cm.asignaturas_validas("Álgebra; Cálculo; Estadística") == ["Álgebra", "Cálculo", "Estadística"]
    assert cm.asignaturas_validas([["Álgebra", 6], ["1", 6], ["Cálculo", 6], ["Estadística", 6]]) == \
        [["Álgebra", 6], ["Cálculo", 6], ["Estadística", 6]]
    f = {"fuentes": [{"url": "https://u.es/m", "extraido": "2026-10-30T00:00:00+00:00"},
                     {"url": "https://u.es/t.pdf", "pagina": "documento", "curso": "2022-2023"}],
         "campos": {"precio_total": {"valor": 45, "fuente": 0}, "precio_credito": {"valor": 45, "fuente": 0},
                    "reserva_matricula": {"valor": 300, "fuente": 1}}}
    w = cm.campos_web(f)
    assert "precio_total" not in w and w["precio_credito"]["valor"] == 45 and w["reserva_matricula"]["antiguo"]
    # un total de la web que no cabe con el precio oficial del crédito: manda el calculado
    c = {"precio_credito": cm.campo(30.0, "qedu", None, None), "creditos_ects": cm.campo(60, "ruct", None, None),
         "precio_total": cm.campo(18000, "web", "https://u.es/m", None)}
    cm.poner_precio_calculado(c)
    assert c["precio_total"]["fuente"] == "calculado" and c["precio_total"]["valor"] == 1800
    assert c["precio_total"]["alternativas"][0]["valor"] == 18000 and "primera matrícula" in c["precio_total"]["nota"]
    c = {"precio_credito": cm.campo(150.0, "web", None, None), "creditos_ects": cm.campo(60, "ruct", None, None)}
    cm.poner_precio_calculado(c)
    assert c["precio_total"]["base"] == "web" and "primera matrícula" not in c["precio_total"]["nota"]
    assert cm.datos_minimos({"asignaturas": 1, "precio_total": {"valor": 9000, "antiguo": True}}) == ["precio"]


def test_web_de_otra_universidad_fuera():
    dominios = {"us.es": {"001"}, "uco.es": {"002"}}
    web = {"comprobacion_nombre": "confirmado", "paginas": ["https://www.uco.es/m"],
           "campos": {"universidad_que_expide": {"valor": "Universidad de Córdoba"}}}
    claves = {cm.clave_universidad(x) for x in ("Sevilla", "Córdoba")}
    assert cm.filtrar_web(web, {"001"}, dominios, cm.clave_universidad("Sevilla"), claves)[2] == "web_expide_otra_universidad"
    web["campos"] = {}
    assert cm.filtrar_web(web, {"001"}, dominios, "sevilla", claves)[2] == "web_en_dominio_de_otra_universidad"
    assert cm.filtrar_web(web, {"001", "002"}, dominios, "sevilla", claves)[0] is web  # interuniversitario
    probable = {"comprobacion_nombre": "probable_oficial", "paginas": ["https://www.escuela.com/m"], "campos": {}}
    assert cm.filtrar_web(probable, {"001"}, dominios, "sevilla", claves)[2] == "web_probable_fuera_de_su_universidad"
    assert cm.universidades_del_nombre("Máster Universitario en X por la Universidad de A Coruña y la Universidad "
                                       "de Vigo") == ["a coruna", "vigo"]


def test_no_oficiales_filtrados_unidos_y_con_id_estable():
    def f(clave, prog, url, nombre, **campos):
        return {"clave": clave, "programa": prog, "url": url, "dominio": "esc.es", "es_master": True,
                "fuentes": [{"url": url, "extraido": "2026-10-30T00:00:00+00:00"}],
                "campos": {"nombre": {"valor": nombre, "fuente": 0}, **{k: {"valor": v, "fuente": 0} for k, v in campos.items()}}}
    web = [f("u1", "p1", "https://esc.es/es/master-marketing", "Máster en Marketing", precio_total=9000),
           f("u2", "p2", "https://esc.es/en/master-marketing", "Máster en Marketing"),
           f("u3", "p3", "https://esc.es/mx/master-x", "Máster en X"),
           f("u4", "p4", "https://esc.es/m-y", "Máster en Y", sedes=["Bogotá"]),
           f("u5", "p5", "https://esc.es/blog/mejores-masters", "Máster en Z"),
           f("u6", "p6", "https://esc.es/mu", "Máster Universitario en Derecho"),
           f("u7", "p7", "https://esc.es/mp", "Máster de Formación Permanente en Derecho", sedes=["Madrid", "Bogotá"])]
    prev = {"p2": {"id": "p2"}}
    out = cm.programas_no_oficiales(web, prev)
    assert [r["id"] for r in out] == ["p2", "p7"]
    assert out[0]["campos"]["precio_total"]["valor"] == 9000 and out[0]["otras_paginas"]
    assert cm.DESCARTES["no_oficial_otro_pais"] == 2 and cm.DESCARTES["no_oficial_parece_master_oficial"] == 1


def test_modalidad_de_qedu_y_boe_solo_cuadra_si_completo():
    assert cm.MODALIDAD_QEDU["2"] == "semipresencial o a distancia" and cm.MODALIDAD_QEDU["4"] == "varias modalidades"
    plan = {"comprobacion": "basicas_y_obligatorias", "fecha_publicacion": "20200101",
            "filas_plan": [{"nombre": n, "tipo": "obligatoria", "creditos": 6} for n in ("Álgebra", "Cálculo", "Física", "x")]}
    a = cm.campos_boe(plan)["asignaturas"]
    assert "cuadran las básicas y obligatorias" in a["nota"] and len(a["valor"]) == 3


def test_guias_con_pesos_que_no_suman_fuera():
    g = {"url": "u", "asignatura": "A", "extraido": "2026", "evaluacion": [{"sistema": "Examen", "min": 70, "max": 70},
                                                                         {"sistema": "Trabajo", "min": 50, "max": 50}]}
    assert cm.campos_guias([g]) == {}
    g["evaluacion"][1] = {"sistema": "Trabajo", "min": 30, "max": 30}
    assert cm.campos_guias([g])["evaluacion"]["valor"]["sistemas"][0]["sistema"] == "Examen"


def test_alta_del_boe_con_su_fuente_y_su_fecha_de_captura(tmp_path):
    t = _escribir(tmp_path)
    (t / "altas.jsonl").write_text(json.dumps({"codigo_ruct": "4319999", "nombre": "Máster Universitario en Bolsa",
                                               "universidad": "Universidad de Murcia", "boe": "BOE-A-2026-1",
                                               "fecha": "2026-01-15"}) + "\n")
    cm.ejecutar(t / "cat.json", t / "out", altas=t / "altas.jsonl", fichas=t / "fichas.jsonl", fecha_catalogo="2026-10-29")
    o = next(r for r in _leer(t / "out" / "masters_oficiales.jsonl.gz") if r["codigo_ruct"] == "4319999")
    c = o["campos"]["tipo_titulo"]
    assert c["fuente"] == "boe" and c["url"].endswith("BOE-A-2026-1") and c["capturado"] == "2026-10-29"
    assert o["comunidad"] == "Región de Murcia" and o["universidad_tipo"] == "Pública"  # universidad por su clave


def test_plan_del_boe_con_la_ultima_medicion_del_documento(tmp_path):
    filas = [{"nombre": n, "tipo": "obligatoria", "creditos": 6} for n in ("Álgebra", "Cálculo", "Física")]
    doc = {"identificador": "BOE-A-2011-1", "url": "u", "fecha_publicacion": "20110101",
           "planes": [{"comprobacion": "completo", "filas_plan": filas}]}
    a, b = tmp_path / "20261030T1200" / "m", tmp_path / "20261030T1600" / "m"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    (a / "boe_planes_masters.jsonl").write_text(json.dumps({**doc, "codigos_ruct": ["4317886"]}) + "\n")
    (b / "boe_planes_masters.jsonl").write_text(json.dumps({**doc, "codigos_ruct": ["4310001"], "medido": "2026-10-30T16:00:00+00:00"}) + "\n")
    assert set(cm.cargar_boe_planes([tmp_path])) == {"4310001"}  # la unión antigua (a otro código) ya no cuenta


def test_guia_con_la_lectura_mas_reciente_aunque_pierda_la_evaluacion(tmp_path):
    a, b = tmp_path / "t0", tmp_path / "retomado"
    a.mkdir()
    b.mkdir()
    g = {"url": "https://u.es/g.pdf", "codigos_ruct": ["4310001"], "asignatura": "A",
         "evaluacion": [{"sistema": "Examen", "min": 100, "max": 100}], "extraido": "2026-10-30T12:00:00+00:00"}
    (a / "guias.jsonl").write_text(json.dumps(g) + "\n")
    (b / "guias.jsonl").write_text(json.dumps({**g, "evaluacion": [], "extraido": "2026-10-30T15:00:00+00:00"}) + "\n")
    assert cm.cargar_guias([a]) and not cm.cargar_guias([a, b])


def test_paginas_de_otra_universidad_fuera_de_la_ficha():
    cat = {"codigo_ruct": "4316605", "nombre_oficial": "Máster Universitario en Informática por la Universidad de Sevilla",
           "universidad": "Sevilla", "universidad_codigo": "001", "situacion": "Activo", "imparticiones": []}
    web = {"paginas": ["https://www.uma.es/m", "https://www.us.es/m"], "fuentes": [
        {"url": "https://www.uma.es/m", "extraido": "2026-10-30T00:00:00+00:00"}], "campos": {"horario": {"valor": "tarde", "fuente": 0}}}
    o = cm.oficial("4316605", cat, None, [], web, "2026-10-29", ajenos={"uma.es"})
    assert o["paginas_web"] == ["https://www.us.es/m"] and "horario" not in o["campos"]


def test_dominio_de_universidad_aunque_lo_compartan_interuniversitarios():
    cat = {f"c{i}": {"universidad_codigo": "010", "nombre_oficial": "Máster Universitario en X por la Universidad Complutense"}
           for i in range(20)}
    cat.update({"x1": {"universidad_codigo": "023", "nombre_oficial": "Máster Universitario en Y por la Universidad "
                       "Autónoma de Madrid y la Universidad Complutense de Madrid"},
                "y1": {"universidad_codigo": "022", "nombre_oficial": "Máster Universitario en Z por la Universidad de Alcalá"}})
    q = {c: [{"enlace": "https://www.ucm.es/m" + c}] for c in cat}
    d = cm.dominios_de_universidades(cat, q)
    assert d["ucm.es"] == {"010"}  # una sola mención de otras (interuniversitarios) no hace el dominio suyo
