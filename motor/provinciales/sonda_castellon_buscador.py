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


ANTIGUOS = "https://bop.dipcas.es/PortalBOP/boletinesAntiguos/"
AJAX = {"Faces-Request": "partial/ajax", "X-Requested-With": "XMLHttpRequest"}


def _ajax(s: requests.Session, url: str, campos: dict, fuente: str, render: str) -> str:
    datos = {**campos, "javax.faces.partial.ajax": "true", "javax.faces.source": fuente,
             "javax.faces.partial.execute": "@all", "javax.faces.partial.render": render, fuente: fuente}
    time.sleep(1)
    r = s.post(url, data=datos, headers={**AJAX, "Referer": ANTIGUOS}, timeout=60)
    print("ajax", fuente, r.status_code, len(r.content))
    return r.text


def main(argv: list[str] | None = None) -> int:
    """Boletines anteriores: búsqueda por fechas (enero de 2022) y anuncios del primer boletín de la lista."""
    args = [x for x in (argv if argv is not None else sys.argv[1:]) if "/" in x and len(x) == 10]
    desde, hasta = args[:2] if len(args) >= 2 else ["03/01/2022", "14/01/2022"]
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    comprobar_robots(ANTIGUOS, s)
    r = s.get(ANTIGUOS, timeout=60)
    accion, campos = campos_formulario(r.text, "buscadorForm")
    url = requests.compat.urljoin(r.url, accion)
    campos.update({"buscadorForm:fechaInicialAntiguo_input": desde, "buscadorForm:fechaFinalAntiguo_input": hasta})
    x = _ajax(s, url, campos, "buscadorForm:j_idt152",
              "formListBoletinAntiguos formListAnunciosBolAnt buscadorForm buscadorReducidaForm")
    filas = re.findall(r'<tr data-ri="(\d+)"[^>]*>(.*?)</tr>', x, re.S)
    print("filas", len(filas))
    for ri, f in filas[:15]:
        celdas = [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", c)).split()) for c in re.findall(r"<td[^>]*>(.*?)</td>", f, re.S)]
        print("  ", ri, celdas, re.findall(r'PrimeFaces\.ab\(\{s:(?:&quot;|")([^&"]+)', f)[:3],
              re.findall(r'href="([^"]+)"', f)[:3])
    if not filas:
        print(x[:3000])
        return 0
    a_tag = re.search(r'<a[^>]+id="(formListBoletinAntiguos:tableBoletinesAntiguos:0:j_idt\d+)"[^>]*>', filas[0][1])
    print("enlace fila 0:", html.unescape(a_tag.group(0))[:600] if a_tag else None)
    vs = re.search(r'<update id="[^"]*ViewState[^"]*"><!\[CDATA\[([^\]]+)\]\]>', x)
    if a_tag and vs:
        fuente = a_tag.group(1)
        c2 = {"formListBoletinAntiguos": "formListBoletinAntiguos", "javax.faces.ViewState": vs.group(1),
              "formListBoletinAntiguos:tableBoletinesAntiguos_scrollState": "0,0"}
        y = _ajax(s, url, c2, fuente, "formListAnunciosBolAnt")
        t = " ".join(html.unescape(re.sub(r"<script.*?</script>|<[^>]+>", " ", y, flags=re.S)).split())
        print("anuncios:", t[:2500])
        print("enlaces:", sorted(set(re.findall(r'href="([^"]+)"', y)))[:20])
        i = y.find("formListAnunciosBolAnt")
        print("html:", y[i:i + 2500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
