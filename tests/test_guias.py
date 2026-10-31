from motor.estudios import guias as g


def test_enlaces_de_guia_del_propio_centro():
    html = ('<a href="/doa/consultaPublica/look[conpub]MostrarPubGuiaDocAs?_codAsignatura=123">Ver</a>'
            '<a href="https://www.uv.es/recursos/fatwirepub/guias/43001-CAS-2025-26.pdf">Guía</a>'
            '<a href="/docs/guia-docente-finanzas.pdf">Guía docente de Finanzas</a>'
            '<a href="/docs/guia-del-tfm.pdf">Guía docente del TFM</a>'
            '<a href="https://otra.es/guia-docente.pdf">Guía docente</a>'
            '<a href="/docs/normativa.pdf">Normativa</a>')
    out = g.enlaces_de_guia(html, "https://www.uv.es/master/finanzas")
    assert out == ["https://www.uv.es/doa/consultaPublica/look[conpub]MostrarPubGuiaDocAs?_codAsignatura=123",
                   "https://www.uv.es/recursos/fatwirepub/guias/43001-CAS-2025-26.pdf",
                   "https://www.uv.es/docs/guia-docente-finanzas.pdf"]


def test_peso():
    assert g.peso("40") == (40, 40) and g.peso("40 %") == (40, 40) and g.peso("30-50 %") == (30, 50)
    assert g.peso("30 a 50") == (30, 50) and g.peso("mucho") == (None, None) and g.peso("150") == (None, None)


def test_verificar_solo_lo_citado():
    texto = ("Sistema de evaluación\nExamen final: 60 %\nTrabajos prácticos | 40%\nAsistencia a clase "
             "(obligatoria)")
    datos = {"es_guia": True, "asignatura": "Finanzas", "creditos": "6", "curso_academico": "2025-2026",
             "evaluacion": [{"sistema": "Examen final", "peso": "60", "cita": "Examen final: 60 %"},
                            {"sistema": "Trabajos", "peso": "40", "cita": "Trabajos prácticos: 40%"},
                            {"sistema": "Asistencia", "peso": "10", "cita": "Asistencia a clase obligatoria 10 %"}],
             "metodologia": ["Clases magistrales"]}
    v = g.verificar(datos, texto)
    assert [s["sistema"] for s in v["evaluacion"]] == ["Examen final", "Trabajos"]
    assert v["evaluacion"][1]["cita_nivel"] == "sin_signos" and v["evaluacion_completa"] and v["creditos"] == 6
    assert v["cuentas"] == {"sistemas_aceptados": 2, "cita_no_literal": 1}


def test_ruta_con_puntos_se_normaliza():
    out = g.enlaces_de_guia('<a href="/content/../master/guiadocent/pdf/esp/1/x.pdf">Guía docente</a>', "https://www.upc.edu/m")
    assert out == ["https://www.upc.edu/master/guiadocent/pdf/esp/1/x.pdf"]


def test_el_peso_tiene_que_ser_un_porcentaje_de_la_cita():
    assert g.porcentaje_en_cita(60, "Test de 40 preguntas: 60 %") and not g.porcentaje_en_cita(40, "Test de 40 preguntas: 60 %")
    assert not g.porcentaje_en_cita(10, "Nota mínima 5 sobre 10") and not g.porcentaje_en_cita(2, "Examen de 2 horas, 50 %")
    assert g.porcentaje_en_cita(30, "Trabajos: 30-50 %") and g.porcentaje_en_cita(50, "Trabajos: 30-50 %")
    assert g.porcentaje_en_cita(40, "un 40 por ciento de la nota")


def test_descubrir_desde_la_lista_de_paginas_sin_las_ya_leidas(tmp_path, monkeypatch):
    import json
    from motor.estudios import extraer, guias

    pag = tmp_path / "paginas.jsonl"
    pag.write_text(json.dumps({"url": "https://www.u.es/master-x/plan", "clave": "k", "codigos_ruct": ["4310001"]}) + "\n")
    (tmp_path / "ya.txt").write_text("https://www.u.es/guias/A.pdf\n")

    class Almacen:
        def leer(self, clave):
            return (b'<a href="/guias/A.pdf">Gu\xc3\xada docente A</a><a href="/guias/B.pdf">Gu\xc3\xada docente B</a>')

    class G:
        activa = True
        almacen = Almacen()

    monkeypatch.setattr(extraer, "Guarda", G)
    r = guias.descubrir([], tmp_path / "o", paginas=pag, excluir=tmp_path / "ya.txt")
    filas = [json.loads(l) for l in (tmp_path / "o" / "guias_descubiertas.jsonl").read_text().splitlines()]
    assert [f["url"] for f in filas] == ["https://www.u.es/guias/B.pdf"] and filas[0]["codigos_ruct"] == ["4310001"]
    assert r["ya_leidas"] == 1
