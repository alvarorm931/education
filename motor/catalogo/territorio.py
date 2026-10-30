"""Territorio: provincias y municipios con sus códigos oficiales del INE.

Fuente: INE, «Relación de municipios y códigos por comunidades autónomas y provincias a 1 de enero de 2026»
(motor/catalogo/datos/municipios_ine_2026.json, con URL, fecha de captura y huella del original).

  provincia("Alacant") -> {"codigo": "03", "nombre": "Alicante", "comunidad": "Comunitat Valenciana"}
  municipio("Altea", comunidad="10") -> {"codigo_ine": "03018", "nombre": "Altea", "provincia": "Alicante", ...}

Reglas para no inventar: un nombre de municipio solo se resuelve si es único dentro de lo que se sabe
(provincia, comunidad o, si no se sabe nada, toda España). Si hay varios con el mismo nombre, no se resuelve.
Los nombres del INE con artículo pospuesto («Campello, el») y los bilingües («Elche/Elx») se reconocen en
todas sus formas.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

DATOS = Path(__file__).parent / "datos" / "municipios_ine_2026.json"

COMUNIDADES = {
    "01": "Andalucía", "02": "Aragón", "03": "Principado de Asturias", "04": "Illes Balears", "05": "Canarias",
    "06": "Cantabria", "07": "Castilla y León", "08": "Castilla-La Mancha", "09": "Cataluña",
    "10": "Comunitat Valenciana", "11": "Extremadura", "12": "Galicia", "13": "Comunidad de Madrid",
    "14": "Región de Murcia", "15": "Comunidad Foral de Navarra", "16": "País Vasco", "17": "La Rioja",
    "18": "Ceuta", "19": "Melilla",
}
# código INE de provincia -> (nombre que se muestra, comunidad, otras formas de escribirla)
PROVINCIAS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "01": ("Álava", "16", ("Araba", "Araba/Álava", "Álava/Araba")),
    "02": ("Albacete", "08", ()),
    "03": ("Alicante", "10", ("Alacant", "Alicante/Alacant")),
    "04": ("Almería", "01", ()),
    "05": ("Ávila", "07", ()),
    "06": ("Badajoz", "11", ()),
    "07": ("Illes Balears", "04", ("Baleares", "Islas Baleares", "Balears", "Balears, Illes", "Illes Balears")),
    "08": ("Barcelona", "09", ()),
    "09": ("Burgos", "07", ()),
    "10": ("Cáceres", "11", ()),
    "11": ("Cádiz", "01", ()),
    "12": ("Castellón", "10", ("Castelló", "Castellón/Castelló", "Castellón de la Plana")),
    "13": ("Ciudad Real", "08", ()),
    "14": ("Córdoba", "01", ()),
    "15": ("A Coruña", "12", ("La Coruña", "Coruña", "Coruña, A")),
    "16": ("Cuenca", "08", ()),
    "17": ("Girona", "09", ("Gerona",)),
    "18": ("Granada", "01", ()),
    "19": ("Guadalajara", "08", ()),
    "20": ("Gipuzkoa", "16", ("Guipúzcoa",)),
    "21": ("Huelva", "01", ()),
    "22": ("Huesca", "02", ()),
    "23": ("Jaén", "01", ()),
    "24": ("León", "07", ()),
    "25": ("Lleida", "09", ("Lérida",)),
    "26": ("La Rioja", "17", ("Rioja", "Rioja, La", "Logroño")),
    "27": ("Lugo", "12", ()),
    "28": ("Madrid", "13", ()),
    "29": ("Málaga", "01", ()),
    "30": ("Murcia", "14", ()),
    "31": ("Navarra", "15", ("Nafarroa",)),
    "32": ("Ourense", "12", ("Orense",)),
    "33": ("Asturias", "03", ()),
    "34": ("Palencia", "07", ()),
    "35": ("Las Palmas", "05", ("Palmas, Las", "Gran Canaria")),
    "36": ("Pontevedra", "12", ()),
    "37": ("Salamanca", "07", ()),
    "38": ("Santa Cruz de Tenerife", "05", ("S/C de Tenerife", "Tenerife")),
    "39": ("Cantabria", "06", ()),
    "40": ("Segovia", "07", ()),
    "41": ("Sevilla", "01", ()),
    "42": ("Soria", "07", ()),
    "43": ("Tarragona", "09", ()),
    "44": ("Teruel", "02", ()),
    "45": ("Toledo", "08", ()),
    "46": ("Valencia", "10", ("València", "Valencia/València")),
    "47": ("Valladolid", "07", ()),
    "48": ("Bizkaia", "16", ("Vizcaya",)),
    "49": ("Zamora", "07", ()),
    "50": ("Zaragoza", "02", ()),
    "51": ("Ceuta", "18", ()),
    "52": ("Melilla", "19", ()),
}
# Fuente autonómica -> comunidad (para resolver municipios que el boletín no acompaña de provincia)
COMUNIDAD_DE_FUENTE = {"BOJA": "01", "BOA": "02", "BOIB": "04", "BOC": "05", "BOCYL": "07", "DOCM": "08",
                       "DOGC": "09", "DOGV": "10", "DOE": "11", "DOG": "12", "BOCM": "13", "BORM": "14",
                       "BOPV": "16", "BOCCE": "18", "BOME": "19"}
ARTICULOS = {"el", "la", "los", "las", "l'", "els", "les", "o", "a", "os", "as", "es", "sa", "ses", "s'"}


def clave(texto: str) -> str:
    t = "".join(c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn")
    t = t.lower().replace("’", "'").replace("`", "'")
    t = re.sub(r"[^a-z0-9ñ' ]+", " ", t)
    return " ".join(t.split())


def variantes(nombre_ine: str) -> set[str]:
    """«Campello, el» -> {«campello el», «el campello», «campello»}; «Elche/Elx» -> {«elche», «elx»}."""
    salida = set()
    for parte in nombre_ine.split("/"):
        parte = parte.strip()
        m = re.match(r"^(.*?),\s*(\S+)$", parte)
        if m and clave(m.group(2)) in ARTICULOS:
            base, art = m.group(1), m.group(2)
            salida |= {clave(parte), clave(base), clave(f"{art} {base}"), clave(f"{art}{base}") if art.endswith("'") else ""}
        else:
            salida.add(clave(parte))
    return {v for v in salida if v}


@lru_cache(maxsize=1)
def _indices() -> tuple[dict[str, list[tuple[str, str]]], dict[str, str]]:
    datos = json.loads(DATOS.read_text(encoding="utf-8"))
    por_nombre: dict[str, list[tuple[str, str]]] = {}
    for codigo, nombre in datos["municipios"]:
        for v in variantes(nombre):
            por_nombre.setdefault(v, []).append((codigo, nombre))
    provincias: dict[str, str] = {}
    for cod, (nombre, _, otros) in PROVINCIAS.items():
        for v in (nombre, *otros):
            provincias[clave(v)] = cod
    return por_nombre, provincias


@lru_cache(maxsize=1)
def _oficiales() -> dict[str, str]:
    return {c: n for c, n in json.loads(DATOS.read_text(encoding="utf-8"))["municipios"]}


def provincia(texto: str | None) -> dict | None:
    if not texto:
        return None
    _, provs = _indices()
    t = clave(re.sub(r"(?i)^(provincia de|prov\.)\s+", "", texto.strip()))
    cod = provs.get(t)
    if not cod:
        return None
    nombre, ccaa, _ = PROVINCIAS[cod]
    return {"codigo": cod, "nombre": nombre, "comunidad_codigo": ccaa, "comunidad": COMUNIDADES[ccaa]}


# Formas de uso corriente que no coinciden con el nombre oficial del INE (solo casos sin ambigüedad)
USUALES = {"palma de mallorca": "07040", "castell d'aro": "17048", "platja d'aro": "17048", "s'agaro": "17048",
           "vitoria": "01059", "vitoria gasteiz": "01059", "san sebastian": "20069", "donostia": "20069",
           "bilbo": "48020", "pamplona": "31201", "iruna": "31201"}


# Lo que algunos boletines anteponen al nombre del municipio (el BOP de Tenerife: «Ayuntamiento de Villa de los
# Realejos»); solo se quita si el nombre entero no es el de ningún municipio («La Villa de Don Fadrique» sí lo es)
RE_TRATAMIENTO_MUNICIPIO = re.compile(r"^(?:(?:ayuntamiento|ajuntament|concello|udala) (?:de |d')?)?"
                                      r"(?:(?:muy noble y muy leal |real |m\.? ?n\.? y m\.? ?l\.? )?"
                                      r"(?:villa|ciudad|vila|ciutat|cidade|real sitio) (?:de |d'))")


def _candidatos(nombre: str, provincia_codigo: str | None, comunidad_codigo: str | None) -> set[str]:
    por_nombre, _ = _indices()
    k = clave(nombre)
    lista = [c[0] for c in por_nombre.get(k, [])]
    if not lista and " y " in f" {k} ":  # «Vilanova y la Geltrú» -> «Vilanova i la Geltrú»
        lista = [c[0] for c in por_nombre.get(f" {k} ".replace(" y ", " i ").strip(), [])]
    if not lista and k in USUALES:
        lista = [USUALES[k]]
    if not lista and (m := RE_TRATAMIENTO_MUNICIPIO.match(k)):  # «Villa de los Realejos» -> «Los Realejos»
        lista = [c[0] for c in por_nombre.get(k[m.end():], [])]
    if provincia_codigo:
        lista = [c for c in lista if c[:2] == provincia_codigo]
    elif comunidad_codigo:
        lista = [c for c in lista if PROVINCIAS[c[:2]][1] == comunidad_codigo]
    return set(lista)


def municipio(nombre: str | None, provincia_codigo: str | None = None, comunidad_codigo: str | None = None) -> dict | None:
    if not nombre:
        return None
    codigos = _candidatos(nombre, provincia_codigo, comunidad_codigo)
    if not codigos and "/" in nombre:
        # «Elx/Elche», «Alcoi/Alcoy»: cada mitad por separado; vale si todas las que se reconocen coinciden
        partes = [_candidatos(p, provincia_codigo, comunidad_codigo) for p in nombre.split("/") if p.strip()]
        partes = [p for p in partes if p]
        codigos = set.intersection(*partes) if partes else set()
    if len(codigos) != 1:
        return None
    codigo = next(iter(codigos))
    oficial = _oficiales()[codigo]
    nombre_prov, ccaa, _ = PROVINCIAS[codigo[:2]]
    return {"codigo_ine": codigo, "nombre_oficial": oficial, "provincia_codigo": codigo[:2], "provincia": nombre_prov,
            "comunidad_codigo": ccaa, "comunidad": COMUNIDADES[ccaa]}


RE_BOP = re.compile(r"(?:Bolet[ií]n|Butllet[ií]) Oficial d(?:e la|a) Prov[ií]ncia de (?P<p>.+)$", re.IGNORECASE)


def provincia_de_boletin(nombre_boletin: str | None) -> dict | None:
    """«Boletín Oficial de la Provincia de Alicante» -> Alicante; también BOCM, BORM y otros uniprovinciales."""
    if not nombre_boletin:
        return None
    m = RE_BOP.search(nombre_boletin.strip())
    if m:
        return provincia(m.group("p"))
    uni = {"boletin oficial de la comunidad de madrid": "Madrid", "boletin oficial de la region de murcia": "Murcia",
           "boletin oficial de islas baleares": "Illes Balears", "boletin oficial de las illes balears": "Illes Balears",
           "butlleti oficial de les illes balears": "Illes Balears", "boletin oficial de cantabria": "Cantabria",
           "boletin oficial del principado de asturias": "Asturias", "boletin oficial de la rioja": "La Rioja",
           "boletin oficial de navarra": "Navarra", "boletin oficial de bizkaia": "Bizkaia",
           "boletin oficial de gipuzkoa": "Gipuzkoa", "boletin oficial del territorio historico de alava": "Álava",
           "boletin oficial de la ciudad autonoma de ceuta": "Ceuta",
           "boletin oficial de la ciudad autonoma de melilla": "Melilla", "boletin oficial del ayuntamiento de madrid": "Madrid"}
    p = uni.get(clave(nombre_boletin))
    return provincia(p) if p else None


def ubicar_convocante(conv: dict | None, fuentes: tuple[str, ...] | list[str] = (),
                      boletines: list[dict] | None = None) -> dict | None:
    """Añade provincia canónica, comunidad y código INE al convocante, sin inventar. Por orden: la provincia
    escrita en el título, el boletín provincial citado, el nombre de la diputación y, para el municipio, el nombre
    único dentro de esa provincia, de la comunidad del boletín autonómico (`fuentes`) o de toda España."""
    if not conv or not conv.get("tipo"):
        return conv
    salida = dict(conv)
    prov = provincia(conv.get("provincia"))
    if not prov:
        for b in boletines or []:
            prov = provincia_de_boletin(b.get("boletin"))
            if prov:
                break
    tipo = conv["tipo"]
    if tipo in ("Diputación Provincial", "Diputación Foral") and not prov:
        prov = provincia(conv.get("nombre"))
    if tipo == "Ayuntamiento":
        comunidad = next((COMUNIDAD_DE_FUENTE[f] for f in fuentes if f in COMUNIDAD_DE_FUENTE), None)
        m = municipio(conv.get("nombre"), prov["codigo"] if prov else None, None if prov else comunidad)
        if not m and conv.get("organismo"):
            # «Facheca» en el nombre y «AYUNTAMIENTO FAGECA» (el oficial) en el organismo (BOP de Alicante)
            org = re.sub(r"^\s*(?:excmo\.?\s+|ilmo\.?\s+|m\.?\s*i\.?\s+)?(?:ayuntamiento|ajuntament|concello|udala)"
                         r"(?:\s+(?:de|del|d')\b)?\s*", "", conv["organismo"], flags=re.IGNORECASE)
            if org and org != conv["organismo"]:
                m = municipio(org, prov["codigo"] if prov else None, None if prov else comunidad)
        if m:
            salida.update({"codigo_ine": m["codigo_ine"], "municipio_oficial": m["nombre_oficial"]})
            prov = prov or provincia(m["provincia"])
    if prov:
        salida.update({"provincia": prov["nombre"], "provincia_codigo": prov["codigo"], "comunidad": prov["comunidad"]})
    return salida


def comunidad_de_fuentes(fuentes: tuple[str, ...] | list[str]) -> str | None:
    """Comunidad del boletín autonómico, para los procesos de ámbito autonómico."""
    cod = next((COMUNIDAD_DE_FUENTE[f] for f in fuentes if f in COMUNIDAD_DE_FUENTE), None)
    return COMUNIDADES[cod] if cod else None


def comunidad_codigo(convocante: dict | None = None, siglas: str | None = None,
                     boletines: tuple[str, ...] | list[str] = ()) -> str | None:
    """Código INE de la comunidad para los festivos de un plazo: la del convocante (por su provincia), la del boletín
    autonómico o la provincia del boletín provincial (por su nombre). None si no se sabe (se cuentan los nacionales)."""
    if convocante and (p := provincia(convocante.get("provincia"))):
        return p["comunidad_codigo"]
    if siglas in COMUNIDAD_DE_FUENTE:
        return COMUNIDAD_DE_FUENTE[siglas]
    for b in boletines:
        if (p := provincia_de_boletin(b)):
            return p["comunidad_codigo"]
    return None
