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

Reglas:
  - Se buscan frases con «plazo», «solicitud»/«instancia» y una duración o un intervalo de fechas.
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
from motor.calendario import fin_de_plazo, fin_de_plazo_meses

VERSION = "plazo_general_v1"

RE_FRASE = re.compile(r"(?<=[.;])\s+(?=[«(A-ZÁÉÍÓÚÑ0-9])")
RE_DIAS = re.compile(r"(?P<n>\d{1,3}|[a-záéíóúñ]+(?:\s+y\s+[a-záéíóúñ]+)?)\s+d[ií]as\s+(?P<tipo>h[aá]biles|naturales)",
                     re.IGNORECASE)
RE_MESES = re.compile(r"\b(?P<n>un|una|dos|tres|cuatro|seis|\d{1,2})\s+mes(?:es)?\b", re.IGNORECASE)
RE_INTERVALO = re.compile(
    r"\bdel?\s+(?:d[ií]a\s+)?(?P<d1>\d{1,2})(?:\s+de\s+(?P<m1>[a-záéíóú]+))?(?:\s+de\s+(?P<a1>\d{4}))?\s+"
    r"(?:al|hasta\s+el)\s+(?:d[ií]a\s+)?(?P<d2>\d{1,2})\s+de\s+(?P<m2>[a-záéíóú]+)(?:\s+de\s+(?P<a2>\d{4}))?",
    re.IGNORECASE)
RE_INICIO_EXPLICITO = re.compile(
    r"(?:a\s+partir\s+del|desde\s+el)\s+d[ií]a\s+(?P<d>\d{1,2})\s+de\s+(?P<m>[a-záéíóú]+)(?:\s+de\s+(?P<a>\d{4}))?",
    re.IGNORECASE)
RE_FIN_EXPLICITO = re.compile(
    r"(?:finaliza\w*|termina\w*|concluy\w*|concluir\w*|vence\w*)[^.;]{0,60}?\bel\s+(?:d[ií]a\s+)?(?P<d>\d{1,2})\s+de\s+"
    r"(?P<m>[a-záéíóú]+)(?:\s+de\s+(?P<a>\d{4}))?", re.IGNORECASE)
RE_BOLETIN = re.compile(r"[«\"“](?P<b>(?:Boletín|Bolet[ií]n|Diario|Diari|Butlletí)[^»\"”]{3,80})[»\"”]")
RE_DESDE_PUBLICACION = re.compile(
    r"(?:siguiente|siguientes)\s+(?:al?\s+)?(?:de\s+)?(?:la\s+)?(?:fecha\s+de\s+)?(?:su\s+)?(?:la\s+)?publicaci[oó]n|"
    r"desde\s+(?:el\s+d[ií]a\s+)?(?:siguiente\s+)?(?:a|al)?\s*(?:la\s+)?(?:su\s+)?publicaci[oó]n", re.IGNORECASE)

EXCLUIR = ("subsan", "renuncia", "recurso", "demanda", "reclamacion", "alegacion", "han superado", "superado la fase",
           "expirado el plazo", "finalizado el plazo", "terminado el plazo", "concluido el plazo", "lista provisional",
           "listas provisionales", "toma de posesion", "justificacion", "acreditativ", "nombramiento",
           "no implica nuevo", "plazo maximo", "periodo de practicas", "aportar la documentacion",
           "desempleadas durante", "presentar la documentacion", "dentro del plazo de presentacion de instancias y",
           "declaracion responsable", "fecha de finalizacion del plazo")
PREFERIR = ("presentacion de solicitudes", "presentacion de las solicitudes", "solicitudes se presentaran",
            "solicitudes deberan presentarse", "presentacion de instancias", "plazo de presentacion")


def frases(texto: str) -> list[str]:
    return [f.strip() for p in (texto or "").split("\n") for f in RE_FRASE.split(p) if f.strip()]


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
    n = normalizar(f)
    if "plazo" not in n or not ("solicitud" in n or "instancia" in n):
        return False
    if any(x in n for x in EXCLUIR):
        return False
    return bool(RE_DIAS.search(f) or RE_MESES.search(f) or RE_INTERVALO.search(f))


def _boletines(f: str) -> list[str]:
    nombres = [" ".join(m.group("b").split()) for m in RE_BOLETIN.finditer(f)]
    if re.search(r"\bBOE\b", f):
        nombres.append("Boletín Oficial del Estado")
    return list(dict.fromkeys(nombres))


def extraer_plazo(texto: str, publicacion: str, boletin_propio: str | tuple[str, ...]) -> dict | None:
    """Plazo de solicitudes del texto.

    publicacion: fecha ISO del boletín propio; boletin_propio: su nombre (o sus nombres: «Diari Oficial de la
    Generalitat de Catalunya» y «Diario Oficial de la Generalitat de Cataluña» son el mismo).
    """
    pub = date.fromisoformat(publicacion)
    propios = {normalizar(b) for b in ((boletin_propio,) if isinstance(boletin_propio, str) else boletin_propio)}
    candidatas = [f for f in frases(texto) if _candidata(f)]
    if not candidatas:
        return None
    candidatas.sort(key=lambda f: 0 if any(x in normalizar(f) for x in PREFERIR) else 1)
    f = candidatas[0]
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
                    "tipo": "habiles" if normalizar(dias.group("tipo")) == "habiles" else "naturales"})
    elif meses and numero(meses.group("n")):
        res.update({"meses": numero(meses.group("n")), "tipo": "meses"})
    else:
        return None

    inicio_explicito = RE_INICIO_EXPLICITO.search(f)
    boletines = _boletines(f)
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
        fin = fin_de_plazo_meses(base, res["meses"])
    else:
        fin = fin_de_plazo(base, res["dias"], res["tipo"])
    res.update({"fin_estimado": fin.isoformat(), "fin_exacto": False,
                "calendario": "festivos nacionales (estimado)"})
    return res
