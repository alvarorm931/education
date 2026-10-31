"""Limpieza de textos oficiales: se conserva el contenido y se retiran los datos de personas.

Reglas (las mismas para todas las fuentes):
  - tabla con cabecera de datos personales (DNI, NIF, apellidos, nombre...) o con dos o más documentos
    de identidad: se guarda solo el número de filas y la cabecera;
  - párrafo con un documento de identidad o con el nombre de una persona precedido de tratamiento
    («don Antonio García», «D.ª María», «Sra. Puig»): se cuenta y no se guarda;
  - párrafo con un nombre completo sin tratamiento (firmas, tribunales: «El Alcalde, Nombre Apellido Apellido»,
    «Vocal: Apellido Apellido, Nombre»): también se cuenta y no se guarda; en un párrafo largo (un anuncio entero
    sacado de un PDF sin saltos) solo se quitan sus frases con el nombre;
  - los pies de firma electrónica («Firmado por … el 19/09/2025», «Document signat per … en data …») se quitan;
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
    r"|\b\d{1,5}[-·.xX#]{2,}\d{1,5}\s?[A-Z]?\b|\b[xX#]{2,}\d{3,5}[xX#]{1,}\b"
    # tres cifras y letra tras asteriscos, o cifra-asteriscos-cifra («*****365-E», «*****721F», «0******3-L»)
    r"|\*{3,}\d{3,4}-?[A-Z]\b|\b\d{1,3}\*{3,}\d{1,3}-?[A-Z]?\b)"
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
    rf"(?<![\w.])(?P<t>(?i:don|doña|dona|dña\.?|d\.ª\.?|dª\.?|d\.\s?ª|d\.|sr\.|sra\.|señor|señora|senyor|senyora))\s+"
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
    # «D.» seguido de mayúsculas suele ser el apartado de un sumario («D. OTRAS DISPOSICIONES»), no una persona; sí lo
    # es si empieza por un nombre de pila («D. MANUEL SIMÓN VILLAGRASA», 30/10/2026)
    if m.group("t").lower() == "d." and m.group("n").split()[0].isupper():
        primera = _sin_tildes(m.group("n").split()[0].lower())
        return len(m.group("n").split()) >= 2 and primera in NOMBRES_PILA and primera not in NO_NOMBRE
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


# Nombres completos sin tratamiento ni acto de nombramiento (firmas, tribunales, pies de firma electrónica), vistos al
# revisar 3.000 textos de la rama de datos el 30/10/2026: «El Alcalde, Sergio Gambau Gracia.», «Presidente titular:
# Ismael García Burgos», «JON ZARANDONA BORREGUERO.», «Firmado por … JUAN LUIS CUADROS CAMPO el …». Se reconoce un
# nombre de pila frecuente seguido de dos o más palabras con mayúscula (o de una, junto a un cargo o un «Fdo.:»), sin
# palabras de institución y sin una calle, un centro o un santo delante.
_MIN = "a-záéíóúñüàèòçïl·"
RE_PALABRA_NOMBRE = re.compile(rf"^(?:(?:LL|[{_MAY}])[{_MIN}’']+(?:-[{_MAY}]?[{_MIN}’']+)*|[{_MAY}Ü]{{2,}}(?:-[{_MAY}Ü]{{2,}})*)$")
RE_ROMANO = re.compile(r"^X{0,3}(?:IX|IV|V?I{0,3})$")
RE_INICIAL = re.compile(rf"^[{_MAY}]\.$")
PARTICULAS = {"de", "del", "la", "las", "los", "y", "i", "e", "da", "das", "do", "dos", "van", "von", "di"}
ABREVIATURAS_PILA = {"ma", "m.a", "m.a.", "ma.", "fco", "fco.", "fdez", "jose", "josep", "xose", "m.", "jº", "fº"}
# Delante del nombre: calles, centros, santos e instituciones que llevan el nombre de una persona
ANTES_NO_PERSONA = {"c/", "c/.", "calle", "c.", "avda", "avda.", "av", "av.", "avenida", "avinguda", "plaza", "plaça",
                    "praza", "pza", "pza.", "paseo", "passeig", "rua", "carrer", "camino", "cami", "ronda", "travesia",
                    "urbanizacion", "urb", "urb.", "colegio", "col·legi", "colexio", "ceip", "cp", "c.p.", "cra", "cpi",
                    "ies", "i.e.s.", "instituto", "institut", "escuela", "escola", "universidad", "universitat",
                    "universidade", "hospital", "centro", "centre", "residencia", "fundacion", "fundacio", "premio",
                    "premi", "catedra", "biblioteca", "teatro", "auditorio", "pabellon", "polideportivo", "estadio",
                    "parque", "parc", "rey", "reina", "principe", "princesa", "infanta", "infante", "san", "santa",
                    "sant", "santo", "virgen", "beato", "beata", "sor", "fray", "obra", "obras", "poeta", "pintor",
                    "escultor", "maestro", "mestre", "profesor", "beca", "programa", "proyecto", "edificio", "sala",
                    "grupo", "conservatorio", "museo", "museu", "casa", "centros", "iea", "eoi", "cep", "epa", "cfa",
                    "esc.", "inst."}
DESPUES_NO_PERSONA = {"kalea", "kalean", "etorbidea", "enparantza", "bidea", "ikastetxea",
                      "institutua", "ikastola", "fundazioa", "s.l.", "s.a.", "sl", "sa", "slu"}
NO_APELLIDO = NO_PERSONA | (NO_NOMBRE - {"real", "peon", "peón"}) | {"roja", "vermella", "gorria", "boreal", "ayuntamiento", "concello",
                                       "ajuntament", "udala", "provincia", "comunidad", "junta", "gobierno", "govern",
                                       "goberno", "estado", "boletin", "butlleti", "diario", "oficial", "anuncio",
                                       "anunci", "edicto", "edicte", "bases", "convocatoria", "resolucion", "decreto",
                                       "orden", "ley", "lei", "llei", "tema", "temas", "anexo", "annex", "anexos",
                                       # adjetivos de instituciones y marcos («Marc Europeu Comú de Referència»)
                                       "europeo", "europea", "europeu", "europeus", "comun", "comu", "nacional",
                                       "estatal", "espanol", "espanola", "espanyol", "espanyola", "catalan", "catala",
                                       "catalana", "gallego", "galega", "vasco", "vasca", "internacional", "mundial",
                                       "publico", "publica", "public", "superior", "central", "regional", "comarcal",
                                       "insular", "foral", "plan", "programa", "proyecto", "projecte",
                                       "proxecto", "sostenibilidad", "sostibilidade", "estrategia", "fondo", "fons"}
# Nombres de pila que también son palabras corrientes («al amparo de», «la Cruz», «el Rosario»): tras un artículo o
# una contracción no se toman por nombre
PILA_AMBIGUOS = {"amparo", "rosario", "consuelo", "esperanza", "victoria", "gracia", "paz", "luz", "cruz", "salvador",
                 "rocio", "pilar", "dolores", "mercedes", "angeles", "soledad", "flor", "rosa", "blanca", "alba",
                 "aurora", "asuncion", "concepcion", "encarnacion", "remedios", "socorro", "inmaculada", "milagros",
                 "nieves", "reyes", "camino", "marc", "sol", "mar", "marina", "belen", "estrella", "valle", "sierra",
                 "vega", "gloria", "loreto", "pura", "candelaria", "ascension", "libertad", "leon", "jesus", "angel"}
ARTICULOS = {"al", "ao", "á", "el", "la", "las", "los", "lo", "del", "do", "da", "dos", "das", "su", "sus", "un",
             "una", "nuestra", "nuestro", "esta", "este", "cada", "toda", "todo", "sota", "sobre", "baixo", "bajo"}
FIRMA_ANTES = {"fdo", "fdo.", "fdo.:", "fdo:", "firmado", "firmado:", "firma:", "signat", "signat:", "asdo", "asdo.",
               "asdo.:", "asinado", "asinado:", "sinatua", "sinatua:", "sin.:", "fdo.-"}
_PUNTUACION_INICIO = "«“\"'(¿¡•–—-·*"
_PUNTUACION_FIN = ",.;:)»”\"'!?-–—"


def _municipios() -> set[str]:
    try:
        import json as _json
        from pathlib import Path as _Path
        datos = _json.loads((_Path(__file__).parent / "catalogo" / "datos" / "municipios_ine_2026.json")
                            .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {_sin_tildes(n.lower()) for _, n in datos["municipios"]}


# Municipios, provincias y comunidades («Pedro Muñoz», «Santiago de Compostela», «Castilla y León»): no son personas
MUNICIPIOS = _municipios() | {"castilla y leon", "castilla-la mancha", "castilla la mancha", "pais vasco", "euskadi",
                              "comunidad valenciana", "comunitat valenciana", "illes balears", "islas baleares",
                              "la rioja", "region de murcia", "principado de asturias", "comunidad de madrid",
                              "ciudad real", "santa cruz de tenerife", "las palmas", "a coruna", "la coruna"}
MUNICIPIOS_CON_NOMBRE = {m for m in MUNICIPIOS if len(m.split()) >= 2 and m.split()[0] in NOMBRES_PILA}


def _nucleo(token: str) -> str:
    return token.lstrip(_PUNTUACION_INICIO).rstrip(_PUNTUACION_FIN)


def _es_pila(nucleo: str) -> bool:
    n = _sin_tildes(nucleo.lower())
    return (n in NOMBRES_PILA or n in ABREVIATURAS_PILA) and n not in NO_NOMBRE


def _es_apellido(nucleo: str) -> bool:
    n = _sin_tildes(nucleo.lower())
    return (bool(RE_PALABRA_NOMBRE.match(nucleo)) and not RE_ROMANO.match(nucleo) and n not in NO_APELLIDO
            and not CARGOS.match(nucleo))


RE_CABECERA_NOMBRES = re.compile(r"(?i)nombre y apellidos|apellidos y nombre|nom i cognoms|cognoms i nom|"
                                 r"nome e apelidos|apelidos e nome|izen-abizenak|izena eta abizenak")


def _nombre_suelto(texto: str) -> bool:
    # «Vocal 3:Asuncion …», «Fdo.:Nombre»: los dos puntos pegados separan palabras
    toks = re.findall(r"[^\s—–]+|[—–]", re.sub(r"([:;])(?=[^\s\d/])", r"\1 ", texto or ""))
    nucleos = [_nucleo(t) for t in toks]
    solo_nombre = (2 <= len(toks) <= 7 and bool(nucleos[-1]) and _es_apellido(nucleos[-1])
                   and all(RE_PALABRA_NOMBRE.match(n) or n.lower() in PARTICULAS or RE_INICIAL.match(n) for n in nucleos if n))
    for i, n in enumerate(nucleos):
        if not n or not _es_pila(n) or not (RE_PALABRA_NOMBRE.match(n) or "." in n or "ª" in n):
            continue
        if i and _sin_tildes(n.lower()) in PILA_AMBIGUOS and _sin_tildes(toks[i - 1].lower()) in ARTICULOS:
            continue
        # tras «don», «D.», «Sra.»… decide RE_TRATAMIENTO (con sus excepciones: Don Benito, Doña Mencía)
        if i and _sin_tildes(toks[i - 1].lower()) in ("don", "dona", "d.", "dna.", "sr.", "sra.", "senor", "senora",
                                                       "senyor", "senyora", "d.a", "da", "d.a."):
            continue
        # lo que hay delante (hasta tres palabras sin signo de puntuación entre ellas; «Dr.» no corta: «Hospital
        # Universitario Dr. Josep Trueta» es un hospital)
        # (más allá de la palabra inmediata, solo cuentan las que van con mayúscula: «Colegio Público»)
        antes, k = [], i - 1
        while k >= 0 and len(antes) < 3:
            a = _sin_tildes(toks[k].lower()).lstrip(_PUNTUACION_INICIO)
            if a in ("dr.", "dra.", "dr", "dra", "doctor", "doctora"):
                k -= 1
                continue
            if a[-1:] in ",;:)" or (a.endswith(".") and a not in ANTES_NO_PERSONA):
                break
            if antes and not toks[k][:1].isupper():
                break
            antes.append(a)
            k -= 1
        if any(a in ANTES_NO_PERSONA or a.startswith("c/") for a in antes):
            continue
        # el nombre: pila, más pilas o apellidos con partículas; acaba en el primer signo de puntuación
        palabras, j = 1, i
        fin = toks[i][-1:] in ",;:)" or (toks[i].endswith(".") and _sin_tildes(n.lower()) not in ABREVIATURAS_PILA)
        while not fin and j + 1 < len(toks):
            s = nucleos[j + 1]
            k2 = j + 1
            while k2 < len(toks) and k2 - j <= 3 and nucleos[k2].lower() in PARTICULAS and toks[k2][-1:] not in _PUNTUACION_FIN:
                k2 += 1
            if k2 > j + 1:
                if k2 < len(toks) and _es_apellido(nucleos[k2]):
                    j = k2 - 1
                    continue
                break
            if RE_INICIAL.match(toks[j + 1]):
                j += 1
                continue
            if not _es_apellido(s):
                # un apellido que también es un cargo («Fdo.: Álvaro Regidor Reyes»): solo con otro apellido detrás
                if not (CARGOS.match(s) and RE_PALABRA_NOMBRE.match(s) and toks[j + 1][-1:] not in _PUNTUACION_FIN
                        and j + 2 < len(toks) and _es_apellido(nucleos[j + 2])):
                    break
            palabras += 1
            j += 1
            fin = toks[j][-1:] in _PUNTUACION_FIN
        if palabras < 2:
            continue
        nombre = _sin_tildes(" ".join(nucleos[i:j + 1]).lower())
        if any(nombre.startswith(m) for m in MUNICIPIOS_CON_NOMBRE):
            continue
        if j + 1 < len(toks) and _sin_tildes(nucleos[j + 1].lower()) in DESPUES_NO_PERSONA:
            continue
        if palabras >= 3:
            return True
        # dos palabras: solo junto a un cargo con coma o dos puntos, tras «Fdo.:» o si el párrafo es solo el nombre
        previo = toks[i - 1] if i else ""
        if previo in (":", "-", "–", "—") and i > 1:
            previo = toks[i - 2] + previo
        p = _sin_tildes(previo.lower())
        solo = solo_nombre and not any(_nucleo(t).strip("0123456789.ºª") for t in toks[:i])
        # «Vocal número 3: Nombre Apellido Plaza, …»: tras dos puntos con un puesto de tribunal poco antes
        if previo.endswith(":") and RE_TRIBUNAL.search(" ".join(toks[max(0, i - 5):i])):
            return True
        if p in FIRMA_ANTES or (previo[-1:] in ",:" and CARGOS.match(_nucleo(previo).split("-")[-1])) or solo:
            return True
        # «Ana Herrera Alcaldessa», o bajo una cabecera «Nombre y apellidos»
        if (j + 1 < len(toks) and toks[j][-1:] not in ",;:" and CARGOS.match(nucleos[j + 1])
                or RE_CABECERA_NOMBRES.search(" ".join(toks[:i]))):
            return True
    return False


# Apellidos y nombre en las listas de tribunales: «Vocal 1 suplente: Gil González, Ana Belén», «Sutil Barrigón, María»
RE_APELLIDOS_NOMBRE = re.compile(
    rf"(?<![\w])(?P<a>{_PAL}(?:\s+(?:de|del|de\s+la|y|i)\s+|\s+){_PAL}),\s+(?P<p>{_PAL})(?:\s+(?:(?:de|del|de\s+la|de\s+las|de\s+los)\s+)?{_PAL})?(?=\s*$|\s*[.;)]|\s+[{_MAY}]\.)")
# con un puesto de tribunal delante, aunque siga el cargo («Presidente titular Arroyo Aparicio, Alicia Catedrática»)
RE_APELLIDOS_NOMBRE_TRIBUNAL = re.compile(
    rf"(?<![\w])(?P<a>{_PAL}(?:\s+(?:de|del|de\s+la|y|i)\s+|\s+){_PAL}),\s+(?P<p>{_PAL})(?![\w’'-])")
# en mayúsculas basta con la forma («CALDERÓN MARTÍN, MARÍA DEL CARMEN jueves…», «MARCOS DEL CANO,JOSÉ DANIEL»)
_PALM = rf"[{_MAY}Ü][{_MAY}Ü’'-]+"
RE_APELLIDOS_NOMBRE_MAY = re.compile(
    rf"(?<![\w])(?P<a>{_PALM}(?:\s+(?:DE|DEL|DE\s+LA|DE\s+LOS|Y|I)\s+|\s+){_PALM}),\s*(?P<p>{_PALM})(?![\w])")
RE_TRIBUNAL = re.compile(r"(?i)\b(?:vocal|presidente|presidenta|president|secretari[oa]?|suplente|titular|miembro|"
                         r"membre|kidea|idazkari|lehendakari|asesor)\b")


# Entrada numerada de una lista de personas: «23.González Cabral, María Del Mar», «2.-Barba Albarrán, Miriam Del
# Rocío», «28.Ivanysmyna, Tetyana» (BOP de Huelva, 19/06/2023: la v1 solo veía «Apellido Apellido, Nombre» sin número
# pegado ni partículas con mayúscula, y una sonda publicó nombres). Con el número delante basta la forma: apellidos y
# nombre con mayúscula separados por una coma, hasta el final de la línea.
_PART = r"(?i:de|del|la|las|los|y|i|e|da|das|do|dos|van|von|di)"
_PALL = rf"[{_MAY}Ü](?:[\w’'-]+|ª)"
RE_ENTRADA_DE_LISTA = re.compile(
    rf"^\s*\d{{1,4}}\s*[.\-–)º][\s.\-–)º]*(?P<a>{_PALL}(?:\s+(?:{_PART}|{_PALL})){{0,5}}),\s*"
    rf"(?P<p>{_PALL}\.?(?:\s+(?:{_PART}|{_PALL}\.?)){{0,4}})\s*[.;]?\s*$")


APARTADOS_DE_BASES = {
    "lugar", "fecha", "fechas", "hora", "plazo", "plazos", "solicitud", "solicitudes", "calendario", "requisito",
    "requisitos", "tribunal", "temario", "programa", "admision", "exclusion", "publicacion", "publicaciones",
    "presentacion", "derechos", "examen", "normas", "generales", "objeto", "funciones", "retribuciones", "sistema",
    "seleccion", "fase", "fases", "oposicion", "concurso", "ejercicio", "ejercicios", "pruebas", "desarrollo",
    "calificacion", "nombramiento", "toma", "posesion", "bolsa", "empleo", "recursos", "proteccion", "datos", "base",
    "plazas", "plaza", "tasas", "tasa", "documentacion", "meritos", "valoracion", "incidencias", "impugnacion",
    "legislacion", "aplicable", "regimen", "juridico", "contratacion", "duracion", "jornada", "horario", "periodo",
    "practicas", "formacion", "titulacion", "anexo", "anexos", "modelo", "instancia", "lista", "listas", "admitidos",
    "excluidos", "aspirantes", "puntuacion", "puntuaciones", "relacion", "aprobados", "vigencia", "efectos",
}


def _sin_ligaduras(texto: str) -> str:
    # pypdf saca las ligaduras con un espacio detrás («Garﬁ a», «de ﬁ nitivas»)
    return re.sub(r"\s?([ﬁﬂ])\s?(?=[a-záéíóúñ])", r"\1", texto).replace("ﬁ", "fi").replace("ﬂ", "fl")


def _entrada_de_lista(texto: str) -> bool:
    m = RE_ENTRADA_DE_LISTA.match(_sin_ligaduras(texto or ""))
    if not m:
        return False
    nombre = m.group("p").split()
    # en el nombre de pila no hay «y» que una dos palabras («1. Concepto, Elementos y Clases», «Recuperació,
    # Transformació i Resiliència», temarios)
    if any(w in ("y", "Y", "i", "I", "e", "E") for w in nombre[1:]):
        return False
    todo = m.group("a") + " " + m.group("p")
    letras = [c for c in todo if c.isalpha()]
    if letras and all(c.isupper() for c in letras):
        # en mayúsculas, como los títulos de los apartados («5. PREMIOS, DISTINCIONES…»): solo con un nombre de pila
        if not _es_pila(nombre[0].rstrip(".")):
            return False
    elif any(len(w) >= 2 and w.isupper() and w.isalpha() and w.lower() not in PARTICULAS for w in todo.split()):
        return False  # siglas en una línea con minúsculas («15. Protocolos UDP, TCP.»)
    palabras = [_sin_tildes(w.lower().rstrip(".")) for w in todo.split()]
    palabras = [w for w in palabras if w not in PARTICULAS]
    # «1. Ayuntamiento de Cala, Huelva», «3. Temario, Anexo», «10. Lugar, Fecha y Hora»: instituciones y apartados de
    # unas bases no son personas
    return not any(w in NO_APELLIDO or w in APARTADOS_DE_BASES or CARGOS.match(w) for w in palabras)


def _apellidos_y_nombre(texto: str) -> bool:
    for m in [*RE_APELLIDOS_NOMBRE.finditer(texto or ""), *RE_APELLIDOS_NOMBRE_MAY.finditer(texto or ""),
              *(RE_APELLIDOS_NOMBRE_TRIBUNAL.finditer(texto or "") if RE_TRIBUNAL.search(texto or "") else [])]:
        apellidos = [_sin_tildes(w.lower()) for w in m.group("a").split() if w.lower() not in PARTICULAS]
        if not _es_pila(m.group("p")) or any(a in NO_APELLIDO or CARGOS.match(a) for a in apellidos):
            continue
        if _sin_tildes(m.group("a").lower()) in MUNICIPIOS:
            continue
        if (m.re is RE_APELLIDOS_NOMBRE_MAY or RE_TRIBUNAL.search(texto[max(0, m.start() - 60):m.start()])
                or not texto[:m.start()].strip(" -–•·0123456789.ºª)")):
            return True
    return False


# Pies de firma electrónica dentro del texto: se quitan del párrafo (llevan el nombre de quien firma) y el resto se
# conserva. Formatos vistos el 30/10/2026 (BOP de Ciudad Real, plataforma esPublico, BOP de Girona y de Barcelona).
_FECHA = r"\d{1,2}/\d{1,2}/\d{4}"
_HORA = r"\d{1,2}:\d{2}(?::\d{2})?"
RE_PIE_FIRMA = re.compile(
    # BOP de Ciudad Real y de Toledo: «Firmado por Jefe de Sección del B.O.P. NOMBRE el 19/09/2025 14:03:00»
    rf"(?:Documento firmado electr[oó]nicamente\.?\s*)?(?:C[oó]digo Seguro de Verificaci[oó]n:\s*\S+\s*)?"
    rf"(?:Firmado por|FIRMADO POR)\b[^\n]{{0,140}}?\b(?:el\s+)?{_FECHA}(?:\s+{_HORA})?"
    # BOP de Sevilla: «… Estado Fecha y hora Firmado Por NOMBRE Firmado 21/03/2025 12:00:00 Observaciones Página 1/21»
    rf"|Estado Fecha\s?y\s?hora\s+Firmado Por\b[^\n]{{0,120}}?\bFirmado\s+{_FECHA}(?:\s+{_HORA})?(?:\s+Observaciones)?"
    rf"(?:\s+P[aá]gina\s+\d+/\d+)?"
    # plataforma esPublico: «NOMBRE (1 de 1) ALCALDESA Fecha Firma: 14/10/2026 HASH: …» (también con letras dobles)
    rf"|(?:[{_MAY}][\w’'.-]*\s+){{1,8}}\(\(?\d+\s+(?:de|ddee)\s+\d+\)\)?\s+[^\n|]{{0,80}}?Fecha Firma:\s*{_FECHA}"
    r"(?:\s+HASH:\s*[0-9a-fA-F]+)?"
    # «Este documento ha sido firmado por CARGO (NOMBRE) a las 18:24 del día 13/02/2026»
    rf"|(?:Este documento ha sido )?firmado por\s[^\n]{{0,160}}?\([^)\n]{{3,80}}\)\s+a las\s+{_HORA}\s+del d[ií]a\s+{_FECHA}"
    # «Firmado electrónicamente por NOMBRE - CARGO – 20/3/2025»
    rf"|Firmado electr[oó]nicamente por\s[^\n]{{0,160}}?\b{_FECHA}"
    # BOP de Girona y de Lleida: «Document signat per NOMBRE - (FIRMA) en data 28/08/2024»
    rf"|Document signat (?:electr[oò]nicament )?per\b[^\n]{{0,120}}?\ben data\s+{_FECHA}(?:\s+{_HORA})?"
    # «Signat electrònicament per:NOMBRE Data: 18/02/2026 14:44:39 CET»
    rf"|Signat electr[oò]nicament per:?\s*[^\n]{{0,80}}?\bData:\s*{_FECHA}(?:\s+{_HORA})?(?:\s+CET)?"
    # BOP de Barcelona: «Signat per NOMBRE (REGIDOR/A DELEGAT/DA)»
    rf"|Signat (?:electr[oò]nicament )?per\s+(?:[{_MAY}][\w’'.·-]*\s+){{1,7}}\([^)\n]{{0,80}}\)"
    # BOP de Tarragona: «SIGNAT ELECTRÒNICAMENT PER: NOMBRE - DNI ** (TCAT) el dia 14/08/2026 a les 13:51:57»
    rf"|(?:SIGNAT ELECTR[OÒ]NICAMENT PER:?\s*)?(?:[{_MAY}][\w’'.·-]*\s+){{1,7}}-\s+DNI\s+\*+\s+\(TCAT\)\s+el dia\s+{_FECHA}"
    rf"(?:\s+a les\s+{_HORA})?")


def sin_pies_de_firma(texto: str) -> str:
    if "irma" not in texto and "ignat" not in texto and "IRMA" not in texto and "IGNAT" not in texto:
        return texto
    return " ".join(RE_PIE_FIRMA.sub(" ", texto).split())


def tiene_nombre_de_persona(texto: str) -> bool:
    t = texto or ""
    return (any(_es_persona(m) for m in RE_TRATAMIENTO.finditer(t))
            or any(_es_designado(m) for r in RE_DESIGNADO for m in r.finditer(t))
            or _nombre_suelto(t) or _apellidos_y_nombre(t) or _entrada_de_lista(t))


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


# Frases de un párrafo: se corta tras «.» o «;» precedido de dos letras o cifras, salvo tras un tratamiento o una
# abreviatura («Sra. Puig», «Fdo. Juan», «núm. 5»), para no separar un nombre de su apellido
RE_FIN_FRASE = re.compile(r"(?<=[a-záéíóúñüàèòçï0-9)»”]{2}[.;])\s+(?=[^\s])")
ABREVIATURAS = {"sr.", "sra.", "sres.", "sras.", "srta.", "dr.", "dra.", "dna.", "dña.", "excmo.", "excma.", "ilmo.",
                "ilma.", "fdo.", "fco.", "sto.", "sta.", "num.", "núm.", "art.", "arts.", "pag.", "pág.", "avda.",
                "pza.", "ctra.", "urb.", "admon.", "adm.", "dpto.", "depto.", "aptdo.", "tfno.", "tel.", "etc.", "vid.",
                "cfr.", "sr;", "mr.", "mrs.", "prof.", "profa.", "lic.", "ldo.", "lda.", "ing.", "arq.", "secr.",
                "pres.", "vda.", "hno.", "hna.", "fray.", "sor."}
PARRAFO_LARGO = 300


def frases(parrafo: str) -> list[str]:
    trozos, inicio = [], 0
    for m in RE_FIN_FRASE.finditer(parrafo):
        palabra = parrafo[:m.start()].rsplit(None, 1)[-1].lower()
        if palabra in ABREVIATURAS or _sin_tildes(palabra) in ABREVIATURAS:
            continue
        trozos.append(parrafo[inicio:m.start()])
        inicio = m.end()
    trozos.append(parrafo[inicio:])
    return [t for t in trozos if t.strip()]


def _con_datos(p: str) -> bool:
    return bool(RE_DOCUMENTO.search(p) or tiene_nombre_de_persona(p))


def _firma_tras_cargo(anterior: str, parrafo: str) -> bool:
    """«El vicerrector de Personal Docente e Investigador,» y en el párrafo siguiente solo «NOMBRE APELLIDO APELLIDO.»:
    la firma, aunque el nombre de pila no sea de los frecuentes."""
    if not anterior or anterior.rstrip()[-1:] not in ",:" or not any(CARGOS.match(_nucleo(w)) for w in anterior.split()):
        return False
    nucleos = [_nucleo(w) for w in parrafo.split()]
    return 2 <= len(nucleos) <= 6 and all(RE_PALABRA_NOMBRE.match(n) or n.lower() in PARTICULAS or RE_INICIAL.match(n)
                                          for n in nucleos if n) and not CARGOS.match(nucleos[0])


def parrafos_seguros(parrafos: list[str]) -> tuple[list[str], int]:
    """Párrafos sin documentos ni nombres de personas y número de párrafos retirados. Un párrafo largo (por ejemplo
    un anuncio entero extraído de un PDF sin saltos de párrafo) no se retira entero: se quitan solo sus frases con
    datos de personas (la firma, un tribunal) y cuenta como retirado."""
    guardados, omitidos, anterior = [], 0, ""
    for p in parrafos:
        p = sin_pies_de_firma(p) if p else p
        if not p:
            continue
        anterior, previo = p, anterior
        if not _con_datos(p) and not _firma_tras_cargo(previo, p):
            guardados.append(p)
            continue
        omitidos += 1
        if len(p) > PARRAFO_LARGO:
            resto = [f for f in frases(p) if not _con_datos(f)]
            if resto and not _con_datos(" ".join(resto)):
                guardados.append(" ".join(resto))
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

