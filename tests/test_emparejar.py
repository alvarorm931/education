from motor.estudios import emparejar as e


def test_palabras_nombre_quita_lo_comun():
    assert e.palabras_nombre("Máster Universitario en Finanzas Avanzadas por la Universidad Antonio de Nebrija") == {"finanzas", "avanzadas"}


def test_raiz_y_modalidad():
    assert e.raiz_programa("https://x.es/postgrados/master-mba/acceso/") == "https://x.es/postgrados/master-mba/"
    assert e.sin_modalidad("https://x.es/master-ensenanza-bilingue-semipresencial/") == "https://x.es/master-ensenanza-bilingue"


def test_emparejar_une_y_agrupa_modalidades():
    t = [{"codigo_ruct": "1", "nombre_oficial": "Máster Universitario en Enseñanza Bilingüe en Inglés por la Universidad X"},
         {"codigo_ruct": "2", "nombre_oficial": "Máster Universitario en Arqueología por la Universidad X"}]
    urls = ["https://x.es/master-ensenanza-bilingue-ingles/", "https://x.es/master-ensenanza-bilingue-ingles-semipresencial/",
            "https://x.es/master-ensenanza-bilingue-ingles/profesorado", "https://x.es/master-derecho/"]
    r = {x["codigo_ruct"]: x for x in e.emparejar(t, urls)}
    assert r["1"]["estado"] == "unido" and len(r["1"]["urls_modalidad"]) == 2
    assert r["2"]["estado"] == "sin_pagina"


def test_empareja_por_texto_del_enlace_si_la_url_es_opaca():
    from motor.estudios import emparejar as e
    titulos = [{"codigo_ruct": "4310001", "nombre_oficial": "Máster Universitario en Ingeniería Informática por la Universidad Carlos III de Madrid"},
               {"codigo_ruct": "4310002", "nombre_oficial": "Máster Universitario en Derecho de las Telecomunicaciones por la Universidad Carlos III de Madrid"}]
    urls = ["https://www.uc3m.es/ss/Satellite/Postgrado/es/Detalle/Estudio_C/1371210340413",
            "https://www.uc3m.es/ss/Satellite/Postgrado/es/Detalle/Estudio_C/1371212345678"]
    textos = {urls[0]: "Máster Universitario en Ingeniería Informática",
              urls[1]: "Máster Universitario en Derecho de las Telecomunicaciones, Protección de Datos y Sociedad de la Información"}
    r = {x["codigo_ruct"]: x for x in e.emparejar(titulos, urls, textos)}
    assert r["4310001"]["estado"] == "unido" and r["4310001"]["url"] == urls[0]  # la dirección real, tal cual
    assert r["4310002"]["url"] == urls[1]
    assert all(x["estado"] == "sin_pagina" for x in e.emparejar(titulos, urls))  # sin textos, la URL no dice nada


def test_tramos_pegados_e_idiomas():
    from motor.estudios import emparejar as e
    t = [{"codigo_ruct": "1", "nombre_oficial": "Máster Universitario en Antropología Física: Evolución y Biodiversidad Humanas por la Universidad Complutense de Madrid"},
         {"codigo_ruct": "2", "nombre_oficial": "Máster Universitario en Lengua Española por la Universidad Complutense de Madrid"}]
    urls = ["https://www.ucm.es/estudios/master-antropologiafisica", "https://www.ucm.es/estudios/master-lenguaespanola"]
    r = {x["codigo_ruct"]: x for x in e.emparejar(t, urls)}
    assert r["2"]["estado"] == "unido" and r["2"]["url"] == urls[1]
    assert r["1"]["url"] is None or r["1"]["url"] == urls[0]
    t2 = [{"codigo_ruct": "3", "nombre_oficial": "Máster Universitario en Advocacia i Procura por la Universitat Jaume I"}]
    urls2 = ["https://www.uji.es/es/masters/advocacia-procura/", "https://www.uji.es/ca/masters/advocacia-procura/",
             "https://www.uji.es/en/masters/advocacia-procura/"]
    x = e.emparejar(t2, urls2)[0]
    assert x["estado"] == "unido" and "/es/" in x["url"]


def test_misma_ficha_en_subdominios_sufijos_y_paises():
    from motor.estudios import emparejar as e
    assert e.misma_ficha("https://veterinaria.ucm.es/estudios/2026-27/master-libroantiguo-plan/",
                         "https://odontologia.ucm.es/estudios/2023-24/master-libroantiguo-plazas/")
    assert e.misma_ficha("https://www.ull.es/masteres/bioetica-bioderecho/en/", "https://www.ull.es/masteres/bioetica-bioderecho/")
    assert e.misma_ficha("https://www.ugr.es/estudiantes/master-doctorados/master-universitario-ciencias-criminologicas-seguridad/",
                         "https://constitucional.ugr.es/docencia/posgrados/master-universitario-ciencias-criminologicas-y-seguridad/")
    assert not e.misma_ficha("https://www.urjc.es/estudios/master/502-abogacia-y-procura/", "https://www.cedeu.es/master-abogacia-y-procura/")
    t = [{"codigo_ruct": "1", "nombre_oficial": "Máster Universitario en Energías Renovables por la Universidad Internacional de La Rioja"}]
    x = e.emparejar(t, ["https://www.unir.net/ingenieria/master-energias-renovables/",
                        "https://mexico.unir.net/ingenieria/master-energias-renovables/"])[0]
    assert x["estado"] == "unido" and x["url"].startswith("https://www.unir.net")


def test_ejecutar_con_censo_rastreo_y_commoncrawl(tmp_path):
    import json
    from motor.estudios import emparejar as e
    (tmp_path / "cat.jsonl").write_text("\n".join(json.dumps(t) for t in [
        {"codigo_ruct": "1", "nombre_oficial": "Máster Universitario en Lengua Española por la Universidad Complutense de Madrid",
         "situacion": "Activo", "universidad_codigo": "002"},
        {"codigo_ruct": "2", "nombre_oficial": "Máster Universitario en Física Nuclear por la Universidad X",
         "situacion": "Activo", "universidad_codigo": "099"}]))
    (tmp_path / "censo.jsonl").write_text(json.dumps({"id": "prov-ucm", "dominios": ["ucm.es"], "ruct": [{"universidad": "002"}]}))
    (tmp_path / "r" / "oferta_web").mkdir(parents=True)
    (tmp_path / "r" / "oferta_web" / "ucm.es.json").write_text(json.dumps({"dominio": "ucm.es", "centro": {"id": "prov-ucm"}, "programas": []}))
    (tmp_path / "cc").mkdir()
    (tmp_path / "cc" / "urls_x.jsonl").write_text(json.dumps({"dominio": "ucm.es", "urls": ["https://www.ucm.es/estudios/master-lenguaespanola"]}))
    res = e.ejecutar(tmp_path / "cat.jsonl", tmp_path / "censo.jsonl", [tmp_path / "r"], tmp_path / "out", tmp_path / "cc")
    assert res == {"unido": 1, "sin_urls_de_la_universidad": 1}


def test_url_real_sin_barra_inventada_y_programas_por_consulta():
    """La unión devolvía la clave normalizada («….html/»), que da 404 o una página vacía: ahora, la URL encontrada."""
    from motor.estudios import emparejar as e
    t = [{"codigo_ruct": "1", "nombre_oficial": "Máster Universitario en Ingeniería Industrial por la Universidad Nacional de Educación a Distancia"}]
    urls = ["https://www.uned.es/estudios/masteres/master-universitario-en-ingenieria-industrial.html",
            "https://www.uned.es/estudios/masteres/master-universitario-en-ingenieria-industrial/asignaturas.html?codAsignatura=1"]
    x = e.emparejar(t, urls)[0]
    assert x["estado"] in {"unido", "dudoso"} and x["url"] == urls[0] and not x["url_es_subpagina"]
    # mismo camino, programa distinto en la consulta: no se mezclan; la paginación sí se quita
    a = "https://www.uab.cat/web/estudiar/masters/informacion-general/-1096480962610.html?param1=1345716413004"
    b = "https://www.uab.cat/web/estudiar/masters/informacion-general/-1096480962610.html?param1=1345740334958"
    assert e.raiz_programa(a) != e.raiz_programa(b)
    assert e.raiz_programa("https://x.es/master-y?start=20") == e.raiz_programa("https://x.es/master-y?start=40")
    textos = {a: "Máster Universitario en Química Industrial", b: "Máster Universitario en Historia del Arte"}
    t2 = [{"codigo_ruct": "2", "nombre_oficial": "Máster Universitario en Historia del Arte por la Universitat Autònoma de Barcelona"}]
    assert e.emparejar(t2, [a, b], textos)[0]["url"] == b


def test_consulta_que_identifica_el_programa_no_se_pierde():
    from motor.estudios import emparejar as e
    assert e.raiz_programa("https://u.es/estudios/titulacion?id=1") != e.raiz_programa("https://u.es/estudios/titulacion?id=2")
    assert e.raiz_programa("https://c.es/?p=101") != e.raiz_programa("https://c.es/?p=202")
    assert e.raiz_programa("https://u.es/master-x/asignaturas.html?cod=9") == e.raiz_programa("https://u.es/master-x/")
