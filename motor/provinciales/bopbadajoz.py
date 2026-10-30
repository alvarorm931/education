"""BOP de Badajoz por su canal Atom (https://www.dip-badajoz.es/canales/atom_xml_bop.php?c=1&u=1): el boletín del día.

Formato verificado el 30/10/2026 desde GitHub: «Sumario de aquellos edictos que han sido publicados en el día de hoy»;
cada entrada con título «[4306/2026] Lista definitiva de aspirantes…», autor (la entidad: «Ahillones (Badajoz)») y
enlace a la ficha del anuncio (/bop/ventana_anuncio.php?id_anuncio=N). El canal está permitido en robots.txt.

Uso: python -m motor.provinciales.bopbadajoz --salida ruta/
"""

from __future__ import annotations

import re
import sys

from motor.provinciales.canal import Canal, main as main_canal, texto

RE_TITULO = re.compile(r"^\[(?P<num>\d+/\d{4})\]\s*(?P<t>.*)$", re.DOTALL)
RE_ENTIDAD = re.compile(r"^(?P<e>.+?)\s*\((?P<p>[^()]+)\)\s*$")


def leer(xml: str) -> dict:
    fecha = re.search(r"<feed\b.*?<updated>(\d{4}-\d{2}-\d{2})", xml, re.DOTALL)
    anuncios = []
    for e in re.findall(r"<entry>(.*?)</entry>", xml, re.DOTALL):
        tit = texto((re.search(r"<title[^>]*>(.*?)</title>", e, re.DOTALL) or [None, ""])[1])
        m = RE_TITULO.match(tit)
        autor = texto((re.search(r"<author>\s*<name>(.*?)</name>", e, re.DOTALL) or [None, ""])[1])
        ent = RE_ENTIDAD.match(autor)
        enlace = re.search(r'<link rel="alternate"[^>]*href="([^"]+)"', e)
        anuncios.append({"numero_anuncio": m.group("num") if m else tit[:20], "titulo": m.group("t") if m else tit,
                         "entidad": ent.group("e") if ent else autor or None,
                         "url_html": texto(enlace.group(1)) if enlace else None})
    return {"numero": None, "fecha": fecha.group(1) if fecha else None, "anuncios": anuncios}


CANAL = Canal(fuente="bopbadajoz", siglas="BOP-BADAJOZ", provincia="Badajoz",
              url="https://www.dip-badajoz.es/canales/atom_xml_bop.php?c=1&u=1",
              nombres=("Boletín Oficial de la Provincia de Badajoz",), leer=leer)
FUENTE, SIGLAS, NOMBRES = CANAL.fuente, CANAL.siglas, CANAL.nombres


def seleccionar(filas: list[dict]) -> list[dict]:
    from motor.provinciales.canal import seleccionar as sel
    return sel(CANAL, filas)


def main(argv: list[str] | None = None) -> int:
    return main_canal(CANAL, argv)


if __name__ == "__main__":
    sys.exit(main())
