"""Cómputo de plazos administrativos (Ley 39/2015, art. 30).

Con la comunidad autónoma, se usan sus festivos de la relación anual de fiestas laborales del BOE
(motor/catalogo/datos/festivos.json, motor/mantenimiento/festivos.py); sin ella, o para un año que aún no está, los
nacionales. Los festivos locales no se conocen: el resultado sigue siendo una fecha ESTIMADA.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _festivos_boe() -> dict[str, dict[str, frozenset[date]]]:
    try:
        datos = json.loads((Path(__file__).parent / "catalogo" / "datos" / "festivos.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {anio: {c: frozenset(date.fromisoformat(x["fecha"]) for x in v) for c, v in a["comunidades"].items()}
            for anio, a in datos.get("anios", {}).items()}


def hay_festivos_de(anio: int, comunidad: str | None) -> bool:
    return bool(comunidad) and comunidad in _festivos_boe().get(str(anio), {})


def domingo_de_pascua(anio: int) -> date:
    """Algoritmo anónimo gregoriano (Meeus/Jones/Butcher)."""
    a, b, c = anio % 19, anio // 100, anio % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(anio, mes, dia)


def festivos_nacionales(anio: int) -> set[date]:
    fijos = [(1, 1), (1, 6), (5, 1), (8, 15), (10, 12), (11, 1), (12, 6), (12, 8), (12, 25)]
    dias = {date(anio, m, d) for m, d in fijos}
    dias.add(domingo_de_pascua(anio) - timedelta(days=2))  # Viernes Santo
    return dias


def festivos(anio: int, comunidad: str | None = None) -> set[date] | frozenset[date]:
    """Festivos de la comunidad (código INE, «13» Madrid) ese año; sin comunidad o sin datos, los nacionales."""
    if hay_festivos_de(anio, comunidad):
        return _festivos_boe()[str(anio)][comunidad]
    return festivos_nacionales(anio)


def es_habil(d: date, comunidad: str | None = None) -> bool:
    return d.weekday() < 5 and d not in festivos(d.year, comunidad)


def fin_de_plazo(publicacion: date, dias: int, tipo: str, comunidad: str | None = None) -> date:
    """Plazo que empieza el día siguiente a la publicación.

    tipo 'habiles': se cuentan solo días hábiles (sin sábados, domingos ni festivos).
    tipo 'naturales': se cuentan todos; si el último es inhábil, pasa al primer hábil siguiente (art. 30.5).
    """
    d = publicacion
    if tipo == "habiles":
        contados = 0
        while contados < dias:
            d += timedelta(days=1)
            if es_habil(d, comunidad):
                contados += 1
        return d
    d = publicacion + timedelta(days=dias)
    while not es_habil(d, comunidad):
        d += timedelta(days=1)
    return d


def fin_de_plazo_meses(publicacion: date, meses: int, comunidad: str | None = None) -> date:
    """Plazo en meses (art. 30.4): termina el mismo día de la publicación en el mes de vencimiento; si ese mes no
    tiene ese día, el último día del mes. Si el último día es inhábil, pasa al primer hábil siguiente (art. 30.5)."""
    import calendar

    total = publicacion.month - 1 + meses
    anio, mes = publicacion.year + total // 12, total % 12 + 1
    d = date(anio, mes, min(publicacion.day, calendar.monthrange(anio, mes)[1]))
    while not es_habil(d, comunidad):
        d += timedelta(days=1)
    return d


def etiqueta(publicacion: date, comunidad: str | None) -> str:
    """Qué calendario se ha usado, para que la fecha se publique como estimada y diga por qué."""
    if hay_festivos_de(publicacion.year, comunidad):
        from motor.catalogo.territorio import COMUNIDADES
        return f"festivos de {COMUNIDADES.get(comunidad, comunidad)} (BOE; sin los locales, estimado)"
    return "festivos nacionales (estimado)"
