"""Conector del Boletín Oficial de la Provincia de Guadalajara (portal Joomla K2).

Formato verificado el 30/10/2026 desde GitHub (también para 2022):
  - Boletín de un día: la lista por fecha de la categoría «General» (catid=9),
    https://boletin.dguadalajara.es/boletin/index.php/buscar-k2-menu/date/AAAA/MM/DD?catid=9, enlaza su ficha
    («Boletin Oficial de la Provincia de Guadalajara num. 207 de jueves, 29 de Octubre de 2026»).
  - Ficha del boletín: el sumario, con cada anuncio (div.itemSumario): título enlazando a su ficha, entidad
    (p.pTituloCorto «AYUNTAMIENTO DE CIFUENTES») y número (p.codigo_anuncio 2820). El PDF del anuncio es
    /boletin/pdf/pdfAAAA_NNNN.pdf.
  - robots.txt no existe (404): se puede leer todo.

Uso:
  python -m motor.provinciales.bopguadalajara --salida ruta/                                  # ayer y hoy
  python -m motor.provinciales.bopguadalajara --desde 2022-01-01 --max-minutos 30 --salida ruta/
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
                                     escribir_jsonl, estado_dia)
from motor.boe.clasificar import normalizar
from motor.extraccion.texto_es import fecha_texto
from motor.http import obtener
from motor.provinciales.comun import descargar_textos_pdf

FUENTE = "bopguadalajara"
SIGLAS = "BOP-GUADALAJARA"
MADRID = ZoneInfo("Europe/Madrid")
WEB = "https://boletin.dguadalajara.es"
NOMBRES = ("Boletín Oficial de la Provincia de Guadalajara",)

RE_FICHA = re.compile(r'<h2 class="genericItemTitle">\s*<a href="(?P<url>/boletin/index\.php/9-general/[^"]+)">\s*'
                      r"Bolet[ií]n Oficial de la Provincia de Guadalajara n[uú]m\.\s*(?P<n>\d+)\s+de\s+\w+,\s*"
                      r"(?P<d>\d{1,2}) de (?P<m>\w+) de (?P<a>\d{4})", re.IGNORECASE)
RE_ANUNCIO = re.compile(r"<div class='itemSumario'>\s*<h3 class='catItemTitle'>\s*<a href='(?P<url>[^']+)'>(?P<tit>.*?)</a>"
                        r"\s*</h3>\s*<p class='pTituloCorto'>(?P<ent>.*?)</p>.*?<p class=\"codigo_anuncio\">(?P<cod>\d+)</p>",
                        re.DOTALL)


def url_fecha(d: date) -> str:
    return f"{WEB}/boletin/index.php/buscar-k2-menu/date/{d:%Y/%m/%d}?catid=9"


def _t(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).replace("\xa0", " ").split())


def fichas(contenido: bytes) -> list[dict]:
    h = contenido.decode("utf-8", errors="replace")
    return [{"url": WEB + html.unescape(m.group("url")), "numero": m.group("n"),
             "fecha": fecha_texto(m.group("d"), m.group("m"), m.group("a"))} for m in RE_FICHA.finditer(h)]


def sumario(contenido: bytes, anio: int) -> list[dict]:
    h = contenido.decode("utf-8", errors="replace")
    return [{"numero_anuncio": m.group("cod"), "entidad": _t(m.group("ent")), "titulo": _t(m.group("tit")),
             "url_anuncio": WEB + html.unescape(m.group("url")),
             "url_pdf": f"{WEB}/boletin/pdf/pdf{anio}_{m.group('cod')}.pdf"} for m in RE_ANUNCIO.finditer(h)]


NO_LOCALES = ("junta de comunidades", "ministerio", "subdelegacion", "delegacion del gobierno", "confederacion",
              "juzgado", "tribunal", "tesoreria general", "agencia tributaria", "seguridad social", "jefatura",
              "demarcacion", "consejeria")


def es_local(x: dict) -> bool:
    return not normalizar(x.get("entidad") or "").startswith(NO_LOCALES)


def convocante(x: dict) -> dict | None:
    c = convocante_de_organismo(x.get("entidad") or "")
    if c and not c.get("provincia"):
        c["provincia"] = "Guadalajara"
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
    r = obtener(url_fecha(d), accept="text/html")
    inf = {"fecha": d.isoformat(), "status": r.status, "alertas": []}
    if r.status != 200:
        inf["resultado"] = "error_http"
        inf["alertas"].append(f"BOP Guadalajara {d}: HTTP {r.status}")
        return inf
    lista = [f for f in fichas(r.contenido) if f["fecha"] == d.isoformat()]
    if not lista:
        inf["resultado"] = "sin_boletin"
        return inf
    filas, numeros = [], []
    for f in lista:  # el ordinario y, si lo hay, el extraordinario
        time.sleep(pausa)
        rb = obtener(f["url"], accept="text/html")
        if rb.status != 200:
            inf["resultado"] = "error_http"
            inf["alertas"].append(f"BOP Guadalajara {d}: ficha del boletín {f['numero']}: HTTP {rb.status}")
            return inf
        captura = archivo.guardar(FUENTE, d, rb.contenido, f["url"], "html", rb.status, rb.cabeceras)
        numeros.append(f["numero"])
        filas += [{**x, "id": f"BOPGUADALAJARA-{d.year}-{x['numero_anuncio']}", "fecha": d.isoformat(),
                   "boletin": f["numero"], "url_boletin": f["url"], "fuente": SIGLAS,
                   "captura_sha256": captura["sha256"]} for x in sumario(rb.contenido, d.year)]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    inf.update({"resultado": "ok", "numero": ",".join(numeros), "disposiciones": len(filas), "empleo_publico": len(empleo)})
    if not filas:
        inf["alertas"].append(f"BOP Guadalajara {d}: sumario sin anuncios (posible cambio de formato)")
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
        print(f"BOP Guadalajara textos: {hechos} descargados, {errores} errores, {pendientes} pendientes")
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
                inf = procesar_dia(d, a.salida, archivo, a.pausa)
            except (ConnectionError, TimeoutError) as e:
                inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            if not (inf.get("resultado") == "sin_boletin" and d >= hoy - timedelta(days=1)):
                escribir_json(ruta, inf)
            informes.append(inf)
            if freno.anotar(inf, reintento=reintento):
                break
            print(f"BOP Guadalajara {d}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            time.sleep(a.pausa)
        d -= timedelta(days=1)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
