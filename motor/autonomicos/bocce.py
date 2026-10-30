"""Conector del Boletín Oficial de la Ciudad de Ceuta (BOCCE). Solo responde desde el servidor de España.

Formato verificado el 30/10/2026 desde España (sonda motor/autonomicos/sonda_ceuta.py):
  - https://www.ceuta.es/ceuta/bocce enlaza una categoría de jDownloads por año
    (/ceuta/component/jdownloads/viewcategory/1965-2026); cada año, una por mes (…/viewcategory/1982-octubre), y cada
    mes, sus boletines, con el enlace de descarga del PDF (…/finish/1869-enero/21119-bocce-6162-04-01-2022,
    «BOCCE_Extra51_28-10-2026» los extraordinarios). Igual en 2022 y 2024 (sonda del 30/10/2026, 21:38). Cada página
    trae además el recuadro de últimas descargas, con los del mes en curso (…/viewdownload/…): no cuentan.
  - El PDF empieza por el SUMARIO: secciones en mayúsculas («DISPOSICIONES GENERALES CIUDAD DE CEUTA», «CIUDAD
    AUTONOMA DE CEUTA») y cada anuncio «101.- Extracto de la convocatoria… Pág.1367» (el título puede ocupar varias
    líneas). En el cuerpo, cada anuncio empieza por su número («101.-TituloES: …»): de ahí sale su texto.
  - robots.txt: se lee como boletín oficial (motor/http.py, decisión del 30/10/2026).

Uso:
  python -m motor.autonomicos.bocce --salida ruta/                      # el mes en curso y el anterior
  python -m motor.autonomicos.bocce --desde 2022-01 --max-minutos 30 --salida ruta/
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
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (Freno, clasificar, es_empleo_por_titulo, es_resultado, escribir_json,
                                     escribir_jsonl)
from motor.extraccion.citas import citas
from motor.http import obtener
from motor.limpieza import RE_DOCUMENTO, limpiar_texto
from motor.provinciales.comun import CON_TEXTO

FUENTE = "bocce"
SIGLAS = "BOCCE"
MADRID = ZoneInfo("Europe/Madrid")
BASE = "https://www.ceuta.es"
PORTADA = BASE + "/ceuta/bocce"
NOMBRES = ("Boletín Oficial de la Ciudad de Ceuta", "Boletín Oficial de la Ciudad Autónoma de Ceuta")
CONVOCANTE = {"tipo": "Ciudad Autónoma", "nombre": "Ceuta", "provincia": "Ceuta", "organismo": "Ciudad Autónoma de Ceuta"}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]

RE_ANIO = re.compile(r'href=["\'](/ceuta/component/jdownloads/viewcategory/(\d+)-(20\d\d))[?"\']')
# Los enlaces de los meses van entre comillas simples (href='/ceuta/…/viewcategory/1966-enero?Itemid=534')
RE_MES = re.compile(r'href=["\'](/ceuta/component/jdownloads/viewcategory/(\d+)-(' + "|".join(MESES) + r')(?:-20\d\d)?)[?"\']')
# La lista de cada mes enlaza la descarga (…/finish/1869-enero/21119-bocce-6162-04-01-2022); el recuadro de últimas
# descargas, la ficha (…/viewdownload/…). «bocce-trib421» es el Boletín Tributario (padrones y notificaciones de
# tributos, sin empleo público): no se lee.
RE_BOLETIN = re.compile(r'/ceuta/component/jdownloads/(?:viewdownload|finish)/(?P<cat>[\w-]+)/(?P<id>\d+)-bocce[-_]'
                        r'(?P<num>(?:extra|trib)?\d+)[-_](?P<d>\d{2})[-_](?P<m>\d{2})[-_](?P<a>\d{4})', re.IGNORECASE)
RE_ENTRADA = re.compile(r"^(?P<n>\d{1,4})\.-\s*(?P<t>.+?)\s*P[áa]g\.?\s*(?P<p>\d+)(?:\s*[-–]\s*\d+)?\.?$", re.DOTALL)
RE_INICIO_ENTRADA = re.compile(r"^\d{1,4}\.-")
RE_PIE = re.compile(r"Plaza de [ÁA]frica\s*S/N\s*(\d+)\s*$", re.MULTILINE)
# Cabecera y pie de cada página (se quitan del texto de los anuncios)
RE_CABECERA = re.compile(r"^(?:BOCCE\b.*\b(?:19|20)\d\d|Bolet[íi]n Oficial de la Ciudad de Ceuta\s*-\s*Plaza.*)$", re.IGNORECASE)
CABECERAS_SUMARIO = ("Boletín Oficial", "Ciudad de Ceuta", "BOCCE", "Nº", "EXTRAORDINARIO", "SUMARIO", "CEUTA", "D.L.")


def anios(contenido: bytes) -> dict[int, str]:
    return {int(a): u for u, _, a in RE_ANIO.findall(contenido.decode("utf-8", errors="replace"))}


def meses_del_anio(contenido: bytes) -> dict[int, str]:
    return {MESES.index(m) + 1: u for u, _, m in RE_MES.findall(contenido.decode("utf-8", errors="replace"))}


def boletines_del_mes(contenido: bytes, categoria: str | None = None) -> list[dict]:
    """Boletines de la página de un mes. Cada página de jDownloads trae además el recuadro de las últimas descargas
    (los boletines de este mes): con `categoria` («1982-octubre») solo cuentan los del propio mes."""
    vistos = {}
    for m in RE_BOLETIN.finditer(html.unescape(contenido.decode("utf-8", errors="replace"))):
        if categoria and m.group("cat") != categoria:
            continue
        num = m.group("num").lower()
        if num.startswith("trib"):
            continue
        vistos.setdefault(m.group("id"), {
            "id_descarga": m.group("id"), "categoria": m.group("cat"),
            "numero": ("Extra " + num[5:]) if num.startswith("extra") else num,
            "extraordinario": num.startswith("extra"),
            "fecha": f"{m.group('a')}-{m.group('m')}-{m.group('d')}",
            "url_pdf": f"{BASE}/ceuta/component/jdownloads/finish/{m.group('cat')}/{m.group(0).rsplit('/', 1)[1]}?Itemid=0"})
    return sorted(vistos.values(), key=lambda b: (b["fecha"], b["id_descarga"]))


def paginas_pdf(pdf: bytes) -> list[str]:
    from pypdf import PdfReader
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    return [p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf)).pages]


def numero_de_pagina(texto: str) -> int | None:
    m = RE_PIE.search(texto)
    return int(m.group(1)) if m else None


SECCIONES = ("DISPOSICIONES", "AUTORIDADES", "ANUNCIOS", "OTRAS DISPOSICIONES", "ADMINISTRACION DE JUSTICIA",
             "ADMINISTRACIÓN DE JUSTICIA", "ADMINISTRACION GENERAL", "ADMINISTRACIÓN GENERAL")


def sumario(paginas: list[str]) -> tuple[list[dict], int]:
    """Anuncios del sumario: número, título, sección, organismo y página. El sumario acaba en la primera página cuyo
    número (el del pie, «Plaza de África S/N 1367») ya es el de un anuncio. Devuelve también el índice de la primera
    página del cuerpo."""
    entradas, grupo, actual, cuerpo = [], [], [], len(paginas)
    seccion = organismo = None
    for k, texto in enumerate(paginas[:8]):
        n = numero_de_pagina(texto)
        if entradas and n is not None and n >= min(e["pagina"] for e in entradas):
            cuerpo = k
            break
        for linea in texto.splitlines():
            lin = " ".join(linea.split())
            if not lin or RE_CABECERA.match(lin) or (not entradas and not actual and not grupo
                                                       and lin.startswith(CABECERAS_SUMARIO)):
                continue
            if RE_INICIO_ENTRADA.match(lin):
                if grupo:  # encabezados seguidos: el primero es la sección y el último el organismo
                    if len(grupo) > 1:
                        seccion, organismo = grupo[0], grupo[-1]
                    elif grupo[0].startswith(SECCIONES):
                        seccion, organismo = grupo[0], None
                    else:
                        organismo = grupo[0]
                    grupo = []
                actual = [lin]
            elif actual:
                actual.append(lin)
            elif lin.upper() == lin and len(lin) > 5 and not re.search(r"\d", lin):
                grupo.append(lin)
                continue
            else:
                continue
            m = RE_ENTRADA.match(" ".join(actual))
            if m:
                entradas.append({"numero_anuncio": m.group("n"), "titulo": m.group("t").strip(" .-"),
                                 "seccion": seccion, "organismo": organismo, "pagina": int(m.group("p"))})
                actual = []
    return entradas, cuerpo


def textos_cuerpo(paginas: list[str], numeros: list[str], desde: int) -> dict[str, str]:
    """Texto de cada anuncio en el cuerpo (desde la página `desde`): de «101.-» hasta el anuncio siguiente."""
    cuerpo = "\n".join(paginas[desde:])
    posiciones = []
    for n in numeros:
        m = re.search(rf"(?m)^\s*{re.escape(n)}\.-", cuerpo)
        posiciones.append(m.start() if m else -1)
    out = {}
    for k, n in enumerate(numeros):
        i = posiciones[k]
        if i < 0:
            continue
        sig = min([p for p in posiciones if p > i] or [len(cuerpo)])
        out[n] = cuerpo[i:sig]
    return out


def es_empleo_publico(x: dict) -> bool:
    t = x.get("titulo") or ""
    return es_empleo_por_titulo(t) or es_resultado(t)


def seleccionar(disposiciones: list[dict]) -> list[dict]:
    return [{**x, "ambito": "autonomico", **clasificar(x["titulo"], x.get("seccion")), "convocante": CONVOCANTE}
            for x in disposiciones if es_empleo_publico(x)]


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "autonomicos" / FUENTE


def _ruta(raiz: Path, carpeta: str, b: dict, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / b["fecha"][:4] / b["fecha"][5:7] / f"{b['id_descarga']}.{ext}"


def ruta_texto(raiz: Path, x: dict) -> Path:
    return _base(raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"


def procesar_boletin(b: dict, raiz: Path, archivo: Archivo) -> dict:
    r = obtener(b["url_pdf"], accept="application/pdf, */*")
    inf = {**b, "status": r.status, "alertas": []}
    if r.status != 200 or r.contenido[:4] != b"%PDF":
        inf["resultado"] = "error_http"
        inf["alertas"].append(f"BOCCE {b['numero']} {b['fecha']}: HTTP {r.status}")
        return inf
    captura = archivo.guardar(FUENTE, date.fromisoformat(b["fecha"]), r.contenido, b["url_pdf"], "pdf", r.status,
                              r.cabeceras)
    paginas = paginas_pdf(r.contenido)
    entradas, desde = sumario(paginas)
    filas = [{**x, "id": f"BOCCE-{b['fecha'][:4]}-{b['numero'].replace(' ', '')}-{x['numero_anuncio']}",
              "fecha": b["fecha"], "boletin": b["numero"], "extraordinario": b["extraordinario"], "fuente": SIGLAS,
              "url_pdf": b["url_pdf"], "captura_sha256": captura["sha256"]} for x in entradas]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", b), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", b), empleo)
    # Textos de los anuncios de empleo, del propio PDF: en listas de personas solo el recuento y las citas
    cuerpos = textos_cuerpo(paginas, [x["numero_anuncio"] for x in filas], desde)
    for x in empleo:
        bruto = cuerpos.get(x["numero_anuncio"])
        if not bruto:
            continue
        if x.get("tipo_acto") in CON_TEXTO:
            datos = {"titulo": x["titulo"], **limpiar_texto(bruto, RE_CABECERA)}
        else:
            datos = {"titulo": x["titulo"], "texto": None, "tablas": [], "solo_recuento": True,
                     "lineas_con_documento_de_identidad": sum(1 for l in bruto.splitlines() if RE_DOCUMENTO.search(l)),
                     "citas": citas(bruto)}
        escribir_json(ruta_texto(raiz, x), {"id": x["id"], **datos, "captura_sha256": captura["sha256"],
                                            "capturado": captura["capturado"], "url": b["url_pdf"]})
    inf.update({"resultado": "ok", "sha256": captura["sha256"], "disposiciones": len(filas),
                "empleo_publico": len(empleo), "paginas": len(paginas)})
    if not filas:
        inf["alertas"].append(f"BOCCE {b['numero']} {b['fecha']}: sumario sin anuncios (posible cambio de formato)")
        if not b["extraordinario"]:  # un ordinario siempre trae anuncios: no se da por leído y su mes sigue abierto
            inf["resultado"] = "sin_anuncios"
    return inf


def desde_mes_anterior(hoy: date) -> str:
    return f"{hoy.year}-{hoy.month - 1:02d}" if hoy.month > 1 else f"{hoy.year - 1}-12"


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde", default=None, help="AAAA-MM: primer mes (por defecto, el mes anterior)")
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    desde = (int(a.desde[:4]), int(a.desde[5:7])) if a.desde else ((hoy.year, hoy.month - 1) if hoy.month > 1
                                                                      else (hoy.year - 1, 12))
    inicio, informes, freno = time.monotonic(), [], Freno()
    try:
        r = obtener(PORTADA, accept="text/html")
        por_anio = anios(r.contenido)
    except (ConnectionError, TimeoutError) as e:
        print(f"BOCCE: fuente inaccesible ({e})")
        return 1
    if not por_anio:
        print("::warning::BOCCE: la página no enlaza las categorías por año (posible cambio de formato)")
        return 1
    # Meses ya completos (todos sus boletines bien): su página no se vuelve a pedir
    ruta_hist = _base(a.salida) / "historico.json"
    hist = json.loads(ruta_hist.read_text(encoding="utf-8")) if ruta_hist.exists() else {}
    # «meses_completos» de la primera versión contaba el recuadro de últimas descargas de cada página: no vale
    completos = set(hist.get("meses_completos_v2", []))
    recientes = {f"{hoy.year}-{hoy.month:02d}", f"{desde_mes_anterior(hoy)}"}
    parar = False
    for anio in sorted((x for x in por_anio if x >= desde[0]), reverse=True):
        if all(f"{anio}-{m:02d}" in completos for m in range(1, 13)):
            continue
        time.sleep(a.pausa)
        meses = meses_del_anio(obtener(BASE + por_anio[anio] + "?Itemid=534", accept="text/html").contenido)
        if not meses:
            print(f"::warning::BOCCE {anio}: la página del año no enlaza meses (posible cambio de formato)")
        for mes in sorted(meses, reverse=True):
            clave = f"{anio}-{mes:02d}"
            if (anio, mes) < desde or (anio, mes) > (hoy.year, hoy.month) or clave in completos:
                continue
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                parar = True
                break
            time.sleep(a.pausa)
            lista = boletines_del_mes(obtener(BASE + meses[mes] + "?Itemid=534", accept="text/html").contenido,
                                      meses[mes].rsplit("/", 1)[1])
            if not lista:
                print(f"::warning::BOCCE {clave}: el mes no enlaza boletines (posible cambio de formato)")
            bien = 0
            for b in reversed(lista):
                ruta = _ruta(a.salida, "boletines", b, "json")
                if ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") == "ok":
                    bien += 1
                    continue
                if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                    parar = True
                    break
                time.sleep(a.pausa)
                try:
                    inf = procesar_boletin(b, a.salida, archivo)
                except (ConnectionError, TimeoutError) as e:
                    inf = {**b, "resultado": "fuente_inaccesible", "alertas": [str(e)]}
                except Exception as e:  # noqa: BLE001 - un PDF raro no para la carga: queda anotado para revisarlo
                    import traceback
                    traceback.print_exc()
                    inf = {"fecha": b["fecha"], "numero": b["numero"], "resultado": "error_formato",
                           "alertas": [f"BOCCE {b['fecha']}: {type(e).__name__}: {e}"[:300]]}
                escribir_json(ruta, inf)
                informes.append(inf)
                bien += inf["resultado"] == "ok"
                print(f"BOCCE {b['numero']} {b['fecha']}: {inf['resultado']} {inf.get('empleo_publico', '')}")
                if freno.anotar(inf):
                    parar = True
                    break
            if lista and bien == len(lista) and clave not in recientes:
                completos.add(clave)
            if parar:
                break
        if parar:
            break
    escribir_json(ruta_hist, {"meses_completos_v2": sorted(completos)})
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Boletines procesados: {len(informes)}. Alertas: {len(alertas)}")
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
