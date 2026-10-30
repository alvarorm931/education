from motor.grados import relaciones as rel

GEN = [
    {"id": "derecho", "tipo": "grado", "clave": "derecho", "nombre": "Derecho", "titulos": ["1", "2"],
     "pagina_propia": True, "area": "Derecho", "rama": "CSJ"},
    {"id": "ade", "tipo": "grado", "clave": "administracion direccion empresa", "nombre": "ADE", "titulos": ["3", "4"],
     "pagina_propia": True, "area": "Empresa", "rama": "CSJ"},
    {"id": "medicina", "tipo": "grado", "clave": "medicina", "nombre": "Medicina", "titulos": ["5"],
     "pagina_propia": True, "area": "Medicina", "rama": "Salud"},
    {"id": "doble-ade-derecho", "tipo": "doble", "clave": "administracion direccion empresa+derecho",
     "nombre": "ADE y Derecho", "titulos": [str(i) for i in range(10, 40)], "pagina_propia": True},
]


def test_parecidas_por_dobles_y_rama_y_sin_relleno():
    par = rel.parecidas(GEN, {})
    assert [x["generico"] for x in par["derecho"]] == ["ade"]
    assert any("dobles" in m for m in par["derecho"][0]["motivos"])
    assert par["medicina"] == []  # nada cercano: mejor vacío que inventado


def test_dobles_que_lo_incluyen_y_lo_forman():
    incluye, forman = rel.dobles(GEN)
    assert [x["generico"] for x in incluye["derecho"]] == ["doble-ade-derecho"]
    assert [x["generico"] for x in forman["doble-ade-derecho"]] == ["ade", "derecho"]


def test_indice_de_asignaturas_solo_de_planes_comprobados():
    fichas = [{"codigo": "1", "nombre": "Derecho", "universidades": [{"nombre": "U1"}], "generico": {"id": "derecho"},
               "plan": {"comprobado": True, "asignaturas": [{"nombre": "Derecho Civil I", "tipo": "obligatoria", "curso": 1},
                                                            {"nombre": "Derecho Civil II", "tipo": "obligatoria", "curso": 2}]}},
              {"codigo": "2", "nombre": "Derecho", "universidades": [{"nombre": "U2"}], "generico": {"id": "derecho"},
               "plan": {"comprobado": False, "asignaturas": [{"nombre": "Derecho Civil", "tipo": "obligatoria"}]}}]
    idx = rel.indice_asignaturas(fichas)
    assert idx[0]["clave"] == "derecho civil" and idx[0]["titulos"] == 1
