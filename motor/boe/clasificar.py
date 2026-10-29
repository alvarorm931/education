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
    ("correccion", ("correccion de error", "correccion de las bases")),
    ("admitidos", ("admitidos y excluidos", "admitidas y excluidas", "lista provisional", "lista definitiva",
                   "relacion provisional", "relacion definitiva de aspirantes admitidos")),
    ("aprobados", ("aprobados", "aprobadas", "superado el proceso", "han superado", "seleccionados", "seleccionadas")),
    ("nombramiento", ("se nombra", "nombramiento", "nombran funcionari", "toma de posesion")),
    ("tribunal", ("tribunal calificador", "composicion del tribunal", "comision de seleccion", "organo de seleccion")),
    ("examen", ("fecha de celebracion", "fecha, hora y lugar", "lugar, fecha y hora", "primer ejercicio")),
    ("convocatoria", ("se convoca", "convocatoria", "convoca proceso", "proceso selectivo", "referente a la convocatoria")),
    ("bases", ("bases",)),
]

REGLAS_MODALIDAD: list[tuple[str, tuple[str, ...]]] = [
    ("estabilizacion", ("estabilizacion",)),
    ("promocion_interna", ("promocion interna",)),
    ("concurso_oposicion", ("concurso-oposicion", "concurso oposicion")),
    ("libre_designacion", ("libre designacion",)),
    ("concurso", ("concurso de meritos", "concurso especifico", "concurso general", "por concurso")),
    ("oposicion", ("oposicion",)),
    ("bolsa", ("bolsa de empleo", "bolsa de trabajo")),
]


def _primera(reglas: list[tuple[str, tuple[str, ...]]], texto: str) -> str | None:
    for nombre, claves in reglas:
        if any(c in texto for c in claves):
            return nombre
    return None


ENTIDAD = (
    r"Ayuntamiento|Diputaci[oó]n Provincial|Diputaci[oó]n Foral|Diputaci[oó]n|Cabildo Insular|"
    r"Consell Insular|Consell Comarcal|Consejo Comarcal|Comarca|Mancomunidad|Consorcio|"
    r"Entidad Local Menor|Junta Vecinal|[ÁA]rea Metropolitana|Organismo Aut[oó]nomo|Patronato|Instituto Municipal"
)
RE_CONVOCANTE = re.compile(
    rf"\b(?P<tipo>{ENTIDAD})\s+(?:de\s+la\s+|de\s+los\s+|de\s+las\s+|del\s+|de\s+|d')?(?P<nombre>[^,(]+?)\s*\((?P<provincia>[^)]+)\)"
)
RE_PLAZAS = re.compile(
    r"(?:proveer|cubrir|provisi[oó]n de|provisi[oó]n,? de|selecci[oó]n de)\s+(?:mediante\s+\S+\s+)?"
    r"(?P<n>\d+|[a-záéíóúñ]+)\s+plazas?\b",
    re.IGNORECASE,
)
RE_PUESTO = re.compile(r"\bplazas?\s+de\s+(?P<puesto>[^.;]+?)(?:,|\.|;| mediante| por el sistema| en turno|$)", re.IGNORECASE)


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
        "convocante": None,
        "plazas": None,
        "plazas_texto": None,
        "puesto": None,
        "extraccion": "reglas",
        "pendiente_revision": [],
    }

    m = RE_CONVOCANTE.search(titulo)
    if m:
        resultado["convocante"] = {
            "tipo": m.group("tipo"),
            "nombre": m.group("nombre").strip(),
            "provincia": m.group("provincia").strip(),
        }
    elif resultado["ambito"] == "local":
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

    if resultado["tipo_acto"] == "convocatoria":
        if resultado["plazas"] is None:
            resultado["pendiente_revision"].append("plazas")
        if resultado["puesto"] is None:
            resultado["pendiente_revision"].append("puesto")
    return resultado
