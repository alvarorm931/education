"""Conector del Diario Oficial de Extremadura (DOE) por su sumario diario en HTML.

Formato verificado el 29/10/2026 desde GitHub (también para 2022):
  - Sumario del día: https://doe.juntaex.es/ultimosdoe/mostrardoe.php?fecha=AAAAMMDD&t=o  (t=e, extraordinario)
      Cabecera «Núm.: 209» y la fecha; sin boletín, «D.O.E. No encontrado». ISO-8859-1.
      Sección: <span class="dN">II. AUTORIDADES Y PERSONAL</span>; subsección: <span class="DOE6">OPOSICIONES Y
      CONCURSOS</span>; organismo: <p><span class="DOE2">CONSEJERÍA...</span></p>; disposición: <div class="justificado">
      con materia (DOE2), título (DOE4), PDF y enlace a otrosFormatos/html.php?xml=ID&anio=AAAA&doe=NNNo.
  - Disposición en HTML: https://doe.juntaex.es/otrosFormatos/html.php?xml=ID&anio=AAAA&doe=NNNo
      (metadatos y texto en div.xml > div.Txt); también en XML: /pdfs/doe/AAAA/NNNo/xml/ID.xml
  - Empleo público: II, «Oposiciones y concursos» (todo) y «Nombramientos» (resultados); Anuncios de
    ayuntamientos y diputaciones por el título.
  - En años anteriores (2022) la disposición solo está en PDF (sin html.php): se guarda el registro y el texto
    queda pendiente de extracción desde PDF.
  - Los extraordinarios (t=e) solo se piden en la pasada diaria; en la carga histórica quedan como hueco conocido.

Uso:
  python -m motor.autonomicos.doe --salida ruta/                                   # ayer y hoy (con extraordinarios)
  python -m motor.autonomicos.doe --desde 2022-01-01 --saltar-existentes --max-minutos 20 --salida ruta/
  python -m motor.autonomicos.doe --textos --max-minutos 20 --salida ruta/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (Freno, clasificar, convocante_de_organismo, descargar_textos, es_empleo_por_titulo,
                                     es_resultado, escribir_json, escribir_jsonl, leer_jsonl)
from motor.boe.clasificar import normalizar
from motor.extraccion.texto_es import MESES
from motor.http import obtener
from motor.limpieza import limpiar_html, texto_de

FUENTE = "doe"
MADRID = ZoneInfo("Europe/Madrid")
BASE = "https://doe.juntaex.es"
CAPITALES = ("Badajoz", "Cáceres")

RE_NUMERO = re.compile(r"N[úu]m\.?:\s*(\d+)")
RE_FECHA = re.compile(r"(?:lunes|martes|mi[ée]rcoles|jueves|viernes|s[áa]bado|domingo),\s*(\d{1,2}) de ([a-záéíóú]+) de (\d{4})",
                      re.IGNORECASE)
RE_TOKEN = re.compile(
    r'<span class="d\d+">(?P<sec>[^<]*)</span>'
    r'|<span class="DOE6">(?P<sub>[^<]*)</span>'
    r'|<p><span class="DOE2">(?P<org>[^<]*)</span></p>'
    r'|<div class="justificado">(?P<item>.*?)</div>', re.DOTALL)
RE_MATERIA = re.compile(r'<span class="DOE2">(.*?)</span>', re.DOTALL)
RE_TITULO = re.compile(r'<span class="DOE4">(.*?)</span>', re.DOTALL)
RE_PDF = re.compile(r'href="(/pdfs/doe/[^"]+\.pdf)"')
RE_HTML = re.compile(r'href="\.\./otrosFormatos/html\.php\?xml=(?P<id>\d+)&(?:amp;)?anio=(?P<anio>\d{4})&(?:amp;)?doe=(?P<doe>\w+)"')
RE_TEXTO = re.compile(r'<div class="xml">(.*?)(?:<div[^>]*class="pie"|</body>)', re.DOTALL)
RE_DIV_TXT = re.compile(r"<div[^>]*class=\"Txt\w*\"[^>]*>(.*?)</div>", re.DOTALL)


def url_dia(d: date, tipo: str = "o") -> str:
    return f"{BASE}/ultimosdoe/mostrardoe.php?fecha={d:%Y%m%d}&t={tipo}"


def url_html(ident: str, anio: str, edicion: str) -> str:
    return f"{BASE}/otrosFormatos/html.php?xml={ident}&anio={anio}&doe={edicion}"


def parsear_sumario(html: str) -> dict:
    no_encontrado = "No encontrado" in html
    m = RE_NUMERO.search(html)
    f = RE_FECHA.search(html)
    fecha = None
    if f and MESES.get(normalizar(f.group(2))):
        fecha = date(int(f.group(3)), MESES[normalizar(f.group(2))], int(f.group(1))).isoformat()
    seccion = subseccion = organismo = None
    filas = []
    for t in RE_TOKEN.finditer(html):
        if t.group("sec") is not None:
            seccion, subseccion, organismo = texto_de(t.group("sec")), None, None
        elif t.group("sub") is not None:
            subseccion, organismo = texto_de(t.group("sub")), None
        elif t.group("org") is not None:
            organismo = texto_de(t.group("org"))
        elif t.group("item"):
            item = t.group("item")
            h = RE_HTML.search(item)
            tit = RE_TITULO.search(item)
            pdf = RE_PDF.search(item)
            if not tit or not (h or pdf):
                continue
            mat = RE_MATERIA.search(item)
            if h:
                codigo, edicion = h.group("id"), h.group("doe")
            else:  # años anteriores: solo PDF (/pdfs/doe/2022/10o/21040194.pdf)
                partes = pdf.group(1).split("/")
                codigo, edicion = partes[-1].removesuffix(".pdf"), partes[-2]
            filas.append({
                "id": f"DOE-{codigo}", "codigo": codigo, "edicion": edicion,
                "seccion": seccion, "subseccion": subseccion, "organismo": organismo,
                "materia": texto_de(mat.group(1)).rstrip(".- ").strip() if mat else None,
                "titulo": texto_de(tit.group(1)),
                "url_html": url_html(h.group("id"), h.group("anio"), h.group("doe")) if h else None,
                "url_pdf": BASE + pdf.group(1) if pdf else None,
                "url_xml": f"{BASE}/pdfs/doe/{h.group('anio')}/{h.group('doe')}/xml/{h.group('id')}.xml" if h else None,
                "fuente": "DOE",
            })
    return {"no_encontrado": no_encontrado and not filas, "numero": int(m.group(1)) if m else None,
            "fecha": fecha, "disposiciones": filas}


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


def procesar_dia(d: date, raiz: Path, archivo: Archivo, extraordinario: bool = False) -> dict:
    informe = {"fecha": d.isoformat(), "alertas": [], "ediciones": []}
    filas = []
    for tipo in (("o", "e") if extraordinario else ("o",)):
        url = url_dia(d, tipo)
        r = obtener(url, accept="text/html")
        if r.status != 200:
            informe["resultado"] = "error_http"
            informe["alertas"].append(f"DOE {d} ({tipo}): HTTP {r.status}")
            return informe
        s = parsear_sumario(r.contenido.decode("latin-1"))
        if s["no_encontrado"]:
            continue
        if s["fecha"] and s["fecha"] != d.isoformat():
            informe["resultado"] = "error_formato"
            informe["alertas"].append(f"DOE {d} ({tipo}): el sumario es del {s['fecha']}")
            return informe
        if not s["disposiciones"]:
            informe["alertas"].append(f"DOE {d} ({tipo}): sumario sin disposiciones (posible cambio de formato)")
        captura = archivo.guardar(FUENTE, d, r.contenido, url, "html", r.status, r.cabeceras)
        filas += [x | {"fecha": d.isoformat(), "boletin": s["numero"], "tipo_boletin": tipo,
                       "captura_sha256": captura["sha256"]} for x in s["disposiciones"]]
        informe["ediciones"].append({"tipo": tipo, "numero": s["numero"], "sha256": captura["sha256"]})
        time.sleep(0.5)
    if not informe["ediciones"]:
        informe["resultado"] = "sin_boletin"
        if d.weekday() < 5:
            informe["alertas"].append(f"DOE {d}: día laborable sin boletín (¿festivo?)")
        return informe
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    informe.update({"resultado": "ok", "numero": informe["ediciones"][0]["numero"], "disposiciones": len(filas),
                    "empleo_publico": len(empleo)})
    return informe


def texto_disposicion(contenido: bytes) -> dict:
    html = contenido.decode("latin-1")
    m = RE_TEXTO.search(html)
    if not m:
        raise ValueError("sin div.xml: posible cambio de formato")
    cuerpo = RE_DIV_TXT.sub(lambda x: "<p>" + x.group(1) + "</p>", m.group(1))
    return {"titulo": None, **limpiar_html(cuerpo)}


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
    p.add_argument("--saltar-existentes", action="store_true")
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
        print(f"DOE textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        return 0

    reciente = a.desde >= hoy - timedelta(days=3)  # en la pasada diaria se piden también los extraordinarios
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
            inf = procesar_dia(d, a.salida, archivo, extraordinario=reciente)
        except ConnectionError as e:
            inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
        if not (inf.get("resultado") == "sin_boletin" and d >= hoy):
            escribir_json(ruta, inf)
        informes.append(inf)
        if freno.anotar(inf):
            break
        print(f"DOE {d}: {inf.get('resultado')} {inf.get('disposiciones', '')} disposiciones, "
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
