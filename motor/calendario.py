"""Cómputo de plazos administrativos (Ley 39/2015, art. 30).

Por ahora solo con festivos nacionales: el resultado es una fecha ESTIMADA. Los festivos autonómicos
y locales se añadirán desde las resoluciones anuales de días inhábiles.
"""

from __future__ import annotations

from datetime import date, timedelta


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


def es_habil(d: date) -> bool:
    return d.weekday() < 5 and d not in festivos_nacionales(d.year)


def fin_de_plazo(publicacion: date, dias: int, tipo: str) -> date:
    """Plazo que empieza el día siguiente a la publicación.

    tipo 'habiles': se cuentan solo días hábiles (sin sábados, domingos ni festivos).
    tipo 'naturales': se cuentan todos; si el último es inhábil, pasa al primer hábil siguiente (art. 30.5).
    """
    d = publicacion
    if tipo == "habiles":
        contados = 0
        while contados < dias:
            d += timedelta(days=1)
            if es_habil(d):
                contados += 1
        return d
    d = publicacion + timedelta(days=dias)
    while not es_habil(d):
        d += timedelta(days=1)
    return d


def fin_de_plazo_meses(publicacion: date, meses: int) -> date:
    """Plazo en meses (art. 30.4): termina el mismo día de la publicación en el mes de vencimiento; si ese mes no
    tiene ese día, el último día del mes. Si el último día es inhábil, pasa al primer hábil siguiente (art. 30.5)."""
    import calendar

    total = publicacion.month - 1 + meses
    anio, mes = publicacion.year + total // 12, total % 12 + 1
    d = date(anio, mes, min(publicacion.day, calendar.monthrange(anio, mes)[1]))
    while not es_habil(d):
        d += timedelta(days=1)
    return d
