"""Números y fechas escritos en los textos oficiales («veinte días», «3 de octubre de 2026»).

Castellano y, para los boletines que publican en otras lenguas oficiales, catalán/valenciano («vint dies»,
«21 d'octubre») y gallego («vinte días», «xuño»). Las palabras se comparan sin tildes (normalizar).
"""

from __future__ import annotations

from datetime import date

from motor.boe.clasificar import normalizar

MESES = {m: i for i, m in enumerate(
    ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
     "noviembre", "diciembre"], start=1)}
MESES.update({m: i for i, m in enumerate(  # catalán y valenciano
    ["gener", "febrer", "marc", "abril", "maig", "juny", "juliol", "agost", "setembre", "octubre", "novembre",
     "desembre"], start=1)})
MESES.update({m: i for i, m in enumerate(  # gallego
    ["xaneiro", "febreiro", "marzo", "abril", "maio", "xuno", "xullo", "agosto", "setembro", "outubro", "novembro",
     "decembro"], start=1)})
MESES["setiembre"] = 9
UNIDADES = {
    "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
    "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiun": 21,
    "veintiuna": 21, "veintiuno": 21, "veintidos": 22, "veintitres": 23, "veinticuatro": 24,
    "veinticinco": 25, "veintiseis": 26, "veintisiete": 27, "veintiocho": 28, "veintinueve": 29,
    "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80,
    "noventa": 90, "cien": 100, "ciento": 100, "doscientas": 200, "doscientos": 200, "trescientas": 300,
    "trescientos": 300,
    # catalán y valenciano
    "dues": 2, "quatre": 4, "cinc": 5, "sis": 6, "set": 7, "vuit": 8, "huit": 8, "nou": 9, "deu": 10,
    "onze": 11, "dotze": 12, "tretze": 13, "catorze": 14, "quinze": 15, "setze": 16, "disset": 17, "desset": 17,
    "divuit": 18, "devuit": 18, "dinou": 19, "denou": 19, "vint": 20, "trenta": 30, "quaranta": 40,
    "cinquanta": 50, "seixanta": 60, "noranta": 90, "cent": 100,
    # gallego
    "unha": 1, "dous": 2, "duas": 2, "catro": 4, "sete": 7, "oito": 8, "nove": 9, "dez": 10, "dezaseis": 16,
    "dezasete": 17, "dezaoito": 18, "dezanove": 19, "vinte": 20, "trinta": 30, "corenta": 40,
}


def numero(texto: str) -> int | None:
    t = normalizar(texto)
    if t.isdigit():
        return int(t)
    total = 0
    # «veintidós», «vint-i-un», «vinte e un», «treinta y uno»
    t = t.replace("-i-", " ").replace("-", " ")
    for parte in t.replace(" y ", " ").replace(" i ", " ").replace(" e ", " ").split():
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
