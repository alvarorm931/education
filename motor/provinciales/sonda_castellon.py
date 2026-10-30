"""Sonda del BOP de Castellón (bop.dipcas.es/PortalBOP): portal JSF/PrimeFaces con sesión.

Abre el buscador (lista de los últimos boletines, cada uno un enlace de PrimeFaces) y pulsa «Último Boletín» y el
primer boletín de la lista, guardando cada respuesta para estudiar el formato antes de programar el conector.

Uso (con prueba.yml): python -m motor.provinciales.sonda_castellon --salida ruta/
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import requests

from motor.http import USER_AGENT, comprobar_robots
from motor.provinciales.sonda_dival import campos_formulario

BUSCADOR = "https://bop.dipcas.es/PortalBOP/buscador/"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    a = p.parse_args(argv)
    a.salida.mkdir(parents=True, exist_ok=True)
    comprobar_robots(BUSCADOR)  # boletín oficial (motor/http.py): solo se comprueba que no esté cerrado por privacidad
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    indice = []
    r = s.get(BUSCADOR, timeout=40)
    (a.salida / "1-buscador.html").write_bytes(r.content)
    indice.append(f"1 GET {r.status_code} {len(r.content)} {r.url}")
    cab = {"Faces-Request": "partial/ajax", "X-Requested-With": "XMLHttpRequest",
           "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "Referer": r.url}
    pruebas = [("buttons", "buttons:j_idt70", "busquedaBoletinesForm"),
               ("busquedaBoletinesForm", "busquedaBoletinesForm:j_idt74:0:j_idt75", "busquedaBoletinesForm")]
    n = 2
    for form, fuente, render in pruebas:
        try:
            accion, campos = campos_formulario(r.text, form)
        except AttributeError:
            indice.append(f"{n} sin formulario {form}")
            n += 1
            continue
        url = requests.compat.urljoin(r.url, accion)
        campos.update({"javax.faces.partial.ajax": "true", "javax.faces.source": fuente,
                       "javax.faces.partial.execute": fuente, "javax.faces.partial.render": render, fuente: fuente})
        time.sleep(1)
        r2 = s.post(url, data=campos, headers=cab, timeout=60)
        (a.salida / f"{n}-{form}.xml").write_bytes(r2.content)
        indice.append(f"{n} POST {fuente} {r2.status_code} {len(r2.content)} {url}")
        redir = re.search(r'<redirect url="([^"]+)"', r2.text)
        if redir:
            time.sleep(1)
            r3 = s.get(requests.compat.urljoin(url, redir.group(1).replace("&amp;", "&")), timeout=60)
            (a.salida / f"{n}-redireccion.html").write_bytes(r3.content)
            indice.append(f"{n} GET redirección {r3.status_code} {len(r3.content)} {r3.url}")
        n += 1
    (a.salida / "indice.txt").write_text("\n".join(indice), encoding="utf-8")
    print("\n".join(indice))
    return 0


if __name__ == "__main__":
    sys.exit(main())
