"""Auditoría de robots.txt: ¿permite cada servidor las direcciones que piden los conectores?

Para cada fuente, toma direcciones de ejemplo de lo que piden de verdad sus conectores (fuentes/urls_ejemplo.json:
sumario del día, ficha y PDF de un anuncio) y comprueba, con el robots.txt de cada servidor (RFC 9309), si nuestro
agente puede pedirlas. Una petición prohibida por robots.txt no se hace: el conector se limita a lo permitido
(por ejemplo, solo los títulos del sumario). Se ejecuta desde GitHub con prueba.yml.

Uso: python -m motor.robots_auditoria --urls fuentes/urls_ejemplo.json --salida ruta/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse
from motor import http


def auditar(urls: dict[str, list[str]]) -> dict:
    """Con el mismo lector de robots.txt que usa el motor en cada descarga (motor/http.py)."""
    out = {}
    for fuente, lista in urls.items():
        filas = []
        for u in lista:
            ok, regla = http.robots_de(u).regla(u)
            filas.append({"url": u, "permitida": ok, "regla": regla, "robots": http.ROBOTS_ESTADO.get(http._origen(u))})
        out[fuente] = {"todas_permitidas": all(f["permitida"] for f in filas), "urls": filas}
    textos = {o: {"estado": http.ROBOTS_ESTADO.get(o), "reglas": len(r.reglas), "texto": http.ROBOTS_TEXTO.get(o)}
              for o, r in http._ROBOTS.items()}
    return {"fuentes": out, "robots": textos}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--urls", type=Path, default=Path("fuentes/urls_ejemplo.json"))
    p.add_argument("--salida", type=Path, default=Path("."))
    a = p.parse_args(argv)
    res = auditar(json.loads(a.urls.read_text(encoding="utf-8")))
    destino = a.salida / "datos" / "robots_auditoria.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for f, v in res["fuentes"].items():
        malas = [x["url"] for x in v["urls"] if not x["permitida"]]
        print(f"{f:28} {'ok' if not malas else 'PROHIBIDAS: ' + ' '.join(malas)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
