"""Boletines provinciales de la plataforma «mostra-bop» (Girona y Lleida usan la misma aplicación).

Formato verificado el 30/10/2026 (Girona desde GitHub, Lleida desde el servidor de España):
  - Portada: el último boletín, con su cabecera «Bop número: 208/0 - 30/10/2026» (y en Girona, el enlace «Últim
    número» a /bop/mostra-bop/AAAA-MM-DD/AAAA/N).
  - Boletín: /bop/mostra-bop/F/AAAA/N (vale el año y el número; la fecha de la dirección no cuenta). Por sección
    (h2.seccioTau «Administració local - Ajuntaments») cada edicto (li.edicte) como «9143 - <span>AJUNTAMENT
    D'AIGUAVIVA</span> - Aprovació…» enlazando a su PDF. En catalán.
  - Los números son correlativos en el año: el histórico se recorre número a número.

Cada boletín es una Plataforma; su módulo solo la declara (motor/provinciales/bopgirona.py, boplleida.py).
"""

from __future__ import annotations

import argparse
import html
import json
import re
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (Freno, clasificar, convocante_de_organismo, es_empleo_estricto, escribir_json,
                                     escribir_jsonl)
from motor.boe.clasificar import normalizar
from motor.http import obtener

RE_ULTIMO = re.compile(r'href="/bop/mostra-bop/[^/"]+/(\d{4})/(\d+)"[^>]*>\s*[ÚU]ltim')
RE_CABECERA = re.compile(r"Bop n[úu]mero:\s*(?P<n>\d+)/(?P<s>\d+)\s*-\s*(?P<d>\d{2})/(?P<m>\d{2})/(?P<a>\d{4})")
RE_TOKEN = re.compile(r'<h2 class="seccioTau">\s*(?P<sec>.*?)\s*</h2>|<li class="edicte">\s*<a href="(?P<pdf>[^"]+)"[^>]*>'
                      r"\s*(?P<num>\d+)\s*-\s*<span>(?P<ent>.*?)</span>\s*-\s*(?P<tit>.*?)\s*</a>", re.DOTALL)
RE_MUNICIPIO_DETRAS = re.compile(r"\s*\([^()]+\)\s*$")  # Lleida: «AJUNTAMENT D'AGRAMUNT (AGRAMUNT)»


@dataclass
class Plataforma:
    fuente: str
    siglas: str
    provincia: str
    web: str
    nombres: tuple[str, ...]

    @property
    def portada(self) -> str:
        return self.web + "/bop/"

    def url_boletin(self, anio: int, numero: int) -> str:
        return f"{self.web}/bop/mostra-bop/{anio}-01-01/{anio}/{numero}"


def _t(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).replace("\xa0", " ").split())


def ultimo(contenido: bytes) -> tuple[int, int] | None:
    h = contenido.decode("utf-8", errors="replace")
    m = RE_ULTIMO.search(h)
    if m:
        return int(m.group(1)), int(m.group(2))
    c = RE_CABECERA.search(h)  # la portada muestra el último boletín
    return (int(c.group("a")), int(c.group("n"))) if c else None


def parsear_boletin(contenido: bytes) -> dict:
    h = contenido.decode("utf-8", errors="replace")
    c = RE_CABECERA.search(h)
    seccion, anuncios = None, []
    for m in RE_TOKEN.finditer(h, c.end() if c else 0):
        if m.group("sec") is not None:
            seccion = _t(m.group("sec"))
        else:
            anuncios.append({"numero_anuncio": m.group("num"), "seccion": seccion, "entidad": _t(m.group("ent")),
                             "titulo": _t(m.group("tit")), "url_pdf": html.unescape(m.group("pdf"))})
    return {"numero": int(c.group("n")) if c else None,
            "fecha": f"{c.group('a')}-{c.group('m')}-{c.group('d')}" if c else None, "anuncios": anuncios}


def es_local(x: dict) -> bool:
    return "administracio local" in normalizar(x.get("seccion") or "")


def convocante(p: Plataforma, x: dict) -> dict | None:
    c = convocante_de_organismo(RE_MUNICIPIO_DETRAS.sub("", x.get("entidad") or ""))
    if c and not c.get("provincia"):
        c["provincia"] = p.provincia
    return c


def seleccionar(p: Plataforma, filas: list[dict]) -> list[dict]:
    out = []
    for x in filas:
        if not es_empleo_estricto(x["titulo"]):
            continue
        local = es_local(x)
        out.append({**x, "ambito": "local" if local else "otro", **clasificar(x["titulo"]),
                    "convocante": convocante(p, x) if local else None})
    return out


def _base(p: Plataforma, raiz: Path) -> Path:
    return raiz / "datos" / "provinciales" / p.fuente


def _ruta_numero(p: Plataforma, raiz: Path, anio: int, numero: int) -> Path:
    return _base(p, raiz) / "boletines" / str(anio) / f"{numero:03d}.json"


def _ruta(p: Plataforma, raiz: Path, carpeta: str, fecha: str, numero: int) -> Path:
    return _base(p, raiz) / carpeta / fecha[:4] / fecha[5:7] / f"{fecha[8:10]}-{numero:03d}.jsonl"


def procesar_boletin(p: Plataforma, anio: int, numero: int, raiz: Path, archivo: Archivo) -> dict:
    url = p.url_boletin(anio, numero)
    r = obtener(url, accept="text/html")
    inf = {"anio": anio, "numero": numero, "status": r.status, "alertas": []}
    if r.status != 200:
        inf["resultado"] = "error_http"
        inf["alertas"].append(f"{p.siglas} {anio}/{numero}: HTTP {r.status}")
        return inf
    s = parsear_boletin(r.contenido)
    if s["numero"] != numero or not s["fecha"] or s["fecha"][:4] != str(anio):
        inf["resultado"] = "no_existe"  # más allá del último número del año
        return inf
    captura = archivo.guardar(p.fuente, date.fromisoformat(s["fecha"]), r.contenido, url, "html", r.status,
                              r.cabeceras)
    pref = p.siglas.replace("-", "")
    filas = [{**x, "id": f"{pref}-{anio}-{x['numero_anuncio']}", "fecha": s["fecha"], "boletin": numero,
              "url_boletin": url, "fuente": p.siglas, "captura_sha256": captura["sha256"]} for x in s["anuncios"]]
    empleo = seleccionar(p, filas)
    escribir_jsonl(_ruta(p, raiz, "disposiciones", s["fecha"], numero), filas)
    escribir_jsonl(_ruta(p, raiz, "oposiciones", s["fecha"], numero), empleo)
    inf.update({"resultado": "ok", "fecha": s["fecha"], "sha256": captura["sha256"], "disposiciones": len(filas),
                "empleo_publico": len(empleo)})
    if not filas:
        inf["alertas"].append(f"{p.siglas} {anio}/{numero}: boletín sin edictos (posible cambio de formato)")
    return inf


def main(p: Plataforma, argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", type=date.fromisoformat, default=None,
                    help="primer año del histórico (sin ella, solo lo nuevo hasta lo ya leído)")
    ap.add_argument("--salida", type=Path, default=Path("."))
    ap.add_argument("--max-minutos", type=float, default=0)
    ap.add_argument("--pausa", type=float, default=1.0)
    a = ap.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    try:
        r = obtener(p.portada, accept="text/html")
        actual = ultimo(r.contenido) if r.status == 200 else None
    except (ConnectionError, TimeoutError) as e:
        print(f"{p.siglas}: fuente inaccesible ({e})")
        return 1
    if not actual:
        print(f"::warning::{p.siglas}: la portada no dice cuál es el último número (posible cambio de formato)")
        return 1
    anio_fin, num_fin = actual
    primero = a.desde.year if a.desde else anio_fin
    inicio, informes, freno = time.monotonic(), [], Freno()
    for anio in range(anio_fin, primero - 1, -1):
        # el año en curso, del último número hacia atrás; los cerrados, del 1 hacia delante hasta pasar el último
        n, paso = (num_fin, -1) if anio == anio_fin else (1, 1)
        while n >= 1:
            ruta = _ruta_numero(p, a.salida, anio, n)
            previo = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
            if previo.get("resultado") == "no_existe" and paso == 1:
                break
            if previo.get("resultado") == "ok":
                if a.desde is None and paso == -1:
                    break  # sin --desde basta con llegar a lo ya leído
                n += paso
                continue
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                return 0
            time.sleep(a.pausa)
            try:
                inf = procesar_boletin(p, anio, n, a.salida, archivo)
            except (ConnectionError, TimeoutError) as e:
                inf = {"anio": anio, "numero": n, "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            if inf["resultado"] != "no_existe" or paso == 1:
                escribir_json(ruta, inf)
            informes.append(inf)
            print(f"{p.siglas} {anio}/{n} {inf.get('fecha', '')}: {inf['resultado']} {inf.get('empleo_publico', '')}")
            if freno.anotar(inf):
                return 1
            if inf["resultado"] == "no_existe" and paso == 1:
                break
            n += paso
        if a.desde is None:
            break
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Boletines procesados: {len(informes)}. Alertas: {len(alertas)}")
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0
