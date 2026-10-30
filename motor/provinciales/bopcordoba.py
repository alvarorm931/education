"""Conector del Boletín Oficial de la Provincia de Córdoba.

Formato verificado el 30/10/2026 desde GitHub (también para 2022): portal Next.js de Eprinsa con la página servida
entera (sin JavaScript), aunque por trozos.
  - Día: https://bop.dipucordoba.es/dia/DD-MM-AAAA. Cabecera «BOLETÍN número 209» y «28 . Octubre. 2026»;
    secciones en h1 («VI - ADMINISTRACIÓN LOCAL»), entidad en li.emisor > h2 y cada anuncio en li.announcement
    (título en el primer párrafo y enlace al PDF /visor-pdf/DD-MM-AAAA/BOP-A-AAAA-N.pdf). Un día sin boletín dice
    «No se encontraron datos.».
  - Parte de la página llega después en bloques <div hidden id="S:x"> que ocupan el sitio de <template id="P:x">:
    y de <template id="B:x"> (límites de carga): se recolocan antes de leerla (si no, un anuncio podría quedarse sin su PDF o con el de otro).
  - Sale de lunes a viernes. robots.txt no existe (404): sin restricciones.

Uso:
  python -m motor.provinciales.bopcordoba --salida ruta/                                   # ayer y hoy
  python -m motor.provinciales.bopcordoba --desde 2022-01-01 --max-minutos 30 --salida ruta/
  python -m motor.provinciales.bopcordoba --textos --max-minutos 30 --salida ruta/
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
                                     escribir_json, escribir_jsonl, leer_jsonl, estado_dia)
from motor.boe.clasificar import normalizar
from motor.extraccion.texto_es import fecha_texto
from motor.http import obtener
from motor.provinciales.comun import CON_TEXTO, texto_pdf

FUENTE = "bopcordoba"
SIGLAS = "BOP-CORDOBA"
MADRID = ZoneInfo("Europe/Madrid")
BASE = "https://bop.dipucordoba.es"
NOMBRES = ("Boletín Oficial de la Provincia de Córdoba",)
SECCIONES_LOCALES = ("administracion local", "diputacion", "otras entidades")
RE_CABECERA_PDF = re.compile(
    r"^(?:Bolet[ií]n Oficial de la Provincia de C[oó]rdoba|BOP|N[uú]m(?:ero|\.)? \d+.*|\w+, \d+ de \w+ de \d{4}|"
    r"P[aá]g(?:ina|\.)? \d+.*|https?://\S+|C[oó]digo de verificaci\S*.*|\d+)$", re.IGNORECASE)

RE_HUECO = re.compile(r'<template id="[PB]:(?P<id>[^"]+)"></template>')
RE_BLOQUE = re.compile(r'<div hidden id="S:(?P<id>[^"]+)">')
RE_NUMERO = re.compile(r"BOLET[ÍI]N(?:<!-- -->)?\s*<span>n[uú]mero(?:<!-- -->)?\s*(?:<!-- -->)?(?P<n>\d+)</span>")
RE_FECHA = re.compile(r'<p class="text-primary mb-1">\s*(?P<d>\d{1,2})\s*\.\s*(?P<m>[A-Za-záéíóú]+)\s*\.\s*(?P<a>\d{4})')
RE_TOKEN = re.compile(
    r'<h1 class="font-j">(?P<sec>.*?)</h1>'
    r'|<li class="emisor"><h2>(?P<ent>.*?)</h2>'
    r'|<li class="announcement[^"]*">\s*<p>(?P<tit>.*?)</p>'
    r'|href="(?P<pdf>/visor-pdf/[^"]+/(?P<cve>BOP-A-\d{4}-\d+)\.pdf)"', re.DOTALL)


def url_dia(d: date) -> str:
    return f"{BASE}/dia/{d:%d-%m-%Y}"


def _texto(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<!--.*?-->|<[^>]+>", " ", s)).split())


def _bloques(h: str) -> dict[str, str]:
    """Contenido de cada <div hidden id="S:x"> (con los div anidados que lleve dentro)."""
    out = {}
    for m in RE_BLOQUE.finditer(h):
        i, nivel = m.end(), 1
        for t in re.finditer(r"<div\b|</div>", h[i:]):
            nivel += 1 if t.group(0) == "<div" else -1
            if nivel == 0:
                out[m.group("id")] = h[i:i + t.start()]
                break
    return out


def recolocar(h: str) -> str:
    """Pone cada trozo diferido en el sitio de su plantilla (hasta 10 niveles de trozos dentro de trozos)."""
    h = re.sub(r"(?s)<script.*?</script>", "", h)
    bloques = _bloques(h)
    h = re.sub(r'(?s)<div hidden id="S:[^"]+">.*$', "", h)  # los trozos van al final de la página
    for _ in range(10):
        nuevo = RE_HUECO.sub(lambda m: bloques.get(m.group("id"), ""), h)
        if nuevo == h:
            break
        h = nuevo
    return h


def parsear_dia(contenido: bytes) -> dict:
    h = recolocar(contenido.decode("utf-8", errors="replace"))
    n, f = RE_NUMERO.search(h), RE_FECHA.search(h)
    fecha = fecha_texto(f.group("d"), f.group("m"), f.group("a")) if f else None
    seccion = entidad = None
    anuncios = []
    for m in RE_TOKEN.finditer(h):
        if m.group("sec") is not None:
            seccion, entidad = _texto(m.group("sec")), None
        elif m.group("ent") is not None:
            entidad = _texto(m.group("ent"))
        elif m.group("tit") is not None:
            anuncios.append({"seccion": seccion, "organismo": entidad, "titulo": _texto(m.group("tit")),
                             "cve": None, "url_pdf": None})
        elif m.group("pdf") and anuncios and anuncios[-1]["cve"] is None:
            anuncios[-1].update({"cve": m.group("cve"), "url_pdf": BASE + m.group("pdf")})
    return {"numero": n.group("n") if n else None, "fecha": fecha,
            "sin_datos": "No se encontraron datos." in contenido.decode("utf-8", errors="replace"),
            "anuncios": anuncios}


def seleccionar(disposiciones: list[dict]) -> list[dict]:
    out = []
    for x in disposiciones:
        if not normalizar(x.get("seccion") or "").split(" - ")[-1].startswith(SECCIONES_LOCALES):
            continue
        if not es_empleo_estricto(x["titulo"]):
            continue
        conv = convocante_de_organismo(x.get("organismo") or "")
        if conv and not conv.get("provincia"):
            conv["provincia"] = "Córdoba"
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
        informe["alertas"].append(f"BOP Córdoba {d}: HTTP {r.status}")
        return informe
    s = parsear_dia(r.contenido)
    if s["sin_datos"] and not s["numero"]:
        informe["resultado"] = "sin_boletin"
        if d.weekday() < 5:
            informe["alertas"].append(f"BOP Córdoba {d}: día laborable sin boletín (¿festivo?)")
        return informe
    if s["fecha"] != d.isoformat() or not s["numero"]:
        informe["resultado"] = "error_formato"
        informe["alertas"].append(f"BOP Córdoba {d}: la página dice número {s['numero']} y fecha {s['fecha']}")
        return informe
    captura = archivo.guardar(FUENTE, d, r.contenido, url, "html", r.status, r.cabeceras)
    filas = []
    for i, x in enumerate(s["anuncios"], 1):
        ident = f"BOPCORDOBA-{x['cve'][6:]}" if x["cve"] else f"BOPCORDOBA-{d.isoformat()}-{i:03d}"
        filas.append({**x, "id": ident, "fecha": d.isoformat(), "boletin": s["numero"], "url_html": url,
                      "fuente": SIGLAS, "captura_sha256": captura["sha256"]})
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    informe.update({"resultado": "ok", "numero": s["numero"], "sha256": captura["sha256"], "disposiciones": len(filas),
                    "empleo_publico": len(empleo), "sin_pdf": sum(1 for x in filas if not x["url_pdf"])})
    if not filas:
        informe["alertas"].append(f"BOP Córdoba {d}: boletín sin anuncios (posible cambio de formato)")
    elif informe["sin_pdf"]:
        informe["alertas"].append(f"BOP Córdoba {d}: {informe['sin_pdf']} anuncios sin enlace al PDF")
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
        print(f"BOP Córdoba textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        return 0

    inicio, informes = time.monotonic(), []
    freno = Freno()
    d = a.hasta
    while d >= a.desde:  # del más reciente al más antiguo; lo ya hecho no se repite (salvo ayer y hoy)
        ruta = _ruta(a.salida, "dias", d, "json")
        hecho, reintento = estado_dia(ruta)
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
            if freno.anotar(inf, reintento=reintento):
                break
            print(f"BOP Córdoba {d}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            time.sleep(a.pausa)
        d -= timedelta(days=1)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    for x in alertas[:30]:
        print(" -", x)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
