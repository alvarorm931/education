"""Conector del Boletín Oficial del País Vasco (BOPV / EHAA) por sus páginas de sumario.

Formato verificado el 29/10/2026 desde GitHub (también para 2022). Todo en ISO-8859-1:
  - Sumario de un boletín: https://www.euskadi.eus/web01-bopv/es/p43aBOPVWebWar/VerParalelo.do?csAAAANNNNNN
      (AAAA año, NNNNNN número con seis cifras). Si el número no existe, la página dice «Error inesperado».
      Cabecera «Sumario n.º 207 , jueves 29 de octubre de 2026». Dos columnas paralelas: div.bopvBloqueizqda
      (euskera) y div.bopvBloquedcha (castellano). En cada bloque: h4.BOPVSumarioSeccion, h5.BOPVSumarioSubSeccion
      y h5.BOPVSumarioOrganismo (vacíos cuando se repite el anterior) y p.BOPVSumarioTitulo > a (enlace a
      /web01-bopv/es/bopv2/datos/AAAA/MM/AANNNNNa.shtml).
  - Disposición: texto en p.BOPVDetalle y tablas, entre p.BOPVTitulo y el campo oculto bopvNumOrden.
  - Empleo público: «AUTORIDADES Y PERSONAL» > «Oposiciones y concursos» (todo) y «Nombramientos, situaciones e
    incidencias» (solo resultados de procesos); «ANUNCIOS» seleccionados por el título.
  - Último boletín (RSS): https://www.euskadi.eus/bopv2/datos/Ultimo.xml

Uso:
  python -m motor.autonomicos.bopv --salida ruta/                                 # año en curso, lo que falte
  python -m motor.autonomicos.bopv --desde 2022-01-01 --max-minutos 20 --salida ruta/
  python -m motor.autonomicos.bopv --textos --max-minutos 20 --salida ruta/       # textos pendientes

Guarda en datos/autonomicos/bopv/: boletines/ (informe por boletín), disposiciones/, oposiciones/ y textos/.
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo
from motor.autonomicos.comun import (clasificar, convocante_de_organismo, descargar_textos, es_empleo_por_titulo,
                                     es_resultado, escribir_json, escribir_jsonl, leer_jsonl, nombre_propio)
from motor.boe.clasificar import normalizar
from motor.extraccion.texto_es import MESES
from motor.http import obtener
from motor.limpieza import limpiar_html, texto_de

FUENTE = "bopv"
MADRID = ZoneInfo("Europe/Madrid")
BASE = "https://www.euskadi.eus"
RE_CABECERA = re.compile(r"Sumario n\.º\s*(?P<n>\d+)\s*,\s*\w+\s+(?P<d>\d{1,2})\s+de\s+(?P<m>[a-záéíóú]+)\s+de\s+"
                         r"(?P<a>\d{4})", re.IGNORECASE)
RE_BLOQUE = re.compile(r'<div class="bopvBloque(izqda|dcha)">')
RE_TOKEN = re.compile(r'<h[45] class="BOPVSumario(?P<tipo>Seccion|SubSeccion|Organismo)">(?P<v>.*?)</h[45]>'
                      r'|<p class="BOPVSumarioTitulo"><a href="(?P<href>[^"]+)">(?P<titulo>.*?)</a></p>', re.DOTALL)
RE_CODIGO = re.compile(r"/(\d{7})a\.shtml$")
RE_ANUNCIO_EMPLEO = re.compile(r"\b(proceso selectivo|procesos selectivos|pruebas selectivas|plazas?|bolsa|oposicion|"
                               r"convocatoria|funcionari\w+ de carrera|personal laboral fijo)\b")
TERRITORIOS = {"alava": "Araba/Álava", "araba": "Araba/Álava", "bizkaia": "Bizkaia", "gipuzkoa": "Gipuzkoa"}


def url_boletin(anio: int, numero: int) -> str:
    return f"{BASE}/web01-bopv/es/p43aBOPVWebWar/VerParalelo.do?cs{anio}{numero:06d}"


def _html(contenido: bytes) -> str:
    return contenido.decode("latin-1")


def cabecera(html: str) -> tuple[int | None, str | None]:
    plano = " ".join(html_lib.unescape(re.sub(r"<[^>]+>", " ", html)).split())
    m = RE_CABECERA.search(plano)
    if not m or not MESES.get(normalizar(m.group("m"))):
        return None, None
    return int(m.group("n")), date(int(m.group("a")), MESES[normalizar(m.group("m"))], int(m.group("d"))).isoformat()


def parsear_boletin(html: str, numero: int, fecha: str) -> list[dict]:
    """Solo la columna en castellano. Una cabecera vacía repite la anterior."""
    seccion = subseccion = organismo = None
    filas = []
    partes = RE_BLOQUE.split(html)
    for lado, trozo in zip(partes[1::2], partes[2::2]):
        if lado != "dcha":
            continue
        for t in RE_TOKEN.finditer(trozo):
            if t.group("tipo"):
                v = texto_de(t.group("v"))
                if not v:
                    continue
                if t.group("tipo") == "Seccion":
                    seccion, subseccion, organismo = v, None, None
                elif t.group("tipo") == "SubSeccion":
                    subseccion, organismo = v, None
                else:
                    organismo = v
            else:
                href = t.group("href")
                url = href if href.startswith("http") else BASE + href
                codigo = RE_CODIGO.search(href)
                filas.append({
                    "id": f"BOPV-{codigo.group(1)}" if codigo else None, "fecha": fecha, "boletin": numero,
                    "seccion": seccion, "subseccion": subseccion, "organismo": organismo,
                    "titulo": texto_de(t.group("titulo")), "url_html": url,
                    "url_pdf": url.removesuffix(".shtml") + ".pdf", "fuente": "BOPV",
                })
    return [f for f in filas if f["id"]]


def ambito(x: dict) -> str:
    o = normalizar(x.get("organismo") or "")
    if o.startswith(("ayuntamiento", "diputacion foral", "mancomunidad", "cuadrilla", "concejo", "consorcio")):
        return "local"
    if o.startswith("juntas generales"):
        return "otro"
    if o.startswith(("universidad", "euskal herriko unibertsitatea")):
        return "universidad"
    return "autonomico"


def es_empleo_publico(x: dict) -> bool:
    s, sub, t = normalizar(x.get("seccion") or ""), normalizar(x.get("subseccion") or ""), x.get("titulo") or ""
    if s.startswith("autoridades y personal"):
        if "oposiciones" in sub:
            return True
        return es_resultado(t)
    if s.startswith("anuncios"):
        return es_empleo_por_titulo(t) and bool(RE_ANUNCIO_EMPLEO.search(normalizar(t)))
    return False


def convocante(organismo: str) -> dict | None:
    o = " ".join((organismo or "").split())
    n = normalizar(o)
    if n.startswith("diputacion foral de "):
        territorio = TERRITORIOS.get(n.removeprefix("diputacion foral de ").strip())
        return {"tipo": "Diputación Foral", "nombre": territorio or nombre_propio(o[len("DIPUTACIÓN FORAL DE "):]),
                "provincia": territorio, "organismo": o}
    return convocante_de_organismo(o)


def seleccionar(disposiciones: list[dict]) -> list[dict]:
    out = []
    for x in disposiciones:
        if not es_empleo_publico(x):
            continue
        amb = ambito(x)
        out.append({**x, "ambito": amb, **clasificar(x["titulo"], x.get("subseccion")),
                    "convocante": convocante(x["organismo"]) if amb == "local" else None})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "autonomicos" / FUENTE


def ruta_informe(raiz: Path, anio: int, numero: int) -> Path:
    return _base(raiz) / "boletines" / str(anio) / f"{numero:03d}.json"


def _ruta_datos(raiz: Path, carpeta: str, fecha: str, numero: int) -> Path:
    return _base(raiz) / carpeta / fecha[:4] / fecha[5:7] / f"{fecha[8:10]}-{numero:03d}.jsonl"


def procesar_boletin(anio: int, numero: int, raiz: Path, archivo: Archivo) -> dict:
    url = url_boletin(anio, numero)
    r = obtener(url, accept="text/html")
    informe = {"anio": anio, "numero": numero, "status": r.status, "alertas": []}
    if r.status != 200:
        informe["resultado"] = "error_http"
        informe["alertas"].append(f"BOPV {anio}/{numero}: HTTP {r.status}")
        return informe
    html = _html(r.contenido)
    n_cab, fecha = cabecera(html)
    if n_cab is None:
        # El servidor responde 200 con «Error inesperado» cuando el número no existe (aún)
        informe["resultado"] = "sin_boletin" if "Error inesperado" in html or "mensajeerror" in html else "error_formato"
        if informe["resultado"] == "error_formato":
            informe["alertas"].append(f"BOPV {anio}/{numero}: sin cabecera de sumario (posible cambio de formato)")
        return informe
    if n_cab != numero or not fecha or fecha[:4] != str(anio):
        informe["resultado"] = "error_formato"
        informe["alertas"].append(f"BOPV {anio}/{numero}: la cabecera dice número {n_cab} y fecha {fecha}")
        return informe
    captura = archivo.guardar(FUENTE, date.fromisoformat(fecha), r.contenido, url, "html", r.status, r.cabeceras)
    filas = [f | {"captura_sha256": captura["sha256"]} for f in parsear_boletin(html, numero, fecha)]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta_datos(raiz, "disposiciones", fecha, numero), filas)
    escribir_jsonl(_ruta_datos(raiz, "oposiciones", fecha, numero), empleo)
    informe.update({"resultado": "ok", "fecha": fecha, "sha256": captura["sha256"], "disposiciones": len(filas),
                    "empleo_publico": len(empleo)})
    if not filas:
        informe["alertas"].append(f"BOPV {anio}/{numero}: boletín sin disposiciones (posible cambio de formato)")
    return informe


def texto_disposicion(contenido: bytes) -> dict:
    html = _html(contenido)
    i = html.find('<p class="BOPVTitulo">')
    if i < 0:
        raise ValueError("sin BOPVTitulo: posible cambio de formato")
    fin = html.find('name="bopvNumOrden"', i)
    cuerpo = html[i:fin if fin > 0 else None]
    titulo = re.search(r'<p class="BOPVTitulo">(.*?)</p>', cuerpo, re.DOTALL)
    limpio = limpiar_html(cuerpo[titulo.end():] if titulo else cuerpo)

    def _cab(clase: str) -> str | None:
        m = re.search(rf'<h[45] class="{clase}">(.*?)</h[45]>', html, re.DOTALL)
        return texto_de(m.group(1)) or None if m else None
    return {"titulo": texto_de(titulo.group(1)) if titulo else None, "seccion": _cab("BOPVSeccion"),
            "subseccion": _cab("BOPVSubseccion"), "organismo": _cab("BOPVOrganismo"), **limpio}


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
    archivo = Archivo(a.salida / "archivo")

    if a.textos:
        pend = textos_pendientes(a.salida)
        hechos, errores = descargar_textos(pend, lambda x: ruta_texto(a.salida, x), lambda x: x["url_html"],
                                           texto_disposicion, archivo, FUENTE, a.max_minutos, a.pausa,
                                           accept="text/html", ext="html")
        print(f"BOPV textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        return 0

    inicio, informes = time.monotonic(), []
    for anio in range(a.desde.year, a.hasta.year + 1):
        numero = 0
        while True:
            numero += 1
            ruta = ruta_informe(a.salida, anio, numero)
            hecho = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None
            if hecho and hecho.get("resultado") == "ok":
                if hecho.get("fecha", "") > a.hasta.isoformat():
                    break
                continue
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                return _final(informes)
            try:
                inf = procesar_boletin(anio, numero, a.salida, archivo)
            except ConnectionError as e:
                inf = {"anio": anio, "numero": numero, "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            informes.append(inf)
            time.sleep(a.pausa)
            if inf["resultado"] != "ok":
                # Número aún no publicado (fin del año en curso) o fallo: se sigue en la siguiente ejecución.
                # No se guarda informe de «sin_boletin» para poder volver a pedirlo.
                if inf["resultado"] != "sin_boletin":
                    escribir_json(ruta, inf)
                    print(f"BOPV {anio}/{numero}: {inf['resultado']}")
                break
            escribir_json(ruta, inf)
            print(f"BOPV {anio}/{numero} {inf.get('fecha')}: ok {inf.get('disposiciones')} disposiciones, "
                  f"{inf.get('empleo_publico')} de empleo público")
            if inf.get("fecha", "") > a.hasta.isoformat():
                break
    return _final(informes)


def _final(informes: list[dict]) -> int:
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Boletines procesados: {len(informes)}. Alertas: {len(alertas)}")
    for x in alertas[:30]:
        print(" -", x)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
