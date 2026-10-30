"""Bonificaciones y gratuidad que cambian el precio real de un grado en universidad pública, por comunidad.

Datos de docs/fuentes-precios-grado.md (normas de 2026-2027 leídas el 30/10/2026). Solo entran las que están en una
norma abierta y leída; las que solo se han visto en prensa (Cantabria) quedan fuera hasta verificarlas. Cada una
lleva su norma y artículo para citarla en la ficha, y la condición tal como la fija la norma (resumida, sin copiar
su texto).
"""

from __future__ import annotations

BONIFICACIONES = {
    "Andalucía": {
        "que": "99 % del precio de los créditos aprobados en primera matrícula el curso anterior (desde segundo curso)",
        "condicion": "créditos aprobados en primera matrícula en una universidad pública andaluza; no cuenta lo que ya "
                     "cubre otra beca ni los créditos reconocidos",
        "norma": "Decreto 98/2023 (BOJA 84, 5-5-2023), art. 12", "curso": "2026-2027"},
    "Extremadura": {
        "que": "99 % del precio de los créditos aprobados en primera matrícula en 2025-2026",
        "condicion": "créditos aprobados en la Universidad de Extremadura; solo el primer grado; no cubre lo que ya paga "
                     "la beca del Ministerio",
        "norma": "Decreto 145/2026 (DOE 138, 20-7-2026), art. 19", "curso": "2026-2027"},
    "Galicia": {
        "que": "99 %, sin requisito de renta: al nuevo ingreso, de todos los créditos matriculados; después, de los "
               "aprobados en primera matrícula el curso anterior",
        "condicion": "en continuidad, un porcentaje mínimo de créditos aprobados según la rama",
        "norma": "Decreto 72/2026 (DOG 127, 9-7-2026), art. 13", "curso": "2026-2027"},
    "Castilla - La Mancha": {
        "que": "99 % de los créditos de primera matrícula de primer curso (hasta 60; 72 en doble grado)",
        "condicion": "acceso en Castilla-La Mancha o título equivalente obtenido allí; hay que pedir la beca del Ministerio",
        "norma": "Orden 74/2026 (DOCM 99, 27-5-2026), art. 13", "curso": "2026-2027"},
    "Rioja (La)": {
        "que": "100 % de los créditos de primera matrícula (en 2026-2027, de primero a tercero; desde 2027-2028, todos)",
        "condicion": "de 17 a 35 años, dos años empadronado sin interrupción y sin un título igual o superior",
        "norma": "Ley 3/2026 de La Rioja (BOR 125, 3-7-2026)", "curso": "2026-2027"},
    "Asturias (Principado de)": {
        "que": "exención de los créditos de primera matrícula del nuevo ingreso y, en continuidad, según lo aprobado",
        "condicion": "haber pedido la beca general o declarar que no se cumplen sus requisitos económicos; sin título "
                     "previo; en continuidad, porcentaje mínimo aprobado por rama",
        "norma": "Decreto 45/2026 (BOPA 121, 25-6-2026), arts. 18 y 19", "curso": "2026-2027"},
    "Balears (Illes)": {
        "que": "100 % de la primera matrícula",
        "condicion": "renta por debajo del umbral y rendimiento (nota de acceso o aprobados) a la vez; al menos 48 "
                     "créditos; no ser becario del Ministerio",
        "norma": "Acuerdo del Consell de Govern de 3-7-2026 (BOIB 84, 4-7-2026), anexo 5", "curso": "2026-2027"},
}
# Ayudas que no rebajan el precio pero devuelven lo pagado (se muestran aparte, como ayuda)
AYUDAS = {
    "Castilla y León": {
        "que": "ayuda de hasta lo pagado por la primera matrícula de primer curso de grado",
        "condicion": "empadronamiento en Castilla y León y primera vez en la universidad; concurrencia ordenada por nota",
        "norma": "Orden IEM/621/2026 (BOCYL 131, 9-7-2026)", "curso": "2026-2027"},
}


def de_comunidad(comunidad: str | None) -> dict | None:
    """Bonificación o ayuda de la comunidad de la universidad (nombres como en el catálogo SIIU)."""
    if not comunidad:
        return None
    if comunidad in BONIFICACIONES:
        return {"tipo": "bonificacion", **BONIFICACIONES[comunidad]}
    if comunidad in AYUDAS:
        return {"tipo": "ayuda", **AYUDAS[comunidad]}
    return None
