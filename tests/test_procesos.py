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
                                  "por_puesto": {"auxiliar-administrativo": 3}}
