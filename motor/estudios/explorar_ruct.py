"""Sonda del RUCT con sesión: abre la ficha de un título y recorre las páginas de su memoria («solicitud»).

Las páginas de la solicitud solo devuelven valores dentro de la sesión abierta por la ficha, por eso no
sirven las sondas sin cookies. Uso (desde prueba.yml):
  python -m motor.estudios.explorar_ruct --codigos 4318301,3500092 --salida ruta/
Guarda cada página tal cual en {salida}/{codigo}/NN.html y un índice con URL, estado y tamaño.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests

from motor.http import USER_AGENT

BASE = "https://www.educacion.gob.es/ruct/"
FICHA = BASE + "estudio.action?codigoCiclo=SC&codigoTipo={tipo}&CodigoEstudio={codigo}&actual=estudios"
RE_ENLACE = re.compile(r'(?:href|action)="([^"]+)"')


def _limpiar(url: str) -> str:
    url = html.unescape(url)
    return re.sub(r";jsessionid=[0-9A-F]+", "", url)


def explorar(codigo: str, salida: Path, tipo: str = "M", maximo: int = 60, pausa: float = 1.0) -> list[dict]:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    carpeta = salida / codigo
    carpeta.mkdir(parents=True, exist_ok=True)
    pendientes = [FICHA.format(tipo=tipo, codigo=codigo)]
    vistos: set[str] = set()
    indice = []
    while pendientes and len(indice) < maximo:
        url = pendientes.pop(0)
        if url in vistos:
            continue
        vistos.add(url)
        try:
            r = s.get(url, timeout=30)
            estado, cuerpo = r.status_code, r.content
        except requests.RequestException as e:
            estado, cuerpo = 0, str(e).encode()
        n = len(indice) + 1
        (carpeta / f"{n:02d}.html").write_bytes(cuerpo)
        indice.append({"n": n, "url": url, "estado": estado, "bytes": len(cuerpo)})
        texto = cuerpo.decode("latin-1", "replace")
        for enlace in RE_ENLACE.findall(texto):
            destino = _limpiar(urljoin(url, enlace))
            if "/ruct/solicitud/" in destino and destino not in vistos and not destino.endswith((".css", ".js")):
                pendientes.append(destino)
        time.sleep(pausa)
    (carpeta / "indice.json").write_text(json.dumps(indice, ensure_ascii=False, indent=1), encoding="utf-8")
    return indice


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--codigos", required=True)
    p.add_argument("--tipo", default="M")
    p.add_argument("--maximo", type=int, default=60)
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    for codigo in a.codigos.split(","):
        indice = explorar(codigo.strip(), Path(a.salida), a.tipo, a.maximo)
        print(codigo, len(indice), "páginas", sum(1 for i in indice if i["estado"] == 200), "con 200")


if __name__ == "__main__":
    main()
