"""Conector del Diari Oficial de la Generalitat Valenciana (DOGV) por la API JSON de su portal.

Formato verificado el 29/10/2026 desde GitHub (la usa el propio portal dogv.gva.es):
  - GET /dogv-portal/dogv/calendar?startDate=AAAA-M-D&endDate=AAAA-M-D  -> [{fecha, esBis}] días con boletín
  - GET /dogv-portal/dogv?date=AAAA-MM-DD&lang=es  -> cabecera.numeroDogv y todas las disposiciones del día:
        id, titulo, seccion{id, descripcion}, subseccion{id, descripcion}, organismo, codigoInsercion, urlPdf...
  - Días con boletín extraordinario (esBis): /dogv/{numero}/versionesSumario -> [1, 2];
        /dogv/{numero}?ordenSumario=2&lang=es devuelve el extraordinario.
  - GET /dogv-portal/disposicion/{id}?lang=es -> datos completos y texto en HTML.
  - Empleo público: sección «II. AUTORIDADES Y PERSONAL», subsección «A) OFERTAS DE EMPLEO PÚBLICO, OPOSICIONES Y
    CONCURSOS» (Generalitat, universidades y ayuntamientos). Los resultados van en «B) NOMBRAMIENTOS Y CESES».

Uso:
  python -m motor.autonomicos.dogv --salida ruta/                                    # ayer y hoy
  python -m motor.autonomicos.dogv --desde 2022-01-01 --saltar-existentes --max-minutos 20 --salida ruta/
  python -m motor.autonomicos.dogv --textos --max-minutos 20 --salida ruta/          # textos pendientes

Guarda en datos/autonomicos/dogv/: dias/ (informe por día), disposiciones/, oposiciones/ y textos/.
"""

from __future__ import annotations

import argparse
import calendar
import json
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (Freno, clasificar, convocante_de_organismo, descargar_textos, es_empleo_por_titulo,
                                     es_resultado, escribir_json, escribir_jsonl, leer_jsonl)
from motor.boe.clasificar import normalizar
from motor.http import obtener, robots_permite
from motor.limpieza import limpiar_html

FUENTE = "dogv"
MADRID = ZoneInfo("Europe/Madrid")
API = "https://dogv.gva.es/dogv-portal"
DATOS = "https://dogv.gva.es/datos"
SECCION_PERSONAL = 13
RE_DIV_ABRE = re.compile(r"<div\b[^>]*>", re.IGNORECASE)
RE_DIV_CIERRA = re.compile(r"</div\s*>", re.IGNORECASE)
RE_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)


def url_calendario(anio: int, mes: int) -> str:
    return f"{API}/dogv/calendar?startDate={anio}-{mes}-1&endDate={anio}-{mes}-{calendar.monthrange(anio, mes)[1]}"


def url_dia(d: date) -> str:
    return f"{API}/dogv?date={d.isoformat()}&lang=es"


def url_versiones(numero: int) -> str:
    return f"{API}/dogv/{numero}/versionesSumario"


def url_orden(numero: int, orden: int) -> str:
    return f"{API}/dogv/{numero}?ordenSumario={orden}&lang=es"


def url_disposicion(ident: int | str) -> str:
    return f"{API}/disposicion/{ident}?lang=es"


def _desc(x: dict | None) -> str | None:
    return (x or {}).get("descripcion")


def ambito(d: dict) -> str:
    o = normalizar(d.get("organismo") or "")
    if o.startswith(("ayuntamiento", "ajuntament", "diputacion", "mancomunidad", "mancomunitat", "consorcio", "consorci",
                     "entidad local", "entitat local")):
        return "local"
    if o.startswith(("universidad", "universitat")):
        return "universidad"
    return "autonomico"


def es_empleo_publico(d: dict) -> bool:
    if d.get("seccion_id") != SECCION_PERSONAL:
        return False
    sub = normalizar(d.get("subseccion") or "")
    if "ofertas de empleo publico" in sub or "oposiciones" in sub:
        return True
    if "nombramientos" in sub:
        return es_resultado(d.get("titulo") or "")
    return es_empleo_por_titulo(d.get("titulo") or "") or es_resultado(d.get("titulo") or "")


def disposicion(x: dict, d: date, numero: int | None, orden: int) -> dict:
    return {
        "id": x.get("id"),
        "fecha": d.isoformat(),
        "boletin": numero,
        "orden_sumario": orden,
        "codigo_insercion": x.get("codigoInsercion"),
        "seccion_id": (x.get("seccion") or {}).get("id"),
        "seccion": _desc(x.get("seccion")),
        "subseccion": _desc(x.get("subseccion")),
        "organismo": " ".join((x.get("organismo") or "").split()),
        "titulo": " ".join((x.get("titulo") or "").split()),
        "pagina": x.get("paginaInicial"),
        "url_pdf": DATOS + x["urlPdf"] if x.get("urlPdf") else None,
        "url_api": url_disposicion(x["id"]) if x.get("id") else None,
        "fuente": "DOGV",
    }


def seleccionar(disposiciones: list[dict]) -> list[dict]:
    out = []
    for x in disposiciones:
        if not es_empleo_publico(x):
            continue
        amb = ambito(x)
        out.append({**x, "ambito": amb, **clasificar(x["titulo"], x.get("subseccion")),
                    "convocante": convocante_de_organismo(x["organismo"]) if amb == "local" else None})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "autonomicos" / FUENTE


def _ruta(raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


def _json(url: str) -> tuple[int, object, bytes, dict]:
    r = obtener(url, accept="application/json")
    if r.status != 200:
        return r.status, None, r.contenido, r.cabeceras
    return r.status, json.loads(r.contenido), r.contenido, r.cabeceras


def calendario_mes(anio: int, mes: int) -> dict[str, bool]:
    status, datos, _, _ = _json(url_calendario(anio, mes))
    if status != 200 or not isinstance(datos, list):
        raise ConnectionError(f"DOGV calendario {anio}-{mes:02d}: HTTP {status}")
    return {x["fecha"]: bool(x.get("esBis")) for x in datos}


def procesar_dia(d: date, es_bis: bool, raiz: Path, archivo: Archivo) -> dict:
    informe = {"fecha": d.isoformat(), "alertas": []}
    url = url_dia(d)
    status, datos, bruto, cab = _json(url)
    informe["status"] = status
    if status != 200 or not isinstance(datos, dict) or "cabecera" not in datos:
        informe["resultado"] = "error_http" if status != 200 else "error_formato"
        informe["alertas"].append(f"DOGV {d}: HTTP {status}" if status != 200 else f"DOGV {d}: sin cabecera")
        return informe
    if datos.get("fechaSumario") and datos["fechaSumario"] != d.strftime("%d-%m-%Y"):
        informe["resultado"] = "error_formato"
        informe["alertas"].append(f"DOGV {d}: el servidor devolvió el sumario de {datos['fechaSumario']}")
        return informe
    numero = datos["cabecera"].get("numeroDogv")
    captura = archivo.guardar(FUENTE, d, bruto, url, "json", status, cab)
    filas = [disposicion(x, d, numero, 1) | {"captura_sha256": captura["sha256"]} for x in datos.get("disposiciones") or []]
    ordenes = [1]
    if es_bis and numero:
        st, versiones, _, _ = _json(url_versiones(numero))
        ordenes = sorted(v for v in versiones if isinstance(v, int)) if st == 200 and isinstance(versiones, list) else [1]
        for orden in ordenes:
            if orden == 1:
                continue
            u = url_orden(numero, orden)
            st, extra, bruto2, cab2 = _json(u)
            if st != 200 or not isinstance(extra, dict):
                informe["alertas"].append(f"DOGV {d}: extraordinario {orden} HTTP {st}")
                continue
            c2 = archivo.guardar(FUENTE, d, bruto2, u, "json", st, cab2)
            filas += [disposicion(x, d, numero, orden) | {"captura_sha256": c2["sha256"]}
                      for x in extra.get("disposiciones") or []]
    vistos, unicas = set(), []
    for f in filas:  # el extraordinario puede repetir disposiciones del ordinario
        if f["id"] not in vistos:
            vistos.add(f["id"])
            unicas.append(f)
    empleo = seleccionar(unicas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), unicas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    informe.update({"resultado": "ok", "numero": numero, "ordenes": ordenes, "sha256": captura["sha256"],
                    "disposiciones": len(unicas), "empleo_publico": len(empleo)})
    if not unicas:
        informe["alertas"].append(f"DOGV {d}: boletín sin disposiciones (posible cambio de formato)")
    return informe


def texto_disposicion(contenido: bytes) -> dict:
    datos = json.loads(contenido)
    if "texto" not in datos:
        raise ValueError("respuesta sin texto: posible cambio de formato")
    # El DOGV maqueta cada párrafo como <div align="justify">: se tratan como párrafos (las tablas se respetan)
    html_texto = RE_DIV_ABRE.sub("<p>", datos.get("texto") or "")
    html_texto = RE_DIV_CIERRA.sub("</p>", RE_BR.sub("</p><p>", html_texto))
    limpio = limpiar_html(html_texto)
    return {"titulo": " ".join((datos.get("titulo") or "").split()), "seccion": datos.get("seccion"),
            "organismo": datos.get("organismo"), "tipo_documento": datos.get("tipoDocumento"),
            "cve": datos.get("cve"), "fecha_disposicion": datos.get("fechaDisposicion"), **limpio}


# Cabeceras y pies del PDF del DOGV («Núm. 9552 / 13.03.2023», «CVE: DOGV-C-2023-2519», «https://dogv.gva.es»)
RE_CABECERA_PDF = re.compile(r"(?i)^(?:N[úu]m\.\s*\d+\s*/\s*\d{1,2}\.\d{1,2}\.\d{4}(?:\s+\d+)?|CVE:\s*DOGV-\S+.*|"
                             r"https?://\S*dogv\S*.*|\d{1,5})$")


def textos_vacios(raiz: Path) -> list[dict]:
    """Disposiciones con el texto ya guardado pero vacío (la API del DOGV no da el texto de muchas de 2023: 532 el
    30/10/2026) y con PDF: se toma el texto del PDF."""
    lista = []
    for f in sorted((_base(raiz) / "oposiciones").glob("*/*/*.jsonl"), reverse=True):
        for x in leer_jsonl(f):
            r = ruta_texto(raiz, x)
            if not x.get("url_pdf") or not r.exists():
                continue
            d = json.loads(r.read_text(encoding="utf-8"))
            if d.get("texto") == "" and not d.get("tablas") and not d.get("parrafos_omitidos_por_datos_personales") \
                    and not d.get("desde_pdf"):
                lista.append(x)
    return lista


def texto_pdf_disposicion(contenido: bytes, x: dict) -> dict:
    from motor.provinciales.comun import texto_pdf
    return {**texto_pdf(contenido, True, RE_CABECERA_PDF), "titulo": x.get("titulo"), "desde_pdf": True}


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
    p.add_argument("--desde", type=date.fromisoformat, default=hoy - timedelta(days=1))
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
        hechos, errores = descargar_textos(pend, lambda x: ruta_texto(a.salida, x), lambda x: url_disposicion(x["id"]),
                                           texto_disposicion, archivo, FUENTE, a.max_minutos, a.pausa,
                                           accept="application/json", ext="json")
        print(f"DOGV textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        # solo los PDF que permite el robots.txt de la fuente (el del DOGV cierra /datos/AAAA/ en algunos años)
        vacios = [x for x in textos_vacios(a.salida) if robots_permite(x["url_pdf"])]
        def desde_pdf(contenido: bytes, x: dict) -> dict:  # conserva sección, organismo… de lo ya guardado
            previo = json.loads(ruta_texto(a.salida, x).read_text(encoding="utf-8"))
            return {**{k: previo[k] for k in ("seccion", "organismo", "tipo_documento", "cve", "fecha_disposicion")
                       if k in previo}, **texto_pdf_disposicion(contenido, x)}
        hechos, errores = descargar_textos(vacios, lambda x: ruta_texto(a.salida, x), lambda x: x["url_pdf"],
                                           desde_pdf, archivo, FUENTE, a.max_minutos, a.pausa,
                                           accept="application/pdf", ext="pdf", por_registro=True)
        print(f"DOGV textos desde el PDF: {hechos} hechos, {errores} errores, {len(vacios) - hechos} pendientes")
        return 0

    inicio, informes, calendarios = time.monotonic(), [], {}
    freno = Freno()
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
            clave = (d.year, d.month)
            if clave not in calendarios:
                calendarios[clave] = calendario_mes(*clave)
                time.sleep(a.pausa)
            cal = calendarios[clave]
            if d.isoformat() not in cal:
                inf = {"fecha": d.isoformat(), "resultado": "sin_boletin", "alertas": []}
                # Hoy puede no estar aún en el calendario: no se da por cerrado
                if d >= hoy:
                    d += timedelta(days=1)
                    continue
            else:
                inf = procesar_dia(d, cal[d.isoformat()], a.salida, archivo)
                time.sleep(a.pausa)
        except (ConnectionError, ValueError) as e:
            inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
        escribir_json(ruta, inf)
        informes.append(inf)
        if freno.anotar(inf):
            break
        if inf.get("resultado") != "sin_boletin":
            print(f"DOGV {d}: {inf.get('resultado')} {inf.get('disposiciones', '')} disposiciones, "
                  f"{inf.get('empleo_publico', '')} de empleo público")
        d += timedelta(days=1)

    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    for x in alertas[:30]:
        print(" -", x)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
