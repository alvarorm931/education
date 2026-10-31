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

VERSION = "plazo_general_v4"  # v4 (31/10/2026): frases partidas tras «Sra.», «veinte (20) días», fin con fecha
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
    r"(?:finaliza\w*|finalitza\w*|termina\w*|concluy\w*|concluir\w*|conclou\w*|vence\w*|remata\w*|acabar[aà]\w*)"
    rf"[^.;]{{0,60}}?\b(?:el|o)\s+(?:d[ií]a\s+)?(?P<d>\d{{1,2}}){_DE}(?P<m>[{L}]+)(?:\s+de\s+(?P<a>\d{{4}}))?",
    re.IGNORECASE)
RE_BOLETIN = re.compile(r"[«\"“](?P<b>(?:Boletín|Bolet[ií]n|Diario|Diari|Butlletí)[^»\"”]{3,80})[»\"”]")
# Nombre del boletín sin comillas, como lo escriben muchos boletines autonómicos y provinciales
RE_BOLETIN_LIBRE = re.compile(
    r"\b(?P<b>(?:Bolet[ií]n|Diario|Diari|Butllet[ií])\s+Oficial"
    r"(?:\s+(?:de\s+la|de\s+las|de\s+les|de\s+los|del|dels|de|da|do)?\s*[A-ZÁÉÍÓÚÑÀÈÒ][\wÀ-ÿ·'’/-]*"
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
           "una vez recibidas las solicitudes")
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


def frases(texto: str) -> list[str]:
    out = []
    for p in (texto or "").split("\n"):
        trozos = [f.strip() for f in RE_FRASE.split(p) if f.strip()]
        for t in trozos:
            if out and out[-1][-1:] == "." and RE_ABREVIATURA_FINAL.search(out[-1][-12:]) and not out[-1].endswith("etc."):
                out[-1] = out[-1] + " " + t
            else:
                out.append(t)
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


def _candidata(f: str) -> bool:
    n = normalizar(f).replace("l·l", "l·l").replace("l.l", "l·l")
    if not any(x in n for x in ("plazo", "termini", "prazo")):
        return False
    if not any(x in n for x in ("solicitud", "instancia", "sol·licitud", "sollicitud", "instanci")):
        return False
    m = RE_DIAS.search(f) or RE_MESES.search(f) or RE_INTERVALO.search(f) or RE_FIN_EXPLICITO.search(f)
    if not m:
        return False
    # Lo que excluye se mira hasta poco después del plazo: una frase larga puede seguir con otra cosa («… y contendrán
    # los requisitos… de la provisión de plazas de nombramiento discrecional», CGPJ)
    ventana = normalizar(f[:m.end() + 200]).replace("l.l", "l·l")
    return not any(x in ventana for x in EXCLUIR)


PARTICULAS_FINALES = re.compile(r"(?:\s+(?:de|del|la|las|les|los|i|y))+$")


RE_UNION = re.compile(r"^[\s»\"”,]*(?:o|y|i|e|u|ou|y/o|o\s+bien)\s+(?:en\s+|a\s+)?(?:el|la|al|o|a)?\s*[«\"“]?$",
                      re.IGNORECASE)


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
    candidatas = [f for f in frases(texto) if _candidata(f)]
    if not candidatas:
        return None
    candidatas.sort(key=lambda f: 0 if any(x in normalizar(f) for x in PREFERIR) else 1)
    # la primera que da la fecha de fin; si ninguna, la primera que da el plazo
    primera = None
    for f in candidatas[:8]:
        r = _plazo_de_frase(f, pub, propios, comunidad)
        if r and r.get("fin_estimado"):
            return r
        primera = primera or r
    return primera


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
        if not {normalizar(b) for b in boletines} <= propios:
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
