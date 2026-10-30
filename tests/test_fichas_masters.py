import json

from motor.estudios import fichas_masters as f


def test_comprobar_nombre():
    o = "Máster Universitario en Ingeniería Industrial por la Universidad de Navarra"
    assert f.comprobar_nombre(o, "Máster Universitario en Ingeniería Industrial")[0] == "confirmado"
    assert f.comprobar_nombre(o, "Máster en Ingeniería")[0] == "probable"
    assert f.comprobar_nombre(o, "Máster en Derecho de la Empresa")[0] == "distinto"
    assert f.comprobar_nombre(o, None)[0] == "sin_nombre"


def _escribir(d, paginas, hechos):
    d.mkdir(parents=True)
    (d / "paginas_extraidas.jsonl").write_text("".join(json.dumps(p) + "\n" for p in paginas))
    (d / "hechos.jsonl").write_text("".join(json.dumps(h) + "\n" for h in hechos))


def test_ficha_oficial_une_principal_y_subpagina_y_rechaza_pagina_de_otro_master(tmp_path):
    t = "2026-10-30T03:00:00+00:00"
    paginas = [{"url": "https://u.es/m", "extraido": t, "grupo": "oficial", "codigos_ruct": ["1"], "pagina": "principal"},
               {"url": "https://u.es/m/precios", "extraido": t, "grupo": "oficial", "codigos_ruct": ["1"],
                "pagina": "subpagina", "principal": "https://u.es/m"},
               {"url": "https://u.es/x", "extraido": t, "grupo": "oficial", "codigos_ruct": ["2"], "pagina": "principal"}]
    h = lambda url, campo, valor: {"url": url, "campo": campo, "valor": valor, "estado": "aceptado", "extraido": t,
                                   "captura_sha256": "s", "cita_sha256": "c"}
    hechos = [h("https://u.es/m", "nombre", "Máster Universitario en Química Industrial"),
              h("https://u.es/m", "creditos_ects", 60),
              h("https://u.es/m/precios", "precio_total", 2400),
              h("https://u.es/x", "nombre", "Máster en Historia del Arte")]
    _escribir(tmp_path / "e1", paginas, hechos)
    cat = [{"codigo_ruct": "1", "nombre_oficial": "Máster Universitario en Química Industrial por la Universidad X",
            "universidad": "X", "rama": "Ciencias"},
           {"codigo_ruct": "2", "nombre_oficial": "Máster Universitario en Biotecnología por la Universidad X",
            "universidad": "X", "rama": "Ciencias"}]
    (tmp_path / "cat.json").write_text(json.dumps(cat))
    r = f.ejecutar([tmp_path / "e1"], tmp_path / "o", catalogo=tmp_path / "cat.json")
    fichas = {x["clave"]: x for x in map(json.loads, (tmp_path / "o/datos/estudios/masters/fichas.jsonl").read_text().splitlines())}
    uno = fichas["ruct:1"]
    assert uno["comprobacion_nombre"] == "confirmado"
    precio = uno["campos"]["precio_total"]
    assert precio["valor"] == 2400 and uno["fuentes"][precio["fuente"]]["pagina"] == "subpagina"
    assert uno["fuentes"][precio["fuente"]]["url"] == "https://u.es/m/precios"
    assert uno["oficiales"]["tipo_titulo"]["valor"] == "máster universitario oficial"
    assert fichas["ruct:2"]["comprobacion_nombre"] == "distinto" and fichas["ruct:2"]["campos"] == {}
    assert r["oficial_confirmado"] == 1 and r["oficial_distinto"] == 1
    assert "cita" not in json.dumps(uno).replace("cita_sha256", "")


def test_probable_solo_si_la_pagina_dice_oficial(tmp_path):
    t = "2026-10-30T03:00:00+00:00"
    pag = [{"url": "https://u.es/a", "extraido": t, "grupo": "oficial", "codigos_ruct": ["1"], "pagina": "principal"},
           {"url": "https://u.es/b", "extraido": t, "grupo": "oficial", "codigos_ruct": ["2"], "pagina": "principal"}]
    h = lambda url, campo, valor: {"url": url, "campo": campo, "valor": valor, "estado": "aceptado", "extraido": t,
                                   "captura_sha256": "s"}
    hs = [h("https://u.es/a", "nombre", "Máster en Dirección de Empresas"), h("https://u.es/a", "tipo_titulo", "otro"),
          h("https://u.es/b", "nombre", "Máster en Dirección de Empresas"),
          h("https://u.es/b", "tipo_titulo", "máster universitario oficial"), h("https://u.es/b", "plazas", 40)]
    _escribir(tmp_path / "e", pag, hs)
    cat = [{"codigo_ruct": c, "universidad_codigo": c,  # de universidades distintas: no compiten entre sí
            "nombre_oficial": "Máster Universitario en Dirección y Gestión de Empresas Familiares por la U"} for c in ("1", "2")]
    (tmp_path / "c.json").write_text(json.dumps(cat))
    r = f.ejecutar([tmp_path / "e"], tmp_path / "o", catalogo=tmp_path / "c.json")
    assert r["oficial_probable_sin_confirmar"] == 1 and r["oficial_probable_oficial"] == 1


def test_rescate_de_oficial_por_nombre(tmp_path):
    t = "2026-10-30T03:00:00+00:00"
    pag = [{"url": "https://u.es/vieja", "extraido": t, "grupo": "oficial", "codigos_ruct": ["1"], "pagina": "principal",
            "no_es_programa": True},
           {"url": "https://u.es/master-quimica", "extraido": t, "grupo": "propio_oficial", "proveedor": "prov-u",
            "pagina": "principal"}]
    h = lambda url, campo, valor: {"url": url, "campo": campo, "valor": valor, "estado": "aceptado", "extraido": t,
                                   "captura_sha256": "s"}
    hs = [h("https://u.es/master-quimica", "nombre", "Máster Universitario en Química Industrial"),
          h("https://u.es/master-quimica", "tipo_titulo", "máster universitario oficial"),
          h("https://u.es/master-quimica", "plazas", 25)]
    _escribir(tmp_path / "e", pag, hs)
    (tmp_path / "c.json").write_text(json.dumps([{"codigo_ruct": "1", "universidad_codigo": "001", "situacion": "Activo",
        "nombre_oficial": "Máster Universitario en Química Industrial por la Universidad X"}]))
    (tmp_path / "p.jsonl").write_text(json.dumps({"id": "prov-u", "ruct": [{"universidad": "001"}]}) + "\n")
    r = f.ejecutar([tmp_path / "e"], tmp_path / "o", catalogo=tmp_path / "c.json", censo=tmp_path / "p.jsonl")
    fichas = [json.loads(l) for l in (tmp_path / "o/datos/estudios/masters/fichas.jsonl").read_text().splitlines()]
    uno = next(x for x in fichas if x["clave"] == "ruct:1")
    assert uno["comprobacion_nombre"] == "confirmado_por_nombre" and uno["campos"]["plazas"]["valor"] == 25
    assert r["paginas_rescatadas_como_oficiales"] == 1 and not any(x["grupo"] == "no_oficial" for x in fichas)


def test_gana_la_mejor_candidata_de_un_mismo_master(tmp_path):
    t = "2026-10-30T03:00:00+00:00"
    pag = [{"url": "https://u.es/evento", "extraido": t, "grupo": "oficial", "codigos_ruct": ["1"], "pagina": "principal",
            "no_es_programa": True},
           {"url": "https://u.es/master-q", "extraido": t, "grupo": "oficial", "codigos_ruct": ["1"], "pagina": "principal"}]
    h = lambda url, campo, valor: {"url": url, "campo": campo, "valor": valor, "estado": "aceptado", "extraido": t,
                                   "captura_sha256": "s"}
    _escribir(tmp_path / "e", pag, [h("https://u.es/master-q", "nombre", "Máster Universitario en Química Industrial"),
                                    h("https://u.es/master-q", "plazas", 30)])
    (tmp_path / "c.json").write_text(json.dumps([{"codigo_ruct": "1", "nombre_oficial": "Máster Universitario en Química Industrial por la U"}]))
    f.ejecutar([tmp_path / "e"], tmp_path / "o", catalogo=tmp_path / "c.json")
    x = json.loads((tmp_path / "o/datos/estudios/masters/fichas.jsonl").read_text().splitlines()[0])
    assert x["comprobacion_nombre"] == "confirmado" and x["campos"]["plazas"]["valor"] == 30
    assert x["paginas"] == ["https://u.es/master-q"]


def test_rescate_por_universidad_que_dice_la_pagina(tmp_path):
    t = "2026-10-30T03:00:00+00:00"
    pag = [{"url": "https://tai.es/master-animacion", "extraido": t, "grupo": "no_oficial", "proveedor": "prov-tai",
            "pagina": "principal"}]
    h = lambda campo, valor: {"url": "https://tai.es/master-animacion", "campo": campo, "valor": valor,
                              "estado": "aceptado", "extraido": t, "captura_sha256": "s"}
    _escribir(tmp_path / "e", pag, [h("nombre", "Máster Universitario en Creación de Animación Audiovisual"),
                                    h("tipo_titulo", "máster universitario oficial"),
                                    h("universidad_que_expide", "Universidad Rey Juan Carlos")])
    cat = [{"codigo_ruct": "1", "universidad": "Rey Juan Carlos", "universidad_codigo": "045", "situacion": "Activo",
            "nombre_oficial": "Máster Universitario en Creación de Animación Audiovisual por la Universidad Rey Juan Carlos"},
           {"codigo_ruct": "2", "universidad": "Barcelona", "universidad_codigo": "001", "situacion": "Activo",
            "nombre_oficial": "Máster Universitario en Creación de Animación Audiovisual por la Universidad de Barcelona"}]
    (tmp_path / "c.json").write_text(json.dumps(cat))
    (tmp_path / "p.jsonl").write_text(json.dumps({"id": "prov-tai", "ruct": []}) + "\n")
    f.ejecutar([tmp_path / "e"], tmp_path / "o", catalogo=tmp_path / "c.json", censo=tmp_path / "p.jsonl")
    fichas = {x["clave"]: x for x in map(json.loads, (tmp_path / "o/datos/estudios/masters/fichas.jsonl").read_text().splitlines())}
    assert fichas["ruct:1"]["comprobacion_nombre"] == "confirmado_por_nombre" and "ruct:2" not in fichas


def test_altas_del_boe_entran_en_el_catalogo():
    cat = {"1": {"codigo_ruct": "1", "universidad": "Cardenal Herrera-CEU", "universidad_codigo": "080",
                 "universidad_tipo": "Privada", "situacion": "Activo", "nombre_oficial": "x"}}
    n = f.con_altas(cat, [{"codigo_ruct": "4317450", "nombre": "Máster Universitario en Dirección y Gestión en Enfermería",
                           "universidad": "Universidad Cardenal Herrera-CEU", "boe": "BOE-A-2022-619", "fecha": "2022-01-15"},
                          {"codigo_ruct": "1", "nombre": "repetido"}])
    assert n == 1 and cat["4317450"]["universidad_codigo"] == "080" and "boe.es" in cat["4317450"]["fuente"]["url"]


def test_tarifa_pdf_rellena_sin_pisar_la_pagina():
    fichas = [{"clave": "url:a", "grupo": "no_oficial", "campos": {"precio_total": {"valor": 9000, "fuente": 0}},
               "fuentes": [{"url": "https://a.es/m"}]},
              {"clave": "url:b", "grupo": "no_oficial", "campos": {}, "fuentes": []}]
    n = f.aplicar_tarifas(fichas, [{"ficha": "url:a", "concepto": "total", "importe": 1, "url": "https://a.es/t.pdf"},
                                   {"ficha": "url:b", "concepto": "total", "importe": 7500, "url": "https://b.es/t.pdf"}])
    assert n == 1 and fichas[0]["campos"]["precio_total"]["valor"] == 9000
    b = fichas[1]
    assert b["campos"]["precio_total"]["valor"] == 7500 and b["fuentes"][0]["pagina"] == "documento"


def test_nombre_en_catalan_y_master_mas_ajustado():
    assert f.comprobar_nombre("Máster Universitario en Investigación sobre el Cáncer por la Universidad de Barcelona",
                              "Màster en Investigació sobre el Càncer")[0] == "confirmado"
    assert f.comprobar_nombre("Máster Universitario en Filosofía Analítica por la U", "Filosofía Analítica - M2503")[0] == "confirmado"
    assert f.ajuste("Máster Universitario en Derecho Penal Económico por la U", "Máster en Derecho Penal Económico") > \
        f.ajuste("Máster Universitario en Derecho Penal por la U", "Máster en Derecho Penal Económico")


def test_palabras_que_empiezan_por_m_no_son_codigos():
    from motor.estudios import fichas_masters as fm
    assert fm.comprobar_nombre("Máster Universitario en Gestión de la Moda", "Máster en Gestión de Museos")[0] != "confirmado"
    assert fm.comprobar_nombre("Máster Universitario en Ingeniería de Minas", "Máster en Ingeniería de Montes")[0] != "confirmado"
    assert fm.comprobar_nombre("Máster Universitario en Finanzas", "Máster en Finanzas - M2503")[0] == "confirmado"


def test_es_master_con_limite_de_palabra():
    from motor.estudios import fichas_masters as fm
    for no in ("Curso de Scrum Master", "Mastering Excel", "MasterClass de cocina", "Masterchef Junior"):
        assert not fm.RE_ES_MASTER.search(no), no
    for si in ("Máster en Finanzas", "Màster en Dret", "Masters in Management", "Executive MBA"):
        assert fm.RE_ES_MASTER.search(si), si


def test_nombre_en_ingles_del_titulo_bilingue():
    from motor.estudios.fichas_masters import comprobar_nombre, nombre_ingles
    o = "Máster Universitario en Finanzas / Master in Finance por la CUNEF Universidad"
    assert nombre_ingles(o) == "Master in Finance"
    assert comprobar_nombre(o, "Master in Finance")[0] == "confirmado"
    assert comprobar_nombre(o, "Master in Management")[0] == "distinto"
    assert comprobar_nombre("Máster Universitario en Química por la Universidad de Oviedo", "Master in Chemistry")[0] == "distinto"


def test_subpagina_enlazada_solo_si_es_de_ese_master():
    from motor.estudios.fichas_masters import cuelga_de, subpagina_valida

    assert cuelga_de("https://www.ucm.es/master-x-plan", "https://www.ucm.es/master-x")
    assert cuelga_de("https://u.es/m/x/plan", "https://u.es/m/x/")
    assert cuelga_de("https://u.es/m/x?tab=2", "https://u.es/m/x?tab=1")
    assert not cuelga_de("https://u.es/admision", "https://u.es/m/x")
    assert not cuelga_de("https://otra.es/m/x/plan", "https://u.es/m/x")
    oficial = "Máster Universitario en Finanzas por la Universidad de Murcia"
    general = {"url": "https://u.es/admision/precios", "pagina": "subpagina", "principal": "https://u.es/m/finanzas"}
    hechos = {general["url"]: [{"campo": "nombre", "valor": "Máster Universitario en Marketing"}]}
    assert not subpagina_valida(general, "https://u.es/m/finanzas", oficial, hechos)
    hechos = {general["url"]: [{"campo": "nombre", "valor": "Máster Universitario en Finanzas"}]}
    assert subpagina_valida(general, "https://u.es/m/finanzas", oficial, hechos)
