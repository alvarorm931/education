"""Números y fechas escritos en castellano en los textos oficiales («veinte días», «3 de octubre de 2026»)."""

from __future__ import annotations

from datetime import date

from motor.boe.clasificar import normalizar

MESES = {m: i for i, m in enumerate(
    ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
     "noviembre", "diciembre"], start=1)}
UNIDADES = {
    "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
    "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiun": 21,
    "veintiuna": 21, "veintiuno": 21, "veintidos": 22, "veintitres": 23, "veinticuatro": 24,
    "veinticinco": 25, "veintiseis": 26, "veintisiete": 27, "veintiocho": 28, "veintinueve": 29,
    "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80,
    "noventa": 90, "cien": 100, "ciento": 100, "doscientas": 200, "doscientos": 200, "trescientas": 300,
    "trescientos": 300,
}


def numero(texto: str) -> int | None:
    t = normalizar(texto)
    if t.isdigit():
        return int(t)
    total = 0
    for parte in t.replace(" y ", " ").split():
        if parte not in UNIDADES:
            return None
        total += UNIDADES[parte]
    return total or None


def fecha_texto(dia: str, mes: str, anio: str) -> str | None:
    m = MESES.get(normalizar(mes))
    try:
        return date(int(anio), m, int(dia)).isoformat() if m else None
    except ValueError:
        return None
