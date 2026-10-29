"""Conector del Boletín Oficial de la Provincia de Santa Cruz de Tenerife.

Formato verificado el 29/10/2026 desde GitHub (también para 2022): portal PHP antiguo.
  - Sumario de un día: http://www.bopsantacruzdetenerife.es/bopsc2/sumario.php?codigopub=1&fecha_mas_reciente=AAAA-MM-DD
    («SUMARIO DEL BOLETÍN Nº 129, DE FECHA 28-10-26»). Un día sin boletín da la misma página sin número ni anuncios.
  - Secciones («III. ADMINISTRACION LOCAL»), entidad en negrita y cursiva y cada anuncio en una línea que empieza
    por «- ». No hay enlace por anuncio: el texto está en el PDF del boletín completo («Descargar Boletín»).
  - Sale lunes, miércoles y viernes; desde noviembre de 2020 con este formato.

Uso:
  python -m motor.provinciales.boptenerife --salida ruta/                                   # ayer y hoy
  python -m motor.provinciales.boptenerife --desde 2022-01-01 --max-minutos 30 --salida ruta/
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
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (Freno, clasificar, convocante_de_organismo, es_empleo_estricto, escribir_json,
                                     escribir_jsonl)
from motor.boe.clasificar import normalizar
from motor.http import obtener

FUENTE = "boptenerife"
SIGLAS = "BOP-TENERIFE"
MADRID = ZoneInfo("Europe/Madrid")
BASE = "http://www.bopsantacruzdetenerife.es/bopsc2/"
NOMBRES = ("Boletín Oficial de la Provincia de Santa Cruz de Tenerife",)

RE_CABECERA = re.compile(
    r"SUMARIO DEL BOLET(?:&Iacute;|Í|I)N N(?:&ordm;|º|o)\s*(?:<[^>]+>\s*)*(?P<n>\d*)\s*(?:<[^>]+>\s*)*,\s*DE FECHA\s*"
    r"(?:<[^>]+>\s*)*(?P<d>\d{1,2})-(?P<m>\d{1,2})-(?P<a>\d{2})", re.IGNORECASE)
RE_PDF = re.compile(r'href="(?P<pdf>[^"]+\.pdf)"[^>]*>\s*Descargar', re.IGNORECASE)
RE_TOKEN = re.compile(
    r'<font color="navy">\s*(?P<sec>[IVX]+\.\s*[^<]+?)\s*</font>'
    r'|<b><i>(?P<ent>[^<]+)</i></b>'
    r'|<br>\s*-\s*(?P<item>[^<]+)', re.IGNORECASE)
SECCIONES_LOCALES = ("iii.",)


def url_dia(d: date) -> str:
    return f"{BASE}sumario.php?codigopub=1&fecha_mas_reciente={d:%Y-%m-%d}"


def _texto(s: str) -> str:
    return " ".join(html.unescape(s).split())


def parsear_dia(contenido: bytes) -> dict:
    h = contenido.decode("utf-8", errors="replace")
    c = RE_CABECERA.search(h)
    numero = c.group("n") if c and c.group("n") else None
    fecha = None
    if c:
        try:
            fecha = date(2000 + int(c.group("a")), int(c.group("m")), int(c.group("d"))).isoformat()
        except ValueError:
            fecha = None
    pdf = RE_PDF.search(h)
    seccion = entidad = None
    anuncios = []
    for m in RE_TOKEN.finditer(h):
        if m.group("sec"):
            seccion, entidad = _texto(m.group("sec")), None
        elif m.group("ent"):
            entidad = _texto(m.group("ent"))
        elif m.group("item") and seccion:
            anuncios.append({"seccion": seccion, "organismo": entidad, "titulo": _texto(m.group("item"))})
    return {"numero": numero, "fecha": fecha, "url_boletin": urljoin(BASE, pdf.group("pdf")) if pdf else None,
            "anuncios": anuncios}


def seleccionar(disposiciones: list[dict]) -> list[dict]:
    out = []
    for x in disposiciones:
        if not normalizar(x.get("seccion") or "").startswith(SECCIONES_LOCALES):
            continue
        if not es_empleo_estricto(x["titulo"]):
            continue
        conv = convocante_de_organismo(x.get("organismo") or "")
        if conv and not conv.get("provincia"):
            conv["provincia"] = "Santa Cruz de Tenerife"
        out.append({**x, "ambito": "local", **clasificar(x["titulo"], x.get("seccion")), "convocante": conv})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "provinciales" / FUENTE


def _ruta(raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


def procesar_dia(d: date, raiz: Path, archivo: Archivo) -> dict:
    url = url_dia(d)
    r = obtener(url, accept="text/html")
    informe = {"fecha": d.isoformat(), "status": r.status, "alertas": []}
    if r.status != 200:
        informe["resultado"] = "error_http"
        informe["alertas"].append(f"BOP Tenerife {d}: HTTP {r.status}")
        return informe
    s = parsear_dia(r.contenido)
    if s["fecha"] != d.isoformat():
        informe["resultado"] = "error_formato"
        informe["alertas"].append(f"BOP Tenerife {d}: la página dice fecha {s['fecha']} (posible cambio de formato)")
        return informe
    if not s["numero"]:
        informe["resultado"] = "sin_boletin"
        return informe
    captura = archivo.guardar(FUENTE, d, r.contenido, url, "html", r.status, r.cabeceras)
    filas = [{**x, "id": f"BOPTENERIFE-{d.isoformat()}-{i:03d}", "fecha": d.isoformat(), "boletin": s["numero"],
              "url_html": url, "url_pdf": s["url_boletin"], "fuente": SIGLAS, "captura_sha256": captura["sha256"]}
             for i, x in enumerate(s["anuncios"], 1)]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    informe.update({"resultado": "ok", "numero": s["numero"], "url_boletin": s["url_boletin"],
                    "sha256": captura["sha256"], "disposiciones": len(filas), "empleo_publico": len(empleo)})
    if not filas:
        informe["alertas"].append(f"BOP Tenerife {d}: sumario sin anuncios (posible cambio de formato)")
    return informe


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=date.fromisoformat, default=hoy - timedelta(days=1))
    p.add_argument("--hasta", type=date.fromisoformat, default=hoy)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--textos", action="store_true", help="sin efecto: el texto solo está en el boletín completo")
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    if a.textos:
        print("BOP Tenerife: sin textos por anuncio (solo el PDF del boletín completo)")
        return 0
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    inicio, informes, freno = time.monotonic(), [], Freno()
    d = a.hasta
    while d >= a.desde:
        ruta = _ruta(a.salida, "dias", d, "json")
        hecho = ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") in {"ok", "sin_boletin"}
        if d.weekday() >= 5 and not hecho:
            escribir_json(ruta, {"fecha": d.isoformat(), "resultado": "sin_boletin", "nota": "fin de semana",
                                 "alertas": []})
            hecho = True
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
            if freno.anotar(inf):
                break
            print(f"BOP Tenerife {d}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            time.sleep(a.pausa)
        d -= timedelta(days=1)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    for x in alertas[:30]:
        print(" -", x)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
