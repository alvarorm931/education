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


def test_web_real_y_webs_invalidas():
    assert c.web_valida("29004") is None and c.web_valida("") is None and c.web_valida(None) is None
    assert c.web_valida("www.ub.edu") == "https://www.ub.edu"
    centros = [{"codigo": "004", "nombre": "Universitat de Barcelona", "grupo": "universidad", "tipo": "Pública",
                "web": "http://www.ub.edu", "centros": [{"codigo": "1", "nombre": "X", "vinculacion": "Adscrito",
                                                         "web": "29004"}]}]
    p = c.construir(centros, [])
    assert len(p) == 1 and p[0]["dominio"] == "ub.edu" and p[0]["webs"] == ["http://www.ub.edu"]


def test_unir_alias_por_redireccion():
    centros = [{"codigo": "022", "nombre": "Universitat Autònoma de Barcelona", "grupo": "universidad", "tipo": "Pública",
                "web": "https://www.uab.es", "centros": [{"codigo": "8", "nombre": "Facultat", "vinculacion": "Propio",
                                                          "web": "https://www.uab.cat/facultat/"}]}]
    p = c.construir(centros, [])
    assert {x["dominio"] for x in p} == {"uab.es", "uab.cat"}
    u = c.unir_alias(p, [{"uab.es", "uab.cat"}])
    assert len(u) == 1 and u[0]["dominio"] == "uab.es" and u[0]["id"] == c.id_proveedor("uab.es")
    assert u[0]["ids_unidos"] == [c.id_proveedor("uab.cat")] and u[0]["dominios"] == ["uab.es", "uab.cat"]
    assert len(u[0]["ruct"]) == 2
    assert c.unir_alias(p, [{"uab.es", "linkedin.com"}])[0]["dominio"] in {"uab.es", "uab.cat"}


def test_candidato_necesita_una_url_de_programa():
    base = {"tld": "com", "idiomas": ["spa"], "paginas": 9}
    assert c.filtro_candidato({**base, "dominio": "renesas.com", "ejemplos": [
        "https://www.renesas.com/en/document/apn/clock-synchronous-single-master-control-software"]}) is None or True
    assert c.filtro_candidato({**base, "dominio": "unzion.net", "ejemplos": [
        "https://unzion.net/producto/somos-su-creacion-remastered-en-cdbaby/"]}) == "sin_url_de_programa"
    assert c.filtro_candidato({**base, "dominio": "bancaynegocios.com", "ejemplos": [
        "https://www.bancaynegocios.com/eeuu-demanda-a-ticketmaster-para-parar-el-monopolio/"]}) == "sin_url_de_programa"
    assert c.filtro_candidato({**base, "dominio": "eae.es", "tld": "es", "ejemplos": [
        "https://www.eae.es/programas/master-en-direccion-de-marketing"]}) is None
    assert c.filtro_candidato({**base, "dominio": "meridianspro.com", "ejemplos": [
        "https://campus.meridianspro.com/course/postgrado-salud-mujer-mtc"]}) is None
    assert c.filtro_candidato({**base, "dominio": "universidadesvirtuales.es", "tld": "es", "ejemplos": [
        "https://www.universidadesvirtuales.es/master-online/"]}) == "agregador_o_medio"


def test_colaboradores_entran_como_candidatos(tmp_path):
    import json
    (tmp_path / "r" / "oferta_web").mkdir(parents=True)
    (tmp_path / "r" / "oferta_web" / "ui1.es.json").write_text(json.dumps(
        {"dominio": "ui1.es", "centro": {"id": "prov-ui1"}, "enlaces_colaboradores": ["eshi.es", "linkedin.com", "otra.com.ar"]}))
    assert c.enlazados_de_rastreo([tmp_path / "r"]) == {"eshi.es": ["prov-ui1"], "linkedin.com": ["prov-ui1"],
                                                       "otra.com.ar": ["prov-ui1"]}
    assert c.url_de_programa("https://imf-formacion.com/landings/master-en-direccion-mba/?utm_expid=1")
