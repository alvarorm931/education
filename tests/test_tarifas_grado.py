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
