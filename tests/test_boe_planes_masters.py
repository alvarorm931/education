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
