"""Motor común de los boletines provinciales hechos con la plataforma de la Diputació de Barcelona.

La usan el BOPB (Barcelona, https://bop.diba.cat) y el BOPT (Tarragona, https://www.dipta.cat/bopt/web).
Verificado el 29/10/2026 desde GitHub (también para 2022):
  - Día filtrado por tipo de anuncio de personal, 20 anuncios por página:
      {base}/anteriors/2026-10-28?bopb_dia%5BtipusAnunci%5D={código}      (Barcelona 60, Tarragona 23)
      {base}/anteriors/2026-10-28/2?bopb_dia%5BtipusAnunci%5D={código}
    «S'han trobat 27 resultats per la seva cerca, mostrant del 1 al 20».
    Cada anuncio: enlace .../anunci/{número}/{título}, anunciante (h3), título (p), «Registre» (CVE) y fecha.
  - Sábados y domingos el BOPB responde 500 (no hay boletín). Un festivo con boletín y sin anuncios de personal
    devuelve la página del día sin resultados.
  - Texto: solo en PDF, {base}/anunci/descarrega-pdf/{número}. De las listas de admitidos, aprobados y
    nombramientos solo se guarda cuántas líneas traen un documento de identidad, no el texto.
  - Los anuncios se publican en la lengua del anunciante, casi siempre en catalán.

robots.txt del BOPB (bop.diba.cat), leído el 30/10/2026: prohíbe /anteriors/, los PDF (/anunci/descarrega-pdf/) y
toda dirección con «?». Por eso el BOPB se lee de sus datos abiertos: el canal RSS del boletín del día
(/dades-obertes/butlleti-del-dia/feed, permitido), con anunciante, registro, tipo de anuncio, fecha, título y enlace
de cada anuncio. Solo da el día en curso: lo de días anteriores ya leído se conserva. Sin texto (está en el PDF).
El BOPT (dipta.cat) lo permite todo y sigue por los días.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (Freno, RE_NO_EMPLEO, RE_PUESTO, _seleccion_inequivoca, clasificar,
                                     convocante_de_organismo, descargar_textos, escribir_json, escribir_jsonl,
                                     leer_jsonl)
from motor.boe.clasificar import normalizar
from motor.http import obtener
from motor.provinciales.comun import CON_TEXTO, texto_pdf

MADRID = ZoneInfo("Europe/Madrid")
POR_PAGINA = 20

RE_TARJETA = re.compile(r'<div class="card bg-white[^"]*">(?P<c>.*?)</div>\s*</div>', re.DOTALL)
RE_ENLACE = re.compile(r'<a href="(?P<href>[^"]*/anunci/(?P<num>\d+)/[^"]*)"[^>]*>(?P<anunciante>.*?)</a>', re.DOTALL)
RE_TITULO = re.compile(r"</h3>\s*<p>(?P<t>.*?)</p>", re.DOTALL)
RE_REGISTRO = re.compile(r"Registre</span>:\s*(?P<r>[\d-]+)")
RE_FECHA = re.compile(r"publicaci[oó]</span>:\s*(?P<d>\d{2})/(?P<m>\d{2})/(?P<a>\d{4})")
RE_DIA = re.compile(r'<time datetime="(?P<f>\d{4}-\d{2}-\d{2})"')
RE_TOTAL = re.compile(r"S(?:&#039;|')han trobat (?P<n>\d+) resultats")


@dataclass(frozen=True)
class Boletin:
    fuente: str             # carpeta en datos/provinciales/ y en archivo/
    siglas: str
    base: str               # sin barra final
    tipus_personal: int     # código del filtro de anuncios de personal
    provincia: str
    nombres: tuple[str, ...]
    cabecera_pdf: re.Pattern
    feed: str | None = None  # canal RSS de datos abiertos del boletín del día (BOPB)

    def url_dia(self, d: date, pagina: int = 1) -> str:
        return (f"{self.base}/anteriors/{d:%Y-%m-%d}" + (f"/{pagina}" if pagina > 1 else "")
                + f"?bopb_dia%5BtipusAnunci%5D={self.tipus_personal}")

    def raiz_web(self) -> str:
        """https://www.dipta.cat/bopt/web -> https://www.dipta.cat (los enlaces de anuncio son absolutos al host)."""
        return re.match(r"https?://[^/]+", self.base).group(0)


def _texto(fragmento: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragmento)).split())


def parsear_dia(b: Boletin, contenido: str) -> dict:
    dia = RE_DIA.search(contenido)
    total = RE_TOTAL.search(contenido)
    anuncios = []
    for t in RE_TARJETA.finditer(contenido):
        c = t.group("c")
        e, ti, r, f = RE_ENLACE.search(c), RE_TITULO.search(c), RE_REGISTRO.search(c), RE_FECHA.search(c)
        if not (e and ti and r):
            continue
        href = e.group("href").split("?")[0]
        anuncios.append({
            "id": f"{b.siglas}-{r.group('r')}", "cve": r.group("r"), "numero_anuncio": e.group("num"),
            "anunciante": _texto(e.group("anunciante")), "titulo": _texto(ti.group("t")),
            "fecha": f"{f.group('a')}-{f.group('m')}-{f.group('d')}" if f else None,
            "url_html": (b.raiz_web() + href) if href.startswith("/") else href,
            "url_pdf": f"{b.base}/anunci/descarrega-pdf/{e.group('num')}", "fuente": b.siglas,
            "tipo_anuncio": "Personal",
        })
    return {"fecha": dia.group("f") if dia else None, "total": int(total.group("n")) if total else 0,
            "anuncios": anuncios}


def ambito(anunciante: str) -> str:
    a = normalizar(anunciante or "")
    if a.startswith("universitat"):
        return "universidad"
    if a.startswith(("generalitat", "departament", "institut catala", "servei catala")):
        return "autonomico"
    if a.startswith(("ministeri", "delegacio del govern", "subdelegacio", "administracio general")):
        return "estatal"
    return "local"


def seleccionar(b: Boletin, anuncios: list[dict]) -> list[dict]:
    """Todo el filtro de personal es empleo público, salvo lo que no lo es aunque caiga ahí (jueces de paz,
    viviendas, ayudas)."""
    out = []
    for x in anuncios:
        t = normalizar(x["titulo"]).replace("´", "'")
        # «técnico/a de comercio», «jefe de sección de vivienda»: el tema excluido es el del puesto
        if RE_NO_EMPLEO.search(t) and not (_seleccion_inequivoca(t) or
                                           any(m.group(0) != "personal" for m in RE_PUESTO.finditer(t))):
            continue
        amb = ambito(x["anunciante"])
        conv = convocante_de_organismo(x["anunciante"]) if amb == "local" else None
        if conv and not conv.get("provincia"):
            conv["provincia"] = b.provincia
        out.append({**x, "ambito": amb, **clasificar(x["titulo"]), "convocante": conv,
                    "organismo": x["anunciante"]})
    return out


def _base(b: Boletin, raiz: Path) -> Path:
    return raiz / "datos" / "provinciales" / b.fuente


def _ruta(b: Boletin, raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return _base(b, raiz) / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


def procesar_dia(b: Boletin, d: date, raiz: Path, archivo: Archivo, pausa: float = 1.0) -> dict:
    informe = {"fecha": d.isoformat(), "alertas": []}
    anuncios, total, paginas = [], None, 1
    pagina = 1
    while pagina <= paginas:
        url = b.url_dia(d, pagina)
        r = obtener(url, accept="text/html")
        informe["status"] = r.status
        if r.status != 200:
            if pagina == 1 and r.status >= 500 and d.weekday() >= 5:
                informe["resultado"] = "sin_boletin"
                return informe
            informe["resultado"] = "error_http"
            informe["alertas"].append(f"{b.siglas} {d} página {pagina}: HTTP {r.status}")
            return informe
        s = parsear_dia(b, r.contenido.decode("utf-8", errors="replace"))
        if s["fecha"] != d.isoformat():
            if pagina == 1 and d.weekday() >= 5:
                informe["resultado"] = "sin_boletin"
                return informe
            informe["resultado"] = "error_formato"
            informe["alertas"].append(f"{b.siglas} {d}: la página no es la del día (posible cambio de formato)")
            return informe
        archivo.guardar(b.fuente, d, r.contenido, url, "html", r.status, r.cabeceras)
        if total is None:
            total = s["total"]
            paginas = max(1, math.ceil(total / POR_PAGINA))
        anuncios += s["anuncios"]
        pagina += 1
        if pagina <= paginas:
            time.sleep(pausa)
    empleo = seleccionar(b, anuncios)
    escribir_jsonl(_ruta(b, raiz, "disposiciones", d), anuncios)
    escribir_jsonl(_ruta(b, raiz, "oposiciones", d), empleo)
    informe.update({"resultado": "ok", "paginas": paginas, "anuncios_personal": total,
                    "disposiciones": len(anuncios), "empleo_publico": len(empleo)})
    if total and len(anuncios) != total:
        informe["alertas"].append(f"{b.siglas} {d}: {len(anuncios)} anuncios leídos de {total} (posible cambio de formato)")
    return informe


RE_ITEM = re.compile(r"<item>(?P<c>.*?)</item>", re.S)
RE_ETIQUETA = {k: re.compile(rf"<{k}>(?P<v>.*?)</{k}>", re.S) for k in ("title", "link", "description", "category")}
RE_CANAL_FECHA = re.compile(r"<title>[^<]*del dia (?P<d>\d{2})/(?P<m>\d{2})/(?P<a>\d{4})")
RE_FEED_DATOS = re.compile(r"Registre:</strong>\s*(?P<r>[\d-]+)\s*-\s*<strong>Tipus d.anunci:</strong>\s*(?P<t>.*?)"
                           r"\s*-\s*<strong>Data publicaci[oó]:</strong>\s*(?P<d>\d{2})/(?P<m>\d{2})/(?P<a>\d{4})", re.S)


def parsear_feed(b: Boletin, contenido: bytes) -> dict:
    x = contenido.decode("utf-8", errors="replace")
    canal = RE_CANAL_FECHA.search(x)
    anuncios = []
    for it in RE_ITEM.finditer(x):
        c = it.group("c")
        campo = {k: (r.search(c).group("v") if r.search(c) else "") for k, r in RE_ETIQUETA.items()}
        desc = html.unescape(re.sub(r"^<!\[CDATA\[|\]\]>$", "", campo["description"].strip()))
        datos = RE_FEED_DATOS.search(desc)
        num = re.search(r"/anunci/(\d+)", campo["link"])
        if not (datos and num):
            continue  # p. ej. el elemento «Sumari d'avui»
        parrafos = re.findall(r"<p>(.*?)</p>", desc, re.S)
        titulo = _texto(parrafos[1]) if len(parrafos) > 1 else ""
        anuncios.append({
            "id": f"{b.siglas}-{datos.group('r')}", "cve": datos.group("r"), "numero_anuncio": num.group(1),
            "anunciante": _texto(campo["title"]), "titulo": titulo,
            "fecha": f"{datos.group('a')}-{datos.group('m')}-{datos.group('d')}",
            "url_html": f"{b.base}/anunci/{num.group(1)}", "url_pdf": f"{b.base}/anunci/descarrega-pdf/{num.group(1)}",
            "fuente": b.siglas, "tipo_anuncio": _texto(datos.group("t")), "categoria": _texto(campo["category"]),
        })
    return {"fecha": f"{canal.group('a')}-{canal.group('m')}-{canal.group('d')}" if canal else None,
            "anuncios": anuncios}


def procesar_feed(b: Boletin, raiz: Path, archivo: Archivo) -> dict:
    r = obtener(b.feed, accept="application/rss+xml, text/xml")
    if r.status != 200:
        return {"fecha": None, "resultado": "error_http", "alertas": [f"{b.siglas} canal RSS: HTTP {r.status}"]}
    s = parsear_feed(b, r.contenido)
    if not s["fecha"]:
        return {"fecha": None, "resultado": "error_formato", "alertas": [f"{b.siglas} canal RSS sin fecha"]}
    d = date.fromisoformat(s["fecha"])
    informe = {"fecha": s["fecha"], "status": 200, "alertas": [], "origen": "canal RSS de datos abiertos"}
    if not s["anuncios"]:
        informe["resultado"] = "sin_boletin"
        return informe
    otros = {x["fecha"] for x in s["anuncios"]} - {s["fecha"]}
    if otros:
        informe["alertas"].append(f"{b.siglas} {d}: anuncios con otras fechas en el canal {sorted(otros)[:3]}")
    captura = archivo.guardar(b.fuente, d, r.contenido, b.feed, "xml", r.status, r.cabeceras)
    filas = [{**x, "captura_sha256": captura["sha256"]} for x in s["anuncios"]]
    personal = [x for x in filas if normalizar(x["tipo_anuncio"]).startswith("personal")]
    empleo = seleccionar(b, personal)
    escribir_jsonl(_ruta(b, raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(b, raiz, "oposiciones", d), empleo)
    informe.update({"resultado": "ok", "disposiciones": len(filas), "anuncios_personal": len(personal),
                    "empleo_publico": len(empleo)})
    return informe


def texto_disposicion(b: Boletin, contenido: bytes, con_texto: bool = True) -> dict:
    return texto_pdf(contenido, con_texto, b.cabecera_pdf)


def ruta_texto(b: Boletin, raiz: Path, x: dict) -> Path:
    return _base(b, raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"


def textos_pendientes(b: Boletin, raiz: Path) -> list[dict]:
    lista = []
    for f in (_base(b, raiz) / "oposiciones").glob("*/*/*.jsonl"):
        lista += [x for x in leer_jsonl(f) if x.get("url_pdf") and not ruta_texto(b, raiz, x).exists()]
    lista.sort(key=lambda x: x["fecha"], reverse=True)
    return sorted(lista, key=lambda x: (0 if x.get("tipo_acto") in CON_TEXTO else 1,
                                        0 if x.get("alcance") in (None, "acceso") else 1))


def main(b: Boletin, argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=date.fromisoformat, default=None,
                   help="por el listado por días; sin él, el boletín del día (por el canal de datos si lo hay)")
    p.add_argument("--hasta", type=date.fromisoformat, default=hoy)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--textos", action="store_true")
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())

    if a.textos:
        pend = textos_pendientes(b, a.salida)
        hechos, errores = descargar_textos(
            pend, lambda x: ruta_texto(b, a.salida, x), lambda x: x["url_pdf"],
            lambda c, x: texto_disposicion(b, c, x.get("tipo_acto") in CON_TEXTO), archivo, b.fuente,
            a.max_minutos, a.pausa, accept="application/pdf", ext="pdf", por_registro=True)
        print(f"{b.siglas} textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        return 0

    if b.feed and a.desde is None:
        # El boletín del día, por su canal de datos abiertos
        try:
            inf = procesar_feed(b, a.salida, archivo)
        except (ConnectionError, TimeoutError) as e:
            inf = {"fecha": None, "resultado": "fuente_inaccesible", "alertas": [str(e)]}
        if inf.get("fecha"):
            escribir_json(_ruta(b, a.salida, "dias", date.fromisoformat(inf["fecha"]), "json"), inf)
        print(f"{b.siglas} {inf.get('fecha')}: {inf['resultado']} {inf.get('empleo_publico', '')} "
              f"{'; '.join(inf.get('alertas', []))}")
        return 1 if inf["resultado"] in {"error_formato", "fuente_inaccesible", "error_http"} else 0

    a.desde = a.desde or hoy - timedelta(days=1)
    inicio, informes = time.monotonic(), []
    freno = Freno()
    d = a.hasta
    # Del más reciente al más antiguo: lo nuevo primero; lo hecho (ok o sin boletín) no se repite
    while d >= a.desde:
        ruta = _ruta(b, a.salida, "dias", d, "json")
        hecho = ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") in {"ok", "sin_boletin"}
        if not hecho or d >= hoy - timedelta(days=1):
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                break
            try:
                inf = procesar_dia(b, d, a.salida, archivo, a.pausa)
            except (ConnectionError, TimeoutError) as e:
                inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            if not (inf.get("resultado") == "sin_boletin" and d >= hoy):
                escribir_json(ruta, inf)
            informes.append(inf)
            if freno.anotar(inf):
                break
            print(f"{b.siglas} {d}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            time.sleep(a.pausa)
        d -= timedelta(days=1)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    for x in alertas[:30]:
        print(" -", x)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0
