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
    assert p["params"]["thinking"] == {"type": "disabled"} and p["params"]["output_config"] == {"effort": "low"}


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
    monkeypatch.setattr(e, "capturar", lambda urls, **kw: [
        {"url": urls[0], "estado_http": 200, "sha256": "abc", "html": pagina, "reserva_tdm": False},
        {"url": "https://y.es/m", "estado_http": 200, "sha256": "def", "html": pagina, "reserva_tdm": True}])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "prueba")
    monkeypatch.setattr(e, "MIN_CARACTERES", 10)  # páginas de prueba cortas
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
    res = e.lote(tmp_path / "m.jsonl", tmp_path / "out", guarda=e.Guarda(None))
    assert enviado["n"] == 1 and res["reserva_tdm"] == 1 and res["extraidas"] == 1
    assert res["hechos_aceptados"] == 1 and res["motivos_revision"] == {"valor_no_en_cita": 1}
    assert abs(res["coste_usd"] - (1000 * 0.05 + 200 * 0.25) / 1e6) < 1e-12
    capt = (tmp_path / "out" / "paginas_capturadas.jsonl").read_text()
    assert "<html" not in capt  # la página no se guarda
    hechos = (tmp_path / "out" / "hechos.jsonl").read_text()
    assert "Precio total" not in hechos and "cita_sha256" in hechos  # ni la cita


def test_verificar_formato_compacto():
    h = e.verificar({"creditos_ects": {"v": 60, "c": "60 créditos ECTS"}}, "Son 60 créditos ECTS en total")[0]
    assert h["estado"] == "aceptado" and h["valor"] == 60


class AlmacenFalso:
    """Como motor.almacen.Almacen: claves con la huella del contenido y escritura única."""

    def __init__(self):
        self.objetos = {}

    def guardar_original(self, fuente, fecha_ref, contenido, ext, url, comprimir=True):
        import hashlib
        from motor.almacen import Resultado, clave_original

        sha = hashlib.sha256(contenido).hexdigest()
        clave = clave_original(fuente, fecha_ref, sha, ext, comprimir)
        nuevo = clave not in self.objetos
        self.objetos.setdefault(clave, contenido)
        return Resultado(clave=clave, nuevo=nuevo, sha256=sha, bytes=len(contenido))

    def leer(self, clave):
        return self.objetos[clave]


def _api_simulada(monkeypatch, estados, enviado):
    """Lote que sigue «in_progress» las primeras consultas y luego termina con una respuesta con cita."""
    import json as js

    class R:
        def __init__(self, status, datos=None, texto=""):
            self.status_code, self._d, self.text = status, datos, texto
            self.content = texto.encode()

        def json(self):
            return self._d

    def post(url, headers, json, timeout):
        enviado["id"] = json["requests"][0]["custom_id"]
        return R(200, {"id": "msgbatch_2", "processing_status": "in_progress"})

    def get(url, headers, timeout):
        if url.endswith("msgbatch_2"):
            return R(200, {"id": "msgbatch_2", "processing_status": estados.pop(0) if estados else "ended",
                           "results_url": "https://r/2"})
        respuesta = {"precio_total": {"v": 9800, "c": "Precio total: 9.800 €"}}
        linea = {"custom_id": enviado["id"], "result": {"type": "succeeded", "message": {
            "content": [{"type": "text", "text": js.dumps(respuesta)}], "stop_reason": "end_turn",
            "usage": {"input_tokens": 1000, "output_tokens": 100}}}}
        return R(200, texto=js.dumps(linea))

    monkeypatch.setenv("ANTHROPIC_API_KEY", "prueba")
    monkeypatch.setattr(e.requests, "post", post)
    monkeypatch.setattr(e.requests, "get", get)
    monkeypatch.setattr(e.time, "sleep", lambda s: None)


def test_lote_guarda_lo_ajeno_solo_en_el_almacen_y_se_puede_retomar(tmp_path, monkeypatch):
    import json as js

    pagina = "<html><body><h1>Máster en Finanzas</h1><p>Precio total: 9.800 €</p></body></html>"
    almacen = AlmacenFalso()

    def capturar(urls, guarda=None, **kw):
        fila = {"url": urls[0], "estado_http": 200, "sha256": "abc", "reserva_tdm": False,
                "texto": e.texto_de_pagina(pagina)}
        fila.update(guarda.original(e.FUENTE_PAGINAS, pagina.encode(), "html", urls[0]))
        return [fila]

    monkeypatch.setattr(e, "capturar", capturar)
    monkeypatch.setattr(e, "MIN_CARACTERES", 10)
    enviado = {}
    _api_simulada(monkeypatch, ["in_progress"] * 1000, enviado)  # no termina en esta ejecución
    (tmp_path / "m.jsonl").write_text(js.dumps({"url": "https://x.es/master", "codigos_ruct": ["4310000"]}) + "\n")
    res = e.lote(tmp_path / "m.jsonl", tmp_path / "a", esperar_min=0, guarda=e.Guarda(almacen))
    assert res["estado_lote"] == "in_progress"
    info = js.loads((tmp_path / "a" / "lote.json").read_text())
    assert info["clave_enviado"].startswith("extraccion-masters/")
    assert any(k.startswith("web-centros/") for k in almacen.objetos)  # el original de la página, privado
    publico = "".join(f.read_text() for f in (tmp_path / "a").iterdir())
    assert "Precio total" not in publico and "<html" not in publico

    # otra ejecución recoge el lote con el texto exacto enviado, sin volver a pedir la página
    _api_simulada(monkeypatch, [], enviado)
    res2 = e.retomar(tmp_path / "a" / "lote.json", tmp_path / "b", guarda=e.Guarda(almacen))
    assert res2["hechos_aceptados"] == 1 and res2["almacen"]["claves_privadas"]["hechos_con_cita"]
    privados = almacen.leer(res2["almacen"]["claves_privadas"]["hechos_con_cita"]).decode()
    assert "Precio total: 9.800" in privados  # la cita, solo en el almacén
    hechos = (tmp_path / "b" / "hechos.jsonl").read_text()
    assert "Precio total" not in hechos and "4310000" in (tmp_path / "b" / "paginas_extraidas.jsonl").read_text()


def test_guarda_no_insiste_tras_cinco_fallos():
    class Roto:
        def guardar_original(self, *a, **k):
            raise RuntimeError("sin permiso")

    g = e.Guarda(Roto())
    for _ in range(6):
        r = g.original("web-centros", b"x", "html", "https://x.es")
        assert "fallo_almacen" in r or r == {}
    assert not g.activa and g.cuentas["fallos"] == 5


def test_lista_oficiales_une_codigos_por_url(tmp_path):
    import json as js

    filas = [{"codigo_ruct": "1", "estado": "unido", "url": "https://u.es/m", "subpaginas": ["https://u.es/m/precios"]},
             {"codigo_ruct": "2", "estado": "dudoso", "url": "https://u.es/m"},
             {"codigo_ruct": "3", "estado": "dudoso", "url": "https://v.es/m"},
             {"codigo_ruct": "4", "estado": "sin_pagina", "url": None}]
    (tmp_path / "p.jsonl").write_text("".join(js.dumps(f) + "\n" for f in filas))
    r = e.lista_oficiales(tmp_path / "p.jsonl", tmp_path / "m.jsonl")
    assert r["urls"] == 3 and r["urls_unido"] == 2 and r["urls_con_varios_codigos"] == 1 and r["subpaginas"] == 1
    m = [js.loads(l) for l in (tmp_path / "m.jsonl").read_text().splitlines()]
    assert m[0]["codigos_ruct"] == ["1", "2"] and m[0]["estado_emparejado"] == "unido" and m[0]["pagina"] == "principal"
    assert m[1]["url"] == "https://u.es/m/precios" and m[1]["principal"] == "https://u.es/m"


def test_capturar_guarda_original_salvo_reserva_tdm(monkeypatch):
    from motor.estudios import rastreador

    class Resp:
        def __init__(self, url, html, cab=None):
            self.url, self.status_code, self.content = url, 200, html.encode()
            self.headers = {"content-type": "text/html", **(cab or {})}
            self.encoding, self.apparent_encoding, self.text = "utf-8", "utf-8", html

    class DominioFalso:
        def __init__(self, base, archivo, pausa=1.0, max_peticiones=80):
            self.base = base

        def get(self, url):
            if "reservada" in url:
                return Resp(url, "<html><body>x</body></html>", {"tdm-reservation": "1"})
            if "nada" in url:
                return None
            return Resp(url, "<html><body><p>Precio total: 9.800 €</p></body></html>")

    monkeypatch.setattr(rastreador, "Dominio", DominioFalso)
    almacen = AlmacenFalso()
    filas = e.capturar(["https://a.es/m1", "https://a.es/m2", "https://b.es/reservada", "https://c.es/nada"],
                       hilos=3, guarda=e.Guarda(almacen))
    por = {f["url"]: f for f in filas}
    assert len(filas) == 4 and "Precio total: 9.800 €" in por["https://a.es/m1"]["texto"]
    assert por["https://a.es/m1"]["clave"].startswith("web-centros/")
    assert por["https://b.es/reservada"]["reserva_tdm"] and "clave" not in por["https://b.es/reservada"]
    assert "texto" not in por["https://b.es/reservada"]
    assert por["https://c.es/nada"]["motivo"] == "sin_respuesta"  # el falso no tiene robots: no respondió
    assert len(almacen.objetos) == 1  # m1 y m2 tienen el mismo contenido: una sola clave, sin sobrescribir


def test_pagina_sin_texto_no_se_envia(tmp_path, monkeypatch):
    import json as js
    monkeypatch.setattr(e, "capturar", lambda urls, **kw: [
        {"url": urls[0], "estado_http": 200, "sha256": "a", "reserva_tdm": False, "texto": "Cargando…"}])
    llamadas = []
    monkeypatch.setattr(e.requests, "post", lambda *a, **k: llamadas.append(1))
    (tmp_path / "m.jsonl").write_text(js.dumps({"url": "https://x.es/m"}) + "\n")
    res = e.lote(tmp_path / "m.jsonl", tmp_path / "o", guarda=e.Guarda(None))
    assert res["sin_texto_suficiente"] == 1 and not llamadas


def test_propios_de_oficiales_sin_los_ya_unidos_ni_noticias(tmp_path):
    import json as js
    censo = [{"id": "prov-g", "dominio": "garrigues.es", "estado": "oficial"}]
    (tmp_path / "censo.jsonl").write_text(js.dumps(censo[0]) + "\n")
    rastreo = {"centro": {"id": "prov-g"}, "programas": [
        "https://www.garrigues.es/",
        "https://www.garrigues.es/masters-oficiales/recursos-humanos/",
        "https://www.garrigues.es/masters-oficiales/recursos-humanos/plan-de-estudios",
        "https://www.garrigues.es/masters-executive/recursos-humanos/?utm_source=x",
        "https://www.garrigues.es/noticias/premio-al-mejor-master/",
        "https://www.garrigues.es/master-universitario-en-tributacion/"]}
    d = tmp_path / "r" / "datos" / "estudios" / "oferta_web"
    d.mkdir(parents=True)
    (d / "garrigues.es.json").write_text(js.dumps(rastreo))
    # un oficial quedó unido a la portada: no por eso se excluye todo el sitio
    unidos = [{"codigo_ruct": "1", "estado": "unido", "url": "https://www.garrigues.es/masters-oficiales/recursos-humanos/"},
              {"codigo_ruct": "2", "estado": "dudoso", "url": "https://www.garrigues.es/"}]
    (tmp_path / "po.jsonl").write_text("".join(js.dumps(x) + "\n" for x in unidos))
    r = e.lista_propios_de_oficiales(tmp_path / "censo.jsonl", [tmp_path / "r"], tmp_path / "po.jsonl", tmp_path / "o",
                                     tramos=1)
    urls = [js.loads(l)["url"] for l in (tmp_path / "o" / "propios_oficiales_0.jsonl").read_text().splitlines()]
    assert urls == ["https://www.garrigues.es/masters-executive/recursos-humanos/"]
    assert r["ya_unidas_a_un_oficial"] == 2 and r["descartadas_por_url"] == 1


def test_segunda_vuelta_solo_masters_sin_ficha_y_urls_nuevas(tmp_path):
    import json as js
    po = [{"codigo_ruct": "1", "estado": "unido", "url": "https://u.es/a", "alternativas": [{"url": "https://u.es/a2", "puntuacion": 0.8}]},
          {"codigo_ruct": "2", "estado": "unido", "url": "https://u.es/b",
           "alternativas": [{"url": "https://u.es/b", "puntuacion": 0.9}, {"url": "https://u.es/b2", "puntuacion": 0.6},
                            {"url": "https://u.es/b3", "puntuacion": 0.3}]},
          {"codigo_ruct": "3", "estado": "sin_pagina", "url": None, "puntuacion": 0.6, "candidata": "https://u.es/c",
           "alternativas": []}]
    (tmp_path / "po.jsonl").write_text("".join(js.dumps(x) + "\n" for x in po))
    fichas = [{"codigo_ruct": "1", "comprobacion_nombre": "confirmado"}, {"codigo_ruct": "2", "comprobacion_nombre": "no_es_ficha"}]
    (tmp_path / "f.jsonl").write_text("".join(js.dumps(x) + "\n" for x in fichas))
    (tmp_path / "c.jsonl").write_text(js.dumps({"url": "https://u.es/b"}) + "\n")
    r = e.lista_segunda_vuelta(tmp_path / "po.jsonl", tmp_path / "f.jsonl", [tmp_path / "c.jsonl"], tmp_path / "s.jsonl")
    urls = [js.loads(l)["url"] for l in (tmp_path / "s.jsonl").read_text().splitlines()]
    assert urls == ["https://u.es/b2", "https://u.es/c"] and r["con_candidatas"] == 2


def test_valores_numericos():
    assert e.como_numero("9.800 €") == 9800 and e.como_numero("12,50") == 12.5 and e.como_numero(60) == 60
    assert e.como_numero("no indicado") is None and e.como_numero("30-40") is None and e.como_numero([1]) is None
    h = e.verificar({"precio_total": {"v": "no indicado", "c": "Precio total: 9.800 €"}}, "Precio total: 9.800 €")[0]
    assert h["estado"] == "revision" and h["motivo"] == "valor_no_numerico"
    h = e.verificar({"precio_total": {"v": "9.800 €", "c": "Precio total: 9.800 €"}}, "Precio total: 9.800 €")[0]
    assert h["estado"] == "aceptado" and h["valor"] == 9800


def test_precio_en_otra_moneda_o_version_de_otro_pais():
    h = e.verificar({"precio_total": {"v": 13307700, "c": "Precio: $13.307.700 COP"}}, "Precio: $13.307.700 COP")[0]
    assert h["estado"] == "revision" and h["motivo"] == "moneda_no_euro_o_fuera_de_rango"
    assert e._no_es_ficha_por_url("https://www.medicapanamericana.com/es-CO/formacion/master-en-urologia")
    assert not e._no_es_ficha_por_url("https://www.medicapanamericana.com/es/formacion/master-en-urologia")


def test_pagina_sin_cambios_no_se_vuelve_a_enviar(tmp_path, monkeypatch):
    import json as js
    monkeypatch.setattr(e, "capturar", lambda urls, **kw: [
        {"url": urls[0], "estado_http": 200, "sha256": "igual", "reserva_tdm": False, "texto": "x" * 500}])
    llamadas = []
    monkeypatch.setattr(e.requests, "post", lambda *a, **k: llamadas.append(1))
    (tmp_path / "m.jsonl").write_text(js.dumps({"url": "https://x.es/m"}) + "\n")
    prev = tmp_path / "prev"
    prev.mkdir()
    (prev / "paginas_extraidas.jsonl").write_text(js.dumps({"url": "https://x.es/m", "captura_sha256": "igual",
                                                            "extraido": "2026-10-30T00:00:00+00:00"}) + "\n"
                                                  + js.dumps({"url": "https://x.es/roto", "captura_sha256": "igual",
                                                              "extraido": "2026-10-30T00:00:00+00:00", "json_legible": False}) + "\n")
    previas = e.huellas_previas([prev])
    assert "https://x.es/roto" not in previas  # respuesta ilegible: se vuelve a enviar
    res = e.lote(tmp_path / "m.jsonl", tmp_path / "o", guarda=e.Guarda(None), previas=previas)
    assert res["sin_cambios"] == 1 and not llamadas
    # la misma página, ahora pedida para un máster oficial: no se salta
    (tmp_path / "m2.jsonl").write_text(js.dumps({"url": "https://x.es/m", "grupo": "oficial", "codigos_ruct": ["9"]}) + "\n")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "prueba")
    monkeypatch.setattr(e.requests, "post", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("enviado")))
    import pytest
    with pytest.raises(RuntimeError):
        e.lote(tmp_path / "m2.jsonl", tmp_path / "o2", guarda=e.Guarda(None), previas=previas)


def test_numeros_y_citas_sin_dobles_lecturas():
    assert e.como_numero("1500,50") == 1500.5 and e.como_numero("9800,00 €") == 9800.0 and e.como_numero("12345.6") == 12345.6
    assert not e.numero_en_cita(4550, "45,50 €") and e.numero_en_cita(45.5, "45,50 €")
    assert not e.numero_en_cita(9.8, "9.800 €") and e.numero_en_cita(60, "Curso 2026/2027 60 ECTS")
    assert not e.cita_en_texto("1.500 € (pago único)", e._norma("Total 11.500 € (pago único)"))
    assert e.cita_en_texto("1.500 € (pago único)", e._norma("Total 1.500 € (pago único)"))


def test_nivel_de_cita_sin_signos_y_fragmentos():
    base = e._norma("Precio: 1.500,50 €\nIdioma | Español\nModalidad\nOnline\n¿Prácticas? No. Incluye TFM.\n"
                    "El máster tiene un enfoque práctico con casos reales. Además se imparten clases magistrales "
                    "por profesionales del sector.")
    assert e.nivel_cita("1.500,50 €", base) == "literal"
    assert e.nivel_cita("Idioma: Español", base) == "sin_signos"            # separador de tabla
    assert e.nivel_cita("Modalidad: Online", base) == "sin_signos"           # etiqueta y valor en dos líneas
    assert e.nivel_cita("El master tiene un enfoque practico", base) == "sin_signos"  # sin tildes
    assert e.nivel_cita("enfoque práctico con casos reales... clases magistrales por profesionales del sector",
                        base) == "fragmentos"
    # lo que cambia el sentido o el número no pasa
    assert e.nivel_cita("No incluye TFM", base) is None                      # «No. Incluye» no es «No incluye»
    assert e.nivel_cita("Precio: 1.500", base) is None                       # 1.500 no está en 1.500,50
    assert e.nivel_cita("casos reales... clases", base) is None              # trozos de menos de cuatro palabras
    assert e.nivel_cita("Idioma: Inglés", base) is None


def test_fragmentos_demasiado_separados_no_valen():
    base = e._norma("Primera parte del texto con datos. " + "relleno " * 80 + "segunda parte con otros datos.")
    assert e.nivel_cita("Primera parte del texto con... segunda parte con otros datos", base) is None


def test_cita_literal_no_vale_dentro_de_un_decimal():
    base = e._norma("Precio: 1.500,50 € y 2.000.000 de visitas")
    assert not e.cita_en_texto("Precio: 1.500", base) and not e.cita_en_texto("2.000", base)


def test_verificar_anota_el_nivel_de_cita():
    h = {x["campo"]: x for x in e.verificar({"idioma": {"valor": "español", "cita": "Idioma: Español"}},
                                            "Idioma | Español")}
    assert h["idioma"]["estado"] == "aceptado" and h["idioma"]["cita_nivel"] == "sin_signos"


def test_capturar_con_navegador_pinta_lo_que_solo_sale_con_javascript_y_no_pasa_antibots(monkeypatch):
    from motor.estudios import rastreador

    class Resp:
        def __init__(self, url, html):
            self.url, self.status_code, self.content = url, 200, html.encode()
            self.headers = {"content-type": "text/html"}
            self.encoding, self.apparent_encoding, self.text = "utf-8", "utf-8", html

    estaticas = {
        "https://a.es/spa": '<html><body><div id="app"></div><script src="/app.js"></script></body></html>',
        "https://a.es/llena": "<html><body><p>" + "Precio total: 9.800 €. " * 20 + "</p></body></html>",
        "https://b.es/reto": '<html><head><title>Just a moment...</title></head><body><script src="/cdn-cgi/challenge-platform/x.js"></script></body></html>',
    }

    class DominioFalso:
        def __init__(self, base, archivo, pausa=1.0, max_peticiones=80):
            pass

        def get(self, url):
            return Resp(url, estaticas[url])

    pintadas = []

    class NavegadorFalso:
        def __init__(self):
            self.bloqueadas = 0

        def html(self, url):
            pintadas.append(url)
            return "<html><body><h1>Máster en Datos</h1><p>" + "Plan de estudios con 60 ECTS. " * 10 + "</p></body></html>"

        def cerrar(self):
            pass

    monkeypatch.setattr(rastreador, "Dominio", DominioFalso)
    monkeypatch.setattr(e, "Navegador", NavegadorFalso)
    monkeypatch.setattr(e, "PAUSA_RENDER", 0)
    almacen = AlmacenFalso()
    filas = {f["url"]: f for f in e.capturar(list(estaticas), hilos=2, guarda=e.Guarda(almacen), navegador=True)}
    assert pintadas == ["https://a.es/spa"]  # ni la que ya tiene texto ni la verificación antibot
    spa = filas["https://a.es/spa"]
    assert spa["pintada"] and "Máster en Datos" in spa["texto"] and spa["clave_pintada"].startswith("web-centros-render/")
    assert spa["clave"].startswith("web-centros/")  # el original estático también se guarda
    assert filas["https://b.es/reto"].get("antibot") and not filas["https://b.es/reto"].get("pintada")
    assert not filas["https://a.es/llena"].get("pintada")


def test_sin_navegador_no_se_pinta(monkeypatch):
    from motor.estudios import rastreador

    class Resp:
        url, status_code, content = "https://a.es/spa", 200, b"<html><body><div id=app></div></body></html>"
        headers = {"content-type": "text/html"}
        encoding = apparent_encoding = "utf-8"
        text = "<html><body><div id=app></div></body></html>"

    class DominioFalso:
        def __init__(self, *a, **k):
            pass

        def get(self, url):
            return Resp()

    monkeypatch.setattr(rastreador, "Dominio", DominioFalso)
    monkeypatch.setattr(e, "Navegador", lambda: (_ for _ in ()).throw(AssertionError("no debe abrir navegador")))
    assert not e.capturar(["https://a.es/spa"], guarda=e.Guarda(None))[0].get("pintada")


def test_lista_qedu_solo_oficiales_sin_ficha_y_enlaces_nuevos(tmp_path):
    import json as js
    q = tmp_path / "q"
    q.mkdir()
    filas = [{"codTitula": "1", "detalle": {"enlace": "https://u.es/m1?utm_source=qedu"}},
             {"codTitula": "2", "detalle": {"enlace": "https://u.es/m2"}},          # ya tiene ficha
             {"codTitula": "3", "detalle": {"enlace": "https://u.es/m3"}},          # ya capturado
             {"codTitula": "4", "detalle": {"enlace": ""}},
             {"codTitula": "5", "detalle": {"enlace": "https://u.es/m1"}}]          # misma web, dos títulos
    (q / "qedu_detalles_master_0_10.jsonl").write_text("".join(js.dumps(f) + "\n" for f in filas))
    (tmp_path / "fichas.jsonl").write_text(js.dumps({"grupo": "oficial", "codigo_ruct": "2",
                                                     "comprobacion_nombre": "confirmado"}) + "\n")
    c = tmp_path / "c"
    c.mkdir()
    (c / "paginas_capturadas.jsonl").write_text(js.dumps({"url": "https://u.es/m3", "estado_http": 200,
                                                          "caracteres_texto": 5000}) + "\n")
    res = e.lista_qedu([q], tmp_path / "fichas.jsonl", [c], tmp_path / "o")
    out = [js.loads(x) for x in (tmp_path / "o" / "oficiales_qedu.jsonl").read_text().split("\n") if x]
    assert out == [{"url": "https://u.es/m1", "grupo": "oficial", "estado_emparejado": "qedu", "pagina": "principal",
                    "codigos_ruct": ["1", "5"], "codigo_ruct": "1"}]
    assert res["ya_con_ficha"] == 1 and res["enlace_ya_capturado"] == 1 and res["sin_enlace"] == 1


def test_por_que_no_distingue_robots_de_sin_respuesta():
    from urllib.robotparser import RobotFileParser

    class D:
        robots = {}

    d = D()
    assert e._por_que_no(d, "https://a.es/m") == "sin_respuesta"
    rp = RobotFileParser()
    rp.parse(["User-agent: *", "Disallow: /privado/"])
    d.robots["https://a.es"] = rp
    assert e._por_que_no(d, "https://a.es/privado/m") == "robots_prohibe"
    rp2 = RobotFileParser()
    rp2.disallow_all = True
    d.robots["https://a.es"] = rp2
    assert e._por_que_no(d, "https://a.es/m") == "robots_ilegible"


def test_lista_qedu_vuelve_a_etiquetar_la_pagina_ya_extraida(tmp_path):
    import json as js
    q = tmp_path / "q"
    q.mkdir()
    (q / "qedu_detalles_master_0_1.jsonl").write_text(js.dumps({"codTitula": "7", "detalle": {"enlace": "https://u.es/m7"}}) + "\n")
    (tmp_path / "fichas.jsonl").write_text("")
    c = tmp_path / "c"
    c.mkdir()
    (c / "paginas_capturadas.jsonl").write_text(js.dumps({"url": "https://u.es/m7", "estado_http": 200,
                                                          "caracteres_texto": 900}) + "\n")
    (c / "paginas_extraidas.jsonl").write_text(js.dumps({"url": "https://u.es/m7", "extraido": "2026-10-30T02:00:00+00:00",
                                                          "grupo": "no_oficial", "proveedor": "p"}) + "\n")
    res = e.lista_qedu([q], tmp_path / "fichas.jsonl", [c], tmp_path / "o")
    x = js.loads((tmp_path / "o" / "asignadas_por_qedu" / "paginas_extraidas.jsonl").read_text())
    assert res["paginas_asignadas_por_qedu"] == 1 and x["grupo"] == "oficial" and x["codigos_ruct"] == ["7"]
    assert x["extraido"] == "2026-10-30T02:00:00+00:00"  # misma fecha: sus hechos siguen valiendo


def test_simbolos_que_cambian_el_sentido_cuentan():
    base = e._norma("Nota media < 7 para acceder. Descuento del 500 % no aplicable.")
    assert e.nivel_cita("Nota media > 7 para acceder", base) is None
    assert e.nivel_cita("Descuento del 500 € no aplicable", base) is None


def test_fragmentos_no_se_saltan_una_negacion():
    base = e._norma("El título es un máster oficial que no habilita para el ejercicio de la profesión de abogado.")
    assert e.nivel_cita("El título es un máster oficial... habilita para el ejercicio de la profesión", base) is None


def test_numero_de_otra_celda_de_la_tabla():
    texto = "Precio del crédito | Precio total\n45 € | 2.700 €"
    h = {x["campo"]: x for x in e.verificar({"precio_total": {"valor": 45, "cita": "Precio total 45 €"}}, texto)}
    assert h["precio_total"]["estado"] == "revision" and h["precio_total"]["motivo"] in ("numero_de_otra_celda", "precio_total_demasiado_bajo")
    texto2 = "Concepto | Importe\nPrecio total | 2.700 €"
    h2 = {x["campo"]: x for x in e.verificar({"precio_total": {"valor": 2700, "cita": "Precio total | 2.700 €"}}, texto2)}
    assert h2["precio_total"]["estado"] == "aceptado"
    texto3 = "Precio del crédito | 45 €\nPrecio total | 2.700 €"
    h3 = {x["campo"]: x for x in e.verificar({"precio_credito": {"valor": 45, "cita": "Precio del crédito 45 €"}}, texto3)}
    assert h3["precio_credito"]["estado"] == "aceptado"
    texto4 = "Créditos | Precio\n60 | 2.700 €"
    h4 = {x["campo"]: x for x in e.verificar({"creditos_ects": {"valor": 60, "cita": "Precio 60"}}, texto4)}
    assert h4["creditos_ects"]["estado"] == "revision"


def test_precio_total_minimo():
    h = {x["campo"]: x for x in e.verificar({"precio_total": {"valor": 0, "cita": "Precio: 0 € sesión informativa"}},
                                            "Precio: 0 € sesión informativa")}
    assert h["precio_total"]["motivo"] == "precio_total_demasiado_bajo"


def test_valor_tiene_que_salir_de_la_cita_en_campos_cortos():
    texto = "Modalidad: 100 % en línea. Se imparte en castellano. Sede: Madrid."
    resp = {"modalidad": {"valor": "online", "cita": "Modalidad: 100 % en línea"},
            "idioma": {"valor": "español", "cita": "Se imparte en castellano"},
            "sedes": {"valor": "Barcelona", "cita": "Sede: Madrid"}}
    h = {x["campo"]: x for x in e.verificar(resp, texto)}
    assert h["modalidad"]["estado"] == "aceptado" and h["idioma"]["estado"] == "aceptado"
    assert h["sedes"]["estado"] == "revision" and h["sedes"]["motivo"] == "valor_no_en_cita"


def test_tipo_de_titulo_y_varias_modalidades_son_categorias():
    texto = "Máster en Finanzas. Clases presenciales y online. Máster Universitario en Datos."
    resp = {"tipo_titulo": {"valor": "otro", "cita": "Máster en Finanzas"},
            "modalidad": {"valor": "varias", "cita": "Clases presenciales y online"}}
    h = {x["campo"]: x for x in e.verificar(resp, texto)}
    assert h["tipo_titulo"]["estado"] == "aceptado" and h["modalidad"]["estado"] == "aceptado"
    # que sea oficial sí tiene que decirlo la cita
    h = e.verificar({"tipo_titulo": {"valor": "máster universitario oficial", "cita": "Máster en Finanzas"}}, texto)[0]
    assert h["motivo"] == "valor_no_en_cita"
    h = e.verificar({"tipo_titulo": {"valor": "máster universitario oficial", "cita": "Máster Universitario en Datos"}}, texto)[0]
    assert h["estado"] == "aceptado"
