"""Conector del Diari Oficial de la Generalitat de Catalunya (DOGC) por la API REST de su portal.

Formato verificado el 29/10/2026 desde GitHub (la usa el propio portal dogc.gencat.cat; solo admite POST):
  - POST https://portaldogc.gencat.cat/eadop-rest/api/dogc/calendarDOGC   language, year, month
        -> calendar: [{date «DD/MM/AAAA», hasDOGC, linkDOGC «...&numDOGC=9783...»}]
  - POST .../summaryDOGC   numDOGC, language
        -> sumaris[0].section[]: title («Cargos y personal», «Administración local»...) > header[] (organismo o
           grupo) > subheader[] (organismo) > document[]: title, linkDownloadDocumentPDF (con documentId)
  - POST .../documentDOGC  documentId, language -> documentData (tipo, organismo, CVE...) y textDocument (HTML)
  - Empleo público: «Cargos y personal» (Generalitat y universidades) y «Administración local», seleccionados por
    el título; en «Anuncios», solo los que hablan de procesos selectivos, plazas o bolsas.

Uso:
  python -m motor.autonomicos.dogc --salida ruta/                                   # mes en curso y anterior
  python -m motor.autonomicos.dogc --desde 2022-01 --saltar-existentes --max-minutos 20 --salida ruta/
  python -m motor.autonomicos.dogc --textos --max-minutos 20 --salida ruta/         # textos pendientes

Guarda en datos/autonomicos/dogc/: dias/, disposiciones/, oposiciones/ y textos/.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (clasificar, convocante_de_organismo, descargar_textos, es_empleo_por_titulo,
                                     es_resultado, escribir_json, escribir_jsonl, leer_jsonl)
from motor.boe.clasificar import normalizar
from motor.http import obtener, sesion_tls_compatible
from motor.limpieza import limpiar_html

FUENTE = "dogc"
MADRID = ZoneInfo("Europe/Madrid")
# El servidor del DOGC rechaza la negociación TLS con la lista de cifrados de Python: se usa la de OpenSSL.
SESION = sesion_tls_compatible()
API = "https://portaldogc.gencat.cat/eadop-rest/api/dogc"
PORTAL = "https://dogc.gencat.cat/es/document-del-dogc/?documentId="
RE_ANUNCIO_EMPLEO = re.compile(r"\b(proceso selectivo|procesos selectivos|pruebas selectivas|bolsa de (?:empleo|trabajo)|"
                               r"oposicion|plazas?|personal laboral fijo|funcionari\w+ de carrera)\b")


def _parametro(url: str | None, nombre: str) -> str | None:
    if not url:
        return None
    v = parse_qs(urlparse(url).query).get(nombre)
    return v[0] if v else None


def _post(endpoint: str, campos: dict) -> tuple[int, object, bytes, dict]:
    r = obtener(f"{API}/{endpoint}", accept="application/json", formulario=campos, sesion=SESION)
    if r.status != 200:
        return r.status, None, r.contenido, r.cabeceras
    return r.status, json.loads(r.contenido), r.contenido, r.cabeceras


def calendario_mes(anio: int, mes: int) -> dict[str, str]:
    """{fecha ISO: numDOGC} de los días con diario."""
    status, datos, _, _ = _post("calendarDOGC", {"language": "es", "year": str(anio), "month": str(mes)})
    if status != 200 or not isinstance(datos, dict) or "calendar" not in datos:
        raise ConnectionError(f"DOGC calendario {anio}-{mes:02d}: HTTP {status}")
    out = {}
    for x in datos["calendar"]:
        if x.get("hasDOGC") and x.get("linkDOGC"):
            d = datetime.strptime(x["date"], "%d/%m/%Y").date().isoformat()
            out[d] = _parametro("https://x/" + x["linkDOGC"], "numDOGC")
    return out


def documentos(sumario: dict, d: date) -> list[dict]:
    """Aplana sección > grupo > organismo > documento."""
    filas = []
    num = sumario.get("numDOGC")
    for sec in sumario.get("section") or []:
        for h in sec.get("header") or []:
            ramas = [(h.get("title"), None, h.get("document") or [])]
            ramas += [(h.get("title"), sh.get("title"), sh.get("document") or []) for sh in h.get("subheader") or []]
            for grupo, organismo, docs in ramas:
                for doc in docs:
                    ident = _parametro(doc.get("linkDownloadDocumentPDF"), "documentId")
                    filas.append({
                        "id": ident, "fecha": d.isoformat(), "boletin": num, "seccion": sec.get("title"),
                        "grupo": grupo, "organismo": organismo or grupo,
                        "titulo": " ".join((doc.get("title") or "").split()),
                        "url_html": PORTAL + ident if ident else None,
                        "url_pdf": doc.get("linkDownloadDocumentPDF"), "fuente": "DOGC",
                    })
    return filas


def ambito(x: dict) -> str:
    if normalizar(x.get("seccion") or "") == "administracion local":
        return "local"
    if normalizar(x.get("grupo") or "").startswith("universidades") or \
            normalizar(x.get("organismo") or "").startswith(("universidad", "universitat")):
        return "universidad"
    return "autonomico"


def es_empleo_publico(x: dict) -> bool:
    s = normalizar(x.get("seccion") or "")
    t = x.get("titulo") or ""
    if s in ("cargos y personal", "administracion local"):
        return es_empleo_por_titulo(t) or es_resultado(t)
    if s == "anuncios":
        return bool(RE_ANUNCIO_EMPLEO.search(normalizar(t)))
    return False


def seleccionar(disposiciones: list[dict]) -> list[dict]:
    out = []
    for x in disposiciones:
        if not x.get("id") or not es_empleo_publico(x):
            continue
        amb = ambito(x)
        out.append({**x, "ambito": amb, **clasificar(x["titulo"], x.get("seccion")),
                    "convocante": convocante_de_organismo(x["organismo"]) if amb == "local" else None})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "autonomicos" / FUENTE


def _ruta(raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


def procesar_dia(d: date, num: str, raiz: Path, archivo: Archivo) -> dict:
    informe = {"fecha": d.isoformat(), "numero": num, "alertas": []}
    status, datos, bruto, cab = _post("summaryDOGC", {"numDOGC": num, "language": "es"})
    informe["status"] = status
    sumarios = (datos or {}).get("sumaris") if isinstance(datos, dict) else None
    if status != 200 or not sumarios:
        informe["resultado"] = "error_http" if status != 200 else "error_formato"
        informe["alertas"].append(f"DOGC {d} ({num}): HTTP {status}" if status != 200 else f"DOGC {d}: sin sumario")
        return informe
    s = sumarios[0]
    if s.get("dateDOGC") and s["dateDOGC"] != d.strftime("%d/%m/%Y"):
        informe["resultado"] = "error_formato"
        informe["alertas"].append(f"DOGC {d}: el diario {num} es del {s['dateDOGC']}")
        return informe
    captura = archivo.guardar(FUENTE, d, bruto, f"{API}/summaryDOGC?numDOGC={num}", "json", status, cab)
    filas = [f | {"captura_sha256": captura["sha256"]} for f in documentos(s, d)]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    informe.update({"resultado": "ok", "sha256": captura["sha256"], "disposiciones": len(filas),
                    "empleo_publico": len(empleo), "secciones": [x.get("title") for x in s.get("section") or []]})
    if not filas:
        informe["alertas"].append(f"DOGC {d}: diario sin documentos (posible cambio de formato)")
    return informe


def texto_disposicion(contenido: bytes) -> dict:
    datos = json.loads(contenido)
    if "textDocument" not in datos:
        raise ValueError("respuesta sin textDocument: posible cambio de formato")
    meta = datos.get("documentData") or {}
    limpio = limpiar_html(datos.get("textDocument") or "")
    return {"titulo": " ".join((datos.get("titleDocument") or "").split()), "tipo_documento": meta.get("typeDocument"),
            "fecha_disposicion": meta.get("dateDocument"), "organismo": meta.get("issuingAuthority"),
            "cve": meta.get("CVE"), "url_xml": (datos.get("linkDownload") or {}).get("linkDownloadXML"), **limpio}


def ruta_texto(raiz: Path, x: dict) -> Path:
    return _base(raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"


def textos_pendientes(raiz: Path) -> list[dict]:
    lista = []
    for f in sorted((_base(raiz) / "oposiciones").glob("*/*/*.jsonl"), reverse=True):
        lista += [x for x in leer_jsonl(f) if x.get("id") and not ruta_texto(raiz, x).exists()]
    return sorted(lista, key=lambda x: 0 if x.get("alcance") in (None, "acceso") else 1)


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=lambda s: date.fromisoformat(s + "-01") if len(s) == 7 else date.fromisoformat(s),
                   default=hoy - timedelta(days=1))
    p.add_argument("--hasta", type=date.fromisoformat, default=hoy)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--saltar-existentes", action="store_true")
    p.add_argument("--textos", action="store_true")
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=0.7)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())

    if a.textos:
        pend = textos_pendientes(a.salida)
        hechos, errores = descargar_textos(pend, lambda x: ruta_texto(a.salida, x), lambda x: f"{API}/documentDOGC",
                                           texto_disposicion, archivo, FUENTE, a.max_minutos, a.pausa,
                                           accept="application/json", ext="json",
                                           formulario=lambda x: {"documentId": x["id"], "language": "es"},
                                           sesion=SESION)
        print(f"DOGC textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        return 0

    inicio, informes, calendarios = time.monotonic(), [], {}
    d = a.desde
    while d <= a.hasta:
        if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
            print("Tiempo agotado; se continúa en la siguiente ejecución")
            break
        ruta = _ruta(a.salida, "dias", d, "json")
        if a.saltar_existentes and ruta.exists() and \
                json.loads(ruta.read_text(encoding="utf-8")).get("resultado") in {"ok", "sin_boletin"}:
            d += timedelta(days=1)
            continue
        try:
            if (d.year, d.month) not in calendarios:
                calendarios[(d.year, d.month)] = calendario_mes(d.year, d.month)
                time.sleep(a.pausa)
            num = calendarios[(d.year, d.month)].get(d.isoformat())
            if not num:
                if d >= hoy:  # hoy puede no estar aún en el calendario
                    d += timedelta(days=1)
                    continue
                inf = {"fecha": d.isoformat(), "resultado": "sin_boletin", "alertas": []}
            else:
                inf = procesar_dia(d, num, a.salida, archivo)
                time.sleep(a.pausa)
        except (ConnectionError, ValueError) as e:
            inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
        escribir_json(ruta, inf)
        informes.append(inf)
        if inf["resultado"] != "sin_boletin":
            print(f"DOGC {d}: {inf['resultado']} {inf.get('disposiciones', '')} documentos, "
                  f"{inf.get('empleo_publico', '')} de empleo público")
        d += timedelta(days=1)

    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    for x in alertas[:30]:
        print(" -", x)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
