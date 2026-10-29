"""Conector del Boletín Oficial de la Provincia de Alicante (BOP de Alicante).

Formato verificado el 29/10/2026 desde GitHub (también para 2022): servicio JSON de la sede de la Diputación
que usa su página «Consultas BOP».
  https://sede.diputacionalicante.es/wp-content/themes/Desarrollo-Diputacion/webservices/wseConsultaAjax.php
      ?nemo=BOP_CON&usuario=-&param=<raiz><entrada><registro><fechaPub>28/10/2026</fechaPub>
      <tipoorganismo>4</tipoorganismo></registro></entrada></raiz>
  - tipoorganismo 4 = «III. Administración local».
  - Respuesta: boletin.boletin[0].registro[0] (número, sumario y boletín completo en PDF) y
    boletin.bop[0].registro[] con un edicto por registro: anyo, edicto (número), extracto (título), ampliacion
    (organismo), denominacion (municipio, con su nombre oficial bilingüe), desecun (tipo de entidad), errata,
    ubicacion (PDF del edicto).
  - Sin boletín ese día: {"error": "No existen datos en la consulta realizada..."}.
  - Texto: PDF del edicto. Los anuncios van en castellano o en valenciano.

Uso:
  python -m motor.provinciales.bopalicante --salida ruta/                                   # ayer y hoy
  python -m motor.provinciales.bopalicante --desde 2022-01-01 --max-minutos 30 --salida ruta/
  python -m motor.provinciales.bopalicante --textos --max-minutos 30 --salida ruta/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (clasificar, convocante_de_organismo, descargar_textos,
                                     es_empleo_estricto, escribir_json, escribir_jsonl, leer_jsonl)
from motor.http import obtener
from motor.provinciales.comun import CON_TEXTO, texto_pdf

FUENTE = "bopalicante"
SIGLAS = "BOP-ALICANTE"
MADRID = ZoneInfo("Europe/Madrid")
SERVICIO = ("https://sede.diputacionalicante.es/wp-content/themes/Desarrollo-Diputacion/webservices/"
            "wseConsultaAjax.php")
ADMINISTRACION_LOCAL = "4"
NOMBRES = ("Boletín Oficial de la Provincia de Alicante", "Butlletí Oficial de la Província d'Alacant",
           "Butlletí Oficial de la Província d’Alacant", "BOP de Alicante")
RE_CABECERA_PDF = re.compile(
    r"^(?:boletín oficial de la provincia de alicante|butlletí oficial de la província d.alacant|"
    r"edita excma\. diputación provincial de alicante|depósito legal.*|https?://www\.dip-alicante\.es.*|"
    r"n.º \d+ de \d{2}/\d{2}/\d{4}|edicto \d+ / \d+|\d+ / \d+|pág\. \d+.*|ilustre colegio.*)$", re.IGNORECASE)


def url_dia(d: date, tipo: str = ADMINISTRACION_LOCAL) -> str:
    param = (f"<raiz><entrada><registro><fechaPub>{d:%d/%m/%Y}</fechaPub><tipoorganismo>{tipo}</tipoorganismo>"
             "</registro></entrada></raiz>")
    return f"{SERVICIO}?nemo=BOP_CON&usuario=-&param={urllib.parse.quote(param)}"


def _plano(r: dict) -> dict:
    return {k: (v[0] if isinstance(v, list) and v else (None if isinstance(v, list) else v)) for k, v in r.items()}


def parsear_dia(contenido: bytes) -> dict:
    datos = json.loads(contenido.decode("utf-8-sig"))
    if "boletin" not in datos:
        return {"sin_boletin": True, "mensaje": datos.get("error") or datos.get("bopError")}
    b = datos["boletin"]
    cab = _plano(((b.get("boletin") or b.get("ultimoboletin") or [{}])[0].get("registro") or [{}])[0])
    edictos = [_plano(r) for r in ((b.get("bop") or [{}])[0].get("registro") or [])]
    return {"sin_boletin": False, "sumario": cab.get("sumario"), "url_sumario": cab.get("urlsumario"),
            "url_boletin": cab.get("urlbopcompleto"), "edictos": edictos}


def disposicion(e: dict, d: date) -> dict:
    return {
        "id": f"BOPALICANTE-{e.get('anyo')}-{e.get('edicto')}", "edicto": e.get("edicto"), "anyo": e.get("anyo"),
        "fecha": d.isoformat(), "boletin": e.get("nBop"), "seccion": e.get("gndenom"), "subseccion": e.get("desecun"),
        "organismo": " ".join((e.get("ampliacion") or "").split()), "municipio": e.get("denominacion"),
        "tipo_entidad": e.get("abreviatura"), "titulo": " ".join((e.get("extracto") or "").split()),
        "errata": e.get("errata"), "url_pdf": e.get("ubicacion"), "url_html": None, "fuente": SIGLAS,
    }


def convocante(x: dict) -> dict | None:
    if (x.get("subseccion") or "").upper().startswith("AYUNTAMIENTOS") and x.get("municipio"):
        return {"tipo": "Ayuntamiento", "nombre": x["municipio"], "provincia": "Alicante", "organismo": x["organismo"]}
    c = convocante_de_organismo(x.get("organismo") or "")
    if c and not c.get("provincia"):
        c["provincia"] = "Alicante"
    return c


def seleccionar(disposiciones: list[dict]) -> list[dict]:
    out = []
    for x in disposiciones:
        t = x["titulo"]
        if not es_empleo_estricto(t):
            continue
        out.append({**x, "ambito": "local", **clasificar(t, x.get("subseccion")), "convocante": convocante(x)})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "provinciales" / FUENTE


def _ruta(raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


def procesar_dia(d: date, raiz: Path, archivo: Archivo) -> dict:
    url = url_dia(d)
    r = obtener(url, accept="application/json")
    informe = {"fecha": d.isoformat(), "status": r.status, "alertas": []}
    if r.status != 200:
        informe["resultado"] = "error_http"
        informe["alertas"].append(f"BOP Alicante {d}: HTTP {r.status}")
        return informe
    try:
        s = parsear_dia(r.contenido)
    except (ValueError, KeyError, IndexError) as e:
        informe["resultado"] = "error_formato"
        informe["alertas"].append(f"BOP Alicante {d}: respuesta no reconocida ({e})")
        return informe
    if s["sin_boletin"]:
        informe["resultado"] = "sin_boletin"
        return informe
    captura = archivo.guardar(FUENTE, d, r.contenido, url, "json", r.status, r.cabeceras)
    filas = [disposicion(e, d) | {"captura_sha256": captura["sha256"]} for e in s["edictos"]]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    informe.update({"resultado": "ok", "sumario": s["sumario"], "url_sumario": s["url_sumario"],
                    "url_boletin": s["url_boletin"], "sha256": captura["sha256"], "disposiciones": len(filas),
                    "empleo_publico": len(empleo)})
    if not filas:
        informe["alertas"].append(f"BOP Alicante {d}: boletín sin edictos locales (posible cambio de formato)")
    return informe


def texto_disposicion(contenido: bytes, con_texto: bool = True) -> dict:
    return texto_pdf(contenido, con_texto, RE_CABECERA_PDF)


def ruta_texto(raiz: Path, x: dict) -> Path:
    return _base(raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"


def textos_pendientes(raiz: Path) -> list[dict]:
    lista = []
    for f in (_base(raiz) / "oposiciones").glob("*/*/*.jsonl"):
        lista += [x for x in leer_jsonl(f) if x.get("url_pdf") and not ruta_texto(raiz, x).exists()]
    lista.sort(key=lambda x: x["fecha"], reverse=True)
    return sorted(lista, key=lambda x: (0 if x.get("tipo_acto") in CON_TEXTO else 1,
                                        0 if x.get("alcance") in (None, "acceso") else 1))


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=date.fromisoformat, default=hoy - timedelta(days=1))
    p.add_argument("--hasta", type=date.fromisoformat, default=hoy)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--textos", action="store_true")
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())

    if a.textos:
        pend = textos_pendientes(a.salida)
        hechos, errores = descargar_textos(
            pend, lambda x: ruta_texto(a.salida, x), lambda x: x["url_pdf"],
            lambda c, x: texto_disposicion(c, x.get("tipo_acto") in CON_TEXTO), archivo, FUENTE, a.max_minutos,
            a.pausa, accept="application/pdf", ext="pdf", por_registro=True)
        print(f"BOP Alicante textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        return 0

    inicio, informes = time.monotonic(), []
    d = a.hasta
    while d >= a.desde:  # del más reciente al más antiguo; lo ya hecho no se repite (salvo ayer y hoy)
        ruta = _ruta(a.salida, "dias", d, "json")
        hecho = ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") in {"ok", "sin_boletin"}
        if not hecho or d >= hoy - timedelta(days=1):
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                break
            try:
                inf = procesar_dia(d, a.salida, archivo)
            except (ConnectionError, TimeoutError) as e:
                inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            if not (inf.get("resultado") == "sin_boletin" and d >= hoy):
                escribir_json(ruta, inf)
            informes.append(inf)
            print(f"BOP Alicante {d}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            time.sleep(a.pausa)
        d -= timedelta(days=1)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    for x in alertas[:30]:
        print(" -", x)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
