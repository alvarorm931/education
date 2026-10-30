"""Revisión de nombres candidatos a dominio antes de registrarlo (guía, fase 0: «dominio .es nuevo con historial
revisado»; ley SEO: prohibido el abuso de dominios caducados).

Para cada candidato:
- **Historial**: capturas en la Wayback Machine (API de disponibilidad documentada en
  https://archive.org/help/wayback_api.php y recuento con su servicio CDX) y direcciones en el último índice de
  Common Crawl. Un dominio con historial se revisa a mano: si fue de otro (y más si fue spam, apuestas, farmacia o
  adultos), se descarta. Google no hereda gratis la autoridad de un dominio caducado y puede sancionarlo.
- **Nombre**: sin palabras que aparenten carácter oficial (la licencia del BOE prohíbe aparentarlo y Google lo
  trata como engaño), de marca y no de palabras clave (decidido), sin guiones ni cifras, corto.
- **DNS**: si ya resuelve, está registrado (que no resuelva no prueba que esté libre: eso lo dice dominios.es).

Se ejecuta desde GitHub (el espacio de trabajo de Claude no llega a archive.org):
    python -m motor.seo.dominio --candidatos nombre1.es,nombre2.es --salida carpeta/
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import sys
from pathlib import Path

import requests

AGENTE = "PortalEstudiosOposiciones/0.1 (revision de historial de dominios candidatos)"
OFICIALES = ["boe", "gob", "gobierno", "oficial", "ministerio", "sepe", "estado", "administracion", "inap",
             "funcionpublica", "ruct", "educacion", "universidades", "junta", "generalitat", "xunta"]
GENERICAS = ["oposiciones", "master", "masters", "carreras", "estudios", "notas", "corte", "fp", "becas",
             "universidad", "cursos"]


def revisar_nombre(dominio: str) -> list[str]:
    problemas = []
    nombre = dominio.lower().rsplit(".", 1)[0]
    if not dominio.lower().endswith(".es"):
        problemas.append("no es .es (la guía decide un .es)")
    if "-" in nombre or re.search(r"\d", nombre):
        problemas.append("lleva guiones o cifras")
    if len(nombre) > 15:
        problemas.append(f"{len(nombre)} letras: largo para una marca")
    for p in OFICIALES:
        if p in nombre:
            problemas.append(f"contiene «{p}»: puede aparentar carácter oficial")
    genericas = [g for g in GENERICAS if g in nombre]
    if genericas and len("".join(genericas)) >= len(nombre) - 2:
        problemas.append("solo palabras clave: se decidió un nombre de marca")
    return problemas


def historial(dominio: str, sesion=None) -> dict:
    sesion = sesion or requests.Session()
    cab = {"User-Agent": AGENTE}
    salida: dict = {"dominio": dominio}
    try:
        r = sesion.get("https://archive.org/wayback/available", params={"url": dominio}, headers=cab, timeout=60)
        cerca = r.json().get("archived_snapshots", {}).get("closest") if r.status_code == 200 else None
        salida["wayback_ultima"] = cerca.get("timestamp") if cerca else None
    except (requests.RequestException, ValueError) as e:
        salida["wayback_ultima"] = f"error: {type(e).__name__}"
    try:
        r = sesion.get("https://web.archive.org/cdx/search/cdx", headers=cab, timeout=120,
                       params={"url": dominio, "matchType": "domain", "output": "json", "fl": "timestamp,original",
                               "collapse": "timestamp:4", "limit": "200"})
        filas = r.json()[1:] if r.status_code == 200 and r.content.strip() else []
        salida["wayback_anos"] = sorted({f[0][:4] for f in filas})
        salida["wayback_ejemplos"] = [f[1] for f in filas[:10]]
    except (requests.RequestException, ValueError) as e:
        salida["wayback_anos"] = f"error: {type(e).__name__}"
    try:
        indices = sesion.get("https://index.commoncrawl.org/collinfo.json", headers=cab, timeout=60).json()
        ultimo = indices[0]["cdx-api"]
        r = sesion.get(ultimo, params={"url": f"*.{dominio}", "output": "json", "limit": "20"}, headers=cab,
                       timeout=120)
        lineas = [json.loads(l) for l in r.text.splitlines() if l.startswith("{")] if r.status_code == 200 else []
        salida["commoncrawl"] = {"indice": indices[0]["id"], "direcciones": len(lineas),
                                 "ejemplos": [l.get("url") for l in lineas[:5]]}
    except (requests.RequestException, ValueError, KeyError, IndexError) as e:
        salida["commoncrawl"] = f"error: {type(e).__name__}"
    try:
        socket.getaddrinfo(dominio, 443)
        salida["resuelve"] = True
    except socket.gaierror:
        salida["resuelve"] = False
    return salida


def veredicto(h: dict, problemas_nombre: list[str]) -> str:
    con_historia = bool(h.get("wayback_ultima")) and not str(h.get("wayback_ultima")).startswith("error") \
        or (isinstance(h.get("wayback_anos"), list) and h["wayback_anos"]) \
        or (isinstance(h.get("commoncrawl"), dict) and h["commoncrawl"]["direcciones"])
    if problemas_nombre:
        return "descartar o repensar el nombre"
    if con_historia:
        return "tiene historial: revisar a mano qué fue antes de registrarlo"
    if any(str(v).startswith("error") for v in h.values()):
        return "sin historial conocido, pero alguna consulta falló: repetir"
    return "sin historial conocido" + (" (ya registrado: resuelve en DNS)" if h.get("resuelve") else "")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Historial y nombre de dominios candidatos")
    p.add_argument("--candidatos", required=True, help="separados por comas")
    p.add_argument("--salida", type=Path)
    a = p.parse_args(argv)
    filas = []
    for d in [x.strip().lower() for x in a.candidatos.split(",") if x.strip()]:
        h, n = historial(d), revisar_nombre(d)
        filas.append(h | {"nombre": n, "veredicto": veredicto(h, n)})
        print(f"{d}: {filas[-1]['veredicto']}" + (f" ({'; '.join(n)})" if n else ""))
    if a.salida:
        a.salida.mkdir(parents=True, exist_ok=True)
        (a.salida / "dominios.json").write_text(json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
