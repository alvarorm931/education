"""Sonda del «Buscador de boletines» del BOP de Castellón (JSF con sesión): abre el buscador, pulsa el botón y
describe el formulario que sale (campos, botones, opciones) y, si hay campos de fecha, prueba una búsqueda de enero
de 2022. Imprime estructura y títulos; no guarda nada.

Uso (con prueba.yml): python -m motor.provinciales.sonda_castellon_buscador
"""

from __future__ import annotations

import html
import re
import sys
import time

import requests

from motor.http import USER_AGENT, comprobar_robots
from motor.provinciales.sonda_dival import campos_formulario

URL = "https://bop.dipcas.es/PortalBOP/buscador/"


def describir(h: str) -> None:
    for m in re.finditer(r'<form[^>]*id="([^"]+)"', h):
        i = m.start()
        f = h[i:h.find("</form>", i)]
        campos = re.findall(r'<(input|select|button)[^>]*(?:name|id)="([^"]+)"[^>]*', f)
        print("form", m.group(1), [(t, n) for t, n in campos][:40])
        for et in re.findall(r"<label[^>]*>(.*?)</label>", f, re.S)[:20]:
            print("   etiqueta:", " ".join(html.unescape(re.sub(r"<[^>]+>", " ", et)).split())[:80])


def main(argv: list[str] | None = None) -> int:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    comprobar_robots(URL, s)
    r = s.get(URL, timeout=60)
    accion, campos = campos_formulario(r.text, "buttons")
    campos["buttons:j_idt72"] = ""
    time.sleep(1)
    r2 = s.post(requests.compat.urljoin(r.url, accion), data=campos, timeout=60)
    print("buscador", r2.status_code, len(r2.content), r2.url)
    describir(r2.text)
    t = " ".join(html.unescape(re.sub(r"<script.*?</script>|<[^>]+>", " ", r2.text, flags=re.S)).split())
    i = t.find("Buscador")
    print("texto:", t[i:i + 1500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
