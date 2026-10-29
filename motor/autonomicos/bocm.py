"""Conector del Boletín Oficial de la Comunidad de Madrid (BOCM).

Formato verificado el 29/10/2026 desde GitHub:
  - Sumario diario en XML: https://www.bocm.es/boletin/CM_Boletin_BOCM/AAAA/MM/DD/BOCM-AAAAMMDDN.xml
    El servidor resuelve por la fecha (el número N no se comprueba); devuelve 404 si ese día no hay boletín.
    Estructura: sumario > metadatos(numero, fecha_publicacion) > diario > secciones > seccion[nombre]
                > apartado[nombre] > organismo[nombre] > disposicion[numero](identificador, titulo, url_xml, url_pdf)
  - Cada disposición en XML: documento > metadatos(titulo, seccion, paginas) + texto (texto plano).
  - Madrid es comunidad de una sola provincia: lo local (ayuntamientos) se publica aquí, sección III, con títulos
    del tipo «Alcobendas. Ofertas de empleo. Proceso selectivo».

Uso:
  python -m motor.autonomicos.bocm --salida ruta/                       # ayer y hoy
  python -m motor.autonomicos.bocm --desde 2022-01-01 --saltar-existentes --max-minutos 30 --salida ruta/
  python -m motor.autonomicos.bocm --textos --max-minutos 30 --salida ruta/   # textos pendientes

Guarda en datos/autonomicos/bocm/: dias/ (informe por día), disposiciones/ (todas, sin texto),
oposiciones/ (selección de empleo público) y textos/ (texto limpio de datos personales).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo
from motor.boe.clasificar import REGLAS_ACTO, REGLAS_MODALIDAD, _primera, alcance, normalizar
from motor.http import obtener
from motor.limpieza import parrafos_seguros

FUENTE = "bocm"
MADRID = ZoneInfo("Europe/Madrid")
BASE = "https://www.bocm.es/boletin/CM_Boletin_BOCM"
MATERIAS_EMPLEO = ("ofertas de empleo", "personal", "oposiciones", "empleo publico")


def url_sumario(d: date) -> str:
    return f"{BASE}/{d:%Y}/{d:%m}/{d:%d}/BOCM-{d:%Y%m%d}1.xml"


def _t(nodo: ET.Element | None, etiqueta: str) -> str | None:
    if nodo is None:
        return None
    x = nodo.findtext(etiqueta)
    return " ".join(x.split()) if x else None


def parsear_sumario(xml: bytes) -> dict:
    raiz = ET.fromstring(xml)
    meta = raiz.find("metadatos")
    if meta is None:
        raise ValueError("falta metadatos: posible cambio de formato")
    disposiciones = []
    for seccion in raiz.iter("seccion"):
        for apartado in seccion.iter("apartado"):
            for organismo in apartado.iter("organismo"):
                for d in organismo.iter("disposicion"):
                    disposiciones.append({
                        "id": _t(d, "identificador"),
                        "numero_disposicion": d.get("numero"),
                        "titulo": " ".join((d.findtext("titulo") or "").replace("–", " ").split()),
                        "seccion": seccion.get("nombre"),
                        "apartado": apartado.get("nombre"),
                        "organismo": organismo.get("nombre"),
                        "url_html": _t(d, "url_html"),
                        "url_xml": _t(d, "url_xml"),
                        "url_pdf": _t(d, "url_pdf"),
                    })
    return {"numero": _t(meta, "numero"), "fecha": (_t(meta, "fecha_publicacion") or "").replace("/", "-"),
            "disposiciones": disposiciones}


def es_empleo_publico(d: dict) -> bool:
    seccion = normalizar(d.get("seccion") or "")
    apartado = normalizar(d.get("apartado") or "")
    titulo = normalizar(d.get("titulo") or "")
    if seccion.startswith("i.") and "autoridades y personal" in apartado:
        return True
    if "administracion local" in seccion:
        partes = [p.strip() for p in titulo.split(".")]
        return len(partes) >= 2 and any(m == partes[1] or partes[1].startswith(m) for m in MATERIAS_EMPLEO)
    return False


def ambito(d: dict) -> str:
    s = normalizar(d.get("seccion") or "")
    if "administracion local" in s:
        return "local"
    if "universidad" in normalizar(d.get("organismo") or "") or "universidad" in normalizar(d.get("titulo") or "")[:80]:
        return "universidad"
    if s.startswith("i."):
        return "autonomico"
    return "otro"


def municipio_y_materia(titulo: str) -> tuple[str | None, str | None, str | None]:
    partes = [p.strip() for p in titulo.split(".") if p.strip()]
    return (partes[0] if partes else None, partes[1] if len(partes) > 1 else None,
            ". ".join(partes[2:]) if len(partes) > 2 else None)


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "autonomicos" / "bocm"


def _ruta(raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


def procesar_dia(d: date, raiz: Path, archivo: Archivo) -> dict:
    url = url_sumario(d)
    resp = obtener(url, accept="application/xml")
    informe = {"fecha": d.isoformat(), "status": resp.status, "alertas": []}
    if resp.status == 404:
        informe["resultado"] = "sin_boletin"
        if d.weekday() < 5:
            informe["alertas"].append(f"BOCM {d}: día laborable sin boletín (¿festivo?)")
        return informe
    if resp.status != 200:
        informe["resultado"] = "error_http"
        informe["alertas"].append(f"BOCM {d}: HTTP {resp.status}")
        return informe
    try:
        s = parsear_sumario(resp.contenido)
    except (ET.ParseError, ValueError) as e:
        informe["resultado"] = "error_formato"
        informe["alertas"].append(f"BOCM {d}: {e}")
        return informe
    if s["fecha"] and s["fecha"] != d.isoformat():
        informe["resultado"] = "error_formato"
        informe["alertas"].append(f"BOCM {d}: el servidor devolvió el boletín de {s['fecha']}")
        return informe

    captura = archivo.guardar(FUENTE, d, resp.contenido, url, "xml", resp.status, resp.cabeceras)
    filas, empleo = [], []
    for x in s["disposiciones"]:
        x.update({"fecha": d.isoformat(), "boletin": s["numero"], "fuente": "BOCM", "captura_sha256": captura["sha256"]})
        filas.append(x)
        if es_empleo_publico(x):
            t = normalizar(x["titulo"])
            mun, materia, asunto = municipio_y_materia(x["titulo"]) if ambito(x) == "local" else (None, None, None)
            modalidad = _primera(REGLAS_MODALIDAD, t)
            empleo.append({**x, "ambito": ambito(x), "municipio": mun, "materia": materia, "asunto": asunto,
                           "tipo_acto": _primera(REGLAS_ACTO, t) or "otro", "modalidad": modalidad,
                           "alcance": alcance(t, modalidad, x.get("apartado"))})
    for carpeta, contenido in (("disposiciones", filas), ("oposiciones", empleo)):
        ruta = _ruta(raiz, carpeta, d)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in contenido), encoding="utf-8")
    informe.update({"resultado": "ok", "numero": s["numero"], "sha256": captura["sha256"],
                    "disposiciones": len(filas), "empleo_publico": len(empleo)})
    if not filas:
        informe["alertas"].append(f"BOCM {d}: boletín sin disposiciones (posible cambio de formato)")
    return informe


def texto_disposicion(xml: bytes) -> dict:
    raiz = ET.fromstring(xml)
    lineas = [" ".join(l.split()) for l in (raiz.findtext("texto") or "").splitlines()]
    guardadas, omitidas = parrafos_seguros([l for l in lineas if l])
    meta = raiz.find("metadatos")
    return {"titulo": _t(meta, "titulo"), "paginas": [_t(meta, "pagina_inicial"), _t(meta, "pagina_final")],
            "texto": "\n".join(guardadas), "parrafos_omitidos_por_datos_personales": omitidas}


def textos_pendientes(raiz: Path) -> list[dict]:
    lista = []
    for f in sorted((_base(raiz) / "oposiciones").glob("*/*/*.jsonl"), reverse=True):
        for linea in f.read_text(encoding="utf-8").splitlines():
            x = json.loads(linea)
            destino = _base(raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"
            if x.get("url_xml") and not destino.exists():
                lista.append(x)
    # Primero lo de acceso abierto; dentro, de lo más reciente a lo más antiguo (orden ya inverso por fichero)
    return sorted(lista, key=lambda x: 0 if x.get("alcance") in (None, "acceso") else 1)


def descargar_textos(raiz: Path, archivo: Archivo, max_minutos: float, pausa: float) -> tuple[int, int]:
    inicio, hechos, errores = time.monotonic(), 0, 0
    for x in textos_pendientes(raiz):
        if max_minutos and (time.monotonic() - inicio) / 60 > max_minutos:
            break
        try:
            r = obtener(x["url_xml"], accept="application/xml")
        except ConnectionError:
            errores += 1
            continue
        if r.status != 200:
            errores += 1
            continue
        try:
            datos = texto_disposicion(r.contenido)
        except ET.ParseError:
            errores += 1
            continue
        d = date.fromisoformat(x["fecha"])
        captura = archivo.guardar(FUENTE + "-texto", d, r.contenido, x["url_xml"], "xml", r.status, r.cabeceras)
        destino = _base(raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps({"id": x["id"], **datos, "captura_sha256": captura["sha256"],
                                       "capturado": captura["capturado"], "url": x["url_xml"]},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
        hechos += 1
        time.sleep(pausa)
    return hechos, errores


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=date.fromisoformat, default=hoy - timedelta(days=1))
    p.add_argument("--hasta", type=date.fromisoformat, default=hoy)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--saltar-existentes", action="store_true")
    p.add_argument("--textos", action="store_true", help="descargar los textos pendientes en lugar de sumarios")
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=0.7)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo")

    if a.textos:
        hechos, errores = descargar_textos(a.salida, archivo, a.max_minutos, a.pausa)
        print(f"BOCM textos: {hechos} descargados, {errores} errores, {len(textos_pendientes(a.salida))} pendientes")
        return 0

    inicio, informes = time.monotonic(), []
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
            inf = procesar_dia(d, a.salida, archivo)
        except ConnectionError as e:
            inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(inf, ensure_ascii=False, indent=1), encoding="utf-8")
        informes.append(inf)
        print(f"BOCM {d}: {inf.get('resultado')} {inf.get('disposiciones', '')} disposiciones, "
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
