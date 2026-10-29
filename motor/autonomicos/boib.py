"""Conector del Butlletí Oficial de les Illes Balears (BOIB) por sus páginas por boletín y sección.

Formato verificado el 29/10/2026 desde GitHub (también para 2022):
  - Calendario anual: https://www.caib.es/eboibfront/es/AAAA  -> por mes (<h3>Enero</h3>...) enlaces
      <a class="ordinario|extraordinario" href="/eboibfront/es/AAAA/ID/" title="BOIB ordinario del dia D">.
      ID es un número interno correlativo (12352 = BOIB núm. 138/2026).
  - Sección II de un boletín: /eboibfront/es/AAAA/ID/seccion-ii-autoridades-y-personal/473 (el 473 es fijo).
      <h3>Subsección primera. Nombramientos...</h3> / <h3>Subsección segunda. Oposiciones y concursos</h3>,
      <h3 class="organisme">GRUPO<strong>ORGANISMO</strong></h3>, y por disposición <p>título</p>,
      «Número de registro N - Páginas», enlaces a PDF, HTML (…/AAAA/ID/ENVIO/slug) y XML (…/xml).
  - Texto: versión HTML, div#contenidoEdicto con párrafos y tablas (la XML aplana las tablas: no sirve para
    retirar las listas de personas).
  - Empleo público: Subsección de oposiciones y concursos (Govern, consells insulars, ayuntamientos y
    universidad); de nombramientos, solo los resultados de procesos.

Uso:
  python -m motor.autonomicos.boib --salida ruta/                                  # año en curso, lo que falte
  python -m motor.autonomicos.boib --desde-anio 2022 --hasta-anio 2025 --max-minutos 20 --salida ruta/
  python -m motor.autonomicos.boib --textos --max-minutos 20 --salida ruta/
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

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (clasificar, convocante_de_organismo, descargar_textos, es_empleo_por_titulo,
                                     es_resultado, escribir_json, escribir_jsonl, leer_jsonl)
from motor.boe.clasificar import normalizar
from motor.extraccion.texto_es import MESES
from motor.http import obtener
from motor.limpieza import limpiar_html, texto_de

FUENTE = "boib"
MADRID = ZoneInfo("Europe/Madrid")
BASE = "https://www.caib.es"
SECCION_II = "seccion-ii-autoridades-y-personal/473"

RE_MES = re.compile(r"<h3>\s*([A-Za-záéíóú]+)\s*</h3>")
RE_ENLACE = re.compile(r'<a class="(?P<tipo>ordinario|extraordinario)" href="/eboibfront/es/(?P<anio>\d{4})/(?P<id>\d+)/"'
                       r'\s+title="BOIB \w+ del dia (?P<dia>\d{1,2})"')
RE_NUMERO = re.compile(r"BOIB N[úu]m\.\s*(\d+)\s*-\s*(\d{1,2})\s*/\s*([A-Za-záéíóú]+)\s*/\s*(\d{4})")
RE_TOKEN = re.compile(
    r'<h3>(?P<sub>Subsecci[oó]n[^<]*)</h3>'
    r'|<h3 class="organisme">(?P<org>.*?)</h3>'
    r'|<ul class="resolucions">(?P<item>.*?)</ul>\s*</div>', re.DOTALL)
RE_DISPOSICION = re.compile(r"<li>\s*<p>(?P<titulo>.*?)</p>\s*<p class=\"registre\">(?P<registro>.*?)</p>(?P<resto>.*?)"
                            r"(?=<li>\s*<p>|$)", re.DOTALL)
RE_HTML = re.compile(r'href="(https://www\.caib\.es/eboibfront/es/\d{4}/\d+/(?P<envio>\d+)/[^"]+)" class="html"')
RE_PDF = re.compile(r"href='(/eboibfront/pdf/[^']+)'")
RE_REGISTRO = re.compile(r"N[úu]mero de registro\s*(\d+)")
RE_CONTENIDO = re.compile(r'id="contenidoEdicto"[^>]*>(.*?)(?:<div class="imc--|<!-- xarxes|</body>)', re.DOTALL)


def url_anio(anio: int) -> str:
    return f"{BASE}/eboibfront/es/{anio}"


def url_seccion(anio: int, ident: str) -> str:
    return f"{BASE}/eboibfront/es/{anio}/{ident}/{SECCION_II}"


def calendario(html: str, anio: int) -> list[dict]:
    """Boletines del año en orden: [{id, fecha, tipo}]."""
    salida, mes = [], None
    posiciones = [(m.start(), "mes", m) for m in RE_MES.finditer(html)] + \
                 [(m.start(), "boib", m) for m in RE_ENLACE.finditer(html)]
    for _, clase, m in sorted(posiciones, key=lambda x: x[0]):
        if clase == "mes":
            mes = MESES.get(normalizar(m.group(1)), mes)
        elif mes and int(m.group("anio")) == anio:
            salida.append({"id": m.group("id"), "fecha": date(anio, mes, int(m.group("dia"))).isoformat(),
                           "tipo": m.group("tipo")})
    return salida


def parsear_seccion(html: str, boletin: dict) -> dict:
    m = RE_NUMERO.search(html)
    numero = int(m.group(1)) if m else None
    subseccion = grupo = organismo = None
    filas = []
    for t in RE_TOKEN.finditer(html):
        if t.group("sub") is not None:
            subseccion = texto_de(t.group("sub"))
        elif t.group("org") is not None:
            partes = re.split(r"<strong>", t.group("org"), maxsplit=1)
            grupo = texto_de(partes[0])
            organismo = texto_de(partes[1]) if len(partes) > 1 else grupo
        elif t.group("item") is not None:
            for d in RE_DISPOSICION.finditer(t.group("item")):
                h = RE_HTML.search(d.group("resto"))
                pdf = RE_PDF.search(d.group("resto"))
                reg = RE_REGISTRO.search(d.group("registro"))
                envio = h.group("envio") if h else (reg.group(1) if reg else None)
                if not envio:
                    continue
                filas.append({
                    "id": f"BOIB-{boletin['fecha'][:4]}-{envio}", "envio": envio,
                    "registro": reg.group(1) if reg else None, "fecha": boletin["fecha"], "boletin": numero,
                    "boletin_id": boletin["id"], "tipo_boletin": boletin["tipo"],
                    "seccion": "II. Autoridades y personal", "subseccion": subseccion, "grupo": grupo,
                    "organismo": organismo, "titulo": texto_de(d.group("titulo")),
                    "url_html": h.group(1) if h else None, "url_pdf": BASE + pdf.group(1) if pdf else None,
                    "fuente": "BOIB",
                })
    return {"numero": numero, "disposiciones": filas}


def ambito(x: dict) -> str:
    g, o = normalizar(x.get("grupo") or ""), normalizar(x.get("organismo") or "")
    insular = ("consejo insular", "consell insular")
    if "administracion local" in g or g.startswith(insular) or o.startswith(
            ("ayuntamiento", "ajuntament", "mancomunitat", "mancomunidad", "consorci") + insular):
        return "local"
    if o.startswith(("universidad", "universitat")) or "universidad" in g or "universitat" in g:
        return "universidad"
    return "autonomico"


def es_empleo_publico(x: dict) -> bool:
    sub = normalizar(x.get("subseccion") or "")
    t = x.get("titulo") or ""
    if "oposiciones" in sub or "concursos" in sub:
        return True
    if "nombramientos" in sub:
        return es_resultado(t)
    return es_empleo_por_titulo(t)


def seleccionar(disposiciones: list[dict]) -> list[dict]:
    out = []
    for x in disposiciones:
        if not es_empleo_publico(x):
            continue
        amb = ambito(x)
        out.append({**x, "ambito": amb, **clasificar(x["titulo"], x.get("subseccion")),
                    "convocante": convocante_de_organismo(x["organismo"]) if amb == "local" else None})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "autonomicos" / FUENTE


def _ruta(raiz: Path, carpeta: str, boletin: dict, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / boletin["fecha"][:4] / f"{boletin['id']}.{ext}"


def procesar_boletin(boletin: dict, raiz: Path, archivo: Archivo) -> dict:
    anio = int(boletin["fecha"][:4])
    url = url_seccion(anio, boletin["id"])
    r = obtener(url, accept="text/html")
    informe = {**boletin, "status": r.status, "alertas": []}
    if r.status == 404:
        informe["resultado"] = "sin_seccion_ii"
        return informe
    if r.status != 200:
        informe["resultado"] = "error_http"
        informe["alertas"].append(f"BOIB {boletin['fecha']} ({boletin['id']}): HTTP {r.status}")
        return informe
    html = r.contenido.decode("utf-8", errors="replace")
    s = parsear_seccion(html, boletin)
    captura = archivo.guardar(FUENTE, date.fromisoformat(boletin["fecha"]), r.contenido, url, "html", r.status,
                              r.cabeceras)
    filas = [x | {"captura_sha256": captura["sha256"]} for x in s["disposiciones"]]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", boletin), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", boletin), empleo)
    informe.update({"resultado": "ok", "numero": s["numero"], "sha256": captura["sha256"],
                    "disposiciones": len(filas), "empleo_publico": len(empleo)})
    if "Sección II" in html and not filas:
        informe["alertas"].append(f"BOIB {boletin['fecha']} ({boletin['id']}): sección II sin disposiciones leídas")
    return informe


def texto_disposicion(contenido: bytes) -> dict:
    html = contenido.decode("utf-8", errors="replace")
    m = RE_CONTENIDO.search(html)
    if not m:
        raise ValueError("sin contenidoEdicto: posible cambio de formato")
    return {"titulo": None, **limpiar_html(m.group(1))}


def ruta_texto(raiz: Path, x: dict) -> Path:
    return _base(raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"


def textos_pendientes(raiz: Path) -> list[dict]:
    lista = []
    for f in sorted((_base(raiz) / "oposiciones").glob("*/*.jsonl"), reverse=True):
        lista += [x for x in leer_jsonl(f) if x.get("url_html") and not ruta_texto(raiz, x).exists()]
    lista.sort(key=lambda x: x["fecha"], reverse=True)
    return sorted(lista, key=lambda x: 0 if x.get("alcance") in (None, "acceso") else 1)


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde-anio", type=int, default=hoy.year)
    p.add_argument("--hasta-anio", type=int, default=hoy.year)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--textos", action="store_true")
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=0.7)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())

    if a.textos:
        pend = textos_pendientes(a.salida)
        hechos, errores = descargar_textos(pend, lambda x: ruta_texto(a.salida, x), lambda x: x["url_html"],
                                           texto_disposicion, archivo, FUENTE, a.max_minutos, a.pausa,
                                           accept="text/html", ext="html")
        print(f"BOIB textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        return 0

    inicio, informes = time.monotonic(), []
    for anio in range(a.desde_anio, a.hasta_anio + 1):
        try:
            r = obtener(url_anio(anio), accept="text/html")
        except ConnectionError as e:
            informes.append({"anio": anio, "resultado": "fuente_inaccesible", "alertas": [str(e)]})
            continue
        if r.status != 200:
            informes.append({"anio": anio, "resultado": "error_http", "alertas": [f"BOIB {anio}: HTTP {r.status}"]})
            continue
        boletines = calendario(r.contenido.decode("utf-8", errors="replace"), anio)
        escribir_json(_base(a.salida) / "calendario" / f"{anio}.json", {"anio": anio, "boletines": boletines})
        if not boletines:
            informes.append({"anio": anio, "resultado": "error_formato",
                             "alertas": [f"BOIB {anio}: calendario sin boletines (posible cambio de formato)"]})
            continue
        for b in boletines:
            ruta = _ruta(a.salida, "boletines", b, "json")
            if ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") in {"ok", "sin_seccion_ii"}:
                continue
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                return 0
            try:
                inf = procesar_boletin(b, a.salida, archivo)
            except ConnectionError as e:
                inf = {**b, "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            escribir_json(ruta, inf)
            informes.append(inf)
            print(f"BOIB {b['fecha']} ({b['id']}, {b['tipo']}): {inf['resultado']} {inf.get('empleo_publico', '')}")
            time.sleep(a.pausa)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Boletines procesados: {len(informes)}. Alertas: {len(alertas)}")
    for x in alertas[:30]:
        print(" -", x)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
