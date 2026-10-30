"""Conector del Boletín Oficial de Gipuzkoa (BOG).

Formato verificado el 30/10/2026 desde GitHub:
  - Sumario de un día, en castellano: https://egoitza.gipuzkoa.eus/gao-bog/castell/bog/AAAA/MM/DD/bcAAMMDD.htm
    (estático; 404 si ese día no hay boletín). Cabecera «Boletín 03-01-2022, Número 1».
  - Por sección (li.seccion «3. ADMINISTRACIÓN LOCAL»), organismo (li.organismo «AYUNTAMIENTO DE IRUN») y anuncio
    (div.titulo_anuncio) con su texto en HTML (cNNNNNNN.htm, div#cuerpoAnuncio) y en PDF.
  - El boletín del día sale por la mañana: antes, la página del día da 404 (no se anota y se vuelve a mirar).
  - robots.txt solo cierra buscadores y portlets del portal, no /gao-bog/.

Uso:
  python -m motor.provinciales.bopgipuzkoa --salida ruta/                                  # ayer y hoy
  python -m motor.provinciales.bopgipuzkoa --desde 2022-01-01 --max-minutos 30 --salida ruta/
  python -m motor.provinciales.bopgipuzkoa --textos --max-minutos 30 --salida ruta/
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
from motor.limpieza import RE_DOCUMENTO, limpiar_html, texto_de
from motor.extraccion.citas import citas
from motor.provinciales.comun import CON_TEXTO

FUENTE = "bopgipuzkoa"
SIGLAS = "BOG"
MADRID = ZoneInfo("Europe/Madrid")
BASE = "https://egoitza.gipuzkoa.eus/gao-bog/castell/bog/"
NOMBRES = ("Boletín Oficial de Gipuzkoa",)

RE_CABECERA = re.compile(r"<h2>\s*Bolet[ií]n\s+(?P<d>\d{2})-(?P<m>\d{2})-(?P<a>\d{4}),&nbsp;N[úu]mero&nbsp;(?P<n>\d+)")
RE_TOKEN = re.compile(r'<li class="seccion">\s*<p>(?P<sec>.*?)</p>|<li class="organismo">\s*<a name="\d+">(?P<org>.*?)</a>'
                      r'|<div class="titulo_anuncio">(?P<tit>.*?)</div>\s*<div class="enlace_html">\s*<a [^>]*href="'
                      r'(?:\.\./)+castell/bog/(?P<ruta>\d{4}/\d{2}/\d{2}/(?P<id>c\d+))\.htm"', re.DOTALL)


def url_dia(d: date) -> str:
    return f"{BASE}{d:%Y/%m/%d}/bc{d:%y%m%d}.htm"


def _t(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).replace("\xa0", " ").split())


def parsear_dia(contenido: bytes) -> dict:
    h = contenido.decode("iso-8859-15", errors="replace")
    c = RE_CABECERA.search(h)
    seccion = organismo = None
    anuncios = []
    for m in RE_TOKEN.finditer(h, c.end() if c else 0):
        if m.group("sec") is not None:
            seccion, organismo = re.sub(r"^\d+\.\s*", "", _t(m.group("sec"))), None
        elif m.group("org") is not None:
            organismo = _t(m.group("org"))
        else:
            anuncios.append({"numero_anuncio": m.group("id"), "seccion": seccion, "organismo": organismo,
                             "titulo": _t(m.group("tit")), "url_html": f"{BASE}{m.group('ruta')}.htm",
                             "url_pdf": f"{BASE}{m.group('ruta')}.pdf"})
    return {"numero": c.group("n") if c else None,
            "fecha": f"{c.group('a')}-{c.group('m')}-{c.group('d')}" if c else None, "anuncios": anuncios}


def es_local(x: dict) -> bool:
    return "administracion local" in normalizar(x.get("seccion") or "")


def convocante(x: dict) -> dict | None:
    c = convocante_de_organismo(x.get("organismo") or "")
    if c:
        c["provincia"] = "Gipuzkoa"
    return c


def seleccionar(filas: list[dict]) -> list[dict]:
    out = []
    for x in filas:
        if not es_empleo_estricto(x["titulo"]):
            continue
        local, sec = es_local(x), normalizar(x.get("seccion") or "")
        ambito = "local" if local else "foral" if "territorio historico" in sec else "otro"
        out.append({**x, "ambito": ambito, **clasificar(x["titulo"]),
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
    if r.status == 404:
        inf["resultado"] = "sin_boletin"
        return inf
    if r.status != 200:
        inf["resultado"] = "error_http"
        inf["alertas"].append(f"BOG {d}: HTTP {r.status}")
        return inf
    s = parsear_dia(r.contenido)
    if s["fecha"] != d.isoformat():
        inf["resultado"] = "error_formato"
        inf["alertas"].append(f"BOG {d}: la página dice {s['fecha']}")
        return inf
    captura = archivo.guardar(FUENTE, d, r.contenido, url, "html", r.status, r.cabeceras)
    filas = [{**x, "id": f"BOG-{x['numero_anuncio']}", "fecha": d.isoformat(), "boletin": s["numero"], "fuente": SIGLAS,
              "captura_sha256": captura["sha256"]} for x in s["anuncios"]]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    inf.update({"resultado": "ok", "numero": s["numero"], "sha256": captura["sha256"], "disposiciones": len(filas),
                "empleo_publico": len(empleo)})
    if not filas:
        inf["alertas"].append(f"BOG {d}: sumario sin anuncios (posible cambio de formato)")
    return inf


# Anuncios que el BOG publica solo en PDF: la página HTML no trae el texto, solo este aviso (174 textos así en la rama
# de datos el 30/10/2026). Su texto se toma del PDF del anuncio.
RE_SOLO_PDF = re.compile(r"(?i)anuncio publicado (?:[uú]nicamente|solamente) en formato pdf|pdf formatuan bakarrik")


def texto_disposicion(contenido: bytes, x: dict | None = None) -> dict:
    """Texto limpio del anuncio. En nombramientos, listas y resultados (tipos fuera de CON_TEXTO) no se guarda el
    texto, que nombra a las personas: solo se cuentan las líneas con documento de identidad."""
    h = contenido.decode("iso-8859-15", errors="replace")
    i = h.find('<div id="cuerpoAnuncio"')
    if i < 0:
        raise ValueError("sin div#cuerpoAnuncio: posible cambio de formato")
    j = h.rfind("</body>")
    cuerpo = h[i:j if j > i else None]
    if RE_SOLO_PDF.search(texto_de(cuerpo)) and len(texto_de(cuerpo)) < 400:
        return {"titulo": None, "texto": "", "tablas": [], "solo_pdf": True}
    if x is not None and x.get("tipo_acto") not in CON_TEXTO:
        lineas = [texto_de(b) for b in re.split(r"</(?:p|tr|li)>", cuerpo)]
        return {"titulo": None, "texto": None, "tablas": [], "solo_recuento": True,
                "lineas_con_documento_de_identidad": sum(1 for l in lineas if RE_DOCUMENTO.search(l)),
                "citas": citas("\n".join(lineas))}
    return {"titulo": None, **limpiar_html(cuerpo)}


def ruta_texto(raiz: Path, x: dict) -> Path:
    return _base(raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"


def textos_pendientes(raiz: Path) -> list[dict]:
    lista = []
    for f in sorted((_base(raiz) / "oposiciones").glob("*/*/*.jsonl"), reverse=True):
        lista += [x for x in leer_jsonl(f) if x.get("url_html") and not ruta_texto(raiz, x).exists()]
    return sorted(lista, key=lambda x: (0 if x.get("tipo_acto") in CON_TEXTO else 1,
                                        0 if x.get("alcance") in (None, "acceso") else 1))


def textos_solo_pdf(raiz: Path) -> list[dict]:
    """Anuncios con el texto guardado desde la página HTML que solo traía el aviso de «publicado únicamente en
    formato pdf» y con PDF: se vuelven a hacer desde el PDF."""
    lista = []
    for f in sorted((_base(raiz) / "oposiciones").glob("*/*/*.jsonl"), reverse=True):
        for x in leer_jsonl(f):
            r = ruta_texto(raiz, x)
            if not x.get("url_pdf") or not r.exists():
                continue
            d = json.loads(r.read_text(encoding="utf-8"))
            if not d.get("desde_pdf") and (d.get("solo_pdf") or RE_SOLO_PDF.search(d.get("texto") or "")):
                lista.append(x)
    return lista


def texto_pdf_anuncio(contenido: bytes, x: dict) -> dict:
    from motor.provinciales.comun import texto_pdf
    return {**texto_pdf(contenido, x.get("tipo_acto") in CON_TEXTO), "titulo": None, "desde_pdf": True}


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
        hechos, errores = descargar_textos(pend, lambda x: ruta_texto(a.salida, x), lambda x: x["url_html"],
                                           texto_disposicion, archivo, FUENTE, a.max_minutos, a.pausa,
                                           accept="text/html", ext="html", por_registro=True)
        print(f"BOG textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        solo_pdf = textos_solo_pdf(a.salida)
        hechos, errores = descargar_textos(solo_pdf, lambda x: ruta_texto(a.salida, x), lambda x: x["url_pdf"],
                                           texto_pdf_anuncio, archivo, FUENTE, a.max_minutos, a.pausa,
                                           accept="application/pdf", ext="pdf", por_registro=True)
        print(f"BOG textos desde el PDF: {hechos} hechos, {errores} errores, {len(solo_pdf) - hechos} pendientes")
        return 0
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
            print(f"BOG {d}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            time.sleep(a.pausa)
        d -= timedelta(days=1)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
