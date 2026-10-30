"""Conector del Boletín Oficial del Principado de Asturias (BOPA).

Formato verificado el 30/10/2026 desde el servidor de España (desde GitHub no responde):
  - Sumario de un día: https://miprincipado.asturias.es/bopa-sumario?p_p_id=pa_sede_bopa_web_portlet_SedeBopaSummaryWeb
    &p_p_lifecycle=0&p_p_state=normal&p_p_mode=view&p_r_p_summaryDate=DD%2FMM%2FAAAA&p_r_p_summaryIsSearch=false
    Cabecera «Boletín Nº 210 del jueves 29 de octubre de 2026». Un día sin boletín devuelve el último publicado:
    se reconoce por la fecha.
  - En div#bopa-boletin: h4 (sección «I. Principado de Asturias», «IV. Administración Local»…), h5 (apartado
    «AUTORIDADES Y PERSONAL», «OTRAS DISPOSICIONES», «AYUNTAMIENTOS»…), h6 (organismo: «CONSEJERÍA DE SALUD»,
    «DE AVILÉS»), p.subAuthor (organismo dependiente) y dt con el título y «[Cód. 2026-08847]».
  - Texto de cada disposición en HTML (div#bopa-articulo) en /bopa/disposiciones?…p_r_p_dispositionReference=CÓDIGO.
    robots.txt cierra en general los textos y los PDF; se leen como boletín oficial (motor/http.py), pero nunca los
    más de 600 documentos que cierra por su código para proteger datos de personas.
  - Empleo público: el título decide (filtro estricto), en «Autoridades y personal» también los nombramientos de
    procesos selectivos. Solo secciones I (Principado) y IV (Administración local).

Uso:
  python -m motor.autonomicos.bopa --salida ruta/                                  # ayer y hoy
  python -m motor.autonomicos.bopa --desde 2022-01-01 --max-minutos 20 --salida ruta/
  python -m motor.autonomicos.bopa --textos --max-minutos 20 --salida ruta/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (Freno, clasificar, convocante_de_organismo, descargar_textos, es_empleo_estricto,
                                     es_resultado, escribir_json, escribir_jsonl, leer_jsonl)
from motor.boe.clasificar import normalizar
from motor.extraccion.texto_es import fecha_texto
from motor.http import obtener
from motor.limpieza import limpiar_html, texto_de

FUENTE = "bopa"
SIGLAS = "BOPA"
MADRID = ZoneInfo("Europe/Madrid")
BASE = "https://miprincipado.asturias.es"
NOMBRES = ("Boletín Oficial del Principado de Asturias",)

RE_CABECERA = re.compile(r"<h1[^>]*>\s*Bolet[ií]n\s+N[ºo°]\s*(?P<n>\d+)(?P<extra>\s+extraordinario)?\s+del\s+\w+\s+"
                         r"(?P<d>\d{1,2})\s+de\s+(?P<m>\w+)\s+de\s+(?P<a>\d{4})", re.IGNORECASE)
RE_TOKEN = re.compile(r"<h4>(?P<h4>.*?)</h4>|<h5>(?P<h5>.*?)</h5>|<h6[^>]*>(?P<h6>.*?)</h6>"
                      r'|<p[^>]*class="subAuthor">(?P<sub>.*?)</p>|<dt>(?P<dt>.*?)</dt>', re.DOTALL)
RE_CODIGO = re.compile(r"\[\s*C[óo]d\.\s*(\d{4}-\d{5})\s*\]")
# Apartados de la sección IV en plural -> tipo de entidad («AYUNTAMIENTOS» + «DE AVILÉS»)
SINGULAR = {"ayuntamientos": "AYUNTAMIENTO", "mancomunidades": "MANCOMUNIDAD", "consorcios": "CONSORCIO",
            "parroquias rurales": "PARROQUIA RURAL", "entidades locales menores": "ENTIDAD LOCAL MENOR"}


def url_dia(d: date) -> str:
    return (f"{BASE}/bopa-sumario?p_p_id=pa_sede_bopa_web_portlet_SedeBopaSummaryWeb&p_p_lifecycle=0"
            f"&p_p_state=normal&p_p_mode=view&p_r_p_summaryDate={d:%d}%2F{d:%m}%2F{d:%Y}&p_r_p_summaryIsSearch=false")


def url_texto(codigo: str, d: date) -> str:
    return (f"{BASE}/bopa/disposiciones?p_p_id=pa_sede_bopa_web_portlet_SedeBopaDispositionWeb&p_p_lifecycle=0"
            f"&_pa_sede_bopa_web_portlet_SedeBopaDispositionWeb_mvcRenderCommandName=%2Fdisposition%2Fdetail"
            f"&p_r_p_dispositionText={quote(codigo)}&p_r_p_dispositionReference={quote(codigo)}"
            f"&p_r_p_dispositionDate={d:%d}%2F{d:%m}%2F{d:%Y}")


def cabecera(html: str) -> tuple[int | None, str | None, bool]:
    m = RE_CABECERA.search(html)
    if not m:
        return None, None, False
    return int(m.group("n")), fecha_texto(m.group("d"), m.group("m"), m.group("a")), bool(m.group("extra"))


def parsear_sumario(html: str) -> list[dict]:
    i = html.find('id="bopa-boletin"')
    if i < 0:
        return []
    seccion = apartado = organismo = suborganismo = None
    filas = []
    for t in RE_TOKEN.finditer(html, i):
        if t.group("h4") is not None:
            seccion, apartado, organismo, suborganismo = texto_de(t.group("h4")), None, None, None
        elif t.group("h5") is not None:
            apartado, organismo, suborganismo = texto_de(t.group("h5")), None, None
        elif t.group("h6") is not None:
            organismo, suborganismo = texto_de(t.group("h6")), None
        elif t.group("sub") is not None:
            suborganismo = texto_de(t.group("sub"))
        else:
            dt = t.group("dt")
            cod = RE_CODIGO.search(dt)
            if not cod:
                continue
            filas.append({"id": f"BOPA-{cod.group(1)}", "codigo": cod.group(1), "seccion": seccion,
                          "apartado": apartado, "organismo": organismo, "suborganismo": suborganismo,
                          "titulo": texto_de(RE_CODIGO.sub("", dt)), "fuente": SIGLAS})
    return filas


def _num_seccion(x: dict) -> str:
    return (x.get("seccion") or "").split(".")[0].strip().upper()


def es_empleo_publico(x: dict) -> bool:
    if _num_seccion(x) not in {"I", "IV"}:
        return False
    t = x.get("titulo") or ""
    if "autoridades y personal" in normalizar(x.get("apartado") or ""):
        return es_empleo_estricto(t) or es_resultado(t)
    return es_empleo_estricto(t)


def organismo_local(x: dict) -> str | None:
    """«AYUNTAMIENTOS» + «DE AVILÉS» -> «AYUNTAMIENTO DE AVILÉS»."""
    org = x.get("organismo") or ""
    tipo = SINGULAR.get(normalizar(x.get("apartado") or ""))
    if tipo and normalizar(org).startswith(("de ", "del ")):
        return f"{tipo} {org}"
    return org or x.get("apartado")


def ambito(x: dict) -> str:
    if _num_seccion(x) == "IV":
        return "local"
    if normalizar(" ".join(filter(None, (x.get("organismo"), x.get("suborganismo"))))).startswith("universidad"):
        return "universidad"
    return "autonomico"


def convocante(x: dict) -> dict | None:
    c = convocante_de_organismo(organismo_local(x) or "")
    if c:
        c["provincia"] = "Asturias"
    return c


def seleccionar(disposiciones: list[dict]) -> list[dict]:
    out = []
    for x in disposiciones:
        if not es_empleo_publico(x):
            continue
        amb = ambito(x)
        out.append({**x, "ambito": amb, **clasificar(x["titulo"], x.get("apartado")),
                    "convocante": convocante(x) if amb == "local" else None})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "autonomicos" / FUENTE


def _ruta(raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


def procesar_dia(d: date, raiz: Path, archivo: Archivo) -> dict:
    url = url_dia(d)
    r = obtener(url, accept="text/html")
    informe = {"fecha": d.isoformat(), "status": r.status, "alertas": []}
    if r.status != 200:
        informe["resultado"] = "error_http"
        informe["alertas"].append(f"BOPA {d}: HTTP {r.status}")
        return informe
    html = r.contenido.decode("utf-8", errors="replace")
    n, fecha, extra = cabecera(html)
    if not fecha:
        informe["resultado"] = "error_formato"
        informe["alertas"].append(f"BOPA {d}: página sin cabecera de boletín (posible cambio de formato)")
        return informe
    if fecha != d.isoformat():
        informe["resultado"] = "sin_boletin"  # devuelve el último publicado
        return informe
    captura = archivo.guardar(FUENTE, d, r.contenido, url, "html", r.status, r.cabeceras)
    filas = [{**x, "fecha": fecha, "boletin": n, "extraordinario": extra, "url_html": url_texto(x["codigo"], d),
              "url_pdf": f"{BASE}/bopa/{d:%Y}/{d:%m}/{d:%d}/{x['codigo']}.pdf", "captura_sha256": captura["sha256"]}
             for x in parsear_sumario(html)]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    informe.update({"resultado": "ok", "numero": n, "extraordinario": extra, "sha256": captura["sha256"],
                    "disposiciones": len(filas), "empleo_publico": len(empleo)})
    if not filas:
        informe["alertas"].append(f"BOPA {d}: sumario sin disposiciones (posible cambio de formato)")
    return informe


def _fin_div(html: str, i: int) -> int:
    """Final del div que se abre en i (por profundidad de etiquetas)."""
    k, prof = html.find(">", i) + 1, 1
    for m in re.finditer(r"<div\b|</div>", html[k:]):
        prof += 1 if m.group(0) == "<div" else -1
        if prof == 0:
            return k + m.start()
    return len(html)


def texto_disposicion(contenido: bytes) -> dict:
    html = contenido.decode("utf-8", errors="replace")
    i = html.find('id="bopa-articulo"')
    if i < 0:
        raise ValueError("sin bopa-articulo: posible cambio de formato")
    i = html.rfind("<div", 0, i)
    cuerpo = html[i:_fin_div(html, i)]
    titulo = re.search(r'<p class="subtit-azul">(.*?)</p>', cuerpo, re.DOTALL)
    return {"titulo": texto_de(titulo.group(1)) if titulo else None, **limpiar_html(cuerpo)}


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
    p.add_argument("--desde", type=date.fromisoformat, default=hoy - timedelta(days=1))
    p.add_argument("--hasta", type=date.fromisoformat, default=hoy)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--textos", action="store_true")
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())

    if a.textos:
        pend = textos_pendientes(a.salida)
        hechos, errores = descargar_textos(pend, lambda x: ruta_texto(a.salida, x), lambda x: x["url_html"],
                                           texto_disposicion, archivo, FUENTE, a.max_minutos, a.pausa,
                                           accept="text/html", ext="html")
        print(f"BOPA textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        return 0

    inicio, informes, freno = time.monotonic(), [], Freno()
    d = a.hasta
    while d >= a.desde:  # del más reciente al más antiguo; lo hecho no se repite (salvo ayer y hoy)
        ruta = _ruta(a.salida, "dias", d, "json")
        hecho = ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") in {"ok", "sin_boletin"}
        if d.weekday() >= 5 and not hecho:  # el BOPA no sale en fin de semana
            escribir_json(ruta, {"fecha": d.isoformat(), "resultado": "sin_boletin", "nota": "fin de semana",
                                 "alertas": []})
            hecho = True
        if not hecho or (d >= hoy - timedelta(days=1) and d.weekday() < 5):
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                break
            try:
                inf = procesar_dia(d, a.salida, archivo)
            except (ConnectionError, TimeoutError) as e:
                inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            if not (inf.get("resultado") == "sin_boletin" and d >= hoy):
                escribir_json(ruta, inf)
            informes.append(inf)
            if freno.anotar(inf):
                break
            print(f"BOPA {d}: {inf['resultado']} {inf.get('disposiciones', '')} disposiciones, "
                  f"{inf.get('empleo_publico', '')} de empleo público")
            time.sleep(a.pausa)
        d -= timedelta(days=1)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    for x in alertas[:30]:
        print(" -", x)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
