import json

from motor.estudios import extraer as e
from motor.estudios import tarifas as t

TEXTO = ("Tarifas curso 2026-2027. Máster Universitario en Psicología General Sanitaria: 9.420 € "
         "Reserva de plaza 1.100 € Máster Universitario en Abogacía 8.494 €")


def test_verificar_precios_con_cita_y_numero():
    datos = {"es_tarifa": True, "curso": "2026-2027", "precios": [
        {"programa": "Máster Universitario en Psicología General Sanitaria", "importe": "9.420",
         "concepto": "total", "cita": "Psicología General Sanitaria: 9.420 €"},
        {"programa": "Máster Universitario en Abogacía", "importe": "8.500", "concepto": "total",
         "cita": "Máster Universitario en Abogacía 8.494 €"},
        {"programa": "Otro", "importe": "consultar", "concepto": "total", "cita": "no está"}]}
    v = t.verificar(datos, TEXTO)
    assert v[0]["estado"] == "aceptado" and v[0]["importe"] == 9420
    assert v[1]["estado"] == "revision" and v[1]["motivo"] == "valor_no_en_cita"
    assert v[2]["motivo"] == "cita_no_literal"


def test_peticion_estructurada():
    p = t.peticion("x", "https://u.es/t.pdf", TEXTO)
    assert p["params"]["output_config"]["format"]["schema"]["required"] == ["es_tarifa", "curso", "precios"]


def test_unir_por_nombre_dentro_del_proveedor(tmp_path):
    (tmp_path / "t").mkdir()
    precios = [{"estado": "aceptado", "programa": "Máster Universitario en Abogacía", "importe": 8494, "concepto": "total",
                "proveedor": "prov-u", "dominio": "u.es", "url": "https://u.es/t.pdf"},
               {"estado": "aceptado", "programa": "Máster en Cocina", "importe": 1, "concepto": "total",
                "proveedor": "prov-u", "dominio": "u.es", "url": "https://u.es/t.pdf"}]
    (tmp_path / "t" / "precios.jsonl").write_text("".join(json.dumps(x) + "\n" for x in precios))
    fichas = [{"clave": "ruct:1", "grupo": "oficial", "comprobacion_nombre": "confirmado",
               "nombre_oficial": "Máster Universitario en Abogacía por la Universidad U", "paginas": ["https://www.u.es/abogacia"]},
              {"clave": "url:x", "grupo": "no_oficial", "proveedor": "prov-otro", "campos": {"nombre": {"valor": "Máster en Cocina"}}}]
    (tmp_path / "f.jsonl").write_text("".join(json.dumps(x) + "\n" for x in fichas))
    r = t.unir([tmp_path / "t"], tmp_path / "f.jsonl", tmp_path / "o")
    assert r["unidos"] == 1 and r["sin_ficha"] == 1  # «Cocina» es de otro proveedor: no se une
    x = json.loads((tmp_path / "o/datos/estudios/tarifas/precios_unidos.jsonl").read_text())
    assert x["ficha"] == "ruct:1"


def test_elegir_pdfs_del_censo_y_recientes_primero(tmp_path):
    (tmp_path / "c.jsonl").write_text(json.dumps({"id": "prov-u", "dominio": "u.es", "dominios": ["u.es"], "estado": "oficial"}) + "\n"
                                      + json.dumps({"id": "prov-x", "dominio": "x.es", "dominios": ["x.es"], "estado": "candidato"}) + "\n")
    (tmp_path / "p.jsonl").write_text(json.dumps({"dominio": "u.es", "urls": ["https://u.es/tarifas-2024.pdf", "https://u.es/tarifas-2026-27.pdf"]}) + "\n"
                                      + json.dumps({"dominio": "x.es", "urls": ["https://x.es/precios.pdf"]}) + "\n")
    f = t.elegir_pdfs([tmp_path / "p.jsonl"], tmp_path / "c.jsonl")
    assert [x["url"] for x in f] == ["https://u.es/tarifas-2026-27.pdf", "https://u.es/tarifas-2024.pdf"]


def test_enlaces_pdf_de_precio():
    html = ('<a href="/docs/tarifas-2026.pdf">Descarga</a> <a href="programa.pdf">Plan de estudios</a>'
            '<a href="https://u.es/f.pdf?v=2"><span>Folleto del máster</span></a>')
    pdfs = [(h, txt) for h, txt in t.RE_ENLACE_PDF.findall(html)]
    elegidos = [h for h, txt in pdfs if t.TEXTO_PRECIO.search(h) or t.TEXTO_PRECIO.search(txt)]
    assert elegidos == ["/docs/tarifas-2026.pdf", "https://u.es/f.pdf?v=2"]


def test_descubrir_pdfs_en_originales(tmp_path, monkeypatch):
    class Alm:
        def leer(self, clave):
            return ('<a href="/docs/tarifas-2026.pdf">x</a><a href="https://otro.es/precios.pdf">y</a>'
                    '<a href="plan.pdf">Plan</a>').encode()

    monkeypatch.setattr(e.Guarda, "__init__", lambda self, almacen="auto": (setattr(self, "almacen", Alm()),
                                                                             setattr(self, "cuentas", {}))[0])
    d = tmp_path / "c"
    d.mkdir()
    (d / "paginas_capturadas.jsonl").write_text(json.dumps({"url": "https://www.u.es/master/x", "clave": "web-centros/a.html.gz"}) + "\n")
    r = t.descubrir_en_originales([d], tmp_path / "o")
    x = json.loads((tmp_path / "o" / "precios_desde_paginas.jsonl").read_text())
    assert r["pdfs"] == 1 and x == {"dominio": "u.es", "urls": ["https://www.u.es/docs/tarifas-2026.pdf"]}


def test_tarifas_otra_moneda_y_un_precio_por_ficha(tmp_path):
    v = t.verificar({"precios": [{"programa": "Máster X", "importe": "150.000", "concepto": "total", "cita": "Máster X MXN 150.000"}]},
                    "Máster X MXN 150.000")
    assert v[0]["estado"] == "revision"
    (tmp_path / "t").mkdir()
    base = {"estado": "aceptado", "programa": "Máster Universitario en Abogacía", "concepto": "total", "proveedor": "p", "dominio": "u.es"}
    precios = [{**base, "importe": 8000, "curso": "2023-2024", "url": "https://u.es/a.pdf"},
               {**base, "importe": 9500, "curso": "2026-2027", "url": "https://u.es/b.pdf"},
               {**base, "importe": 9500, "curso": "2026-2027", "url": "https://u.es/b.pdf"}]
    (tmp_path / "t" / "precios.jsonl").write_text("".join(json.dumps(x) + "\n" for x in precios))
    (tmp_path / "f.jsonl").write_text(json.dumps({"clave": "ruct:1", "grupo": "oficial", "comprobacion_nombre": "confirmado",
                                                  "nombre_oficial": "Máster Universitario en Abogacía por la U",
                                                  "paginas": ["https://u.es/abogacia"]}) + "\n")
    r = t.unir([tmp_path / "t"], tmp_path / "f.jsonl", tmp_path / "o")
    x = [json.loads(l) for l in (tmp_path / "o/datos/estudios/tarifas/precios_unidos.jsonl").read_text().splitlines()]
    assert r["unidos"] == 1 and x[0]["importe"] == 9500


def test_tablas_revisadas_con_su_universidad(tmp_path):
    f = tmp_path / "tablas.jsonl"
    f.write_text("\n".join(json.dumps(x) for x in [
        {"universidad": "Universidad de Navarra", "url": "https://www.unav.edu/admision-y-ayudas/master/precios",
         "tipo": "html", "curso": "2026-2027"},
        {"universidad": "Universidad de Navarra", "url": "https://www.unav.edu/admision-y-ayudas/master/precios"},
        {"universidad": "", "url": "https://x.es/p.pdf"},
        {"universidad": "IE Universidad", "url": "https://www.ie.edu/masters/master-in-management/admissions-fees",
         "programa": "Master in Management"}]))
    filas = t.elegir_tablas(f)
    assert [x["dominio"] for x in filas] == ["unav.edu", "ie.edu"]
    assert filas[0]["estado"] == "tabla" and filas[0]["curso_lista"] == "2026-2027"
    assert filas[1]["programa_lista"] == "Master in Management"


def test_cita_de_tabla_web_sin_separadores():
    texto = "Tuition fee | 43,300€\nAdmission fee | 150€"
    v = t.verificar({"precios": [{"programa": "Master in Management", "importe": "43,300", "concepto": "total",
                                  "cita": "Tuition fee 43,300€"}]}, texto)
    assert v[0]["estado"] == "aceptado" and v[0]["importe"] == 43300 and v[0]["cita_nivel"] == "sin_signos"
