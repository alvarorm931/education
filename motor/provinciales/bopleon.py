"""Conector del Boletín Oficial de la Provincia de León (portal nuevo, desde el 17/02/2025).

Formato verificado el 30/10/2026 desde GitHub:
  - Boletín de un día: https://bop.dipuleon.es/publica/consulta-de-bops/buscador/BOP-DD-MM-AAAA/ (404 si no hay):
    «BOP núm. 206 del 29/10/2026» y los enlaces al sumario en PDF (/export/sites/bop/.galleries/
    DOCUMENTOS-Sumarios-en-PDF/…pdf) y al boletín entero.
  - El sumario en PDF, leído conservando la disposición, trae los niveles por su sangría: sección («Administración
    Local»), grupo («Ayuntamientos», «Mancomunidades»), entidad («- Ayuntamiento de Bembibre») y los asuntos,
    separados por una línea en blanco. Cada asunto enlaza la ficha del anuncio (/publica/buscador-anuncios/anuncio/…/),
    un enlace por línea: los enlaces seguidos iguales son el mismo anuncio.
  - Lo anterior al 17/02/2025, en «boletines anteriores» (verificado el 30/10/2026): POST a
    /publica/boletines-anteriores/resultados-bop-anteriores/ con BusquedaInicial=«desde:AAAA-MM-DD|hasta:AAAA-MM-DD|»
    devuelve la lista (hasta 15) con el PDF del boletín entero («BOP 3/2022», «Boletín núm. 3 de 05/01/2022»). El
    PDF empieza por el sumario: secciones en mayúsculas, grupos («Ayuntamientos»), entidades y asuntos con puntos
    hasta la página. El texto de cada anuncio de empleo se corta del mismo PDF (motor/provinciales/textos.py).
  - robots.txt solo cierra PDF concretos de boletines antiguos (2005-2011).

Uso:
  python -m motor.provinciales.bopleon --salida ruta/                       # ayer y hoy
  python -m motor.provinciales.bopleon --desde 2025-02-17 --max-minutos 30 --salida ruta/
  python -m motor.provinciales.bopleon --textos --max-minutos 30 --salida ruta/
  python -m motor.provinciales.bopleon --antiguos --max-minutos 30 --salida ruta/   # del 16/02/2025 a 2022
"""

from __future__ import annotations

import argparse
import html
import io
import json
import logging
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (Freno, clasificar, convocante_de_organismo, es_empleo_estricto, escribir_json,
                                     escribir_jsonl)
from motor.boe.clasificar import normalizar
from motor.http import obtener
from motor.provinciales.comun import descargar_textos_pdf, ruta_texto_pdf

FUENTE = "bopleon"
SIGLAS = "BOP-LEON"
MADRID = ZoneInfo("Europe/Madrid")
WEB = "https://bop.dipuleon.es"
INICIO = date(2025, 2, 17)
NOMBRES = ("Boletín Oficial de la Provincia de León",)

RE_CABECERA = re.compile(r"<h1><strong>BOP n[uú]m\.\s*(?P<n>\d+)</strong>\s*del\s*(?P<d>\d{2})/(?P<m>\d{2})/(?P<a>\d{4})</h1>")
RE_SUMARIO = re.compile(r'href="(?P<url>/export/sites/bop/\.galleries/DOCUMENTOS-Sumarios-en-PDF/[^"]+\.pdf)"')
RE_PDF_ANUNCIO = re.compile(r'href="(?P<url>/export/sites/bop/\.galleries/Documentos-Anuncios-en-PDF/[^"]+\.pdf)"')
RE_RUIDO = re.compile(r"^(Bolet[íi]n n[úu]m\.|\w+ \d{1,2} de \w+ de \d{4} - p[áa]gina|P[áa]gina \d+ de \d+ del sumario|"
                      r"CVE del|Sumario\s+\[\d+ anuncios?\])", re.IGNORECASE)


def url_dia(d: date) -> str:
    return f"{WEB}/publica/consulta-de-bops/buscador/BOP-{d:%d-%m-%Y}/"


def ficha(contenido: bytes) -> dict:
    h = contenido.decode("utf-8", errors="replace")
    c, s = RE_CABECERA.search(h), RE_SUMARIO.search(h)
    return {"numero": int(c.group("n")) if c else None,
            "fecha": f"{c.group('a')}-{c.group('m')}-{c.group('d')}" if c else None,
            "url_sumario": WEB + html.unescape(s.group("url")) if s else None}


def _paginas_y_enlaces(pdf: bytes) -> tuple[list[list[str]], list[str]]:
    from pypdf import PdfReader
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    lector = PdfReader(io.BytesIO(pdf))
    paginas, enlaces = [], []
    for p in lector.pages:
        paginas.append((p.extract_text(extraction_mode="layout") or "").splitlines())
        for a in p.get("/Annots") or []:
            o = a.get_object()
            uri = (o.get("/A") or {}).get("/URI")
            if uri and "/buscador-anuncios/anuncio/" in uri and (not enlaces or enlaces[-1] != uri):
                enlaces.append(str(uri))
    return paginas, enlaces


def _es_seccion(texto: str) -> bool:
    return normalizar(texto).startswith(("administracion", "anuncios", "otras administraciones"))


def parsear_sumario(pdf: bytes) -> tuple[list[dict], list[str]]:
    """-> (anuncios, alertas). pypdf conserva la disposición pero cada página empieza en su menor sangría, así que
    los niveles se deciden dentro de la página: «- X» es la entidad; lo que va más sangrado que la entidad de esa
    página son asuntos (separados por una línea en blanco); lo que va menos, encabezados (dos seguidos: sección y
    grupo; uno solo: grupo, salvo «Administración…» o «Anuncios…», que es sección). Un asunto partido por un salto
    de página se une si el trozo empieza en minúscula o si sobran asuntos respecto a los enlaces a fichas."""
    paginas, enlaces = _paginas_y_enlaces(pdf)
    seccion = grupo = entidad = None
    parrafos: list[dict] = []  # asuntos: {"seccion","grupo","entidad","titulo","tras_salto"}
    for lineas in paginas:
        utiles = []
        for bruta in lineas:
            texto = " ".join(bruta.split())
            if texto and RE_RUIDO.match(texto):
                continue
            utiles.append((len(bruta) - len(bruta.lstrip()) if texto else None, texto))
        entidades = [s for s, x in utiles if x.startswith("- ")]
        sangria_entidad = entidades[0] if entidades else None
        actual, blanco, primera = (parrafos[-1] if parrafos and entidad is not None else None), True, True
        pendientes: list[str] = []  # encabezados seguidos
        for k, (sangria, texto) in enumerate(utiles):
            if not texto:
                blanco = True
                continue
            if texto.startswith("- "):
                if pendientes:
                    if len(pendientes) >= 2 or _es_seccion(pendientes[0]):
                        seccion, grupo = pendientes[0], (pendientes[1] if len(pendientes) >= 2 else None)
                    else:
                        grupo = pendientes[0]
                    pendientes = []
                entidad, actual, blanco = texto[2:].strip(), None, False
                sangria_entidad = sangria
                primera = False
                continue
            es_asunto = entidad is not None and (sangria_entidad is None or sangria > sangria_entidad)
            if es_asunto and not pendientes:
                if actual is not None and not blanco and not primera:
                    actual["titulo"] += " " + texto
                elif actual is not None and primera and texto[:1].islower():
                    actual["titulo"] += " " + texto
                else:
                    actual = {"seccion": seccion, "grupo": grupo, "entidad": entidad, "titulo": texto,
                              "tras_salto": primera}
                    parrafos.append(actual)
            else:
                if pendientes and not blanco and len(pendientes[-1]) > 0 and texto[:1].islower():
                    pendientes[-1] += " " + texto  # encabezado en dos líneas
                else:
                    pendientes.append(texto)
                actual = None
            blanco = primera = False
    # asuntos de más por saltos de página: se unen al anterior, del primero al último, hasta cuadrar con los enlaces
    while len(parrafos) > len(enlaces) > 0:
        i = next((i for i, x in enumerate(parrafos) if x["tras_salto"] and i > 0
                  and parrafos[i - 1]["entidad"] == x["entidad"]), None)
        if i is None:
            break
        parrafos[i - 1]["titulo"] += " " + parrafos[i]["titulo"]
        del parrafos[i]
    anuncios = [{k: v for k, v in x.items() if k != "tras_salto"} for x in parrafos]
    alertas = []
    if len(enlaces) == len(anuncios):
        for x, u in zip(anuncios, enlaces):
            x["url_anuncio"] = u
    else:
        alertas.append(f"{len(anuncios)} asuntos y {len(enlaces)} enlaces a fichas: no se asocian")
    return anuncios, alertas


def resolver_pdfs(raiz: Path, pausa: float = 1.0, max_minutos: float = 0) -> int:
    """La ficha de cada anuncio de empleo (url_anuncio) enlaza su PDF firmado: se anota en url_pdf para descargar
    luego los textos. Devuelve cuántos se han resuelto."""
    from motor.autonomicos.comun import leer_jsonl
    inicio, hechos = time.monotonic(), 0
    for f in sorted((_base(raiz) / "oposiciones").glob("*/*/*.jsonl"), reverse=True):
        filas, cambio = leer_jsonl(f), False
        for x in filas:
            if x.get("url_pdf") or not x.get("url_anuncio") or ruta_texto_pdf(_base(raiz), x).exists():
                continue
            if max_minutos and (time.monotonic() - inicio) / 60 > max_minutos:
                break
            time.sleep(pausa)
            try:
                r = obtener(x["url_anuncio"], accept="text/html")
            except (ConnectionError, TimeoutError):
                continue
            m = RE_PDF_ANUNCIO.search(r.contenido.decode("utf-8", errors="replace")) if r.status == 200 else None
            if m:
                x["url_pdf"], cambio, hechos = WEB + html.unescape(m.group("url")), True, hechos + 1
        if cambio:
            escribir_jsonl(f, filas)
        if max_minutos and (time.monotonic() - inicio) / 60 > max_minutos:
            break
    return hechos


def es_local(x: dict) -> bool:
    return "administracion local" in normalizar(x.get("seccion") or "")


def convocante(x: dict) -> dict | None:
    e = x.get("entidad") or ""
    if normalizar(e).startswith("diputacion"):
        return {"tipo": "Diputación Provincial", "nombre": "León", "provincia": "León", "organismo": e}
    c = convocante_de_organismo(e or x.get("grupo") or "")
    if c and not c.get("provincia"):
        c["provincia"] = "León"
    return c


def seleccionar(filas: list[dict]) -> list[dict]:
    out = []
    for x in filas:
        if not es_empleo_estricto(x["titulo"]):
            continue
        local = es_local(x)
        out.append({**x, "ambito": "local" if local else "otro", **clasificar(x["titulo"], x.get("seccion")),
                    "convocante": convocante(x) if local else None})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "provinciales" / FUENTE


def _ruta(raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


def procesar_dia(d: date, raiz: Path, archivo: Archivo, pausa: float = 1.0) -> dict:
    r = obtener(url_dia(d), accept="text/html")
    inf = {"fecha": d.isoformat(), "status": r.status, "alertas": []}
    if r.status == 404:
        inf["resultado"] = "sin_boletin"
        return inf
    if r.status != 200:
        inf["resultado"] = "error_http"
        inf["alertas"].append(f"BOP León {d}: HTTP {r.status}")
        return inf
    f = ficha(r.contenido)
    if f["fecha"] != d.isoformat() or not f["url_sumario"]:
        inf["resultado"] = "error_formato"
        inf["alertas"].append(f"BOP León {d}: la ficha no trae número, fecha o sumario (posible cambio de formato)")
        return inf
    time.sleep(pausa)
    rs = obtener(f["url_sumario"], accept="application/pdf")
    if rs.status != 200 or rs.contenido[:4] != b"%PDF":
        inf["resultado"] = "error_http"
        inf["alertas"].append(f"BOP León {d}: sumario HTTP {rs.status}")
        return inf
    captura = archivo.guardar(FUENTE, d, rs.contenido, f["url_sumario"], "pdf", rs.status, rs.cabeceras)
    anuncios, alertas = parsear_sumario(rs.contenido)
    filas = [{**x, "numero_anuncio": f"{f['numero']}-{i:03d}", "id": f"BOPLEON-{d.year}-{f['numero']}-{i:03d}",
              "fecha": d.isoformat(), "boletin": f["numero"], "url_boletin": url_dia(d), "fuente": SIGLAS,
              "captura_sha256": captura["sha256"]} for i, x in enumerate(anuncios, 1)]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    inf.update({"resultado": "ok", "numero": f["numero"], "sha256": captura["sha256"], "disposiciones": len(filas),
                "empleo_publico": len(empleo)})
    inf["alertas"] += [f"BOP León {d}: {a}" for a in alertas]
    if not filas:
        inf["alertas"].append(f"BOP León {d}: sumario sin anuncios (posible cambio de formato)")
    return inf


ANTIGUOS = WEB + "/publica/boletines-anteriores/resultados-bop-anteriores/"
INICIO_ANTIGUOS = date(2022, 1, 1)
RE_ANTIGUO = re.compile(r'<a href="(?P<url>/export/sites/bop/publica/boletines-anteriores/\.galleries/Boletines-Anteriores/'
                        r'[^"]+\.pdf)"[^>]*title="BOP (?P<n>\d+)/(?P<a>\d{4})".*?Bolet[íi]n n[úu]m\.\s*\d+\s*de\s*'
                        r'(?P<d>\d{2})/(?P<m>\d{2})/(?P<a2>\d{4})', re.DOTALL)
RE_ENTRADA_ANT = re.compile(r"^(?P<t>.*?\S)\s*(?:\.{3,}|…+)\s*(?P<p>\d{1,4})\s*$|^(?P<t2>.*?[a-záéíóúñ)])\s+(?P<p2>\d{1,4})\s*$")
RE_CABECERA_ANT = re.compile(r"^(?:S\s?U\s?M\s?A\s?R\s?I\s?O|Edita:|Tel[ée]fono:|P[áa]gina web:|E-mail:|"
                             r"\w+, \d{1,2} de \w+ de \d{4}|Bolet[íi]n Oficial de la Provincia de Le[óo]n|"
                             r"www\.dipuleon\.es|N[úu]mero \d+)", re.IGNORECASE)
RE_DIPUTACION_ANT = re.compile(r"^(?:EXCMA\.?\s+|EXCELENT[ÍI]SIMA\s+)?DIPUTACI[ÓO]N\s+(?:PROVINCIAL\s+)?DE\s+LE[ÓO]N$",
                               re.IGNORECASE)
GRUPOS_ANT = {"ayuntamientos", "mancomunidades de municipios", "mancomunidades", "juntas vecinales",
              "entidades locales menores", "consorcios", "comunidades de regantes", "juntas electorales",
              "juzgados de lo social", "juzgados de primera instancia", "juzgados de primera instancia e instruccion",
              "juzgados de instruccion", "otras entidades", "diputacion provincial"}


def lista_antiguos(contenido: bytes) -> list[dict]:
    h = contenido.decode("utf-8", errors="replace")
    vistos = {}
    for m in RE_ANTIGUO.finditer(h):
        vistos.setdefault(m.group("url"), {"numero": int(m.group("n")), "url_pdf": WEB + html.unescape(m.group("url")),
                                           "fecha": f"{m.group('a2')}-{m.group('m')}-{m.group('d')}"})
    return sorted(vistos.values(), key=lambda b: (b["fecha"], b["numero"]))


def sumario_antiguo(paginas: list[str]) -> list[dict]:
    """Asuntos del sumario del PDF de un boletín anterior a 2025 (texto plano de pypdf): las páginas anteriores a la
    primera que citan los asuntos."""
    total = len(paginas)
    entradas, seccion, grupo, entidad, pendiente = [], None, None, None, ""
    for k, texto in enumerate(paginas[:6]):
        if entradas and k + 1 >= min(e["pagina"] for e in entradas):
            break
        for linea in texto.splitlines():
            lin = " ".join(linea.split())
            if not lin or RE_CABECERA_ANT.match(lin):
                continue
            m = RE_ENTRADA_ANT.match(lin)
            pag = int(m.group("p") or m.group("p2")) if m else None
            if m and 0 < pag <= total:
                titulo = " ".join(f"{pendiente} {m.group('t') or m.group('t2')}".split()).strip(" .")
                entradas.append({"seccion": seccion, "grupo": grupo, "entidad": entidad, "titulo": titulo,
                                 "pagina": pag})
                pendiente = ""
            elif RE_DIPUTACION_ANT.match(lin):  # «EXCMA. DIPUTACIÓN PROVINCIAL DE LEÓN»: lo local de la Diputación
                seccion, grupo, entidad, pendiente = "Administración Local", "Diputación", "Diputación Provincial de León", ""
            elif lin.upper() == lin and len(lin) > 3 and not re.search(r"\d", lin):
                seccion, grupo, entidad, pendiente = lin.title(), None, None, ""
            elif normalizar(lin) in {"anuncio", "anuncios", "edicto", "edictos"}:
                continue
            elif normalizar(lin) in GRUPOS_ANT:
                grupo, entidad, pendiente = lin, None, ""
            elif len(lin) >= 85:  # el comienzo de un asunto que sigue en la línea siguiente
                pendiente = f"{pendiente} {lin}"
            else:
                entidad, pendiente = lin, ""
    return entradas


VERSION_ANTIGUOS = "antiguos_v2"  # v2 (30/10/2026): la Diputación como entidad local; «Anuncio» no es una entidad


def procesar_antiguo(b: dict, raiz: Path, archivo: Archivo) -> dict:
    d = date.fromisoformat(b["fecha"])
    r = obtener(b["url_pdf"], accept="application/pdf")
    inf = {"fecha": b["fecha"], "numero": b["numero"], "status": r.status, "origen": "boletines_anteriores",
           "alertas": []}
    if r.status != 200 or r.contenido[:4] != b"%PDF":
        inf["resultado"] = "error_http"
        inf["alertas"].append(f"BOP León {d}: PDF HTTP {r.status}")
        return inf
    captura = archivo.guardar(FUENTE, d, r.contenido, b["url_pdf"], "pdf", r.status, r.cabeceras)
    return {**inf, **_leer_pdf_antiguo(b, r.contenido, captura, raiz)}


def _leer_pdf_antiguo(b: dict, pdf: bytes, captura: dict, raiz: Path) -> dict:
    """Sumario, selección y textos de un boletín anterior a 2025 a partir de su PDF entero."""
    from motor.extraccion.citas import citas
    from motor.limpieza import RE_DOCUMENTO, limpiar_texto
    from motor.provinciales.comun import CON_TEXTO
    from motor.provinciales.textos import cortar, paginas_pdf

    d = date.fromisoformat(b["fecha"])
    paginas = paginas_pdf(pdf)
    filas = [{**x, "numero_anuncio": f"{b['numero']}-{i:03d}", "id": f"BOPLEON-{d.year}-{b['numero']}-{i:03d}",
              "fecha": b["fecha"], "boletin": b["numero"], "url_boletin": b["url_pdf"], "url_pdf_boletin": b["url_pdf"],
              "fuente": SIGLAS, "captura_sha256": captura["sha256"]}
             for i, x in enumerate(sumario_antiguo(paginas), 1)]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    # Texto de los anuncios de empleo, cortado del propio PDF; de las listas de personas solo recuento y citas
    textos = 0
    if empleo:
        cortes = cortar(paginas, filas)
        for x in empleo:
            if x["id"] not in cortes:
                continue
            bruto, pags = cortes[x["id"]]
            if x.get("tipo_acto") in CON_TEXTO:
                datos = {"titulo": x["titulo"], **limpiar_texto(bruto)}
            else:
                datos = {"titulo": x["titulo"], "texto": None, "tablas": [], "solo_recuento": True,
                         "lineas_con_documento_de_identidad": sum(1 for l in bruto.splitlines() if RE_DOCUMENTO.search(l)),
                         "citas": citas(bruto)}
            escribir_json(ruta_texto_pdf(_base(raiz), x), {"id": x["id"], **datos, "paginas": pags,
                                                          "captura_sha256": captura["sha256"],
                                                          "capturado": captura.get("capturado"), "url": b["url_pdf"]})
            textos += 1
    inf = {"resultado": "ok", "sha256": captura["sha256"], "capturado": captura.get("capturado"),
           "url_pdf": b["url_pdf"], "version": VERSION_ANTIGUOS, "disposiciones": len(filas),
           "empleo_publico": len(empleo), "textos": textos, "alertas": []}
    if not filas:
        inf["alertas"].append(f"BOP León {d}: sumario sin anuncios (posible cambio de formato)")
    return inf


def reprocesar_antiguos(raiz: Path) -> int:
    """Vuelve a leer, desde su original en el almacén (sin pedirlo a la fuente), los boletines anteriores ya
    cargados con una versión vieja del lector."""
    from motor.almacen import Almacen, clave_original
    from motor.autonomicos.comun import leer_jsonl

    almacen, hechos, fallos = None, 0, 0
    for dia in sorted((_base(raiz) / "dias").glob("*/*/*.json")):
        inf = json.loads(dia.read_text(encoding="utf-8"))
        if inf.get("origen") != "boletines_anteriores" or inf.get("resultado") != "ok" \
                or inf.get("version") == VERSION_ANTIGUOS:
            continue
        d = date.fromisoformat(inf["fecha"])
        indice = raiz / "archivo" / "indices" / FUENTE / f"{d:%Y-%m}.jsonl"
        reg = next((x for x in (leer_jsonl(indice) if indice.exists() else []) if x.get("sha256") == inf["sha256"]), {})
        try:
            almacen = almacen or Almacen()
            pdf = almacen.leer(reg.get("clave") or clave_original(FUENTE, d, inf["sha256"], "pdf"))
        except Exception as e:  # noqa: BLE001 - sin almacén se deja para otra ejecución
            fallos += 1
            if fallos >= 5:
                print(f"BOP León: el almacén no responde ({type(e).__name__}); se deja para otra ejecución")
                break
            continue
        url = reg.get("url") or inf.get("url_pdf")
        nuevo = _leer_pdf_antiguo({"fecha": inf["fecha"], "numero": inf["numero"], "url_pdf": url}, pdf,
                                  {"sha256": inf["sha256"], "capturado": reg.get("capturado")}, raiz)
        escribir_json(dia, {**inf, **nuevo})
        hechos += 1
    print(f"BOP León anteriores releídos desde el almacén: {hechos}; sin original: {fallos}")
    return 0


def antiguos(raiz: Path, archivo: Archivo, pausa: float, max_minutos: float) -> int:
    """Boletines anteriores al portal nuevo, de diez en diez días hacia atrás desde el 16/02/2025."""
    inicio, informes, freno = time.monotonic(), [], Freno()
    ruta_hist = _base(raiz) / "antiguos.json"
    hist = json.loads(ruta_hist.read_text(encoding="utf-8")) if ruta_hist.exists() else {"tramos_completos": []}
    completos = set(hist["tramos_completos"])
    hasta, parar = INICIO - timedelta(days=1), False
    while hasta >= INICIO_ANTIGUOS and not parar:
        desde = max(hasta - timedelta(days=9), INICIO_ANTIGUOS)
        clave = f"{desde}/{hasta}"
        if clave not in completos:
            if max_minutos and (time.monotonic() - inicio) / 60 > max_minutos:
                break
            time.sleep(pausa)
            r = obtener(ANTIGUOS, accept="text/html", formulario={
                "busqueda": "", "fechaDesde": "", "fechaHasta": "", "BusquedaInicial": f"desde:{desde}|hasta:{hasta}|"})
            lista = lista_antiguos(r.contenido) if r.status == 200 else []
            if r.status != 200:
                print(f"::warning::BOP León anteriores {clave}: HTTP {r.status}")
                break
            bien = 0
            for b in reversed(lista):
                ruta = _ruta(raiz, "dias", date.fromisoformat(b["fecha"]), "json")
                if ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") == "ok":
                    bien += 1
                    continue
                if max_minutos and (time.monotonic() - inicio) / 60 > max_minutos:
                    parar = True
                    break
                time.sleep(pausa)
                try:
                    inf = procesar_antiguo(b, raiz, archivo)
                except (ConnectionError, TimeoutError) as e:
                    inf = {"fecha": b["fecha"], "resultado": "fuente_inaccesible", "alertas": [str(e)]}
                except Exception as e:  # noqa: BLE001 - un PDF raro no para la carga: queda anotado para revisarlo
                    import traceback
                    traceback.print_exc()
                    inf = {"fecha": b["fecha"], "numero": b["numero"], "resultado": "error_formato",
                           "alertas": [f"BOP León {b['fecha']}: {type(e).__name__}: {e}"[:300]]}
                escribir_json(ruta, inf)
                informes.append(inf)
                bien += inf["resultado"] == "ok"
                print(f"BOP León {b['fecha']} (anterior): {inf['resultado']} {inf.get('empleo_publico', '')}")
                if freno.anotar(inf):
                    parar = True
                    break
            if lista and bien == len(lista) and len(lista) < 15:
                completos.add(clave)
        hasta = desde - timedelta(days=1)
    escribir_json(ruta_hist, {"tramos_completos": sorted(completos)})
    print(f"BOP León anteriores: {len(informes)} boletines procesados")
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=date.fromisoformat, default=hoy - timedelta(days=1))
    p.add_argument("--hasta", type=date.fromisoformat, default=hoy)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    p.add_argument("--textos", action="store_true", help="PDF de cada anuncio de empleo (por su ficha)")
    p.add_argument("--antiguos", action="store_true", help="boletines anteriores al 17/02/2025 (PDF entero)")
    p.add_argument("--reprocesar-antiguos", action="store_true", help="releer desde el almacén los ya cargados")
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    if a.reprocesar_antiguos:
        return reprocesar_antiguos(a.salida)
    if a.antiguos:
        return antiguos(a.salida, archivo, a.pausa, a.max_minutos)
    if a.textos:
        resueltos = resolver_pdfs(a.salida, a.pausa, a.max_minutos / 2 if a.max_minutos else 0)
        hechos, errores, pendientes = descargar_textos_pdf(_base(a.salida), FUENTE, archivo,
                                                           a.max_minutos / 2 if a.max_minutos else 0, a.pausa)
        print(f"BOP León textos: {resueltos} PDF localizados, {hechos} descargados, {errores} errores, "
              f"{pendientes} pendientes")
        return 0
    inicio, informes, freno = time.monotonic(), [], Freno()
    d = a.hasta
    while d >= max(a.desde, INICIO):
        ruta = _ruta(a.salida, "dias", d, "json")
        hecho = ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") in {"ok", "sin_boletin"}
        if d.weekday() >= 5 and not hecho:
            escribir_json(ruta, {"fecha": d.isoformat(), "resultado": "sin_boletin", "nota": "fin de semana", "alertas": []})
            hecho = True
        if not hecho:
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                break
            try:
                inf = procesar_dia(d, a.salida, archivo, a.pausa)
            except (ConnectionError, TimeoutError) as e:
                inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            if not (inf.get("resultado") == "sin_boletin" and d >= hoy):
                escribir_json(ruta, inf)
            informes.append(inf)
            print(f"BOP León {d}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            if freno.anotar(inf):
                break
            time.sleep(a.pausa)
        d -= timedelta(days=1)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
