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
    assert r["4310001"]["estado"] == "unido" and r["4310001"]["url"].endswith("1371210340413/")
    assert r["4310002"]["url"].endswith("1371212345678/")
    assert all(x["estado"] == "sin_pagina" for x in e.emparejar(titulos, urls))  # sin textos, la URL no dice nada


def test_tramos_pegados_e_idiomas():
    from motor.estudios import emparejar as e
    t = [{"codigo_ruct": "1", "nombre_oficial": "Máster Universitario en Antropología Física: Evolución y Biodiversidad Humanas por la Universidad Complutense de Madrid"},
         {"codigo_ruct": "2", "nombre_oficial": "Máster Universitario en Lengua Española por la Universidad Complutense de Madrid"}]
    urls = ["https://www.ucm.es/estudios/master-antropologiafisica", "https://www.ucm.es/estudios/master-lenguaespanola"]
    r = {x["codigo_ruct"]: x for x in e.emparejar(t, urls)}
    assert r["2"]["estado"] == "unido" and r["2"]["url"].endswith("master-lenguaespanola/")
    assert r["1"]["url"] is None or r["1"]["url"].endswith("master-antropologiafisica/")
    t2 = [{"codigo_ruct": "3", "nombre_oficial": "Máster Universitario en Advocacia i Procura por la Universitat Jaume I"}]
    urls2 = ["https://www.uji.es/es/masters/advocacia-procura/", "https://www.uji.es/ca/masters/advocacia-procura/",
             "https://www.uji.es/en/masters/advocacia-procura/"]
    x = e.emparejar(t2, urls2)[0]
    assert x["estado"] == "unido" and "/es/" in x["url"]
