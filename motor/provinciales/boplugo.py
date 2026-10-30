"""BOP de Lugo por su canal RSS (https://deputacionlugo.gal/boletin-oficial-da-provincia-de-lugo/bop/feed.xml).

Formato verificado el 30/10/2026 desde GitHub: un elemento por boletín («BOP DE 29/10/2026», con su «Código» 248 y la
fecha de publicación) y en la descripción el sumario en listas anidadas: el grupo («EXCMA. DEPUTACIÓN PROVINCIAL DE
LUGO», «CONCELLOS», «XUNTA DE GALICIA»…), dentro el área o el concello («MONFORTE DE LEMOS») y cada anuncio con su
título, página y registro («… (PÁX. 5, R. 2962)») enlazando a la página del PDF del boletín. En gallego.
robots.txt lo permite.

Histórico: la lista de boletines (/gl/boletin-oficial-da-provincia-de-lugo/bop?…&page=N, «BOP DE 29/10/2026» con su
código) y la página de cada boletín (/gl/node/N), con el mismo sumario. Las páginas que robots.txt cierra una a una no
se piden.

Uso: python -m motor.provinciales.boplugo --salida ruta/
     python -m motor.provinciales.boplugo --historico --desde 2022-01-01 --max-minutos 30 --salida ruta/
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
    if "--historico" in (argv if argv is not None else sys.argv[1:]):
        return historico(argv)
    return main_canal(CANAL, argv)



# --- Histórico: la lista de boletines (tabla paginada) y la página de cada boletín (mismo sumario que el canal) ---
LISTA = WEB + "/gl/boletin-oficial-da-provincia-de-lugo/bop"
RE_FILA = re.compile(r'views-field-field-ail-codigo">\s*(?P<cod>\d+)\s*</td>\s*<td[^>]*>\s*<a href="(?P<nodo>/gl/node/(?P<id>\d+))"'
                     r'[^>]*>\s*BOP DE (?P<d>\d{2})/(?P<m>\d{2})/(?P<a>\d{4})', re.DOTALL)


def url_lista(pagina: int) -> str:
    return (f"{LISTA}?fecha_publicacion%5Bmin%5D=&fecha_publicacion%5Bmax%5D=&field_ail_codigo_value="
            f"&field_ail_bop_contenido_value=&page={pagina}")


def boletines_lista(contenido: bytes) -> list[dict]:
    h = contenido.decode("utf-8", errors="replace")
    return [{"numero": m.group("cod"), "id_nodo": m.group("id"), "url": WEB + m.group("nodo"),
             "fecha": f"{m.group('a')}-{m.group('m')}-{m.group('d')}"} for m in RE_FILA.finditer(h)]


def leer_nodo(contenido: bytes, fecha: str) -> list[dict]:
    d = contenido.decode("utf-8", errors="replace")
    return [{**x, "numero_anuncio": f"{fecha[:4]}-{x['registro']}" if x["registro"] else f"{fecha}-{n}"}
            for n, x in enumerate(sumario(d), 1)]


def historico(argv: list[str] | None = None) -> int:
    import argparse
    import json
    import time
    from datetime import date
    from pathlib import Path

    from motor.archivo import Archivo, solo_huella_por_defecto
    from motor.autonomicos.comun import Freno, escribir_json, escribir_jsonl
    from motor.http import obtener, robots_de
    from motor.provinciales.canal import seleccionar as sel

    p = argparse.ArgumentParser()
    p.add_argument("--historico", action="store_true")
    p.add_argument("--desde", type=date.fromisoformat, default=date(2022, 1, 1))
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    base = a.salida / "datos" / "provinciales" / FUENTE
    try:  # páginas que robots.txt cierra una a una («Disallow: http://deputacionlugo.gal/gl/node/66327»)
        cerrados = {m for permite, ruta, *_ in robots_de(WEB + "/").reglas or [] if not permite
                    for m in re.findall(r"node/(\d+)", ruta)}
    except Exception:
        cerrados = set()
    inicio, freno, hechos, pagina = time.monotonic(), Freno(), 0, 0
    estado_ruta = base / "estado_historico.json"
    estado = json.loads(estado_ruta.read_text(encoding="utf-8")) if estado_ruta.exists() else {}
    while not estado.get("completo"):
        if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
            print("Tiempo agotado; se continúa en la siguiente ejecución")
            break
        r = obtener(url_lista(pagina), accept="text/html")
        lista = boletines_lista(r.contenido) if r.status == 200 else []
        time.sleep(a.pausa)
        if not lista:
            break
        for b in lista:
            if b["fecha"] < a.desde.isoformat():
                estado["completo"] = True
                break
            d = date.fromisoformat(b["fecha"])
            ruta = base / "dias" / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.json"
            if b["id_nodo"] in cerrados or (ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get(
                    "resultado") == "ok"):
                continue
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                break
            time.sleep(a.pausa)
            try:
                rn = obtener(b["url"], accept="text/html")
            except (ConnectionError, TimeoutError) as e:
                inf = {"fecha": b["fecha"], "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            else:
                if rn.status != 200:
                    inf = {"fecha": b["fecha"], "resultado": "error_http", "status": rn.status, "alertas": []}
                else:
                    captura = archivo.guardar(FUENTE, d, rn.contenido, b["url"], "html", rn.status, rn.cabeceras)
                    filas = [{**x, "id": f"{SIGLAS}-{x['numero_anuncio']}", "fecha": b["fecha"], "boletin": b["numero"],
                              "fuente": SIGLAS, "captura_sha256": captura["sha256"]}
                             for x in leer_nodo(rn.contenido, b["fecha"])]
                    empleo = sel(CANAL, filas)
                    escribir_jsonl(base / "disposiciones" / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.jsonl", filas)
                    escribir_jsonl(base / "oposiciones" / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.jsonl", empleo)
                    inf = {"fecha": b["fecha"], "resultado": "ok", "numero": b["numero"], "origen": "pagina",
                           "sha256": captura["sha256"], "disposiciones": len(filas), "empleo_publico": len(empleo),
                           "alertas": [] if filas else [f"BOP Lugo {b['fecha']}: sin anuncios"]}
                    hechos += 1
            escribir_json(ruta, inf)
            print(f"BOP Lugo {b['fecha']}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            if freno.anotar(inf):
                return 1
        pagina += 1
    escribir_json(estado_ruta, estado)
    print(f"BOP Lugo histórico: {hechos} boletines nuevos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
