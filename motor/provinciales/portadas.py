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
    url_dia: Callable[[date], str] | None = None  # dirección del boletín de un día, si el BOP la tiene (histórico)


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


def _guardar(p: Portada, s: dict, r, url: str, raiz: Path, archivo: Archivo, origen: str) -> dict:
    d = date.fromisoformat(s["fecha"])
    captura = archivo.guardar(p.fuente, d, r.contenido, url, "html", r.status, r.cabeceras)
    filas = [{**x, "id": f"{p.siglas}-{s['fecha']}-{x['numero_anuncio']}", "fecha": s["fecha"], "boletin": s.get("numero"),
              "fuente": p.siglas, "captura_sha256": captura["sha256"]} for x in s["anuncios"]]
    empleo = seleccionar(p, filas)
    escribir_jsonl(_ruta(p, raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(p, raiz, "oposiciones", d), empleo)
    inf = {"fecha": s["fecha"], "status": 200, "resultado": "ok", "numero": s.get("numero"), "origen": origen,
           "sha256": captura["sha256"], "disposiciones": len(filas), "empleo_publico": len(empleo), "alertas": []}
    escribir_json(_ruta(p, raiz, "dias", d, "json"), inf)
    return inf


def procesar(p: Portada, raiz: Path, archivo: Archivo) -> dict:
    r = obtener(p.url, accept="text/html")
    if r.status != 200:
        return {"fecha": None, "status": r.status, "resultado": "error_http", "alertas": [f"{p.siglas} portada: HTTP {r.status}"]}
    s = p.leer(r.contenido)
    if not s.get("fecha") or not s.get("anuncios"):
        return {"fecha": s.get("fecha"), "status": 200, "resultado": "error_formato",
                "alertas": [f"{p.siglas} portada sin fecha o sin anuncios (posible cambio de formato)"]}
    dia = _ruta(p, raiz, "dias", date.fromisoformat(s["fecha"]), "json")
    if dia.exists() and json.loads(dia.read_text(encoding="utf-8")).get("resultado") == "ok":
        return {**json.loads(dia.read_text(encoding="utf-8")), "nota": "ya leído"}
    return _guardar(p, s, r, p.url, raiz, archivo, "portada")


def historico(p: Portada, raiz: Path, archivo: Archivo, desde: date, hasta: date, pausa: float = 1.0,
              max_minutos: float = 0) -> int:
    """Días anteriores, de hasta hacia atrás, por la dirección del boletín de cada día (p.url_dia), con el mismo
    lector que la portada. Si la página trae otra fecha (o ningún sumario), ese día no hubo boletín."""
    import time
    from datetime import timedelta

    from motor.autonomicos.comun import Freno

    inicio, informes, freno, d = time.monotonic(), [], Freno(), hasta
    while d >= desde:
        ruta = _ruta(p, raiz, "dias", d, "json")
        hecho = ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") in {"ok", "sin_boletin"}
        if d.weekday() >= 5 and not hecho:
            escribir_json(ruta, {"fecha": d.isoformat(), "resultado": "sin_boletin", "nota": "fin de semana", "alertas": []})
            hecho = True
        if not hecho:
            if max_minutos and (time.monotonic() - inicio) / 60 > max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                break
            time.sleep(pausa)
            url = p.url_dia(d)
            try:
                r = obtener(url, accept="text/html")
                if r.status == 404:
                    inf = {"fecha": d.isoformat(), "status": 404, "resultado": "sin_boletin", "alertas": []}
                elif r.status != 200:
                    inf = {"fecha": d.isoformat(), "status": r.status, "resultado": "error_http",
                           "alertas": [f"{p.siglas} {d}: HTTP {r.status}"]}
                else:
                    s = p.leer(r.contenido)
                    if s.get("fecha") != d.isoformat() or not s.get("anuncios"):
                        inf = {"fecha": d.isoformat(), "status": 200, "resultado": "sin_boletin",
                               "nota": f"la página trae {s.get('fecha')}", "alertas": []}
                    else:
                        inf = _guardar(p, s, r, url, raiz, archivo, "dia")
            except (ConnectionError, TimeoutError) as e:
                inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            escribir_json(ruta, inf)
            informes.append(inf)
            print(f"{p.siglas} {d}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            if freno.anotar(inf):
                break
        d -= timedelta(days=1)
    print(f"{p.siglas} histórico: {len(informes)} días, {sum(i.get('empleo_publico', 0) for i in informes)} de empleo")
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


def main(p: Portada, argv: list[str] | None = None) -> int:
    a = argparse.ArgumentParser()
    a.add_argument("--salida", type=Path, default=Path("."))
    a.add_argument("--historico", action="store_true", help="días anteriores (solo si el BOP tiene dirección por día)")
    a.add_argument("--desde", type=date.fromisoformat, default=date(2022, 1, 1))
    a.add_argument("--max-minutos", type=float, default=0)
    a.add_argument("--pausa", type=float, default=1.0)
    args = a.parse_args(argv)
    archivo = Archivo(args.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    if args.historico:
        if not p.url_dia:
            print(f"{p.siglas}: sin dirección por día; solo se lee la portada")
            return 0
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        ayer = datetime.now(ZoneInfo("Europe/Madrid")).date() - timedelta(days=1)
        return historico(p, args.salida, archivo, args.desde, ayer, args.pausa, args.max_minutos)
    try:
        inf = procesar(p, args.salida, archivo)
    except (ConnectionError, TimeoutError) as e:
        inf = {"fecha": None, "resultado": "fuente_inaccesible", "alertas": [str(e)]}
    print(f"{p.siglas} {inf.get('fecha')}: {inf['resultado']} {inf.get('disposiciones', '')} anuncios, "
          f"{inf.get('empleo_publico', '')} de empleo {'; '.join(inf.get('alertas', []))}")
    return 1 if inf["resultado"] in {"error_formato", "fuente_inaccesible", "error_http"} else 0


if __name__ == "__main__":
    sys.exit(2)
