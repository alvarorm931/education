from motor.estudios import censo as c


def test_dominio_registrado():
    assert c.dominio_registrado("https://www.aq.upm.es/") == "upm.es"
    assert c.dominio_registrado("esimar.edu.es") == "esimar.edu.es"
    assert c.dominio_registrado("https://online.anahuac.mx/x") == "anahuac.mx"


def test_id_estable():
    assert c.id_proveedor("upm.es") == c.id_proveedor("upm.es") and c.id_proveedor("upm.es").startswith("prov-")


def test_filtros():
    assert c.filtro_candidato({"dominio": "unc.edu.ar", "tld": "ar", "idiomas": ["spa"], "paginas": 800}) == "otro_pais"
    assert c.filtro_candidato({"dominio": "emagister.com", "tld": "com", "idiomas": ["spa"], "paginas": 900}) == "agregador_o_medio"
    assert c.filtro_candidato({"dominio": "eigp.es", "tld": "es", "idiomas": ["spa"], "paginas": 70}) is None
    assert c.filtro_candidato({"dominio": "inesalud.com", "tld": "com", "idiomas": ["spa"], "paginas": 98}) is None
    assert c.filtro_candidato({"dominio": "x.com", "tld": "com", "idiomas": ["eng"], "paginas": 98}) == "idioma"
    assert c.filtro_candidato({"dominio": "eshi.es", "tld": "es", "idiomas": ["-"], "paginas": 1}) is None
    assert c.filtro_candidato({"dominio": "x.com", "tld": "com", "idiomas": ["-"], "paginas": 1}) == "una_sola_pagina"


def test_construir_une_ruct_y_commoncrawl():
    centros = [{"codigo": "025", "nombre": "Universidad Politécnica de Madrid", "grupo": "universidad", "tipo": "Pública",
                "web": "https://www.upm.es", "centros": [{"codigo": "28026870", "nombre": "ETS Arquitectura",
                                                          "vinculacion": "Propio", "web": "https://www.aq.upm.es/"}]}]
    cc = [{"dominio": "upm.es", "tld": "es", "idiomas": ["spa"], "paginas": 5, "ejemplos": ["https://www.upm.es/master"]},
          {"dominio": "eigp.es", "tld": "es", "idiomas": ["spa"], "paginas": 70, "ejemplos": []},
          {"dominio": "unc.edu.ar", "tld": "ar", "idiomas": ["spa"], "paginas": 800, "ejemplos": []}]
    p = {x["dominio"]: x for x in c.construir(centros, cc)}
    assert set(p) == {"upm.es", "eigp.es"}
    assert p["upm.es"]["estado"] == "oficial" and len(p["upm.es"]["ruct"]) == 2 and "commoncrawl" in p["upm.es"]["fuentes"]
    assert p["eigp.es"]["estado"] == "candidato"
