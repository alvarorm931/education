import json

from motor.estudios import extraer as ex
from motor.estudios import recitar as rc

TEXTO = "Máster en Datos\nModalidad | Online\nPrecio total: 9.800 €\nIdioma: castellano"


class GuardaFalsa:
    activa = True

    def __init__(self, privados):
        self.privados, self.escritos = privados, {}
        from collections import Counter
        self.cuentas = Counter()

    def leer_jsonl(self, clave):
        return self.privados[clave]

    def original(self, fuente, contenido, ext, url):
        self.escritos[url] = contenido
        return {"clave": f"{fuente}/x.{ext}"}

    def jsonl(self, fuente, filas, nombre, url):
        self.escritos[url] = filas
        return f"{fuente}/{nombre}"


def _carpeta(tmp_path):
    c = tmp_path / "retomado_abc"
    c.mkdir()
    (c / "lote.json").write_text(json.dumps({"id": "msgbatch_origen", "clave_enviado": "env"}))
    (c / "resumen.json").write_text(json.dumps({"almacen": {"claves_privadas": {"hechos_con_cita": "hc"}}}))
    p = {"url": "https://x.es/m", "captura_sha256": "s", "extraido": "2026-10-30T03:00:00+00:00", "grupo": "no_oficial"}
    (c / "paginas_extraidas.jsonl").write_text(json.dumps(p) + "\n")
    pub = [{"campo": "nombre", "valor": "Máster en Datos", "estado": "aceptado", "url": p["url"], "extraido": "2026-10-30T03:00:00+00:00"},
           {"campo": "modalidad", "valor": None, "valor_propuesto": "online", "estado": "revision",
            "motivo": "cita_no_literal", "url": p["url"], "extraido": "2026-10-30T03:00:00+00:00"},
           {"campo": "precio_total", "valor": None, "valor_propuesto": 9800, "estado": "revision",
            "motivo": "cita_no_literal", "url": p["url"], "extraido": "2026-10-30T03:00:00+00:00"},
           {"campo": "idioma", "valor": None, "valor_propuesto": "inglés", "estado": "revision",
            "motivo": "cita_no_literal", "url": p["url"], "extraido": "2026-10-30T03:00:00+00:00"}]
    (c / "hechos.jsonl").write_text("".join(json.dumps(h) + "\n" for h in pub))
    privados = {"env": [{"custom_id": "c1", "url": p["url"], "sha256": "s", "texto": TEXTO}],
                "hc": [{**h, "cita": "x y"} for h in pub]}
    return c, GuardaFalsa(privados)


def test_preparar_pide_solo_las_citas_no_literales(tmp_path):
    c, g = _carpeta(tmp_path)
    peticiones, textos, _ = rc.preparar(c, g)
    assert len(peticiones) == 1
    pedido = peticiones[0]["params"]["messages"][0]["content"]
    assert "modalidad: online" in pedido and "precio_total: 9800" in pedido and "nombre" not in pedido.split("TEXTO")[0]
    assert peticiones[0]["params"]["output_config"]["format"]["type"] == "json_schema"


def test_procesar_acepta_solo_lo_que_comprueba_la_extraccion(tmp_path, monkeypatch):
    c, g = _carpeta(tmp_path)
    _, textos, _ = rc.preparar(c, g)
    cid = next(iter(textos))
    respuesta = {"citas": [{"campo": "modalidad", "cita": "Modalidad | Online"},
                           {"campo": "precio_total", "cita": "Precio total: 9.800 €"},
                           {"campo": "idioma", "cita": "Idioma: inglés"}]}  # no está en el texto
    linea = {"custom_id": cid, "result": {"type": "succeeded", "message": {
        "content": [{"type": "text", "text": json.dumps(respuesta)}], "usage": {"input_tokens": 100, "output_tokens": 20}}}}

    class R:
        text = json.dumps(linea) + "\n"
        content = text.encode()

    monkeypatch.setattr(rc.requests, "get", lambda *a, **k: R())
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    from collections import Counter
    res = rc.procesar({"id": "msgbatch_rec", "results_url": "u"}, textos, c, tmp_path / "o", g, Counter())
    assert res["recuperados"] == 2 and res["por_campo"] == {"modalidad": 1, "precio_total": 1}
    hs = {h["campo"]: h for h in map(json.loads, (tmp_path / "o" / "hechos.jsonl").read_text().split("\n")[:-1])}
    assert hs["modalidad"]["estado"] == "aceptado" and hs["modalidad"]["valor"] == "online"
    assert hs["precio_total"]["valor"] == 9800 and hs["precio_total"]["recitado"] == "msgbatch_rec"
    assert hs["idioma"]["estado"] == "revision" and hs["nombre"]["estado"] == "aceptado"
    assert "cita" not in hs["modalidad"] and hs["modalidad"]["cita_sha256"]
    assert len({h["extraido"] for h in hs.values()}) == 1 and hs["nombre"]["extraido"] > "2026-10-30T03:00:00+00:00"
    p = json.loads((tmp_path / "o" / "paginas_extraidas.jsonl").read_text())
    assert p["extraido"] == hs["nombre"]["extraido"] and p["grupo"] == "no_oficial"
    # fichas_masters se queda con la versión recitada de la página
    from motor.estudios.fichas_masters import leer_extracciones
    paginas, hechos = leer_extracciones([c, tmp_path / "o"])
    assert {h["campo"] for h in hechos["https://x.es/m"]} == {"nombre", "modalidad", "precio_total"}
