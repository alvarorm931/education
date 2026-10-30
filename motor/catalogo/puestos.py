"""Normalización de puestos: el mismo puesto escrito de muchas formas se reconoce como uno solo.

«Agente de Policía Local», «Policía Local» y «Agente de la Policía Local» -> clave «policia-local».
La denominación original se conserva siempre; la clave sirve para agrupar páginas y estadísticas.

Grupo profesional:
  - si el texto lo dice («grupo A, subgrupo A1», «grupo C2»), se usa ese;
  - si no, en Administración General se deduce de la subescala (RDLeg 781/1986, art. 169: Técnica,
    Gestión, Administrativa, Auxiliar y Subalterna) con la equivalencia de grupos del TREBEP;
  - en el resto se deja sin grupo antes que inventarlo.
"""

from __future__ import annotations

import re
import unicodedata

# Formas equivalentes -> forma canónica (sin tildes, minúsculas, sin marcas de género).
SINONIMOS: dict[str, str] = {
    "agente de policia local": "policia local",
    "agente de la policia local": "policia local",
    "policia": "policia local",
    "policia local y sus auxiliares": "policia local",
    "auxiliar administrativo de administracion general": "auxiliar administrativo",
    "auxiliar de administracion general": "auxiliar administrativo",
    "auxiliar administrativo de la escala de administracion general": "auxiliar administrativo",
    "administrativo de administracion general": "administrativo",
    "tecnico administracion general": "tecnico de administracion general",
    "tecnico superior de administracion general": "tecnico de administracion general",
    "tag": "tecnico de administracion general",
    "tecnico de gestion de administracion general": "tecnico de gestion",
    "tecnico medio de gestion": "tecnico de gestion",
    "trabajador social": "trabajador social",
    "asistente social": "trabajador social",
    "aparejador": "arquitecto tecnico",
    "bombero conductor": "bombero",
    "bombero especialista": "bombero",
    "conserje": "conserje",
    "ordenanza": "ordenanza",
    "auxiliar de policia local": "auxiliar de policia local",
}

# Femenino -> masculino solo para nombres de puesto frecuentes (para agrupar; la denominación original se conserva).
FEMENINOS = {
    "administrativa": "administrativo", "bombera": "bombero", "tecnica": "tecnico", "psicologa": "psicologo",
    "arquitecta": "arquitecto", "educadora": "educador", "trabajadora": "trabajador", "conductora": "conductor",
    "monitora": "monitor", "limpiadora": "limpiador", "operaria": "operario", "veterinaria": "veterinario",
    "inspectora": "inspector", "letrada": "letrado", "ingeniera": "ingeniero", "abogada": "abogado",
    "cocinera": "cocinero", "enfermera": "enfermero", "profesora": "profesor", "maestra": "maestro",
    "directora": "director", "coordinadora": "coordinador", "gestora": "gestor", "informadora": "informador",
    "tramitadora": "tramitador", "encargada": "encargado", "jefa": "jefe", "peona": "peon", "mecanica": "mecanico",
    "economista": "economista", "juridica": "juridico", "sanitaria": "sanitario", "tributaria": "tributario",
    "media": "medio", "oficiala": "oficial", "animadora": "animador", "agentes": "agente", "tesorera": "tesorero",
    "interventora": "interventor", "secretaria": "secretario", "bibliotecaria": "bibliotecario",
    "archivera": "archivero", "delineante": "delineante", "programadora": "programador", "analista": "analista",
}
PALABRAS_VACIAS = {"de", "del", "la", "las", "los", "el", "y", "e", "en", "a", "para", "d", "l", "les", "els",
                   "da", "do", "das", "dos"}
# Catalán/valenciano y gallego -> castellano, palabra a palabra, para que el mismo puesto tenga la misma clave
# («agent de la policia local», «axente da policía local» -> «agente de la policia local» -> «policia local»).
TRADUCCION = {
    "agent": "agente", "agents": "agente", "axente": "agente", "caporal": "cabo", "administratiu": "administrativo",
    "administrativa": "administrativo", "tecnic": "tecnico", "tecnics": "tecnico", "treballador": "trabajador",
    "treballadora": "trabajador", "traballador": "trabajador", "traballadora": "trabajador", "arquitecte": "arquitecto",
    "enginyer": "ingeniero", "enginyera": "ingeniero", "enxeneiro": "ingeniero", "enxeneira": "ingeniero",
    "bomber": "bombero", "bombera": "bombero", "bombeiro": "bombero", "bombeira": "bombero", "conserge": "conserje",
    "conserxe": "conserje", "peo": "peon", "operari": "operario", "operaria": "operario", "serveis": "servicios",
    "servizos": "servicios", "gestio": "gestion", "xestion": "gestion", "administracio": "administracion",
    "mestre": "maestro", "mestra": "maestro", "psicoleg": "psicologo", "psicologa": "psicologo", "infermer": "enfermero",
    "infermera": "enfermero", "arxiver": "archivero", "arxivera": "archivero", "bibliotecari": "bibliotecario",
    "bibliotecaria": "bibliotecario", "netejador": "limpiador", "netejadora": "limpiador", "jardiner": "jardinero",
    "jardinera": "jardinero", "lampista": "fontanero", "paleta": "albanil", "tresorer": "tesorero",
    "tresorera": "tesorero", "secretari": "secretario", "advocat": "abogado", "advocada": "abogado",
    "informatic": "informatico", "delineant": "delineante", "cuiner": "cocinero",
    "cuinera": "cocinero", "ajudant": "ayudante", "vigilant": "vigilante", "mitja": "medio", "mitjana": "medio",
    "persoal": "personal", "condutor": "conductor", "condutora": "conductor", "educadora": "educador",
    "auxiliars": "auxiliar", "oficials": "oficial", "administratives": "administrativo", "administratius": "administrativo",
    "tecniques": "tecnico", "tecnica": "tecnico", "conserges": "conserje", "netejadores": "limpiador", "brigada": "brigada", "socials": "social", "general": "general",
    "policies": "policia", "policia": "policia", "local": "local", "locals": "local", "superiors": "superior",
    "biblioteca": "biblioteca", "escoleta": "escuela infantil", "llar": "escuela", "infants": "infantil",
}

GRUPO_POR_SUBESCALA_AG = {"tecnica": "A1", "gestion": "A2", "administrativa": "C1", "auxiliar": "C2",
                          "subalterna": "AP"}

RE_GENERO = re.compile(r"(?<=\w)/(?:a|as|o|os|la|las|va|ra|ora|era|ana|ària|aria|essa|ina|iva|ica|ua|ra|na)\b|"
                       r"\((?:a|as|o|os)\)|(?<=\w)\(a\)")
RE_ESPECIALIDAD = re.compile(r"\(([^)]*especialidad[^)]*)\)", re.IGNORECASE)
RE_GRUPO = re.compile(r"\b(?:sub)?grupo\s+(A1|A2|B|C1|C2|AP|E)\b", re.IGNORECASE)
RE_GRUPO_LETRA = re.compile(r"\bgrupo\s+([ABCE])\b(?!\d)", re.IGNORECASE)


def _plano(texto: str) -> str:
    t = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return " ".join(t.lower().split())


def _clave(t: str) -> str:
    return "-".join(w for w in t.split() if w not in PALABRAS_VACIAS)


NO_SINGULAR = {"crisis", "analisis", "tesis", "menos", "mas", "tres", "dos", "seis", "ademas", "lunes", "martes",
               "miercoles", "jueves", "viernes", "campus", "virus", "bus", "gas", "pais", "mies", "ciempozuelos"}


def singular(w: str) -> str:
    """«auxiliares administrativos» y «auxiliar administrativo», «peones», «oficiales», «técnicos»: la misma clave."""
    if len(w) < 5 or w in NO_SINGULAR or w.endswith(("is", "us")):
        return w
    if w.endswith("es") and len(w) > 5 and w[-3] in "rlndz" and w[-4] in "aeiou":
        return w[:-2]
    if w.endswith(("os", "as", "es")):
        return w[:-1]
    return w


_SINONIMOS_POR_CLAVE = {_clave(k): v for k, v in SINONIMOS.items()}


def normalizar_puesto(denominacion: str) -> dict:
    """Devuelve clave, nombre canónico y especialidad a partir de la denominación tal como viene."""
    original = denominacion.strip()
    especialidad = None
    m = RE_ESPECIALIDAD.search(original)
    if m:
        especialidad = re.sub(r"(?i)^\s*especialidad\s*:?\s*", "", m.group(1)).strip()
        original_sin = original[: m.start()] + original[m.end():]
    else:
        original_sin = original
    t = RE_GENERO.sub("", original_sin)
    t = _plano(t)
    t = re.sub(r"^(?:personal|plaza|plazas|puesto|puestos|placa|places|praza|prazas|lloc|llocs)\s+"
               r"(?:de\s+|d'\s*|de\s+treball\s+(?:de\s+|d'\s*)?)?", "", t)
    t = re.sub(r"\s*,.*$", "", t)                       # lo que va tras una coma suele ser destino o detalle
    t = re.sub(r"\s+(?:con destino|adscrit\w*|para el|para la|en el area|del area)\b.*$", "", t)
    t = re.sub(r"[^a-z0-9ñ ]+", " ", t)
    t = re.sub(r"\b(?:d|l|s)\s+(?=[a-z])", "", t)          # restos de «d'», «l'» tras quitar el apóstrofo
    t = " ".join(FEMENINOS.get(w, w) for w in " ".join(TRADUCCION.get(w, w) for w in t.split()).split())
    t = " ".join(FEMENINOS.get(singular(w), singular(w)) for w in t.split())
    t = re.sub(r"\b(\w+(?: \w+)?) o \1\b", r"\1", t)    # «trabajador o trabajadora social» -> «trabajador social»
    canonico = SINONIMOS.get(t) or _SINONIMOS_POR_CLAVE.get(_clave(t), t)
    clave = _clave(canonico)
    return {"clave": clave, "nombre": canonico, "especialidad": especialidad, "denominacion": original}


def grupo(texto: str, escala: str | None, subescala: str | None) -> tuple[str | None, str | None]:
    """(grupo, cómo se ha obtenido): 'texto', 'subescala' o (None, None)."""
    m = RE_GRUPO.search(texto or "")
    if m:
        return m.group(1).upper(), "texto"
    m = RE_GRUPO_LETRA.search(texto or "")
    if m and m.group(1).upper() in {"B", "E"}:
        return m.group(1).upper(), "texto"
    if escala and _plano(escala).startswith("administracion general") and subescala:
        g = GRUPO_POR_SUBESCALA_AG.get(_plano(subescala).split()[0])
        if g:
            return g, "subescala"
    # Administración Especial, subescala Técnica: clase Superior A1, Media A2, Técnicos Auxiliares C1
    # (RDLeg 781/1986, art. 171, con la equivalencia de grupos del TREBEP)
    if escala and _plano(escala).startswith("administracion especial") and subescala \
            and _plano(subescala).startswith("tecnica"):
        clase = _plano(texto or "")
        if "clase superior" in clase or "tecnicos superiores" in clase:
            return "A1", "subescala"
        if "clase media" in clase or "tecnicos medios" in clase:
            return "A2", "subescala"
        if "tecnicos auxiliares" in clase:
            return "C1", "subescala"
    return None, None
