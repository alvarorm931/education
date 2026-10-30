"""Sonda de los «boletines anteriores» de la plataforma SAGA (BOP de Granada y León): la página de resultados trae los
parámetros del listado (parametrosBase_SagaListado…, con urlAjax) y el listado se filtra por año y mes con los
facets «personalizado_bopantiguo.anio_prop_s» y «personalizado_bopantiguo.mes.formateado_prop_s» (SagaListado.js).
Imprime los facets, el número de resultados y los PDF de un mes. No guarda nada.

Uso (con prueba.yml): python -m motor.provinciales.sonda_saga_antiguos [BASE] [AAAA] [MM]
"""

from __future__ import annotations

import html
import re
import sys
import time

import requests

from motor.http import USER_AGENT, comprobar_robots

RE_PARAM = re.compile(r"^\s*(\w+)\s*:\s*(?:'([^']*)'|\"([^\"]*)\"|(true|false|-?\d+))\s*,?\s*$", re.MULTILINE)
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]


def parametros_base(h: str) -> dict:
    i = h.find('parametrosSagaListado["parametrosBase_')
    j = h.find("};", i)
    return {m.group(1): next(g for g in m.groups()[1:] if g is not None) for m in RE_PARAM.finditer(h[i:j])}


def main(argv: list[str] | None = None) -> int:
    args = [x for x in (argv if argv is not None else sys.argv[1:]) if not x.startswith("--")]
    base = next((x for x in args if x.startswith("http")), "https://bop.dipgra.es")
    nums = [x for x in args if x.isdigit()]
    anio, mes = nums[:2] if len(nums) >= 2 else ("2023", "3")
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    url = base + "/publica/boletines-anteriores/resultados-bop-anteriores/"
    comprobar_robots(url, s)
    r = s.post(url, data={"busqueda": "", "fechaDesde": "", "fechaHasta": "", "BusquedaInicial": ""}, timeout=60)
    h = r.text
    p = parametros_base(h)
    print("resultados", r.status_code, len(r.content), "parámetros", len(p), "urlAjax", p.get("urlAjax"),
          "indexacionFecha", p.get("indexacionFecha"), "IndiceSolr", p.get("IndiceSolr"))
    facets = sorted(set(re.findall(r'data-camposolr="bopantiguo\.mes\.formateado_prop_s"\] \.filtro_busqueda-opciones'
                                   r'\[value="([^"]*)"\]', h) + re.findall(r"value='((?:<quitar>[^<]*</quitar>)?[^']{1,30})' "
                                                                          r"class='filtro_busqueda-opciones facet'", h)))
    print("facets:", facets[:40])
    valor_mes = next((f for f in facets if f.endswith(MESES[int(mes) - 1])), f"{int(mes):02d} - {MESES[int(mes) - 1]}")
    datos = {**p, "busquedaActiva": "true", "forma_listar": "busqueda", "page": "1",
             "personalizado_bopantiguo.anio_prop_s": anio, "personalizado_bopantiguo.mes.formateado_prop_s": valor_mes}
    time.sleep(1)
    u = requests.compat.urljoin(base, p.get("urlAjax", ""))
    comprobar_robots(u, s)
    r2 = s.post(u, data=datos, headers={"X-Requested-With": "XMLHttpRequest", "Referer": url}, timeout=60)
    x = r2.text
    t = " ".join(html.unescape(re.sub(r"<script.*?</script>|<[^>]+>", " ", x, flags=re.S)).split())
    print("ajax", r2.status_code, len(r2.content), "| mes", valor_mes)
    i = t.find("Resultados del")
    print("texto:", t[i:i + 700] if i >= 0 else t[:700])
    print("pdf:", re.findall(r'href="([^"]+\.pdf)"', x)[:30])
    print("paginas:", re.findall(r'class="totalPages" value="(\d+)"', x))
    return 0


if __name__ == "__main__":
    sys.exit(main())
