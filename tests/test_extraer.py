from motor.estudios import extraer as e

HTML = ("<html><body><h1>Máster en Dirección Financiera</h1><p>Duración: 12 meses. 60 créditos ECTS.</p>"
        "<p>Precio total: 9.800 € con reserva de plaza de 1.100 €.</p>"
        "<table><tr><td>Módulo</td><td>ECTS</td></tr><tr><td>Finanzas corporativas</td><td>6</td></tr></table></body></html>")


def test_texto_incluye_tablas():
    t = e.texto_de_pagina(HTML)
    assert "60 créditos ECTS" in t and "Finanzas corporativas | 6" in t


def test_verificar_acepta_cita_literal_y_rechaza_inventada():
    texto = e.texto_de_pagina(HTML)
    resp = {"creditos_ects": {"valor": 60, "cita": "60 créditos ECTS"},
            "precio_total": {"valor": 9800, "cita": "Precio total: 9.800 €"},
            "plazas": {"valor": 30, "cita": "30 plazas disponibles"},
            "becas": None}
    h = {x["campo"]: x for x in e.verificar(resp, texto)}
    assert h["creditos_ects"]["estado"] == "aceptado" and h["creditos_ects"]["valor"] == 60
    assert h["precio_total"]["estado"] == "aceptado"
    assert h["plazas"]["estado"] == "revision" and h["plazas"]["valor"] is None and h["plazas"]["valor_propuesto"] == 30


def test_peticion_de_lote():
    p = e.peticion("abc", "https://x.es/master", "texto")
    assert p["custom_id"] == "abc" and p["params"]["model"] == e.MODELO
    assert p["params"]["system"][0]["cache_control"] == {"type": "ephemeral"}


def test_texto_web_quita_menus_y_guarda_divs_y_schema():
    html = ('<html><head><title>x</title></head><body><nav><a>Inicio</a><a>Másteres</a></nav>'
            '<div class="precio">Precio: <span>9.800 €</span></div><div>60 ECTS</div>'
            '<form><input name="email"></form><footer>Aviso legal</footer>'
            '<script type="application/ld+json">{"@type":"Course","name":"Máster X","offers":{"@type":"Offer","price":"9800","priceCurrency":"EUR"}}</script>'
            '</body></html>')
    t = e.texto_de_pagina(html)
    assert "Precio: 9.800 €" in t and "60 ECTS" in t
    assert "Inicio" not in t and "Aviso legal" not in t
    assert "Schema.org Offer: price=9800; priceCurrency=EUR" in t


def test_numero_en_cita():
    assert e.numero_en_cita(9800, "Precio total: 9.800 €")
    assert e.numero_en_cita("60", "60 créditos ECTS")
    assert e.numero_en_cita(12.5, "12,50 € por crédito")
    assert not e.numero_en_cita(9900, "Precio total: 9.800 €")
    texto = "Precio total: 9.800 €"
    h = e.verificar({"precio_total": {"valor": 9900, "cita": "Precio total: 9.800 €"}}, texto)[0]
    assert h["estado"] == "revision" and h["motivo"] == "valor_no_en_cita"


def test_coste_por_tramos():
    assert abs(e.coste({"input_tokens": 50_000, "output_tokens": 0}) - 50_000 * 0.05 / 1e6) < 1e-12
    assert abs(e.coste({"input_tokens": 1_000, "output_tokens": 4_000}) - (1_000 * 0.05 + 4_000 * 0.25) / 1e6) < 1e-12
    assert abs(e.coste({"input_tokens": 200_000, "output_tokens": 0}) - 200_000 * 0.25 / 1e6) < 1e-12  # más de 100k


def test_lote_completo_sin_red(tmp_path, monkeypatch):
    import json as js
    pagina = ("<html><body><h1>Máster en Finanzas</h1><p>Precio total: 9.800 €</p><p>60 créditos ECTS</p></body></html>")
    monkeypatch.setattr(e, "capturar", lambda urls, pausa=1.0: [
        {"url": urls[0], "estado_http": 200, "sha256": "abc", "html": pagina, "reserva_tdm": False},
        {"url": "https://y.es/m", "estado_http": 200, "sha256": "def", "html": pagina, "reserva_tdm": True}])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "prueba")
    enviado = {}

    class R:
        def __init__(self, status, datos=None, texto=""):
            self.status_code, self._d, self.text = status, datos, texto

        def json(self):
            return self._d

    def post(url, headers, json, timeout):
        enviado["n"] = len(json["requests"])
        enviado["id"] = json["requests"][0]["custom_id"]
        return R(200, {"id": "msgbatch_1", "processing_status": "in_progress"})

    def get(url, headers, timeout):
        if url.endswith("msgbatch_1"):
            return R(200, {"id": "msgbatch_1", "processing_status": "ended", "results_url": "https://r/1"})
        respuesta = {"precio_total": {"valor": 9800, "cita": "Precio total: 9.800 €"},
                     "creditos_ects": {"valor": 90, "cita": "60 créditos ECTS"}}
        linea = {"custom_id": enviado["id"], "result": {"type": "succeeded", "message": {
            "content": [{"type": "text", "text": js.dumps(respuesta)}], "stop_reason": "end_turn",
            "usage": {"input_tokens": 1000, "output_tokens": 200}}}}
        return R(200, texto=js.dumps(linea))

    monkeypatch.setattr(e.requests, "post", post)
    monkeypatch.setattr(e.requests, "get", get)
    monkeypatch.setattr(e.time, "sleep", lambda s: None)
    (tmp_path / "m.jsonl").write_text(js.dumps({"url": "https://x.es/master", "grupo": "no_oficial"}) + "\n")
    res = e.lote(tmp_path / "m.jsonl", tmp_path / "out")
    assert enviado["n"] == 1 and res["reserva_tdm"] == 1 and res["extraidas"] == 1
    assert res["hechos_aceptados"] == 1 and res["motivos_revision"] == {"valor_no_en_cita": 1}
    assert abs(res["coste_usd"] - (1000 * 0.05 + 200 * 0.25) / 1e6) < 1e-12
    capt = (tmp_path / "out" / "paginas_capturadas.jsonl").read_text()
    assert "<html" not in capt  # la página no se guarda
    hechos = (tmp_path / "out" / "hechos.jsonl").read_text()
    assert "Precio total" not in hechos and "cita_sha256" in hechos  # ni la cita
