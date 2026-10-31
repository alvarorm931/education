"""Clasificación por reglas de los anuncios de la sección II.B (Oposiciones y concursos).

Primera pasada determinista y barata. Lo que no se resuelve con seguridad queda marcado
para la extracción con IA y, si sigue dudoso, para revisión humana.
"""

from __future__ import annotations

import re
import unicodedata

SECCION_OPOSICIONES = "2B"

NUMEROS = {
    "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
    "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13,
    "catorce": 14, "quince": 15, "dieciseis": 16, "diecisiete": 17, "dieciocho": 18,
    "diecinueve": 19, "veinte": 20, "veintiuna": 21, "veintiun": 21, "veintidos": 22,
    "veintitres": 23, "veinticuatro": 24, "veinticinco": 25, "treinta": 30, "cuarenta": 40,
    "cincuenta": 50,
}


def normalizar(texto: str) -> str:
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return " ".join(sin_tildes.lower().split())


def ambito(departamento: str | None) -> str:
    d = normalizar(departamento or "")
    if "administracion local" in d:
        return "local"
    if d.startswith("universidad") or "universidades" in d:
        return "universidad"
    if d.startswith("comunidad") or d.startswith("ciudad autonoma") or d.startswith("ciudad de "):
        return "autonomico"
    if d.startswith("ministerio") or d:
        return "estatal"
    return "desconocido"


# Orden importante: la primera regla que encaja gana.
REGLAS_ACTO: list[tuple[str, tuple[str, ...]]] = [
    # Castellano y, a continuación de cada regla, catalán/valenciano y gallego (textos sin tildes, en minúscula)
    ("correccion", ("correccion de error", "correccion de las bases", "correccion de errata", "se corrigen errores",
                    "se corrigen los errores", "se corrige error", "se corrige el error", "rectificacion de error",
                    "se subsanan errores",
                    "correccio d'errade", "correccio d'error", "correccio de les bases", "rectificacio d'error",
                    "correccion de erros", "correccion das bases")),
    ("desierta", ("desierta", "desierto", "deserta", "desert")),
    ("anulacion", ("deja sin efecto", "se anula", "anulacion de la convocatoria",
                   "deixa sense efecte", "deixar sense efecte", "anul·lacio de la convocatoria", "anul·lar la convocatoria",
                   "deixar sen efecto", "deixa sen efecto", "anulacion da convocatoria")),
    ("modificacion", ("se modifica la resolucion", "se modifica la orden", "se modifica la convocatoria",
                      "modificacion de la convocatoria", "se amplia el plazo", "ampliacion del plazo",
                      "se abre un nuevo plazo", "apertura de un nuevo plazo",
                      "modificacio de les bases", "modificacio de la convocatoria", "es modifica la convocatoria",
                      "es modifiquen les bases", "ampliacio del termini", "obertura d'un nou termini",
                      "nou termini de presentacio",
                      "modificacion da convocatoria", "modificacion das bases", "ampliacion do prazo",
                      "novo prazo de presentacion")),
    ("normativa", ("normas procedimentales", "por la que se establecen las normas")),
    ("admitidos", ("admitidos y excluidos", "admitidas y excluidas", "lista provisional", "lista definitiva",
                   "admision y exclusion", "admisiones y exclusion", "lista de admitidos", "relacion de admitidos",
                   "listado de admitidos", "aspirantes admitidos", "personas admitidas", "llista d'admesos",
                   "llista de persones admeses", "relacio d'admesos", "listaxe de admitidos",
                   "solicitudes presentadas", "solicitudes admitidas", "relacion de solicitudes", "solicitudes recibidas",
                   "lista de solicitudes",
                   "listado provisional", "listado definitivo", "listas de admisiones", "admisiones y exclusiones",
                   "admisiones, exclusiones",
                   "relacion provisional", "relacion definitiva de aspirantes admitidos",
                   "admeses i excloses", "admesos i exclosos", "admesos i excloses", "admeses i exclosos",
                   "llista provisional", "llista definitiva", "llistat provisional", "llistat definitiu",
                   "llistes provisionals", "llistes definitives", "relacio provisional", "relacio definitiva",
                   "admitidos e excluidos", "admitidas e excluidas", "listaxe provisional", "listaxe definitiva",
                   # «Admitidos/excluidos para plaza de…», «admitidos-excluidos» (BOP de Granada, 30/10/2026)
                   "admitidos/excluidos", "admitidas/excluidas", "admitidos/as/excluidos", "admitidos-excluidos",
                   "admitidos y no admitidos", "admitidos/as y excluidos",
                   # Listas que se quedaban con el texto (revisión de la rama de datos, 30/10/2026): «Listas
                   # provisionales de admitidos», «LISTADO ADMITIDOS Y EXLCUIDOS», «relación de aspirantes»,
                   # «Listaxe de persoas admitidas», «onartuen eta baztertuen behin-behineko zerrenda»
                   "admitidos", "admitidas", "admitido/a", "excluidos", "excluidas", "admesos", "admeses", "exclosos",
                   "excloses", "excluidos/as", "excluidas/os", "listas provisionales", "listas definitivas",
                   "listados provisionales", "listados definitivos", "listaxes provisionais", "listaxes definitivas",
                   "relacion de aspirantes", "relacion de personas aspirantes", "relacio d'aspirants",
                   "relacio de persones aspirants", "relacion de persoas aspirantes", "relacion nominal",
                   "onartuen", "baztertuen", "onartutakoen", "baztertutakoen", "behin-behineko zerrenda",
                   "behin betiko zerrenda", "behin-betiko zerrenda", "hautagaien zerrenda")),
    ("aprobados", ("aprobados", "aprobadas", "superado el proceso", "prelacion", "orden de puntuacion",
                   "relacion de puntuaciones", "calificaciones definitivas", "calificaciones provisionales",
                   "puntuaciones definitivas", "puntuaciones provisionales", "cualificacions", "puntuacions", "han superado", "seleccionados", "seleccionadas",
                   "aspirants aprovats", "persones aprovades", "relacio d'aprovats", "llista d'aprovats",
                   "han superat", "superat el proces", "seleccionats",
                   # Resultados, calificaciones, baremos, adjudicaciones y personas seleccionadas (30/10/2026)
                   "persona seleccionada", "personas seleccionadas", "persoa seleccionada", "aspirante seleccionado",
                   "aspirante seleccionada", "candidato seleccionado", "candidata seleccionada", "aspirante aprobado",
                   "aspirante aprobada", "persona aprobada", "persoa aprobada", "persona aprovada", "aspirant aprovat",
                   "resultado definitivo", "resultado provisional", "resultado final", "resultado parcial",
                   "resultados definitivos", "resultados provisionales", "resultados finales", "resultado del proceso",
                   "resultados del proceso", "resultado de la fase", "resultados de la fase", "resultado de la prueba",
                   "resultados de la prueba", "resultados de las pruebas", "resultado do proceso",
                   "resultados do proceso", "resultado do procedemento", "resultados do procedemento",
                   "resultat definitiu", "resultat provisional", "resultat final", "resultats definitius",
                   "resultats provisionals", "resultats finals", "resultat del proces", "resultats del proces",
                   "emaitzak", "behin betiko emaitzak", "calificaciones", "calificacion obtenida",
                   "calificacion de la fase", "calificacion final", "qualificacions", "qualificacio final",
                   "kalifikazioak", "baremacion definitiva", "baremacion provisional", "baremacion inicial",
                   "barem definitiu", "barem provisional", "valoracion definitiva", "valoracion provisional",
                   "acta de valoracion", "acta de constitucion y valoracion", "resultado de la valoracion",
                   "adjudicacion de plazas", "adjudicacion definitiva de", "adjudicacion provisional de",
                   "adjudicacio de places", "publicacion adxudicacion", "adxudicacion de postos de traballo",
                   "constitucion de lista de espera", "constitucion lista de espera", "constitucion de la lista de espera",
                   "lista de espera definitiva", "lista de espera provisional", "listaxe de espera definitiva",
                   "aprobacion definitiva listaxe", "integrantes de la bolsa", "composicion de la bolsa",
                   "integrants de la borsa", "composicio de la borsa")),
    # Antes que «nombramiento»: «por la que se nombran los miembros del Tribunal», «nombramiento del tribunal»
    ("tribunal", ("nombran los miembros del tribunal", "nombra a los miembros del tribunal", "nombran los tribunales",
                  "nombramiento del tribunal", "nombramiento de los miembros del tribunal", "nombramiento de tribunal",
                  "nombra el tribunal", "designacion del tribunal", "modificacion del tribunal", "asesores especialistas",
                  "designacion de asesores", "nomenament del tribunal", "nomenament dels membres", "es nomena el tribunal",
                  "nomeamento do tribunal")),
    ("nombramiento", ("se nombra", "nombramiento", "nombran funcionari", "toma de posesion", "se promociona",
                      "formalizacion de la contratacion como personal",
                      "nomenament", "es nomena", "presa de possessio", "nomeamento", "nomease")),
    # Resoluciones del proceso que salían como convocatoria u «otro» (procesos sin plazo, 31/10/2026): «por la que se
    # resuelve la convocatoria pública para la provisión…», «se adjudica destino definitivo al personal que superó…»,
    # «se constituye la bolsa», «se aprueba la bolsa de empleo derivada del proceso selectivo». Después de
    # «nombramiento»: «se procede al nombramiento… y se le adjudica destino» es un nombramiento
    ("aprobados", ("se resuelve la convocatoria", "se resuelve el proceso selectivo", "se resuelve el concurso",
                   "se resuelve parcialmente la convocatoria", "es resol la convocatoria", "es resol el concurs",
                   "es resol el proces", "resolvese a convocatoria", "resolvese o concurso", "se resolve a convocatoria",
                   "se adjudica destino", "se adjudican destinos", "adjudicacion de destinos", "s'adjudica destinacio",
                   "s'adjudiquen destinacions", "adxudicanse destinos", "se adxudica destino",
                   "se constituye la bolsa", "es constitueix la borsa", "constituese a bolsa", "se aprueba la bolsa",
                   "bolsa de empleo derivada", "lista de espera derivada", "s'aprova la borsa", "aprobase a bolsa")),
    ("tribunal", ("tribunal calificador", "composicion del tribunal", "tribunal que ha de juzgar", "comision de seleccion",
                  "composicion nominal del tribunal", "composicio nominal del tribunal", "composicion nominal de la comision",
                  "miembros del tribunal", "membres del tribunal", "membros do tribunal",
                  "organo de seleccion", "comision evaluadora", "composicion de la comision",
                  "tribunal qualificador", "composicio del tribunal", "organ de seleccio", "organ qualificador",
                  "comissio de seleccio", "comissio qualificadora", "tribunal cualificador",
                  "composicion do tribunal", "comissio de valoracio", "comision de valoracion",
                  "designacio de membres", "designacion de miembros", "designacion de los miembros")),
    ("examen", ("fecha de celebracion", "fecha, hora y lugar", "lugar, fecha y hora", "primer ejercicio",
                "data de realitzacio", "data, hora i lloc", "lloc, data i hora", "primer exercici",
                "data, hora e lugar", "lugar, data e hora", "primeiro exercicio")),
    # «Concurso-oposición de dos plazas de animador/a» (anuncio de convocatoria de una entidad local en el BON)
    ("convocatoria", ("se convoca", "convocatoria", "convoca proceso", "convoca concurso", "proceso selectivo",
                      "es convoca", "es convoquen", "proces selectiu", "proces de seleccio", "convocase",
                      "concurso-oposicion de ", "concurso oposicion de ", "concurs-oposicio de ")),
    ("bases", ("bases",)),
    # Al final: muchos títulos citan la oferta («en ejecución de la Oferta de Empleo Público») sin ser la oferta
    # «ANUNCIO sobre aprobación de la oferta pública de empleo para el 2023» (DOGC): unos 2.000 títulos que quedaban
    # como «otro» y en la cola de huérfanos (30/10/2026)
    ("oferta_empleo", ("oferta de empleo publico", "oferta publica d'ocupacio", "oferta d'ocupacio publica",
                       "oferta de ocupacio publica", "oferta de emprego publico", "oferta publica de emprego",
                       "oferta publica de empleo", "oferta extraordinaria de empleo", "oferta excepcional de empleo")),
]

REGLAS_MODALIDAD: list[tuple[str, tuple[str, ...]]] = [
    ("estabilizacion", ("estabilizacion", "estabilitzacio")),
    ("promocion_interna", ("promocion interna", "promocio interna")),
    ("concurso_oposicion", ("concurso-oposicion", "concurso oposicion", "concurs-oposicio", "concurs oposicio")),
    ("libre_designacion", ("libre designacion", "lliure designacio")),
    ("concurso", ("concurso de meritos", "concurso especifico", "concurso general", "por concurso",
                  "concurs de merits", "concurs especific", "per concurs")),
    ("oposicion", ("oposicion", "oposicio")),
    ("bolsa", ("bolsa de empleo", "bolsa de trabajo", "borsa de treball", "borsa d'ocupacio", "borsa d'aspirants",
               "borsa de personal", "borsa de", "bolsa de emprego")),
]


def _primera(reglas: list[tuple[str, tuple[str, ...]]], texto: str) -> str | None:
    for nombre, claves in reglas:
        if any(c in texto for c in claves):
            return nombre
    return None


ENTIDADES = (
    "Ayuntamiento", "Diputación Provincial", "Diputación Foral", "Diputación", "Cabildo Insular",
    "Consell Insular", "Consejo Insular de Aguas", "Consejo Insular", "Gerencia Municipal de Urbanismo", "Consell Comarcal", "Consejo Comarcal", "Comarca", "Mancomunidad", "Mancomunitat",
    "Consorcio", "Consorci", "Entidad Local Menor", "Entidad", "Junta Vecinal", "Área Metropolitana",
    "Àrea Metropolitana", "Agrupación", "Comunidad de Villa y Tierra", "Concello", "Organismo Autónomo",
    "Patronato", "Instituto Municipal",
)
# Tramo del título con el convocante: ", del Ayuntamiento de X (Provincia), [organismo,] referente a ..."
RE_TRAMO = re.compile(
    r",\s+(?:del|de la|de los|de las|de l')\s+(?P<tramo>.+?),\s+(?:referente|por la que|por el que|relativa|relativo|sobre|de convocatoria)"
)
RE_PARENTESIS_FINAL = re.compile(r"\s*\(([^()]+)\)\s*$")
RE_PLAZAS = re.compile(
    r"(?:proveer|cubrir|provisi[oó]n de|selecci[oó]n de)\s+(?P<n>\d+|[a-záéíóúñ]+)\s+plazas?\b",
    re.IGNORECASE,
)
RE_PUESTO = re.compile(r"\bplazas?\s+de\s+(?P<puesto>[^.;,]+?)(?:,|\.|;| mediante| por el sistema| en turno|$)", re.IGNORECASE)


def _partir_fuera_de_parentesis(texto: str) -> list[str]:
    partes, actual, nivel = [], [], 0
    for i, c in enumerate(texto):
        nivel += (c == "(") - (c == ")")
        if c == "," and nivel == 0 and texto[i + 1:i + 2] == " ":
            partes.append("".join(actual))
            actual = []
        else:
            actual.append(c)
    partes.append("".join(actual))
    return partes


def convocante(titulo: str) -> dict | None:
    """Extrae tipo de entidad, nombre, provincia y organismo dependiente del título del BOE."""
    m = RE_TRAMO.search(titulo)
    if not m:
        return None
    partes = [p.strip() for p in _partir_fuera_de_parentesis(m.group("tramo"))]
    principal, organismo = partes[0], (", ".join(partes[1:]) or None)
    tipo = next((e for e in sorted(ENTIDADES, key=len, reverse=True) if principal.startswith(e + " ")), None)
    if tipo is None:
        return None
    resto = principal[len(tipo):].strip()
    resto = re.sub(r"^(?:de la|de los|de las|del|de|d')\s+", "", resto)
    provincia = None
    p = RE_PARENTESIS_FINAL.search(resto)
    if p:
        provincia = p.group(1).strip()
        resto = resto[: p.start()].strip()
    return {"tipo": tipo, "nombre": resto, "provincia": provincia, "organismo": organismo}


def alcance(titulo_norm: str, modalidad: str | None, epigrafe: str | None) -> str:
    """Qué parte del producto cubre el anuncio. Fase 1: oposiciones de acceso; fuera, provisión de puestos."""
    ep = normalizar(epigrafe or "")
    if modalidad in {"libre_designacion"} or "provision de puesto" in titulo_norm or "concursos de traslados" in titulo_norm \
            or "concurso de traslados" in titulo_norm or "concurso de traslado" in titulo_norm \
            or RE_PROVISION_HABILITADOS.search(titulo_norm) \
            or "procedimientos de libre designacion" in ep or ep == "personal funcionario. concursos" \
            or "provisio de lloc" in titulo_norm or "concurs de trasllats" in titulo_norm \
            or "provision de posto" in titulo_norm \
            or ("comissio de serveis" in titulo_norm and "acces" not in titulo_norm) \
            or (modalidad == "concurso" and not any(p in titulo_norm for p in ("plaza", "placa", "places", "praza"))
                and not any(p in titulo_norm for p in ("proces de seleccio", "proces selectiu", "contractacio",
                                                        "borsa", "proceso de seleccion"))):
        return "provision_puestos"
    if "cuerpos docentes universitarios" in ep or "profesor titular" in titulo_norm or "catedratic" in titulo_norm \
            or "professor titular" in titulo_norm:
        return "docente_universitario"
    if modalidad == "promocion_interna":
        return "promocion_interna"
    return "acceso"


# Nombramientos accidentales, provisionales o en acumulación de los puestos reservados a habilitados nacionales
# («se confiere nombramiento accidental para el puesto de Secretaría-Intervención»): provisión, no acceso
RE_PROVISION_HABILITADOS = re.compile(
    r"nombramientos? (?:accidental|provisional|en comision de servicios|interino) (?:para|en|del?) (?:el )?puesto "
    r"(?:de (?:la )?)?(?:secretari|intervenci|tesorer|vicesecretari|vicointervenci)|"
    r"nombramientos? accidental|acumulacion de (?:las )?funciones|"
    r"nomenament (?:accidental|provisional)|acumulacio de funcions|"
    # «en comisión de servicios», salvo en una convocatoria de acceso («procedimiento selectivo para el acceso al
    # Cuerpo de Inspectores… y Inspector Accidental, en comisión de servicios»)
    r"^(?!.*(?:acceso|ingreso|selectiv|oposici)).*comision de servicios")
# Lo que no es de ningún proceso de selección aunque hable de personal (ceses, personal eventual, plantillas,
# relaciones de puestos, convenios, retribuciones): ni crea procesos ni se espera en ninguno
RE_NO_SELECCION = re.compile(
    r"\b(?:cese|ceses|cesa|cesan|cessament|cesamento)\b|personal eventual|personal de confianza|"
    r"relacion de puestos de trabajo|relacion de los puestos de trabajo|relacio de llocs de treball|"
    r"relacion puestos trabajo|catalogo de puestos|valoracion de puestos|\brpt\b|convenio colectivo|"
    r"conveni col.lectiu|conveni collectiu|plantilla (?:de personal|organica|presupuestaria)|"
    r"(?:aprobacion|modificacion) (?:inicial |definitiva )?de (?:la )?plantilla|retribuciones|"
    r"complemento (?:especifico|de destino|de productividad)|masa salarial|calendario laboral|jubilacion|"
    r"compatibilidad|excedencia|reingreso|permuta|segunda actividad|redistribucion de efectivos|"
    r"delegacion de (?:competencias|atribuciones|funciones|firma)|personal emerito|emerit[oa]s?\b|"
    r"reconocimiento de (?:servicios|trienios|grado)|adscripcion provisional|reclasificacion")


RE_GUARDA_SELECCION = re.compile(
    r"funcionari\w* de carrera|personal laboral fijo|personal estatutario fijo|selectiv|proces selectiu|oposici|"
    r"concurso|concurs\b|\bbases\b|convocatori|\bplazas?\b|\bplaces?\b|\bprazas?\b|bolsa|borsa|\blistas?\b|"
    r"\bllistes?\b|tribunal|admitid|aprobad|superado|aspirantes")


def alcance_vigente(titulo: str | None, tipo_acto: str | None, modalidad: str | None, guardado: str | None) -> str | None:
    """El alcance con las reglas vigentes del título: el guardado al capturar si ya dejaba fuera el anuncio (por su
    epígrafe o apartado), y si no, el que da hoy el título; «no_seleccion» para lo que no es de ningún proceso."""
    if guardado not in (None, "acceso"):
        return guardado
    t = normalizar(titulo or "")
    if not t:
        return guardado
    nuevo = alcance(t, modalidad, None)
    if nuevo == "acceso" and tipo_acto in ("otro", "nombramiento", "correccion", "modificacion") and \
            RE_NO_SELECCION.search(t) and not RE_GUARDA_SELECCION.search(t):
        return "no_seleccion"
    return nuevo if guardado == "acceso" or nuevo != "acceso" else guardado


def _numero(palabra: str) -> int | None:
    if palabra.isdigit():
        return int(palabra)
    return NUMEROS.get(normalizar(palabra))


def clasificar(item: dict) -> dict:
    titulo = item.get("titulo") or ""
    t = normalizar(titulo)
    resultado = {
        "ambito": ambito(item.get("departamento")),
        "tipo_acto": _primera(REGLAS_ACTO, t) or "otro",
        "modalidad": _primera(REGLAS_MODALIDAD, t),
        "alcance": None,
        "convocante": None,
        "plazas": None,
        "plazas_texto": None,
        "puesto": None,
        "extraccion": "reglas",
        "pendiente_revision": [],
    }

    resultado["alcance"] = alcance(t, resultado["modalidad"], item.get("epigrafe"))
    resultado["convocante"] = convocante(titulo)
    if resultado["convocante"] is None and resultado["ambito"] == "local":
        resultado["pendiente_revision"].append("convocante")

    m = RE_PLAZAS.search(titulo)
    if m:
        resultado["plazas_texto"] = m.group("n")
        resultado["plazas"] = _numero(m.group("n"))  # None si es "varias"
    elif re.search(r"\buna plaza\b", t):
        resultado["plazas"], resultado["plazas_texto"] = 1, "una"

    m = RE_PUESTO.search(titulo)
    if m:
        puesto = m.group("puesto").strip()
        if len(puesto) <= 120:
            resultado["puesto"] = puesto

    if resultado["tipo_acto"] == "convocatoria" and resultado["alcance"] == "acceso":
        if resultado["plazas"] is None:
            resultado["pendiente_revision"].append("plazas")
        if resultado["puesto"] is None:
            resultado["pendiente_revision"].append("puesto")
    return resultado
