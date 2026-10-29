"""Conector del Boletín Oficial de Canarias (BOC) por sus páginas estáticas de índice.

Formato verificado el 29/10/2026 desde GitHub (también para 2022):
  - Índice del año: https://www.gobiernodecanarias.org/boc/AAAA/index.html
      enlaces «/boc/AAAA/NNN/index.html» con título «Ir al boletín BOC 210/2026 (2026-10-21)»: número y fecha de
      todos los boletines del año.
  - Índice del boletín: https://www.gobiernodecanarias.org/boc/AAAA/NNN/  (NNN con tres cifras; 404 si no existe)
      h4 (sección «II. Autoridades y personal», o bloque «Administración Local» / «Otras Administraciones
      Públicas»), h3.titboc (subsección «Oposiciones y concursos», «Nombramientos, situaciones e incidencias»...),
      h5 (organismo) y li.justificado_boc (número, título, CVE «BOC-A-2026-210-3613», enlace a la versión HTML
      «/boc/2026/210/3613.html» o «/boc/2022/001/001.html» y al PDF oficial en sede.gobiernodecanarias.org).
  - Disposición en HTML (versión no oficial; la oficial es el PDF): texto en párrafos tras el título.
  - Empleo público: «II. Autoridades y personal» > «Oposiciones y concursos» (todo) y «Nombramientos...»
    (solo resultados de procesos); «V. Anuncios» seleccionados por el título. Las islas se traducen a provincia.

Uso:
  python -m motor.autonomicos.boc --salida ruta/                                  # año en curso, lo que falte
  python -m motor.autonomicos.boc --desde 2022-01-01 --saltar-existentes --max-minutos 20 --salida ruta/
  python -m motor.autonomicos.boc --textos --max-minutos 20 --salida ruta/        # textos pendientes

Guarda en datos/autonomicos/boc/: boletines/ (informe por boletín), disposiciones/, oposiciones/ y textos/.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo
from motor.autonomicos.comun import (clasificar, convocante_de_organismo, descargar_textos, es_empleo_por_titulo,
                                     es_resultado, escribir_json, escribir_jsonl, leer_jsonl)
from motor.boe.clasificar import normalizar
from motor.extraccion.texto_es import MESES
from motor.http import obtener
from motor.limpieza import limpiar_html, texto_de

FUENTE = "boc"
MADRID = ZoneInfo("Europe/Madrid")
BASE = "https://www.gobiernodecanarias.org"
ISLA_A_PROVINCIA = {
    "gran canaria": "Las Palmas", "lanzarote": "Las Palmas", "fuerteventura": "Las Palmas",
    "tenerife": "Santa Cruz de Tenerife", "la palma": "Santa Cruz de Tenerife",
    "la gomera": "Santa Cruz de Tenerife", "el hierro": "Santa Cruz de Tenerife",
}
RE_BOLETIN_ANIO = re.compile(r'href="/boc/(?P<a>\d{4})/(?P<n>\d{3})/index\.html"\s*title="Ir al boletín BOC '
                             r'(?P<n2>\d+)/\d{4} \((?P<f>\d{4}-\d{2}-\d{2})\)"')
RE_CABECERA = re.compile(r"<h2>\s*BOC\s+Nº\s*(?P<n>\d+)\.\s*\w+\s+(?P<d>\d{1,2})\s+de\s+(?P<m>[a-záéíóú]+)\s+de\s+"
                         r"(?P<a>\d{4})\s*</h2>", re.IGNORECASE)
RE_TOKEN = re.compile(r'<h4[^>]*>(?P<h4>.*?)</h4>|<h3 class="titboc">(?P<h3>.*?)</h3>|<h5>(?P<h5>.*?)</h5>'
                      r'|<li class="justificado_boc">(?P<li>.*?)</li>', re.DOTALL)
RE_SECCION = re.compile(r"^[IVX]+\.\s")
RE_ANUNCIO_EMPLEO = re.compile(r"\b(proceso selectivo|procesos selectivos|pruebas selectivas|plazas?|bolsa|oposicion|"
                               r"convocatoria|funcionari\w+ de carrera|personal laboral fijo)\b")


def url_anio(anio: int) -> str:
    return f"{BASE}/boc/{anio}/index.html"


def url_boletin(anio: int, numero: int) -> str:
    return f"{BASE}/boc/{anio}/{numero:03d}/"


def boletines_del_anio(html: str) -> list[tuple[int, str]]:
    """(número, fecha ISO) de cada boletín del índice anual, en orden."""
    vistos = {}
    for m in RE_BOLETIN_ANIO.finditer(html):
        vistos[int(m.group("n"))] = m.group("f")
    return sorted(vistos.items())


def parsear_boletin(html: str, anio: int, numero: int, fecha: str) -> list[dict]:
    seccion = subseccion = bloque = organismo = None
    filas = []
    for t in RE_TOKEN.finditer(html):
        if t.group("h4") is not None:
            v = texto_de(t.group("h4"))
            if RE_SECCION.match(v):
                seccion, subseccion, bloque, organismo = v, None, None, None
            else:
                bloque, organismo = v, None
        elif t.group("h3") is not None:
            subseccion, bloque, organismo = texto_de(t.group("h3")), None, None
        elif t.group("h5") is not None:
            organismo = texto_de(t.group("h5"))
        elif t.group("li"):
            li = t.group("li")
            enlaces = re.findall(r'<a href="([^"]*)"[^>]*>(.*?)</a>', li, re.DOTALL)
            cve = re.search(r"\b(BOC-A-\d{4}-\d+-\d+)\b", li)
            html_rel = re.search(r'href="(/boc/\d{4}/\d+/\d+\.html)"', li)
            if not cve or len(enlaces) < 2:
                continue
            filas.append({
                "id": cve.group(1), "fecha": fecha, "boletin": numero, "numero_disposicion": texto_de(enlaces[0][1]),
                "seccion": seccion, "subseccion": subseccion, "bloque": bloque, "organismo": organismo,
                "titulo": texto_de(enlaces[1][1]),
                "url_html": BASE + html_rel.group(1) if html_rel else None,
                "url_pdf": enlaces[0][0] if enlaces[0][0].endswith(".pdf") else None,
                "fuente": "BOC",
            })
    return filas


def cabecera(html: str) -> tuple[int | None, str | None]:
    m = RE_CABECERA.search(html)
    if not m or not MESES.get(normalizar(m.group("m"))):
        return None, None
    return int(m.group("n")), date(int(m.group("a")), MESES[normalizar(m.group("m"))], int(m.group("d"))).isoformat()


def ambito(x: dict) -> str:
    o = normalizar(x.get("organismo") or "")
    if normalizar(x.get("bloque") or "") == "administracion local" or \
            o.startswith(("ayuntamiento", "cabildo", "mancomunidad", "consorcio")):
        return "local"
    if o.startswith("universidad"):
        return "universidad"
    if normalizar(x.get("bloque") or "") == "otras administraciones publicas":
        return "otro"
    return "autonomico"


def es_empleo_publico(x: dict) -> bool:
    s, sub, t = normalizar(x.get("seccion") or ""), normalizar(x.get("subseccion") or ""), x.get("titulo") or ""
    if s.startswith("ii."):
        if "oposiciones" in sub:
            return True
        return es_resultado(t)
    if s.startswith("v."):
        return es_empleo_por_titulo(t) and bool(RE_ANUNCIO_EMPLEO.search(normalizar(t)))
    return False


def convocante(organismo: str) -> dict | None:
    c = convocante_de_organismo(organismo)
    if not c:
        return None
    isla = None
    if c.get("tipo") == "Cabildo Insular":
        isla = c["nombre"]
    elif c.get("provincia") and normalizar(c["provincia"]) in ISLA_A_PROVINCIA:
        isla = c["provincia"]
    if isla:
        c["isla"] = isla
        c["provincia"] = ISLA_A_PROVINCIA.get(normalizar(isla), c.get("provincia"))
    return c


def seleccionar(disposiciones: list[dict]) -> list[dict]:
    out = []
    for x in disposiciones:
        if not es_empleo_publico(x):
            continue
        amb = ambito(x)
        out.append({**x, "ambito": amb, **clasificar(x["titulo"], x.get("subseccion")),
                    "convocante": convocante(x["organismo"] or "") if amb == "local" else None})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "autonomicos" / FUENTE


def ruta_informe(raiz: Path, anio: int, numero: int) -> Path:
    return _base(raiz) / "boletines" / str(anio) / f"{numero:03d}.json"


def _ruta_datos(raiz: Path, carpeta: str, fecha: str, numero: int) -> Path:
    return _base(raiz) / carpeta / fecha[:4] / fecha[5:7] / f"{fecha[8:10]}-{numero:03d}.jsonl"


def procesar_boletin(anio: int, numero: int, fecha: str, raiz: Path, archivo: Archivo) -> dict:
    url = url_boletin(anio, numero)
    r = obtener(url, accept="text/html")
    informe = {"anio": anio, "numero": numero, "fecha": fecha, "status": r.status, "alertas": []}
    if r.status == 404:
        informe["resultado"] = "sin_boletin"
        informe["alertas"].append(f"BOC {anio}/{numero}: figura en el índice anual pero da 404")
        return informe
    if r.status != 200:
        informe["resultado"] = "error_http"
        informe["alertas"].append(f"BOC {anio}/{numero}: HTTP {r.status}")
        return informe
    html = r.contenido.decode("utf-8", errors="replace")
    n_cab, f_cab = cabecera(html)
    if n_cab != numero or (f_cab and f_cab != fecha):
        informe["resultado"] = "error_formato"
        informe["alertas"].append(f"BOC {anio}/{numero}: la cabecera dice número {n_cab} y fecha {f_cab}")
        return informe
    captura = archivo.guardar(FUENTE, date.fromisoformat(fecha), r.contenido, url, "html", r.status, r.cabeceras)
    filas = [f | {"captura_sha256": captura["sha256"]} for f in parsear_boletin(html, anio, numero, fecha)]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta_datos(raiz, "disposiciones", fecha, numero), filas)
    escribir_jsonl(_ruta_datos(raiz, "oposiciones", fecha, numero), empleo)
    informe.update({"resultado": "ok", "sha256": captura["sha256"], "disposiciones": len(filas),
                    "empleo_publico": len(empleo)})
    if not filas:
        informe["alertas"].append(f"BOC {anio}/{numero}: boletín sin disposiciones (posible cambio de formato)")
    return informe


def texto_disposicion(contenido: bytes) -> dict:
    html = contenido.decode("utf-8", errors="replace")
    i = html.find('class="article_title"')
    if i < 0:
        raise ValueError("sin article_title: posible cambio de formato")
    inicio = html.find("</h3>", i)
    fin = html.find('<div id="pie"', inicio)
    if inicio < 0:
        raise ValueError("sin título de la disposición: posible cambio de formato")
    titulo = re.search(r"<h3[^>]*>\s*<b>[^<]*</b>(.*?)<p", html[i:inicio], re.DOTALL)
    limpio = limpiar_html(html[inicio:fin if fin > 0 else None])
    return {"titulo": texto_de(titulo.group(1)) if titulo else None,
            "seccion": texto_de(re.search(r'class="article_title">(.*?)</h5>', html, re.DOTALL).group(1)), **limpio}


def ruta_texto(raiz: Path, x: dict) -> Path:
    return _base(raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"


def textos_pendientes(raiz: Path) -> list[dict]:
    lista = []
    for f in sorted((_base(raiz) / "oposiciones").glob("*/*/*.jsonl"), reverse=True):
        lista += [x for x in leer_jsonl(f) if x.get("url_html") and not ruta_texto(raiz, x).exists()]
    return sorted(lista, key=lambda x: 0 if x.get("alcance") in (None, "acceso") else 1)


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=date.fromisoformat, default=date(hoy.year, 1, 1))
    p.add_argument("--hasta", type=date.fromisoformat, default=hoy)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--saltar-existentes", action="store_true",
                   help="(por defecto ya se saltan los boletines con informe correcto)")
    p.add_argument("--textos", action="store_true")
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=0.7)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True)

    if a.textos:
        pend = textos_pendientes(a.salida)
        hechos, errores = descargar_textos(pend, lambda x: ruta_texto(a.salida, x), lambda x: x["url_html"],
                                           texto_disposicion, archivo, FUENTE, a.max_minutos, a.pausa,
                                           accept="text/html", ext="html")
        print(f"BOC textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        return 0

    inicio, informes = time.monotonic(), []
    for anio in range(a.desde.year, a.hasta.year + 1):
        try:
            r = obtener(url_anio(anio), accept="text/html")
        except ConnectionError as e:
            informes.append({"anio": anio, "resultado": "fuente_inaccesible", "alertas": [str(e)]})
            continue
        if r.status != 200:
            informes.append({"anio": anio, "resultado": "error_http", "alertas": [f"BOC índice {anio}: HTTP {r.status}"]})
            continue
        lista = boletines_del_anio(r.contenido.decode("utf-8", errors="replace"))
        archivo.guardar(FUENTE + "-indice", date(anio, 1, 1), r.contenido, url_anio(anio), "html", r.status, r.cabeceras)
        escribir_json(_base(a.salida) / "calendario" / f"{anio}.json", {"anio": anio, "boletines": lista})
        if not lista:
            informes.append({"anio": anio, "resultado": "error_formato",
                             "alertas": [f"BOC índice {anio}: sin boletines (posible cambio de formato)"]})
            continue
        time.sleep(a.pausa)
        for numero, fecha in lista:
            if not (a.desde.isoformat() <= fecha <= a.hasta.isoformat()):
                continue
            ruta = ruta_informe(a.salida, anio, numero)
            if ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") == "ok":
                continue
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                return _final(informes)
            try:
                inf = procesar_boletin(anio, numero, fecha, a.salida, archivo)
            except ConnectionError as e:
                inf = {"anio": anio, "numero": numero, "fecha": fecha, "resultado": "fuente_inaccesible",
                       "alertas": [str(e)]}
            escribir_json(ruta, inf)
            informes.append(inf)
            print(f"BOC {anio}/{numero} {fecha}: {inf.get('resultado')} {inf.get('disposiciones', '')} disposiciones, "
                  f"{inf.get('empleo_publico', '')} de empleo público")
            time.sleep(a.pausa)
    return _final(informes)


def _final(informes: list[dict]) -> int:
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Boletines procesados: {len(informes)}. Alertas: {len(alertas)}")
    for x in alertas[:30]:
        print(" -", x)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
