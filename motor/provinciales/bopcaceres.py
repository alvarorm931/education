"""Conector del Boletín Oficial de la Provincia de Cáceres (servicios JSON de su portal).

Formato verificado el 30/10/2026 desde GitHub (también para 2022):
  - Boletines de un mes: https://bop.dip-caceres.es/bop/services/boletines/bopMesAntSig?mes=M&anio=AAAA, con el
    identificador de cada boletín (correlativo: 4979 el 03/01/2022, 6181 el 30/10/2026) y su día.
  - Último boletín: /bop/services/boletines/ultimoBop.
  - Anuncios de un boletín, con su texto: /bop/services/anuncios/anunciosAnunciantes?idBoletin=N. Por anuncio: csv
    («BOP-2026-5048», su código), numBop, sección («Sección I - Administración Local»), grupo («Ayuntamientos»),
    entidad, título (empieza por el código), el texto en HTML (contenidoHtml) y el PDF.
  - El texto llega con el sumario: no hace falta una petición por anuncio. Solo se guarda limpio y, en nombramientos,
    listas y resultados, solo se cuenta (nombran a las personas).
  - robots.txt cierra anuncios concretos por su código (retirados por privacidad): esos no se guardan.

Uso:
  python -m motor.provinciales.bopcaceres --salida ruta/                                  # este mes y el anterior
  python -m motor.provinciales.bopcaceres --desde 2022-01-01 --max-minutos 30 --salida ruta/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (Freno, clasificar, convocante_de_organismo, es_empleo_estricto, escribir_json,
                                     escribir_jsonl)
from motor.boe.clasificar import normalizar
from motor.http import obtener, robots_de
from motor.limpieza import RE_DOCUMENTO, limpiar_html, texto_de
from motor.provinciales.comun import CON_TEXTO

FUENTE = "bopcaceres"
SIGLAS = "BOP-CACERES"
MADRID = ZoneInfo("Europe/Madrid")
WEB = "https://bop.dip-caceres.es"
SERVICIOS = WEB + "/bop/services"
NOMBRES = ("Boletín Oficial de la Provincia de Cáceres",)
RE_CODIGO = re.compile(r"BOP-\d{4}-\d+(?!\d)")


def url_mes(anio: int, mes: int) -> str:
    return f"{SERVICIOS}/boletines/bopMesAntSig?mes={mes}&anio={anio}"


def url_boletin(id_boletin: int) -> str:
    return f"{SERVICIOS}/anuncios/anunciosAnunciantes?idBoletin={id_boletin}"


def boletines_del_mes(contenido: bytes, anio: int, mes: int) -> list[dict]:
    j = json.loads(contenido.decode("utf-8"))
    return [{"id_boletin": x["idBoletin"], "fecha": date(anio, mes, x["diaBop"]).isoformat()}
            for x in j.get("data") or [] if x.get("idBoletin") and x.get("diaBop")]


def _fecha(ms: int | None) -> str | None:
    return datetime.fromtimestamp(ms / 1000, MADRID).date().isoformat() if ms else None


def leer_boletin(contenido: bytes) -> dict:
    datos = json.loads(contenido.decode("utf-8")).get("data") or []
    anuncios = []
    for a in datos:
        titulo = " ".join((a.get("tituloAnuncio") or "").split())
        codigo = a.get("csv") or (RE_CODIGO.match(titulo).group(0) if RE_CODIGO.match(titulo) else None)
        if codigo and titulo.startswith(codigo):
            titulo = titulo[len(codigo):].strip()
        anuncios.append({"numero_anuncio": codigo or str(a.get("idAnuncio")), "seccion": a.get("nombreTipoEntidad"),
                         "grupo": a.get("nombreGrupoEntidad"), "entidad": a.get("nombreEntidad"), "titulo": titulo,
                         "url_pdf": f"{WEB}/bop/{a['urlPdf']}" if a.get("urlPdf") else None,
                         "url_anuncio": f"{WEB}/bop/anuncio.html?csv={codigo}" if codigo else None,
                         "_html": a.get("contenidoHtml") or ""})
    return {"fecha": _fecha(datos[0].get("fechaPublicacion")) if datos else None,
            "numero": str(datos[0].get("numBop")) if datos and datos[0].get("numBop") else None, "anuncios": anuncios}


def retirados(sesion=None) -> set[str]:
    """Códigos de los anuncios que robots.txt cierra uno a uno (retirados por privacidad)."""
    try:
        reglas = robots_de(WEB + "/bop/", sesion).reglas or []
    except Exception:  # sin robots.txt legible no hay lista: se sigue con la regla general de http.py
        return set()
    return {c for permite, ruta, *_ in reglas if not permite for c in RE_CODIGO.findall(ruta)}


def texto_anuncio(x: dict) -> dict:
    if x.get("tipo_acto") not in CON_TEXTO:
        lineas = [texto_de(b) for b in re.split(r"</(?:p|tr|li)>", x["_html"])]
        return {"titulo": x["titulo"], "texto": None, "tablas": [], "solo_recuento": True,
                "lineas_con_documento_de_identidad": sum(1 for l in lineas if RE_DOCUMENTO.search(l))}
    return {"titulo": x["titulo"], **limpiar_html(x["_html"])}


def es_local(x: dict) -> bool:
    return "administracion local" in normalizar(x.get("seccion") or "")


def convocante(x: dict) -> dict | None:
    c = convocante_de_organismo(x.get("entidad") or "")
    if c and not c.get("provincia"):
        c["provincia"] = "Cáceres"
    return c


def seleccionar(filas: list[dict]) -> list[dict]:
    out = []
    for x in filas:
        if not es_empleo_estricto(x["titulo"]):
            continue
        local = es_local(x)
        out.append({**x, "ambito": "local" if local else "otro", **clasificar(x["titulo"]),
                    "convocante": convocante(x) if local else None})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "provinciales" / FUENTE


def _ruta(raiz: Path, carpeta: str, fecha: str, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / fecha[:4] / fecha[5:7] / f"{fecha[8:10]}.{ext}"


def procesar_boletin(b: dict, raiz: Path, archivo: Archivo, cerrados: set[str]) -> dict:
    url = url_boletin(b["id_boletin"])
    r = obtener(url, accept="application/json")
    inf = {**b, "status": r.status, "alertas": []}
    if r.status != 200:
        inf["resultado"] = "error_http"
        inf["alertas"].append(f"BOP Cáceres {b['fecha']}: HTTP {r.status}")
        return inf
    try:
        s = leer_boletin(r.contenido)
    except ValueError:
        inf["resultado"] = "error_formato"
        inf["alertas"].append(f"BOP Cáceres {b['fecha']}: la respuesta no es JSON")
        return inf
    if s["fecha"] != b["fecha"]:
        inf["resultado"] = "error_formato"
        inf["alertas"].append(f"BOP Cáceres {b['id_boletin']}: el boletín es del {s['fecha']}, no del {b['fecha']}")
        return inf
    d = date.fromisoformat(b["fecha"])
    captura = archivo.guardar(FUENTE, d, r.contenido, url, "json", r.status, r.cabeceras)
    vistos = [x for x in s["anuncios"] if x["numero_anuncio"] not in cerrados]
    filas = [{**x, "id": x["numero_anuncio"], "fecha": b["fecha"], "boletin": s["numero"],
              "id_boletin": b["id_boletin"], "fuente": SIGLAS, "captura_sha256": captura["sha256"]} for x in vistos]
    empleo = seleccionar(filas)
    for x in empleo:
        ruta = _base(raiz) / "textos" / b["fecha"][:4] / b["fecha"][5:7] / f"{x['id']}.json"
        if x["_html"] and not ruta.exists():
            escribir_json(ruta, {"id": x["id"], "url": x["url_anuncio"], "fecha": b["fecha"], **texto_anuncio(x)})
    sin_html = lambda fs: [{k: v for k, v in f.items() if k != "_html"} for f in fs]
    escribir_jsonl(_ruta(raiz, "disposiciones", b["fecha"]), sin_html(filas))
    escribir_jsonl(_ruta(raiz, "oposiciones", b["fecha"]), sin_html(empleo))
    inf.update({"resultado": "ok", "numero": s["numero"], "sha256": captura["sha256"], "disposiciones": len(filas),
                "empleo_publico": len(empleo), "retirados_por_privacidad": len(s["anuncios"]) - len(vistos)})
    if not filas:
        inf["alertas"].append(f"BOP Cáceres {b['fecha']}: boletín sin anuncios (posible cambio de formato)")
    return inf


def meses(desde: date, hasta: date) -> list[tuple[int, int]]:
    out, a, m = [], hasta.year, hasta.month
    while (a, m) >= (desde.year, desde.month):
        out.append((a, m))
        a, m = (a, m - 1) if m > 1 else (a - 1, 12)
    return out


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=date.fromisoformat, default=(hoy.replace(day=1) - timedelta(days=1)).replace(day=1))
    p.add_argument("--hasta", type=date.fromisoformat, default=hoy)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    cerrados = retirados()
    inicio, informes, freno = time.monotonic(), [], Freno()
    for anio, mes in meses(a.desde, a.hasta):
        if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
            print("Tiempo agotado; se continúa en la siguiente ejecución")
            break
        cal = _base(a.salida) / "calendario" / f"{anio}-{mes:02d}.json"
        if cal.exists():
            lista = json.loads(cal.read_text(encoding="utf-8"))
        else:
            try:
                r = obtener(url_mes(anio, mes), accept="application/json")
                lista = boletines_del_mes(r.contenido, anio, mes) if r.status == 200 else None
            except (ConnectionError, TimeoutError, ValueError):
                lista = None
            time.sleep(a.pausa)
            if lista is None:
                print(f"::warning::BOP Cáceres {anio}-{mes:02d}: no se pudo leer el calendario")
                continue
            if (anio, mes) < (hoy.year, hoy.month):
                escribir_json(cal, lista)
        parar = False
        for b in sorted(lista, key=lambda x: x["fecha"], reverse=True):
            if not (a.desde.isoformat() <= b["fecha"] <= a.hasta.isoformat()):
                continue
            ruta = _ruta(a.salida, "boletines", b["fecha"], "json")
            if ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") == "ok":
                continue
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                parar = True
                break
            try:
                inf = procesar_boletin(b, a.salida, archivo, cerrados)
            except (ConnectionError, TimeoutError) as e:
                inf = {**b, "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            escribir_json(ruta, inf)
            informes.append(inf)
            print(f"BOP Cáceres {b['fecha']}: {inf['resultado']} {inf.get('disposiciones', '')} anuncios, "
                  f"{inf.get('empleo_publico', '')} de empleo")
            time.sleep(a.pausa)
            if freno.anotar(inf):
                parar = True
                break
        if parar:
            print("Se para; se continúa en la siguiente ejecución")
            break
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Boletines procesados: {len(informes)}. Alertas: {len(alertas)}")
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
