"""Sonda del calendario del BOP de Albacete (solo responde desde España): días con boletín y sumario de un día por
los servicios que usa su portada (servicesajax/obtenerdiaspublicacion y obtenersumariobop, con el token de la
página). Imprime estados y el principio de cada respuesta; no guarda nada.

Uso: python -m motor.provinciales.sonda_albacete [FECHA ...]
"""

from __future__ import annotations

import base64
import html
import json
import re
import sys
import time

import requests

from motor.http import USER_AGENT, comprobar_robots

BASE = "https://bop.dipualba.es/"


def main(argv: list[str] | None = None) -> int:
    fechas = (argv if argv is not None else sys.argv[1:]) or ["2022-01-01", "01/01/2022", "2026-10-01"]
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    comprobar_robots(BASE, s)
    r = s.get(BASE, timeout=60)
    token = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', r.text)
    print("portada", r.status_code, len(r.content), "token" if token else "SIN TOKEN")
    cab = {"RequestVerificationToken": token.group(1) if token else "", "X-Requested-With": "XMLHttpRequest"}
    eventos = []
    for f in fechas:
        time.sleep(1)
        x = s.get(BASE + "servicesajax/obtenerdiaspublicacion", params={"a": f}, headers=cab, timeout=60)
        print("dias", f, x.status_code, x.text[:200].replace("\n", " "))
        try:
            d = x.json()
            lista = json.loads(base64.b64decode(d.get("yedata") or "") or b"[]")
            print("  eventos:", len(lista), json.dumps(lista[:2], ensure_ascii=False)[:600])
            eventos += lista
        except Exception as e:  # noqa: BLE001 - es una sonda
            print("  no es JSON con yedata:", type(e).__name__, e)
    for ev in eventos[:2]:
        fb = (ev.get("extendedProps") or {}).get("fechabop") or ev.get("fechabop") or ev.get("start")
        time.sleep(1)
        x = s.post(BASE + "servicesajax/obtenersumariobop", data={"a": fb}, headers=cab, timeout=60)
        print("sumario", fb, x.status_code, len(x.content))
        try:
            h = x.json().get("yedata") or ""
            t = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", h)).split())
            print("  ", t[:900])
            print("   clases:", sorted(set(re.findall(r'class="([^"]+)"', h)))[:25])
            print("   enlaces:", sorted(set(re.sub(r"\d+", "N", u) for u in re.findall(r'href="([^"]+)"', h)))[:10])
        except Exception as e:  # noqa: BLE001
            print("  respuesta no JSON:", x.text[:300])
    return 0


if __name__ == "__main__":
    sys.exit(main())
