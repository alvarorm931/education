import json
from datetime import date
from pathlib import Path

from motor.autonomicos import bocm
from motor.http import Respuesta

F = Path(__file__).parent / "fixtures"


def test_url_del_boletin_completo():
    assert bocm.url_completo(date(2026, 10, 29), 260) == "https://www.bocm.es/boletin-completo/BOCM-20261029/260"


def test_boletin_completo_html():
    # robots.txt prohíbe el sumario XML; el boletín completo en HTML da lo mismo (comprobado contra el XML del 28/10)
    s = bocm.parsear_completo((F / "bocm_completo_20261029_260.html").read_bytes())
    assert s["numero"] == "260" and s["fecha"] == "2026-10-29" and len(s["disposiciones"]) == 96
    alc = [d for d in s["disposiciones"] if d["titulo"].startswith("Alcobendas. Ofertas de empleo")][0]
    assert bocm.es_empleo_publico(alc) and bocm.ambito(alc) == "local" and alc["organismo"] == "ALCOBENDAS"
    assert bocm.municipio_y_materia(alc["titulo"]) == ("Alcobendas", "Ofertas de empleo", "Proceso selectivo")
    assert alc["url_xml"].startswith("https://www.bocm.es/boletin/CM_Orden_BOCM/2026/10/29/BOCM-20261029-")
    urbanismo = [d for d in s["disposiciones"] if "Urbanismo" in d["titulo"]][0]
    assert not bocm.es_empleo_publico(urbanismo)
    s28 = bocm.parsear_completo((F / "bocm_completo_20261028_258.html").read_bytes())
    d1 = s28["disposiciones"][0]
    assert (d1["id"], d1["seccion"], d1["apartado"]) == ("BOCM-20261028-1", "I. COMUNIDAD DE MADRID",
                                                         "B) Autoridades y Personal")
    assert d1["titulo"].startswith("Puesto libre designación Orden de 19 de octubre de 2026")


def _servidor(paginas):
    def obtener(url, **kw):
        return Respuesta(url, 200, paginas[url], {}) if url in paginas else Respuesta(url, 404, b"", {})
    return obtener


def test_numero_desde_el_dia_anterior_y_extraordinario(tmp_path, monkeypatch):
    # El 28/10 salió el 258 y, aparte, el extraordinario 259; el 29/10, el 260.
    dias = tmp_path / "datos/autonomicos/bocm/dias/2026/10"
    dias.mkdir(parents=True)
    (dias / "27.json").write_text(json.dumps({"fecha": "2026-10-27", "resultado": "ok", "numero": "257"}))
    paginas = {bocm.url_completo(date(2026, 10, 28), 258): (F / "bocm_completo_20261028_258.html").read_bytes(),
               bocm.url_completo(date(2026, 10, 29), 260): (F / "bocm_completo_20261029_260.html").read_bytes(),
               bocm.url_completo(date(2026, 10, 28), 259): (F / "bocm_completo_20261028_258.html").read_bytes()
               .replace(b"BOCM - N\xc2\xba 258", b"BOCM - N\xc2\xba 259")}
    monkeypatch.setattr(bocm, "obtener", _servidor(paginas))
    archivo = bocm.Archivo(tmp_path / "archivo")
    inf = bocm.procesar_dia(date(2026, 10, 28), tmp_path, archivo)
    assert inf["resultado"] == "ok" and inf["numero"] == "258"
    (dias / "28.json").write_text(json.dumps(inf))
    inf = bocm.procesar_dia(date(2026, 10, 29), tmp_path, archivo)
    assert inf["numero"] == "260" and inf["extraordinarios"] == [{"numero": 259, "fecha": "2026-10-28", "resultado": "ok"}]
    assert (dias / "28-259.json").exists()
    assert (tmp_path / "datos/autonomicos/bocm/disposiciones/2026/10/28-259.jsonl").exists()


def test_domingo_sin_peticiones(tmp_path, monkeypatch):
    monkeypatch.setattr(bocm, "obtener", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debe pedir")))
    dias = tmp_path / "datos/autonomicos/bocm/dias/2026/10"
    dias.mkdir(parents=True)
    (dias / "24.json").write_text(json.dumps({"fecha": "2026-10-24", "resultado": "ok", "numero": "255"}))
    inf = bocm.procesar_dia(date(2026, 10, 25), tmp_path, bocm.Archivo(tmp_path / "archivo"))
    assert inf["resultado"] == "sin_boletin" and inf["alertas"] == []


def test_texto_disposicion_real():
    d = bocm.texto_disposicion((F / "bocm_disposicion_72.xml").read_bytes())
    assert "13 de noviembre de 2026" in d["texto"]
    assert "Oferta de Empleo Público del Ayuntamiento de Alcobendas del año 2024" in d["texto"]


def test_huecos_no_se_buscan_cada_dia(tmp_path, monkeypatch):
    """Un número que falta y no aparece no se vuelve a buscar en 30 días, y entre petición y petición hay pausa."""
    import json
    from datetime import date
    from motor.archivo import Archivo
    from motor.autonomicos import bocm
    for d, n in (("2026-10-05", 190), ("2026-10-07", 192)):
        r = tmp_path / "datos" / "autonomicos" / "bocm" / "dias" / "2026" / "10" / f"{d[-2:]}.json"
        r.parent.mkdir(parents=True, exist_ok=True)
        r.write_text(json.dumps({"fecha": d, "resultado": "ok", "numero": str(n)}))
    pedidas, pausas = [], []
    monkeypatch.setattr(bocm, "leer_boletin", lambda d, n, *a, **k: pedidas.append((d, n)))
    monkeypatch.setattr(bocm.time, "sleep", lambda s: pausas.append(s))
    a = Archivo(tmp_path / "a", solo_huella=True)
    res = bocm.rellenar_huecos(tmp_path, a, hoy=date(2026, 10, 31))
    assert res == [{"numero": 191, "fecha": None, "resultado": "no_encontrado"}] and len(pedidas) == 3 == len(pausas)
    assert bocm.rellenar_huecos(tmp_path, a, hoy=date(2026, 11, 10)) == [] and len(pedidas) == 3
    assert len(bocm.rellenar_huecos(tmp_path, a, hoy=date(2026, 12, 1))) == 1 and len(pedidas) == 6


def test_numero_del_boletin_recuperado_por_los_huecos(tmp_path):
    import json as _json
    from datetime import date as _date
    from motor.autonomicos import bocm as b
    dia = b._ruta(tmp_path, "dias", _date(2026, 7, 15), "json")
    dia.parent.mkdir(parents=True)
    dia.write_text(_json.dumps({"fecha": "2026-07-15", "resultado": "error_formato", "alertas": []}))
    (dia.parent / "15-167.json").write_text(_json.dumps({"fecha": "2026-07-15", "resultado": "ok", "numero": "167",
                                                         "extraordinario": True}))
    assert b.numeros_leidos(tmp_path, _date(2026, 7, 15)) == [167]
    assert b.ultimo_numero(tmp_path, _date(2026, 7, 16)) == (167, _date(2026, 7, 15))
