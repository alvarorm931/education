import json
from datetime import date

from motor.estudios import conjunto_masters, diario_masters, extraer, fichas_masters, qedu_masters


def test_reparto_en_siete_dias_estable():
    urls = [f"https://u{i}.es/m" for i in range(700)]
    dias = [sum(diario_masters.del_dia(u, d) for u in urls) for d in range(7)]
    assert sum(dias) == 700 and min(dias) > 60
    assert all(diario_masters.del_dia(u, 3) == diario_masters.del_dia(u, 10) for u in urls)


def test_pasada_del_dia(tmp_path, monkeypatch):
    raiz = tmp_path / "entrada"
    ext = raiz / "20261030T0000" / "datos" / "estudios" / "extraccion" / "x"
    ext.mkdir(parents=True)
    urls = [f"https://u{i}.es/m" for i in range(40)]
    ext.joinpath("paginas_extraidas.jsonl").write_text("".join(json.dumps(
        {"url": u, "extraido": "2026-10-30T01:00:00+00:00", "grupo": "no_oficial", "proveedor": "p",
         "no_es_programa": i == 0}) + "\n" for i, u in enumerate(urls)))
    (raiz / "masters-estado").mkdir(parents=True)
    (raiz / "cat.json").write_text("[]")
    (raiz / "masters-estado" / "manifiesto.json").write_text(json.dumps(
        {"catalogo": "cat.json", "extracciones": ["20261030T0000"], "ruct": [], "qedu": []}))
    llamadas = {}

    def lote(muestra, salida, **kw):
        llamadas["lote"] = [json.loads(l)["url"] for l in muestra.read_text().split("\n") if l]
        llamadas["navegador"] = kw.get("navegador")
        (salida).mkdir(parents=True)
        return {"enviadas": 1}

    monkeypatch.setattr(extraer, "lote", lote)
    monkeypatch.setattr(extraer, "huellas_previas", lambda c: {})
    monkeypatch.setattr(qedu_masters, "tarjetas", lambda r: (_ for _ in ()).throw(ConnectionError("QEDU caído")))

    def fichas(ext, salida, *a):
        llamadas["fichas"] = [str(x) for x in ext]
        (salida / "datos").mkdir(parents=True)
        (salida / "datos" / "fichas.jsonl").write_text("")
        return {}

    monkeypatch.setattr(fichas_masters, "ejecutar", fichas)
    monkeypatch.setattr(conjunto_masters, "ejecutar", lambda *a, **k: llamadas.setdefault("conjunto", a) and {"oficiales": 0})
    res = diario_masters.ejecutar(raiz, tmp_path / "out", 2, "SELLO", hoy=date(2026, 10, 31))
    esperadas = sorted(u for i, u in enumerate(urls) if i > 0 and diario_masters.del_dia(u, 2))
    assert llamadas["lote"] == esperadas and llamadas["navegador"]
    assert res["qedu_error"].startswith("ConnectionError") and "ruct" not in res  # el RUCT diario aún no
    assert any(x.endswith("SELLO") for x in llamadas["fichas"])
    m = json.loads((tmp_path / "out" / "masters-estado" / "manifiesto.json").read_text())
    assert "extracciones" not in m and m["actualizado"] == "SELLO" and m["catalogo"] == "cat.json"


def test_carpetas_por_su_forma_en_la_rama():
    arbol = ["20261030T103924/datos/estudios/extraccion/retomado_x/hechos.jsonl",
             "20261030T000449/datos/estudios/extraccion/lote.json",
             "20261030T111924-t0/datos/estudios/masters/ruct/4310193.json",
             "20261030T111924-t0/datos/estudios/masters/ruct/resumen-ficha-1.json",
             "20261031T010000-t3/datos/estudios/masters/ruct_memoria/3500004.json",
             "20261030T112546-t0/datos/estudios/masters/qedu/qedu_detalles_master_0_950.jsonl",
             "20261030T150000/datos/estudios/masters/boe_planes_masters.jsonl",
             "20261030T160000-t0/datos/estudios/masters/guias/tramo_0/guias.jsonl",
             "masters-estado/conjunto/resumen.json"]
    cs = diario_masters.carpetas_en_arbol(arbol, "20261030T1000")
    assert cs == {"extracciones": ["20261030T103924"], "ruct": ["20261030T111924-t0", "20261031T010000-t3"],
                  "qedu": ["20261030T112546-t0"], "boe": ["20261030T150000"], "guias": ["20261030T160000-t0"]}
    r = diario_masters.rutas_a_traer({"catalogo": "masters-estado/cat.json"}, cs)
    assert "20261031T010000-t3/datos/estudios/masters/ruct_memoria" in r and r[0] == "masters-estado"
    # el RUCT de antes del sello general, con el suyo; las extracciones de antes, no
    arbol.append("20261029T175722/datos/estudios/masters/ruct_memoria/4310001.json")
    cs = diario_masters.carpetas_en_arbol(arbol, "20261030T1000", {"ruct": "20261029T1700"})
    assert cs["ruct"][0] == "20261029T175722" and cs["extracciones"] == ["20261030T103924"]


def test_pasada_del_dia_baja_los_planes_del_boe_de_las_fichas(tmp_path, monkeypatch):
    from motor.estudios import boe_planes_masters

    raiz = tmp_path / "entrada"
    r = raiz / "20261030T120000-t0" / "datos" / "estudios" / "masters" / "ruct"
    r.mkdir(parents=True)
    for c, i in (("4310001", "BOE-A-2011-1"), ("4310002", "BOE-A-2012-2")):
        (r / f"{c}.json").write_text(json.dumps({"codigo": c, "boe": {"plan": {"identificador": i}}}))
    (raiz / "masters-estado").mkdir(parents=True)
    (raiz / "cat.json").write_text("[]")
    (raiz / "boe_descargados.txt").write_text("BOE-A-2011-1\n")
    (raiz / "masters-estado" / "manifiesto.json").write_text(json.dumps(
        {"catalogo": "cat.json", "extracciones": [], "ruct": ["20261030T120000-t0"], "qedu": []}))
    pedidos = {}

    def textos(ruct, salida, desde, hasta, minutos, ya=None, por_nombre=None):
        pedidos["ids"] = sorted(set(boe_planes_masters.ids_de_ruct(ruct)) - set(ya or ()))
        (salida / "datos" / "boe" / "textos").mkdir(parents=True)
        return {"descargados": 1}

    monkeypatch.setattr(boe_planes_masters, "cmd_textos", textos)
    monkeypatch.setattr(boe_planes_masters, "cmd_medir", lambda *a, **k: {"documentos": 1})
    monkeypatch.setattr(extraer, "huellas_previas", lambda c: {})
    monkeypatch.setattr(qedu_masters, "tarjetas", lambda r: (_ for _ in ()).throw(ConnectionError("x")))

    def fichas(ext, salida, *a):
        (salida / "datos").mkdir(parents=True)
        (salida / "datos" / "fichas.jsonl").write_text("")
        return {}

    monkeypatch.setattr(fichas_masters, "ejecutar", fichas)
    visto = {}
    monkeypatch.setattr(conjunto_masters, "ejecutar", lambda *a, **k: visto.setdefault("boe", k.get("boe")) and {})
    res = diario_masters.ejecutar(raiz, tmp_path / "out", 2, "SELLO", hoy=date(2026, 10, 31))
    assert pedidos["ids"] == ["BOE-A-2012-2"] and res["boe_pendientes"] == 1
    assert any(str(x).endswith("SELLO") for x in visto["boe"])
