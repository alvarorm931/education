import json

from motor.estudios import clasificar as c
from motor.estudios import extraer as e

PORTADA = ('<html><head><title>Escuela de Finanzas Ejemplo | Másteres en Madrid</title>'
           '<meta name="description" content="Escuela de negocios en Madrid desde 1990"></head>'
           '<body><nav><a href="/m">Másteres</a><a href="/a">Admisiones</a></nav>'
           '<h1>Escuela de Finanzas Ejemplo</h1><p>Formamos a profesionales de las finanzas.</p></body></html>')


def test_texto_portada_lleva_titulo_metadatos_menu_y_texto():
    t = c.texto_portada(PORTADA)
    assert "Título: Escuela de Finanzas Ejemplo" in t and "description: Escuela de negocios en Madrid" in t
    assert "Másteres · Admisiones" in t and "Formamos a profesionales" in t


def test_normalizar_listas_cerradas_y_nombre_con_cita():
    t = c.texto_portada(PORTADA)
    n = c.normalizar({"categoria": "centro", "tipo_centro": "escuela_negocios", "ambito": "espana",
                      "vende_masters": True, "confianza": "alta", "motivo": "Escuela con másteres propios",
                      "nombre": {"v": "Escuela de Finanzas Ejemplo", "c": "Escuela de Finanzas Ejemplo"}}, t)
    assert n["nombre"] == "Escuela de Finanzas Ejemplo" and c.apto_para_censo(n)
    n2 = c.normalizar({"categoria": "portal", "nombre": {"v": "Otra Escuela", "c": "Otra Escuela"}}, t)
    assert n2["categoria"] is None and n2["nombre"] is None and n2["nombre_propuesto"] == "Otra Escuela"
    assert not c.apto_para_censo({"categoria": "agregador", "ambito": "espana"})
    assert not c.apto_para_censo({"categoria": "centro", "ambito": "otro_pais"})


def test_lote_sin_red(tmp_path, monkeypatch):
    filas = [{"id": "prov-1", "dominio": "efe.es", "web": "https://efe.es", "urls_programa": 12, "titulos": []},
             {"id": "prov-2", "dominio": "res.es", "web": "https://res.es", "urls_programa": 3, "titulos": []}]
    (tmp_path / "e.jsonl").write_text("".join(json.dumps(f) + "\n" for f in filas))

    def capturar(urls, procesar=None, **kw):
        return [{"url": "https://efe.es", "sha256": "a", "reserva_tdm": False, "texto": procesar(PORTADA)},
                {"url": "https://res.es", "sha256": "b", "reserva_tdm": True}]

    monkeypatch.setattr(e, "capturar", capturar)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "prueba")
    estado = {}

    class R:
        def __init__(self, d=None, texto=""):
            self.status_code, self._d, self.text, self.content = 200, d, texto, texto.encode()

        def json(self):
            return self._d

    def post(url, headers, json, timeout):
        estado["ids"] = [p["custom_id"] for p in json["requests"]]
        return R({"id": "msgbatch_c", "processing_status": "ended", "results_url": "https://r/c"})

    def get(url, headers, timeout):
        resp = {"categoria": "centro", "tipo_centro": "escuela_negocios", "ambito": "espana", "vende_masters": True,
                "confianza": "alta", "motivo": "x", "nombre": {"v": "Escuela de Finanzas Ejemplo",
                                                                "c": "Escuela de Finanzas Ejemplo | Másteres"}}
        linea = {"custom_id": estado["ids"][0], "result": {"type": "succeeded", "message": {
            "content": [{"type": "text", "text": json.dumps(resp)}], "usage": {"input_tokens": 800, "output_tokens": 60}}}}
        return R(texto=json.dumps(linea))

    monkeypatch.setattr(c.requests, "post", post)
    monkeypatch.setattr(c.requests, "get", get)
    res = c.lote(tmp_path / "e.jsonl", tmp_path / "out", guarda=e.Guarda(None))
    assert len(estado["ids"]) == 1  # la portada con reserva TDM no se envía
    assert res["clasificados"] == 1 and res["apto_censo"] == 1 and res["portada_reserva_tdm"] == 1
    out = [json.loads(l) for l in (tmp_path / "out" / "clasificacion.jsonl").read_text().splitlines()]
    assert out[0]["nombre"] == "Escuela de Finanzas Ejemplo" and out[0]["apto_censo"]
    assert "Formamos" not in (tmp_path / "out" / "clasificacion.jsonl").read_text()


def test_aplicar_descarta_lo_que_no_es_centro_y_vale_la_ultima_legible(tmp_path):
    censo = [{"id": "a", "dominio": "a.es", "estado": "verificado", "nombres": []},
             {"id": "b", "dominio": "b.es", "estado": "verificado", "nombres": []},
             {"id": "c", "dominio": "c.es", "estado": "oficial", "nombres": []}]
    (tmp_path / "p.jsonl").write_text("".join(json.dumps(x) + "\n" for x in censo))
    c1 = [{"id": "a", "categoria": None}, {"id": "b", "categoria": "agregador", "ambito": "espana"}]
    c2 = [{"id": "a", "categoria": "centro", "ambito": "espana", "vende_masters": True, "nombre": "Escuela A"}]
    (tmp_path / "c1.jsonl").write_text("".join(json.dumps(x) + "\n" for x in c1))
    (tmp_path / "c2.jsonl").write_text("".join(json.dumps(x) + "\n" for x in c2))
    r = c.aplicar(tmp_path / "p.jsonl", [tmp_path / "c1.jsonl", tmp_path / "c2.jsonl"], tmp_path / "o")
    assert r["verificado/None"] == 1 and r["descartado/agregador"] == 1 and r["oficial/None"] == 1
    out = {x["id"]: x for x in map(json.loads, (tmp_path / "o/datos/estudios/censo/proveedores.jsonl").read_text().splitlines())}
    assert out["a"]["nombres"] == ["Escuela A"]
    assert (tmp_path / "o/datos/estudios/censo/agregadores.jsonl").read_text().count("b.es") == 1


def test_peticion_con_salida_estructurada_y_nombre_plano():
    p = c.peticion("x", "texto")
    f = p["params"]["output_config"]["format"]
    assert f["type"] == "json_schema" and f["schema"]["additionalProperties"] is False
    assert set(f["schema"]["required"]) == set(f["schema"]["properties"])
    t = c.texto_portada(PORTADA)
    n = c.normalizar({"categoria": "agregador", "tipo_centro": "ninguno", "ambito": "espana", "vende_masters": False,
                      "nombre": "Escuela de Finanzas Ejemplo", "cita_nombre": "Escuela de Finanzas Ejemplo",
                      "confianza": "alta", "motivo": "x"}, t)
    assert n["tipo_centro"] is None and n["nombre"] == "Escuela de Finanzas Ejemplo"
