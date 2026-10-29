"""Texto completo de cada disposición del BOE (documento XML de cada BOE-A), sin datos personales.

Uso:
  python -m motor.boe.texto --ids BOE-A-2026-20413,BOE-A-2026-20626 --salida ruta/
  python -m motor.boe.texto --pendientes --salida ruta/ --max-minutos 300

El original completo se guarda en archivo/boe-texto/ (privado). En datos/boe/textos/AAAA/MM/{id}.json
se guarda el texto con estas reglas:
  - tablas con datos de personas (DNI, apellidos, nombre): solo número de filas y cabecera;
  - párrafos con un documento de identidad: se cuentan y no se guardan;
  - referencias a otras disposiciones (bloque «análisis» del BOE): se guardan, sirven para unir actos.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo
from motor.http import obtener

URL_XML = "https://www.boe.es/diario_boe/xml.php?id={id}"
RE_ID = re.compile(r"^BOE-[AB]-\d{4}-\d+$")
FUENTE = "boe-texto"
MADRID = ZoneInfo("Europe/Madrid")

RE_DOCUMENTO = re.compile(
    r"(\b\d{8}\s?[A-Z]\b|\b[XYZ]\d{7}\s?[A-Z]\b|\*{2,}\d{3,5}\*{1,}|\b\d{3,4}\*{3,}|\*{3,}\d{4}[A-Z]?\b|\bX{3,}\d{3,}X*)"
)
CABECERA_PERSONAL = re.compile(r"\b(dni|nif|nie|apellidos|nombre|documento|pasaporte)\b", re.IGNORECASE)


def _limpio(nodo: ET.Element) -> str:
    return " ".join("".join(nodo.itertext()).split())


def _tabla(tabla: ET.Element) -> dict:
    filas = [[_limpio(c) for c in fila if c.tag in {"td", "th"}] for fila in tabla.iter("tr")]
    filas = [f for f in filas if any(f)]
    cabecera = filas[0] if filas else []
    contenido = " ".join(" ".join(f) for f in filas)
    personal = bool(CABECERA_PERSONAL.search(" ".join(cabecera))) or len(RE_DOCUMENTO.findall(contenido)) >= 2
    if personal:
        return {"filas": max(len(filas) - 1, 0), "cabecera": cabecera, "datos_personales": True}
    return {"filas": len(filas), "contenido": filas, "datos_personales": False}


def texto_plano(xml: bytes) -> dict:
    raiz = ET.fromstring(xml)
    meta = raiz.find("metadatos")

    def m(etiqueta: str) -> str | None:
        n = meta.find(etiqueta) if meta is not None else None
        return " ".join(n.text.split()) if n is not None and n.text else None

    parrafos, tablas, omitidos = [], [], 0
    cuerpo = raiz.find("texto")
    if cuerpo is not None:
        pila = list(cuerpo)
        while pila:
            nodo = pila.pop(0)
            if nodo.tag == "table":
                tablas.append(_tabla(nodo))
            elif nodo.tag in {"p", "li"}:
                t = _limpio(nodo)
                if not t:
                    continue
                if RE_DOCUMENTO.search(t):
                    omitidos += 1
                else:
                    parrafos.append(t)
            else:
                pila[0:0] = list(nodo)

    referencias = []
    for grupo in ("anteriores", "posteriores"):
        for ref in raiz.findall(f"analisis/referencias/{grupo}/*"):
            referencias.append({
                "sentido": grupo,
                "referencia": ref.get("referencia"),
                "relacion": _limpio(ref.find("palabra")) if ref.find("palabra") is not None else None,
                "texto": _limpio(ref.find("texto")) if ref.find("texto") is not None else None,
            })

    return {
        "titulo": m("titulo"),
        "fecha_publicacion": m("fecha_publicacion"),
        "departamento": m("departamento"),
        "rango": m("rango"),
        "texto": "\n".join(parrafos),
        "tablas": tablas,
        "parrafos_omitidos_por_datos_personales": omitidos,
        "referencias": referencias,
    }


def ruta_texto(raiz: Path, ident: str, fecha: str) -> Path:
    """fecha: AAAA-MM-DD o AAAAMMDD."""
    f = fecha.replace("-", "")
    return raiz / "datos" / "boe" / "textos" / f[:4] / f[4:6] / f"{ident}.json"


def pendientes(raiz: Path) -> list[tuple[str, str]]:
    """(identificador, fecha) de los anuncios de oposiciones sin texto descargado, del más reciente al más antiguo."""
    lista = []
    for fichero in sorted((raiz / "datos" / "boe" / "oposiciones").glob("*/*/*.jsonl"), reverse=True):
        for linea in fichero.read_text(encoding="utf-8").splitlines():
            fila = json.loads(linea)
            ident, fecha = fila.get("identificador"), fila.get("fecha")
            if ident and fecha and not ruta_texto(raiz, ident, fecha).exists():
                lista.append((ident, fecha))
    return lista


def descargar(ident: str, raiz: Path, archivo: Archivo) -> str:
    url = URL_XML.format(id=ident)
    resp = obtener(url, accept="application/xml")
    if resp.status != 200:
        return f"HTTP {resp.status}"
    try:
        datos = texto_plano(resp.contenido)
    except ET.ParseError as e:
        return f"XML no válido ({e})"
    fp = datos.get("fecha_publicacion") or ""
    fecha = date(int(fp[:4]), int(fp[4:6]), int(fp[6:8])) if len(fp) == 8 else datetime.now(MADRID).date()
    captura = archivo.guardar(FUENTE, fecha, resp.contenido, url, "xml", resp.status, resp.cabeceras)
    destino = ruta_texto(raiz, ident, fecha.isoformat())
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps({"identificador": ident, **datos, "captura_sha256": captura["sha256"],
                                   "capturado": captura["capturado"], "url": url},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
    return "ok"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ids", help="identificadores separados por comas")
    p.add_argument("--pendientes", action="store_true", help="todos los anuncios de oposiciones sin texto")
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--pausa", type=float, default=0.7)
    p.add_argument("--max", type=int, default=0, help="máximo de documentos (0 = sin límite)")
    p.add_argument("--max-minutos", type=float, default=0, help="parar al llegar a este tiempo (0 = sin límite)")
    a = p.parse_args(argv)

    if a.ids:
        trabajo = [(x.strip(), "") for x in a.ids.split(",") if x.strip()]
        malos = [x for x, _ in trabajo if not RE_ID.match(x)]
        if malos:
            p.error(f"identificadores no válidos: {malos}")
    elif a.pendientes:
        trabajo = pendientes(a.salida)
    else:
        p.error("indica --ids o --pendientes")
    if a.max:
        trabajo = trabajo[: a.max]

    archivo = Archivo(a.salida / "archivo")
    inicio, hechos, errores = time.monotonic(), 0, []
    print(f"Documentos a descargar: {len(trabajo)}")
    for i, (ident, _) in enumerate(trabajo):
        if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
            print(f"Tiempo agotado: quedan {len(trabajo) - i} para la siguiente ejecución")
            break
        try:
            r = descargar(ident, a.salida, archivo)
        except ConnectionError as e:
            r = str(e)
        if r == "ok":
            hechos += 1
        else:
            errores.append(f"{ident}: {r}")
        if i < len(trabajo) - 1:
            time.sleep(a.pausa)
    print(f"Descargados: {hechos}. Errores: {len(errores)}")
    for e in errores[:50]:
        print(" -", e)
    return 1 if errores and not hechos else 0


if __name__ == "__main__":
    sys.exit(main())
