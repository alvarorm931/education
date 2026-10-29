"""Conector del Boletín Oficial de la Ciudad Autónoma de Melilla (BOME).

Formato verificado el 29/10/2026 desde GitHub (también para 2022):
  - Calendario: https://bomemelilla.es/api/bomes/calendar?start=AAAA-MM-DD&end=AAAA-MM-DD
      -> [{title «Nº 6419», start «2026-10-02», url «/bome/BOME-B-2026-6419»}]; los extraordinarios son BOME-BX-.
  - Boletín: https://bomemelilla.es/bome/BOME-B-2026-6419 -> consejerías (acordeón), organismos (h4) y
      artículos: «ARTÍCULO 2 (CVE: BOME-A-2026-2)», título en blockquote, PDF /bome/descargar/BOME-A-…pdf y
      versión web /bome/BOME-B-…/articulo/2.
  - Texto: versión web del artículo, div.pagina-texto por cada página.
  - Melilla es a la vez comunidad y ayuntamiento: sus convocatorias se seleccionan por el título.

Uso:
  python -m motor.autonomicos.bome --salida ruta/                                   # mes en curso y anterior
  python -m motor.autonomicos.bome --desde 2022-01-01 --max-minutos 10 --salida ruta/
  python -m motor.autonomicos.bome --textos --max-minutos 10 --salida ruta/
"""

from __future__ import annotations

import argparse
import calendar as cal_mod
import json
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (Freno, clasificar, descargar_textos, es_empleo_por_titulo, es_resultado, escribir_json,
                                     escribir_jsonl, leer_jsonl)
from motor.http import obtener
from motor.limpieza import limpiar_html, texto_de

FUENTE = "bome"
MADRID = ZoneInfo("Europe/Madrid")
BASE = "https://bomemelilla.es"
CONVOCANTE = {"tipo": "Ciudad Autónoma", "nombre": "Melilla", "provincia": "Melilla",
              "organismo": "Ciudad Autónoma de Melilla"}

RE_TOKEN = re.compile(
    r'<button class="accordion-button[^"]*"[^>]*>\s*<span>\s*<i[^>]*></i>\s*(?P<cons>[^<]+?)\s*</span>'
    r'|<h4 class="text-uppercase h5">\s*<i[^>]*></i>\s*(?P<org>[^<]+?)\s*</h4>'
    r'|<h5 class="uppercase bold h6">(?P<art>.*?)</h5>\s*<blockquote[^>]*>(?P<tit>.*?)</blockquote>(?P<resto>.*?)</li>',
    re.DOTALL)
RE_CVE = re.compile(r"ART[ÍI]CULO\s+(\d+).*?CVE:\s*(BOME-AX?-\d{4}-\d+)", re.DOTALL)
RE_WEB = re.compile(r"href='(/bome/BOME-BX?-\d{4}-\d+/articulo/\d+)'")
RE_PAGINA = re.compile(r'<div class="pagina-texto">(.*?)</div>', re.DOTALL)


def url_calendario(anio: int, mes: int) -> str:
    fin = cal_mod.monthrange(anio, mes)[1]
    return f"{BASE}/api/bomes/calendar?start={anio}-{mes:02d}-01&end={anio}-{mes:02d}-{fin:02d}"


def calendario(contenido: bytes) -> list[dict]:
    out = []
    for x in json.loads(contenido):
        nombre = (x.get("url") or "").rsplit("/", 1)[-1]
        if nombre.startswith("BOME-B"):
            out.append({"id": nombre, "fecha": x.get("start"), "numero": re.sub(r"\D", "", x.get("title") or "") or None,
                        "tipo": "extraordinario" if nombre.startswith("BOME-BX") else "ordinario"})
    return out


def parsear_boletin(html: str, boletin: dict) -> list[dict]:
    consejeria = organismo = None
    filas = []
    for t in RE_TOKEN.finditer(html):
        if t.group("cons") is not None:
            consejeria, organismo = " ".join(t.group("cons").split()), None
        elif t.group("org") is not None:
            organismo = " ".join(t.group("org").split())
        elif t.group("art") is not None:
            m = RE_CVE.search(texto_de(t.group("art")))
            if not m:
                continue
            web = RE_WEB.search(t.group("resto"))
            filas.append({
                "id": m.group(2), "articulo": int(m.group(1)), "fecha": boletin["fecha"], "boletin": boletin["numero"],
                "boletin_id": boletin["id"], "tipo_boletin": boletin["tipo"], "seccion": consejeria,
                "organismo": organismo or consejeria, "titulo": texto_de(t.group("tit")),
                "url_html": BASE + web.group(1) if web else None,
                "url_pdf": f"{BASE}/bome/descargar/{m.group(2)}.pdf", "fuente": "BOME",
            })
    return filas


def es_empleo_publico(x: dict) -> bool:
    t = x.get("titulo") or ""
    return es_empleo_por_titulo(t) or es_resultado(t)


def seleccionar(disposiciones: list[dict]) -> list[dict]:
    return [{**x, "ambito": "autonomico", **clasificar(x["titulo"], x.get("seccion")), "convocante": CONVOCANTE}
            for x in disposiciones if es_empleo_publico(x)]


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "autonomicos" / FUENTE


def _ruta(raiz: Path, carpeta: str, b: dict, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / b["fecha"][:4] / f"{b['id']}.{ext}"


def procesar_boletin(b: dict, raiz: Path, archivo: Archivo) -> dict:
    url = f"{BASE}/bome/{b['id']}"
    r = obtener(url, accept="text/html")
    informe = {**b, "status": r.status, "alertas": []}
    if r.status != 200:
        informe["resultado"] = "error_http"
        informe["alertas"].append(f"BOME {b['id']}: HTTP {r.status}")
        return informe
    filas = parsear_boletin(r.contenido.decode("utf-8", errors="replace"), b)
    captura = archivo.guardar(FUENTE, date.fromisoformat(b["fecha"]), r.contenido, url, "html", r.status, r.cabeceras)
    filas = [x | {"captura_sha256": captura["sha256"]} for x in filas]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", b), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", b), empleo)
    informe.update({"resultado": "ok", "sha256": captura["sha256"], "disposiciones": len(filas),
                    "empleo_publico": len(empleo)})
    if not filas:
        informe["alertas"].append(f"BOME {b['id']}: boletín sin artículos leídos (posible cambio de formato)")
    return informe


def texto_disposicion(contenido: bytes) -> dict:
    html = contenido.decode("utf-8", errors="replace")
    paginas = RE_PAGINA.findall(html)
    if not paginas:
        raise ValueError("sin pagina-texto: posible cambio de formato")
    return {"titulo": None, **limpiar_html("".join(paginas))}


def ruta_texto(raiz: Path, x: dict) -> Path:
    return _base(raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"


def textos_pendientes(raiz: Path) -> list[dict]:
    lista = []
    for f in sorted((_base(raiz) / "oposiciones").glob("*/*.jsonl"), reverse=True):
        lista += [x for x in leer_jsonl(f) if x.get("url_html") and not ruta_texto(raiz, x).exists()]
    lista.sort(key=lambda x: x["fecha"], reverse=True)
    return sorted(lista, key=lambda x: 0 if x.get("alcance") in (None, "acceso") else 1)


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=date.fromisoformat, default=(hoy.replace(day=1) - timedelta(days=1)).replace(day=1))
    p.add_argument("--hasta", type=date.fromisoformat, default=hoy)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--textos", action="store_true")
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=0.8)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())

    if a.textos:
        pend = textos_pendientes(a.salida)
        hechos, errores = descargar_textos(pend, lambda x: ruta_texto(a.salida, x), lambda x: x["url_html"],
                                           texto_disposicion, archivo, FUENTE, a.max_minutos, a.pausa,
                                           accept="text/html", ext="html")
        print(f"BOME textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        return 0

    inicio, informes = time.monotonic(), []
    freno = Freno()
    anio, mes = a.desde.year, a.desde.month
    while (anio, mes) <= (a.hasta.year, a.hasta.month):
        try:
            r = obtener(url_calendario(anio, mes), accept="application/json")
            boletines = calendario(r.contenido) if r.status == 200 else []
        except (ConnectionError, ValueError) as e:
            informes.append({"mes": f"{anio}-{mes:02d}", "resultado": "fuente_inaccesible", "alertas": [str(e)]})
            boletines = []
        for b in boletines:
            if not (a.desde.isoformat() <= b["fecha"] <= a.hasta.isoformat()):
                continue
            ruta = _ruta(a.salida, "boletines", b, "json")
            if ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") == "ok":
                continue
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                return 0
            try:
                inf = procesar_boletin(b, a.salida, archivo)
            except ConnectionError as e:
                inf = {**b, "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            escribir_json(ruta, inf)
            informes.append(inf)
            if freno.anotar(inf):
                break
            print(f"BOME {b['fecha']} {b['id']}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            time.sleep(a.pausa)
        anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
        time.sleep(a.pausa)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Boletines procesados: {len(informes)}. Alertas: {len(alertas)}")
    for x in alertas[:30]:
        print(" -", x)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
