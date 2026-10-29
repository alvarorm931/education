from datetime import date

from motor.procesos import construir, resumen


def _acto(i, fecha, tipo, **kw):
    return {"id": i, "fecha": fecha, "tipo_acto": tipo, "ambito": "local", "alcance": "acceso", **kw}


def test_estados_y_enlaces():
    actos = [
        _acto("A1", "2026-10-20", "apertura_plazo", convocante={"tipo": "Ayuntamiento", "nombre": "Mijas", "provincia": "Málaga"},
              plazas=[{"numero": 3, "puesto_clave": "auxiliar-administrativo"}], total_plazas=3,
              plazo={"dias": 20, "tipo": "habiles", "fin_estimado": "2026-11-17"}),
        _acto("A2", "2026-09-01", "apertura_plazo", convocante={"tipo": "Ayuntamiento", "nombre": "Ourense", "provincia": None},
              total_plazas=1, plazo={"dias": 10, "tipo": "habiles", "fin_estimado": "2026-09-15"}),
        _acto("A3", "2026-10-01", "apertura_plazo", total_plazas=2, plazo={"fin_estimado": "2026-11-30"}),
        _acto("C1", "2026-10-25", "correccion", refiere_a=["A1"]),
        _acto("N1", "2026-10-26", "anulacion", refiere_a=["A3"]),
        _acto("P1", "2026-10-01", "apertura_plazo", alcance="promocion_interna", plazo={"fin_estimado": "2026-12-01"}),
    ]
    ps = {p["id"]: p for p in construir(actos, date(2026, 10, 29))}
    assert set(ps) == {"boe:A1", "boe:A2", "boe:A3"}  # la promoción interna no crea proceso público
    assert ps["boe:A1"]["estado"] == "plazo_abierto" and [a["id"] for a in ps["boe:A1"]["actos"]] == ["A1", "C1"]
    assert ps["boe:A1"]["actualizado"] == "2026-10-25"
    assert ps["boe:A2"]["estado"] == "plazo_cerrado" and ps["boe:A2"]["provincia"] == "Ourense"
    assert ps["boe:A3"]["estado"] == "anulado"
    r = resumen(list(ps.values()), date(2026, 10, 29))
    assert r["plazo_abierto"] == {"procesos": 1, "plazas": 3, "por_provincia": {"Málaga": 3},
                                  "por_puesto": {"auxiliar-administrativo": 3}, "por_fuente": {"BOE": 1}}


def test_boe_y_boletines_autonomicos():
    titulo = ("Resolución de 5 de octubre de 2026, de la Universidad de Granada, por la que se convoca proceso selectivo "
              "para ingreso en la Escala Auxiliar Administrativa.")
    boe = [
        # La universidad publica en el BOJA y el plazo cuenta desde allí: el BOE no da fecha de fin
        _acto("U1", "2026-10-12", "convocatoria", ambito="universidad", titulo=titulo,
              plazo={"dias": 20, "tipo": "habiles", "cuenta_desde": "Boletín Oficial de la Junta de Andalucía"}),
        # Anuncio local del BOE que cita las bases íntegras publicadas en el BOCYL
        _acto("L1", "2026-10-20", "apertura_plazo", convocante={"tipo": "Ayuntamiento", "nombre": "Miranda de Ebro",
                                                               "provincia": "Burgos"},
              boletines_citados=[{"boletin": "Boletín Oficial de Castilla y León", "numero": "189",
                                  "fecha": "2026-10-02", "papel": "bases"}],
              plazo={"dias": 20, "tipo": "naturales", "fin_estimado": "2026-11-09"}),
    ]
    autonomicos = [
        {"id": "boja:1", "fecha": "2026-10-08", "fuente": "BOJA", "tipo_acto": "convocatoria", "ambito": "universidad",
         "alcance": "acceso", "titulo": titulo.upper(), "tiene_texto": True,
         "plazo": {"dias": 20, "tipo": "habiles", "fin_estimado": "2026-11-05"}},
        {"id": "bocyl:B1", "fecha": "2026-10-02", "fuente": "BOCYL", "tipo_acto": "convocatoria", "ambito": "local",
         "alcance": "acceso", "titulo": "ACUERDO ... bases ...", "convocante": {"nombre": "Miranda de Ebro"}},
        # Convocatoria autonómica que no sale en el BOE: proceso propio
        {"id": "dogv:9", "fecha": "2026-10-27", "fuente": "DOGV", "tipo_acto": "convocatoria", "ambito": "autonomico",
         "alcance": "acceso", "titulo": "RESOLUCIÓN ... por la que se convocan pruebas selectivas",
         "plazo": {"dias": 20, "tipo": "habiles", "fin_estimado": "2026-11-24"}},
    ]
    ps = {p["id"]: p for p in construir(boe, date(2026, 10, 29), autonomicos)}
    assert set(ps) == {"boe:U1", "boe:L1", "dogv:9"}
    u = ps["boe:U1"]
    assert u["estado"] == "plazo_abierto" and u["plazo"]["de_acto"] == "boja:1" and u["fuentes"] == ["BOE", "BOJA"]
    assert [x["id"] for x in ps["boe:L1"]["otras_publicaciones"]] == ["bocyl:B1"]
    assert ps["dogv:9"]["fuente"] == "Diari Oficial de la Generalitat Valenciana"
