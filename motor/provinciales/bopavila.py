"""BOP de Ávila por su canal RSS (https://www.diputacionavila.es/bop/rss.xml): el boletín del día.

Formato verificado el 30/10/2026 desde GitHub: canal «Número 210 (29-10-2026)»; cada anuncio con título «AYUNTAMIENTO
DE VELAYOS - 2101/26» (entidad y número), descripción (el asunto) y enlace a su PDF. robots.txt lo permite.

Histórico: cada boletín tiene su propio canal (/bops/AAAA/DD-MM-AAAA/rss.xml, enlazado desde
/boletin-oficial/AAAA/DD-MM-AAAA.html), con el mismo formato.

Uso: python -m motor.provinciales.bopavila --salida ruta/
     python -m motor.provinciales.bopavila --historico --desde 2022-01-01 --max-minutos 30 --salida ruta/
"""

from __future__ import annotations

import re
import sys

from motor.extraccion.texto_es import fecha_texto
from motor.provinciales.canal import Canal, items_rss, main as main_canal, texto

RE_NUMERO = re.compile(r"N[úu]mero\s+(?P<n>\d+)\s*\((?P<d>\d{1,2})-(?P<m>\d{1,2})-(?P<a>\d{4})\)")
RE_TITULO = re.compile(r"^(?P<ent>.+?)\s+-\s+(?P<num>\d+/\d+)$")


def leer(xml: str) -> dict:
    desc = texto((re.search(r"<channel>.*?<description>(.*?)</description>", xml, re.DOTALL) or [None, ""])[1])
    m = RE_NUMERO.search(desc)
    anuncios = []
    for it in items_rss(xml):
        t = RE_TITULO.match(it["title"])
        anuncios.append({"numero_anuncio": t.group("num") if t else it["link"].rsplit("_", 1)[-1].split(".")[0],
                         "entidad": t.group("ent") if t else it["title"], "titulo": it["description"],
                         "url_pdf": it["link"] or None})
    return {"numero": m.group("n") if m else None,
            "fecha": f"{m.group('a')}-{int(m.group('m')):02d}-{int(m.group('d')):02d}" if m else None,
            "anuncios": anuncios}


CANAL = Canal(fuente="bopavila", siglas="BOP-AVILA", provincia="Ávila", url="https://www.diputacionavila.es/bop/rss.xml",
              nombres=("Boletín Oficial de la Provincia de Ávila",), leer=leer)
FUENTE, SIGLAS, NOMBRES = CANAL.fuente, CANAL.siglas, CANAL.nombres


def seleccionar(filas: list[dict]) -> list[dict]:
    from motor.provinciales.canal import seleccionar as sel
    return sel(CANAL, filas)


def url_dia(d) -> str:
    """Canal de un día concreto (el mismo formato que el del día): /bops/AAAA/DD-MM-AAAA/rss.xml."""
    return f"https://www.diputacionavila.es/bops/{d:%Y}/{d:%d-%m-%Y}/rss.xml"


def main(argv: list[str] | None = None) -> int:
    if "--historico" in (argv if argv is not None else sys.argv[1:]):
        from motor.provinciales.canal import historico
        return historico(CANAL, url_dia, lambda c: leer(c.decode("utf-8", errors="replace")), argv, ext="xml")
    return main_canal(CANAL, argv)


if __name__ == "__main__":
    sys.exit(main())
