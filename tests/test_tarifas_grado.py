import json

from motor.grados import tarifas_grado as tg

G = [{"codigo": "1", "clase": "grado", "nombre": "Psicología", "componentes": []},
     {"codigo": "2", "clase": "grado", "nombre": "Administración y Dirección de Empresas", "componentes": []},
     {"codigo": "3", "clase": "doble", "nombre": "ADE y Derecho",
      "componentes": [{"nombre": "Administración y Dirección de Empresas"}, {"nombre": "Derecho"}]},
     {"codigo": "4", "clase": "grado", "nombre": "Derecho", "componentes": []}]


def test_grado_de_linea():
    assert tg.grado_de("Grado en Psicología 9.990 €", G) == "1"
    assert tg.grado_de("Doble Grado en Derecho + ADE 12.500 €", G) == "3"
    assert tg.grado_de("Grado en Derecho 8.000 €", G) == "4"
    assert tg.grado_de("Máster en Marketing 9.000 €", G) is None


def test_extraer_tipos_por_linea_y_por_rotulo():
    paginas = ["PRECIOS CURSO 2026-2027\nPrecio por curso\nGrado en Psicología 9.990 €\n"
               "Grado en Derecho\n8.400 €\nReserva de plaza: 500 € Grado en Administración y Dirección de Empresas"]
    r = tg.extraer(paginas, G)
    assert r["curso_documento"] == "2026-2027"
    assert r["grados"]["1"][0]["valor"] == 9990 and r["grados"]["1"][0]["tipo"] == "curso"
    assert r["grados"]["4"][0]["valor"] == 8400 and r["grados"]["4"][0]["verosimil"]
    assert r["grados"]["2"][0]["tipo"] == "reserva"


def test_elegir_solo_pdf_de_precios(tmp_path):
    d = tmp_path / "x" / "web_privadas"
    d.mkdir(parents=True)
    (d / "123.json").write_text(json.dumps({"universidad": "U", "codigo": "123", "pdf_precio": [
        "https://u.es/precios-grados-26-27.pdf", "https://u.es/guia-docente/2026/G1.pdf",
        "https://u.es/Informe_Tasas_e_indicadores.pdf"]}))
    assert [p["url"] for p in tg.elegir(tmp_path)] == ["https://u.es/precios-grados-26-27.pdf"]


def test_html_tabla_con_rotulos_de_columna():
    html = ("<table><tr><th>Titulación</th><th>Reserva de plaza</th><th>Precio por curso</th></tr>"
            "<tr><td>Grado en Psicología</td><td>500 €</td><td>9.990 €</td></tr></table>")
    lineas = tg.lineas_html(html)
    assert lineas[1] == "Grado en Psicología | 500 € | 9.990 €"
    r = tg.extraer(["\n".join(lineas)], G)
    assert [(i["valor"], i["tipo"]) for i in r["grados"]["1"]] == [(500, "reserva"), (9990, "curso")]


def test_elegir_cc_une_por_codigo_y_no_repite(tmp_path):
    d = tmp_path / "x" / "cc_precios"
    d.mkdir(parents=True)
    filas = [{"dominio": "u.es", "url": "https://u.es/precios-grados.pdf", "codigo": "123", "universidad": "U"},
             {"dominio": "u.es", "url": "https://u.es/ya.pdf", "codigo": "123", "universidad": "U"},
             {"dominio": "v.es", "url": "https://v.es/precios.pdf"}]
    (d / "urls_CC_0_1.jsonl").write_text("\n".join(json.dumps(x) for x in filas))
    r = tg.elegir_cc(tmp_path, {"https://u.es/ya.pdf"})
    assert [x["url"] for x in r] == ["https://u.es/precios-grados.pdf"] and r[0]["origen"] == "common_crawl"


def test_pagina_de_precios_de_un_solo_grado():
    url = "https://www.u.es/es/grado-psicologia/precios-becas-ayudas"
    assert tg.grado_de_url(url, G) == "1"
    r = tg.extraer(["Precio por crédito: 150 €\nPrecio del curso: 9.000 €"], G, "1")
    assert {i["valor"] for i in r["grados"]["1"]} == {150, 9000}


def test_listas_de_precios_conocidas_sin_repetir():
    from motor.grados.tarifas_grado import elegir_conocidas
    ya = {"https://ya.es/precios"}
    xs = elegir_conocidas(ya, {"999": ["https://ya.es/precios", "https://otra.es/precios"]})
    urls = [x["url"] for x in xs]
    assert "https://otra.es/precios" in urls and "https://ya.es/precios" not in urls
    assert any(x["codigo_universidad"] == "031" for x in xs)


def test_rastreo_de_centro_lleva_sus_grados(tmp_path):
    d = tmp_path / "x" / "web_privadas"
    d.mkdir(parents=True)
    (d / "03908073491.json").write_text(json.dumps({
        "universidad": "UPF · Tecnocampus", "codigo": "03908073491", "centro": "08073491", "centro_adscrito": True,
        "urls_precio": ["https://tecnocampus.cat/es/precios"], "fichas": {"9": {"url": "https://tecnocampus.cat/g9"}}}))
    p = tg.elegir(tmp_path)[0]
    assert p["centro"] == "08073491" and p["centro_adscrito"] is True and p["grados_rastreo"] == ["9"]
    cat = [{"codigo": "5", "clase": "grado", "situacion": "Activo",
            "universidades": [{"nombre": "Pompeu Fabra", "codigo": "039", "tipo": "Pública"}],
            "imparticiones": [{"universidad": "Pompeu Fabra", "unidad_codigo": "08073491", "situacion": "Activo"},
                              {"universidad": "Pompeu Fabra", "unidad_codigo": "08000001", "situacion": "Activo"}]},
           {"codigo": "6", "clase": "grado", "situacion": "Activo",
            "universidades": [{"nombre": "Privada X", "codigo": "123", "tipo": "Privada"}],
            "imparticiones": [{"universidad": "Privada X", "unidad_codigo": "08111111", "situacion": "Activo"}]}]
    por = tg.grados_por_codigo(cat)
    assert [t["codigo"] for t in por["03908073491"]] == ["5"]
    assert [t["codigo"] for t in por["03908000001"]] == ["5"]
    assert [t["codigo"] for t in por["123"]] == ["6"] and "039" not in por  # pública: solo por centro


def test_ejecutar_con_lista_conocida_sin_universidad(tmp_path, monkeypatch):
    """Una URL de la lista conocida no trae nombre de universidad: el resumen no puede romperse por eso."""
    import motor.estudios.rastreador as rastreador
    from motor.grados import tarifas_grado as tg

    class R:
        status_code = 200
        headers = {"content-type": "text/html"}
        text = "<html><body><p>Precio del grado: 9.000 euros</p></body></html>"
        content = text.encode()

    class D:
        def __init__(self, *a, **k):
            pass

        def get(self, url, guardar=False):
            return R()

    monkeypatch.setattr(rastreador, "Dominio", D)
    monkeypatch.setattr(tg, "URLS_CONOCIDAS", {"031": ["https://www.unav.edu/precios"]})
    (tmp_path / "r").mkdir()
    res = tg.ejecutar([], tmp_path / "r", tmp_path / "s", max_minutos=1)
    assert res["por_origen"]["lista_conocida"] == 1
    assert "031" in res["por_universidad"]


def test_no_se_repiten_las_direcciones_ya_pedidas(tmp_path, monkeypatch):
    import motor.estudios.rastreador as rastreador
    from motor.grados import tarifas_grado as tg

    pedidas = []

    class D:
        def __init__(self, *a, **k):
            pass

        def get(self, url, guardar=False):
            pedidas.append(url)
            return None

    monkeypatch.setattr(rastreador, "Dominio", D)
    monkeypatch.setattr(tg, "URLS_CONOCIDAS", {"031": ["https://a.es/1", "https://a.es/2", "https://a.es/3"]})
    prev = tmp_path / "p" / "datos" / "estudios" / "grados" / "tarifas_grado"
    prev.mkdir(parents=True)
    (prev / "tarifas.jsonl").write_text(
        json.dumps({"url": "https://a.es/1", "estado": 200}) + "\n" + json.dumps({"url": "https://a.es/2", "estado": None})
        + "\n", encoding="utf-8")
    (tmp_path / "r").mkdir()
    tg.ejecutar([], tmp_path / "r", tmp_path / "s", max_minutos=1, previas=tmp_path / "p")
    assert pedidas == ["https://a.es/2", "https://a.es/3"]


def test_tabla_con_importes_sin_simbolo_de_euro():
    paginas = ["Importes en euros\nGRADO | CRÉDITOS | MATRÍCULA | 8 PLAZOS ENSEÑANZA | TOTAL\n"
               "Psicología | 60 | 1.278,00 | 639,00 | 6.390,00"]
    r = tg.extraer(paginas, G, None)
    assert sorted(i["valor"] for i in r["grados"]["1"]) == [639.0, 1278.0, 6390.0]
    # sin la palabra «euros» en la página, las cifras sueltas no se toman por importes
    assert not tg.extraer([paginas[0].replace("Importes en euros\n", "")], G, None)["grados"]


def test_celdas_con_parrafos_no_parten_la_fila():
    assert tg.lineas_html("<table><tr><td><p>Psicología</p></td><td><p>1.278,00</p></td></tr></table><p>Otra</p>") \
        == ["Psicología | 1.278,00", "Otra"]


def test_motivo_cuando_no_hay_respuesta(tmp_path):
    """Sin respuesta se dice por qué: robots.txt que lo prohíbe, que no responde, límite o error de conexión."""
    from collections import Counter
    from urllib.robotparser import RobotFileParser

    from motor.grados import tarifas_grado as tg

    class D:
        def __init__(self, reglas, error=None, peticiones=0):
            self.peticiones, self.max_peticiones, self.estados, self.error = peticiones, 40, Counter(), error
            rp = RobotFileParser()
            if reglas is None:
                rp.disallow_all = True
            else:
                rp.parse(reglas)
            self.robots = {"https://a.es": rp}

        def robots_ok_para(self, url):
            return self.robots["https://a.es"].can_fetch("motor", url)

        def get(self, url, guardar=False):
            self.estados[self.error] += 1
            return None

    assert tg.pedir_con_motivo(D(["User-agent: *", "Disallow: /Portals/"]), "https://a.es/Portals/0/t.pdf") \
        == (None, "robots_txt_lo_prohibe")
    assert tg.pedir_con_motivo(D(None), "https://a.es/t.pdf") == (None, "robots_txt_no_responde")
    assert tg.pedir_con_motivo(D([], peticiones=40), "https://a.es/t.pdf") == (None, "limite_de_peticiones_al_servidor")
    assert tg.pedir_con_motivo(D([], error="ReadTimeout"), "https://a.es/t.pdf") == (None, "ReadTimeout")


def test_solo_algunas_universidades(tmp_path, monkeypatch):
    import motor.estudios.rastreador as rastreador
    from motor.grados import tarifas_grado as tg

    pedidas = []

    class D:
        def __init__(self, *a, **k):
            pass

        def get(self, url, guardar=False):
            pedidas.append(url)
            return None

    monkeypatch.setattr(rastreador, "Dominio", D)
    monkeypatch.setattr(tg, "URLS_CONOCIDAS", {"031": ["https://a.es/1"], "072": ["https://b.es/1"]})
    (tmp_path / "r").mkdir()
    res = tg.ejecutar([], tmp_path / "r", tmp_path / "s", max_minutos=1, solo={"072"})
    assert pedidas == ["https://b.es/1"] and res["pdfs_elegidos"] == 1
    assert json.loads((tmp_path / "s/datos/estudios/grados/tarifas_grado/tarifas.jsonl").read_text())["motivo"] \
        == "sin_respuesta"
