"""BOP de Teruel: el boletín del día desde su portada (solo responde desde el servidor de España).

Formato verificado el 30/10/2026: https://236ws.dpteruel.es/DPT/bopt.nsf/inicio.xsp trae «BOP del día 29 de Octubre
de 2026 . BOP número 208» y los anuncios del último boletín por sección (h2 «Administración Local»): título enlazando
a la ficha (/DPT/bopt.nsf/0/UNID), entidad (div.campo_seccion «Ayto. de Beceite», «Comarca del Bajo Aragón») y número
(«Anuncio #2026-3143»). Los boletines anteriores solo están en PDF (Redireccion?OpenPage&dia=AAAAMMDD), así que el
histórico se forma día a día desde que se conecta. robots.txt no responde: se lee como boletín oficial
(motor/http.py, decisión del 30/10/2026).

Uso: python -m motor.provinciales.bopteruel --salida ruta/
"""

from __future__ import annotations

import html
import re
import sys

from motor.extraccion.texto_es import fecha_texto
from motor.provinciales.portadas import Portada, main as main_portada, seleccionar as sel_portada

BASE = "https://236ws.dpteruel.es/DPT/bopt.nsf/"
RE_FECHA = re.compile(r"Anuncios del (?:ú|&uacute;)ltimo Bolet(?:í|&iacute;)n</h1>.*?>(\d{1,2}) de (\w+) de (\d{4})<.*?"
                      r"N(?:ú|&uacute;)mero(?:\s|&nbsp;)*(?:<[^>]+>)*(\d+)<", re.DOTALL | re.IGNORECASE)
RE_TOKEN = re.compile(r"<h2[^>]*>(?:<[^>]+>)*(?P<sec>[^<]+)</|<a href=\"(?P<href>0/[0-9A-F]{32})\"[^>]*class=\"link_anuncio\">"
                      r"(?P<tit>.*?)</a>.*?class=\"campo_seccion\">(?:<[^>]+>)*(?P<ent>[^<]*)<.*?Anuncio #(?P<num>\d{4}-\d+)",
                      re.DOTALL)


def _t(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).replace("\xa0", " ").split())


def leer(contenido: bytes) -> dict:
    h = contenido.decode("utf-8", errors="replace")
    f = RE_FECHA.search(h)
    i = h.find("Anuncios del")
    seccion, anuncios = None, []
    for m in RE_TOKEN.finditer(h, max(i, 0)):
        if m.group("sec") is not None:
            seccion = _t(m.group("sec"))
        else:
            anuncios.append({"numero_anuncio": m.group("num"), "seccion": seccion, "grupo": None,
                             "entidad": _t(m.group("ent")), "titulo": _t(m.group("tit")),
                             "url_pdf": None, "url_ficha": BASE + m.group("href")})
    return {"fecha": fecha_texto(f.group(1), f.group(2), f.group(3)) if f else None,
            "numero": f.group(4) if f else None, "anuncios": anuncios}


PORTADA = Portada(fuente="bopteruel", siglas="BOP-TERUEL", provincia="Teruel", url=BASE + "inicio.xsp",
                  nombres=("Boletín Oficial de la Provincia de Teruel",), leer=leer)
FUENTE, SIGLAS, NOMBRES = PORTADA.fuente, PORTADA.siglas, PORTADA.nombres


def seleccionar(filas: list[dict]) -> list[dict]:
    return sel_portada(PORTADA, filas)


def main(argv: list[str] | None = None) -> int:
    return main_portada(PORTADA, argv)


if __name__ == "__main__":
    sys.exit(main())
