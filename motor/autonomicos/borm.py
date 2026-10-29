"""Conector del Boletín Oficial de la Región de Murcia (BORM) por los servicios XML de su portal.

Formato verificado el 29/10/2026 desde GitHub (también para 2022); los usa el propio portal www.borm.es:
  - GET https://www.borm.es/services/boletin/fecha/DD-MM-AAAA/sumario
      SumarioBoletinDTO: id, numero, ano, fechaPublicacion, extraordinario, fechaSiguiente y anunciosBoletin:
      id, numero, sumario (título), anunciante, subAnunciante, apartado («I. Comunidad Autónoma», «IV.
      Administración Local»...), subApartado («2. Autoridades y Personal»), categoriaCompleta («Oposiciones -
      Convocatoria», «Personal - Ceses/Nombramientos»; a veces vacía en los días recientes).
  - GET https://www.borm.es/services/anuncio/{id}/txt -> texto del anuncio.
  - Murcia es uniprovincial: los ayuntamientos publican aquí sus bases (apartado IV); el anunciante es el
    nombre del municipio.

Uso:
  python -m motor.autonomicos.borm --salida ruta/                                  # ayer y hoy
  python -m motor.autonomicos.borm --desde 2022-01-01 --saltar-existentes --max-minutos 20 --salida ruta/
  python -m motor.autonomicos.borm --textos --max-minutos 20 --salida ruta/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (clasificar, descargar_textos, es_empleo_por_titulo, es_resultado, escribir_json,
                                     escribir_jsonl, leer_jsonl, nombre_propio)
from motor.boe.clasificar import normalizar
from motor.http import obtener
from motor.limpieza import parrafos_seguros, tabla

FUENTE = "borm"
MADRID = ZoneInfo("Europe/Madrid")
API = "https://www.borm.es/services"


def url_dia(d: date) -> str:
    return f"{API}/boletin/fecha/{d:%d-%m-%Y}/sumario"


def url_texto(ident: str) -> str:
    return f"{API}/anuncio/{ident}/txt"


def _t(nodo: ET.Element, etiqueta: str) -> str | None:
    x = nodo.findtext(etiqueta)
    return " ".join(x.split()) if x and x.strip() else None


def parsear_sumario(xml: bytes) -> dict:
    raiz = ET.fromstring(xml)
    anuncios = []
    for a in raiz.findall("anunciosBoletin/anunciosBoletin"):
        anuncios.append({
            "id": f"BORM-{_t(a, 'ano')}-{_t(a, 'numero')}", "anuncio_id": _t(a, "id"), "numero_anuncio": _t(a, "numero"),
            "titulo": _t(a, "sumario") or "", "organismo": _t(a, "anunciante"), "suborganismo": _t(a, "subAnunciante"),
            "seccion": _t(a, "apartado"), "subseccion": _t(a, "subApartado"), "categoria": _t(a, "categoriaCompleta"),
            "paginas": _t(a, "paginas"), "fuente": "BORM",
            "url_html": f"https://www.borm.es/#/home/anuncio/{_t(a, 'fechaPublicacion')}/{_t(a, 'numero')}",
            "url_pdf": f"{API}/anuncio/{_t(a, 'id')}/pdf",
        })
    return {"id": _t(raiz, "id"), "numero": _t(raiz, "numero"), "fecha": _t(raiz, "fechaPublicacion"),
            "extraordinario": _t(raiz, "extraordinario") == "true", "anuncios": anuncios}


def ambito(x: dict) -> str:
    s = normalizar(x.get("seccion") or "")
    if "administracion local" in s:
        return "local"
    if normalizar(x.get("suborganismo") or "").startswith("universidad"):
        return "universidad"
    if "comunidad autonoma" in s:
        return "autonomico"
    return "otro"


def es_empleo_publico(x: dict) -> bool:
    s, sub = normalizar(x.get("seccion") or ""), normalizar(x.get("subseccion") or "")
    cat, t = normalizar(x.get("categoria") or ""), x.get("titulo") or ""
    if cat.startswith("oposiciones"):
        return True
    if "autoridades y personal" in sub:
        return es_empleo_por_titulo(t) or es_resultado(t)
    if "administracion local" in s:
        return (cat.startswith("personal") and (es_empleo_por_titulo(t) or es_resultado(t))) or \
            (not cat and es_empleo_por_titulo(t))
    return False


def seleccionar(anuncios: list[dict]) -> list[dict]:
    out = []
    for x in anuncios:
        if not es_empleo_publico(x):
            continue
        amb = ambito(x)
        conv = {"tipo": "Ayuntamiento", "nombre": nombre_propio(x["organismo"] or ""), "provincia": "Murcia",
                "organismo": x["organismo"]} if amb == "local" and x.get("organismo") else None
        out.append({**x, "ambito": amb, **clasificar(x["titulo"], x.get("subseccion")), "convocante": conv})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "autonomicos" / FUENTE


def _ruta(raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


def procesar_dia(d: date, raiz: Path, archivo: Archivo) -> dict:
    url = url_dia(d)
    r = obtener(url, accept="application/xml")
    informe = {"fecha": d.isoformat(), "status": r.status, "alertas": []}
    if r.status in (204, 404) or (r.status == 200 and not r.contenido.strip()):
        informe["resultado"] = "sin_boletin"
        return informe
    if r.status != 200:
        informe["resultado"] = "error_http"
        informe["alertas"].append(f"BORM {d}: HTTP {r.status}")
        return informe
    try:
        s = parsear_sumario(r.contenido)
    except ET.ParseError as e:
        informe["resultado"] = "error_formato"
        informe["alertas"].append(f"BORM {d}: {e}")
        return informe
    if not s["numero"]:
        informe["resultado"] = "sin_boletin"
        return informe
    if s["fecha"] != d.strftime("%d-%m-%Y"):
        informe["resultado"] = "sin_boletin" if s["fecha"] else "error_formato"
        informe["alertas"].append(f"BORM {d}: el servidor devolvió el boletín de {s['fecha']}")
        return informe
    captura = archivo.guardar(FUENTE, d, r.contenido, url, "xml", r.status, r.cabeceras)
    filas = [x | {"fecha": d.isoformat(), "boletin": s["numero"], "extraordinario": s["extraordinario"],
                  "captura_sha256": captura["sha256"]} for x in s["anuncios"]]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    informe.update({"resultado": "ok", "numero": s["numero"], "sha256": captura["sha256"],
                    "disposiciones": len(filas), "empleo_publico": len(empleo)})
    if not filas:
        informe["alertas"].append(f"BORM {d}: boletín sin anuncios (posible cambio de formato)")
    return informe


def texto_disposicion(contenido: bytes) -> dict:
    """Texto plano del BORM: párrafos cortados por la maquetación y tablas con columnas separadas por tabuladores.

    Las líneas con tabuladores seguidas forman una tabla: si es una lista de personas (cabecera con DNI, apellidos,
    nombre... o varios documentos de identidad) solo se guarda su número de filas.
    """
    texto = contenido.decode("utf-8", errors="replace")
    if texto.lstrip().startswith("<"):
        raise ValueError("se esperaba texto plano")
    parrafos, tablas, actual, filas = [], [], [], []

    def cerrar_parrafo():
        if actual:
            parrafos.append(" ".join(actual))
            actual.clear()

    def cerrar_tabla():
        if filas:
            tablas.append(tabla([[" ".join(c.split()) for c in f.split("\t")] for f in filas]))
            filas.clear()

    for bruta in texto.replace("\r", "").split("\n"):
        if "\t" in bruta:
            cerrar_parrafo()
            filas.append(bruta)
            continue
        cerrar_tabla()
        l = " ".join(bruta.split())
        if not l:
            cerrar_parrafo()
            continue
        actual.append(l)
        if re.search(r"[.:;]$", l):
            cerrar_parrafo()
    cerrar_parrafo()
    cerrar_tabla()
    guardados, omitidos = parrafos_seguros(parrafos)
    return {"titulo": None, "texto": "\n".join(guardados), "tablas": tablas,
            "parrafos_omitidos_por_datos_personales": omitidos}


def ruta_texto(raiz: Path, x: dict) -> Path:
    return _base(raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"


def textos_pendientes(raiz: Path) -> list[dict]:
    lista = []
    for f in sorted((_base(raiz) / "oposiciones").glob("*/*/*.jsonl"), reverse=True):
        lista += [x for x in leer_jsonl(f) if x.get("anuncio_id") and not ruta_texto(raiz, x).exists()]
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
        hechos, errores = descargar_textos(pend, lambda x: ruta_texto(a.salida, x), lambda x: url_texto(x["anuncio_id"]),
                                           texto_disposicion, archivo, FUENTE, a.max_minutos, a.pausa,
                                           accept="text/plain", ext="txt")
        print(f"BORM textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        return 0

    inicio, informes, d = time.monotonic(), [], a.desde
    while d <= a.hasta:
        if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
            print("Tiempo agotado; se continúa en la siguiente ejecución")
            break
        ruta = _ruta(a.salida, "dias", d, "json")
        if d.weekday() == 6 or (a.saltar_existentes and ruta.exists() and
                                json.loads(ruta.read_text(encoding="utf-8")).get("resultado") in {"ok", "sin_boletin"}):
            d += timedelta(days=1)
            continue
        try:
            inf = procesar_dia(d, a.salida, archivo)
        except ConnectionError as e:
            inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
        if not (inf.get("resultado") == "sin_boletin" and d >= hoy):
            escribir_json(ruta, inf)
        informes.append(inf)
        if inf["resultado"] != "sin_boletin":
            print(f"BORM {d}: {inf['resultado']} {inf.get('disposiciones', '')} anuncios, "
                  f"{inf.get('empleo_publico', '')} de empleo público")
        d += timedelta(days=1)
        time.sleep(a.pausa)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    for x in alertas[:30]:
        print(" -", x)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
