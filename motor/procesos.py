"""Procesos de oposición a partir de los actos extraídos del BOE y de los boletines autonómicos.

Uso:
  python -m motor.procesos --salida ruta/ [--hoy 2026-10-29]

Lee datos/boe/actos/ y datos/autonomicos/actos/ y escribe:
  datos/oposiciones/procesos.jsonl   un proceso por convocatoria de acceso, con sus actos enlazados
  datos/oposiciones/resumen.json     cifras del día: plazos abiertos por provincia, por puesto y por fuente

Reglas:
  - Nace un proceso por cada anuncio de apertura de plazo (local) o convocatoria (resto) de acceso abierto,
    del BOE o de un boletín autonómico.
  - Una misma convocatoria publicada en el BOE y en su boletín autonómico (mismo título) es un solo proceso:
    manda el BOE y la publicación autonómica queda enlazada (con su texto completo).
  - Lo local de los boletines autonómicos (bases íntegras) no crea procesos: se enlaza al anuncio del BOE que
    las cita («En el Boletín Oficial de ... número N, de fecha, se han publicado las bases...»).
  - Se enlazan los actos que citan al de origen por su identificador del BOE (correcciones, anulaciones...).
  - Estado: «anulado» si hay anulación; «plazo_abierto» si la fecha de fin es hoy o posterior;
    «plazo_cerrado» si ya pasó (el proceso sigue en curso, sin novedades conocidas);
    «sin_datos_de_plazo» si aún no se ha extraído el plazo. Nunca se inventa un estado.
  - Si una corrección o modificación posterior abre un plazo nuevo, ese plazo sustituye al original.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.boe.clasificar import normalizar
from motor.catalogo.territorio import comunidad_de_fuentes, ubicar_convocante

MADRID = ZoneInfo("Europe/Madrid")
NOMBRE_FUENTE = {
    "BOE": "Agencia Estatal Boletín Oficial del Estado",
    "BOJA": "Boletín Oficial de la Junta de Andalucía (Junta de Andalucía, CC BY 4.0)",
    "BOCM": "Boletín Oficial de la Comunidad de Madrid",
    "BOCYL": "Boletín Oficial de Castilla y León (Junta de Castilla y León, CC BY 4.0)",
    "DOGV": "Diari Oficial de la Generalitat Valenciana",
    "DOG": "Diario Oficial de Galicia",
    "DOGC": "Diari Oficial de la Generalitat de Catalunya",
    "BOA": "Boletín Oficial de Aragón",
    "DOE": "Diario Oficial de Extremadura",
    "BORM": "Boletín Oficial de la Región de Murcia",
    "BOC": "Boletín Oficial de Canarias",
    "DOCM": "Diario Oficial de Castilla-La Mancha",
    "BOME": "Boletín Oficial de la Ciudad Autónoma de Melilla",
    "BOPV": "Boletín Oficial del País Vasco",
    "BOIB": "Butlletí Oficial de les Illes Balears",
    "BOPA": "Boletín Oficial del Principado de Asturias",
    "BON": "Boletín Oficial de Navarra",
    "BOC-CANT": "Boletín Oficial de Cantabria",
    "BOR": "Boletín Oficial de La Rioja",
    "BOPB": "Butlletí Oficial de la Província de Barcelona",
    "BOP-ALICANTE": "Boletín Oficial de la Provincia de Alicante",
    "BOP-VALENCIA": "Butlletí Oficial de la Província de València",
    "BOPT": "Butlletí Oficial de la Província de Tarragona",
    "BOP-CIUDADREAL": "Boletín Oficial de la Provincia de Ciudad Real",
    "BOP-GRANADA": "Boletín Oficial de la Provincia de Granada",
    "BOP-SEVILLA": "Boletín Oficial de la Provincia de Sevilla",
    "BOP-HUESCA": "Boletín Oficial de la Provincia de Huesca",
    "BOP-TENERIFE": "Boletín Oficial de la Provincia de Santa Cruz de Tenerife",
    "BOP-CORDOBA": "Boletín Oficial de la Provincia de Córdoba",
    "BOP-CORUNA": "Boletín Oficial de la Provincia de A Coruña",
    "BOP-PONTEVEDRA": "Boletín Oficial de la Provincia de Pontevedra",
    "BOP-AVILA": "Boletín Oficial de la Provincia de Ávila",
    "BOP-BADAJOZ": "Boletín Oficial de la Provincia de Badajoz",
    "BOP-ZAMORA": "Boletín Oficial de la Provincia de Zamora",
    "BOP-TOLEDO": "Boletín Oficial de la Provincia de Toledo",
    "BOP-BURGOS": "Boletín Oficial de la Provincia de Burgos",
    "BOTHA": "Boletín Oficial del Territorio Histórico de Álava",
    "BOP-SALAMANCA": "Boletín Oficial de la Provincia de Salamanca",
    "BOP-ALBACETE": "Boletín Oficial de la Provincia de Albacete",
    "BOP-JAEN": "Boletín Oficial de la Provincia de Jaén",
    "BOP-ZARAGOZA": "Boletín Oficial de la Provincia de Zaragoza",
    "BOG": "Boletín Oficial de Gipuzkoa",
    "BOB": "Boletín Oficial de Bizkaia",
    "BOP-LUGO": "Boletín Oficial de la Provincia de Lugo",
    "BOP-HUELVA": "Boletín Oficial de la Provincia de Huelva",
    "BOP-LASPALMAS": "Boletín Oficial de la Provincia de Las Palmas",
    "BOP-VALLADOLID": "Boletín Oficial de la Provincia de Valladolid",
    "BOP-CACERES": "Boletín Oficial de la Provincia de Cáceres",
    "BOP-GUADALAJARA": "Boletín Oficial de la Provincia de Guadalajara",
    "BOP-GIRONA": "Boletín Oficial de la Provincia de Girona",
    "BOP-OURENSE": "Boletín Oficial de la Provincia de Ourense",
    "BOP-LLEIDA": "Boletín Oficial de la Provincia de Lleida",
    "BOP-PALENCIA": "Boletín Oficial de la Provincia de Palencia",
    "BOP-SORIA": "Boletín Oficial de la Provincia de Soria",
    "BOP-TERUEL": "Boletín Oficial de la Provincia de Teruel",
    "BOP-CASTELLON": "Boletín Oficial de la Provincia de Castellón",
    "BOP-LEON": "Boletín Oficial de la Provincia de León",
}
# Cómo citan los anuncios del BOE a cada boletín autonómico (para enlazar las bases íntegras)
BOLETIN_A_FUENTE = {
    "boletin oficial de la junta de andalucia": "BOJA",
    "boletin oficial de la comunidad de madrid": "BOCM",
    "boletin oficial de castilla y leon": "BOCYL",
    "diari oficial de la generalitat valenciana": "DOGV",
    "diario oficial de la generalitat valenciana": "DOGV",
    "diari oficial de la comunitat valenciana": "DOGV",
    "diario oficial de la comunitat valenciana": "DOGV",
    "diario oficial de galicia": "DOG",
    "boletin oficial de aragon": "BOA",
    "diario oficial de extremadura": "DOE",
    "boletin oficial de la region de murcia": "BORM",
    "boletin oficial de canarias": "BOC",
    "boletin oficial del principado de asturias": "BOPA",
    "boletin oficial de navarra": "BON",
    "boletin oficial de cantabria": "BOC-CANT",
    "boletin oficial de la rioja": "BOR",
    "diario oficial de castilla-la mancha": "DOCM",
    "diario oficial de castilla la mancha": "DOCM",
    "boletin oficial de la ciudad de melilla": "BOME",
    "boletin oficial de la ciudad autonoma de melilla": "BOME",
    "boletin oficial del pais vasco": "BOPV",
    "butlleti oficial de les illes balears": "BOIB",
    "boletin oficial de las illes balears": "BOIB",
    "boletin oficial de las islas baleares": "BOIB",
    "boletin oficial de islas baleares": "BOIB",
    "diari oficial de la generalitat de catalunya": "DOGC",
    "diario oficial de la generalitat de cataluna": "DOGC",
    "diario oficial de la generalidad de cataluna": "DOGC",
    "boletin oficial de la provincia de barcelona": "BOPB",
    "butlleti oficial de la provincia de barcelona": "BOPB",
    "boletin oficial de la provincia de alicante": "BOP-ALICANTE",
    "butlleti oficial de la provincia d'alacant": "BOP-ALICANTE",
    "butlleti oficial de la provincia d’alacant": "BOP-ALICANTE",
    "boletin oficial de la provincia de valencia": "BOP-VALENCIA",
    "butlleti oficial de la provincia de valencia": "BOP-VALENCIA",
    "boletin oficial de la provincia de tarragona": "BOPT",
    "butlleti oficial de la provincia de tarragona": "BOPT",
    "boletin oficial de la provincia de ciudad real": "BOP-CIUDADREAL",
    "boletin oficial de la provincia de granada": "BOP-GRANADA",
    "boletin oficial de la provincia de sevilla": "BOP-SEVILLA",
    "boletin oficial de la provincia de huesca": "BOP-HUESCA",
    "boletin oficial de la provincia de santa cruz de tenerife": "BOP-TENERIFE",
    "boletin oficial de la provincia de cordoba": "BOP-CORDOBA",
    "boletin oficial de la provincia de a coruna": "BOP-CORUNA",
    "boletin oficial de la provincia de la coruna": "BOP-CORUNA",
    "boletin oficial da provincia da coruna": "BOP-CORUNA",
    "boletin oficial de la provincia de pontevedra": "BOP-PONTEVEDRA",
    "boletin oficial de la provincia de avila": "BOP-AVILA",
    "boletin oficial de la provincia de badajoz": "BOP-BADAJOZ",
    "boletin oficial de la provincia de zamora": "BOP-ZAMORA",
    "boletin oficial de la provincia de toledo": "BOP-TOLEDO",
    "boletin oficial de la provincia de burgos": "BOP-BURGOS",
    "boletin oficial del territorio historico de alava": "BOTHA",
    "boletin oficial de la provincia de salamanca": "BOP-SALAMANCA",
    "boletin oficial de la provincia de albacete": "BOP-ALBACETE",
    "boletin oficial de la provincia de jaen": "BOP-JAEN",
    "boletin oficial de la provincia de zaragoza": "BOP-ZARAGOZA",
    "boletin oficial de gipuzkoa": "BOG",
    "boletin oficial de guipuzcoa": "BOG",
    "boletin oficial de bizkaia": "BOB",
    "boletin oficial de vizcaya": "BOB",
    "boletin oficial de la provincia de lugo": "BOP-LUGO",
    "boletin oficial da provincia de lugo": "BOP-LUGO",
    "boletin oficial de la provincia de huelva": "BOP-HUELVA",
    "boletin oficial de la provincia de las palmas": "BOP-LASPALMAS",
    "boletin oficial de la provincia de valladolid": "BOP-VALLADOLID",
    "boletin oficial de la provincia de caceres": "BOP-CACERES",
    "boletin oficial de la provincia de guadalajara": "BOP-GUADALAJARA",
    "boletin oficial de la provincia de girona": "BOP-GIRONA",
    "butlleti oficial de la provincia de girona": "BOP-GIRONA",
    "boletin oficial de la provincia de ourense": "BOP-OURENSE",
    "boletin oficial da provincia de ourense": "BOP-OURENSE",
    "boletin oficial de la provincia de lleida": "BOP-LLEIDA",
    "butlleti oficial de la provincia de lleida": "BOP-LLEIDA",
    "boletin oficial de la provincia de palencia": "BOP-PALENCIA",
    "boletin oficial de la provincia de soria": "BOP-SORIA",
    "boletin oficial de la provincia de teruel": "BOP-TERUEL",
    "boletin oficial de la provincia de castellon": "BOP-CASTELLON",
    "boletin oficial de la provincia de leon": "BOP-LEON",
}
RE_NO_ALFANUM = re.compile(r"[^a-z0-9ñ]+")
RE_PREFIJO_CITA = re.compile(r"^(?:en\s+(?:el|la)\s+)?[«\"“]?", re.IGNORECASE)


# Para las formas de citar que no están en BOLETIN_A_FUENTE («Boletín Oficial de Málaga», «Boletín Oficial de la
# Provincial de Granada», «Boletín Oficial de Provincia de Cuenca»): la provincia o comunidad que nombran. Los
# boletines sin conector llevan su sigla propia para que el control de cobertura los cuente aparte.
PROVINCIA_A_FUENTE = {
    "barcelona": "BOPB", "alicante": "BOP-ALICANTE", "alacant": "BOP-ALICANTE", "valencia": "BOP-VALENCIA",
    "tarragona": "BOPT", "ciudad real": "BOP-CIUDADREAL", "granada": "BOP-GRANADA", "sevilla": "BOP-SEVILLA",
    "huesca": "BOP-HUESCA", "santa cruz de tenerife": "BOP-TENERIFE", "tenerife": "BOP-TENERIFE",
    "cordoba": "BOP-CORDOBA", "a coruna": "BOP-CORUNA", "la coruna": "BOP-CORUNA", "coruna": "BOP-CORUNA",
    "pontevedra": "BOP-PONTEVEDRA", "avila": "BOP-AVILA", "badajoz": "BOP-BADAJOZ", "zamora": "BOP-ZAMORA",
    "toledo": "BOP-TOLEDO", "burgos": "BOP-BURGOS", "alava": "BOTHA", "araba": "BOTHA", "salamanca": "BOP-SALAMANCA",
    "albacete": "BOP-ALBACETE", "jaen": "BOP-JAEN", "zaragoza": "BOP-ZARAGOZA", "gipuzkoa": "BOG", "guipuzcoa": "BOG",
    "bizkaia": "BOB", "vizcaya": "BOB", "lugo": "BOP-LUGO", "huelva": "BOP-HUELVA", "las palmas": "BOP-LASPALMAS",
    "las palmas de gran canaria": "BOP-LASPALMAS", "valladolid": "BOP-VALLADOLID", "caceres": "BOP-CACERES",
    "guadalajara": "BOP-GUADALAJARA", "girona": "BOP-GIRONA", "gerona": "BOP-GIRONA", "ourense": "BOP-OURENSE",
    "orense": "BOP-OURENSE", "lleida": "BOP-LLEIDA", "lerida": "BOP-LLEIDA", "palencia": "BOP-PALENCIA",
    "soria": "BOP-SORIA", "teruel": "BOP-TERUEL", "castellon": "BOP-CASTELLON", "castello": "BOP-CASTELLON",
    "leon": "BOP-LEON", "madrid": "BOCM", "asturias": "BOPA", "cantabria": "BOC-CANT", "murcia": "BORM",
    "navarra": "BON", "la rioja": "BOR", "melilla": "BOME", "ceuta": "BOCCE",
    "malaga": "BOP-MALAGA", "almeria": "BOP-ALMERIA", "cadiz": "BOP-CADIZ", "cuenca": "BOP-CUENCA",
    "segovia": "BOP-SEGOVIA",
}
RE_PROVINCIA_CITA = re.compile(r"^(?:boletin(?:es)? (?:oficial(?:es)? )?|butlleti oficial |diario oficial )"
                               r"(?:de\s+|del\s+|de la\s+|la\s+)*(?:(?:provincial|provincia|diputacion provincial|"
                               r"territorio historico|comunidad|ciudad autonoma|principado|region)\s*(?:\(bop\)\s*)?"
                               r"(?:de\s+|del\s+|de la\s+|d'\s*)*)?(?P<p>[a-z ]+?)\s*$")
OTRAS_CITAS = (("comunidad de madrid", "BOCM"), ("castilla y leon", "BOCYL"), ("illes balears", "BOIB"),
               ("islas baleares", "BOIB"), ("generalitat valenciana", "DOGV"), ("generalidad valenciana", "DOGV"),
               ("comunidad valenciana", "DOGV"), ("comunitat valenciana", "DOGV"), ("generalitat de catalunya", "DOGC"),
               ("generalidad de cataluna", "DOGC"), ("de cataluna", "DOGC"), ("principado de asturias", "BOPA"),
               ("canarias", "BOC"), ("ayuntamiento de madrid", "BOAM"), ("diario municipal", "DIARIO-MUNICIPAL"),
               ("gaceta municipal", "DIARIO-MUNICIPAL"))


def fuente_de_boletin(nombre: str | None) -> str | None:
    """«Boletín Oficial de la Provincia de Barcelona» -> «BOPB» (también con restos de la frase: «En el «...»), y
    las formas abreviadas o con erratas por la provincia o comunidad que nombran."""
    n = normalizar(RE_PREFIJO_CITA.sub("", (nombre or "").strip()).strip(" «»\"”"))
    if (f := BOLETIN_A_FUENTE.get(n)):
        return f
    n = re.sub(r"\b(de|del)\s+(?=de\b|del\b|la\b|oficial\b|boletin\b)", "", n)
    n = re.sub(r"\s+", " ", re.sub(r"\bboletin oficial (?:de )?boletin oficial\b", "boletin oficial", n)).strip()
    n = re.sub(r"\boficial (?:de )?oficial\b", "oficial", n)
    for clave, fuente in OTRAS_CITAS:
        if clave in n:
            return fuente
    m = RE_PROVINCIA_CITA.match(n)
    return PROVINCIA_A_FUENTE.get(m.group("p").strip()) if m else None


def _leer(carpeta: Path) -> list[dict]:
    actos = []
    for f in sorted(carpeta.rglob("*.jsonl")):
        actos += [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    return actos


def leer_actos(raiz: Path) -> list[dict]:
    return _leer(raiz / "datos" / "boe" / "actos")


def leer_actos_autonomicos(raiz: Path) -> list[dict]:
    return _leer(raiz / "datos" / "autonomicos" / "actos")


def es_origen(a: dict) -> bool:
    if a.get("alcance") not in (None, "acceso"):
        return False
    return a.get("tipo_acto") == "apertura_plazo" or (a.get("ambito") != "local" and a.get("tipo_acto") == "convocatoria")


def clave_titulo(titulo: str | None) -> str:
    """Título normalizado para reconocer la misma disposición publicada en dos boletines."""
    return RE_NO_ALFANUM.sub(" ", normalizar(titulo or "")).strip()[:220]


def _nombre(conv: dict | None) -> str:
    return clave_titulo((conv or {}).get("nombre"))


def _municipio(conv: dict | None, fuentes: list[str], boletines: list[dict] | None = None) -> list[str]:
    """Claves del convocante para enlazar publicaciones: su código INE si se sabe sin dudas y su nombre
    normalizado («El Masnou» y «el Masnou» o «Elx/Elche» y «Elche» comparten código)."""
    u = ubicar_convocante(conv, fuentes, boletines) or {}
    return [k for k in (u.get("codigo_ine"), _nombre(conv)) if k]


def es_origen_local(x: dict) -> bool:
    """Bases o convocatoria de una entidad local publicadas en un boletín autonómico o provincial."""
    return x.get("ambito") == "local" and x.get("alcance") in (None, "acceso") and \
        x.get("tipo_acto") in ("convocatoria", "bases")


RE_TEMPORAL = re.compile(r"\b(temporal|interin|interi|bolsa|borsa|substitu|sustitu|suplenc|listaxe de contratacion)")


def _plazo_salida(plazo: dict) -> dict | None:
    if not plazo:
        return None
    return {k: plazo.get(k) for k in ("dias", "meses", "tipo", "inicio", "fin_estimado", "fin_exacto", "cuenta_desde",
                                      "calendario", "de_acto", "cita") if plazo.get(k) is not None}


RE_GRUPO_TITULO = re.compile(r"\b(?:sub)?grupo\s+(?:profesional\s+)?(A1|A2|B|C1|C2|AP|E)\b", re.IGNORECASE)
SISTEMA_DE_MODALIDAD = {"concurso_oposicion": "concurso-oposición", "oposicion": "oposición", "concurso": "concurso",
                        "libre_designacion": "libre designación"}


def _rasgos_proceso(a: dict, otras: list[dict]) -> tuple[str | None, str | None, str | None]:
    """Sistema, turno y grupo del proceso: de sus plazas (texto) o, si no constan, de los títulos de la convocatoria y
    de sus bases. None si no se sabe: nunca se supone."""
    from motor.union import turno
    plazas = a.get("plazas") or []
    titulos = " ".join([a.get("titulo") or ""] + [o.get("titulo") or "" for o in otras])
    sistema = next((p.get("sistema") for p in plazas if p.get("sistema")), None)
    if not sistema:
        mod = [x.get("modalidad") for x in [a, *otras] if x.get("modalidad") in SISTEMA_DE_MODALIDAD]
        sistema = SISTEMA_DE_MODALIDAD[mod[0]] if mod else None
    t = next((p.get("turno") for p in plazas if p.get("turno")), None) or turno(titulos)
    grupos = sorted({p.get("grupo") for p in plazas if p.get("grupo")})
    if not grupos:
        grupos = sorted({g.upper() for g in RE_GRUPO_TITULO.findall(titulos)})
    return sistema, t, ", ".join(grupos) or None


def _ref(x: dict) -> dict:
    return {"id": x["id"], "fecha": x["fecha"], "tipo": x.get("tipo_acto"), "fuente": x.get("fuente") or "BOE",
            "url": x.get("url")}


def construir(actos: list[dict], hoy: date, autonomicos: list[dict] | None = None) -> list[dict]:
    autonomicos = autonomicos or []
    citados_por: dict[str, list[dict]] = defaultdict(list)
    for a in actos:
        for ref in a.get("refiere_a") or []:
            citados_por[ref].append(a)

    # Publicaciones autonómicas: por título (para fusionar con el BOE) y lo local por boletín, fecha y municipio
    por_titulo: dict[str, list[dict]] = defaultdict(list)
    locales: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for x in autonomicos:
        if x.get("ambito") == "local":
            for k in _municipio(x.get("convocante"), [x.get("fuente")]):
                locales[(x.get("fuente"), x.get("fecha"), k)].append(x)
        elif es_origen(x):
            por_titulo[clave_titulo(x.get("titulo"))].append(x)
    usados: set[str] = set()

    procesos = []
    for a in actos:
        if not es_origen(a):
            continue
        a = {**a, "fuente": a.get("fuente") or "BOE"}
        gemelos = [x for x in por_titulo.get(clave_titulo(a.get("titulo")), []) if x["id"] not in usados]
        usados.update(x["id"] for x in gemelos)
        bases_enlazadas = []
        citados = a.get("boletines_citados") or []
        for b in citados:
            fuente = fuente_de_boletin(b.get("boletin"))
            if fuente and b.get("fecha"):
                for k in _municipio(a.get("convocante"), ["BOE", fuente], citados):
                    vistos = {x["id"] for x in bases_enlazadas}
                    bases_enlazadas += [x for x in locales.get((fuente, b["fecha"], k), [])
                                        if x["id"] not in usados and x["id"] not in vistos]
        usados.update(x["id"] for x in bases_enlazadas)
        procesos.append(_proceso(a, sorted(citados_por.get(a["id"], []), key=lambda x: x["fecha"]),
                                 gemelos + bases_enlazadas, hoy, f"boe:{a['id']}"))

    for x in autonomicos:
        if x.get("ambito") != "local" and es_origen(x) and x["id"] not in usados:
            procesos.append(_proceso(x, [], [], hoy, x["id"]))
        elif es_origen_local(x) and x["id"] not in usados:
            # Bases locales sin anuncio en el BOE que las cite: bolsas y contratos temporales (no van al BOE) o
            # bases cuyo plazo empezará con el anuncio en el BOE, que aún no ha salido o no se ha podido enlazar
            procesos.append(_proceso(x, [], [], hoy, x["id"], solo_bases=True))
    return procesos


def _proceso(a: dict, posteriores: list[dict], otras: list[dict], hoy: date, ident: str,
             solo_bases: bool = False) -> dict:
    plazo = a.get("plazo") or {}
    if not plazo.get("fin_estimado"):
        # La publicación autonómica puede fijar el plazo desde su propio boletín cuando el BOE remite a él
        for x in otras:
            if (x.get("plazo") or {}).get("fin_estimado") and x.get("ambito") != "local":
                plazo = {**x["plazo"], "de_acto": x["id"]}
                break
    for x in posteriores:  # una corrección o modificación posterior puede abrir un plazo nuevo
        if x.get("tipo_acto") in ("modificacion", "correccion") and (x.get("plazo") or {}).get("fin_estimado"):
            plazo = {**x["plazo"], "de_acto": x["id"]}
    fin = plazo.get("fin_estimado")
    temporal = bool(RE_TEMPORAL.search(normalizar(a.get("titulo") or ""))) or a.get("modalidad") == "bolsa"
    if any(x.get("tipo_acto") == "anulacion" for x in posteriores):
        estado = "anulado"
    elif fin:
        estado = "plazo_abierto" if fin >= hoy.isoformat() else "plazo_cerrado"
    elif solo_bases and not temporal and "Boletín Oficial del Estado" in (plazo.get("cuenta_desde") or ""):
        estado = "bases_publicadas_pendiente_boe"
    else:
        estado = "sin_datos_de_plazo"
    todos = [a] + posteriores + otras
    fuentes = sorted({x.get("fuente") or "BOE" for x in todos})
    citadas = [fuente_de_boletin(b.get("boletin")) for b in a.get("boletines_citados") or []]
    conv = ubicar_convocante(a.get("convocante"), [f for f in [*fuentes, *citadas] if f],
                             a.get("boletines_citados")) or {}
    comunidad = conv.get("comunidad") or (comunidad_de_fuentes(fuentes) if a.get("ambito") == "autonomico" else None)
    sistema, turno_, grupo_ = _rasgos_proceso(a, otras)
    return {
        "id": ident,
        "estado": estado,
        "sistema": sistema,
        "turno": turno_,
        "grupo": grupo_,
        "ambito": a.get("ambito"),
        "convocante": conv,
        "provincia": conv.get("provincia"),
        "comunidad": comunidad,
        "organismo": a.get("organismo") or a.get("departamento"),
        "titulo": a.get("titulo"),
        "plazas": [{k: p.get(k) for k in ("numero", "puesto_clave", "puesto", "especialidad", "denominacion", "grupo",
                                          "regimen", "sistema", "turno")} for p in a.get("plazas") or []],
        "total_plazas": a.get("total_plazas"),
        "plazo": _plazo_salida(plazo),
        "apertura_plazo": a["fecha"],
        "bases": [b for b in a.get("boletines_citados") or [] if b.get("papel") in ("bases", "extracto", "rectificacion")],
        "otras_publicaciones": [{**_ref(x), "titulo": x.get("titulo"), "tiene_texto": x.get("tiene_texto")} for x in otras],
        "actos": [_ref(x) for x in [a] + posteriores],
        "actualizado": max(x["fecha"] for x in todos),
        "fuente": NOMBRE_FUENTE.get(a["fuente"], a["fuente"]),
        "fuentes": fuentes,
        "pendiente": a.get("pendiente") or [],
        "temporal": temporal,
        "solo_bases_locales": solo_bases,
    }


def clave_convocante(x: dict) -> list[str]:
    """Claves con las que un acto identifica a su convocante: código INE o nombre del municipio (local) y el
    organismo normalizado."""
    claves = _municipio(x.get("convocante"), [x.get("fuente") or "BOE"]) if x.get("convocante") else []
    org = clave_titulo(x.get("organismo") or x.get("departamento"))
    if org and x.get("ambito") != "local":
        claves.append("orgn:" + org)
    return claves


RE_NOMBRAMIENTO_2A = re.compile(
    r"(?:nombra\w*|nombramiento).{0,120}(?:funcionari\w* de carrera|personal estatutario fijo|personal laboral fijo|"
    r"proceso selectivo|pruebas selectivas)|(?:funcionari\w* de carrera|personal estatutario fijo).{0,80}nombra\w*")


def leer_nombramientos_boe(raiz: Path) -> list[dict]:
    """Nombramientos de la sección II.A del BOE que cierran un proceso selectivo («se nombra personal funcionario de
    carrera del Cuerpo…»). Se leen de los sumarios ya guardados; el título va sin nombres de personas."""
    from motor.boe.clasificar import ambito
    from motor.limpieza import titulo_sin_nombres
    out = []
    for f in sorted((raiz / "datos" / "boe" / "sumarios").glob("*/*/*.jsonl")):
        for l in f.read_text(encoding="utf-8").splitlines():
            if '"2A"' not in l:
                continue
            x = json.loads(l)
            if x.get("seccion_codigo") != "2A" or not RE_NOMBRAMIENTO_2A.search(normalizar(x.get("titulo") or "")):
                continue
            out.append({"id": x["identificador"] if "identificador" in x else x.get("id"), "fecha": x["fecha"],
                        "fuente": "BOE", "titulo": titulo_sin_nombres(x.get("titulo") or ""),
                        "departamento": x.get("departamento"), "ambito": ambito(x.get("departamento")),
                        "tipo_acto": "nombramiento", "alcance": "acceso", "convocante": None,
                        "url": x.get("url_html") or x.get("url")})
    return [x for x in out if x["id"]]


def construir_y_unir(actos: list[dict], hoy: date, autonomicos: list[dict] | None = None,
                     extra: list[dict] | None = None) -> tuple[list[dict], dict, list[dict]]:
    """Procesos con sus actos posteriores unidos (motor/union.py). Devuelve (procesos, recuento, huérfanos).
    extra: actos que no crean procesos y solo se unen (nombramientos de la sección II.A del BOE)."""
    from motor.union import fase_y_estado, unir
    autonomicos = autonomicos or []
    procesos = construir(actos, hoy, autonomicos)
    por_id = {a["id"]: a for a in actos}
    por_id.update({x["id"]: x for x in autonomicos})
    origenes = {p["id"]: por_id.get(p["actos"][0]["id"]) for p in procesos if p.get("actos")}
    recuento, huerfanos = unir(procesos, origenes, actos + autonomicos + (extra or []), clave_convocante)
    for p in procesos:
        fase_y_estado(p, hoy)
    return procesos, dict(recuento), huerfanos


def cobertura(procesos: list[dict]) -> dict:
    """Control del modelo: cada anuncio local del BOE debe tener sus bases localizadas en el boletín que cita. Por
    boletín citado: cuántas bases cita el BOE, cuántas están enlazadas y si el boletín tiene conector."""
    con_conector = set(NOMBRE_FUENTE)
    por_boletin: dict[str, Counter] = defaultdict(Counter)
    sin_localizar: dict[str, list[str]] = defaultdict(list)
    sin_cita = 0
    for p in procesos:
        if not p["id"].startswith("boe:") or p.get("ambito") != "local":
            continue
        bases = [b for b in p.get("bases") or [] if b.get("papel") == "bases"]
        if not bases:
            sin_cita += 1
            continue
        enlazadas = {o.get("fuente") for o in p.get("otras_publicaciones") or []}
        for b in bases[:1]:
            f = fuente_de_boletin(b.get("boletin")) or f"sin identificar: {b.get('boletin')}"
            c = por_boletin[f]
            c["citadas"] += 1
            if f in enlazadas:
                c["enlazadas"] += 1
            elif len(sin_localizar[f]) < 20:
                sin_localizar[f].append(p["id"])
    filas = {f: {"citadas": c["citadas"], "enlazadas": c["enlazadas"],
                 "porcentaje": round(100 * c["enlazadas"] / c["citadas"], 1) if c["citadas"] else None,
                 "conector": f in con_conector, "ejemplos_sin_localizar": sin_localizar.get(f, [])[:10]}
             for f, c in sorted(por_boletin.items(), key=lambda kv: -kv[1]["citadas"])}
    citadas = sum(v["citadas"] for v in filas.values())
    enlazadas = sum(v["enlazadas"] for v in filas.values())
    return {"anuncios_locales_con_cita_de_bases": citadas, "con_bases_localizadas": enlazadas,
            "sin_cita_de_bases": sin_cita,
            "citas_a_boletines_sin_conector": sum(v["citadas"] for v in filas.values() if not v["conector"]),
            "por_boletin": filas}


def resumen(procesos: list[dict], hoy: date) -> dict:
    abiertos = [p for p in procesos if p["estado"] == "plazo_abierto"]
    por_provincia, por_comunidad, por_puesto, por_fuente = Counter(), Counter(), Counter(), Counter()
    for p in abiertos:
        por_provincia[p.get("provincia") or "sin provincia"] += p.get("total_plazas") or 0
        por_comunidad[p.get("comunidad") or ("estatal" if p.get("ambito") == "estatal" else "sin comunidad")] += 1
        for pl in p["plazas"]:
            por_puesto[pl.get("puesto_clave") or "sin puesto"] += pl.get("numero") or 0
        for f in p.get("fuentes") or ["BOE"]:
            por_fuente[f] += 1
    locales_boe = [p for p in procesos if p["id"].startswith("boe:") and p.get("ambito") == "local"]
    enlaces = Counter(o["fuente"] for p in locales_boe for o in p.get("otras_publicaciones") or [])
    return {
        "fecha": hoy.isoformat(),
        "procesos": len(procesos),
        "enlaces_locales": {
            "anuncios_locales_del_boe": len(locales_boe),
            "con_bases_enlazadas": sum(1 for p in locales_boe if p.get("otras_publicaciones")),
            "bases_enlazadas_por_fuente": dict(enlaces.most_common()),
            "procesos_solo_con_bases_locales": dict(Counter(p["fuentes"][0] for p in procesos
                                                            if p.get("solo_bases_locales")).most_common()),
        },
        "por_estado": dict(Counter(p["estado"] for p in procesos)),
        "por_fuente": dict(Counter(f for p in procesos for f in p.get("fuentes") or ["BOE"])),
        "plazo_abierto": {"procesos": len(abiertos), "plazas": sum(p.get("total_plazas") or 0 for p in abiertos),
                          "por_provincia": dict(por_provincia.most_common()),
                          "procesos_por_comunidad": dict(por_comunidad.most_common()), "por_puesto": dict(por_puesto.most_common(50)),
                          "por_fuente": dict(por_fuente.most_common())},
        "aviso": "Fechas de fin estimadas con festivos nacionales; comprobar siempre en el boletín oficial.",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--hoy", type=date.fromisoformat, default=datetime.now(MADRID).date())
    a = p.parse_args(argv)
    procesos, uniones, huerfanos = construir_y_unir(leer_actos(a.salida), a.hoy, leer_actos_autonomicos(a.salida),
                                                    leer_nombramientos_boe(a.salida))
    destino = a.salida / "datos" / "oposiciones"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "procesos.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in procesos),
                                            encoding="utf-8")
    # Cola de huérfanos: actos posteriores que no se han podido unir con seguridad, para revisarlos
    (destino / "huerfanos.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in huerfanos),
                                             encoding="utf-8")
    r = resumen(procesos, a.hoy)
    cob = cobertura(procesos)
    (destino / "cobertura.json").write_text(json.dumps(cob, ensure_ascii=False, indent=1), encoding="utf-8")
    r["cobertura_bases"] = {k: v for k, v in cob.items() if k != "por_boletin"}
    r["uniones"] = {"actos_unidos": sum(v for k, v in uniones.items() if not k.startswith("huerfano:")),
                    "huerfanos": len(huerfanos), "por_motivo": dict(sorted(uniones.items(), key=lambda kv: -kv[1])),
                    "procesos_con_actos_posteriores": sum(1 for p in procesos if len(p.get("actos") or []) > 1),
                    "por_fase": dict(Counter(p.get("fase") for p in procesos if p.get("fase")).most_common())}
    (destino / "resumen.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: r[k] for k in ("procesos", "por_estado", "uniones")}, ensure_ascii=False))
    print("Plazo abierto hoy:", r["plazo_abierto"]["procesos"], "procesos,", r["plazo_abierto"]["plazas"], "plazas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
