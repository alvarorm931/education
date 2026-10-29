"""Sonda de URL con el cliente del motor (reintentos, cifrados compatibles e intermedios de motor/certificados/).

Sirve para las webs que la sonda con curl no puede leer (cadena de certificados incompleta, cifrados antiguos).

Uso (desde GitHub, con prueba.yml): python -m motor.provinciales.sonda_urls --salida ruta/ --urls url1,url2
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from motor.http import obtener, sesion_tls_compatible


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--urls", required=True)
    a = p.parse_args(argv)
    a.salida.mkdir(parents=True, exist_ok=True)
    s = sesion_tls_compatible()
    indice = []
    for i, u in enumerate(a.urls.split(","), 1):
        try:
            r = obtener(u, sesion=s, intentos=2)
            (a.salida / f"{i}.cuerpo").write_bytes(r.contenido)
            indice.append(f"{i} {r.status} {r.cabeceras.get('Content-Type') or r.cabeceras.get('content-type')} "
                          f"{len(r.contenido)} {r.url}")
        except ConnectionError as e:
            indice.append(f"{i} error {e}")
        time.sleep(1)
    (a.salida / "indice.txt").write_text("\n".join(indice) + "\n", encoding="utf-8")
    print("\n".join(indice))
    return 0


if __name__ == "__main__":
    sys.exit(main())
