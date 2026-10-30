"""Festivos de cada comunidad desde la relación anual de fiestas laborales del BOE (formato de 2022 a 2027)."""

from datetime import date

from motor import calendario
from motor.mantenimiento.festivos import festivos_de_resolucion

COMUNIDADES = ["Andalucía", "Aragón", "Asturias", "Illes Balears", "Canarias (1)", "Cantabria", "Castilla-La Mancha",
               "Castilla y León", "Cataluña (2)", "Extremadura", "Galicia", "Com. Madrid", "Región Murcia",
               "C. Foral Navarra", "País Vasco", "La Rioja", "Comunitat Valenciana", "Ciudad de Ceuta", "Ciudad de Melilla"]


def test_tabla_del_boe():
    tabla = [["Fecha de las fiestas", "Comunidades Autónomas"], COMUNIDADES, ["Enero"] + [""] * 19,
             ["1 Año Nuevo."] + ["*"] * 19, ["Febrero"] + [""] * 19, ["28 Día de Andalucía.", "***"] + [""] * 18,
             ["Marzo"] + [""] * 19, ["19 San José."] + [""] * 10 + ["**", "", "**"] + [""] * 6]
    r = festivos_de_resolucion({"identificador": "BOE-A-2025-21667", "url": "https://www.boe.es/x", "capturado": "c",
                                "titulo": "Resolución de 17 de octubre de 2025, de la Dirección General de Trabajo, por "
                                          "la que se publica la relación de fiestas laborales para el año 2026.",
                                "tablas": [{"filas": 8, "contenido": tabla}]})
    assert r["anio"] == 2026 and r["fuente"] == "BOE-A-2025-21667"
    assert [x["fecha"] for x in r["comunidades"]["01"]] == ["2026-01-01", "2026-02-28"]
    assert [x["fecha"] for x in r["comunidades"]["12"]] == ["2026-01-01", "2026-03-19"]  # Galicia
    assert [x["fecha"] for x in r["comunidades"]["13"]] == ["2026-01-01"]  # Madrid


def test_plazo_con_festivos_de_la_comunidad():
    # 2026: el 2 de noviembre es festivo en Madrid (Todos los Santos cae en domingo), no en Cataluña
    assert not calendario.es_habil(date(2026, 11, 2), "13") and calendario.es_habil(date(2026, 11, 2), "09")
    assert calendario.es_habil(date(2026, 11, 2))  # sin comunidad, solo los nacionales
    assert calendario.fin_de_plazo(date(2026, 10, 29), 2, "habiles", "13") == date(2026, 11, 3)
    assert calendario.fin_de_plazo(date(2026, 10, 29), 2, "habiles", "09") == date(2026, 11, 2)
    assert calendario.etiqueta(date(2026, 10, 29), "13").startswith("festivos de Comunidad de Madrid")
    assert calendario.etiqueta(date(2030, 1, 1), "13") == "festivos nacionales (estimado)"
