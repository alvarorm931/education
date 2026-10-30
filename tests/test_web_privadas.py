from motor.grados import web_privadas as wp


def test_url_de_grado():
    assert wp.es_url_grado("https://www.ufv.es/estudios/grado-en-derecho/")
    assert wp.es_url_grado("https://www.nebrija.com/carreras-universitarias/grado-psicologia/")
    assert not wp.es_url_grado("https://www.ufv.es/master-universitario-en-abogacia/")
    assert not wp.es_url_grado("https://www.ufv.es/blog/grado-en-derecho-salidas/")


def test_unir_grados_con_su_url():
    grados = [{"codigo": "1", "clase": "grado", "nombre": "Derecho", "componentes": []},
              {"codigo": "2", "clase": "grado", "nombre": "Administración y Dirección de Empresas", "componentes": []},
              {"codigo": "3", "clase": "doble", "nombre": "Derecho y ADE",
               "componentes": [{"nombre": "Derecho"}, {"nombre": "Administración y Dirección de Empresas"}]}]
    urls = ["https://u.es/estudios/grado-en-derecho/", "https://u.es/en/degree-derecho/",
            "https://u.es/estudios/grado-en-administracion-y-direccion-de-empresas/",
            "https://u.es/estudios/doble-grado-derecho-administracion-direccion-empresas/",
            "https://u.es/blog/grado-en-derecho-que-estudiar/"]
    u = wp.unir(grados, urls)
    assert u["1"]["url"] == "https://u.es/estudios/grado-en-derecho/"
    assert u["2"]["url"].endswith("grado-en-administracion-y-direccion-de-empresas/")
    assert u["3"]["url"].endswith("doble-grado-derecho-administracion-direccion-empresas/")


def test_importes_con_su_tipo():
    html = "<p>Precio por crédito: 180 € ECTS</p><p>Reserva de plaza 1.100 €</p><p>Mensualidad de 795 euros</p>" \
           "<script>var x='9.999 €'</script><p>Precio por curso académico 9.420 €</p>"
    i = wp.importes(html)
    assert [(x["valor"], x["tipo"]) for x in i] == [(180, "credito"), (1100, "reserva"), (795, "mensual"), (9420, "curso")]
    assert all(len(x["contexto_sha256"]) == 16 for x in i)


def test_otra_sede_y_paginas_que_no_son_ficha():
    grados = [{"codigo": "1", "clase": "grado", "nombre": "Fisioterapia", "componentes": []},
              {"codigo": "2", "clase": "grado", "nombre": "Empresas y Actividades Turísticas", "componentes": []}]
    urls = ["https://ue.com/grado-fisioterapia-madrid/", "https://ue.com/grado-fisioterapia-valencia/",
            "https://u.es/trabajo-fin-grado-empresas-actividades-turisticas"]
    u = wp.unir(grados, urls, propias={"europea", "valencia"})
    assert u["1"]["url"] == "https://ue.com/grado-fisioterapia-valencia/"
    assert "2" not in u


def test_importes_fuera_de_rango():
    i = wp.importes("<p>Salario medio por curso 70.000 €</p><p>Precio por curso 9.420 €</p>")
    assert [(x["valor"], x["verosimil"]) for x in i] == [(70000, False), (9420, True)]


def test_unir_descarta_noticias_fp_y_falsos_grado():
    grados = [{"codigo": "1", "clase": "grado", "nombre": "Fisioterapia", "componentes": []},
              {"codigo": "2", "clase": "grado", "nombre": "Marketing", "componentes": []},
              {"codigo": "3", "clase": "grado", "nombre": "Enseñanza y Animación Sociodeportiva", "componentes": []}]
    urls = ["https://u.es/el-grado-en-fisioterapia-celebra-a-su-patron-san-juan-de-dios/",
            "https://u.es/marketing-directo-integrado",
            "https://u.es/formacion-profesional/grado-superior-ensenanza-animacion-sociodeportiva/"]
    assert wp.unir(grados, urls) == {}
    urls.append("https://u.es/estudios/grado-en-fisioterapia-online/")
    assert wp.unir(grados, urls)["1"]["url"] == "https://u.es/estudios/grado-en-fisioterapia-online/"


def test_unir_usa_el_nombre_en_ingles_de_los_titulos_bilingues():
    g = {"codigo": "9", "clase": "grado", "nombre": "Diseño de Moda / Bachelor in Fashion Design", "componentes": []}
    u = wp.unir([g], ["https://www.ie.edu/university/studies/bachelor-in-fashion-design/"])
    assert u["9"]["url"].endswith("bachelor-in-fashion-design/")


def test_importes_no_toma_sueldos_por_precios():
    imp = wp.importes("<p>Un ingeniero tiene un sueldo medio de 28.000 € al año.</p><p>Precio por curso: 5.990 €</p>")
    assert [(i["valor"], i["tipo"], i["verosimil"]) for i in imp] == [(28000, "sueldo", False), (5990, "curso", True)]


def test_importes_en_formato_ingles():
    imp = wp.importes("<p>Tuition fee: €24,900 per year. Reservation: €1,500.</p>")
    assert [i["valor"] for i in imp] == [24900, 1500]


def test_titulo_que_contradice_la_union_por_direccion():
    from motor.grados.web_privadas import titulo_contradice
    g = {"clase": "grado", "nombre": "Fisioterapia"}
    assert titulo_contradice(g, "Proceso de Admisión Grado en Enfermería | UPSA")
    assert titulo_contradice(g, "Doble grado en Podología + Fisioterapia")
    assert not titulo_contradice(g, "Grado en Fisioterapia | UPSA")
    assert not titulo_contradice(g, "Admisión")  # genérico: vale la dirección
    assert titulo_contradice({"clase": "grado", "nombre": "Animación"}, "FP en Videojuegos | Universidad Europea")
    doble = {"clase": "doble", "nombre": "X", "componentes": [{"nombre": "Economía"},
                                                            {"nombre": "Administración y Dirección de Empresas"}]}
    assert titulo_contradice(doble, "Doble Grado en Economía + Finanzas y Contabilidad")
    assert not titulo_contradice(doble, "Doble Grado en ADE y Economía | X")
    assert not titulo_contradice({"clase": "grado", "nombre": "Ingeniería Informática"},
                                 "Grado en Ingenier&iacute;a Inform&aacute;tica - Universidad Europea")


def test_objetivos_por_centros_propios_de_privadas_y_adscritos_de_publicas(tmp_path):
    import json
    from motor.grados.web_privadas import objetivos_centros
    (tmp_path / "041.json").write_text(json.dumps({"codigo": "041", "nombre": "Ramón Llull", "tipo": "Privada",
        "web": "https://www.url.edu", "centros": [
            {"codigo": "08037051", "nombre": "IQS", "web": "https://www.iqs.url.edu/", "vinculacion": "Propio"},
            {"codigo": "08070088", "nombre": "Derecho Esade", "web": "https://www.esade.edu/", "vinculacion": "Propio"},
            {"codigo": "08033067", "nombre": "Empresa Esade", "web": "https://www.esade.edu/", "vinculacion": "Propio"}]}))
    (tmp_path / "004.json").write_text(json.dumps({"codigo": "004", "nombre": "Barcelona", "tipo": "Pública",
        "web": "https://www.ub.edu", "centros": [
            {"codigo": "08072000", "nombre": "CETT", "web": "https://www.cett.es", "vinculacion": "Adscrito"},
            {"codigo": "08001234", "nombre": "Facultad", "web": "https://www.ub.edu/dret", "vinculacion": "Propio"}]}))

    def t(codigo, nombre, uni, ucod, tipo, centro):
        return {"codigo": codigo, "clase": "grado", "nombre": nombre, "situacion": "Activo", "universidad_tipo": tipo,
                "universidades": [{"nombre": uni, "codigo": ucod}],
                "imparticiones": [{"situacion": "Activo", "unidad_codigo": centro, "universidad": uni}]}
    cat = [t("1", "Química", "Ramón Llull", "041", "Privada", "08037051"),
           t("2", "Derecho", "Ramón Llull", "041", "Privada", "08070088"),
           t("3", "ADE", "Ramón Llull", "041", "Privada", "08033067"),
           t("4", "Turismo", "Barcelona", "004", "Pública", "08072000"),
           t("5", "Derecho", "Barcelona", "004", "Pública", "08001234")]
    obj = {o["web"]: (o, sorted(g["codigo"] for g in gs)) for o, gs in objetivos_centros(cat, tmp_path)}
    assert set(obj) == {"https://www.iqs.url.edu/", "https://www.esade.edu/", "https://www.cett.es"}
    assert obj["https://www.esade.edu/"][1] == ["2", "3"]  # un rastreo por dominio
    assert obj["https://www.cett.es"][0]["centro_adscrito"] and obj["https://www.cett.es"][1] == ["4"]
