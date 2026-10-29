"""Conector del Boletín Oficial de Castilla y León (BOCYL) por su conjunto de datos abiertos (CC BY 4.0 ES).

Formato verificado el 29/10/2026 desde GitHub:
  - API Opendatasoft de la Junta de Castilla y León:
      https://analisis.datosabiertos.jcyl.es/api/explore/v2.1/catalog/datasets/bocyl
    Una fila por disposición desde el 2 de enero de 2020 (unas 10.000 al año): edición («209/2026»), fecha,
    sección, subsección, apartado, organismo, rango, número oficial, título, páginas y enlaces a PDF, XML y HTML.
    Se actualiza cada mañana con el boletín del día anterior.
  - exports/json?where=... devuelve en una sola petición todas las filas de un mes (unas 800).
  - Cada disposición en XML (ISO-8859-15): disposicion > metadatos, contenido > titulo, texto (párrafos y tablas).
  - Empleo público: apartado «B.2. Oposiciones y Concursos» en la sección I (Comunidad) y en la III
    (Administración local). Los resultados (nombramientos de quienes superan un proceso) van en «B.1».
    Las entidades locales vienen como «AYUNTAMIENTO DE MIRANDA DE EBRO (BURGOS)»; las capitales, sin provincia.

Uso:
  python -m motor.autonomicos.bocyl --salida ruta/                                  # mes en curso y anterior
  python -m motor.autonomicos.bocyl --desde 2022-01 --saltar-existentes --salida ruta/
  python -m motor.autonomicos.bocyl --textos --max-minutos 20 --salida ruta/        # textos pendientes

Guarda en datos/autonomicos/bocyl/: meses/ (informe por mes), disposiciones/ (todas, sin texto),
oposiciones/ (selección de empleo público) y textos/ (texto limpio de datos personales).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (clasificar, convocante_de_organismo, descargar_textos, es_empleo_por_titulo,
                                     es_resultado, escribir_json, escribir_jsonl, leer_jsonl)
from motor.boe.clasificar import normalizar
from motor.http import obtener
from motor.limpieza import limpiar_html

FUENTE = "bocyl"
MADRID = ZoneInfo("Europe/Madrid")
API = "https://analisis.datosabiertos.jcyl.es/api/explore/v2.1/catalog/datasets/bocyl"
LICENCIA = "CC BY 4.0 ES - Junta de Castilla y León"
CAPITALES = ("Ávila", "Burgos", "León", "Palencia", "Salamanca", "Segovia", "Soria", "Valladolid", "Zamora")
RE_EDICION = re.compile(r"(\d+)\s*/\s*(\d{4})")


def url_mes(anio: int, mes: int) -> str:
    inicio = date(anio, mes, 1)
    fin = date(anio + (mes == 12), mes % 12 + 1, 1)
    where = f"fecha_publicacion>=date'{inicio}' and fecha_publicacion<date'{fin}'"
    return f"{API}/exports/json?where={quote(where)}&order_by={quote('fecha_publicacion,pagina_inicial')}"


def _https(url: str | None) -> str | None:
    return url.replace("http://bocyl.jcyl.es/", "https://bocyl.jcyl.es/") if url else None


def identificador(fila: dict) -> str | None:
    for campo in ("enlace_fichero_xml", "enlace_fichero_pdf", "enlace_fichero_html"):
        u = fila.get(campo)
        if u:
            return re.sub(r"\.(xml|pdf|do)$", "", u.rsplit("/", 1)[-1])
    return None


def ambito(fila: dict) -> str:
    s = normalizar(fila.get("seccion") or "")
    o = normalizar(fila.get("organismo") or "")
    if s.startswith("iii"):
        return "local"
    if re.match(r"universidad\b", o):
        return "universidad"
    if s.startswith("ii."):
        return "estatal"
    if s.startswith("i."):
        return "autonomico"
    return "otro"


def es_empleo_publico(fila: dict) -> bool:
    apartado = normalizar(fila.get("apartado") or "")
    if apartado.startswith("b.2"):
        return True
    if apartado.startswith("b.1"):
        return es_resultado(fila.get("titulo") or "")
    if normalizar(fila.get("seccion") or "").startswith("iii"):
        return es_empleo_por_titulo(fila.get("titulo") or "")
    return False


def fila_a_disposicion(fila: dict) -> dict:
    m = RE_EDICION.search(fila.get("no_edicion") or "")
    return {
        "id": identificador(fila),
        "fecha": fila.get("fecha_publicacion"),
        "boletin": fila.get("no_edicion"),
        "boletin_numero": int(m.group(1)) if m else None,
        "seccion": fila.get("seccion"),
        "subseccion": fila.get("subseccion"),
        "apartado": fila.get("apartado"),
        "organismo": fila.get("organismo"),
        "suborganismo": fila.get("suborganismo"),
        "rango": fila.get("rango"),
        "numero_oficial": fila.get("no_oficial"),
        "fecha_disposicion": fila.get("fecha_disposicion"),
        "titulo": " ".join((fila.get("titulo") or "").split()),
        "paginas": [fila.get("pagina_inicial"), fila.get("pagina_final")],
        "url_html": _https(fila.get("enlace_fichero_html")),
        "url_xml": _https(fila.get("enlace_fichero_xml")),
        "url_pdf": _https(fila.get("enlace_fichero_pdf")),
        "fuente": "BOCYL",
    }


def seleccionar(disposiciones: list[dict]) -> list[dict]:
    empleo = []
    for x in disposiciones:
        fila = {"seccion": x["seccion"], "apartado": x["apartado"], "organismo": x["organismo"], "titulo": x["titulo"]}
        if not es_empleo_publico(fila):
            continue
        amb = ambito(fila)
        empleo.append({**x, "ambito": amb, **clasificar(x["titulo"], x["apartado"]),
                       "convocante": convocante_de_organismo(x["organismo"], CAPITALES) if amb == "local" else None})
    return empleo


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "autonomicos" / FUENTE


def control_ediciones(disposiciones: list[dict]) -> dict:
    """Números de edición presentes por año y saltos dentro del mes (posibles boletines no recogidos)."""
    por_anio: dict[str, set[int]] = {}
    for x in disposiciones:
        m = RE_EDICION.search(x.get("boletin") or "")
        if m:
            por_anio.setdefault(m.group(2), set()).add(int(m.group(1)))
    saltos = {}
    for anio, nums in por_anio.items():
        faltan = sorted(set(range(min(nums), max(nums) + 1)) - nums)
        if faltan:
            saltos[anio] = faltan
    return {"ediciones": {a: [min(n), max(n), len(n)] for a, n in por_anio.items()}, "saltos": saltos}


def procesar_mes(anio: int, mes: int, raiz: Path, archivo: Archivo, hoy: date) -> dict:
    url = url_mes(anio, mes)
    resp = obtener(url, accept="application/json")
    informe = {"mes": f"{anio}-{mes:02d}", "status": resp.status, "alertas": []}
    if resp.status != 200:
        informe["resultado"] = "error_http"
        informe["alertas"].append(f"BOCYL {anio}-{mes:02d}: HTTP {resp.status}")
        return informe
    try:
        filas = json.loads(resp.contenido)
        assert isinstance(filas, list)
    except (ValueError, AssertionError):
        informe["resultado"] = "error_formato"
        informe["alertas"].append(f"BOCYL {anio}-{mes:02d}: respuesta que no es una lista JSON")
        return informe
    faltan_campos = {"fecha_publicacion", "titulo", "apartado", "enlace_fichero_xml"} - set(filas[0]) if filas else set()
    if faltan_campos:
        informe["resultado"] = "error_formato"
        informe["alertas"].append(f"BOCYL {anio}-{mes:02d}: faltan campos {sorted(faltan_campos)} (cambio de formato)")
        return informe

    captura = archivo.guardar(FUENTE, date(anio, mes, 1), resp.contenido, url, "json", resp.status, resp.cabeceras)
    disposiciones = [fila_a_disposicion(f) | {"captura_sha256": captura["sha256"]} for f in filas]
    empleo = seleccionar(disposiciones)
    escribir_jsonl(_base(raiz) / "disposiciones" / f"{anio}" / f"{mes:02d}.jsonl", disposiciones)
    escribir_jsonl(_base(raiz) / "oposiciones" / f"{anio}" / f"{mes:02d}.jsonl", empleo)

    fin_mes = date(anio + (mes == 12), mes % 12 + 1, 1) - timedelta(days=1)
    dias = Counter(x["fecha"] for x in disposiciones)
    laborables_sin = [d.isoformat() for d in (date(anio, mes, 1) + timedelta(days=i) for i in range(fin_mes.day))
                      if d.weekday() < 5 and d < hoy - timedelta(days=1) and d.isoformat() not in dias]
    control = control_ediciones(disposiciones)
    informe.update({
        "resultado": "ok", "sha256": captura["sha256"], "disposiciones": len(disposiciones),
        "empleo_publico": len(empleo), "dias_con_boletin": len(dias), "ultimo_dia": max(dias) if dias else None,
        "laborables_sin_boletin": laborables_sin, **control,
        # El conjunto de datos se actualiza con un día de retraso: el mes solo se da por cerrado pasada una semana.
        "completo": fin_mes < hoy - timedelta(days=7),
    })
    if control["saltos"]:
        informe["alertas"].append(f"BOCYL {anio}-{mes:02d}: faltan ediciones {control['saltos']}")
    if not disposiciones and fin_mes < hoy:
        informe["alertas"].append(f"BOCYL {anio}-{mes:02d}: mes sin disposiciones (posible cambio de formato)")
    return informe


def texto_disposicion(xml: bytes) -> dict:
    raiz = ET.fromstring(xml)
    texto = raiz.find("contenido/texto")
    if texto is None:
        raise ValueError("falta contenido/texto: posible cambio de formato")
    limpio = limpiar_html(ET.tostring(texto, encoding="unicode"))
    return {"titulo": " ".join((raiz.findtext("contenido/titulo") or "").split()),
            "organismo": raiz.findtext("organismo"), "numero_oficial": raiz.findtext("numeroOficial"), **limpio}


def ruta_texto(raiz: Path, x: dict) -> Path:
    return _base(raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"


def textos_pendientes(raiz: Path) -> list[dict]:
    lista = []
    for f in sorted((_base(raiz) / "oposiciones").glob("*/*.jsonl"), reverse=True):
        lista += [x for x in sorted(leer_jsonl(f), key=lambda x: x["fecha"], reverse=True)
                  if x.get("url_xml") and x.get("id") and not ruta_texto(raiz, x).exists()]
    # Primero lo de acceso abierto; dentro, de lo más reciente a lo más antiguo
    return sorted(lista, key=lambda x: 0 if x.get("alcance") in (None, "acceso") else 1)


def meses(desde: date, hasta: date) -> list[tuple[int, int]]:
    out, a, m = [], desde.year, desde.month
    while (a, m) <= (hasta.year, hasta.month):
        out.append((a, m))
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return out


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=lambda s: date.fromisoformat(s + "-01"), default=(hoy.replace(day=1) - timedelta(days=1)).replace(day=1),
                   help="mes inicial AAAA-MM (por defecto, el anterior)")
    p.add_argument("--hasta", type=lambda s: date.fromisoformat(s + "-01"), default=hoy.replace(day=1))
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--saltar-existentes", action="store_true", help="no repetir meses ya cerrados")
    p.add_argument("--textos", action="store_true", help="descargar los textos pendientes")
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=0.7)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())

    if a.textos:
        pend = textos_pendientes(a.salida)
        hechos, errores = descargar_textos(pend, lambda x: ruta_texto(a.salida, x), lambda x: x["url_xml"],
                                           texto_disposicion, archivo, FUENTE, a.max_minutos, a.pausa)
        print(f"BOCYL textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        return 0

    inicio, informes = time.monotonic(), []
    for anio, mes in meses(a.desde, a.hasta):
        if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
            print("Tiempo agotado; se continúa en la siguiente ejecución")
            break
        ruta = _base(a.salida) / "meses" / f"{anio}" / f"{mes:02d}.json"
        if a.saltar_existentes and ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("completo"):
            continue
        try:
            inf = procesar_mes(anio, mes, a.salida, archivo, hoy)
        except ConnectionError as e:
            inf = {"mes": f"{anio}-{mes:02d}", "resultado": "fuente_inaccesible", "alertas": [str(e)]}
        escribir_json(ruta, inf)
        informes.append(inf)
        print(f"BOCYL {anio}-{mes:02d}: {inf.get('resultado')} {inf.get('disposiciones', '')} disposiciones, "
              f"{inf.get('empleo_publico', '')} de empleo público, último día {inf.get('ultimo_dia')}")
        time.sleep(a.pausa)

    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Meses procesados: {len(informes)}. Alertas: {len(alertas)}")
    for x in alertas[:30]:
        print(" -", x)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
