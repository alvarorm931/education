"""Sonda del DOCM (Castilla-La Mancha) con sesión: el portal pide la cookie de sesión para cambiar de fecha.

Uso (desde GitHub, con prueba.yml): python -m motor.autonomicos.sonda_docm --salida ruta/
Guarda cada respuesta en la carpeta de salida para estudiar el formato antes de programar el conector.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import requests

from motor.http import USER_AGENT


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    a = p.parse_args(argv)
    a.salida.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    urls = [
        "https://docm.jccm.es/portaldocm/sumario.do",
        "https://docm.jccm.es/docm/cambiarBoletin.do?fecha=20261028",
        "https://docm.jccm.es/portaldocm/cambiarBoletin.do?fecha=20261028",
        "https://docm.jccm.es/docm/cambiarBoletin.do?fecha=20220103",
    ]
    indice = []
    for i, u in enumerate(urls, 1):
        try:
            r = s.get(u, timeout=40)
            (a.salida / f"{i}.html").write_bytes(r.content)
            indice.append(f"{i} {r.status_code} {len(r.content)} {r.url} {r.headers.get('content-type')}")
            # Del primer sumario válido, probar la versión HTML de una disposición
            if r.status_code == 200 and "verArchivoHtml" in r.text and not any("verArchivo" in x for x in urls):
                m = re.search(r"verArchivoHtml\.do\?ruta=([^'&]+)&(?:amp;)?tipo=rutaDocm", r.text)
                if m:
                    base = r.url.rsplit("/", 1)[0]
                    urls.append(f"{base}/verArchivoHtml.do?ruta={m.group(1)}&tipo=rutaDocm")
                m = re.search(r"detalleDocumento\.do\?idDisposicion=(\d+)", r.text)
                if m:
                    base = r.url.rsplit("/", 1)[0]
                    urls.append(f"{base}/detalleDocumento.do?idDisposicion={m.group(1)}")
        except requests.RequestException as e:
            indice.append(f"{i} error {e} {u}")
        time.sleep(1)
    indice.append("cookies: " + ", ".join(sorted(s.cookies.keys())))
    (a.salida / "indice.txt").write_text("\n".join(indice) + "\n", encoding="utf-8")
    print("\n".join(indice))
    return 0


if __name__ == "__main__":
    sys.exit(main())
