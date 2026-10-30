import json

from motor.grados import fichas


def _cat():
    return [{"codigo": "2500828", "clase": "grado", "nombre": "Derecho", "nombre_oficial": "Graduado o Graduada en Derecho por la Universidad Complutense de Madrid",
             "situacion": "Activo", "universidades": [{"nombre": "Complutense de Madrid", "tipo": "Pública"}],
             "universidad_tipo": "Pública", "rama": "CSJ", "campo": "Derecho", "componentes": [],
             "imparticiones": [{"situacion": "Activo", "presencialidad": "Estudio presencial", "idioma_extranjero": "No"}],
             "fuente": {"url": "u", "curso": "2025-2026", "capturado": "x"}}]


GEN = [{"id": "derecho", "nombre": "Derecho", "titulos": ["2500828"], "pagina_propia": True}]
TARJ = {("2500828", "28027001"): {"codTitula": "2500828", "codCentro": "28027001", "nombreCentro": "Facultad de Derecho",
                                  "tipoCentro": "Propio", "provincia": "Madrid", "notaCorte": "8.44", "anio": "2025-2026"}}
DET = {("2500828", "28027001"): {"detalle": {"nota_corte": 8.44, "nota_corte_anterior": 8.88, "plazas": 709.0,
                                             "precio_credito": 16.92, "creditos": 240.0, "curso": "2025-2026"},
                                 "insercion": {"tasa_afiliacion": 65.67, "base_media_cotizacion": 29115.69},
                                 "fuente": {"capturado": "2026-10-30T02:00:00+00:00"}}}
PLAN = {"identificador": "BOE-A-2024-1", "fecha": "2024-03-01", "tipo": "plan",
        "esperado_sin_optativas": 12.0, "suma_sin_optativas": 12.0,
        "distribucion": {"formacion_basica": 6, "obligatorias": 6, "optativas": 0, "total": 12},
        "plan": [{"nombre": "Derecho Romano", "tipo": "basica", "creditos": 6, "curso": 1, "semestre": 1},
                 {"nombre": "Derecho Civil I", "tipo": "obligatoria", "creditos": 6, "curso": 1, "semestre": 2}]}


def test_ficha_completa_es_indexable():
    planes = {(fichas.clave_universidad("Universidad Complutense de Madrid"), "derecho"): [PLAN]}
    f, comp = fichas.construir(_cat(), GEN, TARJ, DET, planes)
    f = f[0]
    assert f["indexable"] and f["motivos_noindex"] == []
    assert f["precio_primera_matricula"] == round(16.92 * 240, 2)
    assert f["centros"][0]["plazas"] == 709 and f["centros"][0]["insercion"]["tasa_afiliacion"] == 65.67
    assert f["plan"]["comprobado"] and len(f["plan"]["asignaturas"]) == 2
    assert comp[0]["generico"] == "derecho" and comp[0]["filas"][0]["nota_corte"] == 8.44


def test_sin_plan_ni_datos_no_indexa():
    f, _ = fichas.construir(_cat(), GEN, {}, {}, {})
    assert not f[0]["indexable"]
    assert set(f[0]["motivos_noindex"]) == {"sin asignaturas comprobadas", "sin nota de corte ni precio"}


def test_clave_universidad():
    assert fichas.clave_universidad("Universidad Complutense de Madrid") == fichas.clave_universidad("Complutense de Madrid")
    assert fichas.clave_universidad("Universitat de València (Estudi General)") == fichas.clave_universidad("València (Estudi General)")


def test_indicadores_por_universidad_y_ambito(tmp_path):
    import json
    d = tmp_path / "ind"
    d.mkdir()
    filas = [{"Universidad": "Complutense de Madrid", "Ámbito de estudio": "Derecho", "Indicador": "Tasa global de abandono", "Periodo": p, "valor": v}
             for p, v in (("2018-2019", 23.19), ("2019-2020", 18.75))]
    filas.append({"Universidad": "Todas las universidades", "Ámbito de estudio": "Derecho", "Indicador": "Tasa global de abandono", "Periodo": "2019-2020", "valor": 24.0})
    (d / "abandono.jsonl").write_text("\n".join(json.dumps(x) for x in filas), encoding="utf-8")
    ind = fichas.indexar_indicadores(d)
    cat = _cat()
    cat[0]["ambito"] = "Derecho"
    f, _ = fichas.construir(cat, GEN, TARJ, DET, {}, ind)
    v = f[0]["indicadores"]["valores"]["abandono"]
    assert (v["valor"], v["curso"], v["media_espana_ambito"]) == (18.75, "2019-2020", 24.0)
    assert f[0]["indicadores"]["grados_de_la_universidad_en_el_ambito"] == 1


def test_bonificacion_por_comunidad_solo_en_publicas():
    from motor.grados import precios
    assert precios.de_comunidad("Andalucía")["tipo"] == "bonificacion"
    assert precios.de_comunidad("Castilla y León")["tipo"] == "ayuda"
    assert precios.de_comunidad("Cantabria") is None  # solo vista en prensa: fuera hasta verificarla
    cat = _cat()
    cat[0]["universidades"][0]["comunidad"] = "Galicia"
    assert fichas.construir(cat, GEN, TARJ, DET, {})[0][0]["bonificacion"]["norma"].startswith("Decreto 72/2026")
    cat[0]["universidad_tipo"] = "Privada"
    assert fichas.construir(cat, GEN, TARJ, DET, {})[0][0]["bonificacion"] is None


def _imp(valor, tipo):
    return {"valor": valor, "tipo": tipo, "verosimil": True, "contexto_sha256": "x"}


def test_precio_web_prefiere_curso_que_cuadra_con_el_credito_y_no_se_fia_del_jsonld_que_no_cuadra():
    from motor.grados.fichas import precio_web
    f = {"url": "https://u.es/grado/farmacia", "precio_jsonld": {"precio": 15000, "moneda": "EUR"},
         "importes": [_imp(230.0, "credito"), _imp(13800.0, "curso"), _imp(950.0, "reserva")]}
    p = precio_web(f)
    assert p["precio_curso"] == 13800.0 and p["metodo"] == "curso_igual_a_credito_por_60"
    # datos estructurados que contradicen al texto y sin crédito que desempate: sin precio, con nota
    p = precio_web({"url": "x", "precio_jsonld": {"precio": 2880, "moneda": "EUR"}, "importes": [_imp(4800.0, "curso")]})
    assert p["precio_curso"] is None and "distintos" in p["nota"]


def test_precio_web_resto_de_casos():
    from motor.grados.fichas import precio_web
    assert precio_web({"url": "x", "precio_jsonld": {"precio": 3060, "moneda": "EUR"}, "importes": []})["metodo"] == "datos_estructurados"
    p = precio_web({"url": "x", "importes": [_imp(9000.0, "curso"), _imp(9900.0, "curso")]})
    assert p["precio_curso"] == 9000.0 and "desde" in p["nota"]
    assert precio_web({"url": "x", "importes": [_imp(6000.0, "curso"), _imp(15000.0, "curso")]})["precio_curso"] is None
    assert precio_web({"url": "x", "importes": [_imp(213.0, "credito")]})["precio_curso"] == 12780.0
    assert precio_web({"url": "x", "importes": [_imp(1400.0, "mensual")]})["precio_curso"] is None
    assert precio_web({"url": "x", "importes": []}) is None


def test_indexar_web_privadas_gana_el_rastreo_mas_reciente(tmp_path):
    from motor.grados.fichas import indexar_web_privadas
    for carpeta, url, imp in (("20261030T010000-t0", "https://u.es/a", [_imp(9000.0, "curso")]),
                              ("20261030T030000-t0", "https://u.es/b", [])):
        d = tmp_path / carpeta / "datos" / "estudios" / "grados" / "web_privadas"
        d.mkdir(parents=True)
        (d / "123.json").write_text(json.dumps({"universidad": "U", "fichas": {"2500001": {"url": url, "importes": imp}}}))
    assert indexar_web_privadas(tmp_path) == {}
