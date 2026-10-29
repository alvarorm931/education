"""Conector del Boletín Oficial de la Junta de Andalucía (BOJA) por su API de datos abiertos (CC BY 4.0).

API: https://datos.juntadeandalucia.es/api/v0/boja/  (OpenAPI en /openapi.json)
  - get/calendar?year=AAAA            -> números de boletín (ordinarios y extraordinarios) con su fecha
  - get/bulletin?year=AAAA&number=N   -> todas las disposiciones del boletín, con texto completo

Uso:
  python -m motor.autonomicos.boja --desde-anio 2022 --hasta-anio 2026 --salida ruta/ [--sin-guardar-original]

Guarda:
  datos/autonomicos/boja/disposiciones/AAAA/NNNNNN.jsonl  metadatos de todas las disposiciones (sin texto)
  datos/autonomicos/boja/oposiciones/AAAA/NNNNNN.jsonl    sección 2.2 y anuncios de entidades locales sobre
                                                          plazas, con texto limpio de datos personales
  datos/autonomicos/boja/boletines/AAAA/NNNNNN.json       informe por boletín (para reanudar y controlar huecos)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo
from motor.boe.clasificar import REGLAS_ACTO, REGLAS_MODALIDAD, _primera, normalizar
from motor.http import obtener
from motor.limpieza import limpiar_html

BASE = "https://datos.juntadeandalucia.es/api/v0/boja"
FUENTE = "boja"
MADRID = ZoneInfo("Europe/Madrid")
ORGANISMOS_LOCALES = ("ayuntamiento", "diputacion", "mancomunidad", "consorcio", "entidad local", "entidades locales",
                      "agencia publica administrativa local", "patronato")
RE_PLAZAS_LOCAL = re.compile(
    r"\b(plazas?|convocatoria|bases|seleccion|bolsa|oposicion|concurso|proceso selectivo|personal|funcionari|"
    r"laboral fij|empleo publico)\b")


def fecha_iso(ddmmaaaa: str) -> str | None:
    try:
        return datetime.strptime(ddmmaaaa, "%d/%m/%Y").date().isoformat()
    except (TypeError, ValueError):
        return None


def ambito(organismo: str, titulo: str) -> str:
    o, t = normalizar(organismo or ""), normalizar(titulo or "")
    if any(x in o for x in ORGANISMOS_LOCALES) or re.search(r"\bdel ayuntamiento de\b|\bde la diputacion provincial\b", t):
        return "local"
    if "universidad" in o or re.search(r"\bde la universidad de\b", t):
        return "universidad"
    return "autonomico"


def es_oposicion(disp: dict) -> bool:
    if (disp.get("sectionN2") or "").startswith("2.2"):
        return True
    t = normalizar(disp.get("summaryNoHtml") or "")
    return ambito(disp.get("organisation") or "", t) == "local" and bool(RE_PLAZAS_LOCAL.search(t)) \
        and not re.search(r"\b(subvencion|licencia|urbanis|ordenanza|presupuesto|expropiacion)", t)


def metadatos(disp: dict, numero: int) -> dict:
    pdfs = disp.get("pdf") or []
    return {
        "id": disp.get("id"),
        "boletin": numero,
        "fecha": fecha_iso(disp.get("date")),
        "seccion": disp.get("sectionN1"),
        "subseccion": disp.get("sectionN2"),
        "organismo": " ".join((disp.get("organisation") or "").replace("\xa0", " ").split()),
        "tipo_disposicion": disp.get("type"),
        "titulo": " ".join((disp.get("summaryNoHtml") or "").split()),
        "paginas": [disp.get("startPageDisposition"), disp.get("endPageDisposition")],
        "url_pdf": pdfs[0].get("publicUrl") if pdfs else None,
        "version": disp.get("version"),
    }


def procesar_boletin(anio: int, numero: int, raiz: Path, archivo: Archivo, guardar_original: bool) -> dict:
    url = f"{BASE}/get/bulletin?year={anio}&number={numero}"
    resp = obtener(url, accept="application/json", timeout=120)
    informe = {"anio": anio, "numero": numero, "status": resp.status, "alertas": []}
    if resp.status != 200:
        informe["resultado"] = "error_http"
        informe["alertas"].append(f"BOJA {anio}/{numero}: HTTP {resp.status}")
        return informe
    try:
        datos = json.loads(resp.contenido)
        disposiciones = datos["results"]
    except (ValueError, KeyError) as e:
        informe["resultado"] = "error_formato"
        informe["alertas"].append(f"BOJA {anio}/{numero}: formato inesperado ({e})")
        return informe

    fecha = fecha_iso(disposiciones[0].get("date")) if disposiciones else None
    fecha_ref = date.fromisoformat(fecha) if fecha else date(anio, 1, 1)
    if guardar_original:
        captura = archivo.guardar(FUENTE, fecha_ref, resp.contenido, url, "json", resp.status, resp.cabeceras)
    else:
        captura = archivo.registrar(FUENTE, fecha_ref, resp.contenido, url, resp.status, resp.cabeceras)

    filas, opos = [], []
    for d in disposiciones:
        meta = metadatos(d, numero)
        meta.update({"fuente": "BOJA", "captura_sha256": captura["sha256"], "capturado": captura["capturado"]})
        filas.append(meta)
        if es_oposicion(d):
            t = normalizar(meta["titulo"])
            limpio = limpiar_html(d.get("body") or "")
            opos.append({
                **meta,
                "ambito": ambito(meta["organismo"], meta["titulo"]),
                "tipo_acto": _primera(REGLAS_ACTO, t) or "otro",
                "modalidad": _primera(REGLAS_MODALIDAD, t),
                **limpio,
            })

    base = raiz / "datos" / "autonomicos" / "boja"
    for carpeta, contenido in (("disposiciones", filas), ("oposiciones", opos)):
        destino = base / carpeta / str(anio) / f"{numero:06d}.jsonl"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in contenido), encoding="utf-8")

    if datos.get("total_hits") is not None and datos["total_hits"] != len(disposiciones):
        informe["alertas"].append(f"BOJA {anio}/{numero}: total_hits {datos['total_hits']} y recibidas {len(disposiciones)}")
    informe.update({
        "resultado": "ok", "fecha": fecha, "sha256": captura["sha256"], "original_guardado": guardar_original,
        "disposiciones": len(filas), "oposiciones": len(opos),
        "por_ambito": dict(Counter(o["ambito"] for o in opos)),
    })
    return informe


def ruta_informe(raiz: Path, anio: int, numero: int) -> Path:
    return raiz / "datos" / "autonomicos" / "boja" / "boletines" / str(anio) / f"{numero:06d}.json"


def calendario(anio: int, raiz: Path, archivo: Archivo) -> list[tuple[int, str]]:
    url = f"{BASE}/get/calendar?year={anio}"
    resp = obtener(url, accept="application/json")
    if resp.status != 200:
        raise ConnectionError(f"calendario BOJA {anio}: HTTP {resp.status}")
    archivo.guardar(FUENTE + "-calendario", date(anio, 1, 1), resp.contenido, url, "json", resp.status, resp.cabeceras)
    filas = json.loads(resp.contenido)["rows"]
    return sorted((int(n), fecha_iso(f) or "") for n, f in filas)


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde-anio", type=int, default=hoy.year)
    p.add_argument("--hasta-anio", type=int, default=hoy.year)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--pausa", type=float, default=1.0)
    p.add_argument("--sin-guardar-original", action="store_true",
                   help="solo registrar la huella del original (cargas históricas grandes hasta tener almacén externo)")
    p.add_argument("--max-minutos", type=float, default=0)
    a = p.parse_args(argv)

    archivo = Archivo(a.salida / "archivo")
    inicio, informes = time.monotonic(), []
    for anio in range(a.desde_anio, a.hasta_anio + 1):
        try:
            numeros = calendario(anio, a.salida, archivo)
        except ConnectionError as e:
            informes.append({"anio": anio, "resultado": "fuente_inaccesible", "alertas": [str(e)]})
            continue
        resumen_cal = a.salida / "datos" / "autonomicos" / "boja" / "calendario" / f"{anio}.json"
        resumen_cal.parent.mkdir(parents=True, exist_ok=True)
        resumen_cal.write_text(json.dumps(numeros, ensure_ascii=False), encoding="utf-8")
        for numero, fecha in numeros:
            if fecha and fecha > hoy.isoformat():
                continue
            ruta = ruta_informe(a.salida, anio, numero)
            if ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") == "ok":
                continue
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                return 0
            try:
                inf = procesar_boletin(anio, numero, a.salida, archivo, not a.sin_guardar_original)
            except ConnectionError as e:
                inf = {"anio": anio, "numero": numero, "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            inf["fecha_calendario"] = fecha
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text(json.dumps(inf, ensure_ascii=False, indent=1), encoding="utf-8")
            informes.append(inf)
            print(f"BOJA {anio}/{numero} {fecha}: {inf.get('resultado')} "
                  f"{inf.get('disposiciones', '')} disposiciones, {inf.get('oposiciones', '')} de oposiciones")
            time.sleep(a.pausa)
    errores = [x for i in informes for x in i.get("alertas", [])]
    print(f"Boletines procesados: {len(informes)}. Alertas: {len(errores)}")
    for e in errores[:50]:
        print(" -", e)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
