"""Sonda de tiempos: pide cada dirección con motor.http.obtener (robots.txt incluido) y anota estado, tamaño,
segundos y los primeros bytes. No guarda el contenido (puede traer datos de personas).

Uso: python -m motor.provinciales.sonda_tiempos URL [URL...]
"""

from __future__ import annotations

import sys
import time

from motor.http import obtener


def main(argv: list[str] | None = None) -> int:
    for url in argv if argv is not None else sys.argv[1:]:
        t = time.monotonic()
        try:
            r = obtener(url, accept="application/pdf, text/html")
            print(f"{r.status} {len(r.contenido)} bytes {time.monotonic() - t:.1f} s {r.contenido[:8]!r} {url}")
        except Exception as e:  # noqa: BLE001 - es una sonda: se anota cualquier error
            print(f"ERROR {type(e).__name__} {time.monotonic() - t:.1f} s {str(e)[:300]} {url}")
        time.sleep(1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
