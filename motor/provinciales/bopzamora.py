"""Conector del Boletín Oficial de la Provincia de Zamora.

Formato verificado el 30/10/2026 desde GitHub:
  - Portada https://www.diputaciondezamora.es/opencms/servicios/BOP/bop/index.html: los últimos 8 boletines, cada uno
    con su índice /opencms/servicios/BOP/indice-bop/UUID/, tipo («ORDINARIO», «EXTRAORDINARIO»), número y fecha.
  - Índice de un boletín: por anuncio, sección (div.sub-header «III. ADMINISTRACIÓN LOCAL»), «Procedencia»
    («AYUNTAMIENTOS», «DIPUTACIÓN PROVINCIAL DE ZAMORA»), «Organismo» («Ayuntamiento de Benavente»), «Extracto» (el
    asunto), «Nº de referencia» y el PDF del anuncio (/.Archivos/documentos/BOP/anuncios/AAAA/NNN/REF.pdf).
  - Al leer cada día la portada, los boletines se recogen según salen (los 8 últimos cubren unas tres semanas).

Uso: python -m motor.provinciales.bopzamora --salida ruta/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (Freno, clasificar, convocante_de_organismo, es_empleo_estricto, escribir_json,
                                     escribir_jsonl)
from motor.boe.clasificar import normalizar
from motor.extraccion.texto_es import fecha_texto
from motor.http import obtener
from motor.limpieza import texto_de

FUENTE = "bopzamora"
SIGLAS = "BOP-ZAMORA"
WEB = "https://www.diputaciondezamora.es"
PORTADA = WEB + "/opencms/servicios/BOP/bop/index.html"
NOMBRES = ("Boletín Oficial de la Provincia de Zamora",)

RE_BOLETIN = re.compile(r'<a href="(?P<url>/opencms/servicios/BOP/indice-bop/(?P<uuid>[0-9a-f-]{36})/)" title="(?P<tipo>[A-ZÁÉÍÓÚ]+):\s*'
                        r'BOP (?P<n>\d+)"><h3.*?<div class="teaser-date">\s*\w+,\s*(?P<d>\d{1,2}) de (?P<m>\w+) de (?P<a>\d{4})',
                        re.DOTALL)
RE_ANUNCIO = re.compile(r'<div class="sub-header"\s*>(?P<sec>.*?)</div>.*?Procedencia:\s*(?P<proc>.*?)</span>'
                        r'.*?Organismo:\s*(?P<org>.*?)</span>.*?<div class="text">(?P<ext>.*?)</div>'
                        r'.*?N[ºo°] de referencia:</span>\s*(?P<ref>\d+)'
                        r'(?:.*?href="(?P<pdf>/opencms/export/[^"]+\.pdf)")?', re.DOTALL)


def boletines_portada(html: str) -> list[dict]:
    vistos = {}
    for m in RE_BOLETIN.finditer(html):
        vistos.setdefault(m.group("uuid"), {"uuid": m.group("uuid"), "url": WEB + m.group("url"),
                                           "extraordinario": m.group("tipo").startswith("EXTRA"),
                                           "numero": int(m.group("n")),
                                           "fecha": fecha_texto(m.group("d"), m.group("m"), m.group("a"))})
    return list(vistos.values())


def parsear_indice(html: str) -> list[dict]:
    out = []
    for bloque in html.split('<div id="anuncio"')[1:]:
        m = RE_ANUNCIO.search(bloque)
        if not m:
            continue
        out.append({"numero_anuncio": m.group("ref"), "seccion": texto_de(m.group("sec")),
                    "procedencia": texto_de(m.group("proc")), "organismo": texto_de(m.group("org")),
                    "titulo": texto_de(m.group("ext")), "url_pdf": WEB + m.group("pdf") if m.group("pdf") else None})
    return out


def es_local(x: dict) -> bool:
    return "administracion local" in normalizar(x.get("seccion") or "")


def convocante(x: dict) -> dict | None:
    org, proc = x.get("organismo") or "", normalizar(x.get("procedencia") or "")
    if proc.startswith("diputacion provincial"):
        return {"tipo": "Diputación Provincial", "nombre": "Zamora", "provincia": "Zamora",
                "organismo": f"Diputación Provincial de Zamora - {org}" if org else "Diputación Provincial de Zamora"}
    c = convocante_de_organismo(org)
    if c and not c.get("provincia"):
        c["provincia"] = "Zamora"
    return c


def seleccionar(filas: list[dict]) -> list[dict]:
    out = []
    for x in filas:
        if not es_empleo_estricto(x["titulo"]):
            continue
        local = es_local(x)
        out.append({**x, "ambito": "local" if local else "otro", **clasificar(x["titulo"], x.get("seccion")),
                    "convocante": convocante(x) if local else None})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "provinciales" / FUENTE


def _ruta(raiz: Path, carpeta: str, b: dict, ext: str = "jsonl") -> Path:
    f = b["fecha"]
    return _base(raiz) / carpeta / f[:4] / f[5:7] / f"{f[8:10]}-{b['numero']:03d}.{ext}"


def procesar_boletin(b: dict, raiz: Path, archivo: Archivo) -> dict:
    r = obtener(b["url"], accept="text/html")
    inf = {**b, "status": r.status, "alertas": []}
    if r.status != 200:
        inf["resultado"] = "error_http"
        inf["alertas"].append(f"BOP Zamora {b['numero']}: HTTP {r.status}")
        return inf
    html = r.contenido.decode("utf-8", errors="replace")
    captura = archivo.guardar(FUENTE, date.fromisoformat(b["fecha"]), r.contenido, b["url"], "html", r.status,
                              r.cabeceras)
    filas = [{**x, "id": f"BOPZAMORA-{x['numero_anuncio']}", "fecha": b["fecha"], "boletin": b["numero"],
              "extraordinario": b["extraordinario"], "url_indice": b["url"], "fuente": SIGLAS,
              "captura_sha256": captura["sha256"]} for x in parsear_indice(html)]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", b), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", b), empleo)
    inf.update({"resultado": "ok", "sha256": captura["sha256"], "disposiciones": len(filas), "empleo_publico": len(empleo)})
    if not filas:
        inf["alertas"].append(f"BOP Zamora {b['numero']}: índice sin anuncios (posible cambio de formato)")
    return inf


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    informes, freno = [], Freno()
    try:
        r = obtener(PORTADA, accept="text/html")
        lista = boletines_portada(r.contenido.decode("utf-8", errors="replace")) if r.status == 200 else []
    except ConnectionError as e:
        print(f"BOP Zamora: fuente inaccesible ({e})")
        return 1
    if not lista:
        print("::warning::BOP Zamora: portada sin boletines (posible cambio de formato)")
        return 1
    for b in lista:
        ruta = _ruta(a.salida, "boletines", b, "json")
        if ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") == "ok":
            continue
        time.sleep(a.pausa)
        try:
            inf = procesar_boletin(b, a.salida, archivo)
        except ConnectionError as e:
            inf = {**b, "resultado": "fuente_inaccesible", "alertas": [str(e)]}
        escribir_json(ruta, inf)
        informes.append(inf)
        print(f"BOP Zamora {b['numero']} {b['fecha']}: {inf['resultado']} {inf.get('disposiciones', '')} anuncios, "
              f"{inf.get('empleo_publico', '')} de empleo")
        if freno.anotar(inf):
            break
    print(f"Boletines procesados: {len(informes)}")
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
