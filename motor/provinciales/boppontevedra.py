"""Conector del Boletín Oficial da Provincia de Pontevedra (BOPPO): boletín del día, solo títulos.

Formato verificado el 30/10/2026 desde GitHub:
  - La portada https://boppo.depo.gal/es trae el sumario completo del último boletín: «BOPPO número 209 · jueves
    29 de octubre de 2026», administración (h4.tit), organismo (p.Org), entidad (span.pub) y título (p.sumario).
  - robots.txt cierra las fichas (/detalle/), las descargas (/bop-v2-portlet/) y todo PDF. Desde el 30/10/2026 se
    lee como boletín oficial (motor/http.py, decisión de Álvaro): el histórico sale de la ficha de cada día
    (/detalle/-/boppo/AAAA/MM/DD, la que enlaza el calendario), con el mismo sumario que la portada (verificado
    para el 27/10/2026 y el 03/01/2022). No hay documentos concretos cerrados por datos de personas.

Uso:
  python -m motor.provinciales.boppontevedra --salida ruta/
  python -m motor.provinciales.boppontevedra --historico --max-minutos 40 --salida ruta/
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import json
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import Freno, clasificar, convocante_de_organismo, es_empleo_estricto, escribir_json, escribir_jsonl
from motor.boe.clasificar import normalizar
from motor.extraccion.texto_es import fecha_texto
from motor.http import obtener

FUENTE = "boppontevedra"
SIGLAS = "BOP-PONTEVEDRA"
WEB = "https://boppo.depo.gal"
PORTADA = WEB + "/es"
INICIO = date(2022, 1, 1)
MADRID = ZoneInfo("Europe/Madrid")
RE_NUMERO_DIA = re.compile(r'<h2 class="numero">\s*BOPPO\s*<span class="bold">n[uú]mero\s*(?P<n>\d+)\s*</span>')


def url_dia(d: date) -> str:
    """Ficha del boletín de un día (la que enlaza el calendario de la portada), con el mismo sumario que la portada."""
    return f"{WEB}/detalle/-/boppo/{d:%Y/%m/%d}"
NOMBRES = ("Boletín Oficial de la Provincia de Pontevedra", "Boletín Oficial da Provincia de Pontevedra")

RE_CABECERA = re.compile(r'<h2 class="numero">\s*BOPPO\s*<span class="bold">n[uú]mero (?P<n>\d+)</span>\s*</h2>\s*'
                         r'<span class="fecha">\s*\w+ (?P<d>\d{1,2}) de (?P<m>\w+) de (?P<a>\d{4})', re.S)
RE_TOKEN = re.compile(
    r'<h4 class="tit">(?P<adm>[^<]+)</h4>'
    r'|<p class="Org">(?P<org>[^<]+)</p>'
    r'|<span class="inst">(?P<inst>[^<]+)</span>'
    r'|<span class="pub">(?P<pub>[^<]+)</span>.*?<p class="sumario"><a href="(?P<href>/web/boppo/detalle/-/boppo/'
    r'(?P<f>\d{4}/\d{2}/\d{2})/(?P<id>\d+))">(?P<tit>.*?)</a>', re.S)


def _texto(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def parsear_portada(contenido: bytes) -> dict:
    h = contenido.decode("utf-8", errors="replace")
    c = RE_CABECERA.search(h)
    adm = org = inst = None
    anuncios = []
    for m in RE_TOKEN.finditer(h, c.end() if c else 0):
        if m.group("adm"):
            adm, org, inst = _texto(m.group("adm")), None, None
        elif m.group("org"):
            org, inst = _texto(m.group("org")), None
        elif m.group("inst"):
            inst = _texto(m.group("inst"))
        elif m.group("id"):
            anuncios.append({"numero_anuncio": m.group("id"), "administracion": adm, "seccion": org, "instancia": inst,
                             "entidad": _texto(m.group("pub")), "titulo": _texto(m.group("tit")),
                             "url_html": WEB + m.group("href"), "fecha_ruta": m.group("f").replace("/", "-")})
    return {"numero": c.group("n") if c else None,
            "fecha": fecha_texto(c.group("d"), c.group("m"), c.group("a")) if c else None, "anuncios": anuncios}


def convocante(x: dict) -> dict | None:
    ent = x.get("entidad")
    if not ent:
        return None
    if normalizar(x.get("seccion") or "") == "municipal":
        return {"tipo": "Ayuntamiento", "nombre": ent, "provincia": "Pontevedra", "organismo": f"Concello de {ent}"}
    if normalizar(ent).startswith("deputacion provincial"):
        return {"tipo": "Diputación Provincial", "nombre": "Pontevedra", "provincia": "Pontevedra", "organismo": ent}
    c = convocante_de_organismo(ent)
    if c and not c.get("provincia"):
        c["provincia"] = "Pontevedra"
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


def _ruta(raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return raiz / "datos" / "provinciales" / FUENTE / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


def procesar_portada(raiz: Path, archivo: Archivo) -> dict:
    r = obtener(PORTADA, accept="text/html")
    if r.status != 200:
        return {"fecha": None, "status": r.status, "resultado": "error_http", "alertas": [f"BOPPO portada: HTTP {r.status}"]}
    s = parsear_portada(r.contenido)
    if not s["fecha"] and "no está disponible temporalmente" in r.contenido.decode("utf-8", errors="replace"):
        # «Último BOPPO no está disponible temporalmente» (de madrugada, mientras se publica): se reintenta otro día
        return {"fecha": None, "status": 200, "resultado": "fuente_inaccesible",
                "alertas": ["BOPPO: la portada dice que el último boletín no está disponible temporalmente"]}
    if not s["fecha"] or not s["anuncios"]:
        return {"fecha": s["fecha"], "status": 200, "resultado": "error_formato",
                "alertas": ["BOPPO portada sin número, fecha o anuncios (posible cambio de formato)"]}
    d = date.fromisoformat(s["fecha"])
    captura = archivo.guardar(FUENTE, d, r.contenido, PORTADA, "html", r.status, r.cabeceras)
    filas = [{**x, "id": f"BOPPONTEVEDRA-{x['numero_anuncio']}", "fecha": d.isoformat(), "boletin": s["numero"],
              "fuente": SIGLAS, "captura_sha256": captura["sha256"]} for x in s["anuncios"]]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    inf = {"fecha": d.isoformat(), "status": 200, "resultado": "ok", "numero": s["numero"], "origen": "portada",
           "sha256": captura["sha256"], "disposiciones": len(filas), "empleo_publico": len(empleo), "alertas": []}
    escribir_json(_ruta(raiz, "dias", d, "json"), inf)
    return inf


def procesar_dia(d: date, raiz: Path, archivo: Archivo) -> dict:
    url = url_dia(d)
    r = obtener(url, accept="text/html")
    inf = {"fecha": d.isoformat(), "status": r.status, "origen": "ficha_dia", "alertas": []}
    if r.status == 404:
        inf["resultado"] = "sin_boletin"
        return inf
    if r.status != 200:
        inf["resultado"] = "error_http"
        inf["alertas"].append(f"BOPPO {d}: HTTP {r.status}")
        return inf
    h = r.contenido.decode("utf-8", errors="replace")
    n = RE_NUMERO_DIA.search(h)
    s = parsear_portada(r.contenido)
    anuncios = [x for x in s["anuncios"] if x["fecha_ruta"] == d.isoformat()]
    if not n and not anuncios:
        inf["resultado"] = "sin_boletin"
        return inf
    if not anuncios:
        inf["resultado"] = "error_formato"
        inf["alertas"].append(f"BOPPO {d}: ficha del boletín {n.group('n')} sin anuncios (posible cambio de formato)")
        return inf
    captura = archivo.guardar(FUENTE, d, r.contenido, url, "html", r.status, r.cabeceras)
    numero = n.group("n") if n else None
    filas = [{**x, "id": f"BOPPONTEVEDRA-{x['numero_anuncio']}", "fecha": d.isoformat(), "boletin": numero,
              "fuente": SIGLAS, "captura_sha256": captura["sha256"]} for x in anuncios]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    inf.update({"resultado": "ok", "numero": numero, "sha256": captura["sha256"], "disposiciones": len(filas),
                "empleo_publico": len(empleo)})
    return inf


def historico(raiz: Path, archivo: Archivo, desde: date, hasta: date, pausa: float, max_minutos: float) -> int:
    """De hasta hacia atrás, día a día, por la ficha del boletín. robots.txt cierra /detalle/ entero (no documentos
    concretos): se lee como boletín oficial (motor/http.py, decisión del 30/10/2026)."""
    inicio, informes, freno, d = time.monotonic(), [], Freno(), hasta
    while d >= desde:
        ruta = _ruta(raiz, "dias", d, "json")
        hecho = ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") in {"ok", "sin_boletin"}
        if d.weekday() >= 5 and not hecho:
            escribir_json(ruta, {"fecha": d.isoformat(), "resultado": "sin_boletin", "nota": "fin de semana", "alertas": []})
            hecho = True
        if not hecho:
            if max_minutos and (time.monotonic() - inicio) / 60 > max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                break
            time.sleep(pausa)
            try:
                inf = procesar_dia(d, raiz, archivo)
            except ConnectionError as e:
                inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            escribir_json(ruta, inf)
            informes.append(inf)
            print(f"BOPPO {d}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            if freno.anotar(inf):
                break
        d -= timedelta(days=1)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"BOPPO histórico: {len(informes)} días, {sum(i.get('empleo_publico', 0) for i in informes)} de empleo, "
          f"{len(alertas)} alertas")
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--historico", action="store_true", help="días anteriores por la ficha de cada boletín")
    p.add_argument("--desde", type=date.fromisoformat, default=INICIO)
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    if a.historico:
        ayer = datetime.now(MADRID).date() - timedelta(days=1)
        return historico(a.salida, archivo, a.desde, ayer, a.pausa, a.max_minutos)
    try:
        inf = procesar_portada(a.salida, archivo)
    except ConnectionError as e:
        inf = {"fecha": None, "resultado": "fuente_inaccesible", "alertas": [str(e)]}
    print(f"BOPPO {inf.get('fecha')}: {inf['resultado']} {inf.get('empleo_publico', '')} {'; '.join(inf['alertas'])}")
    return 1 if inf["resultado"] in {"error_formato", "fuente_inaccesible", "error_http"} else 0


if __name__ == "__main__":
    sys.exit(main())
