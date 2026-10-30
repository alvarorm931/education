"""Conector del Boletín Oficial de la Provincia de Castellón (portal JSF/PrimeFaces con sesión).

Formato verificado el 30/10/2026 desde GitHub (sonda motor/provinciales/sonda_castellon.py):
  - https://bop.dipcas.es/PortalBOP/buscador/ trae el sumario del último boletín («Sumario BOP Nº 131», «29/10/2026»)
    y un carrusel con los 32 últimos boletines (enlaces de PrimeFaces busquedaBoletinesForm:j_idt74:N:j_idt75).
  - Pulsar un boletín del carrusel (petición AJAX con la sesión y el ViewState) devuelve el formulario con su sumario.
  - Sumario: sección (cabecera del acordeón, bilingüe), grupo (span.titulo2 «Ajuntaments / Ayuntamientos»), entidad
    (span.titulo3 «AJUNTAMENT D'ALMASSORA») y cada anuncio (span.titulo4) con su PDF (api/descargarAnuncio?idAnuncio=N).
  - Solo se llega a los boletines del carrusel (unos dos meses y medio): el histórico crece desde que se conecta.
  - robots.txt no responde; se lee como boletín oficial (motor/http.py, decisión del 30/10/2026).

Uso:
  python -m motor.provinciales.bopcastellon --salida ruta/
  python -m motor.provinciales.bopcastellon --textos --max-minutos 30 --salida ruta/
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import requests

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (Freno, clasificar, convocante_de_organismo, es_empleo_estricto, escribir_json,
                                     escribir_jsonl)
from motor.boe.clasificar import normalizar
from motor.http import obtener
from motor.provinciales.comun import descargar_textos_pdf
from motor.provinciales.sonda_dival import campos_formulario

FUENTE = "bopcastellon"
SIGLAS = "BOP-CASTELLON"
WEB = "https://bop.dipcas.es"
BUSCADOR = WEB + "/PortalBOP/buscador/"
NOMBRES = ("Boletín Oficial de la Provincia de Castellón", "Butlletí Oficial de la Província de Castelló")

RE_CABECERA = re.compile(r"Sumario BOP N\S*\s*(?P<n>\d+)</label>.*?<label[^>]*>\s*(?P<d>\d{2})/(?P<m>\d{2})/(?P<a>\d{4})\s*</label>",
                         re.DOTALL)
RE_TOKEN = re.compile(r'ui-accordion-header[^>]*>(?:<span[^>]*></span>)?(?P<sec>[^<]+)</div>'
                      r'|<span class="titulo2">(?P<t2>[^<]*)</span>|<span class="titulo3">(?P<t3>[^<]*)</span>'
                      r'|descargarAnuncio\?idAnuncio=(?P<id>\d+)[^"]*".*?<span class="titulo4">(?P<tit>.*?)</span>', re.DOTALL)
RE_CARRUSEL = re.compile(r'<a id="(?P<src>busquedaBoletinesForm:j_idt\d+:(?P<i>\d+):j_idt\d+)"[^>]*>\s*<table[^>]*>.*?'
                         r'N\S*\s*(?P<n>\d+)</span>.*?<span class="text">\s*\w+\s+(?P<d>\d{1,2})</span>.*?'
                         r'<span class="text">\s*(?P<m>\w+)</span>.*?<span class="text">\s*(?P<a>\d{4})</span>', re.DOTALL)
RE_VIEWSTATE = re.compile(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"|ViewState:\d+"><!\[CDATA\[([^\]]+)\]\]>')


def _t(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).replace("\xa0", " ").split())


def _castellano(s: str | None) -> str | None:
    """«Ajuntaments / Ayuntamientos» -> «Ayuntamientos» (el texto bilingüe lleva el castellano detrás)."""
    return s.split(" / ", 1)[1].strip() if s and " / " in s else s


def parsear_sumario(h: str) -> dict:
    c = RE_CABECERA.search(h)
    seccion = grupo = entidad = None
    anuncios = []
    for m in RE_TOKEN.finditer(h, c.end() if c else 0):
        if m.group("sec") is not None:
            seccion, grupo, entidad = _castellano(_t(m.group("sec"))), None, None
        elif m.group("t2") is not None:
            grupo, entidad = _castellano(_t(m.group("t2"))), None
        elif m.group("t3") is not None:
            entidad = _t(m.group("t3"))
        else:
            anuncios.append({"numero_anuncio": m.group("id"), "seccion": seccion, "grupo": grupo, "entidad": entidad,
                             "titulo": _t(m.group("tit")),
                             "url_pdf": f"{WEB}/PortalBOP/api/descargarAnuncio?idAnuncio={m.group('id')}&idioma=es"})
    return {"numero": int(c.group("n")) if c else None,
            "fecha": f"{c.group('a')}-{c.group('m')}-{c.group('d')}" if c else None, "anuncios": anuncios}


MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
         "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}


def carrusel(h: str) -> list[dict]:
    out = []
    for m in RE_CARRUSEL.finditer(h):
        mes = MESES.get(normalizar(m.group("m")))
        if mes:
            out.append({"fuente_jsf": html.unescape(m.group("src")), "numero": int(m.group("n")),
                        "fecha": date(int(m.group("a")), mes, int(m.group("d"))).isoformat()})
    return out


def es_local(x: dict) -> bool:
    return "administracion local" in normalizar(x.get("seccion") or "")


def convocante(x: dict) -> dict | None:
    g = normalizar(x.get("grupo") or "")
    if g.startswith("diputacion"):
        c = convocante_de_organismo("Diputación Provincial de Castellón")
        if c:
            c["organismo"] = f"Diputación Provincial de Castellón - {x['entidad']}" if x.get("entidad") else c["organismo"]
        return c
    c = convocante_de_organismo(x.get("entidad") or x.get("grupo") or "")
    if c and not c.get("provincia"):
        c["provincia"] = "Castellón"
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


def _ruta(raiz: Path, carpeta: str, fecha: str, numero: int, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / fecha[:4] / fecha[5:7] / f"{fecha[8:10]}-{numero:03d}.{ext}"


def guardar(s: dict, contenido: bytes, url: str, raiz: Path, archivo: Archivo, cabeceras: dict) -> dict:
    captura = archivo.guardar(FUENTE, date.fromisoformat(s["fecha"]), contenido, url, "html", 200, cabeceras)
    filas = [{**x, "id": f"BOPCASTELLON-{x['numero_anuncio']}", "fecha": s["fecha"], "boletin": s["numero"],
              "fuente": SIGLAS, "captura_sha256": captura["sha256"]} for x in s["anuncios"]]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", s["fecha"], s["numero"]), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", s["fecha"], s["numero"]), empleo)
    inf = {"fecha": s["fecha"], "numero": s["numero"], "resultado": "ok", "sha256": captura["sha256"],
           "disposiciones": len(filas), "empleo_publico": len(empleo),
           "alertas": [] if filas else [f"BOP Castellón {s['numero']}: sumario sin anuncios (posible cambio de formato)"]}
    escribir_json(_ruta(raiz, "boletines", s["fecha"], s["numero"], "json"), inf)
    return inf


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    p.add_argument("--textos", action="store_true", help="descargar los PDF de los anuncios de empleo")
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    if a.textos:
        # El servicio responde 500 si se pide «application/pdf»: lo sirve como application/octet-stream
        hechos, errores, pendientes = descargar_textos_pdf(_base(a.salida), FUENTE, archivo, a.max_minutos, a.pausa,
                                                           accept="*/*")
        print(f"BOP Castellón textos: {hechos} descargados, {errores} errores, {pendientes} pendientes")
        return 0
    sesion = requests.Session()
    try:
        r = obtener(BUSCADOR, accept="text/html", sesion=sesion)
    except (ConnectionError, TimeoutError) as e:
        print(f"BOP Castellón: fuente inaccesible ({e})")
        return 1
    h = r.contenido.decode("utf-8", errors="replace")
    s = parsear_sumario(h)
    if r.status != 200 or not s["fecha"]:
        print("::warning::BOP Castellón: el buscador no trae el sumario del último boletín (posible cambio de formato)")
        return 1
    informes = [guardar(s, r.contenido, BUSCADOR, a.salida, archivo, r.cabeceras)]
    print(f"BOP Castellón {s['numero']} {s['fecha']}: ok {informes[0]['empleo_publico']}")
    try:
        accion, base_campos = campos_formulario(h, "busquedaBoletinesForm")
    except AttributeError:
        print("::warning::BOP Castellón: sin formulario del carrusel (posible cambio de formato)")
        return 1
    url_post = urljoin(r.url, accion)
    viewstate = base_campos.get("javax.faces.ViewState")
    inicio, freno = time.monotonic(), Freno()
    for b in carrusel(h):
        if (b["fecha"], b["numero"]) == (s["fecha"], s["numero"]) or not viewstate:
            continue
        ruta = _ruta(a.salida, "boletines", b["fecha"], b["numero"], "json")
        if ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") == "ok":
            continue
        if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
            break
        time.sleep(a.pausa)
        campos = {**base_campos, "javax.faces.ViewState": viewstate,
                  "javax.faces.partial.ajax": "true", "javax.faces.source": b["fuente_jsf"],
                  "javax.faces.partial.execute": b["fuente_jsf"], "javax.faces.partial.render": "busquedaBoletinesForm",
                  b["fuente_jsf"]: b["fuente_jsf"]}
        try:
            r2 = obtener(url_post, accept="application/xml", sesion=sesion, formulario=campos,
                         cabeceras_extra={"Faces-Request": "partial/ajax", "X-Requested-With": "XMLHttpRequest",
                                          "Referer": BUSCADOR})
        except (ConnectionError, TimeoutError) as e:
            inf = {**b, "resultado": "fuente_inaccesible", "alertas": [str(e)]}
        else:
            x = r2.contenido.decode("utf-8", errors="replace")
            nuevo = RE_VIEWSTATE.search(x)
            if nuevo:
                viewstate = nuevo.group(1) or nuevo.group(2)
            sb = parsear_sumario(x)
            if r2.status == 200 and (sb["fecha"], sb["numero"]) == (b["fecha"], b["numero"]):
                inf = guardar(sb, r2.contenido, f"{BUSCADOR}#{b['numero']}-{b['fecha']}", a.salida, archivo,
                              r2.cabeceras)
            else:
                inf = {**b, "resultado": "error_formato", "status": r2.status,
                       "alertas": [f"BOP Castellón {b['numero']}: la respuesta es del boletín {sb['numero']} {sb['fecha']}"]}
                escribir_json(ruta, inf)
        informes.append(inf)
        print(f"BOP Castellón {b['numero']} {b['fecha']}: {inf['resultado']} {inf.get('empleo_publico', '')}")
        if freno.anotar(inf):
            break
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Boletines procesados: {len(informes)}. Alertas: {len(alertas)}")
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
