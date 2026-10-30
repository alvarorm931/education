"""Conector del Boletín Oficial de la Provincia de Ourense (API del portal).

Formato verificado el 30/10/2026 desde GitHub (también para 2022):
  - Último boletín: https://bop.depourense.es/portalapi/api/boletin/ultimaFecha («20261030»).
  - Boletín de un día: /portalapi/api/boletin/getFecha/AAAAMMDD → JSON con el boletín (numeroBop, fechaPublicacion)
    y sus edictos: id, sumarioCas (asunto en castellano), sumarioGal y la sección («IV. ENTIDADES LOCALES»). No trae
    la entidad: está en la cabecera del texto de cada edicto.
  - Texto de un edicto: /portalapi/api/edicto/descargar/html/ID/es (o /gl): sección, organismo
    (span.bop-texto-organismo «AYUNTAMIENTO DE SAN CIBRAO DAS VIÑAS»), sumario y párrafos.
  - Para los edictos de empleo se pide su texto (para saber la entidad y guardar el texto limpio); en nombramientos,
    listas y resultados solo se guarda la entidad y se cuenta, porque el texto nombra a las personas.
  - robots.txt no existe (la dirección devuelve la página de la aplicación).

Uso:
  python -m motor.provinciales.bopourense --salida ruta/                                  # ayer y hoy
  python -m motor.provinciales.bopourense --desde 2022-01-01 --max-minutos 30 --salida ruta/
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
from motor.http import obtener
from motor.limpieza import RE_DOCUMENTO, limpiar_html, texto_de
from motor.extraccion.citas import citas
from motor.provinciales.comun import CON_TEXTO

FUENTE = "bopourense"
SIGLAS = "BOP-OURENSE"
MADRID = ZoneInfo("Europe/Madrid")
API = "https://bop.depourense.es/portalapi/api"
NOMBRES = ("Boletín Oficial de la Provincia de Ourense", "Boletín Oficial da Provincia de Ourense")
RE_ORGANISMO = re.compile(r'<span class="bop-texto-organismo">(.*?)</span>', re.DOTALL)


def url_dia(d: date) -> str:
    return f"{API}/boletin/getFecha/{d:%Y%m%d}"


def url_edicto(id_edicto: int | str, idioma: str = "es") -> str:
    return f"{API}/edicto/descargar/html/{id_edicto}/{idioma}"


def leer_dia(contenido: bytes) -> list[dict]:
    """Boletines del día (el ordinario y, si lo hay, el extraordinario)."""
    out = []
    for x in json.loads(contenido.decode("utf-8")) or []:
        b = x.get("boletin") or {}
        f = b.get("fechaPublicacion") or ""
        out.append({"numero": b.get("numeroBop"), "extraordinario": b.get("excepcional") == "S",
                    "fecha": f"{f[:4]}-{f[4:6]}-{f[6:8]}" if len(f) == 8 else None,
                    "anuncios": [{"numero_anuncio": str(e["id"]), "seccion": (e.get("seccion") or {}).get("nombre"),
                                  "titulo": " ".join((e.get("sumarioCas") or e.get("sumario") or "").split()),
                                  "titulo_gl": " ".join((e.get("sumarioGal") or "").split()) or None,
                                  "url_texto": url_edicto(e["id"])}
                                 for e in b.get("edictos") or [] if e.get("id")]})
    return out


def leer_edicto(contenido: bytes, x: dict | None = None) -> dict:
    h = contenido.decode("utf-8", errors="replace")
    org = RE_ORGANISMO.search(h)
    entidad = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", org.group(1))).split()) if org else None
    if x is not None and x.get("tipo_acto") not in CON_TEXTO:
        lineas = [texto_de(b) for b in re.split(r"</(?:p|tr|li)>", h)]
        return {"entidad": entidad, "titulo": None, "texto": None, "tablas": [], "solo_recuento": True,
                "lineas_con_documento_de_identidad": sum(1 for l in lineas if RE_DOCUMENTO.search(l)),
                "citas": citas("\n".join(lineas))}
    return {"entidad": entidad, "titulo": None, **limpiar_html(h)}


def es_local(x: dict) -> bool:
    s = normalizar(x.get("seccion") or "")
    return "entidades locales" in s or "diputacion provincial" in s


def convocante(entidad: str | None, seccion: str | None) -> dict | None:
    if not entidad and "diputacion provincial" in normalizar(seccion or ""):
        entidad = "Diputación Provincial de Ourense"
    c = convocante_de_organismo(entidad or "")
    if c and not c.get("provincia"):
        c["provincia"] = "Ourense"
    return c


def seleccionar(filas: list[dict]) -> list[dict]:
    out = []
    for x in filas:
        if not es_empleo_estricto(x["titulo"]):
            continue
        local = es_local(x)
        out.append({**x, "ambito": "local" if local else "otro", **clasificar(x["titulo"]),
                    "convocante": convocante(x.get("entidad"), x.get("seccion")) if local else None})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "provinciales" / FUENTE


def _ruta(raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


def procesar_dia(d: date, raiz: Path, archivo: Archivo, pausa: float = 1.0) -> dict:
    url = url_dia(d)
    r = obtener(url, accept="application/json")
    inf = {"fecha": d.isoformat(), "status": r.status, "alertas": []}
    if r.status != 200:
        inf["resultado"] = "error_http"
        inf["alertas"].append(f"BOP Ourense {d}: HTTP {r.status}")
        return inf
    try:
        boletines = [b for b in leer_dia(r.contenido) if b["fecha"] == d.isoformat()]
    except ValueError:
        inf["resultado"] = "error_formato"
        inf["alertas"].append(f"BOP Ourense {d}: la respuesta no es JSON")
        return inf
    if not boletines:
        inf["resultado"] = "sin_boletin"
        return inf
    captura = archivo.guardar(FUENTE, d, r.contenido, url, "json", r.status, r.cabeceras)
    filas = [{**x, "id": f"BOPOURENSE-{x['numero_anuncio']}", "fecha": d.isoformat(), "boletin": b["numero"],
              "extraordinario": b["extraordinario"], "fuente": SIGLAS, "captura_sha256": captura["sha256"]}
             for b in boletines for x in b["anuncios"]]
    empleo = seleccionar(filas)
    por_id = {f["id"]: f for f in filas}
    textos, sin_texto = 0, 0
    for x in empleo:  # la entidad está en el texto: se pide el de cada anuncio de empleo
        ruta = _base(raiz) / "textos" / d.strftime("%Y") / d.strftime("%m") / f"{x['id']}.json"
        try:
            time.sleep(pausa)
            rt = obtener(x["url_texto"], accept="text/html")
        except (ConnectionError, TimeoutError):
            sin_texto += 1
            continue
        if rt.status != 200:
            sin_texto += 1
            continue
        archivo.guardar(FUENTE, d, rt.contenido, x["url_texto"], "html", rt.status, rt.cabeceras)
        t = leer_edicto(rt.contenido, x)
        x["entidad"] = t.pop("entidad")
        por_id[x["id"]]["entidad"] = x["entidad"]  # también en disposiciones: reseleccionar parte de ellas
        if x.get("ambito") == "local":
            x["convocante"] = convocante(x["entidad"], x.get("seccion"))
        escribir_json(ruta, {"id": x["id"], "url": x["url_texto"], "fecha": d.isoformat(), **t,
                             "titulo": x["titulo"]})
        textos += 1
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    inf.update({"resultado": "ok", "numero": ",".join(str(b["numero"]) for b in boletines), "sha256": captura["sha256"],
                "disposiciones": len(filas), "empleo_publico": len(empleo), "textos": textos})
    if sin_texto:
        inf["alertas"].append(f"BOP Ourense {d}: {sin_texto} textos sin descargar")
    if not filas:
        inf["alertas"].append(f"BOP Ourense {d}: boletín sin edictos (posible cambio de formato)")
    return inf


def reparar(raiz: Path, pausa: float, max_minutos: float) -> tuple[int, int]:
    """Anuncios de empleo sin entidad (guardados antes de que pasara a disposiciones y perdida al reseleccionar):
    se vuelve a pedir la cabecera de su texto y se completan oposiciones y disposiciones."""
    from motor.autonomicos.comun import leer_jsonl, estado_dia
    inicio, hechos, errores = time.monotonic(), 0, 0
    for f in sorted((_base(raiz) / "oposiciones").glob("*/*/*.jsonl"), reverse=True):
        filas = leer_jsonl(f)
        faltan = [x for x in filas if not x.get("entidad") and x.get("url_texto")]
        if not faltan:
            continue
        for x in faltan:
            if max_minutos and (time.monotonic() - inicio) / 60 > max_minutos:
                break
            time.sleep(pausa)
            try:
                r = obtener(x["url_texto"], accept="text/html")
            except (ConnectionError, TimeoutError):
                errores += 1
                continue
            if r.status != 200:
                errores += 1
                continue
            x["entidad"] = leer_edicto(r.contenido)["entidad"]
            if x.get("ambito") == "local":
                x["convocante"] = convocante(x["entidad"], x.get("seccion"))
            hechos += 1
        escribir_jsonl(f, filas)
        fd = _base(raiz) / "disposiciones" / f.relative_to(_base(raiz) / "oposiciones")
        ent = {x["id"]: x.get("entidad") for x in filas if x.get("entidad")}
        if fd.exists():
            escribir_jsonl(fd, [{**d, "entidad": ent.get(d.get("id"), d.get("entidad"))} for d in leer_jsonl(fd)])
        if max_minutos and (time.monotonic() - inicio) / 60 > max_minutos:
            break
    return hechos, errores


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=date.fromisoformat, default=hoy - timedelta(days=1))
    p.add_argument("--hasta", type=date.fromisoformat, default=hoy)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--reparar", action="store_true", help="completar la entidad de los anuncios de empleo que no la tienen")
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    if a.reparar:
        hechos, errores = reparar(a.salida, a.pausa, a.max_minutos)
        print(f"BOP Ourense: entidad completada en {hechos} anuncios ({errores} errores)")
        return 0
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    inicio, informes, freno = time.monotonic(), [], Freno()
    d = a.hasta
    while d >= a.desde:
        ruta = _ruta(a.salida, "dias", d, "json")
        hecho, reintento = estado_dia(ruta)
        if d.weekday() >= 5 and not hecho:
            escribir_json(ruta, {"fecha": d.isoformat(), "resultado": "sin_boletin", "nota": "fin de semana", "alertas": []})
            hecho = True
        if not hecho or (d >= hoy - timedelta(days=1) and d.weekday() < 5):
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                break
            try:
                inf = procesar_dia(d, a.salida, archivo, a.pausa)
            except (ConnectionError, TimeoutError) as e:
                inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            if not (inf.get("resultado") == "sin_boletin" and d >= hoy - timedelta(days=1)):
                escribir_json(ruta, inf)
            informes.append(inf)
            if freno.anotar(inf, reintento=reintento):
                break
            print(f"BOP Ourense {d}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            time.sleep(a.pausa)
        d -= timedelta(days=1)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
