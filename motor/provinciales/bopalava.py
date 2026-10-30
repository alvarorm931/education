"""Conector del Boletín Oficial del Territorio Histórico de Álava (BOTHA).

Formato verificado el 30/10/2026 desde GitHub:
  - Boletín de un día: http://www.araba.eus/botha/Inicio/SGBO5001.aspx?FechaBotha=DD/MM/AAAA (bilingüe). Sin fecha,
    el último. El calendario de la página enlaza cada número con su fecha («Boletín Nº124 … FechaBotha=28/10/2026»).
  - Por anuncio, en las dos lenguas: secciones (div.titulo_bloque_resultados, niveles 1 a 3: administración, órgano,
    entidad «AYUNTAMIENTO DE ASPARRENA») y el asunto con su número (Boletines/AAAA/NNN/AAAA_NNN_NNNNN_C.xml; «_C» es
    la versión en castellano, «_E» en euskera) y su PDF. Se guarda la versión en castellano.
  - robots.txt cierra /botha/Busquedas (la versión HTML de cada anuncio): no se pide; queda el PDF.
  - Sale lunes, miércoles y viernes.

Uso:
  python -m motor.provinciales.bopalava --salida ruta/                                   # ayer y hoy
  python -m motor.provinciales.bopalava --desde 2022-01-01 --max-minutos 30 --salida ruta/
"""

from __future__ import annotations

import argparse
import html
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
from motor.http import obtener

FUENTE = "bopalava"
SIGLAS = "BOTHA"
MADRID = ZoneInfo("Europe/Madrid")
BASE = "http://www.araba.eus/botha/"
NOMBRES = ("Boletín Oficial del Territorio Histórico de Álava",)

RE_TOKEN = re.compile(r"<div class='titulo_bloque_resultados' id='TitSeccion(?P<nivel>\d)'>(?:<a[^>]*></a>)?(?P<tit>[^<]*)</div>"
                      r'|href="\.\./Busquedas/Resultado\.aspx\?File=Boletines/(?P<a>\d{4})/(?P<n>\d+)/\d{4}_\d+_(?P<num>\d+)_C\.xml'
                      r'[^"]*"[^>]*>(?P<asunto>[^<]*)</a>')


def url_dia(d: date) -> str:
    return f"{BASE}Inicio/SGBO5001.aspx?FechaBotha={d:%d/%m/%Y}"


def _t(s: str) -> str:
    return " ".join(html.unescape(s or "").split())


def parsear_dia(contenido: bytes) -> dict:
    h = contenido.decode("utf-8", errors="replace")
    niveles: dict[int, str] = {}
    anuncios, numero, anio = [], None, None
    for m in RE_TOKEN.finditer(h):
        if m.group("nivel"):
            n = int(m.group("nivel"))
            niveles = {k: v for k, v in niveles.items() if k < n}
            niveles[n] = _t(m.group("tit"))  # la versión en castellano va después de la de euskera
        else:
            anio, numero = m.group("a"), int(m.group("n"))
            num = m.group("num")
            anuncios.append({"numero_anuncio": num, "seccion": niveles.get(1), "organo": niveles.get(2),
                             "entidad": niveles.get(3), "titulo": _t(m.group("asunto")),
                             "url_pdf": f"{BASE}Boletines/{anio}/{numero:03d}/{anio}_{numero:03d}_{num}_C.pdf"})
    fecha = None
    if numero:
        f = re.search(rf"Bolet[ií]n N[ºo°]{numero}' href='[^']*FechaBotha=(\d{{2}})/(\d{{2}})/(\d{{4}})", h)
        fecha = f"{f.group(3)}-{f.group(2)}-{f.group(1)}" if f else None
    return {"numero": numero, "anio": anio, "fecha": fecha, "anuncios": anuncios}


def es_local(x: dict) -> bool:
    return "administracion local" in normalizar(x.get("seccion") or "")


def convocante(x: dict) -> dict | None:
    c = convocante_de_organismo(x.get("entidad") or "")
    if c:
        c["provincia"] = "Araba/Álava"
    return c


def seleccionar(filas: list[dict]) -> list[dict]:
    out = []
    for x in filas:
        if not es_empleo_estricto(x["titulo"]):
            continue
        local = es_local(x)
        out.append({**x, "ambito": "local" if local else "foral", **clasificar(x["titulo"], x.get("organo")),
                    "convocante": convocante(x) if local else None})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "provinciales" / FUENTE


def _ruta(raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


def procesar_dia(d: date, raiz: Path, archivo: Archivo) -> dict:
    url = url_dia(d)
    r = obtener(url, accept="text/html")
    inf = {"fecha": d.isoformat(), "status": r.status, "alertas": []}
    if r.status != 200:
        inf["resultado"] = "error_http"
        inf["alertas"].append(f"BOTHA {d}: HTTP {r.status}")
        return inf
    s = parsear_dia(r.contenido)
    if not s["anuncios"] and s["fecha"] != d.isoformat():
        # martes y jueves (y festivos) no hay BOTHA: la página sale sin anuncios y sin la fecha pedida
        inf["resultado"] = "sin_boletin"
        return inf
    if not s["anuncios"]:
        inf["resultado"] = "error_formato"
        inf["alertas"].append(f"BOTHA {d}: página sin anuncios (posible cambio de formato)")
        return inf
    if s["fecha"] != d.isoformat():
        inf["resultado"] = "sin_boletin"  # sin boletín ese día: la página da otro
        return inf
    captura = archivo.guardar(FUENTE, d, r.contenido, url, "html", r.status, r.cabeceras)
    filas = [{**x, "id": f"BOTHA-{s['anio']}-{x['numero_anuncio']}", "fecha": d.isoformat(), "boletin": s["numero"],
              "url_dia": url, "fuente": SIGLAS, "captura_sha256": captura["sha256"]} for x in s["anuncios"]]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    inf.update({"resultado": "ok", "numero": s["numero"], "sha256": captura["sha256"], "disposiciones": len(filas),
                "empleo_publico": len(empleo)})
    return inf


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=date.fromisoformat, default=hoy - timedelta(days=2))
    p.add_argument("--hasta", type=date.fromisoformat, default=hoy)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    inicio, informes, freno = time.monotonic(), [], Freno()
    d = a.hasta
    while d >= a.desde:
        ruta = _ruta(a.salida, "dias", d, "json")
        hecho = ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") in {"ok", "sin_boletin"}
        if d.weekday() >= 5 and not hecho:
            escribir_json(ruta, {"fecha": d.isoformat(), "resultado": "sin_boletin", "nota": "fin de semana", "alertas": []})
            hecho = True
        if not hecho or (d >= hoy - timedelta(days=2) and d.weekday() < 5):
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
            if freno.anotar(inf):
                break
            print(f"BOTHA {d}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            time.sleep(a.pausa)
        d -= timedelta(days=1)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
