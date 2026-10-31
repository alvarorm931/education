import json
from datetime import date

from motor import estado


def test_estado_y_alertas(tmp_path):
    a = tmp_path / "datos/autonomicos/dogv/dias/2026/10"
    a.mkdir(parents=True)
    (a / "28.json").write_text(json.dumps({"fecha": "2026-10-28", "resultado": "ok"}))
    (a / "27.json").write_text(json.dumps({"fecha": "2026-10-27", "resultado": "error_http", "alertas": ["HTTP 503"]}))
    o = tmp_path / "datos/autonomicos/dogv/oposiciones/2026/10"
    o.mkdir(parents=True)
    (o / "28.jsonl").write_text('{"id": 1}\n{"id": 2}\n')
    p = tmp_path / "datos/provinciales/bopb/dias/2026/10"
    p.mkdir(parents=True)
    (p / "20.json").write_text(json.dumps({"fecha": "2026-10-20", "resultado": "ok"}))
    assert estado.main(["--salida", str(tmp_path), "--hoy", "2026-10-29"]) == 1
    e = json.loads((tmp_path / "datos/estado.json").read_text())
    d = e["fuentes"]["dogv"]
    assert (d["ultimo_boletin_leido"], d["dias_habiles_sin_boletin"], d["anuncios_empleo"]) == ("2026-10-28", 1, 2)
    assert d["informes"] == {"ok": 1, "error_http": 1} and not d["alerta"]
    assert e["con_alerta"] == ["bopb"]  # 7 días hábiles sin boletín
    assert estado.dias_habiles_entre(date(2026, 10, 23), date(2026, 10, 26)) == 1


def test_huecos_de_numeracion_por_serie():
    # BOME: ordinarios 64xx correlativos y extraordinarios 1, 2, 3… cada año; BOJA: ordinarios y 5xx.
    numeros = {"2026": {6424, 6426, 47, 48, 50}, "2025": {1, 2, 3, 501, 503}}
    assert estado.huecos_numeracion(numeros) == {"2025": [502], "2026": [49, 6425]}


def test_textos_dentro_del_anuncio_cuentan(tmp_path):
    """BOJA y BOA guardan el texto en el propio anuncio: no son textos pendientes."""
    import json
    from datetime import date
    from motor.estado import estado_fuente
    op = tmp_path / "oposiciones" / "2026" / "1.jsonl"
    op.parent.mkdir(parents=True)
    op.write_text(json.dumps({"id": "a", "texto": "Bases"}) + "\n" + json.dumps({"id": "b", "texto": None}) + "\n")
    e = estado_fuente(tmp_path, date(2026, 10, 31))
    assert (e["anuncios_empleo"], e["textos"], e["textos_pendientes"]) == (2, 1, 1)
