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
# Precio del crédito de un doble grado en comunidades donde depende del título: la regla de la norma aplicada a los
# precios de sus dos grados en la misma universidad (que da QEDU). «media»: media aritmética de los dos;
# «cada_asignatura»: cada asignatura paga el de su grado (solo se deduce si los dos grados tienen el mismo precio).
REGLA_DOBLE = {
    "Madrid (Comunidad de)": {
        "regla": "media", "curso": "2026-2027",
        "norma": "Decreto 43/2022 (BOCM 155, 1-7-2022): en las dobles titulaciones con distinto nivel de "
                 "experimentalidad, la media aritmética del precio de los títulos que las componen, en todas las "
                 "asignaturas",
        "url": "https://www.urjc.es/i-d-i/centro-de-apoyo-tecnologico-cat-y-redlabu/485-precios-publicos",
        "capturado": "2026-10-30",
        "contraste": "La Universidad Autónoma de Madrid publica 18,80 €/crédito para los dobles de niveles 1 y 3 y "
                     "18,18 € para los de 2 y 3: la media exacta de 20,68 y 16,92 y de 19,43 y 16,92 "
                     "(https://uam.es/uam/media/doc/1606965874673/precios-para-estudiantes-extranjeros---ea.pdf)"},
}


# Reglas de las propias universidades cuando la norma de su comunidad no regula los dobles. «cada_asignatura»: cada
# asignatura paga el precio de su grado; «nivel_superior»: el del nivel superior (el reglamento no dice si es el de
# más precio). Con las dos solo se deduce un precio por crédito cuando los dos grados cuestan lo mismo.
REGLA_DOBLE_UNIVERSIDAD = {
    "Valladolid": {
        "regla": "cada_asignatura", "curso": "2026-2027",
        "norma": "Reglamento de programas de doble titulación oficial del mismo ciclo de la Universidad de "
                 "Valladolid (Consejo de Gobierno, 6-7-2021), art. 19.1: precios de cada una de las titulaciones que "
                 "lo componen, según las asignaturas matriculadas de cada una",
        "url": "https://secretariageneral.uva.es/wp-content/uploads/VII.22.-Reglamento-programas-doble-titulacion.pdf",
        "capturado": "2026-10-30"},
    "València (Estudi General)": {
        "regla": "nivel_superior", "curso": "2026-2027",
        "norma": "Reglament de programes de doble titulació de grau i màster oficial de la Universitat de València, "
                 "art. 6.6: a falta de regulación autonómica, los precios del nivel superior",
        "url": "https://www.uv.es/dretweb/Reglamentos/Reglamento%20programas%20doble%20titulacion.pdf",
        "capturado": "2026-10-30"},
}

# Dobles grados que la norma de precios de su comunidad pone en un nivel de experimentalidad propio (anexo de
# títulos): código del doble → (nivel, denominación literal del anexo). El cruce con el catálogo se hizo por los
# nombres de sus dos grados (sin acentos, mayúsculas ni palabras vacías) y se revisó a mano; Asturias ya trae el
# código en el anexo. Solo centros propios. Contraste: todos los precios por crédito que QEDU da a los grados de los
# centros propios de cada universidad son uno de los niveles de su norma.
ANEXO_DOBLE = {
    "Castilla - La Mancha": {
        "universidad": "Castilla-La Mancha", "curso": "2026-2027",
        "norma": "Orden 74/2026, de 19 de mayo, de la Consejería de Educación, Cultura y Deportes (DOCM 99, "
                 "27-5-2026): nivel de experimentalidad de cada título en el anexo I, precio del crédito en el II",
        "url": "https://www.cmmedia.es/uploads/files/2026/05/27/2026_3928.pdf", "capturado": "2026-10-30",
        "precios": {1: 12.13, 2: 14.58, 3: 17.64, 4: 18.87},
        "contraste": "QEDU 2025-2026: las 86 ofertas de grado de centros propios de la UCLM con precio "
                     "tienen uno de estos cuatro",
        "dobles": {
            "7000446": (1, "Doble Grado en Derecho y Economía"),
            "7000445": (1, "Doble Grado en Derecho y Administración y Dirección de Empresas"),
            "7000910": (1, "Doble Grado en Derecho y Estudios Internacionales"),
            "7000909": (1, "Doble Grado en Administración y Dirección de Empresas y Estudios Internacionales"),
            "7001093": (1, "Doble Grado en Administración y Dirección de Empresas y Turismo"),
            "7001262": (1, "Doble Grado en Historia y Geografía, Desarrollo Territorial y Sostenibilidad"),
            "7001261": (1, "Doble Grado en Historia e Historia del Arte"),
            "7000998": (2, "Doble Grado en Comunicación Audiovisual-Periodismo"),
            "7001068": (2, "Doble Grado en Maestro en Educación Primaria y Maestro en Educación Infantil"),
            "7001094": (4, "Doble Grado en Enfermería y Podología"),
            "7001428": (4, "Doble Grado en Ingeniería Agrícola y Agroalimentaria y Biotecnología"),
            "7001429": (4, "Doble Grado en Ingeniería Informática y Administración y Dirección de Empresas"),
            "7001444": (4, "Doble Grado en Ingeniería Química y Administración y Dirección de Empresas"),
        }},
    "Extremadura": {
        "universidad": "Extremadura", "curso": "2026-2027",
        "norma": "Decreto 145/2026, de 14 de julio (DOE 138, 20-7-2026): grado de experimentalidad de cada título "
                 "en el anexo I, precio del crédito en el III",
        "url": "https://doe.juntaex.es/pdfs/doe/2026/1380o/26040176.pdf", "capturado": "2026-10-30",
        "precios": {1: 17.74, 2: 16.13, 3: 15.04, 4: 11.82, 5: 9.88},
        "contraste": "QEDU 2025-2026: las 65 ofertas de grado de centros propios de la UEx con precio "
                     "tienen uno de estos cinco",
        "dobles": {
            "7000364": (2, "Ingeniería Telemática/ Ingeniería Informática en Tecnologías de la Información"),
            "7001077": (3, "Matemáticas/Estadística"),
            "7001393": (3, "Administración y Dirección de Empresas/Ingeniería Informática de Computadores"),
            "7001394": (3, "Administración y Dirección de Empresas/Ingeniería Informática del Software"),
            "7001475": (3, "Ingeniería en Tecnologías Industriales/Administración y Dirección de Empresas"),
            "7000062": (4, "Administración y Dirección de Empresas/Derecho"),
            "7000066": (4, "Derecho/Administración y Dirección de Empresa"),
            "7000063": (4, "Administración y Dirección de Empresas/Economía"),
            "7000065": (4, "Administración y Dirección de Empresas/Turismo"),
            "7000793": (4, "Criminología/Derecho"),
            "7000913": (4, "Periodismo/Comunicación Audiovisual"),
            "7000914": (4, "Periodismo/Información y Documentación"),
            "7000363": (4, "Comunicación Audiovisual/Información y Documentación"),
        }},
    "Balears (Illes)": {
        "universidad": "Illes Balears (Les)", "curso": "2026-2027",
        "norma": "Acuerdo del Consejo de Gobierno de las Illes Balears de 3 de julio de 2026 (BOIB 84, 4-7-2026), "
                 "anexo 2: precios de grado por nivel y títulos de cada nivel",
        "url": "https://intranet.caib.es/eboibfront/pdf/ca/2026/84/1223556", "capturado": "2026-10-30",
        "precios": {1: 11.18, 2: 13.40, 3: 15.63, 4: 17.85, 5: 20.08},
        "contraste": "QEDU 2025-2026: las 41 ofertas de grado de centros propios de la UIB con precio "
                     "tienen uno de estos cinco",
        "dobles": {
            "7000436": (2, "Doble titulació en Administració d'Empreses i Dret"),
            "7000602": (2, "Doble titulació en Administració d'Empreses i Turisme"),
            "7000603": (2, "Doble titulació en Economia i Turisme"),
            "7001195": (3, "Doble titulació en Educació Infantil i Educació Primària"),
            "7001269": (4, "Doble titulació en Matemàtiques i Enginyeria Informàtica"),
            "7000438": (4, "Doble titulació en Matemàtiques i Enginyeria Telemàtica"),
        }},
    "Aragón": {
        "universidad": "Zaragoza", "curso": "2026-2027",
        "norma": "Decreto 120/2026, de 24 de junio, del Gobierno de Aragón (BOA 122, 29-6-2026), anexo I",
        "url": "https://www.boa.aragon.es/cgi-bin/EBOA/BRSCGI?CMD=VEROBJ&MLKOB=1454833210505",
        "capturado": "2026-10-30",
        "precios": {1: 20.02, 2: 19.83, 3: 15.52, 4: 13.10},
        "contraste": "QEDU 2025-2026: las 58 ofertas de grado de centros propios de la Universidad de Zaragoza con "
                     "precio tienen uno de estos cuatro",
        "dobles": {
            "7000994": (1, "Nutrición Humana y Dietética + Ciencias de la Actividad Física y del Deporte"),
            "7000826": (2, "Física y Matemáticas"),
            "7000996": (2, "Ingeniería Mecatrónica + Ingeniería de Organización Industrial"),
            "7000995": (2, "Matemáticas + Ingeniería Informática"),
            "7001118": (2, "Ingeniería Informática + Administración y Dirección de Empresas"),
            "7000222": (3, "Derecho + Administración y Dirección de Empresas"),
        }},
    "Canarias": {
        "universidad": "Las Palmas de Gran Canaria", "curso": "2026-2027",
        "norma": "Decreto 177/2022, de 3 de agosto (BOC 159, 11-8-2022), anexos 1.º y 2.º; según su disposición "
                 "final primera sigue aplicándose en los cursos siguientes mientras no se modifique",
        "url": "https://www.ulpgc.es/sites/default/files/ArchivosULPGC/adm_efp/decreto_de_tasas_2022-2023.pdf",
        "capturado": "2026-10-30",
        "precios": {1: 14.59, 2: 12.63, 3: 10.16, 4: 9.47},
        "contraste": "QEDU 2025-2026: las 45 ofertas de grado de centros propios de la ULPGC con precio tienen "
                     "uno de estos cuatro; la Universidad de La Laguna lo cita como vigente (prorrogado) en agosto de "
                     "2026 (https://www.ull.es/portal/normativa/mementolosu/?n=1137&r=voz)",
        "dobles": {
            "7000795": (1, "Programa de Grados en Ingeniería en Organización Industrial y Administración y "
                           "Dirección de Empresas"),
            "7000794": (1, "Programa de Grados en Ingeniería en Tecnologías de la Telecomunicación y en "
                           "Administración y Dirección de Empresas"),
            "7000124": (1, "Programa de Grados en Ingeniería Informática y Administración y Dirección de Empresas"),
            "7000123": (3, "Programa de Grados en Administración y Dirección de Empresas y Derecho"),
            "7001031": (3, "Programa de Grados en Administración y Dirección de Empresas y Turismo"),
            "7000873": (3, "Programa de Grados en Traducción Interpretación (Inglés-Alemán) y Turismo"),
            "7000122": (3, "Programa de Grados en Traducción e Interpretación: Inglés-Francés e Inglés-Alemán"),
        }},
    "Asturias (Principado de)": {
        "universidad": "Oviedo", "curso": "2026-2027",
        "norma": "Decreto 45/2026, de 22 de junio, del Principado de Asturias, anexo I (los PCEO, con su código, "
                 "en el nivel de experimentalidad 2)",
        "url": "https://www.uniovi.es/documents/39158/14275702/Deccreto+de+Precios+P%C3%BAblicos+2026-2027.pdf/"
               "d93bfbb8-862b-51bb-e5a5-478fbe2d63de?t=1782390140771",
        "capturado": "2026-10-30",
        "precios": {1: 15.70, 2: 12.30, 3: 8.63},
        "contraste": "QEDU 2025-2026: las 53 ofertas de grado de centros propios de la Universidad de Oviedo con precio "
                     "tienen uno de estos tres",
        "dobles": {
            "7000393": (2, "PCEO/Doble Grado en Administración y Dirección de Empresas y Derecho"),
            "7000528": (2, "PCEO/Doble Grado Ingeniería Civil e Ingeniería de los Recursos Mineros y Energéticos"),
            "7001100": (2, "PCEO/Doble Grado en Matemáticas y Física (Opción A)"),
            "7001101": (2, "PCEO/Doble Grado en Matemáticas y Física (Opción B)"),
            "7001264": (2, "PCEO/Doble Grado en Ingeniería e Informática del Software y Matemáticas"),
            "7001265": (2, "PCEO/Doble Grado en Ingeniería en Tecnologías y Servicios de Telecomunicación/Grado en "
                           "Ciencia e Ingeniería de Datos"),
            "7001266": (2, "PCEO/Doble Grado en Ingeniería Informática en Tecnologías de la Información/Grado en "
                           "Ciencia e Ingeniería de Datos"),
            "7001387": (2, "PCEO/Doble Grado en Criminología/Grado en Derecho"),
            "7001442": (2, "PCEO/Doble Grado en Maestro en Educación Infantil/Grado en Maestro en Educación Primaria"),
            "7001443": (2, "PCEO/Doble Grado en Maestro en Maestro en Educación Primaria/Grado en Maestro en "
                           "Educación Infantil"),
        }},
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


def precio_doble(comunidad: str | None, precios_componentes: list[float | None], universidad: str | None = None,
                 codigo: str | None = None) -> dict | None:
    """Precio del crédito de un doble grado: el nivel que le da el anexo de la norma de su comunidad o, si no lo
    tiene, la regla de la norma (o de su universidad) aplicada a los precios de sus dos grados."""
    from decimal import ROUND_HALF_UP, Decimal

    anexo = ANEXO_DOBLE.get(comunidad or "")
    if anexo and anexo["universidad"] == universidad and codigo in anexo["dobles"]:
        nivel, denominacion = anexo["dobles"][codigo]
        return {"precio_credito": anexo["precios"][nivel], "regla": "nivel_del_anexo", "nivel": nivel,
                "denominacion_en_la_norma": denominacion,
                **{k: anexo[k] for k in ("curso", "norma", "url", "capturado", "contraste")}}
    regla = REGLA_DOBLE.get(comunidad or "") or REGLA_DOBLE_UNIVERSIDAD.get(universidad or "")
    if not regla or len(precios_componentes) < 2 or any(p is None for p in precios_componentes):
        return None
    if regla["regla"] == "media":
        media = sum(Decimal(str(p)) for p in precios_componentes) / len(precios_componentes)
        precio = float(media.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    elif regla["regla"] in ("cada_asignatura", "nivel_superior") and len(set(precios_componentes)) == 1:
        precio = precios_componentes[0]
    else:
        return None
    return {"precio_credito": precio, "precios_de_sus_grados": list(precios_componentes), **regla}
