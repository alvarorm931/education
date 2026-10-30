"""Conector del Boletín Oficial da Provincia de Pontevedra (BOPPO): boletín del día, solo títulos.

Formato verificado el 30/10/2026 desde GitHub:
  - La portada https://boppo.depo.gal/es trae el sumario completo del último boletín: «BOPPO número 209 · jueves
    29 de octubre de 2026», administración (h4.tit), organismo (p.Org), entidad (span.pub) y título (p.sumario).
  - robots.txt prohíbe las fichas (/web/boppo/detalle/-/boppo/), las descargas (/bop-v2-portlet/) y todo PDF: no
    se pide nada de eso; se anota la dirección de la ficha. El buscador por fechas es un formulario con
    sesión: no se usa. Por eso solo se lee el boletín del día, cada día.

Uso:
  python -m motor.provinciales.boppontevedra --salida ruta/
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from datetime import date
from pathlib import Path

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import clasificar, convocante_de_organismo, es_empleo_estricto, escribir_json, escribir_jsonl
from motor.boe.clasificar import normalizar
from motor.extraccion.texto_es import fecha_texto
from motor.http import obtener

FUENTE = "boppontevedra"
SIGLAS = "BOP-PONTEVEDRA"
WEB = "https://boppo.depo.gal"
PORTADA = WEB + "/es"
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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    try:
        inf = procesar_portada(a.salida, archivo)
    except ConnectionError as e:
        inf = {"fecha": None, "resultado": "fuente_inaccesible", "alertas": [str(e)]}
    print(f"BOPPO {inf.get('fecha')}: {inf['resultado']} {inf.get('empleo_publico', '')} {'; '.join(inf['alertas'])}")
    return 1 if inf["resultado"] in {"error_formato", "fuente_inaccesible", "error_http"} else 0


if __name__ == "__main__":
    sys.exit(main())
