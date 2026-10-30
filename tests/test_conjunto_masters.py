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
                                              {"actividad": "Estudio", "horas": 105, "presencialidad": 0.0}]}]}]}}
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
                          "asignaturas": {"valor": "Marketing digital; Analítica", "fuente": 0},
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
        "planes": [{"comprobacion": "completo", "filas_plan": [{"nombre": "Finanzas", "tipo": "obligatoria", "creditos": 6}]}]}) + "\n")
    cm.ejecutar(t / "cat.json", t / "out", ruct=[t / "ruct"], qedu=[t / "qedu"], fichas=t / "fichas.jsonl",
                fecha_catalogo="2026-10-29", boe=[b])
    c = _leer(t / "out" / "masters_oficiales.jsonl.gz")[0]["campos"]
    assert c["asignaturas"]["fuente"] == "boe" and c["asignaturas"]["valor"][0]["caracter"] == "Obligatoria"
    assert c["asignaturas"]["comprobado"] == "completo" and "2011" in c["asignaturas"]["nota"]
