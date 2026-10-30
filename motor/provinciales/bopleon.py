"""Conector del Boletín Oficial de la Provincia de León (portal nuevo, desde el 17/02/2025).

Formato verificado el 30/10/2026 desde GitHub:
  - Boletín de un día: https://bop.dipuleon.es/publica/consulta-de-bops/buscador/BOP-DD-MM-AAAA/ (404 si no hay):
    «BOP núm. 206 del 29/10/2026» y los enlaces al sumario en PDF (/export/sites/bop/.galleries/
    DOCUMENTOS-Sumarios-en-PDF/…pdf) y al boletín entero.
  - El sumario en PDF, leído conservando la disposición, trae los niveles por su sangría: sección («Administración
    Local»), grupo («Ayuntamientos», «Mancomunidades»), entidad («- Ayuntamiento de Bembibre») y los asuntos,
    separados por una línea en blanco. Cada asunto enlaza la ficha del anuncio (/publica/buscador-anuncios/anuncio/…/),
    un enlace por línea: los enlaces seguidos iguales son el mismo anuncio.
  - Lo anterior al 17/02/2025 está en el buscador antiguo (boletines anteriores): no se lee.
  - robots.txt solo cierra PDF concretos de boletines antiguos (2005-2011).

Uso:
  python -m motor.provinciales.bopleon --salida ruta/                       # ayer y hoy
  python -m motor.provinciales.bopleon --desde 2025-02-17 --max-minutos 30 --salida ruta/
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
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (Freno, clasificar, convocante_de_organismo, es_empleo_estricto, escribir_json,
                                     escribir_jsonl)
from motor.boe.clasificar import normalizar
from motor.http import obtener

FUENTE = "bopleon"
SIGLAS = "BOP-LEON"
MADRID = ZoneInfo("Europe/Madrid")
WEB = "https://bop.dipuleon.es"
INICIO = date(2025, 2, 17)
NOMBRES = ("Boletín Oficial de la Provincia de León",)

RE_CABECERA = re.compile(r"<h1><strong>BOP n[uú]m\.\s*(?P<n>\d+)</strong>\s*del\s*(?P<d>\d{2})/(?P<m>\d{2})/(?P<a>\d{4})</h1>")
RE_SUMARIO = re.compile(r'href="(?P<url>/export/sites/bop/\.galleries/DOCUMENTOS-Sumarios-en-PDF/[^"]+\.pdf)"')
RE_RUIDO = re.compile(r"^(Bolet[íi]n n[úu]m\.|\w+ \d{1,2} de \w+ de \d{4} - p[áa]gina|P[áa]gina \d+ de \d+ del sumario|"
                      r"CVE del|Sumario\s+\[\d+ anuncios?\])", re.IGNORECASE)


def url_dia(d: date) -> str:
    return f"{WEB}/publica/consulta-de-bops/buscador/BOP-{d:%d-%m-%Y}/"


def ficha(contenido: bytes) -> dict:
    h = contenido.decode("utf-8", errors="replace")
    c, s = RE_CABECERA.search(h), RE_SUMARIO.search(h)
    return {"numero": int(c.group("n")) if c else None,
            "fecha": f"{c.group('a')}-{c.group('m')}-{c.group('d')}" if c else None,
            "url_sumario": WEB + html.unescape(s.group("url")) if s else None}


def _paginas_y_enlaces(pdf: bytes) -> tuple[list[list[str]], list[str]]:
    from pypdf import PdfReader
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    lector = PdfReader(io.BytesIO(pdf))
    paginas, enlaces = [], []
    for p in lector.pages:
        paginas.append((p.extract_text(extraction_mode="layout") or "").splitlines())
        for a in p.get("/Annots") or []:
            o = a.get_object()
            uri = (o.get("/A") or {}).get("/URI")
            if uri and "/buscador-anuncios/anuncio/" in uri and (not enlaces or enlaces[-1] != uri):
                enlaces.append(str(uri))
    return paginas, enlaces


def _es_seccion(texto: str) -> bool:
    return normalizar(texto).startswith(("administracion", "anuncios", "otras administraciones"))


def parsear_sumario(pdf: bytes) -> tuple[list[dict], list[str]]:
    """-> (anuncios, alertas). pypdf conserva la disposición pero cada página empieza en su menor sangría, así que
    los niveles se deciden dentro de la página: «- X» es la entidad; lo que va más sangrado que la entidad de esa
    página son asuntos (separados por una línea en blanco); lo que va menos, encabezados (dos seguidos: sección y
    grupo; uno solo: grupo, salvo «Administración…» o «Anuncios…», que es sección). Un asunto partido por un salto
    de página se une si el trozo empieza en minúscula o si sobran asuntos respecto a los enlaces a fichas."""
    paginas, enlaces = _paginas_y_enlaces(pdf)
    seccion = grupo = entidad = None
    parrafos: list[dict] = []  # asuntos: {"seccion","grupo","entidad","titulo","tras_salto"}
    for lineas in paginas:
        utiles = []
        for bruta in lineas:
            texto = " ".join(bruta.split())
            if texto and RE_RUIDO.match(texto):
                continue
            utiles.append((len(bruta) - len(bruta.lstrip()) if texto else None, texto))
        entidades = [s for s, x in utiles if x.startswith("- ")]
        sangria_entidad = entidades[0] if entidades else None
        actual, blanco, primera = (parrafos[-1] if parrafos and entidad is not None else None), True, True
        pendientes: list[str] = []  # encabezados seguidos
        for k, (sangria, texto) in enumerate(utiles):
            if not texto:
                blanco = True
                continue
            if texto.startswith("- "):
                if pendientes:
                    if len(pendientes) >= 2 or _es_seccion(pendientes[0]):
                        seccion, grupo = pendientes[0], (pendientes[1] if len(pendientes) >= 2 else None)
                    else:
                        grupo = pendientes[0]
                    pendientes = []
                entidad, actual, blanco = texto[2:].strip(), None, False
                sangria_entidad = sangria
                primera = False
                continue
            es_asunto = entidad is not None and (sangria_entidad is None or sangria > sangria_entidad)
            if es_asunto and not pendientes:
                if actual is not None and not blanco and not primera:
                    actual["titulo"] += " " + texto
                elif actual is not None and primera and texto[:1].islower():
                    actual["titulo"] += " " + texto
                else:
                    actual = {"seccion": seccion, "grupo": grupo, "entidad": entidad, "titulo": texto,
                              "tras_salto": primera}
                    parrafos.append(actual)
            else:
                if pendientes and not blanco and len(pendientes[-1]) > 0 and texto[:1].islower():
                    pendientes[-1] += " " + texto  # encabezado en dos líneas
                else:
                    pendientes.append(texto)
                actual = None
            blanco = primera = False
    # asuntos de más por saltos de página: se unen al anterior, del primero al último, hasta cuadrar con los enlaces
    while len(parrafos) > len(enlaces) > 0:
        i = next((i for i, x in enumerate(parrafos) if x["tras_salto"] and i > 0
                  and parrafos[i - 1]["entidad"] == x["entidad"]), None)
        if i is None:
            break
        parrafos[i - 1]["titulo"] += " " + parrafos[i]["titulo"]
        del parrafos[i]
    anuncios = [{k: v for k, v in x.items() if k != "tras_salto"} for x in parrafos]
    alertas = []
    if len(enlaces) == len(anuncios):
        for x, u in zip(anuncios, enlaces):
            x["url_anuncio"] = u
    else:
        alertas.append(f"{len(anuncios)} asuntos y {len(enlaces)} enlaces a fichas: no se asocian")
    return anuncios, alertas


def es_local(x: dict) -> bool:
    return "administracion local" in normalizar(x.get("seccion") or "")


def convocante(x: dict) -> dict | None:
    e = x.get("entidad") or ""
    if normalizar(e).startswith("diputacion"):
        return {"tipo": "Diputación Provincial", "nombre": "León", "provincia": "León", "organismo": e}
    c = convocante_de_organismo(e or x.get("grupo") or "")
    if c and not c.get("provincia"):
        c["provincia"] = "León"
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


def _ruta(raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


def procesar_dia(d: date, raiz: Path, archivo: Archivo, pausa: float = 1.0) -> dict:
    r = obtener(url_dia(d), accept="text/html")
    inf = {"fecha": d.isoformat(), "status": r.status, "alertas": []}
    if r.status == 404:
        inf["resultado"] = "sin_boletin"
        return inf
    if r.status != 200:
        inf["resultado"] = "error_http"
        inf["alertas"].append(f"BOP León {d}: HTTP {r.status}")
        return inf
    f = ficha(r.contenido)
    if f["fecha"] != d.isoformat() or not f["url_sumario"]:
        inf["resultado"] = "error_formato"
        inf["alertas"].append(f"BOP León {d}: la ficha no trae número, fecha o sumario (posible cambio de formato)")
        return inf
    time.sleep(pausa)
    rs = obtener(f["url_sumario"], accept="application/pdf")
    if rs.status != 200 or rs.contenido[:4] != b"%PDF":
        inf["resultado"] = "error_http"
        inf["alertas"].append(f"BOP León {d}: sumario HTTP {rs.status}")
        return inf
    captura = archivo.guardar(FUENTE, d, rs.contenido, f["url_sumario"], "pdf", rs.status, rs.cabeceras)
    anuncios, alertas = parsear_sumario(rs.contenido)
    filas = [{**x, "numero_anuncio": f"{f['numero']}-{i:03d}", "id": f"BOPLEON-{d.year}-{f['numero']}-{i:03d}",
              "fecha": d.isoformat(), "boletin": f["numero"], "url_boletin": url_dia(d), "fuente": SIGLAS,
              "captura_sha256": captura["sha256"]} for i, x in enumerate(anuncios, 1)]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    inf.update({"resultado": "ok", "numero": f["numero"], "sha256": captura["sha256"], "disposiciones": len(filas),
                "empleo_publico": len(empleo)})
    inf["alertas"] += [f"BOP León {d}: {a}" for a in alertas]
    if not filas:
        inf["alertas"].append(f"BOP León {d}: sumario sin anuncios (posible cambio de formato)")
    return inf


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=date.fromisoformat, default=hoy - timedelta(days=1))
    p.add_argument("--hasta", type=date.fromisoformat, default=hoy)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    inicio, informes, freno = time.monotonic(), [], Freno()
    d = a.hasta
    while d >= max(a.desde, INICIO):
        ruta = _ruta(a.salida, "dias", d, "json")
        hecho = ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") in {"ok", "sin_boletin"}
        if d.weekday() >= 5 and not hecho:
            escribir_json(ruta, {"fecha": d.isoformat(), "resultado": "sin_boletin", "nota": "fin de semana", "alertas": []})
            hecho = True
        if not hecho:
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                break
            try:
                inf = procesar_dia(d, a.salida, archivo, a.pausa)
            except (ConnectionError, TimeoutError) as e:
                inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            if not (inf.get("resultado") == "sin_boletin" and d >= hoy):
                escribir_json(ruta, inf)
            informes.append(inf)
            print(f"BOP León {d}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            if freno.anotar(inf):
                break
            time.sleep(a.pausa)
        d -= timedelta(days=1)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
