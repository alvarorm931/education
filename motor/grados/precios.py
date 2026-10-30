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
# Comunidades con un solo precio del crédito en primera matrícula para todos sus grados (universidades públicas,
# centros propios). Se usa solo donde QEDU no da precio (sobre todo dobles grados); antes se contrastó con QEDU.
PRECIO_UNICO = {
    "Andalucía": {
        "precio_credito": 12.62, "curso": "2026-2027",
        "norma": "Decreto 98/2023 (BOJA 84, 5-5-2023): precio único de primera matrícula de grado; sigue vigente en "
                 "2026-2027 (disposición final primera)",
        "url": "https://oficinadeposgrado.uca.es/wp-content/uploads/2023/05/BOJA_84_23-de-mayo.pdf",
        "capturado": "2026-10-30",
        "contraste": "QEDU 2025-2026: 402 de las 403 ofertas con precio de centros propios de las públicas andaluzas "
                     "están a 12,62 €/crédito; la otra es un grado conjunto internacional"},
    "Cataluña": {
        "precio_credito": 17.69, "curso": "2026-2027",
        "norma": "Decreto 96/2026 (DOGC 9689, 18-6-2026): precio único de primera matrícula de grado",
        "url": "https://www.upf.edu/documents/d/graus/decret-preus-2026-27-pdf",
        "capturado": "2026-10-30",
        "contraste": "QEDU 2025-2026: las 348 ofertas con precio de centros propios de las siete públicas catalanas "
                     "están a 17,69 €/crédito"},
}
# Comunidades que fijan el precio del crédito por la rama del título: el precio de un grado (y el de un doble cuyos
# dos grados caen en el mismo precio) sale de la rama del SIIU. Contrastado con QEDU antes de usarlo.
PRECIO_POR_RAMA = {
    "Galicia": {
        "precios": {"Ciencias": 13.93, "Ciencias de la Salud": 13.93, "Ingeniería y Arquitectura": 13.93,
                    "Artes y Humanidades": 9.85, "Ciencias Sociales y Jurídicas": 9.85},
        "por_nombre": {"bellas artes": 13.93},  # epígrafe A: Ciencias, Salud, Ingeniería y Arquitectura y Bellas Artes
        "curso": "2026-2027",
        "norma": "Decreto 72/2026 (DOG 127, 9-7-2026): epígrafe A (Ciencias, Ciencias de la Salud, Ingeniería y "
                 "Arquitectura y Bellas Artes) y epígrafe B (el resto)",
        "url": "https://www.xunta.gal/dog/Publicados/2026/20260709/AnuncioG0761-010726-0001_gl.html",
        "capturado": "2026-10-30",
        "contraste": "QEDU 2025-2026: las 140 ofertas con precio de centros propios de las públicas gallegas cuadran "
                     "con su rama (Bellas Artes, en el epígrafe A)"},
    "Cantabria": {
        "precios": {"Ciencias de la Salud": 15.56, "Ingeniería y Arquitectura": 14.54, "Ciencias": 12.22,
                    "Ciencias Sociales y Jurídicas": 10.78, "Artes y Humanidades": 9.95},
        "por_nombre": {},
        "curso": "2026-2027",
        "norma": "Orden UIC/10/2023 (BOC 110, 8-6-2023), prorrogada: precio por rama; tabla de grado 2026-2027 de la "
                 "Universidad de Cantabria",
        "url": "https://web.unican.es/estudiantesuc/Documents/Precios%20P%c3%bablicos/Precios%20Grado%202026-2027.pdf",
        "capturado": "2026-10-30",
        "contraste": "QEDU 2025-2026: las 26 ofertas con precio de centros propios de la Universidad de Cantabria "
                     "cuadran con su rama"},
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


def precio_unico(comunidad: str | None) -> dict | None:
    """Precio único del crédito de grado en primera matrícula de la comunidad, con su norma (o None si la comunidad
    fija varios niveles: entonces depende del título y no se deduce)."""
    return dict(PRECIO_UNICO[comunidad]) if comunidad in PRECIO_UNICO else None


def _sin_acentos(texto: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def precio_por_rama(comunidad: str | None, titulos: list[tuple[str | None, str]]) -> dict | None:
    """Precio del crédito por la rama de cada título (rama del SIIU, nombre): el del grado o, en un doble, el de
    sus dos grados si es el mismo. Si falta una rama o los precios difieren, None (no se deduce)."""
    regla = PRECIO_POR_RAMA.get(comunidad or "")
    if not regla or not titulos:
        return None
    precios = set()
    for rama, nombre in titulos:
        p = next((v for k, v in regla["por_nombre"].items() if k in _sin_acentos(nombre or "")), None) \
            or regla["precios"].get(rama or "")
        if p is None:
            return None
        precios.add(p)
    if len(precios) != 1:
        return None
    return {"precio_credito": precios.pop(), **{k: regla[k] for k in ("curso", "norma", "url", "capturado", "contraste")}}
