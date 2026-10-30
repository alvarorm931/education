"""Conector del Boletín Oficial de la Provincia de Soria.

Formato verificado el 30/10/2026 desde GitHub (también para 2022):
  - Boletines de un día: https://bop.dipsoria.es/index.php/mod.boloficial/mem.listadodia/fecha.DD-MM-AAAA, que
    enlaza su ficha («BOP 124 MIÉRCOLES 28 DE OCTUBRE DE 2026», mem.detalle/id.N/relcategoria.210).
  - Ficha del boletín: el PDF entero y el sumario en una lista (ul.lst), un anuncio por elemento con cuatro niveles
    (sección «II. ADMINISTRACIÓN LOCAL», grupo «AYUNTAMIENTOS», entidad «SORIA», asunto); los niveles vacíos
    repiten el del anuncio anterior. Cada anuncio enlaza su PDF (…/fichero.documentos_2024_d5330904%232E%23pdf,
    con el número de anuncio).
  - robots.txt no existe (404).

Uso:
  python -m motor.provinciales.bopsoria --salida ruta/                                  # ayer y hoy
  python -m motor.provinciales.bopsoria --desde 2022-01-01 --max-minutos 30 --salida ruta/
  python -m motor.provinciales.bopsoria --textos --max-minutos 30 --salida ruta/
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
from motor.extraccion.texto_es import fecha_texto
from motor.http import obtener
from motor.provinciales.comun import descargar_textos_pdf

FUENTE = "bopsoria"
SIGLAS = "BOP-SORIA"
MADRID = ZoneInfo("Europe/Madrid")
WEB = "https://bop.dipsoria.es"
NOMBRES = ("Boletín Oficial de la Provincia de Soria",)

RE_FICHA = re.compile(r'href="(?P<url>/index\.php/mod\.boloficial/mem\.detalle/id\.(?P<id>\d+)/relcategoria\.\d+)"\s+'
                      r'title="M[áa]s informaci(?:ó|&oacute;)n BOP (?P<n>\d+)\s+[^"]*?(?P<d>\d{1,2}) DE (?P<m>[A-Z]+) DE '
                      r'(?P<a>\d{4})"', re.IGNORECASE)
RE_NIVEL = re.compile(r'<div style="display:block;(?:border:0px solid red;margin-left:(?P<ml>\d+)px;)?">\s*'
                      r'(?:<p class="fec-f1">(?P<t>.*?)</p>)?', re.DOTALL)
RE_PDF = re.compile(r'<a href="(?P<url>[^"]+fichero\.documentos_(?P<num>\d+)_[0-9a-f]+%232E%23pdf)"')
NIVELES = {0: "seccion", 5: "grupo", 10: "entidad", 15: "titulo"}


def url_dia(d: date) -> str:
    return f"{WEB}/index.php/mod.boloficial/mem.listadodia/fecha.{d:%d-%m-%Y}"


def _t(s: str) -> str:
    t = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).replace("\xa0", " ").split())
    return re.sub(r"^-\s*", "", t).strip()


def fichas(contenido: bytes) -> list[dict]:
    h = contenido.decode("utf-8", errors="replace")
    vistas = {}
    for m in RE_FICHA.finditer(h):
        vistas.setdefault(m.group("id"), {"id_ficha": m.group("id"), "url": WEB + m.group("url"),
                                          "numero": int(m.group("n")),
                                          "fecha": fecha_texto(m.group("d"), m.group("m"), m.group("a"))})
    return list(vistas.values())


def sumario(contenido: bytes) -> list[dict]:
    h = contenido.decode("utf-8", errors="replace")
    i = h.find('<ul class="lst">')
    if i < 0:
        return []
    actual, out = {}, []
    for li in re.findall(r"<li>(.*?)</li>", h[i:], re.DOTALL):
        for m in RE_NIVEL.finditer(li):
            nivel = NIVELES.get(int(m.group("ml") or 0))
            texto = _t(m.group("t")) if m.group("t") else ""
            if nivel and texto:
                actual[nivel] = texto
                orden = list(NIVELES.values())
                for n in orden[orden.index(nivel) + 1:]:  # un nivel nuevo vacía los de debajo
                    actual.pop(n, None)
        pdf = RE_PDF.search(li)
        if pdf and actual.get("titulo"):
            out.append({"numero_anuncio": pdf.group("num"), "seccion": actual.get("seccion"),
                        "grupo": actual.get("grupo"), "entidad": actual.get("entidad"), "titulo": actual["titulo"],
                        "url_pdf": html.unescape(pdf.group("url")).replace("http://", "https://", 1)})
            actual.pop("titulo", None)
    return out


def es_local(x: dict) -> bool:
    return "administracion local" in normalizar(x.get("seccion") or "")


def convocante(x: dict) -> dict | None:
    g, e = normalizar(x.get("grupo") or ""), x.get("entidad") or ""
    if g.startswith("diputacion"):
        c = convocante_de_organismo(x.get("grupo"))
        if c:
            c["organismo"] = f"{x['grupo']} - {e}" if e else x["grupo"]
    elif g.startswith("ayuntamientos"):
        c = convocante_de_organismo(f"AYUNTAMIENTO DE {e}")
    else:
        c = convocante_de_organismo(e or x.get("grupo") or "")
    if c and not c.get("provincia"):
        c["provincia"] = "Soria"
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


def procesar_dia(d: date, raiz: Path, archivo: Archivo, pausa: float = 1.0) -> dict:
    r = obtener(url_dia(d), accept="text/html")
    inf = {"fecha": d.isoformat(), "status": r.status, "alertas": []}
    if r.status != 200:
        inf["resultado"] = "error_http"
        inf["alertas"].append(f"BOP Soria {d}: HTTP {r.status}")
        return inf
    lista = [f for f in fichas(r.contenido) if f["fecha"] == d.isoformat()]
    if not lista:
        inf["resultado"] = "sin_boletin"
        return inf
    filas = []
    for f in lista:
        time.sleep(pausa)
        rb = obtener(f["url"], accept="text/html")
        if rb.status != 200:
            inf["resultado"] = "error_http"
            inf["alertas"].append(f"BOP Soria {d}: ficha {f['id_ficha']}: HTTP {rb.status}")
            return inf
        captura = archivo.guardar(FUENTE, d, rb.contenido, f["url"], "html", rb.status, rb.cabeceras)
        filas += [{**x, "id": f"BOPSORIA-{d.year}-{x['numero_anuncio']}", "fecha": d.isoformat(), "boletin": f["numero"],
                   "url_boletin": f["url"], "fuente": SIGLAS, "captura_sha256": captura["sha256"]}
                  for x in sumario(rb.contenido)]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    inf.update({"resultado": "ok", "numero": ",".join(str(f["numero"]) for f in lista), "disposiciones": len(filas),
                "empleo_publico": len(empleo)})
    if not filas:
        inf["alertas"].append(f"BOP Soria {d}: sumario sin anuncios (posible cambio de formato)")
    return inf


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=date.fromisoformat, default=hoy - timedelta(days=1))
    p.add_argument("--hasta", type=date.fromisoformat, default=hoy)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--textos", action="store_true", help="descargar los PDF de los anuncios de empleo")
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    if a.textos:
        hechos, errores, pendientes = descargar_textos_pdf(_base(a.salida), FUENTE, archivo, a.max_minutos, a.pausa)
        print(f"BOP Soria textos: {hechos} descargados, {errores} errores, {pendientes} pendientes")
        return 0
    inicio, informes, freno = time.monotonic(), [], Freno()
    d = a.hasta
    while d >= a.desde:
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
                inf = procesar_dia(d, a.salida, archivo, a.pausa)
            except (ConnectionError, TimeoutError) as e:
                inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            if not (inf.get("resultado") == "sin_boletin" and d >= hoy - timedelta(days=1)):
                escribir_json(ruta, inf)
            informes.append(inf)
            if freno.anotar(inf):
                break
            print(f"BOP Soria {d}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            time.sleep(a.pausa)
        d -= timedelta(days=1)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
