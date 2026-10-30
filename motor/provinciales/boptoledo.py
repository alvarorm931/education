"""Conector del Boletín Oficial de la Provincia de Toledo.

Formato verificado el 30/10/2026 desde GitHub (también para 2022):
  - Sumario de un día: https://bop.diputoledo.es/webEbop/ebopResumen.jsp?publication_date=DD/MM/AAAA
    &publication_date_to=DD/MM/AAAA. Cabecera «Boletín número 208 publicado el día 29/10/2026»; por anuncio, el tipo
    de anunciante (h2 «Tipo Anunciante : Ayuntamiento»), el anunciante (h3 «Anunciante : AYUNTAMIENTO DE …», que vale
    para los anuncios siguientes hasta el próximo), el número de inserción, el tipo de anuncio, el asunto y el PDF
    (DocGet?id=…&insert_number=N&insert_year=AAAA).
  - robots.txt cierra todo el servidor; se lee como boletín oficial (motor/http.py, decisión del 30/10/2026).

Uso:
  python -m motor.provinciales.boptoledo --salida ruta/                                   # ayer y hoy
  python -m motor.provinciales.boptoledo --desde 2022-01-01 --max-minutos 30 --salida ruta/
  python -m motor.provinciales.boptoledo --textos --max-minutos 30 --salida ruta/
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
from motor.http import obtener
from motor.provinciales.comun import CON_TEXTO, texto_pdf

FUENTE = "boptoledo"
SIGLAS = "BOP-TOLEDO"
MADRID = ZoneInfo("Europe/Madrid")
BASE = "https://bop.diputoledo.es/webEbop/"
NOMBRES = ("Boletín Oficial de la Provincia de Toledo",)

RE_CABECERA = re.compile(r"<h1>\s*Bolet[ií]n n[uú]mero\s+(?P<n>\d+)\s+publicado el d[ií]a\s+(?P<d>\d{2})/(?P<m>\d{2})/(?P<a>\d{4})")
RE_TOKEN = re.compile(r"<h2>\s*Tipo Anunciante\s*:\s*(?P<tipo>[^<]*)</h2>"
                      r'|<h3 class="publisherBlock">\s*Anunciante\s*:\s*(?P<ent>[^<]*)</h3>'
                      r'|<div id="\d+>?" class="announce">(?P<anuncio>.*?)</ul>', re.DOTALL)
RE_CABECERA_PDF = re.compile(r"^(?:BOLET[IÍ]N OFICIAL|Provincia de Toledo|N[úu]mero \d+.*|P[áa]gina \d+.*|"
                             r"Firmado digitalmente.*|C[óo]digo de verificaci[óo]n.*|\d+)$", re.IGNORECASE)


def url_dia(d: date) -> str:
    return f"{BASE}ebopResumen.jsp?publication_date={d:%d/%m/%Y}&publication_date_to={d:%d/%m/%Y}"


def _texto(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())


def parsear_dia(contenido: bytes) -> dict:
    h = contenido.decode("utf-8", errors="replace")
    c = RE_CABECERA.search(h)
    tipo = entidad = None
    anuncios = []
    for m in RE_TOKEN.finditer(h):
        if m.group("tipo") is not None:
            tipo, entidad = _texto(m.group("tipo")), None
        elif m.group("ent") is not None:
            entidad = _texto(m.group("ent"))
        else:
            a = m.group("anuncio")
            num = re.search(r"N[úu]mero de inserci[óo]n\s*:\s*</strong>\s*(\d+)", a)
            doc = re.search(r'href="(DocGet\?[^"]+)"', a)
            ta = re.search(r"Tipo de anuncio\s*:\s*</strong>([^<]*)", a)
            asunto = re.search(r"Resumen/Asunto\s*:\s*</strong>(.*?)</li>", a, re.DOTALL)
            if not num:
                continue
            anio = re.search(r"insert_year=(\d{4})", doc.group(1)) if doc else None
            anuncios.append({"numero_anuncio": num.group(1), "anio_insercion": anio.group(1) if anio else None,
                             "tipo_anunciante": tipo, "entidad": entidad,
                             "tipo_anuncio": _texto(ta.group(1)) if ta else None,
                             "titulo": _texto(asunto.group(1)) if asunto else "",
                             "url_pdf": BASE + html.unescape(doc.group(1)) if doc else None})
    return {"numero": c.group("n") if c else None,
            "fecha": f"{c.group('a')}-{c.group('m')}-{c.group('d')}" if c else None, "anuncios": anuncios}


def es_local(x: dict) -> bool:
    t = normalizar(x.get("tipo_anunciante") or "")
    return any(p in t for p in ("ayuntamiento", "diputacion", "mancomunidad", "consorcio", "entidad local", "local"))


def convocante(x: dict) -> dict | None:
    c = convocante_de_organismo(x.get("entidad") or "")
    if c and not c.get("provincia"):
        c["provincia"] = "Toledo" if c.get("tipo") != "Diputación Provincial" else c.get("provincia")
    if c and c.get("tipo") == "Diputación Provincial":
        c["provincia"] = "Toledo"
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
        inf["alertas"].append(f"BOP Toledo {d}: HTTP {r.status}")
        return inf
    s = parsear_dia(r.contenido)
    if not s["fecha"]:
        inf["resultado"] = "sin_boletin"  # el día no tiene boletín (festivo o fin de semana)
        return inf
    if s["fecha"] != d.isoformat():
        inf["resultado"] = "error_formato"
        inf["alertas"].append(f"BOP Toledo {d}: la página es del {s['fecha']}")
        return inf
    captura = archivo.guardar(FUENTE, d, r.contenido, url, "html", r.status, r.cabeceras)
    filas = [{**x, "id": f"BOPTOLEDO-{x.get('anio_insercion') or d.year}-{x['numero_anuncio']}", "fecha": d.isoformat(), "boletin": s["numero"],
              "url_dia": url, "fuente": SIGLAS, "captura_sha256": captura["sha256"]} for x in s["anuncios"]]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    inf.update({"resultado": "ok", "numero": s["numero"], "sha256": captura["sha256"], "disposiciones": len(filas),
                "empleo_publico": len(empleo)})
    if not filas:
        inf["alertas"].append(f"BOP Toledo {d}: sumario sin anuncios (posible cambio de formato)")
    return inf


def ruta_texto(raiz: Path, x: dict) -> Path:
    return _base(raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"


def textos_pendientes(raiz: Path) -> list[dict]:
    lista = []
    for f in sorted((_base(raiz) / "oposiciones").glob("*/*/*.jsonl"), reverse=True):
        lista += [x for x in leer_jsonl(f) if x.get("url_pdf") and not ruta_texto(raiz, x).exists()]
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
            lambda c, x: {"titulo": x.get("titulo"), **{k: v for k, v in texto_pdf(c, x.get("tipo_acto") in CON_TEXTO,
                                                                                    RE_CABECERA_PDF).items()
                                                         if k != "titulo"}},
            archivo, FUENTE, a.max_minutos, a.pausa, accept="application/pdf", ext="pdf", por_registro=True)
        print(f"BOP Toledo textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        return 0

    inicio, informes, freno = time.monotonic(), [], Freno()
    d = a.hasta
    while d >= a.desde:
        ruta = _ruta(a.salida, "dias", d, "json")
        hecho, reintento = estado_dia(ruta)
        if d.weekday() >= 5 and not hecho:
            escribir_json(ruta, {"fecha": d.isoformat(), "resultado": "sin_boletin", "nota": "fin de semana",
                                 "alertas": []})
            hecho = True
        if not hecho or (d >= hoy - timedelta(days=1) and d.weekday() < 5):
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
            print(f"BOP Toledo {d}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            time.sleep(a.pausa)
        d -= timedelta(days=1)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    for x in alertas[:30]:
        print(" -", x)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
