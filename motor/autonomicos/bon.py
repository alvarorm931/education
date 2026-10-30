"""Conector del Boletín Oficial de Navarra (BON).

Formato verificado el 30/10/2026 desde el servidor de España (desde GitHub no responde):
  - Boletín: https://bon.navarra.es/es/boletin/-/sumario/AAAA/N  (N correlativo en el año; los extraordinarios
    comparten numeración). Cabecera «BOLETÍN Nº 217 - 29 de octubre de 2026 - EXTRAORDINARIO». Si el número no
    existe: «No se han encontrado resultados».
  - La portada https://bon.navarra.es/es/ trae el último boletín con el mismo sumario.
  - Sumario: ámbito (p.b-ambito «1. Comunidad Foral de Navarra», «2. Administración Local de Navarra»), sección
    (p.b-seccion «1.2. Autoridades y Personal», «2.1. Oposiciones y concursos. Oferta Pública de Empleo»),
    subsección (p.b-subseccion «1.2.2. Oposiciones y concursos. Oferta Pública de Empleo») y, en lo local, la
    entidad (p.b-denominacion «HUARTE»). Cada anuncio enlaza a /es/anuncio/-/texto/AAAA/N/K, con su texto en HTML.
  - robots.txt permite el sumario y los anuncios en esas direcciones (prohíbe /texto/ en la raíz y las búsquedas
    con «?»).
  - Empleo público: «Oposiciones y concursos» (autonómico y local), todo; «Ceses, nombramientos y otras
    situaciones», solo los nombramientos de procesos selectivos; el resto, por el título (filtro estricto).

Uso:
  python -m motor.autonomicos.bon --salida ruta/                                  # año en curso, lo que falte
  python -m motor.autonomicos.bon --desde-anio 2022 --max-minutos 20 --salida ruta/
  python -m motor.autonomicos.bon --textos --max-minutos 20 --salida ruta/

Guarda en datos/autonomicos/bon/: boletines/ (informe por boletín), disposiciones/, oposiciones/ y textos/.
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
from motor.autonomicos.comun import (Freno, clasificar, convocante_de_organismo, descargar_textos, es_empleo_estricto,
                                     es_resultado, escribir_json, escribir_jsonl, leer_jsonl)
from motor.boe.clasificar import normalizar
from motor.extraccion.texto_es import fecha_texto
from motor.http import obtener
from motor.limpieza import limpiar_html, texto_de

FUENTE = "bon"
SIGLAS = "BON"
MADRID = ZoneInfo("Europe/Madrid")
BASE = "https://bon.navarra.es"
PORTADA = BASE + "/es/"
NOMBRES = ("Boletín Oficial de Navarra",)

RE_CABECERA = re.compile(r'id="numero_boletin"[^>]*>\s*BOLET[IÍ]N\s+N[ºo°]\s*(?P<n>\d+)\s*-\s*(?P<d>\d{1,2}) de '
                         r'(?P<m>\w+) de (?P<a>\d{4})(?P<extra>\s*-\s*EXTRAORDINARIO)?', re.IGNORECASE)
RE_TOKEN = re.compile(
    r'<p class="hd r-hn\d b-(?P<nivel>ambito|seccion|subseccion|denominacion)">\s*(?P<v>.*?)\s*</p>'
    r'|<a href="(?P<url>https://bon\.navarra\.es/es/anuncio/-/texto/(?P<a>\d{4})/(?P<n>\d+)/(?P<k>\d+))"[^>]*>'
    r'(?P<tit>.*?)</a>', re.DOTALL)
RE_SIN_BOLETIN = re.compile(r"No se han encontrado resultados")
# Entidades locales de Navarra que no son ayuntamiento: el BON da solo su nombre («CONCEJO DE LARUNBE»)
RE_ENTIDAD = re.compile(r"(?i)^(concejo|mancomunidad|consorcio|agrupaci[oó]n|junta|comunidad|sociedad|organismo|"
                        r"fundaci[oó]n|entidad|servicios?|federaci[oó]n|parlamento|c[aá]mara|universidad)\b")


def url_boletin(anio: int, numero: int) -> str:
    return f"{BASE}/es/boletin/-/sumario/{anio}/{numero}"


def cabecera(html: str) -> tuple[int | None, str | None, bool]:
    m = RE_CABECERA.search(html)
    if not m:
        return None, None, False
    return int(m.group("n")), fecha_texto(m.group("d"), m.group("m"), m.group("a")), bool(m.group("extra"))


def parsear_boletin(html: str) -> list[dict]:
    ambito_bon = seccion = subseccion = entidad = None
    filas = []
    for t in RE_TOKEN.finditer(html):
        if t.group("nivel"):
            v = texto_de(t.group("v"))
            if t.group("nivel") == "ambito":
                ambito_bon, seccion, subseccion, entidad = v, None, None, None
            elif t.group("nivel") == "seccion":
                seccion, subseccion, entidad = v, None, None
            elif t.group("nivel") == "subseccion":
                subseccion, entidad = v, None
            else:
                entidad = v
        elif ambito_bon:  # los enlaces a anuncios de fuera del sumario (columna lateral) no cuentan
            filas.append({"id": f"BON-{t.group('a')}-{int(t.group('n')):03d}-{int(t.group('k')):03d}",
                          "orden": int(t.group("k")), "ambito_bon": ambito_bon, "seccion": seccion,
                          "subseccion": subseccion, "entidad": entidad, "titulo": texto_de(t.group("tit")),
                          "url_html": t.group("url"), "fuente": SIGLAS})
    return filas


def es_local(x: dict) -> bool:
    return normalizar(x.get("ambito_bon") or "").startswith("2.")


def es_empleo_publico(x: dict) -> bool:
    apartado = normalizar(" ".join(filter(None, (x.get("seccion"), x.get("subseccion")))))
    a, t = normalizar(x.get("ambito_bon") or ""), x.get("titulo") or ""
    if not a.startswith(("1.", "2.")):
        return False
    if "oposiciones y concursos" in apartado:
        return True
    if "nombramientos" in apartado:
        return es_resultado(t) or es_empleo_estricto(t)
    return es_empleo_estricto(t)


def ambito(x: dict) -> str:
    if es_local(x):
        return "local"
    t = normalizar(x.get("titulo") or "")
    if "universidad publica de navarra" in t and ("rector" in t or "upna" in t):
        return "universidad"
    return "autonomico"


def convocante(x: dict) -> dict | None:
    ent = x.get("entidad")
    if not ent:
        return None
    c = convocante_de_organismo(ent if RE_ENTIDAD.match(ent) else f"AYUNTAMIENTO DE {ent}")
    if c:
        c["provincia"] = "Navarra"
        c["organismo"] = ent
    return c


def seleccionar(disposiciones: list[dict]) -> list[dict]:
    out = []
    for x in disposiciones:
        if not es_empleo_publico(x):
            continue
        amb = ambito(x)
        out.append({**x, "ambito": amb, **clasificar(x["titulo"], x.get("subseccion") or x.get("seccion")),
                    "convocante": convocante(x) if amb == "local" else None})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "autonomicos" / FUENTE


def ruta_informe(raiz: Path, anio: int, numero: int) -> Path:
    return _base(raiz) / "boletines" / str(anio) / f"{numero:03d}.json"


def _ruta_datos(raiz: Path, carpeta: str, fecha: str, numero: int) -> Path:
    return _base(raiz) / carpeta / fecha[:4] / fecha[5:7] / f"{fecha[8:10]}-{numero:03d}.jsonl"


def procesar_boletin(anio: int, numero: int, raiz: Path, archivo: Archivo, contenido: bytes | None = None,
                     cabeceras: dict | None = None) -> dict:
    url = url_boletin(anio, numero)
    status = 200
    if contenido is None:
        r = obtener(url, accept="text/html")
        status, contenido, cabeceras = r.status, r.contenido, r.cabeceras
    informe = {"anio": anio, "numero": numero, "status": status, "alertas": []}
    if status != 200:
        informe["resultado"] = "error_http"
        informe["alertas"].append(f"BON {anio}/{numero}: HTTP {status}")
        return informe
    html = contenido.decode("utf-8", errors="replace")
    n, fecha, extra = cabecera(html)
    if n is None and RE_SIN_BOLETIN.search(html):
        informe["resultado"] = "sin_boletin"
        return informe
    if n != numero or not fecha or fecha[:4] != str(anio):
        informe["resultado"] = "error_formato"
        informe["alertas"].append(f"BON {anio}/{numero}: la cabecera dice número {n} y fecha {fecha}")
        return informe
    captura = archivo.guardar(FUENTE, date.fromisoformat(fecha), contenido, url, "html", status, cabeceras)
    filas = [{**f, "fecha": fecha, "boletin": numero, "extraordinario": extra, "captura_sha256": captura["sha256"]}
             for f in parsear_boletin(html)]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta_datos(raiz, "disposiciones", fecha, numero), filas)
    escribir_jsonl(_ruta_datos(raiz, "oposiciones", fecha, numero), empleo)
    informe.update({"resultado": "ok", "fecha": fecha, "extraordinario": extra, "sha256": captura["sha256"],
                    "disposiciones": len(filas), "empleo_publico": len(empleo)})
    if not filas:
        informe["alertas"].append(f"BON {anio}/{numero}: boletín sin anuncios (posible cambio de formato)")
    return informe


def texto_disposicion(contenido: bytes) -> dict:
    html = contenido.decode("utf-8", errors="replace")
    titulo = re.search(r'<p class="r-hn3 a-titulo">(.*?)</(?:p|h)>', html, re.DOTALL)
    i = html.find('<p class="contenido">')
    if i < 0:
        raise ValueError("sin contenido: posible cambio de formato")
    fin = html.find("Código del anuncio", i)
    codigo = re.search(r"Código del anuncio:\s*([A-Z]?\d+)", html)
    return {"titulo": texto_de(titulo.group(1)) if titulo else None, "codigo_anuncio": codigo.group(1) if codigo else None,
            **limpiar_html(html[i:fin if fin > 0 else None])}


def ruta_texto(raiz: Path, x: dict) -> Path:
    return _base(raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"


def textos_pendientes(raiz: Path) -> list[dict]:
    lista = []
    for f in sorted((_base(raiz) / "oposiciones").glob("*/*/*.jsonl"), reverse=True):
        lista += [x for x in leer_jsonl(f) if x.get("url_html") and not ruta_texto(raiz, x).exists()]
    return sorted(lista, key=lambda x: 0 if x.get("alcance") in (None, "acceso") else 1)


def _hecho(raiz: Path, anio: int, numero: int) -> bool:
    ruta = ruta_informe(raiz, anio, numero)
    return ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") == "ok"


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde-anio", type=int, default=hoy.year)
    p.add_argument("--hasta-anio", type=int, default=hoy.year)
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
        print(f"BON textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        return 0

    inicio, informes, freno = time.monotonic(), [], Freno()
    ultimo = None
    if a.hasta_anio == hoy.year:
        try:
            r = obtener(PORTADA, accept="text/html")
            n, fecha, _ = cabecera(r.contenido.decode("utf-8", errors="replace")) if r.status == 200 else (None, None, 0)
            if n and fecha and fecha[:4] == str(hoy.year):
                ultimo = n
                if not _hecho(a.salida, hoy.year, n):  # la portada es el último boletín: no se pide dos veces
                    inf = procesar_boletin(hoy.year, n, a.salida, archivo, r.contenido, r.cabeceras)
                    escribir_json(ruta_informe(a.salida, hoy.year, n), inf)
                    informes.append(inf)
            else:
                informes.append({"resultado": "error_formato", "alertas": ["BON portada sin número de boletín"]})
        except ConnectionError as e:
            informes.append({"resultado": "fuente_inaccesible", "alertas": [str(e)]})
            return _final(informes)
        time.sleep(a.pausa)
    for anio in range(a.hasta_anio, a.desde_anio - 1, -1):  # lo más reciente primero
        fin = _base(a.salida) / "boletines" / str(anio) / "fin.json"
        if anio == hoy.year and ultimo:
            tope = ultimo
        elif fin.exists():
            tope = json.loads(fin.read_text(encoding="utf-8"))["ultimo"]
        else:
            tope = 400
        sin, numero = 0, 1
        while numero <= tope:
            if _hecho(a.salida, anio, numero):
                sin, numero = 0, numero + 1
                continue
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                return _final(informes)
            try:
                inf = procesar_boletin(anio, numero, a.salida, archivo)
            except ConnectionError as e:
                inf = {"anio": anio, "numero": numero, "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            informes.append(inf)
            if inf["resultado"] == "sin_boletin":
                sin += 1
                if sin >= 3:  # fin del año: tres números seguidos que no existen
                    if anio < hoy.year:
                        escribir_json(fin, {"anio": anio, "ultimo": numero - 3})
                    break
            else:
                sin = 0
                escribir_json(ruta_informe(a.salida, anio, numero), inf)
            if freno.anotar(inf):
                return _final(informes)
            print(f"BON {anio}/{numero} {inf.get('fecha', '')}: {inf['resultado']} {inf.get('disposiciones', '')} "
                  f"anuncios, {inf.get('empleo_publico', '')} de empleo público")
            numero += 1
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
