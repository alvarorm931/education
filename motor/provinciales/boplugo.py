"""BOP de Lugo por su canal RSS (https://deputacionlugo.gal/boletin-oficial-da-provincia-de-lugo/bop/feed.xml).

Formato verificado el 30/10/2026 desde GitHub: un elemento por boletín («BOP DE 29/10/2026», con su «Código» 248 y la
fecha de publicación) y en la descripción el sumario en listas anidadas: el grupo («EXCMA. DEPUTACIÓN PROVINCIAL DE
LUGO», «CONCELLOS», «XUNTA DE GALICIA»…), dentro el área o el concello («MONFORTE DE LEMOS») y cada anuncio con su
título, página y registro («… (PÁX. 5, R. 2962)») enlazando a la página del PDF del boletín. En gallego.
robots.txt lo permite.

Uso: python -m motor.provinciales.boplugo --salida ruta/
"""

from __future__ import annotations

import html
import re
import sys

from motor.boe.clasificar import normalizar
from motor.provinciales.canal import Canal, main as main_canal, texto

WEB = "https://deputacionlugo.gal"
RE_ITEM = re.compile(r"<item>(.*?)</item>", re.DOTALL)
RE_FECHA = re.compile(r"BOP DE (\d{2})/(\d{2})/(\d{4})")
RE_CODIGO = re.compile(r"C[óo]digo</div>\s*<div class=\"field__item\">(\d+)<")
RE_TOKEN = re.compile(r"<ul>|</ul>|<li>|<a [^>]*?href=\"(?P<href>[^\"]+)\"[^>]*>(?P<tit>.*?)</a>", re.DOTALL)
RE_REFERENCIA = re.compile(r"\s*\(\s*P[ÁA]X\.\s*(?P<pax>\d+)\s*,\s*R\.\s*(?P<r>\d+)\s*\)\s*$")


def entidad(ruta: list[str]) -> str:
    g = normalizar(ruta[0]) if ruta else ""
    if g.startswith("concellos") and len(ruta) > 1:
        return f"CONCELLO DE {ruta[1].upper()}"
    if "deputacion provincial de lugo" in g:
        return "Deputación Provincial de Lugo"
    return ruta[0] if ruta else ""


def sumario(d: str) -> list[dict]:
    i = d.find("field--name-field-ail-bop-contenido")
    profundidad, cabeceras, li, out = 0, {}, None, []
    for m in RE_TOKEN.finditer(d, max(i, 0)):
        tok = m.group(0)
        if tok == "<li>":
            li = m.end()
        elif tok == "<ul>":
            profundidad += 1
            cabeceras = {k: v for k, v in cabeceras.items() if k < profundidad - 1}
            if li is not None:
                cabeceras[profundidad - 1] = texto(d[li:m.start()])
            li = None
        elif tok == "</ul>":
            profundidad -= 1
            if profundidad <= 0 and out:
                break
        else:
            li = None
            t = texto(m.group("tit"))
            r = RE_REFERENCIA.search(t)
            ruta = [cabeceras[k] for k in sorted(cabeceras) if k < profundidad]
            href = html.unescape(m.group("href"))
            out.append({"registro": r.group("r") if r else None, "pagina": int(r.group("pax")) if r else None,
                        "titulo": RE_REFERENCIA.sub("", t), "grupo": ruta[0] if ruta else None,
                        "entidad": entidad(ruta), "url_pdf": href if href.startswith("http") else WEB + href})
    return out


def leer(xml: str) -> dict:
    items = RE_ITEM.findall(xml)
    if not items:
        return {"fecha": None, "numero": None, "anuncios": []}
    d = html.unescape(items[0])
    f, c = RE_FECHA.search(d), RE_CODIGO.search(d)
    fecha = f"{f.group(3)}-{f.group(2)}-{f.group(1)}" if f else None
    anuncios = [{**x, "numero_anuncio": f"{fecha[:4]}-{x['registro']}" if x["registro"] and fecha else
                 f"{fecha}-{n}"} for n, x in enumerate(sumario(d), 1)] if fecha else []
    return {"fecha": fecha, "numero": c.group(1) if c else None, "anuncios": anuncios}


CANAL = Canal(fuente="boplugo", siglas="BOP-LUGO", provincia="Lugo",
              url=WEB + "/boletin-oficial-da-provincia-de-lugo/bop/feed.xml",
              nombres=("Boletín Oficial de la Provincia de Lugo", "Boletín Oficial da Provincia de Lugo"), leer=leer)
FUENTE, SIGLAS, NOMBRES = CANAL.fuente, CANAL.siglas, CANAL.nombres


def seleccionar(filas: list[dict]) -> list[dict]:
    from motor.provinciales.canal import seleccionar as sel
    return sel(CANAL, filas)


def main(argv: list[str] | None = None) -> int:
    return main_canal(CANAL, argv)


if __name__ == "__main__":
    sys.exit(main())
