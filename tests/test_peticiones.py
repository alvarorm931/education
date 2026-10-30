import json

from motor.estudios import peticiones as p


def test_prioridad_y_lista(tmp_path):
    ficha_oculta = {"url": "https://x.es/master-a", "es_programa": True, "formulario_pide_correo": True, "importes_euros": 0,
                    "precio_jsonld": None, "temas": {"metodologia": False, "evaluacion": False, "plazas": False,
                                                     "horario": True, "asignaturas": True}}
    ficha_abierta = {"url": "https://y.es/master-b", "es_programa": True, "formulario_pide_correo": False, "importes_euros": 2,
                     "precio_jsonld": None, "temas": {k: True for k in ("metodologia", "evaluacion", "plazas", "horario", "asignaturas")}}
    (tmp_path / "censo.jsonl").write_text("\n".join(json.dumps(x) for x in [
        {"id": "x", "dominio": "x.es", "estado": "verificado"}, {"id": "y", "dominio": "y.es", "estado": "verificado"},
        {"id": "z", "dominio": "z.es", "estado": "candidato"}]))
    (tmp_path / "r" / "oferta_web").mkdir(parents=True)
    for i, m in (("x", ficha_oculta), ("y", ficha_abierta), ("z", ficha_oculta)):
        (tmp_path / "r" / "oferta_web" / f"{i}.json").write_text(json.dumps({"centro": {"id": i}, "urls_programa": 5, "muestra": [m]}))
    res = p.ejecutar(tmp_path / "censo.jsonl", [tmp_path / "r"], tmp_path / "out")
    assert res["centros"] == 1 and res["con_precio_tras_formulario"] == 1
    fila = json.loads((tmp_path / "out" / "datos" / "estudios" / "peticiones" / "centros_a_pedir.jsonl").read_text())
    assert fila["dominio"] == "x.es" and fila["campos_que_faltan"] == ["evaluacion", "metodologia", "plazas", "precio_total"]


def test_peticiones_desde_fichas(tmp_path):
    import json
    from motor.estudios import peticiones as pe
    fichas = [{"grupo": "no_oficial", "es_master": True, "proveedor": "prov-a", "centro": "Escuela A", "url": "https://a.es/m1",
               "campos": {"asignaturas": {"valor": ["x"]}}},
              {"grupo": "no_oficial", "es_master": True, "proveedor": "prov-a", "centro": "Escuela A", "url": "https://a.es/m2",
               "campos": {"precio_total": {"valor": 9800}}},
              {"grupo": "no_oficial", "es_master": False, "proveedor": "prov-a", "url": "https://a.es/curso", "campos": {}}]
    (tmp_path / "f.jsonl").write_text("".join(json.dumps(x) + "\n" for x in fichas))
    r = pe.desde_fichas([tmp_path / "f.jsonl"], tmp_path / "o")
    assert r["centros"] == 1 and r["fichas_master"] == 2 and r["sin_precio_total"] == 1
    x = json.loads((tmp_path / "o/datos/estudios/peticiones/centros_a_pedir_desde_fichas.jsonl").read_text())
    assert x["ejemplo"]["precio_total"] == "https://a.es/m1" and x["parte_sin_precio"] == 0.5
