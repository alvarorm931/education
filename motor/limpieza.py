"""Limpieza de textos oficiales: se conserva el contenido y se retiran los datos de personas.

Reglas (las mismas para todas las fuentes):
  - tabla con cabecera de datos personales (DNI, NIF, apellidos, nombre...) o con dos o más documentos
    de identidad: se guarda solo el número de filas y la cabecera;
  - párrafo con un documento de identidad o con el nombre de una persona precedido de tratamiento
    («don Antonio García», «D.ª María», «Sra. Puig»): se cuenta y no se guarda;
  - en los títulos, el nombre de la persona se sustituye por «[persona]» (nombramientos individuales);
  - el resto del texto se guarda íntegro.
Los municipios que empiezan por «Don» o «Doña» (Don Benito, Doña Mencía...) no son personas.
"""

from __future__ import annotations

import html
import re

RE_DOCUMENTO = re.compile(
    r"(\b\d{8}\s?[A-Z]\b|\b[XYZ]\d{7}\s?[A-Z]\b|\*{2,}\d{3,5}\*{1,}|\b\d{3,4}\*{3,}|\*{3,}\d{4}[A-Z]?\b|\bX{3,}\d{3,}X*"
    # documentos enmascarados con guiones, puntos o equis («77----74W», «12··345·X», «xxx1234xx»), 30/10/2026
    r"|\b\d{1,5}[-·.xX#]{2,}\d{1,5}\s?[A-Z]?\b|\b[xX#]{2,}\d{3,5}[xX#]{1,}\b)"
)
# Cabeceras de tablas con datos de personas, en castellano, gallego, catalán y euskera («D.N.I», «Nome e Apelidos»,
# «Nom i cognoms», «Izen-abizenak»)
CABECERA_PERSONAL = re.compile(r"(?<!\w)(d\.?\s?n\.?\s?i\.?|n\.?\s?i\.?\s?f\.?|n\.?\s?i\.?\s?e\.?|apellidos|apelidos|nombre(?!\s+(?:del?|de la|de los)\s+(?:puesto|plaza|categor|cuerpo|escala|especialidad|centro|"
                               r"organ|unidad|servicio))|nome|"
                               r"cognoms?|izen\w*|abizen\w*|documento|documento nacional|pasaporte|passaport)(?!\w)",
                               re.IGNORECASE)
RE_BLOQUE = re.compile(r"<table\b.*?</table>|<(p|li|h\d)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
RE_FILA = re.compile(r"<tr\b.*?</tr>", re.IGNORECASE | re.DOTALL)
RE_CELDA = re.compile(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)
RE_ETIQUETA = re.compile(r"<[^>]+>")
_MAY = "A-ZÁÉÍÓÚÑÀÈÒÇ"
_PAL = rf"[{_MAY}][\w’'-]+"
RE_TRATAMIENTO = re.compile(
    rf"(?<![\w.])(?P<t>(?i:don|doña|dona|dña\.?|d\.ª|dª|d\.|sr\.|sra\.|señor|señora|senyor|senyora))\s+"
    rf"(?P<n>{_PAL}(?:\s+(?:(?:de|del|de\s+la|de\s+las|de\s+los|y|i|e)\s+)?{_PAL}){{0,5}})")


def _municipios_con_tratamiento() -> set[str]:
    try:
        import json as _json
        from pathlib import Path as _Path
        datos = _json.loads((_Path(__file__).parent / "catalogo" / "datos" / "municipios_ine_2026.json")
                            .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {n.lower() for _, n in datos["municipios"] if n.split()[0].lower() in {"don", "doña", "dona"}}


MUNICIPIOS_CON_TRATAMIENTO = _municipios_con_tratamiento()
# «Sr. Subsecretario», «Sra. Alcaldesa», «senyor President»: un cargo, no una persona con nombre
CARGOS = re.compile(
    r"^(?:sub)?(?:secretari|director|directora|president|presidenta|presidente|alcald|rector|rectora|vicerrector|"
    r"vicerector|consejer|conseller|consellera|ministr|delegad|subdelegad|jef|cap\b|gerente|gerent|decan|degà|"
    r"interventor|tesorer|tresorer|concejal|regidor|regidora|diputad|viceconsejer|viceconseller|batle|batlessa|"
    r"defensor|fiscal|magistrad|juez|jutge|letrad|lletrad|comisari|inspector|coordinador|administrador|"
    r"responsable|encargad|titular|vocal|portavoz|conselleir|conselleira|xefe|xefa|alcalde|alcaldesa)",
    re.IGNORECASE)


def _es_persona(m: re.Match) -> bool:
    frase = f"{m.group('t')} {m.group('n')}".lower()
    if any(frase.startswith(x) for x in MUNICIPIOS_CON_TRATAMIENTO):
        return False
    if m.string[max(0, m.start() - 12):m.start()].lower().rstrip().endswith(("villa de", "villa del")):
        return False  # «Villa de Don Fadrique»: un municipio
    # «D.» seguido de mayúsculas suele ser el apartado de un sumario («D. OTRAS DISPOSICIONES»), no una persona
    if m.group("t").lower() == "d." and m.group("n").split()[0].isupper():
        return False
    if CARGOS.match(m.group("n")):
        return False
    return True


# Nombres sin tratamiento junto al acto que nombra a la persona: «nombrar … a Nombre Apellido Apellido como …»,
# «funcionaria interina de Nombre Apellido:», «Nombre Apellido tomará posesión».
_NOMBRE = rf"(?P<n>{_PAL}(?:\s+(?:(?:de|del|de\s+la|y|i|e)\s+)?{_PAL}){{1,4}})"
RE_DESIGNADO = [re.compile(x) for x in (
    rf"(?i:\b(?:nombrar|nombra|nombro|se nombra|nomear|nomea|nomenar|nomena|designar|designa|contratar|contrata|"
    rf"adjudicar|adjudica)\b)[^.;:]{{0,160}}?\s(?:a|al|á|à)\s+{_NOMBRE}(?=\s+(?:como|para|en|con|que)\b|\s*[,.:;)])",
    rf"(?i:\b(?:interin[oa]s?|interí|de carrera|en pr[aá]cticas|laboral fix[oa]|laboral fij[oa])\b)\s+"
    rf"(?:a|de|á)\s+{_NOMBRE}(?=\s*[,.:;(]|\s+(?:como|para|con)\b)",
    rf"{_NOMBRE}(?=\s+(?i:tomar[áa] posesi[óo]n|ha tomado posesi[óo]n|tom[óo] posesi[óo]n|prendrà possessió))",
)]
NO_NOMBRE = {"agente", "agent", "auxiliar", "técnico", "técnica", "tecnico", "tècnic", "administrativo",
             "administrativa", "administratiu", "oficial", "operario", "operaria", "operari", "peón", "peon", "policía",
             "policia", "conserje", "arquitecto", "arquitecta", "ingeniero", "ingeniera", "secretario", "secretaria",
             "interventor", "interventora", "tesorero", "tesorera", "ayuntamiento", "concello", "ajuntament",
             "diputación", "diputació", "deputación", "junta", "xunta", "consejería", "conselleria", "comisión",
             "comissió", "tribunal", "personal", "persoal", "funcionario", "funcionaria", "recursos", "servicios",
             "serveis", "departamento", "departament", "área", "area", "alcaldía", "alcaldia", "presidencia",
             "presidència", "concejalía", "plaza", "plaça", "praza", "puesto", "lloc", "posto", "cuerpo", "cos",
             "escala", "subescala", "grupo", "grup", "boletín", "butlletí", "real", "orden", "resolución", "decreto",
             "ley", "mancomunidad", "consorcio", "entidad", "empresa", "sociedad", "fundación", "universidad",
             "excmo", "excma", "ilmo", "ilma", "el", "la", "los", "las", "les", "els", "primer", "primera", "segundo",
             "segunda", "tercer", "tercera", "cuarto", "cuarta", "quinto", "quinta", "teniente", "tenienta", "tinent",
             "concejal", "concejala", "regidor", "regidora", "alcalde", "alcaldesa", "vocal", "presidente",
             "presidenta", "vicepresidente", "vicepresidenta", "diputado", "diputada", "consejero", "consejera"}


# Palabras que no forman parte de un nombre de persona: si aparecen, lo que hay detrás del acto es una institución,
# un cuerpo o un lugar («personal laboral fijo de Administración y Servicios», «Televisión Autonómica de Aragón»)
NO_PERSONA = {"administracion", "administracio", "administracions", "servicios", "servicio", "serveis", "servizos",
              "universidad", "universitat", "universidade", "hospital", "televisión", "television", "radio", "general",
              "especial", "autonomica", "autonomico", "local", "municipal", "provincial", "profesional", "laboral",
              "escuela", "escola", "instituto", "institut", "centro", "centre", "fundacion", "fundacio", "sociedad",
              "consorcio", "consorci", "agencia", "agencia", "oficina", "area", "seccion", "departamento", "unidad",
              "cuerpo", "escala", "subescala", "categoria", "grupo", "plaza", "plazas", "puesto", "puestos", "xxi",
              "sl", "sa", "slu", "s.l", "s.a", "policia", "bomberos", "salud", "sanitario", "enfermeria", "medicina"}


def _nombres_pila() -> set[str]:
    try:
        from pathlib import Path as _Path
        t = (_Path(__file__).parent / "catalogo" / "datos" / "nombres_pila.txt").read_text(encoding="utf-8")
    except OSError:
        return set()
    return {w for l in t.splitlines() if not l.startswith("#") for w in l.split()}


NOMBRES_PILA = _nombres_pila()


def _es_designado(m: re.Match) -> bool:
    """Sin tratamiento delante solo se da por persona si empieza por un nombre de pila frecuente y no trae palabras de
    institución: «Monitor de Musculación» o «Entidades Locales» no son personas."""
    n = m.group("n")
    primera = _sin_tildes(n.split()[0].lower().strip(".,"))
    if primera in NO_NOMBRE or CARGOS.match(n) or n.isupper() or primera not in NOMBRES_PILA:
        return False
    palabras = {_sin_tildes(w.lower().strip(".,")) for w in n.split()}
    return not (palabras & NO_PERSONA)


def _sin_tildes(t: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))


def tiene_nombre_de_persona(texto: str) -> bool:
    t = texto or ""
    return any(_es_persona(m) for m in RE_TRATAMIENTO.finditer(t)) or any(_es_designado(m) for r in RE_DESIGNADO
                                                                        for m in r.finditer(t))


def titulo_sin_nombres(titulo: str | None) -> str | None:
    """«... por la que se nombra Catedrático de Universidad a don Antonio García López.» ->
    «... por la que se nombra Catedrático de Universidad a [persona].»"""
    if not titulo:
        return titulo
    t = RE_TRATAMIENTO.sub(lambda m: "[persona]" if _es_persona(m) else m.group(0), titulo)
    for r in RE_DESIGNADO:
        t = r.sub(lambda m: (m.group(0)[: m.start("n") - m.start()] + "[persona]" + m.group(0)[m.end("n") - m.start():])
                  if _es_designado(m) else m.group(0), t)
    return t


def texto_de(fragmento: str) -> str:
    return " ".join(html.unescape(RE_ETIQUETA.sub(" ", fragmento)).replace("\xa0", " ").split())


def tabla(filas: list[list[str]]) -> dict:
    filas = [f for f in filas if any(f)]
    cabecera = filas[0] if filas else []
    contenido = " ".join(" ".join(f) for f in filas)
    # Un solo documento de identidad basta: una lista de una persona también es un dato personal
    if CABECERA_PERSONAL.search(" ".join(cabecera)) or RE_DOCUMENTO.search(contenido):
        return {"filas": max(len(filas) - 1, 0), "cabecera": cabecera, "datos_personales": True}
    return {"filas": len(filas), "contenido": filas, "datos_personales": False}


def parrafos_seguros(parrafos: list[str]) -> tuple[list[str], int]:
    guardados, omitidos = [], 0
    for p in parrafos:
        if not p:
            continue
        if RE_DOCUMENTO.search(p) or tiene_nombre_de_persona(p):
            omitidos += 1
        else:
            guardados.append(p)
    return guardados, omitidos


def limpiar_html(fragmento_html: str) -> dict:
    """Texto, tablas y recuento de omisiones a partir de HTML de un boletín."""
    parrafos, tablas = [], []
    for m in RE_BLOQUE.finditer(fragmento_html or ""):
        bloque = m.group(0)
        if bloque[:6].lower() == "<table":
            filas = [[texto_de(c) for c in RE_CELDA.findall(f)] for f in RE_FILA.findall(bloque)]
            tablas.append(tabla(filas))
        else:
            parrafos.append(texto_de(bloque))
    guardados, omitidos = parrafos_seguros(parrafos)
    return {"texto": "\n".join(guardados), "tablas": tablas, "parrafos_omitidos_por_datos_personales": omitidos}


def con_datos_personales(limpio: dict) -> bool:
    """El original tenía datos de personas (y por eso no se guarda en el archivo público, solo su huella)."""
    return bool(limpio.get("parrafos_omitidos_por_datos_personales") or limpio.get("lineas_omitidas_por_datos_personales")
                or any(t.get("datos_personales") for t in limpio.get("tablas") or []))


RE_FIN_PARRAFO = re.compile(r"[.:;]\s*$")


def limpiar_texto(texto: str, ignorar: re.Pattern | None = None) -> dict:
    """Texto plano (p. ej. extraído de un PDF): se rehacen los párrafos uniendo las líneas, se quitan cabeceras y
    pies repetidos (`ignorar`) y se omiten las líneas con documentos de identidad y los párrafos con nombres."""
    parrafos, actual, lineas_omitidas = [], [], 0
    for linea in (texto or "").splitlines():
        lin = " ".join(linea.split())
        if not lin:
            if actual:
                parrafos.append(" ".join(actual))
                actual = []
            continue
        if ignorar is not None and ignorar.match(lin):
            continue
        if RE_DOCUMENTO.search(lin):
            lineas_omitidas += 1
            continue
        if actual and actual[-1].endswith("-") and lin[:1].islower():
            actual[-1] = actual[-1][:-1] + lin
        else:
            actual.append(lin)
        if RE_FIN_PARRAFO.search(lin):
            parrafos.append(" ".join(actual))
            actual = []
    if actual:
        parrafos.append(" ".join(actual))
    guardados, omitidos = parrafos_seguros(parrafos)
    return {"texto": "\n".join(guardados), "tablas": [], "parrafos_omitidos_por_datos_personales": omitidos,
            "lineas_omitidas_por_datos_personales": lineas_omitidas}
