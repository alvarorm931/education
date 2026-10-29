"""Tanda de prueba de la extracción: suma del uso que devuelve la API y coste con los precios de lote."""

import json
from types import SimpleNamespace

from motor.ia import prueba_extraccion as pe


def test_coste_y_resumen(tmp_path, monkeypatch):
    html = tmp_path / "p.html"
    html.write_text("<html><body><h1>Máster en Cine</h1><p>El precio total es de 4.500 euros por curso.</p>"
                    "<p>60 créditos ECTS</p></body></html>", encoding="utf-8")
    pagina = {"url": "https://www.ejemplo.es/master-cine/", "sha256": "ab", "ruta": str(html)}
    texto = json.dumps({"precio_total": {"valor": 4500, "cita": "El precio total es de 4.500 euros"},
                        "creditos_ects": {"valor": 60, "cita": "90 créditos ECTS"}})
    resultados = "\n".join(json.dumps(x) for x in [
        {"custom_id": "a", "result": {"type": "succeeded", "message": {
            "content": [{"type": "text", "text": texto}], "stop_reason": "end_turn",
            "usage": {"input_tokens": 10_000, "output_tokens": 800, "cache_creation_input_tokens": 0,
                      "cache_read_input_tokens": 0}}}},
        {"custom_id": "b", "result": {"type": "errored", "error": {"type": "invalid_request_error"}}},
    ])
    monkeypatch.setattr(pe, "_api", lambda *a, **k: SimpleNamespace(text=resultados))
    r = pe.recoger({"id": "msgbatch_x", "results_url": "u", "processing_status": "ended"}, {"a": pagina}, tmp_path)
    # 10.000 × 0,05 + 800 × 0,25 por millón = 0,0007 $
    assert r["coste_usd"] == 0.0007 and r["coste_por_pagina_usd"] == 0.0007
    assert r["proyeccion_usd"]["30000_paginas"] == 21.0
    assert r["resultados"] == {"succeeded": 1, "errored": 1}
    assert r["campos"] == 2 and r["campos_aceptados"] == 1  # la cita de los créditos no está en el texto
    hechos = [json.loads(l) for l in (tmp_path / "hechos_sin_cita.jsonl").read_text().splitlines()]
    assert all("cita" not in h for h in hechos)


def test_candidatos_sin_subpaginas():
    info = {"programas": ["https://www.unir.net/artes/master-cine/", "https://www.unir.net/artes/master-cine/acceso/",
                          "https://www.unir.net/artes/master-cine/plan-de-estudios/",
                          "https://www.unir.net/artes/master-danza/"]}
    assert pe.candidatos(info, 5) == ["https://www.unir.net/artes/master-cine/", "https://www.unir.net/artes/master-danza/"]
