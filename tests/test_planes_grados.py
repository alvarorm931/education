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


def test_varios_planes_se_piden_aunque_no_se_sepa_de_que_grado_son(tmp_path):
    import json

    from motor.grados import planes
    (tmp_path / "boe_actos.jsonl").write_text("\n".join(json.dumps(x) for x in [
        {"identificador": "BOE-A-2023-778", "tipo": "plan", "varios_planes": True, "titulo_grado": None},
        {"identificador": "BOE-A-2023-1", "tipo": "correccion", "varios_planes": True, "titulo_grado": None},
        {"identificador": "BOE-A-2023-2", "tipo": "plan", "varios_planes": False, "titulo_grado": "Grado en X"}]))
    assert planes.varios_planes(tmp_path) == ["BOE-A-2023-778"]
    res = planes.calcular([], {}, {}, set(), ["BOE-A-2023-778"])
    assert res["ids"] == ["BOE-A-2023-778"] and res["resoluciones_con_varios_planes_pendientes"] == 1
