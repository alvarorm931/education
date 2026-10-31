"""Conector del Boletín Oficial de la Provincia de Cádiz (BOPCA), con su histórico desde 2022.

Formato verificado el 31/10/2026 desde GitHub (sondas de las 08:03 a las 08:08):
  - La dirección antigua (www.bopcadiz.org) no responde ni desde España; el boletín está en https://www.bopcadiz.es.
  - Cada boletín tiene su página, /boletin/Boletin-numero-NNN-del-ano-AAAA (número con tres cifras: «001», «100»;
    los números van de 1 en adelante cada año). Trae la fecha («Fri Oct 30 08:00:00 CET 2026»), el enlace al PDF del
    boletín entero (/.boletines_pdf/2026/10_octubre/BOP210_30-10-26.pdf) y el sumario por secciones (h3): cada
    anuncio con su número de registro, su órgano y su asunto («358.235.- Ayuntamiento de Benalup-Casas Viejas. Bases
    para la cobertura de 1 plaza de Administrativo/a…») y la página del PDF donde está (#page=25). Un número que no
    existe responde 404. Los registros pueden llevar año («76.702/21»).
  - En el PDF, cada anuncio acaba con su registro en una línea («Nº 357.549»): el texto de un anuncio va del registro
    anterior al suyo, y se casa por el número, sin buscar títulos.
  - robots.txt solo cierra los PDF de noviembre de 2021.

Uso:
  python -m motor.provinciales.bopcadiz --salida ruta/                              # lo nuevo del año en curso
  python -m motor.provinciales.bopcadiz --historico --max-minutos 30 --salida ruta/ # años anteriores desde 2022
"""

from __future__ import annotations

import argparse
import html
import io
import logging
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (Freno, clasificar, convocante_de_organismo, es_empleo_estricto, escribir_json,
                                     escribir_jsonl, estado_dia)
from motor.boe.clasificar import normalizar
from motor.extraccion.citas import citas
from motor.http import obtener
from motor.limpieza import RE_DOCUMENTO, limpiar_texto, titulo_sin_nombres
from motor.provinciales.comun import CON_TEXTO

FUENTE = "bopcadiz"
SIGLAS = "BOP-CADIZ"
BASE = "https://www.bopcadiz.es"
MADRID = ZoneInfo("Europe/Madrid")
DESDE_ANIO = 2022
MESES_EN = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10,
            "nov": 11, "dec": 12}
RE_FECHA = re.compile(r'<p class="fecha">\s*\w{3} (?P<m>\w{3}) (?P<d>\d{1,2}) [\d:]+ \w+ (?P<a>\d{4})')
RE_PDF = re.compile(r'href="(?P<u>[^"]+/\.boletines_pdf/[^"]+/BOP[^"/]+\.pdf)"[^>]*>\s*Bolet[íi]n PDF', re.I)
RE_SECCION = re.compile(r"<h3>\s*(?P<s>[^<]+?)\s*</h3>")
RE_ENTRADA = re.compile(r'<p>\s*<a href="(?P<href>[^"]+?\.pdf(?:#page=(?P<pag>\d+))?)"[^>]*>\s*<strong>\s*'
                        r'(?P<reg>\d{1,3}(?:\.\d{3})*(?:/\d{2,4})?)\.?-\s*(?P<org>.*?)</strong>(?P<asunto>.*?)</a>\s*</p>',
                        re.S)
# Fin de cada anuncio en el PDF: «Nº 357.549» en su línea o al final de la última, separado del texto por varios
# espacios («…a su derecho.           Nº 3.796»); a veces con espacios dentro del número
RE_FIN_ANUNCIO = re.compile(r"(?m)(?:^[ \t]*|[ \t]{2,})N[º°]\s*(?P<reg>\d{1,3}(?:\s?\.\s?\d{3})*(?:\s?/\s?\d{2,4})?)[ \t]*$")
RE_CABECERA = re.compile(r"(?i)^(?:P[áa]gina \d+|(?:\d{1,2} de \w+ de \d{4} )?B\.O\.P\. DE CADIZ NUM\. \d+.*)$")
SECCIONES_LOCALES = ("administracion local", "diputacion provincial")


def url_boletin(anio: int, numero: int) -> str:
    return f"{BASE}/boletin/Boletin-numero-{numero:03d}-del-ano-{anio}"


def _texto(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def _registro(s: str) -> str:
    return re.sub(r"\s+", "", s)


def parsear_boletin(contenido: bytes) -> dict:
    """Página de un boletín -> {"fecha", "url_pdf", "anuncios": [{registro, seccion, organismo, titulo, pagina}]}."""
    h = contenido.decode("utf-8", errors="replace")
    m = RE_FECHA.search(h)
    fecha = None
    if m and m.group("m").lower() in MESES_EN:
        fecha = date(int(m.group("a")), MESES_EN[m.group("m").lower()], int(m.group("d"))).isoformat()
    pdf = RE_PDF.search(h)
    marcas = sorted([(x.start(), "s", x) for x in RE_SECCION.finditer(h)] +
                    [(x.start(), "a", x) for x in RE_ENTRADA.finditer(h)], key=lambda t: t[0])
    seccion, anuncios = None, []
    for _, tipo, x in marcas:
        if tipo == "s":
            seccion = _texto(x.group("s"))
            continue
        org = _texto(x.group("org")).rstrip(". ")
        anuncios.append({"registro": x.group("reg"), "seccion": seccion, "organismo": org,
                         "titulo": titulo_sin_nombres(_texto(x.group("asunto"))[:500]),
                         "pagina": int(x.group("pag")) if x.group("pag") else None})
    return {"fecha": fecha, "url_pdf": html.unescape(pdf.group("u")) if pdf else None, "anuncios": anuncios}


def _entidad(x: dict) -> str | None:
    s = normalizar(x.get("seccion") or "")
    if s.startswith("diputacion provincial"):
        return "Diputación Provincial de Cádiz"
    return x.get("organismo")


def seleccionar(disposiciones: list[dict]) -> list[dict]:
    out = []
    for x in disposiciones:
        if not normalizar(x.get("seccion") or "").startswith(SECCIONES_LOCALES) or not es_empleo_estricto(x["titulo"]):
            continue
        conv = convocante_de_organismo(_entidad(x) or "")
        if conv and not conv.get("provincia"):
            conv["provincia"] = "Cádiz"
        out.append({**x, "ambito": "local", **clasificar(x["titulo"], x.get("seccion")), "convocante": conv})
    return out


def paginas_pdf(contenido: bytes) -> list[str]:
    from pypdf import PdfReader
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    return [p.extract_text() or "" for p in PdfReader(io.BytesIO(contenido)).pages]


def textos_por_registro(paginas: list[str]) -> dict[str, str]:
    """Texto de cada anuncio del PDF por su registro: del final del anterior («Nº …») al suyo."""
    completo = "\n".join(paginas)
    out, inicio = {}, 0
    for m in RE_FIN_ANUNCIO.finditer(completo):
        out.setdefault(_registro(m.group("reg")), completo[inicio:m.start()])
        inicio = m.end()
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "provinciales" / FUENTE


def _ruta(raiz: Path, carpeta: str, d: date, numero: int, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}-{numero:03d}.{ext}"


def _ruta_informe(raiz: Path, anio: int, numero: int) -> Path:
    return _base(raiz) / "boletines" / str(anio) / f"{numero:03d}.json"


def ruta_texto(raiz: Path, x: dict) -> Path:
    return _base(raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"  # como actos.ruta_texto


def procesar_boletin(anio: int, numero: int, raiz: Path, archivo: Archivo, pausa: float) -> dict:
    url = url_boletin(anio, numero)
    r = obtener(url, accept="text/html")
    inf = {"anio": anio, "numero": numero, "status": r.status, "url": url, "alertas": []}
    if r.status == 404:
        return {**inf, "resultado": "sin_boletin"}
    if r.status != 200:
        return {**inf, "resultado": "error_http", "alertas": [f"{SIGLAS} {numero}/{anio}: HTTP {r.status}"]}
    s = parsear_boletin(r.contenido)
    if not s["fecha"] or not s["anuncios"]:
        return {**inf, "resultado": "error_formato",
                "alertas": [f"{SIGLAS} {numero}/{anio}: página sin fecha o sin anuncios (posible cambio de formato)"]}
    d = date.fromisoformat(s["fecha"])
    captura = archivo.guardar(FUENTE, d, r.contenido, url, "html", r.status, r.cabeceras)
    filas = [{**x, "id": f"{SIGLAS}-{anio}-{x['registro'].replace('/', '-')}", "fecha": d.isoformat(), "boletin": str(numero),
              "entidad": _entidad(x), "url_html": url,
              "url_pdf_boletin": s["url_pdf"], "fuente": SIGLAS, "captura_sha256": captura["sha256"]} for x in s["anuncios"]]
    empleo = seleccionar(filas)
    textos = 0
    if empleo and s["url_pdf"]:
        time.sleep(pausa)
        textos = _textos(empleo, s["url_pdf"], d, raiz, archivo)
    escribir_jsonl(_ruta(raiz, "disposiciones", d, numero), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d, numero), empleo)
    inf.update({"fecha": d.isoformat(), "resultado": "ok", "sha256": captura["sha256"], "url_pdf": s["url_pdf"],
                "disposiciones": len(filas), "empleo_publico": len(empleo), "textos": textos})
    if empleo and textos < len(empleo):
        inf["alertas"].append(f"{SIGLAS} {numero}/{anio}: {len(empleo) - textos} textos sin cortar del PDF")
    return inf


def _textos(empleo: list[dict], url_pdf: str, d: date, raiz: Path, archivo: Archivo) -> int:
    try:
        rp = obtener(url_pdf, accept="application/pdf, */*")
    except (ConnectionError, TimeoutError):
        return 0
    if rp.status != 200 or rp.contenido[:4] != b"%PDF":
        return 0
    captura = archivo.guardar(FUENTE + "-boletin", d, rp.contenido, url_pdf, "pdf", rp.status, rp.cabeceras)
    try:
        por_registro = textos_por_registro(paginas_pdf(rp.contenido))
    except Exception:  # noqa: BLE001 - un PDF mal formado no para la carga
        return 0
    hechos = 0
    for x in empleo:
        bruto = por_registro.get(_registro(x["registro"]))
        if not bruto:
            continue
        if x.get("tipo_acto") in CON_TEXTO:
            datos = {"titulo": x["titulo"], **{k: v for k, v in limpiar_texto(bruto, RE_CABECERA).items() if k != "titulo"}}
        else:  # listas de personas: solo cuántas líneas traen un documento de identidad, y las citas a boletines
            datos = {"titulo": x["titulo"], "texto": None, "tablas": [], "solo_recuento": True,
                     "lineas_con_documento_de_identidad": sum(1 for l in bruto.splitlines() if RE_DOCUMENTO.search(l)),
                     "citas": citas(bruto)}
        escribir_json(ruta_texto(raiz, x), {"id": x["id"], **datos, "captura_sha256": captura["sha256"],
                                            "capturado": captura.get("capturado"), "url": url_pdf})
        hechos += 1
    return hechos


def recorrer(anio: int, raiz: Path, archivo: Archivo, pausa: float, inicio: float, max_minutos: float,
             freno: Freno) -> list[dict]:
    """Boletines del año, del 1 en adelante, hasta tres números seguidos sin boletín."""
    informes, vacios, n = [], 0, 1
    while vacios < 3 and n < 400:
        ruta = _ruta_informe(raiz, anio, n)
        hecho, reintento = estado_dia(ruta)
        if hecho:
            vacios = 0
            n += 1
            continue
        if max_minutos and (time.monotonic() - inicio) / 60 > max_minutos:
            print("Tiempo agotado; se continúa en la siguiente ejecución")
            break
        time.sleep(pausa)
        try:
            inf = procesar_boletin(anio, n, raiz, archivo, pausa)
        except (ConnectionError, TimeoutError) as e:
            inf = {"anio": anio, "numero": n, "resultado": "fuente_inaccesible", "alertas": [str(e)[:300]]}
        except Exception as e:  # noqa: BLE001 - una página rara no para la carga: queda anotada
            inf = {"anio": anio, "numero": n, "resultado": "error_formato",
                   "alertas": [f"{SIGLAS} {n}/{anio}: {type(e).__name__}: {str(e)[:200]}"]}
            print(f"::warning::{inf['alertas'][0]}")
        if inf["resultado"] == "sin_boletin":
            vacios += 1
            # No se guarda: el número puede salir más adelante (el boletín de mañana)
        else:
            vacios = 0
            escribir_json(ruta, inf)
        informes.append(inf)
        print(f"{SIGLAS} {n}/{anio}: {inf['resultado']} {inf.get('empleo_publico', '')}")
        if freno.anotar(inf, reintento=reintento):
            break
        n += 1
    return informes


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--historico", action="store_true", help=f"años anteriores, desde {DESDE_ANIO}")
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    inicio, freno, informes = time.monotonic(), Freno(), []
    anios = range(hoy.year - 1, DESDE_ANIO - 1, -1) if a.historico else [hoy.year]
    for anio in anios:
        informes += recorrer(anio, a.salida, archivo, a.pausa, inicio, a.max_minutos, freno)
        if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
            break
    ok = [i for i in informes if i["resultado"] == "ok"]
    print(f"{SIGLAS}: {len(ok)} boletines leídos, {sum(i.get('empleo_publico', 0) for i in ok)} anuncios de empleo, "
          f"{sum(i.get('textos', 0) for i in ok)} textos")
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
