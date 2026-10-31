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
  - Comprobado el 31/10/2026: los boletines «sin maquetar» (maquetadosn «N», hasta 2023) no tienen el texto de cada
    edicto en HTML ni en PDF (la API responde 500 «No se encontro el fichero»). Solo está el PDF del boletín entero,
    /portalapi/api/boletin/descargar/ID/idioma/es, bilingüe y con sumario: de él sale la entidad de cada edicto (el
    nombre que encabeza sus asuntos en el sumario en castellano). Sin el texto (el cuerpo no repite el asunto).

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


def url_boletin_pdf(id_boletin: int | str) -> str:
    return f"{API}/boletin/descargar/{id_boletin}/idioma/es"


def leer_dia(contenido: bytes) -> list[dict]:
    """Boletines del día (el ordinario y, si lo hay, el extraordinario)."""
    out = []
    for x in json.loads(contenido.decode("utf-8")) or []:
        b = x.get("boletin") or {}
        f = b.get("fechaPublicacion") or ""
        out.append({"numero": b.get("numeroBop"), "extraordinario": b.get("excepcional") == "S",
                    "id_boletin": b.get("id"), "maquetado": b.get("maquetadosn") != "N",
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


RE_LINEA_SUMARIO = re.compile(r"(?:\.\s?){3,}\s*(\d{1,4})\s*$")
RE_SECCION_CASTELLANO = re.compile(r"^\s*([IVX]+)\s?\.\s+([A-ZÁÉÍÓÚÑÜ][A-ZÁÉÍÓÚÑÜ ,.]+?)\s*$")
TIPOS_ENTIDAD = ("ayuntamiento", "concello", "mancomun", "consorcio", "comunidad", "comunidade", "diputacion",
                 "deputacion", "instituto", "organismo", "xunta", "entidad", "agrupacion", "junta", "parroquia")


def _entidad_del_sumario(nombre: str) -> str:
    """«Rúa (A)» -> «Ayuntamiento de A Rúa»; lo que ya dice qué es (mancomunidad, consorcio…), tal cual."""
    nombre = " ".join(nombre.split())
    m = re.match(r"^(.*?)\s*\((A|O|As|Os)\)$", nombre)
    if m:
        nombre = f"{m.group(2)} {m.group(1)}"
    return nombre if normalizar(nombre).startswith(TIPOS_ENTIDAD) else f"Ayuntamiento de {nombre}"


def sumario_pdf(paginas: list[str]) -> list[dict]:
    """Entradas del sumario en castellano del PDF del boletín: {seccion, entidad, titulo, pagina}. El sumario va
    primero en gallego (secciones en minúscula) y luego en castellano (en mayúsculas); en las entidades locales cada
    entidad encabeza sus asuntos y cada asunto acaba en puntos y la página."""
    out, seccion, entidad, actual, en_castellano = [], None, None, [], False
    for pag in paginas[:3]:
        for linea in pag.splitlines():
            l = " ".join(linea.split())
            if not l:
                continue
            m = RE_SECCION_CASTELLANO.match(l)
            if m:
                en_castellano, seccion, entidad, actual = True, f"{m.group(1)}. {m.group(2).strip()}", None, []
                continue
            if not en_castellano:
                continue
            fin = RE_LINEA_SUMARIO.search(l)
            if fin:
                actual.append(RE_LINEA_SUMARIO.sub("", l))
                out.append({"seccion": seccion, "entidad": entidad, "titulo": " ".join(actual).strip(" ."),
                            "pagina": int(fin.group(1))})
                actual = []
            elif not actual and len(l) <= 45 and not l.endswith(".") and "entidades locales" in normalizar(seccion):
                entidad = l
            else:
                actual.append(l)
        if out and not any(RE_LINEA_SUMARIO.search(l) for l in pag.splitlines()):
            break
    return out


def entidades_del_pdf(pdf: bytes, edictos: list[dict]) -> dict[str, str]:
    """Entidad de cada edicto (por id) según el sumario en castellano del PDF del boletín entero, casando su asunto
    (sumarioCas) con la entrada del sumario por las primeras letras."""
    from motor.provinciales.textos import paginas_pdf
    return entidades_de_paginas(paginas_pdf(pdf), edictos)


def entidades_de_paginas(paginas: list[str], edictos: list[dict]) -> dict[str, str]:
    from motor.provinciales.textos import _plano
    entradas = [e for e in sumario_pdf(paginas) if e["entidad"]]
    out = {}
    for x in edictos:
        t = _plano(x.get("titulo") or "").replace(" ", "")[:50]
        if len(t) < 15:
            continue
        cands = [e for e in entradas if (u := _plano(e["titulo"]).replace(" ", "")[:50]) and
                 min(len(u), len(t)) >= 15 and u[:min(len(u), len(t))] == t[:min(len(u), len(t))]]
        if len({e["entidad"] for e in cands}) == 1:
            out[x["id"]] = _entidad_del_sumario(cands[0]["entidad"])
    return out


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
              "extraordinario": b["extraordinario"], "id_boletin": b.get("id_boletin"), "maquetado": b.get("maquetado", True),
              "fuente": SIGLAS, "captura_sha256": captura["sha256"]}
             for b in boletines for x in b["anuncios"]]
    empleo = seleccionar(filas)
    por_id = {f["id"]: f for f in filas}
    textos, sin_texto = 0, 0
    # Boletines sin maquetar: la entidad, del sumario del PDF del boletín entero (los edictos no tienen texto propio)
    for b in boletines:
        sin_maquetar = [x for x in empleo if x["boletin"] == b["numero"] and not x.get("maquetado", True)]
        if sin_maquetar and b.get("id_boletin"):
            for xid, ent in entidades_pdf_boletin(b["id_boletin"], d, sin_maquetar, archivo, pausa).items():
                x = next(y for y in sin_maquetar if y["id"] == xid)
                x["entidad"] = por_id[xid]["entidad"] = ent
                if x.get("ambito") == "local":
                    x["convocante"] = convocante(ent, x.get("seccion"))
    for x in empleo:  # la entidad está en el texto: se pide el de cada anuncio de empleo
        if not x.get("maquetado", True):
            sin_texto += 1
            continue
        ruta = _base(raiz) / "textos" / d.strftime("%Y") / d.strftime("%m") / f"{x['id']}.json"
        try:
            time.sleep(pausa)
            rt = obtener(x["url_texto"], accept="text/html", intentos=2)
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


def entidades_pdf_boletin(id_boletin, d: date, edictos: list[dict], archivo: Archivo, pausa: float) -> dict[str, str]:
    url = url_boletin_pdf(id_boletin)
    try:
        time.sleep(pausa)
        r = obtener(url, accept="application/pdf", intentos=2)
    except (ConnectionError, TimeoutError):
        return {}
    if r.status != 200 or r.contenido[:4] != b"%PDF":
        return {}
    archivo.guardar(FUENTE + "-boletin", d, r.contenido, url, "pdf", r.status, r.cabeceras)
    try:
        return entidades_del_pdf(r.contenido, edictos)
    except Exception:  # noqa: BLE001 - un PDF mal formado no para la carga
        return {}


def reparar(raiz: Path, pausa: float, max_minutos: float) -> tuple[int, int]:
    """Anuncios de empleo sin entidad (guardados antes de que pasara a disposiciones y perdida al reseleccionar):
    se vuelve a pedir la cabecera de su texto y se completan oposiciones y disposiciones."""
    from motor.autonomicos.comun import leer_jsonl, estado_dia
    inicio, hechos, errores = time.monotonic(), 0, 0
    archivo = Archivo(raiz / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    for f in sorted((_base(raiz) / "oposiciones").glob("*/*/*.jsonl"), reverse=True):
        filas = leer_jsonl(f)
        faltan = [x for x in filas if not x.get("entidad") and x.get("url_texto") and not x.get("sin_entidad_en_pdf")]
        if not faltan:
            continue
        # Sin saber si el boletín estaba maquetado (lo guardado antes del 31/10): se pregunta a la API por el día
        if any("maquetado" not in x for x in faltan):
            time.sleep(pausa)
            try:
                rd = obtener(url_dia(date.fromisoformat(faltan[0]["fecha"])), accept="application/json", intentos=2)
                bols = leer_dia(rd.contenido) if rd.status == 200 else []
            except (ConnectionError, TimeoutError, ValueError):
                bols = []
            info = {b["numero"]: b for b in bols}
            for x in faltan:
                b = info.get(x.get("boletin"))
                if b:
                    x["maquetado"], x["id_boletin"] = b["maquetado"], b["id_boletin"]
        for num in {x.get("boletin") for x in faltan if x.get("maquetado") is False and x.get("id_boletin")}:
            grupo = [x for x in faltan if x.get("boletin") == num and x.get("maquetado") is False]
            ents = entidades_pdf_boletin(grupo[0]["id_boletin"], date.fromisoformat(grupo[0]["fecha"]), grupo,
                                         archivo, pausa)
            for x in grupo:
                if x["id"] in ents:
                    x["entidad"] = ents[x["id"]]
                    if x.get("ambito") == "local":
                        x["convocante"] = convocante(x["entidad"], x.get("seccion"))
                    hechos += 1
                else:
                    x["sin_entidad_en_pdf"] = True  # no se vuelve a pedir el PDF por él
                    errores += 1
        for x in [y for y in faltan if y.get("maquetado", True) and not y.get("entidad")]:
            if max_minutos and (time.monotonic() - inicio) / 60 > max_minutos:
                break
            time.sleep(pausa)
            try:
                r = obtener(x["url_texto"], accept="text/html", intentos=2)
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
