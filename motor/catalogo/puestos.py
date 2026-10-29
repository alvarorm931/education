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
PALABRAS_VACIAS = {"de", "del", "la", "las", "los", "el", "y", "e", "en", "a", "para"}

GRUPO_POR_SUBESCALA_AG = {"tecnica": "A1", "gestion": "A2", "administrativa": "C1", "auxiliar": "C2",
                          "subalterna": "AP"}

RE_GENERO = re.compile(r"(?<=\w)/(?:a|as|o|os|la|las|va|ra|ora|era)\b|\((?:a|as|o|os)\)|(?<=\w)\(a\)")
RE_ESPECIALIDAD = re.compile(r"\(([^)]*especialidad[^)]*)\)", re.IGNORECASE)
RE_GRUPO = re.compile(r"\b(?:sub)?grupo\s+(A1|A2|B|C1|C2|AP|E)\b", re.IGNORECASE)
RE_GRUPO_LETRA = re.compile(r"\bgrupo\s+([ABCE])\b(?!\d)", re.IGNORECASE)


def _plano(texto: str) -> str:
    t = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return " ".join(t.lower().split())


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
    t = re.sub(r"^(?:personal|plaza|plazas|puesto|puestos)\s+(?:de\s+)?", "", t)
    t = re.sub(r"\s*,.*$", "", t)                       # lo que va tras una coma suele ser destino o detalle
    t = re.sub(r"\s+(?:con destino|adscrit\w*|para el|para la|en el area|del area)\b.*$", "", t)
    t = re.sub(r"[^a-z0-9ñ ]+", " ", t)
    t = " ".join(FEMENINOS.get(w, w) for w in t.split())
    canonico = SINONIMOS.get(t, t)
    clave = "-".join(w for w in canonico.split() if w not in PALABRAS_VACIAS)
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
