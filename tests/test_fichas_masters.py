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
    assert uno["campos"]["precio_total"]["valor"] == 2400 and uno["campos"]["precio_total"]["pagina"] == "subpagina"
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
    cat = [{"codigo_ruct": c, "nombre_oficial": "Máster Universitario en Dirección y Gestión de Empresas Familiares por la U"}
           for c in ("1", "2")]
    (tmp_path / "c.json").write_text(json.dumps(cat))
    r = f.ejecutar([tmp_path / "e"], tmp_path / "o", catalogo=tmp_path / "c.json")
    assert r["oficial_probable_sin_confirmar"] == 1 and r["oficial_probable_oficial"] == 1
