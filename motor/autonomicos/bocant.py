"""Conector del Boletín Oficial de Cantabria (BOC de Cantabria).

Formato verificado el 30/10/2026 desde el servidor de España (desde GitHub no responde):
  - Boletín de un día: https://boc.cantabria.es/boces/boletines.do?boton=Buscar&boletinBean.fecBolString=DD/MM/AAAA
    &boletinBean.tipoBol=0 (ordinario; 1 = extraordinario). Cabecera «Boletín Oficial de Cantabria: 29 de octubre de
    2026, ORD. Núm. 208» («EXT.» en los extraordinarios, con numeración propia). Sin boletín: «No se han encontrado
    boletines que mostrar».
  - Extraordinarios por número: …boletinBean.numBolString=N/AAAA&boletinBean.tipoBol=1.
  - Sumario: sección (span.titulo2 «2.Autoridades y Personal»), subsección (span.spanH5 «2.2.Cursos, Oposiciones y
    Concursos»), organismo (span.spanH4) y, por anuncio, el título (p) y su PDF (verAnuncioAction.do?idAnuBlob=N,
    «BOC-2026-8422»). El boletín completo en XML (verXmlAction.do?idBlob=N) trae el texto de cada anuncio: de ahí
    salen los textos, un XML por boletín.
  - robots.txt: el servidor responde con una página de error, sin reglas.
  - Empleo público: «2.2 Cursos, oposiciones y concursos», todo; «2.1 Nombramientos…», los de procesos selectivos;
    «2.3 Otros» y «7 Otros anuncios», por el título (filtro estricto).

Uso:
  python -m motor.autonomicos.bocant --salida ruta/                                  # ayer y hoy, y extraordinarios
  python -m motor.autonomicos.bocant --desde 2022-01-01 --max-minutos 20 --salida ruta/
  python -m motor.autonomicos.bocant --textos --max-minutos 20 --salida ruta/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (Freno, clasificar, convocante_de_organismo, es_empleo_estricto, es_resultado,
                                     escribir_json, escribir_jsonl, leer_jsonl)
from motor.boe.clasificar import normalizar
from motor.extraccion.texto_es import fecha_texto
from motor.http import obtener
from motor.limpieza import limpiar_html, texto_de

FUENTE = "bocant"
SIGLAS = "BOC-CANT"
MADRID = ZoneInfo("Europe/Madrid")
BASE = "https://boc.cantabria.es/boces"
NOMBRES = ("Boletín Oficial de Cantabria",)

RE_CABECERA = re.compile(r"Bolet(?:&iacute;|í)n Oficial de Cantabria:\s*(?P<d>\d{1,2}) de (?P<m>\w+) de (?P<a>\d{4}),\s*"
                         r"(?P<tipo>ORD|EXT)\.\s*N(?:&uacute;|ú)m\.\s*(?P<n>\d+)")
RE_SIN_BOLETIN = re.compile(r"No se han encontrado boletines")
RE_XML = re.compile(r'href="verXmlAction\.do\?idBlob=(\d+)"')
RE_TOKEN = re.compile(r'<span class="titulo2 margin-bottom-12">(?P<sec>.*?)</span>|<span class="spanH5">(?P<sub>.*?)</span>'
                      r'|<span class="spanH4">(?P<org>.*?)</span>|<p>(?P<p>.*?)</p>'
                      r'|<a href="verAnuncioAction\.do\?idAnuBlob=(?P<blob>\d+)"[^>]*>\s*PDF \((?P<cve>BOC-\d{4}-\d+)',
                      re.DOTALL)
RE_DISPOSICION = re.compile(r'<disposicion\b[^>]*numExpediente="(?P<cve>[^"]+)"[^>]*>(?P<d>.*?)</disposicion>', re.DOTALL)


def url_dia(d: date, extraordinario: bool = False) -> str:
    return (f"{BASE}/boletines.do?boton=Buscar&boletinBean.fecBolString={d:%d}/{d:%m}/{d:%Y}"
            f"&boletinBean.tipoBol={1 if extraordinario else 0}")


def url_extraordinario(numero: int, anio: int) -> str:
    return f"{BASE}/boletines.do?boton=Buscar&boletinBean.numBolString={numero}/{anio}&boletinBean.tipoBol=1"


def cabecera(html: str) -> tuple[int | None, str | None, bool]:
    m = RE_CABECERA.search(html)
    if not m:
        return None, None, False
    return int(m.group("n")), fecha_texto(m.group("d"), m.group("m"), m.group("a")), m.group("tipo") == "EXT"


def parsear_sumario(html: str) -> list[dict]:
    seccion = subseccion = organismo = titulo = None
    filas = []
    for t in RE_TOKEN.finditer(html):
        if t.group("sec") is not None:
            seccion, subseccion, organismo, titulo = texto_de(t.group("sec")), None, None, None
        elif t.group("sub") is not None:
            subseccion, organismo, titulo = texto_de(t.group("sub")), None, None
        elif t.group("org") is not None:
            organismo, titulo = texto_de(t.group("org")), None
        elif t.group("p") is not None:
            titulo = texto_de(t.group("p"))
        elif t.group("blob") and titulo and seccion:
            filas.append({"id": t.group("cve"), "cve": t.group("cve"), "seccion": seccion, "subseccion": subseccion,
                          "organismo": organismo, "titulo": titulo,
                          "url_pdf": f"{BASE}/verAnuncioAction.do?idAnuBlob={t.group('blob')}", "fuente": SIGLAS})
            titulo = None
    return filas


def es_empleo_publico(x: dict) -> bool:
    sec, sub, t = normalizar(x.get("seccion") or ""), normalizar(x.get("subseccion") or ""), x.get("titulo") or ""
    if sub.startswith("2.2."):
        return True
    if sub.startswith("2.1."):
        return es_resultado(t) or es_empleo_estricto(t)
    if sub.startswith("2.") or sec.startswith("7."):
        return es_empleo_estricto(t)
    return False


RE_LOCAL = re.compile(r"(?i)^(ayuntamiento|mancomunidad|junta vecinal|concejo|consorcio|entidad local)\b")


def ambito(x: dict) -> str:
    o = x.get("organismo") or ""
    if RE_LOCAL.match(o):
        return "local"
    if normalizar(o).startswith("universidad"):
        return "universidad"
    return "autonomico"


def convocante(x: dict) -> dict | None:
    c = convocante_de_organismo(x.get("organismo") or "")
    if c:
        c["provincia"] = "Cantabria"
    return c


def seleccionar(disposiciones: list[dict]) -> list[dict]:
    out = []
    for x in disposiciones:
        if not es_empleo_publico(x):
            continue
        amb = ambito(x)
        out.append({**x, "ambito": amb, **clasificar(x["titulo"], x.get("subseccion")),
                    "convocante": convocante(x) if amb == "local" else None})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "autonomicos" / FUENTE


def _ruta(raiz: Path, carpeta: str, fecha: str, sufijo: str = "", ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / fecha[:4] / fecha[5:7] / f"{fecha[8:10]}{sufijo}.{ext}"


def procesar(url: str, raiz: Path, archivo: Archivo, fecha_pedida: str | None = None) -> dict:
    r = obtener(url, accept="text/html")
    informe = {"url": url, "status": r.status, "alertas": [], **({"fecha": fecha_pedida} if fecha_pedida else {})}
    if r.status != 200:
        informe["resultado"] = "error_http"
        informe["alertas"].append(f"BOC Cantabria {url}: HTTP {r.status}")
        return informe
    html = r.contenido.decode("iso-8859-1", errors="replace")
    n, fecha, extra = cabecera(html)
    if n is None:
        informe["resultado"] = "sin_boletin" if RE_SIN_BOLETIN.search(html) else "error_formato"
        if informe["resultado"] == "error_formato":
            informe["alertas"].append(f"BOC Cantabria {url}: página sin cabecera de boletín (posible cambio de formato)")
        return informe
    if fecha_pedida and fecha != fecha_pedida:
        informe["resultado"] = "error_formato"
        informe["alertas"].append(f"BOC Cantabria: pedido el {fecha_pedida}, la página es del {fecha}")
        return informe
    sufijo = f"-ext{n:03d}" if extra else ""
    captura = archivo.guardar(FUENTE, date.fromisoformat(fecha), r.contenido, url, "html", r.status, r.cabeceras)
    xml = RE_XML.search(html)
    filas = [{**x, "fecha": fecha, "boletin": n, "extraordinario": extra,
              "url_xml": f"{BASE}/verXmlAction.do?idBlob={xml.group(1)}" if xml else None,
              "captura_sha256": captura["sha256"]} for x in parsear_sumario(html)]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", fecha, sufijo), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", fecha, sufijo), empleo)
    informe.update({"resultado": "ok", "fecha": fecha, "numero": n, "extraordinario": extra,
                    "sha256": captura["sha256"], "disposiciones": len(filas), "empleo_publico": len(empleo)})
    if not filas:
        informe["alertas"].append(f"BOC Cantabria {fecha} n.º {n}: boletín sin anuncios (posible cambio de formato)")
    return informe


def textos_del_xml(contenido: bytes) -> dict[str, dict]:
    """Texto limpio de cada anuncio del boletín completo en XML, por CVE («BOC-2026-8422»)."""
    xml = contenido.decode("utf-8", errors="replace")
    out = {}
    for m in RE_DISPOSICION.finditer(xml):
        d = m.group("d")
        titulo = re.search(r"<titulo_text>(.*?)</titulo_text>", d, re.DOTALL)
        texto = re.search(r"<texto>(.*?)</texto>", d, re.DOTALL)
        out["BOC-" + m.group("cve").strip()] = {"titulo": texto_de(titulo.group(1)) if titulo else None,
                                                **limpiar_html(texto.group(1) if texto else "")}
    return out


def ruta_texto(raiz: Path, x: dict) -> Path:
    return _base(raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"


def textos_pendientes(raiz: Path) -> list[dict]:
    lista = []
    for f in sorted((_base(raiz) / "oposiciones").glob("*/*/*.jsonl"), reverse=True):
        lista += [x for x in leer_jsonl(f) if x.get("url_xml") and not ruta_texto(raiz, x).exists()]
    return lista


def descargar_textos(raiz: Path, archivo: Archivo, max_minutos: float, pausa: float) -> tuple[int, int, int]:
    """Un XML por boletín para todos sus anuncios de empleo pendientes. Devuelve (hechos, errores, pendientes)."""
    por_xml: dict[str, list[dict]] = defaultdict(list)
    pend = textos_pendientes(raiz)
    for x in pend:
        por_xml[x["url_xml"]].append(x)
    inicio, hechos, errores = time.monotonic(), 0, 0
    for url, lista in por_xml.items():
        if max_minutos and (time.monotonic() - inicio) / 60 > max_minutos:
            break
        try:
            r = obtener(url, accept="application/xml")
        except ConnectionError:
            errores += 1
            continue
        if r.status != 200:
            errores += 1
            time.sleep(pausa)
            continue
        textos = textos_del_xml(r.contenido)
        captura = archivo.guardar(FUENTE + "-xml", date.fromisoformat(lista[0]["fecha"]), r.contenido, url, "xml",
                                  r.status, r.cabeceras)
        for x in lista:
            t = textos.get(x["id"])
            if t is None:
                errores += 1
                continue
            escribir_json(ruta_texto(raiz, x), {"id": x["id"], **t, "captura_sha256": captura["sha256"],
                                                "capturado": captura["capturado"], "url": url})
            hechos += 1
        time.sleep(pausa)
    return hechos, errores, len(pend) - hechos


def extraordinarios(raiz: Path, archivo: Archivo, anio: int, pausa: float, informes: list[dict]) -> None:
    """Los extraordinarios del año por su número, desde el último conocido hasta el primero que no existe."""
    estado = _base(raiz) / "boletines" / f"extraordinarios-{anio}.json"
    hechos = json.loads(estado.read_text(encoding="utf-8")) if estado.exists() else {"anio": anio, "ultimo": 0}
    n = hechos["ultimo"] + 1
    while True:
        try:
            inf = procesar(url_extraordinario(n, anio), raiz, archivo)
        except ConnectionError as e:
            informes.append({"resultado": "fuente_inaccesible", "alertas": [str(e)]})
            return
        informes.append(inf)
        if inf["resultado"] != "ok" or not inf.get("extraordinario") or inf.get("numero") != n:
            if inf["resultado"] == "ok":
                inf["alertas"].append(f"BOC Cantabria extraordinario {n}/{anio}: la página dice otro boletín")
            break
        hechos["ultimo"] = n
        escribir_json(_ruta(raiz, "dias", inf["fecha"], f"-ext{n:03d}", "json"), inf)
        print(f"BOC Cantabria extraordinario {n}/{anio} ({inf['fecha']}): {inf.get('empleo_publico')} de empleo")
        n += 1
        time.sleep(pausa)
    escribir_json(estado, hechos)


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
        hechos, errores, pendientes = descargar_textos(a.salida, archivo, a.max_minutos, a.pausa)
        print(f"BOC Cantabria textos: {hechos} descargados, {errores} errores, {pendientes} pendientes")
        return 0

    inicio, informes, freno = time.monotonic(), [], Freno()
    for anio in range(a.hasta.year, a.desde.year - 1, -1):
        extraordinarios(a.salida, archivo, anio, a.pausa, informes)
    d = a.hasta
    while d >= a.desde:  # ordinarios, del más reciente al más antiguo; lo hecho no se repite (salvo ayer y hoy)
        ruta = _ruta(a.salida, "dias", d.isoformat(), ext="json")
        hecho = ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") in {"ok", "sin_boletin"}
        if d.weekday() >= 5 and not hecho:  # los ordinarios salen de lunes a viernes
            escribir_json(ruta, {"fecha": d.isoformat(), "resultado": "sin_boletin", "nota": "fin de semana",
                                 "alertas": []})
            hecho = True
        if not hecho or (d >= hoy - timedelta(days=1) and d.weekday() < 5):
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                break
            try:
                inf = procesar(url_dia(d), a.salida, archivo, d.isoformat())
            except (ConnectionError, TimeoutError) as e:
                inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            if not (inf.get("resultado") == "sin_boletin" and d >= hoy):
                escribir_json(ruta, inf)
            informes.append(inf)
            if freno.anotar(inf):
                break
            print(f"BOC Cantabria {d}: {inf['resultado']} {inf.get('disposiciones', '')} anuncios, "
                  f"{inf.get('empleo_publico', '')} de empleo público")
            time.sleep(a.pausa)
        d -= timedelta(days=1)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Boletines procesados: {len(informes)}. Alertas: {len(alertas)}")
    for x in alertas[:30]:
        print(" -", x)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
