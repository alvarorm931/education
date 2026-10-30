"""Conector del Boletín Oficial de la Provincia de Burgos (BOPBUR).

Formato verificado el 30/10/2026 desde el servidor de España (desde GitHub no responde):
  - Boletín por número: http://bopbur.diputaciondeburgos.es/bopbur-AAAA-NNN (correlativo en el año); cabecera
    «núm. 206» y «jueves, 29 de octubre de 2026». La hemeroteca por día (/hemeroteca/AAAA-MM-DD) enlaza al boletín.
  - Sumario anidado: sección (h2 «III. Administración Local»), entidad (h3 «Ayuntamiento de Hontoria del Pinar»),
    órgano (h4) y, por anuncio, el asunto (p) y su PDF («Anuncio 202604609 (BOPBUR-2026-04609 …)»).
  - Empleo público: por el asunto (filtro estricto).

Uso:
  python -m motor.provinciales.bopburgos --salida ruta/                                  # año en curso, lo que falte
  python -m motor.provinciales.bopburgos --desde-anio 2022 --max-minutos 30 --salida ruta/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (Freno, clasificar, convocante_de_organismo, es_empleo_estricto, escribir_json,
                                     escribir_jsonl)
from motor.boe.clasificar import normalizar
from motor.extraccion.texto_es import fecha_texto
from motor.http import obtener
from motor.limpieza import texto_de

FUENTE = "bopburgos"
SIGLAS = "BOP-BURGOS"
MADRID = ZoneInfo("Europe/Madrid")
BASE = "http://bopbur.diputaciondeburgos.es"
NOMBRES = ("Boletín Oficial de la Provincia de Burgos",)

RE_CABECERA = re.compile(r'class="title-number"><a [^>]*>\s*n[úu]m\.\s*(?P<n>\d+)\s*</a>.*?class="title-date"><a [^>]*>'
                         r"\s*\w+,\s*(?P<d>\d{1,2}) de (?P<m>\w+) de (?P<a>\d{4})", re.DOTALL)
RE_TOKEN = re.compile(r"<h2>(?P<h2>.*?)</h2>|<h3>(?P<h3>.*?)</h3>|<h4>(?P<h4>.*?)</h4>"
                      r'|<li id="bopbur-anuncio-(?P<id>\d+)"[^>]*>(?P<li>.*?)</li>', re.DOTALL)


def url_boletin(anio: int, numero: int) -> str:
    return f"{BASE}/bopbur-{anio}-{numero:03d}"


def cabecera(html: str) -> tuple[int | None, str | None]:
    m = RE_CABECERA.search(html)
    return (int(m.group("n")), fecha_texto(m.group("d"), m.group("m"), m.group("a"))) if m else (None, None)


def parsear_boletin(html: str) -> list[dict]:
    seccion = entidad = organo = None
    out = []
    for t in RE_TOKEN.finditer(html):
        if t.group("h2") is not None:
            seccion, entidad, organo = texto_de(t.group("h2")), None, None
        elif t.group("h3") is not None:
            entidad, organo = texto_de(t.group("h3")), None
        elif t.group("h4") is not None:
            organo = texto_de(t.group("h4"))
        else:
            li = t.group("li")
            titulo = re.search(r"<p>(.*?)</p>", li, re.DOTALL)
            pdf = re.search(r'href="([^"]+\.pdf)"', li)
            out.append({"numero_anuncio": t.group("id"), "seccion": seccion, "entidad": entidad, "organo": organo,
                        "titulo": texto_de(titulo.group(1)) if titulo else "", "url_pdf": pdf.group(1) if pdf else None})
    return out


def es_local(x: dict) -> bool:
    return "administracion local" in normalizar(x.get("seccion") or "")


def convocante(x: dict) -> dict | None:
    c = convocante_de_organismo(x.get("entidad") or "")
    if c and not c.get("provincia"):
        c["provincia"] = "Burgos"
    if c and c.get("tipo") == "Diputación Provincial":
        c["provincia"] = "Burgos"
    return c


def seleccionar(filas: list[dict]) -> list[dict]:
    out = []
    for x in filas:
        if not es_empleo_estricto(x["titulo"]):
            continue
        local = es_local(x)
        out.append({**x, "ambito": "local" if local else "otro", **clasificar(x["titulo"], x.get("seccion")),
                    "convocante": convocante(x) if local else None})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "provinciales" / FUENTE


def ruta_informe(raiz: Path, anio: int, numero: int) -> Path:
    return _base(raiz) / "boletines" / str(anio) / f"{numero:03d}.json"


def _ruta(raiz: Path, carpeta: str, fecha: str, numero: int) -> Path:
    return _base(raiz) / carpeta / fecha[:4] / fecha[5:7] / f"{fecha[8:10]}-{numero:03d}.jsonl"


def procesar_boletin(anio: int, numero: int, raiz: Path, archivo: Archivo) -> dict:
    url = url_boletin(anio, numero)
    r = obtener(url, accept="text/html")
    inf = {"anio": anio, "numero": numero, "status": r.status, "alertas": []}
    if r.status == 404:
        inf["resultado"] = "sin_boletin"
        return inf
    if r.status != 200:
        inf["resultado"] = "error_http"
        inf["alertas"].append(f"BOP Burgos {anio}/{numero}: HTTP {r.status}")
        return inf
    html = r.contenido.decode("utf-8", errors="replace")
    n, fecha = cabecera(html)
    if n is None:
        inf["resultado"] = "sin_boletin"
        return inf
    if n != numero or not fecha or fecha[:4] != str(anio):
        inf["resultado"] = "error_formato"
        inf["alertas"].append(f"BOP Burgos {anio}/{numero}: la cabecera dice {n} y {fecha}")
        return inf
    captura = archivo.guardar(FUENTE, date.fromisoformat(fecha), r.contenido, url, "html", r.status, r.cabeceras)
    filas = [{**x, "id": f"BOPBURGOS-{x['numero_anuncio']}", "fecha": fecha, "boletin": numero, "fuente": SIGLAS,
              "url_boletin": url, "captura_sha256": captura["sha256"]} for x in parsear_boletin(html)]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", fecha, numero), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", fecha, numero), empleo)
    inf.update({"resultado": "ok", "fecha": fecha, "sha256": captura["sha256"], "disposiciones": len(filas),
                "empleo_publico": len(empleo)})
    if not filas:
        inf["alertas"].append(f"BOP Burgos {anio}/{numero}: boletín sin anuncios (posible cambio de formato)")
    return inf


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde-anio", type=int, default=hoy.year)
    p.add_argument("--hasta-anio", type=int, default=hoy.year)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    inicio, informes, freno = time.monotonic(), [], Freno()
    for anio in range(a.hasta_anio, a.desde_anio - 1, -1):
        fin = _base(a.salida) / "boletines" / str(anio) / "fin.json"
        tope = json.loads(fin.read_text(encoding="utf-8"))["ultimo"] if fin.exists() and anio < hoy.year else 400
        sin, numero = 0, 1
        while numero <= tope:
            ruta = ruta_informe(a.salida, anio, numero)
            if ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") == "ok":
                sin, numero = 0, numero + 1
                continue
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                return _final(informes)
            try:
                inf = procesar_boletin(anio, numero, a.salida, archivo)
            except ConnectionError as e:
                inf = {"anio": anio, "numero": numero, "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            informes.append(inf)
            if inf["resultado"] == "sin_boletin":
                sin += 1
                if sin >= 3:
                    if anio < hoy.year:
                        escribir_json(fin, {"anio": anio, "ultimo": numero - 3})
                    break
            else:
                sin = 0
                escribir_json(ruta, inf)
            if freno.anotar(inf):
                return _final(informes)
            print(f"BOP Burgos {anio}/{numero} {inf.get('fecha', '')}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            numero += 1
            time.sleep(a.pausa)
    return _final(informes)


def _final(informes: list[dict]) -> int:
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Boletines procesados: {len(informes)}. Alertas: {len(alertas)}")
    for x in alertas[:30]:
        print(" -", x)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
