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
from motor.http import obtener
from motor.robots import Robots


def robots_de(origen: str) -> tuple[Robots, dict]:
    try:
        r = obtener(origen + "/robots.txt", accept="text/plain", intentos=2, limite_total=60)
    except (ConnectionError, TimeoutError) as e:
        # sin respuesta: se trata como prohibido hasta poder leerlo (RFC 9309, 2.3.1.4)
        return Robots(todo_prohibido=True), {"estado": "sin_respuesta", "error": str(e)[:200]}
    tipo = (r.cabeceras.get("content-type") or r.cabeceras.get("Content-Type") or "").lower()
    if r.status >= 500:
        return Robots(todo_prohibido=True), {"estado": f"http_{r.status}", "regla": "error de servidor: no se rastrea"}
    if r.status != 200 or "html" in tipo:
        return Robots(), {"estado": f"http_{r.status}" if r.status != 200 else "html",
                          "regla": "sin robots.txt: todo permitido"}
    texto = r.contenido.decode("utf-8", errors="replace")
    lineas = texto.splitlines()
    return Robots(texto), {"estado": "ok", "lineas": len(lineas), "texto": texto[:20000],
                "disallow": [l.strip() for l in lineas if l.lower().startswith("disallow")][:40]}


def auditar(urls: dict[str, list[str]]) -> dict:
    cache: dict[str, tuple[Robots, dict]] = {}
    out = {}
    for fuente, lista in urls.items():
        filas = []
        for u in lista:
            p = urlparse(u)
            origen = f"{p.scheme}://{p.netloc}"
            if origen not in cache:
                cache[origen] = robots_de(origen)
            rp, info = cache[origen]
            ok, regla = rp.regla(u)
            filas.append({"url": u, "permitida": ok, "regla": regla,
                          "robots": info["estado"]})
        out[fuente] = {"todas_permitidas": all(f["permitida"] for f in filas), "urls": filas}
    return {"fuentes": out, "robots": {o: i for o, (_, i) in cache.items()}}


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
