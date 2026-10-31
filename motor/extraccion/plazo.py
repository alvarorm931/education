"""Plazo de presentación de solicitudes a partir del texto de una convocatoria (cualquier boletín).

Formas verificadas en convocatorias reales del BOE (2025-2026) de la AGE, comunidades y universidades:
  «El plazo de presentación de solicitudes será de veinte días hábiles contados a partir del día siguiente al de la
   publicación de esta convocatoria en el «Boletín Oficial del Estado».»
  «Las solicitudes se presentarán en el plazo de veinte días naturales, contados a partir del siguiente al de la
   publicación del presente concurso en el «Boletín Oficial del Estado»...»
  «La presentación de solicitudes se hará en el plazo de los quince días hábiles siguientes a la publicación...»
  «El plazo para la presentación de solicitudes de participación es del 28 de octubre al 24 de noviembre de 2025,
   ambos incluidos.»  (fechas exactas)
  «La presentación de solicitudes deberá realizarse en el plazo de veinte días hábiles contados a partir del día
   1 de octubre de 2026.»  (inicio explícito)

Lenguas: castellano, catalán/valenciano («termini de presentació de sol·licituds ... 20 dies hàbils ... a partir de
l'endemà de la publicació») y gallego («prazo ... vinte días hábiles ... do día seguinte ao da publicación»).

Reglas:
  - Se buscan frases con «plazo» (termini, prazo), «solicitud»/«instancia» y una duración o un intervalo de fechas.
  - El boletín desde el que cuenta se lee entre comillas, sin comillas («en el Diari Oficial de la Generalitat de
    Catalunya») o por sus siglas (BOE, DOGC, BOPB...): el primero que sigue a «publicación» tras la duración, con
    los que vayan unidos a él («en el DOGC y en el BOE»: depende de los dos).
  - Se descartan las que hablan de otros plazos (subsanación, alegaciones, recursos, renuncias, presentación de
    documentación tras superar el proceso, toma de posesión...).
  - El fin solo se calcula si el plazo cuenta desde la publicación en el boletín cuya fecha se conoce (el propio)
    o desde una fecha escrita. Si cuenta desde otro boletín, se guarda la frase y se deja sin fecha de fin.
  - La fecha calculada es ESTIMADA (festivos nacionales); la escrita en el texto es exacta.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from motor.boe.clasificar import normalizar
from motor.extraccion.texto_es import MESES, numero
from motor.calendario import etiqueta, fin_de_plazo, fin_de_plazo_meses

VERSION = "plazo_general_v5"  # v5 (31/10/2026): frases sin «plazo» o sin «solicitud» que cuentan desde la
# publicación de la convocatoria; v4: frases partidas tras «Sra.», «veinte (20) días», fin con fecha
# v3 (30/10/2026): festivos de la comunidad del convocante

L = r"a-záéíóúñàèòïüç·"  # letras de castellano, catalán y gallego
RE_FRASE = re.compile(r"(?<=[.;])\s+(?=[«(A-ZÁÉÍÓÚÑÀÈÒ0-9])")
RE_DIAS = re.compile(
    rf"(?P<n>\d{{1,3}}|[{L}]+(?:-i-[{L}]+)?(?:\s+[ye]\s+[{L}]+)?)(?:\s*\(\d{{1,3}}\))?\s+(?:d[ií]as|dies)\s+"
    r"(?P<tipo>h[aáà]biles|h[aà]bils|feiners|naturales|naturals|naturais)", re.IGNORECASE)
RE_MESES = re.compile(r"\b(?P<n>un|una|unha|dos|dous|dues|duas|tres|cuatro|quatre|catro|seis|sis|\d{1,2})\s+mes(?:es|os)?\b",
                      re.IGNORECASE)
_DE = r"(?:\s+de\s+|\s+d[\'’]\s*)"  # «de octubre», «d'octubre»
RE_INTERVALO = re.compile(
    rf"\b(?:del?|des\s+del|do)\s+(?:d[ií]a\s+)?(?P<d1>\d{{1,2}})(?:{_DE}(?P<m1>[{L}]+))?(?:\s+de\s+(?P<a1>\d{{4}}))?\s+"
    rf"(?:al|hasta\s+el|fins\s+al|fins\s+el|ao|ata\s+o)\s+(?:d[ií]a\s+)?(?P<d2>\d{{1,2}}){_DE}(?P<m2>[{L}]+)"
    r"(?:\s+de\s+(?P<a2>\d{4}))?", re.IGNORECASE)
RE_INICIO_EXPLICITO = re.compile(
    rf"(?:a\s+partir\s+del|desde\s+el|des\s+del|a\s+partir\s+do|desde\s+o)\s+d[ií]a\s+(?P<d>\d{{1,2}}){_DE}(?P<m>[{L}]+)"
    r"(?:\s+de\s+(?P<a>\d{4}))?", re.IGNORECASE)
RE_FIN_EXPLICITO = re.compile(
    r"\b(?:finaliza\w*|finalitza\w*|termina\w*|concluy\w*|concluir\w*|conclou\w*|vence\w*|remata\w*|acabar[aà]\w*)"
    rf"[^.;]{{0,60}}?\b(?:el|o)\s+(?:d[ií]a\s+)?(?P<d>\d{{1,2}}){_DE}(?P<m>[{L}]+)(?:\s+de\s+(?P<a>\d{{4}}))?",
    re.IGNORECASE)
RE_BOLETIN = re.compile(r"[«\"“](?P<b>(?:Boletín|Bolet[ií]n|Diario|Diari|Butlletí)[^»\"”]{3,80})[»\"”]")
# Palabras que empiezan la frase siguiente cuando el PDF perdió el punto («… de la Provincia de Teruel Se adjuntan…»)
_COMIENZOS_DE_FRASE = (r"(?:Se|En|Contra|Que|Para|Por|Con|Asimismo|Dich[oa]s?|Lo|Si|No|Tras|Durante|Mediante|Cuando|"
                       r"Igualmente|También|Esta|Este|Estas|Estos|Una?|Es|Será|Serán|Quienes|Los\s+aspirantes|"
                       r"Las\s+(?:bases|solicitudes|instancias|personas))\b")
# Nombre del boletín sin comillas, como lo escriben muchos boletines autonómicos y provinciales
RE_BOLETIN_LIBRE = re.compile(
    r"\b(?P<b>(?:Bolet[ií]n|Diario|Diari|Butllet[ií])\s+Oficial"
    r"(?:\s+(?:de\s+la|de\s+las|de\s+les|de\s+los|del|dels|de|da|do)?\s*(?!" + _COMIENZOS_DE_FRASE + r")"
    r"[A-ZÁÉÍÓÚÑÀÈÒ][\wÀ-ÿ·'’/-]*"
    r"(?:\s+(?:de|del|la|las|les|los|i|y)\b)*)+)")
SIGLAS = {
    "BOE": "Boletín Oficial del Estado", "DOGC": "Diari Oficial de la Generalitat de Catalunya",
    "DOGV": "Diari Oficial de la Generalitat Valenciana", "DOCV": "Diari Oficial de la Comunitat Valenciana",
    "DOG": "Diario Oficial de Galicia", "BOJA": "Boletín Oficial de la Junta de Andalucía",
    "BOCM": "Boletín Oficial de la Comunidad de Madrid", "BOCYL": "Boletín Oficial de Castilla y León",
    "BOA": "Boletín Oficial de Aragón", "DOE": "Diario Oficial de Extremadura",
    "BORM": "Boletín Oficial de la Región de Murcia", "BOPV": "Boletín Oficial del País Vasco",
    "BOIB": "Butlletí Oficial de les Illes Balears", "DOCM": "Diario Oficial de Castilla-La Mancha",
    "BOME": "Boletín Oficial de la Ciudad de Melilla", "BOCCE": "Boletín Oficial de la Ciudad de Ceuta",
    "BOPB": "Butlletí Oficial de la Província de Barcelona",
}
RE_SIGLAS = re.compile(r"\b(" + "|".join(sorted(SIGLAS, key=len, reverse=True)) + r")\b")
RE_DESDE_PUBLICACION = re.compile(
    r"(?:siguiente|siguientes)\s+(?:al?\s+)?(?:de\s+)?(?:la\s+)?(?:fecha\s+de\s+)?(?:su\s+)?(?:la\s+)?publicaci[oó]n|"
    r"desde\s+(?:el\s+d[ií]a\s+)?(?:siguiente\s+)?(?:a|al)?\s*(?:la\s+)?(?:su\s+)?publicaci[oó]n|"
    r"endem[aà]\s+(?:de\s+la\s+|de\s+)?(?:seva\s+|la\s+seva\s+)?publicaci[oó]|"
    r"seg[uü]ents?\s+(?:al|a\s+la|a)\s+(?:de\s+la\s+)?(?:seva\s+)?publicaci[oó]|"
    r"seguinte\s+(?:ao|á|a)\s+(?:da\s+|de\s+)?(?:súa\s+|sua\s+)?publicaci[oó]n", re.IGNORECASE)

EXCLUIR = ("subsan", "esmen", "emenda", "renuncia", "recurso de", "recurso potestativo", "recurso contencioso",
           "interponer recurso", "recurs de", "recurs potestatiu", "recurs contencios", "demanda", "reclamacion",
           "reclamacio", "legacion", "han superado", "han superat", "superado la fase", "superat la fase",
           "expirado el plazo", "finalizado el plazo", "terminado el plazo", "concluido el plazo",
           "finalitzat el termini", "expirat el termini", "lista provisional", "listas provisionales",
           "llista provisional", "llistes provisionals", "toma de posesion", "presa de possessio", "justificacion",
           "justificacio", "acreditativ", "nombramiento", "nomenament", "nomeamento", "no implica nuevo",
           "plazo maximo", "termini maxim", "prazo maximo", "periodo de practicas", "periode de practiques",
           "aportar la documentacion", "aportar la documentacio", "desempleadas durante", "presentar la documentacion",
           "presentar la documentacio", "dentro del plazo de presentacion de instancias y", "declaracion responsable",
           "declaracio responsable", "fecha de finalizacion del plazo", "finalizacion del plazo", "terminacion del plazo",
           "una vez recibidas las solicitudes", "solicitudes de revision", "solicitud de revision", "plazo para resolver",
           "plazo de resolucion", "plazo maximo para resolver", "plazo de vigencia", "periodo de vigencia", "vigencia de la bolsa", "vigencia de las bolsas", "vigencia de la lista", "termini per resoldre",
           "sollicituds de revisio", "sol·licituds de revisio")
PREFERIR = ("presentacion de solicitudes", "presentacion de las solicitudes", "solicitudes se presentaran",
            "solicitudes deberan presentarse", "presentacion de instancias", "plazo de presentacion",
            "presentacio de sol·licituds", "presentacio de les sol·licituds", "presentacio d'instancies",
            "termini de presentacio", "prazo de presentacion")


# Abreviaturas tras las que un punto no acaba la frase («se dirigirán a la Sra. Rectora Magnífica… y se presentarán en el
# plazo de veinte días hábiles»: partida ahí, la frase del plazo no decía de qué era, BOE-A-2026-8173)
RE_ABREVIATURA_FINAL = re.compile(
    r"(?i)(?:^|[\s(«\"“])(?:sr|sra|sres|sras|srs|excmo|excma|excmos|ilmo|ilma|ilmos|iltre|d|dña|dª|dr|dra|dres|mgfco|mgfca|"
    r"magfco|magfca|magnfco|núm|num|nº|art|arts|apdo|apdos|avda|av|pág|págs|pag|ej|etc|sig|ss|vol|cap|ap|aptdo|cía|"
    r"[a-záéíóúñ])\.$")


# Tratamientos y abreviaturas tras los que un salto de línea no acaba la frase («dirigidas al Sr.⏎Alcalde…»); las
# letras sueltas no, porque «… del Anexo I.⏎» acaba un párrafo.
RE_ABREVIATURA_DE_LINEA = re.compile(
    r"(?i)(?:^|[\s(«\"“])(?:sr|sra|sres|sras|srs|excmo|excma|excmos|ilmo|ilma|ilmos|iltre|dña|dª|dr|dra|dres|núm|num|"
    r"nº|art|arts|apdo|apdos|avda|pág|págs)\.$")


def frases(texto: str) -> list[str]:
    out: list[str] = []
    for p in (texto or "").split("\n"):
        linea: list[str] = []  # las letras sueltas solo juntan trozos de la misma línea
        for t in (f.strip() for f in RE_FRASE.split(p) if f.strip()):
            if linea and linea[-1][-1:] == "." and RE_ABREVIATURA_FINAL.search(linea[-1][-12:]) \
                    and not linea[-1].endswith("etc."):
                linea[-1] = linea[-1] + " " + t
            elif not linea and out and RE_ABREVIATURA_DE_LINEA.search(out[-1][-12:]):
                out[-1] = out[-1] + " " + t
            else:
                linea.append(t)
        out += linea
    return out


def _fecha(d: str, m: str | None, a: str | None, referencia: date) -> date | None:
    mes = MESES.get(normalizar(m or ""))
    if not mes:
        return None
    anio = int(a) if a else referencia.year
    try:
        return date(anio, mes, int(d))
    except ValueError:
        return None


# Lo que se publica y abre el plazo («desde la publicación de la convocatoria / de las bases / de este anuncio…»)
RE_PUBLICACION_DE = re.compile(
    r"publicaci[oó]n?\s+(?:\w+\s+){0,4}?(?:de\s+la\s+convocatoria|de\s+las\s+bases|del\s+anuncio|de\s+este\s+anuncio|"
    r"de\s+esta\s+resoluci[oó]n|de\s+la\s+presente|del\s+presente|del\s+extracto|de\s+la\s+resoluci[oó]n\s+de\s+convocatoria|"
    r"de\s+la\s+convocat[oò]ria|de\s+les\s+bases|de\s+l'anunci|d'aquest\s+anunci|d'aquesta\s+resoluci[oó]|del\s+present|"
    r"da\s+convocatoria|das\s+bases|deste\s+anuncio|desta\s+resoluci[oó]n)|a\s+esta\s+publicaci[oó]n|su\s+publicaci[oó]n|"
    r"la\s+seva\s+publicaci[oó]|s[uú]a\s+publicaci[oó]n", re.IGNORECASE)


RE_DONDE_DICE = re.compile(r"(?i)\b(?:donde\s+(?:dice|pone|figura)|onde\s+d[ií]|on\s+diu|on\s+hi\s+diu)\b")
RE_DEBE_DECIR = re.compile(r"(?i)\b(?:debe\s+decir|deber[aá]\s+decir|ha\s+de\s+dir|debe\s+dicir|ha\s+de\s+dicir|"
                           r"debe\s+figurar|queda\s+redactad)")


def _texto_corregido(texto: str, f: str, i: int) -> bool:
    """La frase (que empieza en la posición i del texto) es el texto que una corrección sustituye («Donde dice:
    “El plazo… en el BOE”. Debe decir: …»)."""
    if i < 0:
        return False
    antes = texto[max(0, i - 120):i + min(len(f), 200)]
    ultimo_dice = max((m.end() for m in RE_DONDE_DICE.finditer(antes)), default=-1)
    ultimo_debe = max((m.end() for m in RE_DEBE_DECIR.finditer(antes)), default=-1)
    return ultimo_dice > ultimo_debe


def _candidata(f: str) -> int:
    """0 si la frase no es del plazo de solicitudes. 1 si dice plazo y solicitud (o instancia); 2 si dice solicitud
    (o presentar) sin la palabra plazo («disponen de 15 días naturales para presentar la solicitud, contados a partir
    del día siguiente a la publicación de esta resolución»); 3 si dice plazo sin decir de qué, pero cuenta desde la
    publicación de la convocatoria o de las bases («El plazo es de quince días hábiles, a contar a partir del día
    siguiente al de la publicación de la convocatoria en el BOIB», tras el título «Plazo»)."""
    n = normalizar(f).replace("l·l", "l·l").replace("l.l", "l·l")
    m = RE_DIAS.search(f) or RE_MESES.search(f) or RE_INTERVALO.search(f) or RE_FIN_EXPLICITO.search(f)
    if not m:
        return 0
    # Lo que excluye se mira hasta poco después del plazo: una frase larga puede seguir con otra cosa («… y contendrán
    # los requisitos… de la provisión de plazas de nombramiento discrecional», CGPJ)
    ventana = normalizar(f[:m.end() + 200]).replace("l.l", "l·l")
    if any(x in ventana for x in EXCLUIR):
        return 0
    plazo = any(x in n for x in ("plazo", "termini", "prazo"))
    solicitud = any(x in n for x in ("solicitud", "instancia", "sol·licitud", "sollicitud", "instanci",
                                     "plazo de inscripcion", "termini d'inscripcio", "prazo de inscricion"))
    if plazo and solicitud:
        return 1
    # Sin una de las dos palabras, solo si no habla de otra cosa (documentación de los aprobados, recursos,
    # contratos, licitaciones…) y cuenta desde la publicación de la convocatoria (muestra del 31/10/2026)
    if any(x in ventana for x in EXCLUIR_SIN_SOLICITUD):
        return 0
    publicacion = RE_PUBLICACION_DE.search(f)
    if solicitud:
        return 2 if publicacion else 0
    return 3 if plazo and RE_PUBLICACION_CONVOCATORIA.search(f) else 0


EXCLUIR_SIN_SOLICITUD = ("documentaci", "documents", "recurr", "reposici", "recus", "contrato", "contracte", "licitaci",
                         "expresiones de interes", "cese", "opcion", "errores", "acredit", "juramento", "formalizaci",
                         "incorporaci", "alega", "reclama", "subsana", "toma de", "presa de", "tribunal", "aprobad",
                         "seleccionad", "propuest", "lista", "relacion", "llista", "relacio")
RE_PUBLICACION_CONVOCATORIA = re.compile(
    r"publicaci[oó]n?\s+(?:\w+\s+){0,3}?(?:de\s+(?:la|esta|la\s+presente)\s+convocatoria|de\s+las\s+bases|del\s+extracto|"
    r"del\s+anuncio\s+de\s+(?:la\s+)?convocatoria|de\s+la\s+convocat[oò]ria|de\s+les\s+bases|"
    r"de\s+l'anunci\s+de\s+(?:la\s+)?convocat[oò]ria|da\s+convocatoria|das\s+bases)", re.IGNORECASE)


PARTICULAS_FINALES = re.compile(r"(?:\s+(?:de|del|la|las|les|los|i|y))+$")


RE_UNION = re.compile(r"^[\s»\"”,]*(?:o|y|i|e|u|ou|y/o|o\s+bien)\s+(?:en\s+|a\s+)?(?:el|la|al|o|a)?\s*[«\"“]?$",
                      re.IGNORECASE)


# Los nombres genéricos escritos en minúscula («… en el boletín oficial de la provincia», «… del estado»)
RE_BOLETIN_GENERICO = re.compile(
    r"\b(?:(?P<estado>bolet[ií]n\s+oficial\s+del\s+estado)|(?P<prov>bolet[ií]n\s+oficial\s+de\s+la\s+provincia|"
    r"butllet[ií]\s+oficial\s+de\s+la\s+prov[ií]ncia|bolet[ií]n\s+oficial\s+da\s+provincia))\b", re.IGNORECASE)


def _menciones(f: str) -> list[tuple[int, int, str]]:
    """Boletines citados en la frase, con su posición: entre comillas, sin comillas o por sus siglas."""
    vistos: dict[str, tuple[int, int, str]] = {}
    for m in list(RE_BOLETIN.finditer(f)) + list(RE_BOLETIN_LIBRE.finditer(f)):
        nombre = PARTICULAS_FINALES.sub("", " ".join(m.group("b").split()))
        k = normalizar(nombre)
        if k not in vistos or m.start() < vistos[k][0]:
            vistos[k] = (m.start(), m.end(), nombre)
    for m in RE_SIGLAS.finditer(f):
        vistos.setdefault(normalizar(SIGLAS[m.group(1)]), (m.start(), m.end(), SIGLAS[m.group(1)]))
    for m in RE_BOLETIN_GENERICO.finditer(f):
        if any(i < m.end() and m.start() < j for i, j, _ in vistos.values()):
            continue  # ya está con su nombre completo
        nombre = "Boletín Oficial del Estado" if m.group("estado") else "Boletín Oficial de la Provincia"
        vistos.setdefault(normalizar(nombre) + f"@{m.start()}", (m.start(), m.end(), nombre))
    return sorted(vistos.values())


def _boletines(f: str, desde: int = 0) -> list[str]:
    """Boletín desde el que cuenta el plazo. Si tras la duración se lee «publicación ... en el X», es X (y los que
    vayan unidos a él: «en el BOE o en el BOJA»); si no, todos los citados en la frase. El fin solo se calcula
    si todos son el propio."""
    menciones = _menciones(f)
    pub = re.compile(r"publicaci[oó]n?", re.IGNORECASE).search(f, desde)
    if pub:
        siguientes = [m for m in menciones if pub.start() < m[0] <= pub.end() + 160]
        if siguientes:
            elegidos = [siguientes[0]]
            for m in siguientes[1:]:
                if RE_UNION.match(f[elegidos[-1][1]:m[0]]):
                    elegidos.append(m)
                else:
                    break
            return list(dict.fromkeys(n for _, _, n in elegidos))
    # sin «publicación» detrás de la duración, los que se citan detrás de ella («… de 20 dies hàbils a partir de
    # l'endemà del present anunci en el DOGC», tras «Les bases s'han publicat… al Butlletí Oficial de la Província»)
    despues = [m for m in menciones if m[0] >= desde]
    return list(dict.fromkeys(n for _, _, n in (despues or menciones)))


def extraer_plazo(texto: str, publicacion: str, boletin_propio: str | tuple[str, ...],
                  comunidad: str | None = None) -> dict | None:
    """Plazo de solicitudes del texto.

    publicacion: fecha ISO del boletín propio; boletin_propio: su nombre (o sus nombres: «Diari Oficial de la
    Generalitat de Catalunya» y «Diario Oficial de la Generalitat de Cataluña» son el mismo); comunidad: código INE
    de la comunidad del convocante, para contar con sus festivos.
    """
    pub = date.fromisoformat(publicacion)
    propios = {normalizar(b) for b in ((boletin_propio,) if isinstance(boletin_propio, str) else boletin_propio)}
    candidatas, cursor = [], 0
    for f in frases(texto):
        i = texto.find(f[:60], cursor)
        cursor = i + 1 if i >= 0 else cursor
        corregida = False
        if RE_DONDE_DICE.search(f) and (debe := list(RE_DEBE_DECIR.finditer(f))):
            f, corregida = f[debe[-1].end():].lstrip(" :“\"«"), True  # «Donde dice: … debe decir: “…”» en una frase
        if (k := _candidata(f)) and (corregida or not _texto_corregido(texto, f, i)):
            candidatas.append((f, k))
    if not candidatas:
        return None
    candidatas.sort(key=lambda fk: (fk[1], 0 if any(x in normalizar(fk[0]) for x in PREFERIR) else 1))
    # Por clase de frase (ver _candidata): la primera que da la fecha de fin; si ninguna, la primera que da el plazo.
    # Una frase de una clase peor solo cuenta si ninguna de las mejores da el plazo
    # La primera frase que da la fecha de fin o dice desde qué boletín cuenta: si cuenta desde otro (el BOE), no
    # tiene fecha de fin a propósito y no se busca otra frase que la dé («solicitudes de revisión… tres días» o «el
    # plazo para resolver las solicitudes» no son el plazo; revisión del 31/10/2026). Las que no dicen desde cuándo
    # cuentan, solo si ninguna otra lo dice
    for clase in (1, 2, 3):
        primera = None
        for f, _ in [fk for fk in candidatas if fk[1] == clase][:8]:
            r = _plazo_de_frase(f, pub, propios, comunidad)
            if not r:
                continue
            if r.get("fin_estimado") or r.get("cuenta_desde"):
                return r
            primera = primera or r
        if primera:
            return primera
    return None


# Nombre genérico del boletín propio, sin la provincia o la comunidad («… desde el siguiente al de la publicación en el
# Boletín Oficial de la Provincia», en el propio BOP)
GENERICOS_PROPIOS = ("boletin oficial de la provincia", "butlleti oficial de la provincia", "boletin oficial da provincia",
                     "diari oficial de la generalitat", "boletin oficial de la comunidad")


def _es_propio(nombre: str, propios: set[str]) -> bool:
    """El boletín citado es el propio: con el mismo nombre, con otra forma del nombre («Boletín Oficial Cantabria»,
    «Boletín Oficial de la Junta de Castilla y León») o con el nombre genérico de su clase («Boletín Oficial de la
    Provincia» en un BOP). (31/10/2026: unos 600 procesos de 2025-2026 se quedaban sin fecha de fin por eso.)"""
    n = normalizar(nombre)
    if n in propios:
        return True
    from motor.procesos import fuente_de_boletin  # aquí: procesos importa la extracción
    f = fuente_de_boletin(nombre)
    if f and any(fuente_de_boletin(p) == f for p in propios):
        return True
    return n in GENERICOS_PROPIOS and any(p.startswith(n + " ") for p in propios)


def _plazo_de_frase(f: str, pub: date, propios: set[str], comunidad: str | None) -> dict | None:
    res: dict = {"cita": f, "metodo": VERSION}

    m = RE_INTERVALO.search(f)
    if m:
        fin = _fecha(m.group("d2"), m.group("m2"), m.group("a2"), pub)
        inicio = _fecha(m.group("d1"), m.group("m1") or m.group("m2"), m.group("a1") or m.group("a2"), pub)
        if fin and inicio and inicio <= fin:
            res.update({"tipo": "fechas", "inicio": inicio.isoformat(), "fin_estimado": fin.isoformat(),
                        "fin_exacto": True, "cuenta_desde": "fechas del texto"})
            return res

    m = RE_FIN_EXPLICITO.search(f)
    if m:
        fin = _fecha(m.group("d"), m.group("m"), m.group("a"), pub)
        if fin and fin >= pub:
            res.update({"tipo": "fechas", "fin_estimado": fin.isoformat(), "fin_exacto": True,
                        "cuenta_desde": "fechas del texto"})
            d0 = RE_DIAS.search(f)
            if d0 and numero(d0.group("n")):
                res["dias"] = numero(d0.group("n"))
            return res

    dias = next((d for d in RE_DIAS.finditer(f) if numero(d.group("n"))), None)
    meses = RE_MESES.search(f) if not dias else None
    if dias:
        res.update({"dias": numero(dias.group("n")),
                    "tipo": "habiles" if normalizar(dias.group("tipo")) in ("habiles", "habils", "feiners") else "naturales"})
    elif meses and numero(meses.group("n")):
        res.update({"meses": numero(meses.group("n")), "tipo": "meses"})
    else:
        return None

    inicio_explicito = RE_INICIO_EXPLICITO.search(f)
    boletines = _boletines(f, (dias or meses).end())
    if inicio_explicito:
        inicio = _fecha(inicio_explicito.group("d"), inicio_explicito.group("m"), inicio_explicito.group("a"), pub)
        if not inicio:
            return res
        base, res["cuenta_desde"] = inicio - timedelta(days=1), "fecha del texto"
        res["inicio"] = inicio.isoformat()
    elif boletines:
        res["cuenta_desde"] = " o ".join(boletines)
        if not all(_es_propio(b, propios) for b in boletines):
            return res  # cuenta desde otro boletín (o desde el último de varios): sin fecha de fin
        base = pub
    elif RE_DESDE_PUBLICACION.search(f):
        res["cuenta_desde"] = "su publicación"
        base = pub
    else:
        return res
    if res["tipo"] == "meses":
        fin = fin_de_plazo_meses(base, res["meses"], comunidad)
    else:
        fin = fin_de_plazo(base, res["dias"], res["tipo"], comunidad)
    res.update({"fin_estimado": fin.isoformat(), "fin_exacto": False, "calendario": etiqueta(base, comunidad)})
    return res
