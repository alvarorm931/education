"""Conector del Boletín Oficial de Bizkaia (BOB).

Formato verificado el 30/10/2026 desde GitHub:
  - Portada https://www.bizkaia.eus/es/bob: enlace al último boletín (a#_IYBIWBCC_last-boletin-title) con su fecha y
    número en la dirección (_IYBIWBCC_bdate=AAAAMMDD&_IYBIWBCC_bnum=N).
  - Boletín: /es/bob/resultados?…&_IYBIWBCC_mvcRenderCommandName=%2Fdetail&_IYBIWBCC_bdate=AAAAMMDD&_IYBIWBCC_bnum=N.
    Fecha y número tienen que casar (si no, la página sale vacía). Trae el anterior y el siguiente (número y fecha),
    y por anuncio la sección (h3 «Administración Local del Territorio Histórico de Bizkaia»), el emisor (h4, que vale
    para los anuncios siguientes hasta el próximo), el resumen y el PDF (/lehendakaritza/Bao_bob/AAAA/MM/DD/I-NNNN_cas.pdf).
  - Para recorrer el histórico se baja de un boletín al anterior; lo ya leído no se vuelve a pedir (su anterior queda
    anotado), así que cada ejecución sigue donde lo dejó la anterior.
  - robots.txt deja leer los sumarios; cierra la carpeta de los PDF (Bao_bob), que por ahora no se descargan.

Uso:
  python -m motor.provinciales.bopbizkaia --salida ruta/                                  # lo nuevo
  python -m motor.provinciales.bopbizkaia --desde 2022-01-01 --max-minutos 30 --salida ruta/
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

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (Freno, clasificar, convocante_de_organismo, es_empleo_estricto, escribir_json,
                                     escribir_jsonl)
from motor.boe.clasificar import normalizar
from motor.extraccion.texto_es import fecha_texto
from motor.http import obtener

FUENTE = "bopbizkaia"
SIGLAS = "BOB"
WEB = "https://www.bizkaia.eus"
PORTADA = WEB + "/es/bob"
NOMBRES = ("Boletín Oficial de Bizkaia",)
PRIMERO = {"fecha": "2022-01-03", "numero": 1}

RE_ULTIMO = re.compile(r"_IYBIWBCC_bdate=(\d{4})(\d{2})(\d{2})&(?:amp;)?_IYBIWBCC_bnum=(\d+)")
RE_CABECERA = re.compile(r"<h1>\s*Bolet[íi]n\s+(\d+)\s*</h1>\s*<p class=\"bibob_fecharesult\">\s*\w+,\s*(\d{1,2}) de (\w+) de (\d{4})")
RE_VECINO = re.compile(r'id="_IYBIWBCC_boletin-(anterior|siguiente)-detail"[^>]*>\s*Bolet[íi]n\s+(\d+)\s*<span>\s*\w+,\s*'
                       r"(\d{1,2}) de (\w+) de (\d{4})")
RE_TOKEN = re.compile(r"<h3>(?P<sec>[^<]*)</h3>|<h4 id=\"emisorEntidad[\d-]+\">(?P<ent>.*?)</h4>"
                      r'|<p id="emisorResumen[\d-]+">(?P<res>.*?)</p>\s*</div>\s*<div class="col-2[^"]*">.*?'
                      r'<a href="(?P<pdf>[^"]+\.pdf)"', re.DOTALL)
RE_PDF = re.compile(r"/(\d{4})/\d{2}/\d{2}/([A-Z]+-\d+)_cas\.pdf$")


def url_boletin(fecha: str, numero: int) -> str:
    return (f"{WEB}/es/bob/resultados?p_p_id=IYBIWBCC&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view"
            f"&_IYBIWBCC_mvcRenderCommandName=%2Fdetail&_IYBIWBCC_bdate={fecha.replace('-', '')}&_IYBIWBCC_bnum={numero}")


def _t(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).replace("\xa0", " ").split())


def ultimo(contenido: bytes) -> dict | None:
    h = contenido.decode("utf-8", errors="replace")
    i = h.find("last-boletin-title")
    m = RE_ULTIMO.search(h, max(i, 0))
    return {"fecha": f"{m.group(1)}-{m.group(2)}-{m.group(3)}", "numero": int(m.group(4))} if m else None


def parsear_boletin(contenido: bytes) -> dict:
    h = contenido.decode("utf-8", errors="replace")
    c = RE_CABECERA.search(h)
    vecinos = {m.group(1): {"numero": int(m.group(2)), "fecha": fecha_texto(m.group(3), m.group(4), m.group(5))}
               for m in RE_VECINO.finditer(h)}
    i = h.find("listado-resultados")
    seccion = entidad = None
    anuncios = []
    for m in RE_TOKEN.finditer(h, max(i, 0)) if i >= 0 else []:
        if m.group("sec") is not None:
            seccion, entidad = _t(m.group("sec")), None
        elif m.group("ent") is not None:
            entidad = _t(m.group("ent"))
        else:
            pdf = html.unescape(m.group("pdf"))
            p = RE_PDF.search(pdf)
            anuncios.append({"numero_anuncio": f"{p.group(1)}-{p.group(2)}" if p else pdf.rsplit("/", 1)[-1],
                             "seccion": seccion, "entidad": entidad, "titulo": _t(m.group("res")), "url_pdf": pdf})
    return {"numero": int(c.group(1)) if c else None,
            "fecha": fecha_texto(c.group(2), c.group(3), c.group(4)) if c else None,
            "anterior": vecinos.get("anterior"), "siguiente": vecinos.get("siguiente"), "anuncios": anuncios}


LOCALES = ("ayuntamiento", "mancomunidad", "consorcio", "junta administrativa", "concejo", "diputacion foral")


def es_local(x: dict) -> bool:
    return ("administracion local" in normalizar(x.get("seccion") or "")
            or normalizar(x.get("entidad") or "").startswith(LOCALES[:5]))


def convocante(x: dict) -> dict | None:
    c = convocante_de_organismo(x.get("entidad") or "")
    if c and not c.get("provincia"):
        c["provincia"] = "Bizkaia"
    return c


def seleccionar(filas: list[dict]) -> list[dict]:
    out = []
    for x in filas:
        if not es_empleo_estricto(x["titulo"]):
            continue
        local, sec = es_local(x), normalizar(x.get("seccion") or "")
        ambito = "local" if local else "foral" if "foral" in sec else "otro"
        out.append({**x, "ambito": ambito, **clasificar(x["titulo"]), "convocante": convocante(x) if local else None})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "provinciales" / FUENTE


def _ruta(raiz: Path, carpeta: str, b: dict, ext: str = "jsonl") -> Path:
    f = b["fecha"]
    return _base(raiz) / carpeta / f[:4] / f[5:7] / f"{f[8:10]}-{b['numero']:03d}.{ext}"


def procesar_boletin(b: dict, raiz: Path, archivo: Archivo) -> dict:
    url = url_boletin(b["fecha"], b["numero"])
    r = obtener(url, accept="text/html")
    inf = {**b, "status": r.status, "alertas": []}
    if r.status != 200:
        inf["resultado"] = "error_http"
        inf["alertas"].append(f"BOB {b['numero']} {b['fecha']}: HTTP {r.status}")
        return inf
    s = parsear_boletin(r.contenido)
    if (s["fecha"], s["numero"]) != (b["fecha"], b["numero"]):
        inf["resultado"] = "error_formato"
        inf["alertas"].append(f"BOB {b['numero']} {b['fecha']}: la página dice {s['numero']} {s['fecha']}")
        return inf
    captura = archivo.guardar(FUENTE, date.fromisoformat(b["fecha"]), r.contenido, url, "html", r.status, r.cabeceras)
    filas = [{**x, "id": f"BOB-{x['numero_anuncio']}", "fecha": b["fecha"], "boletin": b["numero"], "url_boletin": url,
              "fuente": SIGLAS, "captura_sha256": captura["sha256"]} for x in s["anuncios"]]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", b), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", b), empleo)
    inf.update({"resultado": "ok", "sha256": captura["sha256"], "anterior": s["anterior"], "siguiente": s["siguiente"],
                "disposiciones": len(filas), "empleo_publico": len(empleo)})
    if not filas:
        inf["alertas"].append(f"BOB {b['numero']} {b['fecha']}: boletín sin anuncios (posible cambio de formato)")
    return inf


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=date.fromisoformat, default=None,
                   help="hasta qué fecha bajar en el histórico (sin ella, solo lo nuevo hasta el último ya leído)")
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    try:
        r = obtener(PORTADA, accept="text/html")
        actual = ultimo(r.contenido) if r.status == 200 else None
    except (ConnectionError, TimeoutError) as e:
        print(f"BOB: fuente inaccesible ({e})")
        return 1
    if not actual:
        print("::warning::BOB: la portada no enlaza el último boletín (posible cambio de formato)")
        return 1
    tope = (a.desde or date.min).isoformat()
    inicio, informes, freno, vistos = time.monotonic(), [], Freno(), 0
    while actual and actual["fecha"] >= tope:
        ruta = _ruta(a.salida, "boletines", actual, "json")
        previo = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
        if previo.get("resultado") == "ok":
            if a.desde is None:
                break  # sin --desde basta con llegar a lo ya leído
            actual, vistos = previo.get("anterior"), vistos + 1
            continue
        if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
            print("Tiempo agotado; se continúa en la siguiente ejecución")
            break
        time.sleep(a.pausa)
        try:
            inf = procesar_boletin(actual, a.salida, archivo)
        except (ConnectionError, TimeoutError) as e:
            inf = {**actual, "resultado": "fuente_inaccesible", "alertas": [str(e)]}
        escribir_json(ruta, inf)
        informes.append(inf)
        print(f"BOB {actual['numero']} {actual['fecha']}: {inf['resultado']} {inf.get('disposiciones', '')} anuncios, "
              f"{inf.get('empleo_publico', '')} de empleo")
        if freno.anotar(inf) or inf["resultado"] != "ok":
            break  # sin el boletín no se sabe cuál es el anterior: se reintenta en la próxima ejecución
        actual = inf.get("anterior")
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Boletines leídos: {len(informes)} (ya estaban: {vistos}). Alertas: {len(alertas)}")
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
