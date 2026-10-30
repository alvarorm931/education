"""Conector del Diario Oficial de Galicia (DOG) por sus páginas estáticas de sumario.

Formato verificado el 29/10/2026 desde GitHub:
  - Índice del día: https://www.xunta.gal/dog/Publicados/AAAA/AAAAMMDD/Indice{N}_es.html
      N es el número del boletín, correlativo dentro del año (1 el primer día hábil). Lista las secciones del día
      y enlaza a SeccionesK_es.html (K es el orden de la sección ese día, no un código fijo).
  - Sección: .../SeccionesK_es.html con p.dog-toc-nivel-1 (sección), p.dog-toc-nivel-2 (subsección),
      p.dog-toc-organismo y li.dog-toc-sumario > a (título y enlace a AnuncioXXXX_es.html), p.dog-pagina.
  - Disposición: .../Anuncio{codigo}_es.html, texto en div.story (párrafos y tablas).
  - Empleo público: «IV. Oposiciones y concursos» (todo); «II. Autoridades y personal» (nombramientos de quienes
    superan un proceso); «VI. Anuncios» b) Administración local y c) Otros anuncios, seleccionados por el título.
  - Como N no se conoce de antemano, se recorre cada año en orden: tras el boletín N se busca N+1 (y N+2 por si
    hubo un número extraordinario). También sábados y domingos. Si no aparece, ese día no hubo boletín.

Uso:
  python -m motor.autonomicos.dog --salida ruta/                                   # año en curso, lo que falte
  python -m motor.autonomicos.dog --desde 2022-01-01 --max-minutos 20 --salida ruta/
  python -m motor.autonomicos.dog --textos --max-minutos 20 --salida ruta/         # textos pendientes

Guarda en datos/autonomicos/dog/: dias/, disposiciones/, oposiciones/ y textos/.
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
from motor.boe.extraer import MESES
from motor.http import obtener
from motor.limpieza import limpiar_html, texto_de

FUENTE = "dog"
MADRID = ZoneInfo("Europe/Madrid")
BASE = "https://www.xunta.gal"
PUBLICADOS = BASE + "/dog/Publicados"

RE_NUMERO = re.compile(r'id="DOGNumero"[^>]*>\s*N[ºo°]\s*(\d+)', re.IGNORECASE)
RE_FECHA = re.compile(r'id="DOGData"[^>]*>[^,<]*,\s*(\d{1,2}) de ([a-záéíóú]+) de (\d{4})', re.IGNORECASE)
RE_ENLACE_SECCION = re.compile(r'<a href="[^"]*ruta=/\d{4}/\d{8}/Secciones(\d+)_es\.html(?:#[^"]*)?">([^<]+)</a>')
RE_TOKEN = re.compile(
    r'<p class="dog-toc-(?P<nivel>nivel-1|nivel-2|organismo)">(?P<texto>.*?)</p>'
    r'|<li class="dog-toc-sumario">(?P<item>.*?)</li>'
    r'|<p class="dog-pagina">(?P<pagina>.*?)</p>', re.DOTALL)
RE_A = re.compile(r'<a href="(?P<href>[^"]+)"[^>]*>(?P<titulo>.*?)</a>', re.DOTALL)
RE_STORY = re.compile(r'<div class="story">(.*?)(?:<nav id="navegacionInferior"|</main>)', re.DOTALL)


def url_indice(d: date, n: int) -> str:
    return f"{PUBLICADOS}/{d:%Y}/{d:%Y%m%d}/Indice{n}_es.html"


def url_seccion(d: date, k: int) -> str:
    return f"{PUBLICADOS}/{d:%Y}/{d:%Y%m%d}/Secciones{k}_es.html"


def parsear_indice(html: str) -> dict:
    m = RE_NUMERO.search(html)
    f = RE_FECHA.search(html)
    fecha = None
    if f and MESES.get(normalizar(f.group(2))):
        fecha = date(int(f.group(3)), MESES[normalizar(f.group(2))], int(f.group(1))).isoformat()
    secciones: dict[int, str] = {}
    for k, titulo in RE_ENLACE_SECCION.findall(html):
        secciones.setdefault(int(k), " ".join(titulo.split()))  # la primera aparición es la sección principal
    return {"numero": int(m.group(1)) if m else None, "fecha": fecha,
            "secciones": [{"k": k, "titulo": t} for k, t in sorted(secciones.items())]}


def parsear_seccion(html: str, d: date, numero: int) -> list[dict]:
    seccion = subseccion = organismo = None
    filas = []
    for t in RE_TOKEN.finditer(html):
        if t.group("nivel") == "nivel-1":
            seccion, subseccion, organismo = texto_de(t.group("texto")), None, None
        elif t.group("nivel") == "nivel-2":
            subseccion, organismo = texto_de(t.group("texto")), None
        elif t.group("nivel") == "organismo":
            organismo = texto_de(t.group("texto"))
        elif t.group("item"):
            a = RE_A.search(t.group("item"))
            if not a:
                continue
            href = a.group("href")
            url = href if href.startswith("http") else BASE + href
            codigo = url.rsplit("/", 1)[-1].removesuffix("_es.html")
            filas.append({"id": f"DOG-{d:%Y%m%d}-{codigo}", "codigo": codigo, "fecha": d.isoformat(), "boletin": numero,
                          "seccion": seccion, "subseccion": subseccion, "organismo": organismo,
                          "titulo": texto_de(a.group("titulo")), "url_html": url,
                          "url_pdf": url.removesuffix(".html") + ".pdf", "pagina": None, "fuente": "DOG"})
        elif t.group("pagina") and filas:
            filas[-1]["pagina"] = texto_de(t.group("pagina"))
    return filas


def ambito(x: dict) -> str:
    o = normalizar(x.get("organismo") or "")
    sub = normalizar(x.get("subseccion") or "")
    if "administracion local" in sub or o.startswith(("ayuntamiento", "concello", "diputacion", "deputacion",
                                                       "mancomunidad", "consorcio")):
        return "local"
    if o.startswith(("universidad", "universidade")):
        return "universidad"
    if "otros anuncios" in sub:
        return "otro"
    return "autonomico"


def es_empleo_publico(x: dict) -> bool:
    s = normalizar(x.get("seccion") or "")
    t = x.get("titulo") or ""
    if s.startswith("iv."):
        return True
    if s.startswith("ii."):
        return es_resultado(t)
    if s.startswith("vi."):
        sub = normalizar(x.get("subseccion") or "")
        return ("administracion local" in sub or "otros anuncios" in sub) and \
            (es_empleo_por_titulo(t) or es_resultado(t))
    return False


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


def _ruta(raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


def _html(url: str) -> tuple[int, str, bytes, dict]:
    r = obtener(url, accept="text/html")
    return r.status, r.contenido.decode("utf-8", errors="replace") if r.status == 200 else "", r.contenido, r.cabeceras


def procesar_dia(d: date, siguiente: int, raiz: Path, archivo: Archivo) -> dict:
    """Busca el boletín «siguiente» (o el posterior) en la fecha d y procesa sus secciones de interés."""
    informe = {"fecha": d.isoformat(), "alertas": [], "probados": []}
    for n in (siguiente, siguiente + 1):
        url = url_indice(d, n)
        status, html, bruto, cab = _html(url)
        informe["probados"].append([n, status])
        if status == 200:
            break
        if status != 404:
            informe["resultado"] = "error_http"
            informe["alertas"].append(f"DOG {d}: índice {n} HTTP {status}")
            return informe
    else:
        informe["resultado"] = "sin_boletin"
        if d.weekday() < 5:
            informe["alertas"].append(f"DOG {d}: día laborable sin boletín (¿festivo?)")
        return informe

    indice = parsear_indice(html)
    if indice["numero"] != n or (indice["fecha"] and indice["fecha"] != d.isoformat()):
        informe["resultado"] = "error_formato"
        informe["alertas"].append(f"DOG {d}: índice {n} dice número {indice['numero']} y fecha {indice['fecha']}")
        return informe
    if n != siguiente:
        informe["alertas"].append(f"DOG {d}: se esperaba el {siguiente} y salió el {n} (¿extraordinario?)")
    captura = archivo.guardar(FUENTE, d, bruto, url, "html", status, cab)
    filas = []
    for s in indice["secciones"]:
        st = normalizar(s["titulo"])
        if not st.startswith(("ii.", "iv.", "vi.")):
            continue
        u = url_seccion(d, s["k"])
        status, html_s, bruto_s, cab_s = _html(u)
        if status != 200:
            informe["alertas"].append(f"DOG {d}: sección {s['k']} HTTP {status}")
            continue
        c = archivo.guardar(FUENTE, d, bruto_s, u, "html", status, cab_s)
        filas += [f | {"captura_sha256": c["sha256"]} for f in parsear_seccion(html_s, d, n)]
        time.sleep(0.5)
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    informe.update({"resultado": "ok", "numero": n, "sha256": captura["sha256"],
                    "secciones": [s["titulo"] for s in indice["secciones"]],
                    "disposiciones_leidas": len(filas), "empleo_publico": len(empleo)})
    return informe


def texto_disposicion(contenido: bytes) -> dict:
    html = contenido.decode("utf-8", errors="replace")
    m = RE_STORY.search(html)
    if not m:
        raise ValueError("sin div.story: posible cambio de formato")
    limpio = limpiar_html(m.group(1))
    return {"titulo": None, **limpio}


def ruta_texto(raiz: Path, x: dict) -> Path:
    return _base(raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"


def textos_pendientes(raiz: Path) -> list[dict]:
    lista = []
    for f in sorted((_base(raiz) / "oposiciones").glob("*/*/*.jsonl"), reverse=True):
        lista += [x for x in leer_jsonl(f) if x.get("url_html") and not ruta_texto(raiz, x).exists()]
    return sorted(lista, key=lambda x: 0 if x.get("alcance") in (None, "acceso") else 1)


def ultimo_numero(raiz: Path, antes_de: date) -> tuple[int, date] | None:
    """Último boletín conocido del mismo año antes de la fecha (desde los informes ya guardados)."""
    d = antes_de - timedelta(days=1)
    while d.year == antes_de.year:
        r = _ruta(raiz, "dias", d, "json")
        if r.exists():
            inf = json.loads(r.read_text(encoding="utf-8"))
            if inf.get("resultado") == "ok" and inf.get("numero"):
                return inf["numero"], d
        d -= timedelta(days=1)
    return None


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=date.fromisoformat, default=date(hoy.year, 1, 1))
    p.add_argument("--hasta", type=date.fromisoformat, default=hoy)
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
        print(f"DOG textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        return 0

    inicio, informes = time.monotonic(), []
    freno = Freno()
    d = a.desde
    previo = ultimo_numero(a.salida, d)
    if previo is None and d != date(d.year, 1, 1):
        print(f"DOG: sin boletines conocidos de {d.year} antes de {d}; se empieza el 1 de enero")
        d = date(d.year, 1, 1)
    siguiente = previo[0] + 1 if previo else 1
    while d <= a.hasta:
        if d.month == 1 and d.day == 1:
            siguiente = 1
        if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
            print("Tiempo agotado; se continúa en la siguiente ejecución")
            break
        ruta = _ruta(a.salida, "dias", d, "json")
        hecho = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None
        # «fin_de_semana» ya no cuenta como hecho: esos días se piden (el DOG saca extraordinarios en sábado)
        if hecho and hecho.get("resultado") in {"ok", "sin_boletin"} and d < hoy:
            if hecho.get("numero"):
                siguiente = hecho["numero"] + 1
            d += timedelta(days=1)
            continue
        # También sábados y domingos: n.º 166 de 2025 el sábado 30/08 y n.º 83 de 2022 el sábado 30/04 (comprobado el
        # 29/10/2026); un día sin boletín son dos 404.
        try:
            inf = procesar_dia(d, siguiente, a.salida, archivo)
        except ConnectionError as e:
            inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
        time.sleep(a.pausa)
        if inf.get("resultado") == "sin_boletin" and d >= hoy:
            break  # el de hoy puede no estar publicado aún: no se da por cerrado
        escribir_json(ruta, inf)
        informes.append(inf)
        if freno.anotar(inf):
            break
        if inf.get("numero"):
            siguiente = inf["numero"] + 1
        if inf["resultado"] not in {"fin_de_semana"}:
            print(f"DOG {d}: {inf['resultado']} {inf.get('numero', '')} {inf.get('empleo_publico', '')}")
        if inf["resultado"] in {"error_http", "error_formato", "fuente_inaccesible"}:
            break  # sin el número correcto no se puede seguir en orden; se reintenta en la siguiente ejecución
        d += timedelta(days=1)

    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    for x in alertas[:30]:
        print(" -", x)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
