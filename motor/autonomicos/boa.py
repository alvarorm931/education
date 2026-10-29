"""Conector del Boletín Oficial de Aragón (BOA) por su servicio de datos abiertos en JSON.

Formato verificado el 29/10/2026 desde GitHub (también para 2022):
  - https://www.boa.aragon.es/cgi-bin/EBOA/BRSCGI?CMD=VERLST&BASE=BOLE&DOCS=1-1000&SEC=OPENDATABOAJSON
        &OUTPUTMODE=JSON&SORT=-PUBL&SEPARADOR=&PUBL-C=AAAAMMDD
    Devuelve todas las disposiciones del día con su texto: DOCN, FechaPublicacion, Numeroboletin, Seccion,
    Subseccion, Fechadisposicion, Rango, Emisor, Titulo, Texto (texto plano, párrafos separados por dos espacios),
    UrlPdf. Viene en ISO-8859-1 y algún texto trae barras invertidas que no son escapes JSON válidos.
  - Empleo público: «II. Autoridades y Personal» b) Oposiciones y concursos (Gobierno de Aragón, universidad y
    entidades locales); a) Nombramientos, solo los resultados de procesos; «V. Anuncios» por el título.

Uso:
  python -m motor.autonomicos.boa --salida ruta/                                   # ayer y hoy
  python -m motor.autonomicos.boa --desde 2022-01-01 --saltar-existentes --max-minutos 20 --salida ruta/

Guarda en datos/autonomicos/boa/: dias/, disposiciones/ (sin texto) y oposiciones/ (con texto limpio).
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
from motor.autonomicos.comun import (Freno, clasificar, convocante_de_organismo, es_empleo_por_titulo, es_resultado,
                                     escribir_json, escribir_jsonl)
from motor.boe.clasificar import normalizar
from motor.http import obtener
from motor.limpieza import parrafos_seguros

FUENTE = "boa"
MADRID = ZoneInfo("Europe/Madrid")
CGI = "https://www.boa.aragon.es/cgi-bin/EBOA/BRSCGI"
# Un escape JSON válido se deja tal cual; cualquier otra barra invertida se dobla. Hay que leer las parejas «\\\\»
# como un solo escape: con un simple «barra no seguida de…» la segunda barra de la pareja se tomaba por inválida.
RE_ESCAPE = re.compile(r'\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4})|\\')
RE_URL = re.compile(r"https://[^`´\s]+")
CAPITALES = ("Huesca", "Teruel", "Zaragoza")


def url_dia(d: date) -> str:
    return (f"{CGI}?CMD=VERLST&BASE=BOLE&DOCS=1-1000&SEC=OPENDATABOAJSON&OUTPUTMODE=JSON&SORT=-PUBL&SEPARADOR="
            f"&PUBL-C={d:%Y%m%d}")


def leer_json(contenido: bytes) -> list[dict]:
    texto = contenido.decode("latin-1")
    datos = json.loads(RE_ESCAPE.sub(lambda m: m.group(0) if len(m.group(0)) > 1 else "\\\\", texto), strict=False)
    if not isinstance(datos, list):
        raise ValueError("no es una lista")
    return datos


def texto_limpio(texto: str) -> tuple[str, int]:
    parrafos = [" ".join(p.split()) for p in re.split(r"\s{2,}", html.unescape(texto or "").replace("\xa0", " "))]
    guardados, omitidos = parrafos_seguros([p for p in parrafos if p])
    return "\n".join(guardados), omitidos


def ambito(x: dict) -> str:
    o = normalizar(x.get("organismo") or "")
    if o.startswith(("ayuntamiento", "comarca", "diputacion", "mancomunidad", "entidad local", "consorcio")):
        return "local"
    if o.startswith("universidad"):
        return "universidad"
    return "autonomico"


def es_empleo_publico(x: dict) -> bool:
    s, sub, t = normalizar(x.get("seccion") or ""), normalizar(x.get("subseccion") or ""), x.get("titulo") or ""
    if s.startswith("ii."):
        if "oposiciones" in sub:
            return True
        return es_resultado(t)
    if s.startswith("v."):
        return es_empleo_por_titulo(t) and bool(re.search(r"\b(proceso selectivo|plazas?|bolsa|oposicion|convocatoria)\b",
                                                         normalizar(t)))
    return False


def disposicion(f: dict, d: date) -> dict:
    urls = RE_URL.findall(f.get("UrlPdf") or "")
    return {
        "id": f"BOA-{f.get('DOCN')}",
        "docn": f.get("DOCN"),
        "fecha": d.isoformat(),
        "boletin": f.get("Numeroboletin"),
        "seccion": f.get("Seccion"),
        "subseccion": f.get("Subseccion") or None,
        "rango": f.get("Rango"),
        "organismo": " ".join((f.get("Emisor") or "").split()),
        "fecha_disposicion": f.get("Fechadisposicion"),
        "titulo": " ".join(html.unescape(f.get("Titulo") or "").split()),
        "url_pdf": urls[0] if urls else None,
        "url_html": f"{CGI}?CMD=VERDOC&BASE=BOLE&SEC=BUSQUEDA_AVANZADA&DOCN={f.get('DOCN')}" if f.get("DOCN") else None,
        "fuente": "BOA",
    }


def _ruta(raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return raiz / "datos" / "autonomicos" / FUENTE / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


def procesar_dia(d: date, raiz: Path, archivo: Archivo) -> dict:
    url = url_dia(d)
    r = obtener(url, accept="application/json", timeout=90)
    informe = {"fecha": d.isoformat(), "status": r.status, "alertas": []}
    if r.status != 200:
        informe["resultado"] = "error_http"
        informe["alertas"].append(f"BOA {d}: HTTP {r.status}")
        return informe
    inicio = r.contenido.lstrip()[:15].lower()
    if not inicio or inicio.startswith((b"<!doctype", b"<html")):
        # Un día sin boletín (sábado, domingo, festivo) el servicio responde 200 con la página de inicio del BOA en
        # vez de datos (verificado el 29/10/2026 con el 11/07/2026 y el 15/08/2025). Si fuera un fallo, el número
        # que falta se vería en el control de huecos de la numeración (motor.estado).
        informe.update({"resultado": "sin_boletin", "nota": "página de inicio en vez de datos"})
        return informe
    try:
        filas = leer_json(r.contenido)
    except ValueError as e:
        informe["resultado"] = "error_formato"
        informe["alertas"].append(f"BOA {d}: {e}")
        return informe
    if not filas:
        informe["resultado"] = "sin_boletin"
        return informe
    otras_fechas = {f.get("FechaPublicacion") for f in filas} - {d.strftime("%Y%m%d")}
    if otras_fechas:
        informe["resultado"] = "error_formato"
        informe["alertas"].append(f"BOA {d}: llegan disposiciones de otras fechas {sorted(otras_fechas)[:3]}")
        return informe
    captura = archivo.guardar(FUENTE, d, r.contenido, url, "json", r.status, r.cabeceras)
    disposiciones, empleo = [], []
    for f in filas:
        x = disposicion(f, d) | {"captura_sha256": captura["sha256"]}
        disposiciones.append(x)
        if es_empleo_publico(x):
            texto, omitidos = texto_limpio(f.get("Texto") or "")
            amb = ambito(x)
            empleo.append({**x, "ambito": amb, **clasificar(x["titulo"], x.get("subseccion")),
                           "convocante": convocante_de_organismo(x["organismo"], CAPITALES) if amb == "local" else None,
                           "texto": texto, "parrafos_omitidos_por_datos_personales": omitidos})
    escribir_jsonl(_ruta(raiz, "disposiciones", d), disposiciones)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    informe.update({"resultado": "ok", "numero": filas[0].get("Numeroboletin"), "sha256": captura["sha256"],
                    "disposiciones": len(disposiciones), "empleo_publico": len(empleo)})
    return informe


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=date.fromisoformat, default=hoy - timedelta(days=1))
    p.add_argument("--hasta", type=date.fromisoformat, default=hoy)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--saltar-existentes", action="store_true")
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    inicio, informes, d = time.monotonic(), [], a.desde
    freno = Freno()
    while d <= a.hasta:
        if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
            print("Tiempo agotado; se continúa en la siguiente ejecución")
            break
        ruta = _ruta(a.salida, "dias", d, "json")
        # También sábados y domingos: el BOA saca números en fin de semana (n.º 132 de 2026 el domingo 12/07, n.º 157
        # de 2025 el sábado 16/08) y un día sin boletín cuesta una sola petición.
        if (a.saltar_existentes and ruta.exists() and
                                json.loads(ruta.read_text(encoding="utf-8")).get("resultado") in {"ok", "sin_boletin"}):
            d += timedelta(days=1)
            continue
        try:
            inf = procesar_dia(d, a.salida, archivo)
        except ConnectionError as e:
            inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
        if not (inf.get("resultado") == "sin_boletin" and d >= hoy):  # hoy puede no estar publicado todavía
            escribir_json(ruta, inf)
        informes.append(inf)
        if freno.anotar(inf):
            break
        print(f"BOA {d}: {inf.get('resultado')} {inf.get('disposiciones', '')} disposiciones, "
              f"{inf.get('empleo_publico', '')} de empleo público")
        d += timedelta(days=1)
        time.sleep(a.pausa)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    for x in alertas[:30]:
        print(" -", x)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
