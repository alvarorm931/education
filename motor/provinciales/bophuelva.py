"""Conector del Boletín Oficial de la Provincia de Huelva.

Formato verificado el 30/10/2026 desde GitHub:
  - La sede (sede.diphuelva.es/…/BOP.jsp) carga en un marco https://s2.diphuelva.es/servicios/bope_web/, que pide los
    anuncios de un día por POST a https://s2.diphuelva.es/lib/bope/anuncios_bop/ajaxAnuncios.php (tipo=2,
    fecha=AAAA-MM-DD). Responde JSON: success, fecha_publicacion, Indice.num_bop y, por anuncio, id_anuncio, num_expe,
    entidad_anunciante, titulo, Seccion («Administración Local»), Categoria («Ayuntamientos») y el PDF (documento).
  - Un día sin boletín responde success=false. Este sistema empieza el 20/06/2023 (lo anterior está en otro archivo).
  - robots.txt de s2.diphuelva.es lo cierra todo; se lee como boletín oficial (motor/http.py, decisión del 30/10/2026).

Uso:
  python -m motor.provinciales.bophuelva --salida ruta/                                  # ayer y hoy
  python -m motor.provinciales.bophuelva --desde 2023-06-20 --max-minutos 30 --salida ruta/
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (Freno, clasificar, convocante_de_organismo, es_empleo_estricto, escribir_json,
                                     escribir_jsonl)
from motor.boe.clasificar import normalizar
from motor.http import obtener

FUENTE = "bophuelva"
SIGLAS = "BOP-HUELVA"
MADRID = ZoneInfo("Europe/Madrid")
WEB = "https://s2.diphuelva.es"
API = WEB + "/lib/bope/anuncios_bop/ajaxAnuncios.php"
NOMBRES = ("Boletín Oficial de la Provincia de Huelva",)
INICIO = date(2023, 6, 20)


def leer(contenido: bytes) -> dict:
    j = json.loads(contenido.decode("utf-8", errors="replace"))
    if not j.get("success"):
        return {"fecha": None, "numero": None, "anuncios": []}
    anuncios = [{"numero_anuncio": str(a.get("num_expe") or a.get("id_anuncio")), "seccion": a.get("Seccion"),
                 "categoria": a.get("Categoria"), "entidad": a.get("entidad_anunciante"),
                 "titulo": " ".join((a.get("titulo") or "").split()),
                 "url_detalle": f"{WEB}/servicios/bope_web/anuncio/?anuncio={a.get('num_expe')}",
                 "url_pdf": f"{WEB}/portalweb/bope/anuncios/{a['documento']}" if a.get("documento") else None}
                for a in j.get("Anuncios") or []]
    return {"fecha": j.get("fecha_publicacion"), "numero": (j.get("Indice") or {}).get("num_bop"), "anuncios": anuncios}


def es_local(x: dict) -> bool:
    return "administracion local" in normalizar(x.get("seccion") or "")


def convocante(x: dict) -> dict | None:
    c = convocante_de_organismo(x.get("entidad") or "")
    if c and not c.get("provincia"):
        c["provincia"] = "Huelva"
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


def _ruta(raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


def procesar_dia(d: date, raiz: Path, archivo: Archivo) -> dict:
    r = obtener(API, accept="application/json", formulario={"tipo": "2", "fecha": d.isoformat()})
    inf = {"fecha": d.isoformat(), "status": r.status, "alertas": []}
    if r.status != 200:
        inf["resultado"] = "error_http"
        inf["alertas"].append(f"BOP Huelva {d}: HTTP {r.status}")
        return inf
    try:
        s = leer(r.contenido)
    except ValueError:
        inf["resultado"] = "error_formato"
        inf["alertas"].append(f"BOP Huelva {d}: la respuesta no es JSON")
        return inf
    if s["fecha"] != d.isoformat():
        inf["resultado"] = "sin_boletin"
        return inf
    captura = archivo.guardar(FUENTE, d, r.contenido, f"{API}?tipo=2&fecha={d.isoformat()}", "json", r.status,
                              r.cabeceras)
    filas = [{**x, "id": f"BOPHUELVA-{x['numero_anuncio']}", "fecha": d.isoformat(), "boletin": s["numero"],
              "fuente": SIGLAS, "captura_sha256": captura["sha256"]} for x in s["anuncios"]]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    inf.update({"resultado": "ok", "numero": s["numero"], "sha256": captura["sha256"], "disposiciones": len(filas),
                "empleo_publico": len(empleo)})
    if not filas:
        inf["alertas"].append(f"BOP Huelva {d}: boletín sin anuncios (posible cambio de formato)")
    return inf


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=date.fromisoformat, default=hoy - timedelta(days=1))
    p.add_argument("--hasta", type=date.fromisoformat, default=hoy)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    inicio, informes, freno = time.monotonic(), [], Freno()
    d, desde = a.hasta, max(a.desde, INICIO)
    while d >= desde:
        ruta = _ruta(a.salida, "dias", d, "json")
        hecho = ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") in {"ok", "sin_boletin"}
        if d.weekday() >= 5 and not hecho:
            escribir_json(ruta, {"fecha": d.isoformat(), "resultado": "sin_boletin", "nota": "fin de semana", "alertas": []})
            hecho = True
        if not hecho or (d >= hoy - timedelta(days=1) and d.weekday() < 5):
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                break
            try:
                inf = procesar_dia(d, a.salida, archivo)
            except (ConnectionError, TimeoutError) as e:
                inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            if not (inf.get("resultado") == "sin_boletin" and d >= hoy - timedelta(days=1)):
                escribir_json(ruta, inf)
            informes.append(inf)
            if freno.anotar(inf):
                break
            print(f"BOP Huelva {d}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            time.sleep(a.pausa)
        d -= timedelta(days=1)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
