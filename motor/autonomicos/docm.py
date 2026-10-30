"""Conector del Diario Oficial de Castilla-La Mancha (DOCM) por su sumario diario en HTML (con sesión).

Formato verificado el 29/10/2026 desde GitHub (también para 2022):
  - El portal exige su cookie de sesión: primero https://docm.jccm.es/portaldocm/sumario.do y después
    https://docm.jccm.es/docm/cambiarBoletin.do?fecha=AAAAMMDD (sin la cookie responde 500).
  - Sumario: cabecera (anyoDiario, fechaDiario «Lunes, 3 de enero de 2022», numeroDiario «Núm. 1»); secciones
    <h3 class = "cabeceraCategoria">II.- AUTORIDADES Y PERSONAL</h3>, subsecciones <li>OPOSICIONES Y CONCURSOS,
    organismo <h4 class = "tituloOrganismo">, y cada disposición <p class = "sumario"> con «Materia. Rango de fecha»,
    el resto del título, «[NID 2026/7798]», el PDF y (desde 2023 aprox.) la versión HTML verArchivoHtml.do.
  - Texto: versión HTML (no oficial; el PDF firmado es el oficial), div#contenido_html.
  - Empleo público: II, «Oposiciones y concursos» (todo) y «Ceses y nombramientos» (solo resultados de
    procesos); en Anuncios, ayuntamientos y diputaciones por el título.

Uso:
  python -m motor.autonomicos.docm --salida ruta/                                  # ayer y hoy
  python -m motor.autonomicos.docm --desde 2022-01-01 --saltar-existentes --max-minutos 20 --salida ruta/
  python -m motor.autonomicos.docm --textos --max-minutos 20 --salida ruta/
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (Freno, clasificar, convocante_de_organismo, descargar_textos, es_empleo_por_titulo,
                                     es_resultado, escribir_json, escribir_jsonl, leer_jsonl)
from motor.boe.clasificar import normalizar
from motor.extraccion.texto_es import MESES
from motor.http import USER_AGENT, obtener
from motor.limpieza import limpiar_html, texto_de

FUENTE = "docm"
MADRID = ZoneInfo("Europe/Madrid")
BASE = "https://docm.jccm.es"
PORTADA = BASE + "/docm/"  # el diario del día; los demás por cambiarBoletin.do (--historico)
CAPITALES = ("Albacete", "Ciudad Real", "Cuenca", "Guadalajara", "Toledo")

RE_FECHA = re.compile(r'class\s*=\s*"fechaDiario"[^>]*>\s*[^,<]*,\s*(\d{1,2}) de ([a-záéíóú]+) de (\d{4})', re.IGNORECASE)
RE_NUMERO = re.compile(r'class\s*=\s*"numeroDiario"[^>]*>\s*N(?:&uacute;|ú|u)m\.\s*(\d+)', re.IGNORECASE)
RE_TOKEN = re.compile(
    r'<h3 class\s*=\s*"cabeceraCategoria"[^>]*>(?P<sec>.*?)</h3>'
    r'|<li>\s*(?P<sub>[A-ZÁÉÍÓÚÑ ,]{6,80})\s*<'
    r'|<h4 class\s*=\s*"tituloOrganismo"[^>]*>(?P<org>.*?)</h4>'
    r'|<p class\s*=\s*"sumario"[^>]*>(?P<item>.*?)</p>(?P<resto>.*?)(?=<p class\s*=\s*"sumario"|<h4 class|<h3 class|<li>|</ol>)',
    re.DOTALL)
RE_NID = re.compile(r"\[NID\s*(\d{4})/(\d+)\]")
RE_PDF = re.compile(r'descargarArchivo\.do\?ruta=([^"&]+\.pdf)')
RE_HTML = re.compile(r"verArchivoHtml\.do\?ruta=([^'&]+\.html)")
RE_CONTENIDO = re.compile(r'<div id="contenido_html">(.*?)(?:<div id="footer_nota"|</body>)', re.DOTALL)

SESION: requests.Session | None = None


def sesion(nueva: bool = False) -> requests.Session:
    """Sesión con la cookie del portal (se abre una vez por ejecución; con nueva=True se vuelve a abrir, porque
    el portal caduca la sesión y entonces responde 400 a todo)."""
    global SESION
    if SESION is None or nueva:
        SESION = requests.Session()
        SESION.headers["User-Agent"] = USER_AGENT
        obtener(PORTADA, accept="text/html", sesion=SESION)
    return SESION


def url_dia(d: date) -> str:
    return f"{BASE}/docm/cambiarBoletin.do?fecha={d:%Y%m%d}"


def parsear_sumario(html: str) -> dict:
    f = RE_FECHA.search(html)
    fecha = None
    if f and MESES.get(normalizar(f.group(2))):
        fecha = date(int(f.group(3)), MESES[normalizar(f.group(2))], int(f.group(1))).isoformat()
    n = RE_NUMERO.search(html)
    seccion = subseccion = organismo = None
    filas = []
    for t in RE_TOKEN.finditer(html):
        if t.group("sec") is not None:
            seccion, subseccion, organismo = texto_de(t.group("sec")), None, None
        elif t.group("sub") is not None:
            subseccion, organismo = " ".join(t.group("sub").split()), None
        elif t.group("org") is not None:
            organismo = texto_de(t.group("org"))
        elif t.group("item") is not None:
            item, resto = t.group("item"), t.group("resto") or ""
            nid = RE_NID.search(item)
            pdf = RE_PDF.search(item + resto)
            if not nid:
                continue
            h = RE_HTML.search(resto)
            titulo = re.sub(r"\s+([,.;])", r"\1", RE_NID.sub("", texto_de(item))).strip()
            materia = texto_de(re.search(r">(.*?)</a>", item, re.DOTALL).group(1)) if "</a>" in item else None
            filas.append({
                "id": f"DOCM-{nid.group(1)}-{nid.group(2)}", "nid": f"{nid.group(1)}/{nid.group(2)}",
                "seccion": seccion, "subseccion": subseccion, "organismo": organismo,
                "materia": materia.split(". ")[0] if materia else None, "titulo": titulo,
                "url_pdf": f"{BASE}/portaldocm/descargarArchivo.do?ruta={pdf.group(1)}&tipo=rutaDocm" if pdf else None,
                "url_html": f"{BASE}/portaldocm/verArchivoHtml.do?ruta={h.group(1)}&tipo=rutaDocm" if h else None,
                "fuente": "DOCM",
            })
    return {"fecha": fecha, "numero": int(n.group(1)) if n else None, "disposiciones": filas}


def ambito(x: dict) -> str:
    o = normalizar(x.get("organismo") or "")
    if o.startswith(("ayuntamiento", "diputacion", "mancomunidad", "consorcio", "entidad local")):
        return "local"
    if o.startswith("universidad"):
        return "universidad"
    return "autonomico"


def es_empleo_publico(x: dict) -> bool:
    s, sub, t = normalizar(x.get("seccion") or ""), normalizar(x.get("subseccion") or ""), x.get("titulo") or ""
    if "autoridades y personal" in s:
        if "oposiciones" in sub:
            return True
        return es_resultado(t)
    if "anuncios" in s:
        return ambito(x) in ("local", "universidad") and es_empleo_por_titulo(t)
    return False


def seleccionar(disposiciones: list[dict]) -> list[dict]:
    out = []
    for x in disposiciones:
        if not es_empleo_publico(x):
            continue
        amb = ambito(x)
        out.append({**x, "ambito": amb, **clasificar(x["titulo"], x.get("subseccion")),
                    "convocante": convocante_de_organismo(x["organismo"], CAPITALES) if amb == "local" else None})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "autonomicos" / FUENTE


def _ruta(raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


def procesar_dia(d: date, raiz: Path, archivo: Archivo) -> dict:
    url = url_dia(d)
    r = obtener(url, accept="text/html", sesion=sesion())
    if r.status == 400:  # sesión caducada: se abre otra y se repite una vez
        r = obtener(url, accept="text/html", sesion=sesion(nueva=True))
    informe = {"fecha": d.isoformat(), "status": r.status, "alertas": []}
    if r.status != 200:
        informe["resultado"] = "error_http"
        informe["alertas"].append(f"DOCM {d}: HTTP {r.status}")
        return informe
    s = parsear_sumario(r.contenido.decode("utf-8", errors="replace"))
    if s["fecha"] != d.isoformat():
        # Sin diario ese día, el portal muestra otro (el último publicado) o una página sin sumario
        if s["fecha"]:
            informe["resultado"] = "sin_boletin"
            return informe
        # Página sin fecha: se guarda el original para poder estudiarla y no se da por buena
        captura = archivo.guardar(FUENTE, d, r.contenido, url, "html", r.status, r.cabeceras)
        informe["sha256"] = captura["sha256"]
        if d.weekday() >= 5 and not s["disposiciones"]:
            informe.update({"resultado": "sin_boletin", "nota": "fin de semana: página sin sumario"})
        else:
            informe["resultado"] = "error_formato"
            informe["alertas"].append(f"DOCM {d}: sumario sin fecha (posible cambio de formato)")
        return informe
    captura = archivo.guardar(FUENTE, d, r.contenido, url, "html", r.status, r.cabeceras)
    filas = [x | {"fecha": d.isoformat(), "boletin": s["numero"], "captura_sha256": captura["sha256"]}
             for x in s["disposiciones"]]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    informe.update({"resultado": "ok", "numero": s["numero"], "sha256": captura["sha256"],
                    "disposiciones": len(filas), "empleo_publico": len(empleo)})
    if not filas:
        informe["alertas"].append(f"DOCM {d}: sumario sin disposiciones (posible cambio de formato)")
    return informe


def texto_disposicion(contenido: bytes) -> dict:
    html = contenido.decode("utf-8", errors="replace")
    m = RE_CONTENIDO.search(html)
    if not m:
        raise ValueError("sin contenido_html: posible cambio de formato")
    cuerpo = re.sub(r'<div class="cabecera">.*?</div>\s*</div>', "", m.group(1), count=1, flags=re.DOTALL)
    return {"titulo": None, **limpiar_html(html_mod.unescape(cuerpo) if "&lt;" not in cuerpo else cuerpo)}


def ruta_texto(raiz: Path, x: dict) -> Path:
    return _base(raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"


def textos_pendientes(raiz: Path) -> list[dict]:
    lista = []
    for f in sorted((_base(raiz) / "oposiciones").glob("*/*/*.jsonl"), reverse=True):
        lista += [x for x in leer_jsonl(f) if x.get("url_html") and not ruta_texto(raiz, x).exists()]
    return sorted(lista, key=lambda x: 0 if x.get("alcance") in (None, "acceso") else 1)


def procesar_portada(raiz: Path, archivo: Archivo) -> dict:
    """El diario del día desde la portada /docm/ (mismo sumario que sumario.do, que robots.txt prohíbe)."""
    r = obtener(PORTADA, accept="text/html", sesion=sesion())
    if r.status == 400:
        r = obtener(PORTADA, accept="text/html", sesion=sesion(nueva=True))
    if r.status != 200:
        return {"fecha": None, "status": r.status, "resultado": "error_http", "alertas": [f"DOCM portada: HTTP {r.status}"]}
    s = parsear_sumario(r.contenido.decode("utf-8", errors="replace"))
    if not s["fecha"]:
        return {"fecha": None, "status": 200, "resultado": "error_formato",
                "alertas": ["DOCM portada sin fecha de diario (posible cambio de formato)"]}
    d = date.fromisoformat(s["fecha"])
    captura = archivo.guardar(FUENTE, d, r.contenido, PORTADA, "html", r.status, r.cabeceras)
    filas = [x | {"fecha": d.isoformat(), "boletin": s["numero"], "captura_sha256": captura["sha256"]}
             for x in s["disposiciones"]]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    inf = {"fecha": d.isoformat(), "status": 200, "resultado": "ok", "numero": s["numero"], "origen": "portada",
           "sha256": captura["sha256"], "disposiciones": len(filas), "empleo_publico": len(empleo), "alertas": []}
    if not filas:
        inf["alertas"].append(f"DOCM {d}: portada sin disposiciones (posible cambio de formato)")
    escribir_json(_ruta(raiz, "dias", d, "json"), inf)
    return inf


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=date.fromisoformat, default=hoy - timedelta(days=1))
    p.add_argument("--hasta", type=date.fromisoformat, default=hoy)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--saltar-existentes", action="store_true")
    p.add_argument("--textos", action="store_true")
    p.add_argument("--historico", action="store_true",
                   help="por días con cambiarBoletin.do (cerrado en robots.txt; se lee como boletín oficial)")
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=0.8)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())

    if a.textos:
        pend = textos_pendientes(a.salida)
        hechos, errores = descargar_textos(pend, lambda x: ruta_texto(a.salida, x), lambda x: x["url_html"],
                                           texto_disposicion, archivo, FUENTE, a.max_minutos, a.pausa,
                                           accept="text/html", ext="html", sesion=sesion(), renovar_sesion=lambda: sesion(nueva=True))
        print(f"DOCM textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        return 0

    if not a.historico:
        # El diario del día, por la portada
        try:
            inf = procesar_portada(a.salida, archivo)
        except ConnectionError as e:
            inf = {"fecha": None, "resultado": "fuente_inaccesible", "alertas": [str(e)]}
        print(f"DOCM {inf.get('fecha')}: {inf.get('resultado')} {inf.get('disposiciones', '')} disposiciones, "
              f"{inf.get('empleo_publico', '')} de empleo público {'; '.join(inf.get('alertas', []))}")
        return 1 if inf.get("resultado") in {"error_formato", "fuente_inaccesible", "error_http"} else 0

    inicio, informes, d = time.monotonic(), [], a.desde
    freno = Freno()
    while d <= a.hasta:
        if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
            print("Tiempo agotado; se continúa en la siguiente ejecución")
            break
        ruta = _ruta(a.salida, "dias", d, "json")
        if d.weekday() >= 5 or (a.saltar_existentes and ruta.exists() and
                                json.loads(ruta.read_text(encoding="utf-8")).get("resultado") in {"ok", "sin_boletin"}):
            d += timedelta(days=1)
            continue
        try:
            inf = procesar_dia(d, a.salida, archivo)
        except ConnectionError as e:
            inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
        if not (inf.get("resultado") == "sin_boletin" and d >= hoy):
            escribir_json(ruta, inf)
        informes.append(inf)
        if freno.anotar(inf):
            break
        print(f"DOCM {d}: {inf.get('resultado')} {inf.get('disposiciones', '')} disposiciones, "
              f"{inf.get('empleo_publico', '')} de empleo público")
        d += timedelta(days=1)
        time.sleep(a.pausa)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    for x in alertas[:30]:
        print(" -", x)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
