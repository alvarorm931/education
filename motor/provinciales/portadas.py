"""BOP que publican en su portada el sumario del boletín del día (sin otra forma de pedir días anteriores).

Cada uno tiene su lector de la portada; lo común (selección por el título, convocante, ficheros e informe) está
aquí. Al leer la portada cada día, el histórico se forma desde el día en que se conecta.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import clasificar, convocante_de_organismo, es_empleo_estricto, escribir_json, escribir_jsonl
from motor.boe.clasificar import normalizar
from motor.http import obtener

# Grupos de entidades con el nombre aparte («Ayuntamientos» + «Calvarrasa de Abajo»)
GRUPOS = {"ayuntamientos": "AYUNTAMIENTO DE", "mancomunidades": "MANCOMUNIDAD", "entidades locales menores":
          "ENTIDAD LOCAL MENOR", "otras entidades locales": "", "juntas vecinales": "JUNTA VECINAL DE",
          "agrupacion de municipios": "AGRUPACIÓN DE MUNICIPIOS", "consorcios": "CONSORCIO"}


@dataclass
class Portada:
    fuente: str
    siglas: str
    provincia: str
    url: str
    nombres: tuple[str, ...]
    leer: Callable[[bytes], dict]  # -> {"fecha", "numero", "anuncios": [{numero_anuncio, seccion, grupo, entidad, titulo, url_pdf}]}


def organismo(x: dict) -> str:
    grupo, ent = x.get("grupo") or "", x.get("entidad") or ""
    pref = GRUPOS.get(normalizar(grupo))
    if pref and ent and not normalizar(ent).startswith(normalizar(pref.split()[0]) if pref else "~"):
        return f"{pref} {ent}".strip()
    return ent or grupo


def es_local(x: dict) -> bool:
    return "local" in normalizar(x.get("seccion") or "")


def convocante(p: Portada, x: dict) -> dict | None:
    org = organismo(x)
    c = convocante_de_organismo(org)
    if c:
        if c.get("tipo") == "Diputación Provincial" or not c.get("provincia"):
            c["provincia"] = p.provincia
        if c.get("tipo") == "Diputación Provincial":
            c["nombre"] = p.provincia
        c["organismo"] = x.get("entidad") or org
    return c


def seleccionar(p: Portada, filas: list[dict]) -> list[dict]:
    out = []
    for x in filas:
        if not es_empleo_estricto(x["titulo"]):
            continue
        local = es_local(x)
        out.append({**x, "ambito": "local" if local else "otro", **clasificar(x["titulo"], x.get("seccion")),
                    "convocante": convocante(p, x) if local else None})
    return out


def _ruta(p: Portada, raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return raiz / "datos" / "provinciales" / p.fuente / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


def procesar(p: Portada, raiz: Path, archivo: Archivo) -> dict:
    r = obtener(p.url, accept="text/html")
    if r.status != 200:
        return {"fecha": None, "status": r.status, "resultado": "error_http", "alertas": [f"{p.siglas} portada: HTTP {r.status}"]}
    s = p.leer(r.contenido)
    if not s.get("fecha") or not s.get("anuncios"):
        return {"fecha": s.get("fecha"), "status": 200, "resultado": "error_formato",
                "alertas": [f"{p.siglas} portada sin fecha o sin anuncios (posible cambio de formato)"]}
    d = date.fromisoformat(s["fecha"])
    dia = _ruta(p, raiz, "dias", d, "json")
    if dia.exists() and json.loads(dia.read_text(encoding="utf-8")).get("resultado") == "ok":
        return {**json.loads(dia.read_text(encoding="utf-8")), "nota": "ya leído"}
    captura = archivo.guardar(p.fuente, d, r.contenido, p.url, "html", r.status, r.cabeceras)
    filas = [{**x, "id": f"{p.siglas}-{s['fecha']}-{x['numero_anuncio']}", "fecha": s["fecha"], "boletin": s.get("numero"),
              "fuente": p.siglas, "captura_sha256": captura["sha256"]} for x in s["anuncios"]]
    empleo = seleccionar(p, filas)
    escribir_jsonl(_ruta(p, raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(p, raiz, "oposiciones", d), empleo)
    inf = {"fecha": s["fecha"], "status": 200, "resultado": "ok", "numero": s.get("numero"), "origen": "portada",
           "sha256": captura["sha256"], "disposiciones": len(filas), "empleo_publico": len(empleo), "alertas": []}
    escribir_json(dia, inf)
    return inf


def main(p: Portada, argv: list[str] | None = None) -> int:
    a = argparse.ArgumentParser()
    a.add_argument("--salida", type=Path, default=Path("."))
    args = a.parse_args(argv)
    archivo = Archivo(args.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    try:
        inf = procesar(p, args.salida, archivo)
    except (ConnectionError, TimeoutError) as e:
        inf = {"fecha": None, "resultado": "fuente_inaccesible", "alertas": [str(e)]}
    print(f"{p.siglas} {inf.get('fecha')}: {inf['resultado']} {inf.get('disposiciones', '')} anuncios, "
          f"{inf.get('empleo_publico', '')} de empleo {'; '.join(inf.get('alertas', []))}")
    return 1 if inf["resultado"] in {"error_formato", "fuente_inaccesible", "error_http"} else 0


if __name__ == "__main__":
    sys.exit(2)
