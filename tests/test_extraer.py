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
