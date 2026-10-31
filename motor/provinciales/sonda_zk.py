"""Sonda de una aplicación ZK (BOP de Almería, app.dipalme.org/bop): pide las páginas en una misma sesión, como un
navegador que sigue la redirección de la portada, e imprime lo que trae cada una (las definiciones de los
componentes, donde ZK suele llevar los datos iniciales) y sus enlaces a PDF. Lo impreso pasa por el filtro de datos
de personas de las sondas.

Uso (prueba.yml): python -m motor.provinciales.sonda_zk https://app.dipalme.org/bop/publico.zul publicoValidar.zul
"""

from __future__ import annotations

import argparse
import re
import sys
from urllib.parse import urljoin

import requests

from motor.http import obtener
from motor.provinciales.sonda_pdf_texto import _seguro

RE_PDF = re.compile(r"""(?:https?:)?[\w/.:%-]*?\.pdf[^\s"'<>\\]*""", re.IGNORECASE)
RE_ZUL = re.compile(r"""['"]([\w/.-]+\.zul[^'"]*)['"]""")
RE_SCRIPT = re.compile(r"""src="([^"]+\.js[^"]*)\"""")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("inicio")
    p.add_argument("siguientes", nargs="*", help="páginas relativas a la primera, en la misma sesión")
    p.add_argument("--scripts", default="", help="trozo del nombre de los .js propios que se imprimen (dipalme)")
    p.add_argument("--caracteres", type=int, default=20000)
    p.add_argument("--salida", default="sonda")
    a = p.parse_args(argv)
    s = requests.Session()
    urls = [a.inicio] + [urljoin(a.inicio, x) for x in a.siguientes]
    for url in urls:
        r = obtener(url, sesion=s, accept="text/html,*/*")
        cuerpo = r.contenido.decode("utf-8", errors="replace")
        print(f"===== {r.status} {len(r.contenido)} {r.url} {r.cabeceras.get('content-type')}")
        print("cookies:", sorted(s.cookies.keys()))
        print("zul citados:", sorted(set(RE_ZUL.findall(cuerpo)))[:30])
        print("pdf citados:", sorted(set(RE_PDF.findall(cuerpo)))[:30])
        print(_seguro(cuerpo)[:a.caracteres])
        if a.scripts:
            for src in RE_SCRIPT.findall(cuerpo):
                if a.scripts in src:
                    js = obtener(urljoin(r.url, src), sesion=s)
                    print(f"----- script {src[:120]} ({len(js.contenido)})")
                    print(js.contenido.decode("utf-8", errors="replace")[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
