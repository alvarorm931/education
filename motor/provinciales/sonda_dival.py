"""Sonda del BOP de Valencia (bop.dival.es): portal JSF/PrimeFaces con sesión.

Prueba la búsqueda por fechas y sección («Municipis») y la paginación del listado, y guarda cada respuesta en la
carpeta de salida para estudiar el formato antes de programar el conector.

Uso (desde GitHub, con prueba.yml): python -m motor.provinciales.sonda_dival --salida ruta/ [--desde DD/MM/AAAA]
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import time
from pathlib import Path

import requests

from motor.http import USER_AGENT

PORTAL = "https://bop.dival.es/bop/xhtml/portal.xhtml"


def campos_formulario(pagina: str, form_id: str) -> tuple[str, dict]:
    i = pagina.find(f'id="{form_id}"')
    j = pagina.find("</form>", i)
    f = pagina[i:j]
    accion = html.unescape(re.search(r'action="([^"]+)"', pagina[pagina.rfind("<form", 0, i + 1):i + 400]).group(1))
    campos = {}
    for m in re.finditer(r"<input\b[^>]*>", f):
        t = m.group(0)
        n = re.search(r'name="([^"]+)"', t)
        if not n or 'type="checkbox"' in t or 'type="submit"' in t:
            continue
        v = re.search(r'value="([^"]*)"', t)
        campos[html.unescape(n.group(1))] = html.unescape(v.group(1)) if v else ""
    for m in re.finditer(r'<select\b[^>]*name="([^"]+)"', f):
        campos.setdefault(m.group(1), "")
    return accion, campos


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--desde", default="28/10/2026")
    p.add_argument("--hasta", default=None)
    p.add_argument("--seccion", default="8")
    a = p.parse_args(argv)
    a.salida.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    indice = []

    r = s.get(PORTAL, timeout=40)
    (a.salida / "1-portal.html").write_bytes(r.content)
    indice.append(f"1 GET {r.status_code} {len(r.content)} {r.url}")
    accion, campos = campos_formulario(r.text, "j_idt131")
    url = requests.compat.urljoin(r.url, accion)
    campos.update({
        "filtroCalendarioIni_input": a.desde, "filtroCalendarioFin_input": a.hasta or a.desde,
        "j_idt175:field_input": a.seccion, "j_idt175:field_focus": "",
        "javax.faces.partial.ajax": "true", "javax.faces.source": "buscarBtn", "javax.faces.partial.execute": "@all",
        "javax.faces.partial.render": "messages boletines3 edictos", "buscarBtn": "buscarBtn",
    })
    (a.salida / "2-campos.txt").write_text("\n".join(f"{k}={v}" for k, v in campos.items()), encoding="utf-8")
    time.sleep(1)
    cab = {"Faces-Request": "partial/ajax", "X-Requested-With": "XMLHttpRequest",
           "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "Referer": r.url}
    r2 = s.post(url, data=campos, headers=cab, timeout=60)
    (a.salida / "3-busqueda.xml").write_bytes(r2.content)
    indice.append(f"3 POST busqueda {r2.status_code} {len(r2.content)} {url}")

    # Paginación del listado de edictos (segunda página)
    vs = re.search(r'javax\.faces\.ViewState[^>]*><!\[CDATA\[([^\]]+)\]\]>', r2.text)
    viewstate = vs.group(1) if vs else campos.get("javax.faces.ViewState")
    rejilla = re.search(r'PrimeFaces\.cw\("DataGrid","(\w+)",\{id:"([^"]+)"[^}]*paginator', r2.text)
    form_lista = re.search(r'<form id="([^"]+)"[^>]*>\s*<input type="hidden" name="\1" value="\1" />\s*<div id="([^"]+)"[^>]*ui-datagrid',
                           r2.text)
    indice.append(f"rejilla={rejilla.groups() if rejilla else None} form={form_lista.groups() if form_lista else None}")
    if rejilla and form_lista:
        lid, fid = rejilla.group(2), form_lista.group(1)
        datos = {fid: fid, "javax.faces.ViewState": viewstate, "javax.faces.partial.ajax": "true",
                 "javax.faces.source": lid, "javax.faces.partial.execute": lid, "javax.faces.partial.render": lid,
                 f"{lid}_pagination": "true", f"{lid}_first": "25", f"{lid}_rows": "25", f"{lid}_encodeFeature": "true"}
        time.sleep(1)
        r3 = s.post(url, data=datos, headers=cab, timeout=60)
        (a.salida / "4-pagina2.xml").write_bytes(r3.content)
        indice.append(f"4 POST pagina2 {r3.status_code} {len(r3.content)}")
    indice.append("cookies: " + ", ".join(sorted(s.cookies.keys())))
    (a.salida / "indice.txt").write_text("\n".join(indice) + "\n", encoding="utf-8")
    print("\n".join(indice))
    return 0


if __name__ == "__main__":
    sys.exit(main())
