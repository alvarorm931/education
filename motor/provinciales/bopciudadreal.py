"""Conector del Boletín Oficial de la Provincia de Ciudad Real.

Formato verificado el 29/10/2026 desde GitHub (también para 2022):
  - Sumario de cada día: https://bop.dipucr.es/bop/AAAA/MM/DD (ISO-8859-1). El título de la página dice el número y
    la fecha («Boletín Oficial de la Provincia 208 · Miércoles 28 de Octubre de 2026»).
  - Secciones (h3 «AYUNTAMIENTOS», «DIPUTACIÓN PROVINCIAL»...), entidad (p.clasificaciones) y anuncios (li con
    número, título, página y PDF en https://se1.dipucr.es:4443/SIGEM_BuscadorDocsWeb/getDocument.do?...).
  - El servidor no envía su certificado intermedio (GlobalSign GCC R6 AlphaSSL 2025): está en motor/certificados/.

Uso:
  python -m motor.provinciales.bopciudadreal --salida ruta/                                   # ayer y hoy
  python -m motor.provinciales.bopciudadreal --desde 2022-01-01 --max-minutos 30 --salida ruta/
  python -m motor.provinciales.bopciudadreal --textos --max-minutos 30 --salida ruta/
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
from motor.autonomicos.comun import (Freno, clasificar, convocante_de_organismo, descargar_textos, es_empleo_estricto,
                                     escribir_json, escribir_jsonl, leer_jsonl, nombre_propio)
from motor.boe.clasificar import normalizar
from motor.extraccion.texto_es import fecha_texto
from motor.http import obtener
from motor.provinciales.comun import CON_TEXTO, texto_pdf

FUENTE = "bopciudadreal"
SIGLAS = "BOP-CIUDADREAL"
MADRID = ZoneInfo("Europe/Madrid")
BASE = "https://bop.dipucr.es"
NOMBRES = ("Boletín Oficial de la Provincia de Ciudad Real", "BOP de Ciudad Real")
SECCIONES_LOCALES = ("ayuntamientos", "diputacion", "mancomunidad", "consorcio", "entidad", "organismo")
RE_CABECERA_PDF = re.compile(
    r"^(?:Boletín Oficial de la Provincia de Ciudad Real|BOP|Número \d+ · .*|\d+ de \w+ de \d{4}|"
    r"Página \d+|Pag\. \d+|https?://bop\.dipucr\.es\S*|Anuncio número \d+.*|Bolet[ií]n Oficial)$", re.IGNORECASE)

RE_TITULO_PAGINA = re.compile(r"<title>\s*Bolet[^<]*?Provincia (?P<n>\d+) \S (?P<dia>[^<|]+?)\s*\|", re.IGNORECASE)
RE_FECHA = re.compile(r"(?P<d>\d{1,2}) de (?P<m>[A-Za-záéíóú]+) de (?P<a>\d{4})")
RE_TOKEN = re.compile(
    r'<h3 class="admons">(?P<sec>[^<]+)</h3>'
    r'|<p class="clasificaciones">(?P<ent>[^<]+)</p>'
    r'|<li id="(?P<num>\d+)">\s*<p><a href="(?P<pdf>[^"]+)"[^>]*>(?P<tit>.*?)</a>', re.DOTALL)


def url_dia(d: date) -> str:
    return f"{BASE}/bop/{d:%Y/%m/%d}"


def _texto(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def parsear_dia(contenido: bytes) -> dict:
    h = contenido.decode("iso-8859-1")
    t = RE_TITULO_PAGINA.search(h)
    fecha = numero = None
    if t:
        numero = t.group("n")
        f = RE_FECHA.search(t.group("dia"))
        fecha = fecha_texto(f.group("d"), f.group("m"), f.group("a")) if f else None
    i = h.find('<div id="clasificaciones">')
    seccion = entidad = None
    anuncios = []
    for m in RE_TOKEN.finditer(h, max(i, 0)):
        if m.group("sec"):
            seccion, entidad = _texto(m.group("sec")), None
        elif m.group("ent"):
            entidad = _texto(m.group("ent"))
        elif m.group("num"):
            anuncios.append({"numero_anuncio": m.group("num"), "seccion": seccion, "organismo": entidad,
                             "titulo": _texto(m.group("tit")), "url_pdf": html.unescape(m.group("pdf"))})
    return {"fecha": fecha, "numero": numero, "anuncios": anuncios}


def convocante(seccion: str | None, entidad: str | None) -> dict | None:
    if not entidad:
        return None
    s = normalizar(seccion or "")
    if s.startswith("ayuntamientos"):
        nombre = nombre_propio(entidad.split(" - ")[0].strip())
        return {"tipo": "Ayuntamiento", "nombre": nombre, "provincia": "Ciudad Real", "organismo": entidad}
    c = convocante_de_organismo(entidad)
    if c and not c.get("provincia"):
        c["provincia"] = "Ciudad Real"
    return c


def seleccionar(disposiciones: list[dict]) -> list[dict]:
    out = []
    for x in disposiciones:
        if not normalizar(x.get("seccion") or "").startswith(SECCIONES_LOCALES):
            continue
        if not es_empleo_estricto(x["titulo"]):
            continue
        out.append({**x, "ambito": "local", **clasificar(x["titulo"], x.get("seccion")),
                    "convocante": convocante(x.get("seccion"), x.get("organismo"))})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "provinciales" / FUENTE


def _ruta(raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


def procesar_dia(d: date, raiz: Path, archivo: Archivo) -> dict:
    url = url_dia(d)
    r = obtener(url, accept="text/html")
    informe = {"fecha": d.isoformat(), "status": r.status, "alertas": []}
    if r.status == 404 or (r.status != 200 and d.weekday() >= 5):
        informe["resultado"] = "sin_boletin"
        return informe
    if r.status != 200:
        informe["resultado"] = "error_http"
        informe["alertas"].append(f"BOP Ciudad Real {d}: HTTP {r.status}")
        return informe
    s = parsear_dia(r.contenido)
    if s["fecha"] != d.isoformat():
        # Sin boletín ese día el portal enseña otro (o la portada)
        informe["resultado"] = "sin_boletin" if s["fecha"] or d.weekday() >= 5 else "error_formato"
        if informe["resultado"] == "error_formato":
            informe["alertas"].append(f"BOP Ciudad Real {d}: página sin fecha (posible cambio de formato)")
        return informe
    captura = archivo.guardar(FUENTE, d, r.contenido, url, "html", r.status, r.cabeceras)
    filas = [{**x, "id": f"BOPCIUDADREAL-{d:%Y}-{x['numero_anuncio']}", "fecha": d.isoformat(), "boletin": s["numero"],
              "url_html": url, "fuente": SIGLAS, "captura_sha256": captura["sha256"]} for x in s["anuncios"]]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    informe.update({"resultado": "ok", "numero": s["numero"], "sha256": captura["sha256"], "disposiciones": len(filas),
                    "empleo_publico": len(empleo)})
    if not filas:
        informe["alertas"].append(f"BOP Ciudad Real {d}: sumario sin anuncios (posible cambio de formato)")
    return informe


def texto_disposicion(contenido: bytes, con_texto: bool = True) -> dict:
    return texto_pdf(contenido, con_texto, RE_CABECERA_PDF)


def ruta_texto(raiz: Path, x: dict) -> Path:
    return _base(raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"


def textos_pendientes(raiz: Path) -> list[dict]:
    lista = []
    for f in (_base(raiz) / "oposiciones").glob("*/*/*.jsonl"):
        lista += [x for x in leer_jsonl(f) if x.get("url_pdf") and not ruta_texto(raiz, x).exists()]
    lista.sort(key=lambda x: x["fecha"], reverse=True)
    return sorted(lista, key=lambda x: (0 if x.get("tipo_acto") in CON_TEXTO else 1,
                                        0 if x.get("alcance") in (None, "acceso") else 1))


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=date.fromisoformat, default=hoy - timedelta(days=1))
    p.add_argument("--hasta", type=date.fromisoformat, default=hoy)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--textos", action="store_true")
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())

    if a.textos:
        pend = textos_pendientes(a.salida)
        hechos, errores = descargar_textos(
            pend, lambda x: ruta_texto(a.salida, x), lambda x: x["url_pdf"],
            lambda c, x: texto_disposicion(c, x.get("tipo_acto") in CON_TEXTO), archivo, FUENTE, a.max_minutos,
            a.pausa, accept="application/pdf", ext="pdf", por_registro=True)
        print(f"BOP Ciudad Real textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        return 0

    inicio, informes = time.monotonic(), []
    freno = Freno()
    d = a.hasta
    while d >= a.desde:  # del más reciente al más antiguo; lo ya hecho no se repite (salvo ayer y hoy)
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
            print(f"BOP Ciudad Real {d}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            time.sleep(a.pausa)
        d -= timedelta(days=1)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    for x in alertas[:30]:
        print(" -", x)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
