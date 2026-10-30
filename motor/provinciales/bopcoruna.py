"""Conector del Boletín Oficial da Provincia da Coruña (solo títulos).

Formato verificado el 30/10/2026 desde GitHub (también para 2022):
  - Día: https://bop.dacoruna.gal/bopportal/cambioBoletin?fechaInput=DD%2fMM%2fAAAA («Sumario do Boletín Nº 206 -
    Mércores, 28 de outubro de 2026»). Sin boletín (sábados, domingos, festivos) responde 500.
  - Secciones en h1 («Administración Local», «Municipal»), entidad en h2/h3 y cada anuncio en div.bloqueAnuncio con
    su número («2026/6891») y su título en p.resumenSumario.
  - El texto de cada anuncio, en HTML (versión del PDF oficial): /bopportal/publicado/AAAA/MM/DD/AAAA_NNNNNNNNNN.html.
    robots.txt cierra /bopportal/publicado; se lee como boletín oficial (motor/http.py, decisión del 30/10/2026).
  - Títulos en gallego o en castellano.

Uso:
  python -m motor.provinciales.bopcoruna --salida ruta/                                   # ayer y hoy
  python -m motor.provinciales.bopcoruna --desde 2022-01-01 --max-minutos 30 --salida ruta/
  python -m motor.provinciales.bopcoruna --textos --max-minutos 30 --salida ruta/
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
from motor.autonomicos.comun import (Freno, articulo_delante, clasificar, convocante_de_organismo, descargar_textos,
                                     es_empleo_estricto, escribir_json, escribir_jsonl, leer_jsonl)
from motor.boe.clasificar import normalizar
from motor.extraccion.texto_es import fecha_texto
from motor.http import obtener
from motor.limpieza import limpiar_html, texto_de

FUENTE = "bopcoruna"
SIGLAS = "BOP-CORUNA"
MADRID = ZoneInfo("Europe/Madrid")
BASE = "https://bop.dacoruna.gal/bopportal"
NOMBRES = ("Boletín Oficial de la Provincia de A Coruña", "Boletín Oficial da Provincia da Coruña")

RE_INFO = re.compile(r'<div id\s*=\s*"infoBoletin">.*?>\s*Sumario do Bolet(?:&iacute;|í)n N(?:&ordm;|º)\s*(?P<n>\d+)\s*-\s*'
                     r'\w+,\s*(?P<d>\d{1,2}) de (?P<m>\w+) de (?P<a>\d{4})', re.S)
RE_RUTA = re.compile(r'id="rutaRelativa"[^>]*value="(?P<r>[^"]+)"')
RE_TOKEN = re.compile(
    r'<h1 class\s*=\s*"(?P<cls>administracion|norepetido)">(?P<h1>[^<]+)<'
    r'|<h(?P<nivel>[2-5]) class\s*=\s*"tituloEdicto">(?P<ent>[^<]+)</h[2-5]>'
    r'|<div id\s*=\s*"(?P<bloque>\d+)" class\s*=\s*"bloqueAnuncio">'
    r'|<p class\s*=\s*"resumenSumario">\s*<a href\s*=\s*"(?P<fich>[^"]+)"[^>]*>\s*(?P<num>\d{4}/\d+)</a>\s*'
    r'<a [^>]*>(?P<tit>.*?)</a>', re.S)


def url_dia(d: date) -> str:
    return f"{BASE}/cambioBoletin?fechaInput={d:%d}%2f{d:%m}%2f{d:%Y}"


def _texto(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def parsear_dia(contenido: bytes) -> dict:
    h = contenido.decode("utf-8", errors="replace")
    info, ruta = RE_INFO.search(h), RE_RUTA.search(h)
    fecha = fecha_texto(info.group("d"), info.group("m"), info.group("a")) if info else None
    administracion = seccion = None
    entidades: dict[int, str] = {}
    anuncios = []
    for m in RE_TOKEN.finditer(h):
        if m.group("h1"):
            if m.group("cls") == "administracion":
                administracion, seccion = _texto(m.group("h1")), None
            else:
                seccion = _texto(m.group("h1"))
            entidades = {}
        elif m.group("bloque"):
            entidades = {}
        elif m.group("ent"):
            nivel = int(m.group("nivel"))
            entidades = {k: v for k, v in entidades.items() if k < nivel}
            entidades[nivel] = articulo_delante(_texto(m.group("ent")))  # «Pobra do Caramiñal, A» -> «A Pobra…»
        elif m.group("num"):
            base = f"{BASE}{ruta.group('r')}/" if ruta else None
            fichero = m.group("fich")
            anuncios.append({
                "numero_anuncio": m.group("num"), "administracion": administracion, "seccion": seccion,
                "organismo": " - ".join(entidades[k] for k in sorted(entidades)) or None,
                "entidad": entidades[min(entidades)] if entidades else None,
                "titulo": _texto(m.group("tit")),
                "url_pdf": base + fichero if base else None,
                "url_html": base + fichero.replace(".pdf", ".html") if base else None,
            })
    return {"numero": info.group("n") if info else None, "fecha": fecha, "anuncios": anuncios}


def convocante(x: dict) -> dict | None:
    """En «Administración Local · Municipal» la entidad es el nombre del concello («Abegondo»)."""
    ent = x.get("entidad")
    if not ent:
        return None
    if normalizar(x.get("seccion") or "") == "municipal" and not re.match(r"(?i)concello|mancomunidade|consorcio", ent):
        return {"tipo": "Ayuntamiento", "nombre": ent, "provincia": "A Coruña", "organismo": f"Concello de {ent}"}
    c = convocante_de_organismo(ent)
    if c and not c.get("provincia"):
        c["provincia"] = "A Coruña"
    return c


def seleccionar(disposiciones: list[dict]) -> list[dict]:
    out = []
    for x in disposiciones:
        if "local" not in normalizar(x.get("administracion") or ""):
            continue
        if not es_empleo_estricto(x["titulo"]):
            continue
        out.append({**x, "ambito": "local", **clasificar(x["titulo"], x.get("seccion")), "convocante": convocante(x)})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "provinciales" / FUENTE


def _ruta(raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


def procesar_dia(d: date, raiz: Path, archivo: Archivo) -> dict:
    url = url_dia(d)
    r = obtener(url, accept="text/html")
    informe = {"fecha": d.isoformat(), "status": r.status, "alertas": []}
    if r.status == 500 or (r.status != 200 and d.weekday() >= 5):
        informe["resultado"] = "sin_boletin"  # el portal responde 500 los días sin boletín
        if d.weekday() < 5:
            informe["alertas"].append(f"BOP A Coruña {d}: día laborable sin boletín (¿festivo?)")
        return informe
    if r.status != 200:
        informe["resultado"] = "error_http"
        informe["alertas"].append(f"BOP A Coruña {d}: HTTP {r.status}")
        return informe
    s = parsear_dia(r.contenido)
    if s["fecha"] != d.isoformat():
        informe["resultado"] = "error_formato"
        informe["alertas"].append(f"BOP A Coruña {d}: la página dice número {s['numero']} y fecha {s['fecha']}")
        return informe
    captura = archivo.guardar(FUENTE, d, r.contenido, url, "html", r.status, r.cabeceras)
    filas = [{**x, "id": f"BOPCORUNA-{x['numero_anuncio'].replace('/', '-')}", "fecha": d.isoformat(),
              "boletin": s["numero"], "url_dia": url, "fuente": SIGLAS, "captura_sha256": captura["sha256"]}
             for x in s["anuncios"]]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    informe.update({"resultado": "ok", "numero": s["numero"], "sha256": captura["sha256"], "disposiciones": len(filas),
                    "empleo_publico": len(empleo)})
    if not filas:
        informe["alertas"].append(f"BOP A Coruña {d}: sumario sin anuncios (posible cambio de formato)")
    return informe


def texto_disposicion(contenido: bytes) -> dict:
    h = contenido.decode("utf-8", errors="replace")
    i = h.find('<div class="Marco-gr-fico-b-sico"')
    if i < 0:
        raise ValueError("anuncio sin cuerpo: posible cambio de formato")
    titulo = re.search(r'<p class="P-rrafo-texto-sumario">(.*?)</p>', h, re.DOTALL)
    return {"titulo": texto_de(titulo.group(1)) if titulo else None, **limpiar_html(h[i:])}


def ruta_texto(raiz: Path, x: dict) -> Path:
    return _base(raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"


def textos_pendientes(raiz: Path) -> list[dict]:
    lista = []
    for f in sorted((_base(raiz) / "oposiciones").glob("*/*/*.jsonl"), reverse=True):
        lista += [x for x in leer_jsonl(f) if x.get("url_html") and not ruta_texto(raiz, x).exists()]
    return sorted(lista, key=lambda x: 0 if x.get("alcance") in (None, "acceso") else 1)


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=date.fromisoformat, default=hoy - timedelta(days=1))
    p.add_argument("--hasta", type=date.fromisoformat, default=hoy)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    p.add_argument("--textos", action="store_true")
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    if a.textos:
        pend = textos_pendientes(a.salida)
        hechos, errores = descargar_textos(pend, lambda x: ruta_texto(a.salida, x), lambda x: x["url_html"],
                                           texto_disposicion, archivo, FUENTE, a.max_minutos, a.pausa,
                                           accept="text/html", ext="html")
        print(f"BOP A Coruña textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        return 0
    inicio, informes, freno = time.monotonic(), [], Freno()
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
            print(f"BOP A Coruña {d}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            time.sleep(a.pausa)
        d -= timedelta(days=1)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    for x in alertas[:30]:
        print(" -", x)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
