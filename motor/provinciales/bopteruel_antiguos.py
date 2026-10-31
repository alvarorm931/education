"""BOP de Teruel: boletines anteriores a la portada, día a día desde el PDF del boletín entero.

Formato verificado el 30/10/2026 desde el servidor de España (prueba motor.provinciales.sonda_pdf_texto, 22:19):
  - https://236ws.dpteruel.es/DPT/bopt.nsf/Redireccion?OpenPage&dia=20230112 es una página que enlaza el PDF del
    boletín de ese día (/estatico/boletines/2023/12enero.pdf). Sin enlace, ese día no hubo boletín.
  - El PDF (79 páginas el 12/01/2023) trae en la primera página el sumario, que solo nombra entidades y páginas
    («Villastar……2»). En el cuerpo, cada anuncio empieza por su número («Núm. 2023-0057»), sigue la entidad en
    mayúsculas («VILLASTAR») y después el asunto («Bases de la convocatoria para la elaboración de una bolsa de
    empleo…»). Las secciones van en mayúsculas («ADMINISTRACIÓN LOCAL», «NO OFICIAL») y cada página empieza por
    «BOP TE Número 7 12 de enero de 2023 2».
  - El número de anuncio es el mismo de la portada («Anuncio #2026-3143»), así que los identificadores casan.
  - robots.txt no responde: se lee como boletín oficial (motor/http.py). Solo responde desde España.

Uso: python -m motor.provinciales.bopteruel_antiguos --max-minutos 30 --salida ruta/
"""

from __future__ import annotations

import argparse
import html
import io
import json
import logging
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import Freno, escribir_json, escribir_jsonl, estado_dia, nombre_propio
from motor.boe.clasificar import normalizar
from motor.extraccion.citas import citas
from motor.http import obtener
from motor.limpieza import RE_DOCUMENTO, limpiar_texto, titulo_sin_nombres
from motor.provinciales import bopteruel as bt
from motor.provinciales.comun import CON_TEXTO, ruta_texto_pdf
from motor.provinciales.portadas import _ruta

INICIO = date(2022, 1, 1)
VERSION = "pdf_dia_v1"
RE_ENLACE_PDF = re.compile(r"""["'](?P<u>[^"'\s>]*/estatico/boletines/\d{4}/[^"'\s>]+\.pdf)["']""", re.IGNORECASE)
RE_NUMERO = re.compile(r"^N[úu]m\.\s*(?P<n>\d{4}-\d{2,6})$")
RE_CABECERA = re.compile(r"^BOP TE N[úu]mero \d+\b.*\d{4}(?:\s+\d+)?$", re.IGNORECASE)
RE_SECCION = re.compile(r"^(?:ADMINISTRACI[ÓO]N(?: [A-ZÁÉÍÓÚÑ]+){1,3}|NO OFICIAL|ANUNCIOS PARTICULARES|"
                        r"OTRAS ENTIDADES|ADMINISTRACI[ÓO]N)$")


def url_dia(d: date) -> str:
    return f"{bt.BASE}Redireccion?OpenPage&dia={d:%Y%m%d}"


def enlace_pdf(contenido: bytes, base: str) -> str | None:
    """El PDF del boletín que enlaza la página del día; None si ese día no hubo boletín."""
    m = RE_ENLACE_PDF.search(contenido.decode("latin-1", errors="replace"))
    return urljoin(base, html.unescape(m.group("u"))) if m else None


def paginas(pdf: bytes) -> list[str]:
    from motor.pdf import paginas as paginas_pdf
    return paginas_pdf(pdf)


def _mayusculas(lin: str) -> bool:
    letras = [c for c in lin if c.isalpha()]
    return len(letras) >= 3 and all(c.isupper() for c in letras)


def anuncios(pags: list[str]) -> list[dict]:
    """Anuncios del cuerpo (de la segunda página en adelante): número, sección, entidad, asunto y texto."""
    lineas = [" ".join(l.split()) for p in pags[1:] for l in p.splitlines()]
    lineas = [l for l in lineas if l and not RE_CABECERA.match(l)]
    bloques, seccion, actual = [], None, None
    for k, lin in enumerate(lineas):
        if (m := RE_NUMERO.match(lin)):
            actual = {"numero_anuncio": m.group("n"), "seccion": seccion, "lineas": []}
            bloques.append(actual)
            continue
        siguiente = lineas[k + 1] if k + 1 < len(lineas) else ""
        if RE_SECCION.match(lin) and (RE_NUMERO.match(siguiente) or RE_SECCION.match(siguiente) or
                                      _mayusculas(siguiente)):
            seccion = lin
            if RE_NUMERO.match(siguiente) or actual is None:
                continue
        if actual is not None:
            actual["lineas"].append(lin)
    out = []
    for b in bloques:
        ls, i = b["lineas"], 0
        entidad = []
        while i < len(ls) and _mayusculas(ls[i]) and len(entidad) < 3:
            entidad.append(ls[i])
            i += 1
        frase: list[str] = []
        for n, lin in enumerate(ls[i:], i):
            frase.append(lin)
            if lin.endswith((".", ":")) or sum(len(x) for x in frase) > 300:
                break
        titulo = _unir_lineas(frase)
        out.append({"numero_anuncio": b["numero_anuncio"], "seccion": nombre_propio(b["seccion"]) if b["seccion"] else None,
                    "grupo": None, "entidad": " ".join(entidad) or None, "titulo": titulo_sin_nombres(titulo[:400]),
                    "texto": "\n".join(ls)})
    return out


def _unir_lineas(lineas: list[str]) -> str:
    """Une las líneas de una frase; una palabra partida al final de la línea («va-» + «cantes») se junta."""
    texto = ""
    for lin in lineas:
        if texto.endswith("-") and lin[:1].islower():
            texto = texto[:-1] + lin
        else:
            texto = f"{texto} {lin}" if texto else lin
    return " ".join(texto.split())


def entidad_local(entidad: str | None) -> str | None:
    """«VILLASTAR» -> «Ayuntamiento de Villastar» si es un municipio de Teruel; las comarcas, mancomunidades y la
    diputación se quedan con su nombre."""
    from motor.catalogo.territorio import municipio
    if not entidad:
        return None
    e = nombre_propio(entidad) if entidad.isupper() else entidad
    n = normalizar(e)
    if n.startswith(("comarca", "mancomun", "consorci", "diputaci", "ayuntamiento", "entidad", "junta", "comunidad")):
        return e
    partes = [x.strip() for x in re.split(r"\s+y\s+|\s*/\s*", e) if x.strip()]
    if partes and municipio(partes[0], "44"):
        return f"Ayuntamiento de {partes[0]}" if len(partes) == 1 else e
    return e


def leer_pdf(d: date, url_pdf: str, pdf: bytes, captura: dict, raiz: Path) -> dict:
    lista = anuncios(paginas(pdf))
    filas = [{**{k: v for k, v in x.items() if k != "texto"}, "entidad": entidad_local(x["entidad"]),
              "id": f"{bt.SIGLAS}-{d.isoformat()}-{x['numero_anuncio']}", "fecha": d.isoformat(), "boletin": None,
              "url_pdf": None, "url_pdf_boletin": url_pdf, "fuente": bt.SIGLAS, "captura_sha256": captura["sha256"]}
             for x in lista]
    empleo = bt.seleccionar(filas)
    escribir_jsonl(_ruta(bt.PORTADA, raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(bt.PORTADA, raiz, "oposiciones", d), empleo)
    textos = {f["id"]: x["texto"] for f, x in zip(filas, lista)}
    base = raiz / "datos" / "provinciales" / bt.FUENTE
    for x in empleo:
        bruto = textos.get(x["id"]) or ""
        if x.get("tipo_acto") in CON_TEXTO:
            datos = {"titulo": x["titulo"], **limpiar_texto(bruto)}
        else:  # listas de personas: solo cuántas líneas traen un documento de identidad, y las citas a boletines
            datos = {"titulo": x["titulo"], "texto": None, "tablas": [], "solo_recuento": True,
                     "lineas_con_documento_de_identidad": sum(1 for l in bruto.splitlines() if RE_DOCUMENTO.search(l)),
                     "citas": citas(bruto)}
        escribir_json(ruta_texto_pdf(base, x), {"id": x["id"], **datos, "captura_sha256": captura["sha256"],
                                                "capturado": captura.get("capturado"), "url": url_pdf})
    inf = {"fecha": d.isoformat(), "status": 200, "resultado": "ok", "origen": "pdf_dia", "version": VERSION,
           "sha256": captura["sha256"], "url_pdf": url_pdf, "disposiciones": len(filas), "empleo_publico": len(empleo),
           "textos": len(empleo), "alertas": []}
    if not filas:
        inf["resultado"] = "sin_anuncios"
        inf["alertas"].append(f"{bt.SIGLAS} {d}: PDF sin anuncios en el cuerpo (posible cambio de formato)")
    return inf


def procesar_dia(d: date, raiz: Path, archivo: Archivo, pausa: float) -> dict:
    url = url_dia(d)
    r = obtener(url, accept="text/html")
    if r.status == 404:
        return {"fecha": d.isoformat(), "status": 404, "resultado": "sin_boletin", "alertas": []}
    if r.status != 200:
        return {"fecha": d.isoformat(), "status": r.status, "resultado": "error_http",
                "alertas": [f"{bt.SIGLAS} {d}: página del día HTTP {r.status}"]}
    pdf_url = enlace_pdf(r.contenido, r.url or url)
    if not pdf_url:
        return {"fecha": d.isoformat(), "status": 200, "resultado": "sin_boletin", "nota": "sin PDF", "alertas": []}
    time.sleep(pausa)
    rp = obtener(pdf_url, accept="application/pdf, */*")
    if rp.status == 404:
        return {"fecha": d.isoformat(), "status": 404, "resultado": "sin_boletin", "nota": "PDF 404", "alertas": []}
    if rp.status != 200 or rp.contenido[:4] != b"%PDF":
        return {"fecha": d.isoformat(), "status": rp.status, "resultado": "error_http",
                "alertas": [f"{bt.SIGLAS} {d}: PDF HTTP {rp.status}"]}
    captura = archivo.guardar(bt.FUENTE, d, rp.contenido, pdf_url, "pdf", rp.status, rp.cabeceras)
    return leer_pdf(d, pdf_url, rp.contenido, captura, raiz)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--desde", type=date.fromisoformat, default=INICIO)
    p.add_argument("--hasta", type=date.fromisoformat, default=None)
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    hasta = a.hasta or datetime.now(ZoneInfo("Europe/Madrid")).date() - timedelta(days=1)
    inicio, informes, freno, d = time.monotonic(), [], Freno(), hasta
    while d >= a.desde:
        ruta = _ruta(bt.PORTADA, a.salida, "dias", d, "json")
        hecho, reintento = estado_dia(ruta)
        if d.weekday() >= 5 and not hecho:
            escribir_json(ruta, {"fecha": d.isoformat(), "resultado": "sin_boletin", "nota": "fin de semana",
                                 "alertas": []})
            hecho = True
        if not hecho:
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                break
            time.sleep(a.pausa)
            try:
                inf = procesar_dia(d, a.salida, archivo, a.pausa)
            except (ConnectionError, TimeoutError) as e:
                inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            except Exception as e:  # noqa: BLE001 - un PDF raro no para la carga: queda anotado para revisarlo
                inf = {"fecha": d.isoformat(), "resultado": "error_formato",
                       "alertas": [f"{bt.SIGLAS} {d}: {type(e).__name__}: {str(e)[:200]}"]}
                print(f"::warning::{inf['alertas'][0]}")
            escribir_json(ruta, inf)
            informes.append(inf)
            print(f"{bt.SIGLAS} {d} (PDF): {inf['resultado']} {inf.get('empleo_publico', '')}")
            if freno.anotar(inf, reintento=reintento):
                break
        d -= timedelta(days=1)
    print(f"{bt.SIGLAS} anteriores: {len(informes)} días, {sum(i.get('empleo_publico', 0) for i in informes)} de empleo")
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
