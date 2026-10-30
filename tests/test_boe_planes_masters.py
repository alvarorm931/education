import json

from motor.estudios import boe_planes_masters as bp


def _doc():
    filas = [["Asignatura", "Carácter", "ECTS"]] + [[f"Asignatura obligatoria {i}", "OB", "6"] for i in range(7)] + \
            [["Mercados Financieros Avanzados", "OP", "6"], ["Trabajo Fin de Máster", "TFM", "12"]]
    return {"identificador": "BOE-A-2011-1220", "titulo": "Resolución de la Universidad de Murcia, por la que se "
            "publica el plan de estudios de Máster en Finanzas.", "texto": "", "url": "https://www.boe.es/x",
            "tablas": [{"contenido": [["Tipo de materia", "Créditos"], ["Obligatorias", "42"], ["Optativas", "6"],
                                      ["Trabajo fin de Máster", "12"], ["Total", "60"]]},
                       {"contenido": filas}]}


def test_plan_de_master_con_tfm_se_comprueba():
    planes = bp.leer_plan(_doc())
    assert len(planes) == 1
    p = planes[0]
    assert p["comprobacion"] == "completo"
    nombres = [f["nombre"] for f in p["filas_plan"]]
    assert "Trabajo Fin de Máster" in nombres and len(nombres) == 9


def test_medir_une_por_el_identificador_de_la_ficha(tmp_path):
    r = tmp_path / "r" / "datos" / "estudios" / "masters" / "ruct"
    r.mkdir(parents=True)
    (r / "4310193.json").write_text(json.dumps({"codigo": "4310193", "boe": {"plan": {"identificador": "BOE-A-2011-1220"}},
                                                "fuente": {"capturado": "2026-10-30T11:00:00+00:00"}}))
    t = tmp_path / "t" / "2011" / "01"
    t.mkdir(parents=True)
    (t / "BOE-A-2011-1220.json").write_text(json.dumps(_doc()))
    (t / "BOE-A-2099-1.json").write_text(json.dumps({**_doc(), "identificador": "BOE-A-2099-1"}))  # de nadie
    res = bp.cmd_medir(tmp_path / "t", [tmp_path / "r"], tmp_path / "o")
    assert res["documentos"] == 1 and res["comprobados"] == 1 and res["codigos"] == 1
    fila = json.loads((tmp_path / "o/datos/estudios/masters/boe_planes_masters.jsonl").read_text())
    assert fila["codigos_ruct"] == ["4310193"] and fila["planes"][0]["filas_plan"][0]["creditos"] == 6


def test_union_por_nombre_y_universidad_solo_si_es_unica():
    cat = [{"codigo_ruct": "1", "nombre_oficial": "Máster Universitario en Comercio Internacional por la Universidad de Extremadura",
            "universidad": "Extremadura", "situacion": "Activo"},
           {"codigo_ruct": "2", "nombre_oficial": "Máster Universitario en Comercio Internacional y Logística por la Universidad de Extremadura",
            "universidad": "Extremadura", "situacion": "Activo"},
           {"codigo_ruct": "3", "nombre_oficial": "Máster Universitario en Comercio Internacional por la Universidad de Murcia",
            "universidad": "Murcia", "situacion": "Activo"}]
    res = [{"identificador": "BOE-A-2025-1", "tipo": "plan", "titulo": "Resolución de 16 de diciembre de 2025, de la "
            "Universidad de Extremadura, por la que se publica el plan de estudios de Máster Universitario en Comercio Internacional."},
           {"identificador": "BOE-A-2025-2", "tipo": "otro", "titulo": "Convenio con la Universidad de Murcia"}]
    assert bp.ids_por_nombre(res, cat) == {"BOE-A-2025-1": ["1"]}


def test_union_por_nombre_universidad_exacta_traduccion_y_fecha():
    cat = [{"codigo_ruct": "4310001", "nombre_oficial": "Máster Universitario en Química por la Universidad de Barcelona",
            "universidad": "Barcelona", "situacion": "Activo"},
           {"codigo_ruct": "4316002", "nombre_oficial": "Máster Universitario en Gestión de Talento / Master in Talent "
            "Management por la Universidad Pontificia Comillas", "universidad": "Pontificia Comillas", "situacion": "Activo"},
           {"codigo_ruct": "3500003", "nombre_oficial": "Máster Universitario en Física por la Universitat de València",
            "universidad": "València (Estudi General)", "situacion": "Activo"}]
    t = "Resolución de 1 de marzo, de la {}, por la que se publica el plan de estudios de {}."
    res = [{"identificador": "BOE-A-2010-1", "tipo": "plan", "titulo": t.format("Universidad Autónoma de Barcelona", "Máster en Química")},
           {"identificador": "BOE-A-2010-2", "tipo": "plan", "titulo": t.format("Universidad de Barcelona", "Máster en Química")},
           {"identificador": "BOE-A-2017-3", "tipo": "plan", "titulo": t.format("Universidad Pontificia Comillas",
                                                                               "Máster en Gestión de Talento/Talent Management")},
           # el plan de 2012 es de un código anterior: los 35xxxxx no existían
           {"identificador": "BOE-A-2012-4", "tipo": "plan", "titulo": t.format("Universitat de València", "Máster en Física")},
           {"identificador": "BOE-A-2023-5", "tipo": "plan_modif", "titulo": t.format("Universitat de València", "Máster en Física")},
           {"identificador": "BOE-A-2023-6", "tipo": "plan", "titulo": "Resolución de 2 de mayo, de la Universitat de València, "
            "por la que se corrigen errores en la de 1 de marzo, por la que se publica el plan de estudios de Máster en Física."}]
    assert bp.ids_por_nombre(res, cat) == {"BOE-A-2010-2": ["4310001"], "BOE-A-2017-3": ["4316002"], "BOE-A-2023-5": ["3500003"]}


def test_mismo_nombre_con_codigo_antiguo_y_nuevo():
    cat = [{"codigo_ruct": "4314001", "nombre_oficial": "Máster Universitario en Cine por la Universidad de Barcelona",
            "universidad": "Barcelona", "situacion": "Activo"},
           {"codigo_ruct": "3500809", "nombre_oficial": "Máster Universitario en Cine por la Universidad de Barcelona",
            "universidad": "Barcelona", "situacion": "Activo"}]
    t = "Resolución de 1 de marzo, de la Universidad de Barcelona, por la que se publica {} de Máster Universitario en Cine."
    res = [{"identificador": "BOE-A-2015-1", "tipo": "plan", "titulo": t.format("el plan de estudios")},
           {"identificador": "BOE-A-2024-2", "tipo": "plan", "titulo": t.format("el plan de estudios")},
           {"identificador": "BOE-A-2024-3", "tipo": "plan_modif", "titulo": t.format("la modificación del plan de estudios")}]
    assert bp.ids_por_nombre(res, cat) == {"BOE-A-2015-1": ["4314001"], "BOE-A-2024-2": ["3500809"]}
