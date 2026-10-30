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
