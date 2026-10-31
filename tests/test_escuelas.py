from motor.estudios import escuelas


def test_fichas_de_master_con_sus_paginas_de_precio_detras():
    res = {"programas": ["https://www.ie.edu/masters/master-in-finance/", "https://www.ie.edu/bachelor/business/",
                         "https://www.ie.edu/masters/mba/"],
           "subpaginas_precio": ["https://www.ie.edu/masters/master-in-finance/admissions-fees",
                                 "https://www.ie.edu/bachelor/business/fees"]}
    fs = escuelas.filas(res, "ie.edu")
    assert [x["url"] for x in fs] == ["https://www.ie.edu/masters/master-in-finance/",
                                      "https://www.ie.edu/masters/master-in-finance/admissions-fees",
                                      "https://www.ie.edu/masters/mba/"]
    assert all(x["grupo"] == "no_oficial" and x["proveedor"].startswith("prov-") for x in fs)
    assert escuelas.filas(res, "ie.edu", max_paginas=1)[0]["url"].endswith("master-in-finance/")


def test_las_que_rechazan_al_lector_no_se_leen(tmp_path):
    assert escuelas.ejecutar("esade.edu", tmp_path)["no_se_lee"]


def test_paginas_de_precio_por_su_nombre():
    from motor.estudios.rastreador import SUBPAGINA_PRECIO
    for ok in ("admissions-fees", "fees", "tuition-and-financing", "precio", "becas-y-financiacion", "admisión"):
        assert SUBPAGINA_PRECIO.search(ok), ok
    for no in ("faculty", "curriculum", "programa"):
        assert not SUBPAGINA_PRECIO.search(no), no
