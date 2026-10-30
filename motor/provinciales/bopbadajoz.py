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


def texto_disposicion(contenido: bytes) -> dict:
    from motor.limpieza import limpiar_html, texto_de

    h = contenido.decode("utf-8", errors="replace")
    i = h.find('<div class="contenido_anuncio">')
    if i < 0:
        raise ValueError("sin contenido_anuncio: posible cambio de formato")
    fin = h.find("</article>", i)
    tit = re.search(r"<div class='epigrafe'>(.*?)</div>", h, re.DOTALL)
    return {"titulo": texto_de(tit.group(1)) if tit else None, **limpiar_html(h[i:fin if fin > 0 else None])}


def ruta_texto(raiz, x: dict):
    return raiz / "datos" / "provinciales" / FUENTE / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"


def main(argv: list[str] | None = None) -> int:
    """--textos: la ficha de cada anuncio de empleo (/bop/ventana_anuncio.php, cerrada en robots.txt; se lee como
    boletín oficial, motor/http.py)."""
    argv = sys.argv[1:] if argv is None else argv
    if "--textos" not in argv:
        return main_canal(CANAL, argv)
    import argparse
    from pathlib import Path

    from motor.archivo import Archivo, solo_huella_por_defecto
    from motor.autonomicos.comun import descargar_textos, leer_jsonl

    p = argparse.ArgumentParser()
    p.add_argument("--textos", action="store_true")
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    base = a.salida / "datos" / "provinciales" / FUENTE / "oposiciones"
    pend = [x for f in sorted(base.glob("*/*/*.jsonl"), reverse=True) for x in leer_jsonl(f)
            if x.get("url_html") and not ruta_texto(a.salida, x).exists()]
    hechos, errores = descargar_textos(pend, lambda x: ruta_texto(a.salida, x), lambda x: x["url_html"],
                                       texto_disposicion, archivo, FUENTE, a.max_minutos, a.pausa,
                                       accept="text/html", ext="html")
    print(f"BOP Badajoz textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
