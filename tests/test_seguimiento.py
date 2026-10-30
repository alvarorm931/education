from datetime import date

from motor.estudios import seguimiento as s

HOY = date(2026, 10, 29)


def test_origen_de_cada_campo_y_siguiente_paso():
    hechos = {
        "precio_total": {"campo": "precio_total", "valor": 9900, "estado": "aceptado", "cita": "Precio: 9.900 €",
                         "url": "https://x.es/master", "extraido": "2026-10-29T10:00:00+00:00"},
        "evaluacion": {"campo": "evaluacion", "valor_propuesto": "50 % examen", "estado": "revision", "cita": "x"},
        "asignaturas": {"campo": "asignaturas", "valor": ["A"], "estado": "aceptado", "cita": "A",
                        "url": "https://x.es/docs/plan.pdf", "extraido": "2026-10-29T10:00:00+00:00"},
    }
    oficiales = {"plazas": {"valor": 40, "fuente": "RUCT", "url": "https://ruct", "capturado": "2026-10-28"}}
    facilitados = {"horario": {"valor": "viernes tarde y sábado", "fecha": "2026-10-20", "canal": "correo"}}
    r = s.seguir("https://x.es/master", hechos, {"extraido": True, "formulario_pide_correo": True}, oficiales,
                 facilitados, HOY)
    c = r["campos"]
    assert c["precio_total"]["estado"] == "publicado_ficha" and c["precio_total"]["valor"] == 9900
    assert c["asignaturas"]["estado"] == "documento_publico"
    assert c["plazas"]["estado"] == "fuente_oficial"
    assert c["horario"]["estado"] == "facilitado_centro" and c["horario"]["proxima_comprobacion"] == "2027-10-29"
    assert c["evaluacion"]["estado"] == "en_revision"
    assert c["metodologia"]["estado"] == "solo_con_registro"
    assert c["metodologia"]["siguiente_paso"].startswith("buscar_documento_publico")
    assert "metodologia" in r["pedir_al_centro"] and "precio_total" not in r["pedir_al_centro"]
    assert r["transparencia"] == 0.3  # precio, asignaturas y plazas de 10 esenciales


def test_sin_extraer_no_es_sin_dato():
    r = s.seguir("https://x.es/m", {}, {}, {}, {}, HOY)
    assert {e["estado"] for e in r["campos"].values()} == {"sin_comprobar"}
    assert r["transparencia"] is None and r["pedir_al_centro"] == []
    r2 = s.seguir("https://x.es/m", {}, {"extraido": True, "formulario_pide_correo": False}, {}, {}, HOY)
    assert r2["campos"]["precio_total"]["estado"] == "no_publicado" and r2["transparencia"] == 0.0


def test_frecuencia_segun_temporada():
    fuera = {"plazo_admision": {"valor": {"hasta": "2026-07-31"}, "estado": "aceptado"}}
    assert not s.en_temporada(HOY, fuera)
    assert s.en_temporada(date(2026, 3, 1), {})
    assert s.proxima("publicado_ficha", True, HOY) == date(2026, 11, 5)
    assert s.proxima("publicado_ficha", False, HOY) == date(2026, 11, 28)


def test_ejecutar(tmp_path):
    import json
    (tmp_path / "h.jsonl").write_text(json.dumps({"url": "https://x.es/m", "campo": "precio_total", "valor": 1,
                                                  "estado": "aceptado", "cita": "1 €", "extraido": "2026-10-29"}) + "\n")
    (tmp_path / "m.jsonl").write_text(json.dumps({"url": "https://x.es/m", "formulario_pide_correo": True}) + "\n" +
                                      json.dumps({"url": "https://x.es/n", "formulario_pide_correo": True}) + "\n")
    (tmp_path / "e.jsonl").write_text(json.dumps({"url": "https://x.es/n", "no_es_programa": True}) + "\n")
    res = s.ejecutar(tmp_path / "h.jsonl", tmp_path / "m.jsonl", tmp_path / "out", hoy=HOY, extraidas=tmp_path / "e.jsonl")
    assert res["paginas"] == 1 and res["no_programa"] == 1 and res["campos_a_pedir"]["metodologia"] == 1


def test_estado_por_master_desde_fichas(tmp_path):
    import json
    from datetime import date
    from motor.estudios import seguimiento as sg
    fichas = [{"clave": "ruct:1", "grupo": "oficial", "comprobacion_nombre": "confirmado", "codigo_ruct": "1",
               "fuentes": [{"url": "https://u.es/m", "extraido": "2026-10-30T03:00:00+00:00"}],
               "campos": {"asignaturas": {"valor": ["A"], "fuente": 0}},
               "oficiales": {"tipo_titulo": {"valor": "máster universitario oficial", "fuente": "catalogo_siiu"},
                             "titularidad": {"valor": "Pública"}}},
              {"clave": "url:x", "grupo": "no_oficial", "es_master": True, "proveedor": "prov-a", "fuentes": [], "campos": {}}]
    (tmp_path / "f.jsonl").write_text("".join(json.dumps(x) + "\n" for x in fichas))
    r = sg.desde_fichas(tmp_path / "f.jsonl", tmp_path / "o", hoy=date(2026, 10, 30))
    assert r["masters"] == 2
    assert r["por_campo"]["precio_total"] == {"fuente_oficial_pendiente": 1, "no_publicado": 1}
    assert r["por_campo"]["asignaturas"]["publicado_ficha"] == 1 and r["por_campo"]["tipo_titulo"]["fuente_oficial"] == 1
