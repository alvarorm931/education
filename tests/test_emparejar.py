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
