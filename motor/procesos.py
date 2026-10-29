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
    "BOPB": "Butlletí Oficial de la Província de Barcelona",
    "BOP-ALICANTE": "Boletín Oficial de la Provincia de Alicante",
    "BOP-VALENCIA": "Butlletí Oficial de la Província de València",
    "BOPT": "Butlletí Oficial de la Província de Tarragona",
    "BOP-CIUDADREAL": "Boletín Oficial de la Provincia de Ciudad Real",
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
    "diario oficial de castilla-la mancha": "DOCM",
    "diario oficial de castilla la mancha": "DOCM",
    "boletin oficial de la ciudad de melilla": "BOME",
    "boletin oficial de la ciudad autonoma de melilla": "BOME",
    "boletin oficial del pais vasco": "BOPV",
    "butlleti oficial de les illes balears": "BOIB",
    "boletin oficial de las illes balears": "BOIB",
    "boletin oficial de las islas baleares": "BOIB",
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
}
RE_NO_ALFANUM = re.compile(r"[^a-z0-9ñ]+")


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
            fuente = BOLETIN_A_FUENTE.get(normalizar(b.get("boletin") or ""))
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
    citadas = [BOLETIN_A_FUENTE.get(normalizar(b.get("boletin") or "")) for b in a.get("boletines_citados") or []]
    conv = ubicar_convocante(a.get("convocante"), [f for f in [*fuentes, *citadas] if f],
                             a.get("boletines_citados")) or {}
    comunidad = conv.get("comunidad") or (comunidad_de_fuentes(fuentes) if a.get("ambito") == "autonomico" else None)
    return {
        "id": ident,
        "estado": estado,
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
    return {
        "fecha": hoy.isoformat(),
        "procesos": len(procesos),
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
    procesos = construir(leer_actos(a.salida), a.hoy, leer_actos_autonomicos(a.salida))
    destino = a.salida / "datos" / "oposiciones"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "procesos.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in procesos),
                                            encoding="utf-8")
    r = resumen(procesos, a.hoy)
    (destino / "resumen.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: r[k] for k in ("procesos", "por_estado", "por_fuente")}, ensure_ascii=False))
    print("Plazo abierto hoy:", r["plazo_abierto"]["procesos"], "procesos,", r["plazo_abierto"]["plazas"], "plazas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
