"""Conector del Boletín Oficial de La Rioja (BOR), por su buscador ordenado por fecha de publicación.

Formato verificado el 30/10/2026 desde el servidor de España (desde GitHub no responde):
  - Listado: https://web.larioja.org/bor-portada/bor?page=N&sort=fecha_publicacion+desc, 20 anuncios por página, del
    más reciente al más antiguo (432.723 en total). Por anuncio: organismo (h6), título con enlace al PDF
    (ias1.larioja.org/boletin/Bor_Boletin_visor_Servlet?referencia=…), «BOR nº 210 - Fecha: 30/10/2026» y la versión
    HTML /bor-portada/boranuncio?n=anu-580514.
  - La página del día (/bor-portada?fecha=…) se carga con JavaScript; el buscador no.
  - robots.txt cierra /apps y anuncios concretos por datos de personas («protege el DNI»): esos no se piden nunca.
  - Lo diario: las primeras páginas hasta encontrar una ya conocida. El histórico sigue página a página desde donde se
    quedó (estado.json), hasta 2022.
  - Empleo público: por el título (filtro estricto). Comunidad uniprovincial: también publica lo local.

Uso:
  python -m motor.autonomicos.bor --salida ruta/                                    # lo nuevo
  python -m motor.autonomicos.bor --desde 2022-01-01 --max-minutos 30 --salida ruta/
  python -m motor.autonomicos.bor --textos --max-minutos 20 --salida ruta/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (clasificar, convocante_de_organismo, descargar_textos, es_empleo_estricto,
                                     escribir_json, escribir_jsonl, leer_jsonl)
from motor.boe.clasificar import normalizar
from motor.http import obtener
from motor.limpieza import limpiar_html, texto_de

FUENTE = "bor"
SIGLAS = "BOR"
MADRID = ZoneInfo("Europe/Madrid")
BASE = "https://web.larioja.org"
NOMBRES = ("Boletín Oficial de La Rioja",)

RE_ITEM = re.compile(r"<li>\s*<h6>(?P<org>.*?)</h6>\s*<p>\s*<a href=\"(?P<pdf>[^\"]+)\">(?P<tit>.*?)</a>\s*</p>\s*<p>\s*"
                     r"BOR n[ºo°]\s*(?P<n>\d+)\s*-\s*Fecha:\s*(?P<d>\d{2})/(?P<m>\d{2})/(?P<a>\d{4})\s*-\s*"
                     r"<a [^>]*href=\"(?P<html>/bor-portada/boranuncio\?n=(?P<id>anu-\d+))\"", re.DOTALL)
RE_LOCAL = re.compile(r"(?i)^(ayuntamiento|mancomunidad|consorcio|junta vecinal|entidad local|comunidad de regantes)\b")


def url_pagina(n: int) -> str:
    return f"{BASE}/bor-portada/bor?page={n}&sort=fecha_publicacion+desc"


def parsear_pagina(html: str) -> list[dict]:
    out = []
    for m in RE_ITEM.finditer(html):
        out.append({"id": f"BOR-{m.group('id')}", "anuncio": m.group("id"), "organismo": texto_de(m.group("org")),
                    "titulo": texto_de(m.group("tit")), "boletin": int(m.group("n")),
                    "fecha": f"{m.group('a')}-{m.group('m')}-{m.group('d')}",
                    "url_pdf": texto_de(m.group("pdf")), "url_html": BASE + m.group("html"), "fuente": SIGLAS})
    return out


def ambito(x: dict) -> str:
    o = x.get("organismo") or ""
    if RE_LOCAL.match(o):
        return "local"
    if normalizar(o).startswith("universidad"):
        return "universidad"
    return "autonomico"


def convocante(x: dict) -> dict | None:
    c = convocante_de_organismo(x.get("organismo") or "")
    if c:
        c["provincia"] = "La Rioja"
    return c


def seleccionar(filas: list[dict]) -> list[dict]:
    out = []
    for x in filas:
        if not es_empleo_estricto(x["titulo"]):
            continue
        amb = ambito(x)
        out.append({**x, "ambito": amb, **clasificar(x["titulo"]), "convocante": convocante(x) if amb == "local" else None})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "autonomicos" / FUENTE


def _ruta(raiz: Path, carpeta: str, fecha: str, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / fecha[:4] / fecha[5:7] / f"{fecha[8:10]}.{ext}"


def guardar(raiz: Path, filas: list[dict]) -> tuple[int, int]:
    """Añade las filas a los ficheros de su fecha (sin repetir). Devuelve (nuevas, de empleo nuevas)."""
    nuevas = empleo = 0
    por_fecha: dict[str, list[dict]] = defaultdict(list)
    for x in filas:
        por_fecha[x["fecha"]].append(x)
    for fecha, lista in por_fecha.items():
        ruta = _ruta(raiz, "disposiciones", fecha)
        previas = {x["id"]: x for x in leer_jsonl(ruta)} if ruta.exists() else {}
        nuevos = [x for x in lista if x["id"] not in previas]
        if not nuevos:
            continue
        previas.update({x["id"]: x for x in nuevos})
        todas = sorted(previas.values(), key=lambda x: x["id"])
        escribir_jsonl(ruta, todas)
        sel = seleccionar(todas)
        escribir_jsonl(_ruta(raiz, "oposiciones", fecha), sel)
        nuevas += len(nuevos)
        empleo += sum(1 for x in sel if x["id"] in {y["id"] for y in nuevos})
    return nuevas, empleo


def conocida(raiz: Path, x: dict) -> bool:
    ruta = _ruta(raiz, "disposiciones", x["fecha"])
    return ruta.exists() and any(y["id"] == x["id"] for y in leer_jsonl(ruta))


def procesar_pagina(n: int, raiz: Path, archivo: Archivo) -> dict:
    url = url_pagina(n)
    r = obtener(url, accept="text/html")
    inf = {"pagina": n, "status": r.status, "alertas": []}
    if r.status != 200:
        inf["resultado"] = "error_http"
        inf["alertas"].append(f"BOR página {n}: HTTP {r.status}")
        return inf
    html = r.contenido.decode("utf-8", errors="replace")
    filas = parsear_pagina(html)
    if not filas:
        inf["resultado"] = "error_formato"
        inf["alertas"].append(f"BOR página {n}: sin anuncios (posible cambio de formato)")
        return inf
    captura = archivo.guardar(FUENTE, date.fromisoformat(filas[0]["fecha"]), r.contenido, url, "html", r.status,
                              r.cabeceras)
    filas = [{**x, "captura_sha256": captura["sha256"]} for x in filas]
    ya = sum(1 for x in filas if conocida(raiz, x))
    nuevas, empleo = guardar(raiz, filas)
    inf.update({"resultado": "ok", "anuncios": len(filas), "ya_conocidos": ya, "nuevos": nuevas, "empleo_nuevos": empleo,
                "fecha_primera": filas[0]["fecha"], "fecha_ultima": filas[-1]["fecha"]})
    return inf


def texto_disposicion(contenido: bytes) -> dict:
    h = contenido.decode("utf-8", errors="replace")
    i = h.find('<div class="anuncio_texto">')
    if i < 0:
        raise ValueError("sin anuncio_texto: posible cambio de formato")
    tit = re.search(r'<p class="entradilla_anuncio">(.*?)</p>', h, re.DOTALL)
    sec = re.search(r'<div class="roma_letra[^"]*">(.*?)</div>', h, re.DOTALL)
    return {"titulo": texto_de(tit.group(1)) if tit else None, "seccion": texto_de(sec.group(1)) if sec else None,
            **limpiar_html(h[i:])}


def ruta_texto(raiz: Path, x: dict) -> Path:
    return _base(raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"


def textos_pendientes(raiz: Path) -> list[dict]:
    lista = []
    for f in sorted((_base(raiz) / "oposiciones").glob("*/*/*.jsonl"), reverse=True):
        lista += [x for x in leer_jsonl(f) if x.get("url_html") and not ruta_texto(raiz, x).exists()]
    return sorted(lista, key=lambda x: 0 if x.get("alcance") in (None, "acceso") else 1)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=date.fromisoformat, default=None, help="carga histórica hasta esa fecha")
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--textos", action="store_true")
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--max-paginas", type=int, default=30, help="tope de páginas para lo nuevo")
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())

    if a.textos:
        pend = textos_pendientes(a.salida)
        hechos, errores = descargar_textos(pend, lambda x: ruta_texto(a.salida, x), lambda x: x["url_html"],
                                           texto_disposicion, archivo, FUENTE, a.max_minutos, a.pausa,
                                           accept="text/html", ext="html")
        print(f"BOR textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        return 0

    estado_ruta = _base(a.salida) / "estado.json"
    estado = json.loads(estado_ruta.read_text(encoding="utf-8")) if estado_ruta.exists() else {}
    inicio, informes, fallos = time.monotonic(), [], 0
    if a.desde is None:  # lo nuevo: hasta una página ya conocida del todo
        n = 1
        while n <= a.max_paginas:
            try:
                inf = procesar_pagina(n, a.salida, archivo)
            except ConnectionError as e:
                inf = {"pagina": n, "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            informes.append(inf)
            print(f"BOR página {n}: {inf['resultado']} {inf.get('nuevos', '')} nuevos ({inf.get('fecha_ultima', '')})")
            if inf["resultado"] != "ok" or inf["ya_conocidos"] == inf["anuncios"]:
                break
            n += 1
            time.sleep(a.pausa)
    elif estado.get("historico_completo_hasta", "9999") <= a.desde.isoformat():
        print(f"BOR: histórico completo hasta {estado['historico_completo_hasta']}")
    else:  # histórico: desde la página donde se quedó, hacia atrás en el tiempo
        n = max(1, estado.get("historico_pagina", 1) - 2)  # un margen: lo nuevo desplaza las páginas
        while True:
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                break
            try:
                inf = procesar_pagina(n, a.salida, archivo)
            except ConnectionError as e:
                inf = {"pagina": n, "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            informes.append(inf)
            if inf["resultado"] != "ok":
                fallos += 1
                if fallos >= 5:
                    break
                n += 1
                continue
            fallos = 0
            estado.update({"historico_pagina": n, "historico_fecha": inf["fecha_ultima"]})
            if n % 20 == 0:
                print(f"BOR histórico: página {n}, {inf['fecha_ultima']}")
                escribir_json(estado_ruta, estado)
            if inf["fecha_ultima"] < a.desde.isoformat():
                estado["historico_completo_hasta"] = a.desde.isoformat()
                break
            n += 1
            time.sleep(a.pausa)
        escribir_json(estado_ruta, estado)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Páginas: {len(informes)}. Nuevos: {sum(i.get('nuevos', 0) for i in informes)}. "
          f"De empleo: {sum(i.get('empleo_nuevos', 0) for i in informes)}. Alertas: {len(alertas)}")
    for x in alertas[:20]:
        print(" -", x)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes[-3:]) else 0


if __name__ == "__main__":
    sys.exit(main())
