"""BOP de Zaragoza (BOPZ): el boletín del día desde su portada.

Formato verificado el 30/10/2026 desde el servidor de España (desde GitHub no responde): https://bop.dpz.es/BOPZ/
trae el sumario del último boletín: sección (h3 «Sección quinta»), entidad (p.parrafo «AYUNTAMIENTO DE ZARAGOZA») y,
por anuncio, el asunto (a.enlaceEdicto, abreVentanaDetalleEdicto('N')). El número sale de la ruta del boletín completo
(Boletines\\AAAA\\NNN\\bop.pdf) y la fecha, de la cabecera.

Texto de cada anuncio (verificado el 30/10/2026): obtenerContenidoEdicto.do?idEdicto=N, con el texto en
div.medium-12.panel (versión HTML; el oficial es el PDF de Edictos). De las listas de personas solo el recuento y las
citas.

Uso: python -m motor.provinciales.bopzaragoza --salida ruta/
     python -m motor.provinciales.bopzaragoza --historico --max-minutos 30 --salida ruta/
     python -m motor.provinciales.bopzaragoza --textos --max-minutos 30 --salida ruta/
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import descargar_textos, leer_jsonl
from motor.extraccion.citas import citas
from motor.extraccion.texto_es import fecha_texto
from motor.limpieza import RE_DOCUMENTO, limpiar_html, texto_de
from motor.provinciales.comun import CON_TEXTO
from motor.provinciales.portadas import Portada, main as main_portada, seleccionar as sel_portada

BASE = "https://bop.dpz.es/BOPZ/"
RE_NUMERO = re.compile(r"UploadServlet\?ruta=Boletines\\+(?P<a>\d{4})\\+(?P<n>\d+)\\+bop\.pdf")
RE_FECHA = re.compile(r"\b(?P<d>\d{1,2}) de (?P<m>[a-záéíóú]+) de (?P<a>\d{4})\b")
RE_TOKEN = re.compile(r"<h3>(?P<sec>[^<]+)</h3>"
                      r'|<div class="small-12 columns">\s*<p class="parrafo"[^>]*>(?P<ent>[^<]+)</p>'
                      r"|<a class=\"enlaceEdicto\"[^>]*abreVentanaDetalleEdicto\('(?P<id>\d+)'\)\">(?P<tit>.*?)</a>", re.DOTALL)


def _t(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())


def leer(contenido: bytes) -> dict:
    h = contenido.decode("latin-1", errors="replace")
    n, f = RE_NUMERO.search(h), RE_FECHA.search(h)
    seccion = entidad = None
    anuncios = []
    for m in RE_TOKEN.finditer(h):
        if m.group("sec") is not None:
            sec = _t(m.group("sec"))
            if sec.lower().startswith(("sección", "seccion", "parte")):
                seccion, entidad = sec, None
        elif m.group("ent") is not None:
            entidad = re.sub(r"\s*\((?:DPZ)\)", "", _t(m.group("ent"))).split(".-")[0].strip()
        elif seccion:
            # Se marca aquí lo local (secciones tercera, quinta y sexta) para que la selección común lo vea
            sec_local = f"{seccion} (administración local)" if es_local({"seccion": seccion}) else seccion
            anuncios.append({"numero_anuncio": m.group("id"), "seccion": sec_local, "entidad": entidad,
                             "titulo": _t(m.group("tit")), "url_pdf": None})
    return {"numero": n.group("n") if n else None,
            "fecha": fecha_texto(f.group("d"), f.group("m"), f.group("a")) if f else None, "anuncios": anuncios}


def es_local(x: dict) -> bool:
    """En el BOPZ: tercera, la Diputación; quinta, el Ayuntamiento de Zaragoza; sexta, las demás entidades locales."""
    return (x.get("seccion") or "").lower().replace("ó", "o").startswith(
        ("seccion tercera", "seccion quinta", "seccion sexta"))


PORTADA = Portada(fuente="bopzaragoza", siglas="BOP-ZARAGOZA", provincia="Zaragoza", url=BASE,
                  nombres=("Boletín Oficial de la Provincia de Zaragoza",), leer=leer)
FUENTE, SIGLAS, NOMBRES = PORTADA.fuente, PORTADA.siglas, PORTADA.nombres


def seleccionar(filas: list[dict]) -> list[dict]:
    filas = [{**x, "seccion": f"{x['seccion']} (administración local)"
              if es_local(x) and "administración local" not in (x.get("seccion") or "") else x["seccion"]}
             for x in filas]
    return sel_portada(PORTADA, filas)


PORTADA_DO = BASE + "portada.do?SERVICE_NAME=mostrarPortada"
RE_ID = re.compile(r"verboletin\((\d+)\)")


def ids_del_mes(contenido: bytes) -> list[str]:
    return sorted(set(RE_ID.findall(contenido.decode("latin-1", errors="replace"))), key=int)


def historico(argv: list[str] | None = None) -> int:
    """Días anteriores por el calendario de la portada (formulario de portada.do, verificado desde España el
    30/10/2026): con fechaNueva=01/MM/AAAA da los boletines de ese mes (verboletin(id)); con idBoletin, ese boletín
    con el mismo sumario que la portada. Mes a mes hacia atrás hasta enero de 2022; lo hecho queda en historico.json."""
    import argparse
    import json
    import time
    from datetime import date, datetime
    from pathlib import Path
    from zoneinfo import ZoneInfo

    from motor.archivo import Archivo, solo_huella_por_defecto
    from motor.autonomicos.comun import Freno, escribir_json
    from motor.http import obtener
    from motor.provinciales.portadas import _guardar

    a = argparse.ArgumentParser()
    a.add_argument("--historico", action="store_true")
    a.add_argument("--salida", type=Path, default=Path("."))
    a.add_argument("--max-minutos", type=float, default=0)
    a.add_argument("--pausa", type=float, default=1.0)
    a.add_argument("--hoy", type=date.fromisoformat, default=None)
    args = a.parse_args(argv)
    archivo = Archivo(args.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    ruta_estado = args.salida / "datos" / "provinciales" / FUENTE / "historico.json"
    estado = json.loads(ruta_estado.read_text(encoding="utf-8")) if ruta_estado.exists() else {"ids": {}, "meses": []}
    hoy = args.hoy or datetime.now(ZoneInfo("Europe/Madrid")).date()
    inicio, freno, hechos = time.monotonic(), Freno(), 0
    anio, mes = hoy.year, hoy.month
    try:
        while (anio, mes) >= (2022, 1):
            clave_mes = f"{anio}-{mes:02d}"
            if clave_mes in estado["meses"]:
                anio, mes = (anio, mes - 1) if mes > 1 else (anio - 1, 12)
                continue
            if args.max_minutos and (time.monotonic() - inicio) / 60 > args.max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                break
            fecha_mes = f"01/{mes:02d}/{anio}"
            time.sleep(args.pausa)
            r = obtener(PORTADA_DO, accept="text/html", formulario={"idBoletin": "", "fechaNueva": fecha_mes})
            ids = ids_del_mes(r.contenido) if r.status == 200 else []
            if not ids:
                print(f"::warning::BOPZ {clave_mes}: el calendario no trae boletines (HTTP {r.status})")
                break
            completo = True
            for ident in ids:
                if ident in estado["ids"]:
                    continue
                if args.max_minutos and (time.monotonic() - inicio) / 60 > args.max_minutos:
                    completo = False
                    break
                time.sleep(args.pausa)
                rb = obtener(PORTADA_DO, accept="text/html", formulario={"idBoletin": ident, "fechaNueva": fecha_mes})
                s = leer(rb.contenido) if rb.status == 200 else {}
                if not s.get("fecha") or not s.get("anuncios"):
                    inf = {"resultado": "error_formato", "alertas": [f"BOPZ boletín {ident}: sin fecha o sin anuncios"]}
                    completo = False
                else:
                    inf = _guardar(PORTADA, s, rb, f"{PORTADA_DO}#idBoletin={ident}", args.salida, archivo, "historico")
                    estado["ids"][ident] = s["fecha"]
                    hechos += 1
                print(f"BOPZ {ident} {s.get('fecha')}: {inf['resultado']} {inf.get('empleo_publico', '')}")
                if freno.anotar(inf):
                    completo = False
                    break
            # Un mes ya cerrado con todos sus boletines leídos no se vuelve a pedir
            if completo and (anio, mes) < (hoy.year, hoy.month):
                estado["meses"].append(clave_mes)
            escribir_json(ruta_estado, estado)
            if not completo:
                break
            anio, mes = (anio, mes - 1) if mes > 1 else (anio - 1, 12)
    except (ConnectionError, TimeoutError) as e:
        print(f"BOPZ: fuente inaccesible ({e})")
        escribir_json(ruta_estado, estado)
        return 1
    escribir_json(ruta_estado, estado)
    print(f"BOPZ histórico: {hechos} boletines nuevos; meses completos: {len(estado['meses'])}")
    return 0


def url_edicto(x: dict) -> str:
    return f"{BASE}obtenerContenidoEdicto.do?idEdicto={x['numero_anuncio']}"


def texto_edicto(contenido: bytes, x: dict | None = None) -> dict:
    """Texto del anuncio (div.medium-12.panel). En listas, nombramientos y resultados (fuera de CON_TEXTO) solo se
    cuentan las líneas con documento de identidad y se guardan las citas."""
    h = contenido.decode("latin-1", errors="replace")
    i = h.find('<div class="medium-12 panel">')
    if i < 0:
        raise ValueError("sin div.medium-12.panel: posible cambio de formato")
    j = h.find('<div class="medium-12 text-center">', i)
    cuerpo = h[i:j if j > i else None]
    if x is not None and x.get("tipo_acto") not in CON_TEXTO:
        lineas = [texto_de(b) for b in re.split(r"</(?:p|tr|li|div)>", cuerpo)]
        return {"titulo": None, "texto": None, "tablas": [], "solo_recuento": True,
                "lineas_con_documento_de_identidad": sum(1 for l in lineas if RE_DOCUMENTO.search(l)),
                "citas": citas("\n".join(lineas))}
    return {"titulo": None, **limpiar_html(cuerpo)}


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "provinciales" / FUENTE


def ruta_texto(raiz: Path, x: dict) -> Path:
    return _base(raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"


def textos_pendientes(raiz: Path) -> list[dict]:
    lista = []
    for f in sorted((_base(raiz) / "oposiciones").glob("*/*/*.jsonl"), reverse=True):
        lista += [x for x in leer_jsonl(f) if x.get("numero_anuncio") and not ruta_texto(raiz, x).exists()]
    return sorted(lista, key=lambda x: (0 if x.get("tipo_acto") in CON_TEXTO else 1,
                                        0 if x.get("alcance") in (None, "acceso") else 1))


def textos(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--textos", action="store_true")
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    pend = textos_pendientes(a.salida)
    hechos, errores = descargar_textos(pend, lambda x: ruta_texto(a.salida, x), url_edicto, texto_edicto, archivo,
                                       FUENTE, a.max_minutos, a.pausa, accept="text/html", ext="html",
                                       por_registro=True)
    print(f"BOPZ textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if "--historico" in args:
        return historico(argv)
    if "--textos" in args:
        return textos(args)
    return main_portada(PORTADA, argv)


if __name__ == "__main__":
    sys.exit(main())
