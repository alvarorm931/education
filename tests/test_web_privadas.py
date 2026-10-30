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
