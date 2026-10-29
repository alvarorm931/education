"""Descarga del texto completo de disposiciones del BOE (documento XML de cada BOE-A).

Uso:
  python -m motor.boe.texto --ids BOE-A-2026-20413,BOE-A-2026-20626 --salida ruta/

Guarda el original en archivo/boe-texto/ y el texto plano en datos/boe/textos/{id}.json.
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


def texto_plano(xml: bytes) -> dict:
    raiz = ET.fromstring(xml)
    meta = raiz.find("metadatos")

    def m(etiqueta: str) -> str | None:
        n = meta.find(etiqueta) if meta is not None else None
        return " ".join(n.text.split()) if n is not None and n.text else None

    cuerpo = raiz.find("texto")
    parrafos = []
    if cuerpo is not None:
        for nodo in cuerpo.iter():
            if nodo.tag in {"p", "td", "th", "li"}:
                t = " ".join("".join(nodo.itertext()).split())
                if t:
                    parrafos.append(t)
    return {
        "titulo": m("titulo"),
        "fecha_publicacion": m("fecha_publicacion"),
        "departamento": m("departamento"),
        "rango": m("rango"),
        "texto": "\n".join(parrafos),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ids", required=True, help="identificadores separados por comas")
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    ids = [x.strip() for x in a.ids.split(",") if x.strip()]
    malos = [x for x in ids if not RE_ID.match(x)]
    if malos:
        p.error(f"identificadores no válidos: {malos}")

    archivo = Archivo(a.salida / "archivo")
    errores = 0
    for i, ident in enumerate(ids):
        url = URL_XML.format(id=ident)
        resp = obtener(url, accept="application/xml")
        if resp.status != 200:
            print(f"{ident}: HTTP {resp.status}")
            errores += 1
            continue
        try:
            datos = texto_plano(resp.contenido)
        except ET.ParseError as e:
            print(f"{ident}: XML no válido ({e})")
            errores += 1
            continue
        fp = datos.get("fecha_publicacion") or ""
        fecha = date(int(fp[:4]), int(fp[4:6]), int(fp[6:8])) if len(fp) == 8 else datetime.now(ZoneInfo("Europe/Madrid")).date()
        captura = archivo.guardar(FUENTE, fecha, resp.contenido, url, "xml", resp.status, resp.cabeceras)
        destino = a.salida / "datos" / "boe" / "textos" / f"{ident}.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps({"identificador": ident, **datos, "captura_sha256": captura["sha256"],
                                       "capturado": captura["capturado"], "url": url},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{ident}: {len(datos['texto'])} caracteres")
        if i < len(ids) - 1:
            time.sleep(a.pausa)
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
