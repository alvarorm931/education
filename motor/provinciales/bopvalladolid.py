"""Conector del Boletín Oficial de la Provincia de Valladolid (se lee desde el servidor de España: desde GitHub no responde).

Formato verificado el 30/10/2026:
  - Días con boletín de un mes: https://bop.sede.diputaciondevalladolid.es/o/BOP-Calendario/CalendarioControl?month=M
    &year=AAAA (JSON con las fechas, también para 2022).
  - Boletín de un día: /ultimobop?p_p_id=BOPVisualizaBoletin_WAR_BOPVisualizaBoletin&p_p_lifecycle=0&p_p_state=normal
    &p_p_mode=view&_BOPVisualizaBoletin_WAR_BOPVisualizaBoletin_fecha=AAAA-MM-DD (sin fecha, o con otro formato, da el
    último). Cabecera «BOLETIN Nº 2026/208» y «29 de octubre de 2026»; por sección (p.titulo_secc_boletin
    «III.-ADMINISTRACIÓN LOCAL») cada anuncio con su entidad (p.bop_tit_articulo) y su asunto enlazando al PDF
    (/boletines/2026/octubre/29/BOPVA-A-2026-03147.pdf).
  - robots.txt lo permite todo.

Uso:
  python -m motor.provinciales.bopvalladolid --salida ruta/                                  # ayer y hoy
  python -m motor.provinciales.bopvalladolid --desde 2022-01-01 --max-minutos 30 --salida ruta/
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

FUENTE = "bopvalladolid"
SIGLAS = "BOP-VALLADOLID"
MADRID = ZoneInfo("Europe/Madrid")
WEB = "https://bop.sede.diputaciondevalladolid.es"
NOMBRES = ("Boletín Oficial de la Provincia de Valladolid",)

RE_CABECERA = re.compile(r'<h1 id="bop_sumario_tit">\s*BOLETIN N\S*\s+(?P<a>\d{4})/(?P<n>\d+)\s*</h1>\s*'
                         r'<h2 id="bop_sumario_tit_fecha">\s*(?P<d>\d{1,2}) de (?P<m>\w+) de (?P<a2>\d{4})')
RE_TOKEN = re.compile(r'<p class="titulo_secc_boletin">(?P<sec>.*?)</p>|<p class="bop_tit_articulo">(?P<ent>.*?)</p>\s*'
                      r'<p class="bop_res_articulo">\s*<a href="(?P<pdf>[^"]+)"[^>]*>(?P<tit>.*?)</a>', re.DOTALL)
RE_CODIGO = re.compile(r"(BOPVA-A-\d{4}-\d+)\.pdf$")


def url_dia(d: date) -> str:
    return (f"{WEB}/ultimobop?p_p_id=BOPVisualizaBoletin_WAR_BOPVisualizaBoletin&p_p_lifecycle=0&p_p_state=normal"
            f"&p_p_mode=view&_BOPVisualizaBoletin_WAR_BOPVisualizaBoletin_fecha={d.isoformat()}")


def url_calendario(anio: int, mes: int) -> str:
    return f"{WEB}/o/BOP-Calendario/CalendarioControl?month={mes}&year={anio}"


def _t(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).replace("\xa0", " ").split())


def parsear_boletin(contenido: bytes) -> dict:
    h = contenido.decode("utf-8", errors="replace")
    c = RE_CABECERA.search(h)
    i = h.find('<div id="listado_anuncios">')
    seccion, anuncios = None, []
    for m in RE_TOKEN.finditer(h, max(i, 0)) if i >= 0 else []:
        if m.group("sec") is not None:
            seccion = _t(m.group("sec"))
        else:
            pdf = html.unescape(m.group("pdf"))
            cod = RE_CODIGO.search(pdf)
            anuncios.append({"numero_anuncio": cod.group(1) if cod else pdf.rsplit("/", 1)[-1], "seccion": seccion,
                             "entidad": _t(m.group("ent")), "titulo": _t(m.group("tit")), "url_pdf": pdf})
    return {"numero": f"{c.group('a')}/{c.group('n')}" if c else None,
            "fecha": fecha_texto(c.group("d"), c.group("m"), c.group("a2")) if c else None, "anuncios": anuncios}


def es_local(x: dict) -> bool:
    return "administracion local" in normalizar(x.get("seccion") or "")


def convocante(x: dict) -> dict | None:
    c = convocante_de_organismo(x.get("entidad") or "")
    if c and not c.get("provincia"):
        c["provincia"] = "Valladolid"
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


def dias_con_boletin(raiz: Path, anio: int, mes: int, hoy: date) -> set[str] | None:
    """Fechas con boletín de ese mes. Los meses ya cerrados se guardan y no se vuelven a pedir."""
    ruta = _base(raiz) / "calendario" / f"{anio}-{mes:02d}.json"
    if ruta.exists():
        return set(json.loads(ruta.read_text(encoding="utf-8")))
    r = obtener(url_calendario(anio, mes), accept="application/json")
    if r.status != 200:
        return None
    try:
        fechas = sorted(json.loads(r.contenido.decode("utf-8")))
    except ValueError:
        return None
    if (anio, mes) < (hoy.year, hoy.month):
        escribir_json(ruta, fechas)
    return set(fechas)


def procesar_dia(d: date, raiz: Path, archivo: Archivo) -> dict:
    url = url_dia(d)
    r = obtener(url, accept="text/html")
    inf = {"fecha": d.isoformat(), "status": r.status, "alertas": []}
    if r.status != 200:
        inf["resultado"] = "error_http"
        inf["alertas"].append(f"BOP Valladolid {d}: HTTP {r.status}")
        return inf
    s = parsear_boletin(r.contenido)
    if s["fecha"] != d.isoformat():
        inf["resultado"] = "error_formato" if s["fecha"] is None else "sin_boletin"
        if s["fecha"] is None:
            inf["alertas"].append(f"BOP Valladolid {d}: página sin cabecera de boletín (posible cambio de formato)")
        return inf
    captura = archivo.guardar(FUENTE, d, r.contenido, url, "html", r.status, r.cabeceras)
    filas = [{**x, "id": x["numero_anuncio"], "fecha": d.isoformat(), "boletin": s["numero"], "url_dia": url,
              "fuente": SIGLAS, "captura_sha256": captura["sha256"]} for x in s["anuncios"]]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    inf.update({"resultado": "ok", "numero": s["numero"], "sha256": captura["sha256"], "disposiciones": len(filas),
                "empleo_publico": len(empleo)})
    if not filas:
        inf["alertas"].append(f"BOP Valladolid {d}: boletín sin anuncios (posible cambio de formato)")
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
        print(f"BOP Valladolid textos: {hechos} descargados, {errores} errores, {pendientes} pendientes")
        return 0
    inicio, informes, freno, meses = time.monotonic(), [], Freno(), {}
    d = a.hasta
    while d >= a.desde:
        ruta = _ruta(a.salida, "dias", d, "json")
        hecho = ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") in {"ok", "sin_boletin"}
        reciente = d >= hoy - timedelta(days=1)
        if not hecho or reciente:
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                break
            clave = (d.year, d.month)
            if clave not in meses:
                try:
                    meses[clave] = dias_con_boletin(a.salida, d.year, d.month, hoy)
                except (ConnectionError, TimeoutError):
                    meses[clave] = None
                time.sleep(a.pausa)
            dias = meses[clave]
            if dias is not None and d.isoformat() not in dias:
                if not reciente:
                    escribir_json(ruta, {"fecha": d.isoformat(), "resultado": "sin_boletin", "nota": "no está en el "
                                         "calendario", "alertas": []})
                d -= timedelta(days=1)
                continue
            try:
                inf = procesar_dia(d, a.salida, archivo)
            except (ConnectionError, TimeoutError) as e:
                inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            if not (inf.get("resultado") == "sin_boletin" and reciente):
                escribir_json(ruta, inf)
            informes.append(inf)
            if freno.anotar(inf):
                break
            print(f"BOP Valladolid {d}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            time.sleep(a.pausa)
        d -= timedelta(days=1)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
