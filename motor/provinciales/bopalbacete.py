"""BOP de Albacete: el boletín del día desde su portada.

Formato verificado el 30/10/2026 desde el servidor de España (desde GitHub no responde): https://bop.dipualba.es/
trae «Boletín Número 126 (28/10/2026)» y el sumario por secciones (p.h5 «Sección tercera. Administración Local»),
entidad o grupo («Ayuntamientos») y entidad («Ossa de Montiel») en span.fw-bold, y por anuncio el asunto
(div.col-12) con el PDF de su página (servicesajax/descargararchivopaginaBOP/N).

El PDF de cada anuncio es solo la página donde empieza («Ver página 7»): el texto se corta del boletín completo
(servicesajax/descararchivobopcompleto/?a=N, «Descargar boletín completo»), que se guarda en url_pdf_boletin
(motor/provinciales/textos.py). Para los días ya cargados, --reparar-boletin lo lee de su original en el almacén.

Uso: python -m motor.provinciales.bopalbacete --salida ruta/
     python -m motor.provinciales.bopalbacete --historico --max-minutos 30 --salida ruta/
     python -m motor.provinciales.bopalbacete --reparar-boletin --salida ruta/
"""

from __future__ import annotations

import html
import re
import sys

from motor.provinciales.portadas import Portada, main as main_portada, seleccionar as sel_portada

BASE = "https://bop.dipualba.es"
RE_CABECERA = re.compile(r"Bolet[ií]n\s+N[úu]mero\s+(?P<n>\d+)\s*\((?P<d>\d{2})/(?P<m>\d{2})/(?P<a>\d{4})\)")
RE_TOKEN = re.compile(r'<p class="h5">(?P<sec>[^<]+)</p>'
                      r'|<span class="fw-bold">(?P<ent>[^<]+)</span>(?P<tras></li>|<ul)'
                      r'|<div class="col-12">(?P<tit>[^<]+)</div>\s*<div class="col-12 text-end">\s*<a [^>]*href="(?P<pdf>[^"]+descargararchivopaginaBOP/(?P<id>\d+))"')


def _t(s: str) -> str:
    return " ".join(html.unescape(s or "").split())


RE_COMPLETO = re.compile(r"servicesajax/descararchivobopcompleto/\?a=(\d+)")


def url_boletin(h: str) -> str | None:
    m = RE_COMPLETO.search(h)
    return f"{BASE}/servicesajax/descararchivobopcompleto/?a={m.group(1)}" if m else None


def leer(contenido: bytes) -> dict:
    h = contenido.decode("utf-8", errors="replace")
    c = RE_CABECERA.search(h)
    completo = url_boletin(h)
    seccion = grupo = entidad = None
    anuncios = []
    for m in RE_TOKEN.finditer(h):
        if m.group("sec"):
            seccion, grupo, entidad = _t(m.group("sec")), None, None
        elif m.group("ent"):
            if m.group("tras") == "<ul":
                grupo, entidad = _t(m.group("ent")), None
            else:
                entidad = _t(m.group("ent"))
        else:
            anuncios.append({"numero_anuncio": m.group("id"), "seccion": seccion, "grupo": grupo,
                             "entidad": entidad if grupo and grupo.lower() == "ayuntamientos" else grupo or entidad,
                             "organo": entidad if grupo and grupo.lower() != "ayuntamientos" else None,
                             "titulo": _t(m.group("tit")), "url_pdf": m.group("pdf"), "url_pdf_boletin": completo})
    return {"numero": c.group("n") if c else None,
            "fecha": f"{c.group('a')}-{c.group('m')}-{c.group('d')}" if c else None, "anuncios": anuncios}


PORTADA = Portada(fuente="bopalbacete", siglas="BOP-ALBACETE", provincia="Albacete", url=BASE + "/",
                  nombres=("Boletín Oficial de la Provincia de Albacete",), leer=leer)
FUENTE, SIGLAS, NOMBRES = PORTADA.fuente, PORTADA.siglas, PORTADA.nombres


def seleccionar(filas: list[dict]) -> list[dict]:
    return sel_portada(PORTADA, filas)


def historico(argv: list[str] | None = None) -> int:
    """Días anteriores por los servicios del calendario de la portada (verificado desde España el 30/10/2026):
    servicesajax/obtenerdiaspublicacion?a=AAAA-MM-01 da los boletines del mes (JSON en base64, con «fechabop») y
    servicesajax/obtenersumariobop (POST a=DD/MM/AAAA, con el token de la página) el sumario de ese día, con el mismo
    formato que la portada. Mes a mes hacia atrás hasta enero de 2022."""
    import argparse
    import base64
    import json
    import time
    from datetime import date, datetime
    from pathlib import Path
    from zoneinfo import ZoneInfo

    import requests

    from motor.archivo import Archivo, solo_huella_por_defecto
    from motor.autonomicos.comun import Freno
    from motor.http import USER_AGENT, Respuesta, obtener
    from motor.provinciales.portadas import _guardar, _ruta

    a = argparse.ArgumentParser()
    a.add_argument("--historico", action="store_true")
    a.add_argument("--salida", type=Path, default=Path("."))
    a.add_argument("--max-minutos", type=float, default=0)
    a.add_argument("--pausa", type=float, default=1.0)
    args = a.parse_args(argv)
    archivo = Archivo(args.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    sesion = requests.Session()
    sesion.headers["User-Agent"] = USER_AGENT
    r = obtener(BASE + "/", accept="text/html", sesion=sesion)
    token = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', r.contenido.decode("utf-8", "replace"))
    if not token:
        print("::warning::BOP Albacete: la portada no trae el token del calendario (posible cambio de formato)")
        return 1
    cab = {"RequestVerificationToken": token.group(1), "X-Requested-With": "XMLHttpRequest"}
    hoy = datetime.now(ZoneInfo("Europe/Madrid")).date()
    anio, mes, inicio, freno, hechos = hoy.year, hoy.month, time.monotonic(), Freno(), 0
    while (anio, mes) >= (2022, 1):
        if args.max_minutos and (time.monotonic() - inicio) / 60 > args.max_minutos:
            print("Tiempo agotado; se continúa en la siguiente ejecución")
            break
        time.sleep(args.pausa)
        rd = obtener(f"{BASE}/servicesajax/obtenerdiaspublicacion?a={anio}-{mes:02d}-01", accept="application/json",
                     sesion=sesion, cabeceras_extra=cab)
        try:
            eventos = json.loads(base64.b64decode(json.loads(rd.contenido).get("yedata") or "") or b"[]")
        except ValueError:
            print(f"::warning::BOP Albacete {anio}-{mes:02d}: el calendario no es el esperado (HTTP {rd.status})")
            return 1
        parar = False
        for ev in sorted(eventos, key=lambda e: e.get("start") or "", reverse=True):
            d = date.fromisoformat(ev["start"][:10])
            ruta = _ruta(PORTADA, args.salida, "dias", d, "json")
            if d >= hoy or (ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") == "ok"):
                continue
            if args.max_minutos and (time.monotonic() - inicio) / 60 > args.max_minutos:
                parar = True
                break
            time.sleep(args.pausa)
            rs = obtener(f"{BASE}/servicesajax/obtenersumariobop", accept="application/json", sesion=sesion,
                         formulario={"a": ev.get("fechabop")}, cabeceras_extra=cab)
            try:
                h = (json.loads(rs.contenido).get("yedata") or "").encode("utf-8")
            except ValueError:
                h = b""
            s = leer(h)
            if s.get("fecha") == d.isoformat() and s.get("anuncios"):
                inf = _guardar(PORTADA, s, Respuesta(rs.url, 200, h, rs.cabeceras),
                               f"{BASE}/servicesajax/obtenersumariobop#{ev.get('fechabop')}", args.salida, archivo,
                               "historico")
                hechos += 1
            else:
                inf = {"fecha": d.isoformat(), "resultado": "error_formato",
                       "alertas": [f"BOP Albacete {d}: el sumario no trae fecha o anuncios"]}
            print(f"BOP Albacete {d}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            if freno.anotar(inf):
                parar = True
                break
        if parar:
            break
        anio, mes = (anio, mes - 1) if mes > 1 else (anio - 1, 12)
    print(f"BOP Albacete histórico: {hechos} boletines nuevos")
    return 0


def reparar_boletin(argv: list[str] | None = None) -> int:
    """Añade url_pdf_boletin a los días cargados antes de guardarlo, leyendo el sumario original del almacén (no se
    vuelve a pedir a la fuente)."""
    import argparse
    import json
    from datetime import date
    from pathlib import Path

    from motor.almacen import Almacen, clave_original
    from motor.autonomicos.comun import escribir_jsonl, leer_jsonl

    p = argparse.ArgumentParser()
    p.add_argument("--reparar-boletin", action="store_true")
    p.add_argument("--salida", type=Path, default=Path("."))
    a = p.parse_args(argv)
    base = a.salida / "datos" / "provinciales" / FUENTE
    almacen, hechos, sin_enlace, fallos = None, 0, 0, 0
    for dia in sorted((base / "dias").glob("*/*/*.json"), reverse=True):
        inf = json.loads(dia.read_text(encoding="utf-8"))
        rel = dia.relative_to(base / "dias").with_suffix(".jsonl")
        rutas = [base / "disposiciones" / rel, base / "oposiciones" / rel]
        filas = [leer_jsonl(r) if r.exists() else [] for r in rutas]
        if inf.get("resultado") != "ok" or not inf.get("sha256") or all(x.get("url_pdf_boletin") for x in filas[0]):
            continue
        try:
            almacen = almacen or Almacen()
            h = almacen.leer(clave_original(FUENTE, date.fromisoformat(inf["fecha"]), inf["sha256"], "html"))
        except Exception as e:  # noqa: BLE001 - sin almacén (o sin ese original) se deja para otra ejecución
            fallos += 1
            if fallos >= 5:
                print(f"BOP Albacete: el almacén no responde ({type(e).__name__}); se deja para otra ejecución")
                break
            continue
        u = url_boletin(h.decode("utf-8", errors="replace"))
        if not u:
            sin_enlace += 1
            continue
        for r, lista in zip(rutas, filas):
            if lista:
                escribir_jsonl(r, [{**x, "url_pdf_boletin": u} for x in lista])
        hechos += 1
    print(f"BOP Albacete: boletín completo en {hechos} días; {sin_enlace} sin enlace; {fallos} sin original")
    return 0


def main(argv: list[str] | None = None) -> int:
    if "--reparar-boletin" in (argv if argv is not None else sys.argv[1:]):
        return reparar_boletin(argv)
    if "--historico" in (argv if argv is not None else sys.argv[1:]):
        return historico(argv)
    return main_portada(PORTADA, argv)


if __name__ == "__main__":
    sys.exit(main())
