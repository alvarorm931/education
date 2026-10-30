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
