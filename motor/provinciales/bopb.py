"""Conector del Butlletí Oficial de la Província de Barcelona (BOPB).

Formato verificado el 29/10/2026 desde GitHub (también para 2022):
  - Día filtrado por tipo de anuncio «Personal» (tipusAnunci=60), 20 anuncios por página:
      https://bop.diba.cat/anteriors/2026-10-28?bopb_dia%5BtipusAnunci%5D=60
      https://bop.diba.cat/anteriors/2026-10-28/2?bopb_dia%5BtipusAnunci%5D=60
    «S'han trobat 27 resultats per la seva cerca, mostrant del 1 al 20».
    Cada anuncio: enlace /anunci/{número}/{título}, anunciante (h3), título (p), «Registre» (es el CVE) y fecha.
  - Sábados y domingos el portal responde 500 (no hay boletín). Un festivo con boletín y sin anuncios de
    personal devuelve la página del día sin resultados.
  - Texto: solo en PDF, /anunci/descarrega-pdf/{número}. Las listas de admitidos y los nombramientos traen
    datos de personas: de esos se guarda solo el número de líneas con un documento de identidad, no el texto.
  - Los anuncios se publican en la lengua del anunciante, casi siempre en catalán.

Uso:
  python -m motor.provinciales.bopb --salida ruta/                                   # ayer y hoy
  python -m motor.provinciales.bopb --desde 2022-01-01 --max-minutos 30 --salida ruta/
  python -m motor.provinciales.bopb --textos --max-minutos 30 --salida ruta/
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (RE_NO_EMPLEO, clasificar, convocante_de_organismo, descargar_textos,
                                     escribir_json, escribir_jsonl, leer_jsonl)
from motor.boe.clasificar import normalizar
from motor.http import obtener
from motor.provinciales.comun import CON_TEXTO, texto_pdf

FUENTE = "bopb"
SIGLAS = "BOPB"
MADRID = ZoneInfo("Europe/Madrid")
BASE = "https://bop.diba.cat"
POR_PAGINA = 20
FILTRO_PERSONAL = "bopb_dia%5BtipusAnunci%5D=60"
NOMBRES = ("Butlletí Oficial de la Província de Barcelona", "Boletín Oficial de la Provincia de Barcelona")

RE_TARJETA = re.compile(r'<div class="card bg-white[^"]*">(?P<c>.*?)</div>\s*</div>', re.DOTALL)
RE_ENLACE = re.compile(r'<a href="(?P<href>/anunci/(?P<num>\d+)/[^"]*)"[^>]*>(?P<anunciante>.*?)</a>', re.DOTALL)
RE_TITULO = re.compile(r"</h3>\s*<p>(?P<t>.*?)</p>", re.DOTALL)
RE_REGISTRO = re.compile(r"Registre</span>:\s*(?P<r>\d+)")
RE_FECHA = re.compile(r"publicaci[oó]</span>:\s*(?P<d>\d{2})/(?P<m>\d{2})/(?P<a>\d{4})")
RE_DIA = re.compile(r'<time datetime="(?P<f>\d{4}-\d{2}-\d{2})"')
RE_TOTAL = re.compile(r"S(?:&#039;|')han trobat (?P<n>\d+) resultats")

# Cabeceras y pies repetidos en cada página de los PDF del BOPB
RE_CABECERA_PDF = re.compile(
    r"^(?:[AB]|Butlletí Oficial de la Província de Barcelona|Data \d{2}-\d{2}-\d{4}|CVE \d+|Pàg\. \d+-\d+|"
    r"https://bop\.diba\.cat|\d+/\d+|Powered by TCPDF.*|Codi Validació:.*|Verificació:.*|"
    r"Document signat electrònicament.*)$")


def url_dia(d: date, pagina: int = 1) -> str:
    return f"{BASE}/anteriors/{d:%Y-%m-%d}" + (f"/{pagina}" if pagina > 1 else "") + f"?{FILTRO_PERSONAL}"


def _texto(fragmento: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragmento)).split())


def parsear_dia(contenido: str) -> dict:
    dia = RE_DIA.search(contenido)
    total = RE_TOTAL.search(contenido)
    anuncios = []
    for t in RE_TARJETA.finditer(contenido):
        c = t.group("c")
        e, ti, r, f = RE_ENLACE.search(c), RE_TITULO.search(c), RE_REGISTRO.search(c), RE_FECHA.search(c)
        if not (e and ti and r):
            continue
        anuncios.append({
            "id": f"BOPB-{r.group('r')}", "cve": r.group("r"), "numero_anuncio": e.group("num"),
            "anunciante": _texto(e.group("anunciante")), "titulo": _texto(ti.group("t")),
            "fecha": f"{f.group('a')}-{f.group('m')}-{f.group('d')}" if f else None,
            "url_html": BASE + e.group("href").split("?")[0],
            "url_pdf": f"{BASE}/anunci/descarrega-pdf/{e.group('num')}", "fuente": SIGLAS,
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


def seleccionar(anuncios: list[dict]) -> list[dict]:
    """Todo el filtro «Personal» es empleo público, salvo lo que no lo es aunque caiga ahí (jueces de paz,
    viviendas, ayudas)."""
    out = []
    for x in anuncios:
        if RE_NO_EMPLEO.search(normalizar(x["titulo"])):
            continue
        amb = ambito(x["anunciante"])
        conv = convocante_de_organismo(x["anunciante"]) if amb == "local" else None
        if conv and not conv.get("provincia"):
            conv["provincia"] = "Barcelona"
        out.append({**x, "ambito": amb, **clasificar(x["titulo"]), "convocante": conv,
                    "organismo": x["anunciante"]})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "provinciales" / FUENTE


def _ruta(raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


def procesar_dia(d: date, raiz: Path, archivo: Archivo, pausa: float = 1.0) -> dict:
    informe = {"fecha": d.isoformat(), "alertas": []}
    anuncios, total, paginas = [], None, 1
    pagina = 1
    while pagina <= paginas:
        url = url_dia(d, pagina)
        r = obtener(url, accept="text/html")
        informe["status"] = r.status
        if r.status != 200:
            if pagina == 1 and r.status >= 500 and d.weekday() >= 5:
                informe["resultado"] = "sin_boletin"
                return informe
            informe["resultado"] = "error_http"
            informe["alertas"].append(f"BOPB {d} página {pagina}: HTTP {r.status}")
            return informe
        s = parsear_dia(r.contenido.decode("utf-8", errors="replace"))
        if s["fecha"] != d.isoformat():
            informe["resultado"] = "error_formato"
            informe["alertas"].append(f"BOPB {d}: la página no es la del día (posible cambio de formato)")
            return informe
        archivo.guardar(FUENTE, d, r.contenido, url, "html", r.status, r.cabeceras)
        if total is None:
            total = s["total"]
            paginas = max(1, math.ceil(total / POR_PAGINA))
        anuncios += s["anuncios"]
        pagina += 1
        if pagina <= paginas:
            time.sleep(pausa)
    empleo = seleccionar(anuncios)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), anuncios)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    informe.update({"resultado": "ok", "paginas": paginas, "anuncios_personal": total,
                    "disposiciones": len(anuncios), "empleo_publico": len(empleo)})
    if total and len(anuncios) != total:
        informe["alertas"].append(f"BOPB {d}: {len(anuncios)} anuncios leídos de {total} (posible cambio de formato)")
    return informe


def texto_disposicion(contenido: bytes, con_texto: bool = True) -> dict:
    return texto_pdf(contenido, con_texto, RE_CABECERA_PDF)


def ruta_texto(raiz: Path, x: dict) -> Path:
    return _base(raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"


def textos_pendientes(raiz: Path) -> list[dict]:
    lista = []
    for f in (_base(raiz) / "oposiciones").glob("*/*/*.jsonl"):
        lista += [x for x in leer_jsonl(f) if x.get("url_pdf") and not ruta_texto(raiz, x).exists()]
    lista.sort(key=lambda x: x["fecha"], reverse=True)
    return sorted(lista, key=lambda x: (0 if x.get("tipo_acto") in CON_TEXTO else 1,
                                        0 if x.get("alcance") in (None, "acceso") else 1))


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
        hechos, errores = descargar_textos(
            pend, lambda x: ruta_texto(a.salida, x), lambda x: x["url_pdf"],
            lambda c, x: texto_disposicion(c, x.get("tipo_acto") in CON_TEXTO), archivo, FUENTE, a.max_minutos,
            a.pausa, accept="application/pdf", ext="pdf", por_registro=True)
        print(f"BOPB textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        return 0

    inicio, informes = time.monotonic(), []
    d = a.hasta
    # Del más reciente al más antiguo: lo nuevo primero; lo hecho (ok o sin boletín) no se repite
    while d >= a.desde:
        ruta = _ruta(a.salida, "dias", d, "json")
        hecho = ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") in {"ok", "sin_boletin"}
        if not hecho or d >= hoy - timedelta(days=1):
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
            print(f"BOPB {d}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            time.sleep(a.pausa)
        d -= timedelta(days=1)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    for x in alertas[:30]:
        print(" -", x)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
