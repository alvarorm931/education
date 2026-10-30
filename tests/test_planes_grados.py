from motor.grados import planes


def test_universidad_del_boe_con_la_del_catalogo():
    conocidas = {"pais vasco euskal herriko unibertsitatea", "granada", "politecnica madrid"}
    assert planes.resolver_universidad("granada", conocidas) == "granada"
    assert planes.resolver_universidad("pais vasco euskal herriko unibertsitatea upv ehu", conocidas) == "pais vasco euskal herriko unibertsitatea"
    assert planes.resolver_universidad("madrid", conocidas) == "madrid"  # ambigua o desconocida: se deja


def test_pendientes_primero_lo_mas_reciente():
    cat = [{"codigo": "2500001", "clase": "grado", "situacion": "Activo", "nombre": "Derecho",
            "universidades": [{"nombre": "Granada"}]}]
    actos = {("granada", "derecho"): [{"identificador": "BOE-A-2024-2", "fecha": "2024-01-01"},
                                       {"identificador": "BOE-A-2015-1", "fecha": "2015-01-01"}]}
    r = planes.calcular(cat, {"2500001": {"identificador": "BOE-A-2010-9"}}, actos, {"BOE-A-2015-1"})
    assert r["ids"] == ["BOE-A-2024-2", "BOE-A-2010-9"]
    assert r["con_plan_en_ruct"] == 1 and r["texto_mas_reciente_ya_leido"] == 0
