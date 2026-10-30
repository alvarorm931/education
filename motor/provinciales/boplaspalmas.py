"""Conector del Boletín Oficial de la Provincia de Las Palmas.

Formato verificado el 30/10/2026 desde GitHub (también para 2022):
  - www.boplaspalmas.com redirige a https://www.boplaspalmas.net/nbop2/ (marcos); el calendario del mes (main1.php)
    enlaza el sumario de cada boletín: sumario.php?codigopub=1&fecha_mas_reciente=AAAA-MM-DD (lunes, miércoles y
    viernes, más los extraordinarios).
  - Sumario: «SUMARIO DEL BOLETÍN Nº 129, DE FECHA 28-10-26», el enlace al PDF del boletín entero y, por sección
    («III. ADMINISTRACIÓN LOCAL»), la entidad en negrita y cursiva («EXCMO. CABILDO INSULAR DE GRAN CANARIA») y sus
    anuncios, uno por línea («- Bases específicas de la convocatoria…»). No hay número ni PDF por anuncio: el
    identificador es la fecha y el orden en el sumario.
  - robots.txt de boplaspalmas.net lo cierra todo; se lee como boletín oficial (motor/http.py, decisión del 30/10/2026).

Uso:
  python -m motor.provinciales.boplaspalmas --salida ruta/                                  # ayer y hoy
  python -m motor.provinciales.boplaspalmas --desde 2022-01-01 --max-minutos 30 --salida ruta/
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
                                     escribir_jsonl, estado_dia)
from motor.boe.clasificar import normalizar
from motor.http import obtener

FUENTE = "boplaspalmas"
SIGLAS = "BOP-LASPALMAS"
MADRID = ZoneInfo("Europe/Madrid")
BASE = "https://www.boplaspalmas.net/nbop2/"
NOMBRES = ("Boletín Oficial de la Provincia de Las Palmas",)

RE_CABECERA = re.compile(r"SUMARIO DEL BOLET(?:&Iacute;|Í|I)N N(?:&ordm;|º|°)\s*(?:<[^>]+>\s*)*(?P<n>\d+)(?:\s|<[^>]+>)*,\s*DE"
                         r"\s+FECHA\s*(?:<[^>]+>\s*)*(?P<d>\d{1,2})-(?P<m>\d{1,2})-(?P<a>\d{2})")
RE_PDF = re.compile(r'href="\.\./(boletines/[^"]+\.pdf)"')
RE_TOKEN = re.compile(r'<span class="f">(?P<sec>.*?)</span>|<b><i>(?P<ent>.*?)</i></b>'
                      r"|<br>\s*-\s*(?P<tit>.*?)(?=<br>|</font>|<b>)", re.DOTALL)


def url_dia(d: date) -> str:
    return f"{BASE}sumario.php?codigopub=1&fecha_mas_reciente={d.isoformat()}"


def _t(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).replace("\xa0", " ").split())


def _decodificar(contenido: bytes) -> str:
    try:
        return contenido.decode("utf-8")
    except UnicodeDecodeError:
        return contenido.decode("latin-1")


def parsear_sumario(contenido: bytes) -> dict:
    h = _decodificar(contenido)
    c = RE_CABECERA.search(h)
    pdf = RE_PDF.search(h)
    seccion = entidad = None
    anuncios = []
    for m in RE_TOKEN.finditer(h, c.end() if c else 0):
        if m.group("sec") is not None:
            t = _t(m.group("sec"))
            if t:
                seccion, entidad = t, None
        elif m.group("ent") is not None:
            entidad = _t(m.group("ent"))
        else:
            t = _t(m.group("tit"))
            if t:
                anuncios.append({"orden": len(anuncios) + 1, "seccion": seccion, "entidad": entidad, "titulo": t})
    return {"numero": c.group("n") if c else None,
            "fecha": f"20{c.group('a')}-{int(c.group('m')):02d}-{int(c.group('d')):02d}" if c else None,
            "url_pdf": BASE.rsplit("nbop2/", 1)[0] + pdf.group(1) if pdf else None, "anuncios": anuncios}


def es_local(x: dict) -> bool:
    return "administracion local" in normalizar(x.get("seccion") or "")


def convocante(x: dict) -> dict | None:
    c = convocante_de_organismo(x.get("entidad") or "")
    if c and not c.get("provincia"):
        c["provincia"] = "Las Palmas"
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
    url = url_dia(d)
    r = obtener(url, accept="text/html")
    inf = {"fecha": d.isoformat(), "status": r.status, "alertas": []}
    if r.status != 200:
        inf["resultado"] = "error_http"
        inf["alertas"].append(f"BOP Las Palmas {d}: HTTP {r.status}")
        return inf
    s = parsear_sumario(r.contenido)
    if s["fecha"] != d.isoformat():
        inf["resultado"] = "sin_boletin"  # sin boletín ese día (la página muestra otro o ninguno)
        inf["pagina_es_del"] = s["fecha"]
        return inf
    captura = archivo.guardar(FUENTE, d, r.contenido, url, "html", r.status, r.cabeceras)
    filas = [{**x, "id": f"BOPLASPALMAS-{d.isoformat()}-{x['orden']:03d}", "fecha": d.isoformat(),
              "boletin": s["numero"], "url_sumario": url, "url_pdf_boletin": s["url_pdf"], "fuente": SIGLAS,
              "captura_sha256": captura["sha256"]} for x in s["anuncios"]]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    inf.update({"resultado": "ok", "numero": s["numero"], "sha256": captura["sha256"], "disposiciones": len(filas),
                "empleo_publico": len(empleo)})
    if not filas:
        inf["alertas"].append(f"BOP Las Palmas {d}: sumario sin anuncios (posible cambio de formato)")
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
    d = a.hasta
    while d >= a.desde:
        ruta = _ruta(a.salida, "dias", d, "json")
        hecho, reintento = estado_dia(ruta)
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
            if freno.anotar(inf, reintento=reintento):
                break
            print(f"BOP Las Palmas {d}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            time.sleep(a.pausa)
        d -= timedelta(days=1)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
