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
