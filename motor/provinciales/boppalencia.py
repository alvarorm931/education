"""Conector del Boletín Oficial de la Provincia de Palencia: el sumario de la primera página del PDF de cada boletín.

Formato verificado el 30/10/2026 desde GitHub:
  - Lista de boletines: https://www.diputaciondepalencia.es/servicios/boletin-oficial-provincia (y ?page=N), con
    «BOP Nº 129 del Miércoles, 28 de Octubre de 2026» y el PDF del boletín entero
    (/system/files/bop/2026/20261028-bop-129-Ordinario.pdf). No hay sumario en HTML ni PDF por anuncio.
  - El PDF empieza por el sumario (una o dos páginas, cada una con la cabecera «Sumario»): grupo («ADMINISTRACIÓN
    PROVINCIAL:», «AYUNTAMIENTOS:»), entidad («DIPUTACIÓN PROVINCIAL DE PALENCIA», «Antigüedad.»), servicio
    («Servicio de Personal:») y cada anuncio con su página («Cuenta General ejercicio 2025 ........ 67»).
  - robots.txt cierra los PDF del BOP y la paginación de la lista; se leen como boletín oficial (motor/http.py,
    decisión del 30/10/2026).

Uso:
  python -m motor.provinciales.boppalencia --salida ruta/                       # la primera página de la lista
  python -m motor.provinciales.boppalencia --paginas 60 --max-minutos 30 --salida ruta/   # histórico
"""

from __future__ import annotations

import argparse
import html
import io
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (Freno, clasificar, convocante_de_organismo, es_empleo_estricto, escribir_json,
                                     escribir_jsonl)
from motor.boe.clasificar import normalizar
from motor.extraccion.texto_es import fecha_texto
from motor.http import obtener

FUENTE = "boppalencia"
SIGLAS = "BOP-PALENCIA"
WEB = "https://www.diputaciondepalencia.es"
LISTA = WEB + "/servicios/boletin-oficial-provincia"
NOMBRES = ("Boletín Oficial de la Provincia de Palencia",)

RE_FILA = re.compile(r'<h2 class="field-content titulo-vista"><a href="(?P<ficha>[^"]+)"[^>]*>\s*BOP N\S*\s*(?P<n>\d+)\s+'
                     r"del\s+\w+,\s*(?P<d>\d{1,2}) de (?P<m>\w+) de (?P<a>\d{4})\s*</a>.*?"
                     r'href="(?P<pdf>/system/files/bop/[^"]+\.pdf)"', re.DOTALL | re.IGNORECASE)
RE_PAGINA = re.compile(r"\.{2,}\s*(\d+)\s*$")
# Cabeceras y pies de página del PDF, entre las líneas del sumario
RE_RUIDO = re.compile(r"^(?:(?:lunes|martes|mi[ée]rcoles|jueves|viernes|s[áa]bado|domingo),? \d{1,2} de \w+ de \d{4}|"
                      r"N[úu]m\. ?\d+|\d*\s*BOP de Palencia|Firmado electr[óo]nicamente.*|https?://\S+|"
                      r"C[óo]digo de Verificaci[óo]n.*|C/ Burgos.*|Bolet[íi]n Oficial de la Provincia de Palencia|"
                      r"Administraci[óo]n:.*|Dep[óo]sito Legal.*|A[ñn]o [CLXVI]+|Se publica .*|Bolet[íi]n\s+Oficial|"
                      r"de la Provincia|de Palencia|Sumario|\d+)$", re.IGNORECASE)
GRUPOS_LOCALES = ("administracion provincial", "administracion municipal", "ayuntamientos", "entidades locales menores",
                  "mancomunidades", "otras entidades locales")


def boletines_lista(contenido: bytes) -> list[dict]:
    h = contenido.decode("utf-8", errors="replace")
    out = []
    for m in RE_FILA.finditer(h):
        extra = "extraordinario" in m.group("pdf").lower()
        out.append({"numero": int(m.group("n")), "fecha": fecha_texto(m.group("d"), m.group("m"), m.group("a")),
                    "extraordinario": extra, "url_ficha": WEB + html.unescape(m.group("ficha")),
                    "url_pdf": WEB + html.unescape(m.group("pdf"))})
    return out


def texto_sumario(pdf: bytes, paginas: int = 4) -> str:
    from pypdf import PdfReader
    if pdf[:4] != b"%PDF":
        raise ValueError("no es un PDF")
    r = PdfReader(io.BytesIO(pdf))
    partes = []
    for p in r.pages[:paginas]:  # las páginas del sumario son las que traen «…… 67» al final de las líneas
        t = p.extract_text() or ""
        if partes and not any(RE_PAGINA.search(l) for l in t.splitlines()):
            break
        partes.append(t)
    return "\n".join(partes)


def parsear_sumario(texto: str) -> list[dict]:
    """Anuncios del sumario: grupo, entidad, servicio, título y página."""
    grupo = entidad = servicio = None
    tras_entidad, buf, out = False, [], []
    for bruto in texto.splitlines():
        linea = " ".join(bruto.split())
        if not linea:
            continue
        if RE_RUIDO.match(linea):
            continue
        m = RE_PAGINA.search(linea)
        if buf or m:
            buf.append(linea)
            if m:
                titulo = RE_PAGINA.sub("", " ".join(buf)).rstrip(" .")
                out.append({"grupo": grupo, "entidad": entidad, "servicio": servicio, "titulo": titulo,
                            "pagina": int(m.group(1))})
                buf, tras_entidad = [], False
            continue
        if linea.endswith(":"):
            nombre = linea[:-1].strip()
            if nombre.isupper() and normalizar(nombre).startswith(("administracion", "ayuntamientos", "entidades",
                                                                    "anuncios", "otras", "mancomunidades")):
                grupo, entidad, servicio = nombre, None, None
            else:
                servicio = nombre
            tras_entidad = False
            continue
        if linea.isupper() and len(linea) < 120:
            entidad, servicio, tras_entidad = linea, None, True
            continue
        if linea.endswith(".") and len(linea) < 120:
            if tras_entidad and entidad:
                servicio = linea[:-1]  # «Palencia.» y debajo «Patronato Municipal de Deportes.»
            else:
                entidad, servicio, tras_entidad = linea[:-1], None, True
            continue
        buf.append(linea)  # primera línea de un título largo
    return out


def es_local(x: dict) -> bool:
    return normalizar(x.get("grupo") or "").startswith(GRUPOS_LOCALES)


def convocante(x: dict) -> dict | None:
    ent, g = x.get("entidad") or "", normalizar(x.get("grupo") or "")
    if g.startswith(("ayuntamientos", "administracion municipal")) and not normalizar(ent).startswith(
            ("ayuntamiento", "junta vecinal", "mancomunidad", "consorcio", "patronato")):
        ent = f"Ayuntamiento de {ent}"
    c = convocante_de_organismo(ent)
    if c and not c.get("provincia"):
        c["provincia"] = "Palencia"
    if c and x.get("servicio"):
        c["organismo"] = f"{c['organismo']} - {x['servicio']}"
    return c


def seleccionar(filas: list[dict]) -> list[dict]:
    out = []
    for x in filas:
        if not es_empleo_estricto(x["titulo"]):
            continue
        local = es_local(x)
        out.append({**x, "ambito": "local" if local else "otro", **clasificar(x["titulo"]),
                    "convocante": convocante(x) if local else None})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "provinciales" / FUENTE


def _ruta(raiz: Path, carpeta: str, b: dict, ext: str = "jsonl") -> Path:
    f, tipo = b["fecha"], "E" if b["extraordinario"] else ""
    return _base(raiz) / carpeta / f[:4] / f[5:7] / f"{f[8:10]}-{tipo}{b['numero']:03d}.{ext}"


def procesar_boletin(b: dict, raiz: Path, archivo: Archivo) -> dict:
    r = obtener(b["url_pdf"], accept="application/pdf", timeout=90)
    inf = {**b, "status": r.status, "alertas": []}
    if r.status != 200:
        inf["resultado"] = "error_http"
        inf["alertas"].append(f"BOP Palencia {b['numero']} {b['fecha']}: HTTP {r.status}")
        return inf
    try:
        anuncios = parsear_sumario(texto_sumario(r.contenido))
    except Exception as e:  # PDF dañado o ilegible
        inf["resultado"] = "error_formato"
        inf["alertas"].append(f"BOP Palencia {b['numero']} {b['fecha']}: {type(e).__name__}: {e}")
        return inf
    captura = archivo.guardar(FUENTE, date.fromisoformat(b["fecha"]), r.contenido, b["url_pdf"], "pdf", r.status,
                              r.cabeceras)
    tipo = "E" if b["extraordinario"] else ""
    filas = [{**x, "id": f"BOPPALENCIA-{b['fecha'][:4]}-{tipo}{b['numero']}-{x['pagina']:03d}-{i:02d}", "fecha": b["fecha"],
              "boletin": b["numero"], "url_pdf": b["url_pdf"], "fuente": SIGLAS, "captura_sha256": captura["sha256"]}
             for i, x in enumerate(anuncios, 1)]
    empleo = seleccionar(filas)
    escribir_jsonl(_ruta(raiz, "disposiciones", b), filas)
    escribir_jsonl(_ruta(raiz, "oposiciones", b), empleo)
    inf.update({"resultado": "ok", "sha256": captura["sha256"], "disposiciones": len(filas), "empleo_publico": len(empleo)})
    if not filas:
        inf["alertas"].append(f"BOP Palencia {b['numero']} {b['fecha']}: sumario sin anuncios (posible cambio de formato)")
    return inf


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--paginas", type=int, default=1, help="páginas de la lista que se recorren (10 boletines cada una)")
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    inicio, informes, freno = time.monotonic(), [], Freno()
    estado_ruta = _base(a.salida) / "estado.json"
    estado = json.loads(estado_ruta.read_text(encoding="utf-8")) if estado_ruta.exists() else {}
    for pagina in range(a.paginas):
        if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
            print("Tiempo agotado; se continúa en la siguiente ejecución")
            break
        if pagina and estado.get("historico_completo"):
            break
        url = LISTA if pagina == 0 else f"{LISTA}?page={pagina}"
        try:
            r = obtener(url, accept="text/html")
            lista = boletines_lista(r.contenido) if r.status == 200 else []
        except (ConnectionError, TimeoutError) as e:
            print(f"BOP Palencia: lista inaccesible ({e})")
            return 1
        time.sleep(a.pausa)
        if not lista:
            if pagina:
                estado["historico_completo"] = True  # se ha pasado la última página
            else:
                print("::warning::BOP Palencia: la lista no trae boletines (posible cambio de formato)")
            break
        for b in lista:
            ruta = _ruta(a.salida, "boletines", b, "json")
            if ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") == "ok":
                continue
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                break
            try:
                inf = procesar_boletin(b, a.salida, archivo)
            except (ConnectionError, TimeoutError) as e:
                inf = {**b, "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            escribir_json(ruta, inf)
            informes.append(inf)
            print(f"BOP Palencia {b['numero']} {b['fecha']}: {inf['resultado']} {inf.get('disposiciones', '')} anuncios, "
                  f"{inf.get('empleo_publico', '')} de empleo")
            time.sleep(a.pausa)
            if freno.anotar(inf):
                return 1
        if lista and min(x["fecha"] for x in lista) < "2022-01-01":
            estado["historico_completo"] = True
            break
    escribir_json(estado_ruta, estado)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Boletines procesados: {len(informes)}. Alertas: {len(alertas)}")
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
