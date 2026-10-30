"""Boletines provinciales que se leen por su canal RSS o Atom: el boletín del día, anuncio por anuncio.

Para los BOP que publican en un canal el sumario del día con el número, la entidad y el asunto de cada anuncio. El
canal solo trae el boletín del día, así que el histórico empieza el día en que se conecta (para lo anterior hace
falta otro camino, propio de cada boletín). Cada boletín es un Canal con su forma de leer el canal; el resto (selección
por el título, convocante, ficheros) es común.

Uso (cada boletín tiene su módulo): python -m motor.provinciales.bopavila --salida ruta/
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (clasificar, convocante_de_organismo, es_empleo_estricto, escribir_json,
                                     escribir_jsonl)
from motor.boe.clasificar import normalizar
from motor.http import obtener


@dataclass
class Canal:
    fuente: str
    siglas: str
    provincia: str
    url: str
    nombres: tuple[str, ...]
    leer: Callable[[str], dict]  # texto del canal -> {"fecha", "numero", "anuncios": [{numero_anuncio, entidad, …}]}


def texto(s: str | None) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())


def items_rss(xml: str) -> list[dict]:
    out = []
    for it in re.findall(r"<item>(.*?)</item>", xml, re.DOTALL):
        campo = {k: texto((re.search(rf"<{k}>(.*?)</{k}>", it, re.DOTALL) or [None, ""])[1])
                 for k in ("title", "description", "link", "guid", "pubDate")}
        out.append(campo)
    return out


def convocante(c: Canal, entidad: str | None, titulo: str = "") -> dict | None:
    if not entidad:
        return None
    if normalizar(entidad).startswith(("ayuntamiento", "diputacion", "mancomunidad", "consorcio", "junta vecinal",
                                       "entidad local", "comunidad de villa", "concejo", "concello", "deputacion",
                                       "ajuntament", "consell comarcal")):
        conv = convocante_de_organismo(entidad)
    else:
        conv = convocante_de_organismo(f"AYUNTAMIENTO DE {entidad}")
        if conv and normalizar(conv["nombre"]) == normalizar(c.provincia) and "diputacion" in normalizar(titulo):
            conv = {"tipo": "Diputación Provincial", "nombre": c.provincia, "provincia": c.provincia,
                    "organismo": f"Diputación de {c.provincia}"}
    if conv:
        conv["provincia"] = conv.get("provincia") or c.provincia
        conv["organismo"] = entidad if conv.get("tipo") != "Diputación Provincial" else conv["organismo"]
    return conv


def es_local(entidad: str | None) -> bool:
    e = normalizar(entidad or "")
    return not e.startswith(("junta de castilla", "junta c. y l", "junta cyl", "junta de extremadura", "xunta", "ministerio",
                             "subdelegacion", "delegacion del gobierno", "confederacion", "juzgado", "tribunal",
                             "tesoreria general", "agencia tributaria", "seguridad social", "jefatura", "demarcacion"))


def seleccionar(c: Canal, filas: list[dict]) -> list[dict]:
    out = []
    for x in filas:
        if not es_empleo_estricto(x["titulo"]):
            continue
        local = es_local(x.get("entidad"))
        out.append({**x, "ambito": "local" if local else "otro", **clasificar(x["titulo"]),
                    "convocante": convocante(c, x.get("entidad"), x["titulo"]) if local else None})
    return out


def _ruta(c: Canal, raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return raiz / "datos" / "provinciales" / c.fuente / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


def procesar(c: Canal, raiz: Path, archivo: Archivo) -> dict:
    r = obtener(c.url, accept="application/rss+xml, application/atom+xml, application/xml")
    if r.status != 200:
        return {"fecha": None, "status": r.status, "resultado": "error_http", "alertas": [f"{c.siglas} canal: HTTP {r.status}"]}
    s = c.leer(r.contenido.decode("utf-8", errors="replace"))
    if not s.get("fecha"):
        return {"fecha": None, "status": 200, "resultado": "error_formato",
                "alertas": [f"{c.siglas} canal sin fecha de boletín (posible cambio de formato)"]}
    d = date.fromisoformat(s["fecha"])
    captura = archivo.guardar(c.fuente, d, r.contenido, c.url, "xml", r.status, r.cabeceras)
    filas = [{**x, "id": f"{c.siglas}-{x['numero_anuncio']}".replace("/", "-"), "fecha": s["fecha"],
              "boletin": s.get("numero"), "fuente": c.siglas, "captura_sha256": captura["sha256"]}
             for x in s["anuncios"]]
    empleo = seleccionar(c, filas)
    escribir_jsonl(_ruta(c, raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(c, raiz, "oposiciones", d), empleo)
    inf = {"fecha": s["fecha"], "status": 200, "resultado": "ok", "numero": s.get("numero"), "origen": "canal",
           "sha256": captura["sha256"], "disposiciones": len(filas), "empleo_publico": len(empleo), "alertas": []}
    if not filas:
        inf["alertas"].append(f"{c.siglas} {s['fecha']}: canal sin anuncios")
    escribir_json(_ruta(c, raiz, "dias", d, "json"), inf)
    return inf


def main(c: Canal, argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    try:
        inf = procesar(c, a.salida, archivo)
    except (ConnectionError, TimeoutError) as e:
        inf = {"fecha": None, "resultado": "fuente_inaccesible", "alertas": [str(e)]}
    print(f"{c.siglas} {inf.get('fecha')}: {inf['resultado']} {inf.get('disposiciones', '')} anuncios, "
          f"{inf.get('empleo_publico', '')} de empleo {'; '.join(inf['alertas'])}")
    return 1 if inf["resultado"] in {"error_formato", "fuente_inaccesible", "error_http"} else 0


if __name__ == "__main__":
    sys.exit(2)
