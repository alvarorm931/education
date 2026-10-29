"""Motor común de los boletines provinciales hechos con la plataforma SAGA (OpenCms «inpro»): Granada y Sevilla.

Formato verificado el 29/10/2026 desde GitHub:
  - Sumario de cada día, todos los anuncios en una página:
      {base}/publica/consulta-de-bops/buscador/BOP-DD-MM-AAAA/
    «BOP núm. 210 del 29/10/2026», «Resultados del 1 al 23 de 23».
    Cada anuncio (li.elementoListado): enlace al detalle /publica/buscador-anuncios/anuncio/{título}/, fecha,
    título (h3.titulo_elemento, a veces acortado con «...»), entidad (campo_1) y CVE (campo_3, BOP-GRA-2026-210022).
  - Detalle del anuncio: administración, sección, subsección, grupo y enlace al PDF firmado
    (/export/sites/bop/.galleries/Documentos-Anuncios-en-PDF/...pdf).
  - Un día sin boletín (o anterior al calendario del portal) responde 404.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (Freno, clasificar, convocante_de_organismo, descargar_textos, es_empleo_estricto,
                                     escribir_json, escribir_jsonl, leer_jsonl, nombre_propio)
from motor.boe.clasificar import normalizar
from motor.catalogo.territorio import municipio, provincia
from motor.http import obtener
from motor.provinciales.comun import CON_TEXTO, texto_pdf

MADRID = ZoneInfo("Europe/Madrid")

RE_ELEMENTO = re.compile(r'<li class="elementoListado[^"]*"[^>]*>(?P<c>.*?)</li>', re.DOTALL)
RE_ENLACE = re.compile(r'<a href="(?P<href>/publica/buscador-anuncios/anuncio/[^"]+)"')
RE_FECHA = re.compile(r'class="fecha_elemento">\s*<div class="container">\s*(?P<d>\d{2})/(?P<m>\d{2})/(?P<a>\d{4})')
RE_TITULO = re.compile(r'<h3 class="titulo_elemento">(?P<t>.*?)</h3>', re.DOTALL)
RE_ENTIDAD = re.compile(r'campo_1">\s*<div class="container">(?P<e>.*?)</div>', re.DOTALL)
RE_CVE = re.compile(r'campo_3">\s*(?P<cve>BOP[A-Z]*-(?:[A-Z]+-)?\d{4}-\d+)')  # BOP-GRA-2026-210022, BOPH-2026-207001
RE_RESULTADOS = re.compile(r"Resultados del \d+ al (?P<hasta>\d+) de (?P<total>\d+)")
RE_NUMERO = re.compile(r"BOP núm\. (?P<n>\d+)(?:</strong>)?\s+del\s+(?P<d>\d{2})/(?P<m>\d{2})/(?P<a>\d{4})")
RE_PDF = re.compile(r'href="(?P<pdf>/export/sites/[^"]+\.pdf)"')
RE_DATO = re.compile(r"(?P<k>Administración|Sección|Subsección|Grupo:?)\s*</?[^>]*>\s*(?:<[^>]+>\s*)*(?P<v>[^<]{2,200})")


@dataclass(frozen=True)
class Boletin:
    fuente: str
    siglas: str
    base: str
    provincia: str
    nombres: tuple[str, ...]
    inicio: date            # primer día que el portal sirve con este formato
    cabecera_pdf: re.Pattern

    def url_dia(self, d: date) -> str:
        return f"{self.base}/publica/consulta-de-bops/buscador/BOP-{d:%d-%m-%Y}/"


def _texto(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def parsear_dia(b: Boletin, contenido: str) -> dict:
    n = RE_NUMERO.search(contenido)
    anuncios = []
    for m in RE_ELEMENTO.finditer(contenido):
        c = m.group("c")
        e, f, t, cve = RE_ENLACE.search(c), RE_FECHA.search(c), RE_TITULO.search(c), RE_CVE.search(c)
        if not (e and t and cve):
            continue
        ent = RE_ENTIDAD.search(c)
        anuncios.append({
            "id": cve.group("cve"), "cve": cve.group("cve"), "titulo": _texto(t.group("t")),
            "organismo": _texto(ent.group("e")) if ent else None,
            "fecha": f"{f.group('a')}-{f.group('m')}-{f.group('d')}" if f else None,
            "url_html": b.base + html.unescape(e.group("href")), "url_pdf": None, "fuente": b.siglas,
        })
    return {"numero": n.group("n") if n else None,
            "fecha": f"{n.group('a')}-{n.group('m')}-{n.group('d')}" if n else None, "anuncios": anuncios}


def es_local(b: Boletin, organismo: str | None) -> bool:
    o = normalizar(organismo or "")
    if municipio(organismo, provincia(b.provincia)["codigo"]):  # Sevilla pone solo el nombre del municipio
        return True
    return o.startswith(("ayuntamiento", "excmo. ayuntamiento", "ilmo. ayuntamiento", "mancomunidad", "consorcio",
                         "entidad local", "e.l.a", "ela ", "diputacion", "area de", "organismo autonomo", "patronato",
                         "instituto municipal", "agencia municipal", "empresa municipal", "sociedad municipal"))


def convocante(b: Boletin, organismo: str | None) -> dict | None:
    o = (organismo or "").strip()
    if not o:
        return None
    if normalizar(o).startswith("area de"):  # áreas de la Diputación
        return {"tipo": "Diputación Provincial", "nombre": b.provincia, "provincia": b.provincia, "organismo": o}
    m = municipio(o, provincia(b.provincia)["codigo"])
    if m:
        return {"tipo": "Ayuntamiento", "nombre": nombre_propio(o), "provincia": b.provincia, "organismo": o}
    c = convocante_de_organismo(o)
    if c and c.get("tipo") is None:
        c["nombre"] = nombre_propio(c["nombre"])
    if c and not c.get("provincia"):
        c["provincia"] = b.provincia
    return c


def seleccionar(b: Boletin, anuncios: list[dict]) -> list[dict]:
    out = []
    for x in anuncios:
        if not es_empleo_estricto(x["titulo"]):
            continue
        if not es_local(b, x.get("organismo")):  # lo autonómico y estatal ya llega por su propio boletín
            continue
        out.append({**x, "ambito": "local", **clasificar(x["titulo"]), "convocante": convocante(b, x.get("organismo"))})
    return out


def _base(b: Boletin, raiz: Path) -> Path:
    return raiz / "datos" / "provinciales" / b.fuente


def _ruta(b: Boletin, raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return _base(b, raiz) / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


def procesar_dia(b: Boletin, d: date, raiz: Path, archivo: Archivo) -> dict:
    url = b.url_dia(d)
    r = obtener(url, accept="text/html")
    informe = {"fecha": d.isoformat(), "status": r.status, "alertas": []}
    if r.status == 404:
        informe.update({"resultado": "sin_boletin", "nota": "404: sin boletín ese día o fuera del calendario del portal"})
        return informe
    if r.status != 200:
        informe["resultado"] = "error_http"
        informe["alertas"].append(f"{b.siglas} {d}: HTTP {r.status}")
        return informe
    texto = r.contenido.decode("utf-8", errors="replace")
    s = parsear_dia(b, texto)
    if s["fecha"] and s["fecha"] != d.isoformat():
        informe["resultado"] = "sin_boletin"
        return informe
    captura = archivo.guardar(b.fuente, d, r.contenido, url, "html", r.status, r.cabeceras)
    anuncios, pagina = list(s["anuncios"]), 1
    res = RE_RESULTADOS.search(texto)
    # Huesca pagina de 20 en 20 (Granada y Sevilla lo dan todo en una página): …/BOP-DD-MM-AAAA/?page=2
    while res and int(res.group("hasta")) < int(res.group("total")) and pagina < 20:
        pagina += 1
        time.sleep(1)
        rp = obtener(f"{url}?page={pagina}", accept="text/html")
        if rp.status != 200:
            informe["alertas"].append(f"{b.siglas} {d}: página {pagina} HTTP {rp.status}")
            break
        texto = rp.contenido.decode("utf-8", errors="replace")
        anuncios += parsear_dia(b, texto)["anuncios"]
        archivo.guardar(b.fuente, d, rp.contenido, f"{url}?page={pagina}", "html", rp.status, rp.cabeceras)
        res = RE_RESULTADOS.search(texto)
    anuncios = list({x["id"]: x for x in anuncios}.values())
    filas = [{**x, "boletin": s["numero"], "captura_sha256": captura["sha256"]} for x in anuncios]
    total = RE_RESULTADOS.search(r.contenido.decode("utf-8", errors="replace"))
    if total and len(filas) != int(total.group("total")):
        informe["alertas"].append(f"{b.siglas} {d}: {len(filas)} anuncios leídos de {total.group('total')}")
    empleo = seleccionar(b, filas)
    escribir_jsonl(_ruta(b, raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(b, raiz, "oposiciones", d), empleo)
    informe.update({"resultado": "ok", "numero": s["numero"], "sha256": captura["sha256"], "disposiciones": len(filas),
                    "empleo_publico": len(empleo)})
    if not filas:
        informe["alertas"].append(f"{b.siglas} {d}: sumario sin anuncios (posible cambio de formato)")
    return informe


def datos_detalle(contenido: bytes) -> dict:
    """Del detalle de un anuncio: el enlace al PDF y la clasificación del boletín."""
    h = contenido.decode("utf-8", errors="replace")
    pdf = RE_PDF.search(h)
    datos = {m.group("k").rstrip(":").lower(): " ".join(m.group("v").split()) for m in RE_DATO.finditer(h)}
    return {"pdf": html.unescape(pdf.group("pdf")) if pdf else None, **datos}


def ruta_texto(b: Boletin, raiz: Path, x: dict) -> Path:
    return _base(b, raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"


def textos_pendientes(b: Boletin, raiz: Path) -> list[dict]:
    lista = []
    for f in (_base(b, raiz) / "oposiciones").glob("*/*/*.jsonl"):
        lista += [x for x in leer_jsonl(f) if x.get("url_html") and not ruta_texto(b, raiz, x).exists()]
    lista.sort(key=lambda x: x["fecha"], reverse=True)
    return sorted(lista, key=lambda x: (0 if x.get("tipo_acto") in CON_TEXTO else 1,
                                        0 if x.get("alcance") in (None, "acceso") else 1))


def descargar_texto(b: Boletin, x: dict) -> tuple[bytes | None, str | None, dict]:
    """Detalle del anuncio y su PDF: dos peticiones. Devuelve (pdf, url del pdf, datos del detalle)."""
    r = obtener(x["url_html"], accept="text/html")
    if r.status != 200:
        return None, None, {}
    d = datos_detalle(r.contenido)
    if not d.get("pdf"):
        return None, None, d
    url_pdf = b.base + d["pdf"] if d["pdf"].startswith("/") else d["pdf"]
    time.sleep(1)
    p = obtener(url_pdf, accept="application/pdf")
    return (p.contenido if p.status == 200 else None), url_pdf, d


def main(b: Boletin, argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=date.fromisoformat, default=hoy - timedelta(days=1))
    p.add_argument("--hasta", type=date.fromisoformat, default=hoy)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--textos", action="store_true")
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())

    if a.textos:
        inicio, hechos, errores = time.monotonic(), 0, 0
        pend = textos_pendientes(b, a.salida)
        for x in pend:
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                break
            try:
                pdf, url_pdf, det = descargar_texto(b, x)
                if pdf is None:
                    errores += 1
                    continue
                datos = texto_pdf(pdf, x.get("tipo_acto") in CON_TEXTO, b.cabecera_pdf)
            except Exception:  # red caída o PDF ilegible: no detiene la carga, queda pendiente
                errores += 1
                continue
            captura = archivo.guardar(b.fuente + "-texto", date.fromisoformat(x["fecha"]), pdf, url_pdf, "pdf", 200)
            escribir_json(ruta_texto(b, a.salida, x), {"id": x["id"], **datos, "detalle": det,
                                                        "captura_sha256": captura["sha256"],
                                                        "capturado": captura["capturado"], "url": url_pdf})
            hechos += 1
            time.sleep(a.pausa)
        print(f"{b.siglas} textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        return 0

    inicio, informes = time.monotonic(), []
    freno = Freno()
    d = a.hasta
    desde = max(a.desde, b.inicio)
    while d >= desde:
        ruta = _ruta(b, a.salida, "dias", d, "json")
        hecho = ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") in {"ok", "sin_boletin"}
        if d.weekday() >= 5 and not hecho:
            escribir_json(ruta, {"fecha": d.isoformat(), "resultado": "sin_boletin", "nota": "fin de semana",
                                 "alertas": []})
            hecho = True
        if not hecho or d >= hoy - timedelta(days=1):
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                break
            try:
                inf = procesar_dia(b, d, a.salida, archivo)
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
