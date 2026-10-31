"""Conector del Boletín Oficial de la Comunidad de Madrid (BOCM).

Formato verificado el 30/10/2026 desde GitHub:
  - El robots.txt del BOCM prohíbe a los programas el sumario en XML (/boletin/CM_Boletin_BOCM/) y permite el
    boletín completo en HTML: https://www.bocm.es/boletin-completo/BOCM-AAAAMMDD/N (N, número del boletín,
    correlativo en el año; los extraordinarios llevan su propio número y su propia página, p. ej. el 259 del
    28/10/2026 junto al 258). Cada disposición: sección y apartado (h3 «Sección: I. COMUNIDAD DE MADRID |
    B) Autoridades y Personal»), organismo (h4) y un article con su número, su título y los enlaces a su XML y su
    PDF (/boletin/CM_Orden_BOCM/AAAA/MM/DD/BOCM-AAAAMMDD-K.xml, permitidos).
  - Como N no se sabe de antemano, se parte del último boletín leído y se prueba N+1, N+2 y N+3. Si sale un número
    con salto, los que faltan (extraordinarios) se buscan en ese día y en los anteriores hasta el último leído.
  - Cada disposición en XML: documento > metadatos(titulo, seccion, paginas) + texto (texto plano).
  - Madrid es comunidad de una sola provincia: lo local (ayuntamientos) se publica aquí, sección III, con títulos
    del tipo «Alcobendas. Ofertas de empleo. Proceso selectivo».

Uso:
  python -m motor.autonomicos.bocm --salida ruta/                       # ayer y hoy
  python -m motor.autonomicos.bocm --desde 2022-01-01 --saltar-existentes --max-minutos 30 --salida ruta/
  python -m motor.autonomicos.bocm --textos --max-minutos 30 --salida ruta/   # textos pendientes
  python -m motor.autonomicos.bocm --huecos --salida ruta/              # números que faltan en lo ya leído

Guarda en datos/autonomicos/bocm/: dias/ (informe por día; DD-N.json para un segundo boletín del mismo día),
disposiciones/ (todas, sin texto), oposiciones/ (selección de empleo público) y textos/ (texto limpio de datos
personales).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import html as html_mod
import re
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import Freno
from motor.boe.clasificar import REGLAS_ACTO, REGLAS_MODALIDAD, _primera, alcance, normalizar
from motor.http import obtener
from motor.limpieza import parrafos_seguros

FUENTE = "bocm"
MADRID = ZoneInfo("Europe/Madrid")
WEB = "https://www.bocm.es"
RE_SECCION = re.compile(r"<h3>\s*Secci[oó]n:\s*<strong>(?P<sec>[^<]+)</strong>\s*(?:\|\s*(?P<apa>[^<]+?))?\s*</h3>")
RE_ORGANISMO = re.compile(r"<h4>\s*(?P<org>[^<]+?)\s*</h4>")
RE_ARTICULO = re.compile(r'<article id="node-\d+" class="node node-orden[^"]*"[^>]*about="/(?P<id>bocm-(?P<f>\d{8})-(?P<k>\d+))"')
RE_DESCRIPCION = re.compile(r'field-name-field-short-description.*?<div class="field-item even">(?P<t>.*?)</div>', re.S)
RE_XML_ORDEN = re.compile(r'href="(?P<u>(?:https://www\.bocm\.es)?/boletin/CM_Orden_BOCM/[^"]+\.xml)"', re.I)
RE_PDF_ORDEN = re.compile(r'href="(?P<u>https://www\.bocm\.es/boletin/CM_Orden_BOCM/[^"]+\.PDF)"', re.I)
RE_NUMERO_PAGINA = re.compile(r"<title>\s*BOCM - N[ºo°] (?P<n>\d+)")
MATERIAS_EMPLEO = ("ofertas de empleo", "personal", "oposiciones", "empleo publico")


def url_completo(d: date, n: int) -> str:
    return f"{WEB}/boletin-completo/BOCM-{d:%Y%m%d}/{n}"


def _texto_html(s: str) -> str:
    s = re.sub(r"<br\s*/?>", " ", s)
    return " ".join(html_mod.unescape(re.sub(r"<[^>]+>", " ", s)).replace("–", " ").split())


def parsear_completo(contenido: bytes) -> dict:
    """Boletín completo en HTML -> mismo resultado que parsear_sumario() con el XML."""
    h = contenido.decode("utf-8", errors="replace")
    num = RE_NUMERO_PAGINA.search(h)
    marcas = sorted([(m.start(), "sec", m) for m in RE_SECCION.finditer(h)] +
                    [(m.start(), "org", m) for m in RE_ORGANISMO.finditer(h)] +
                    [(m.start(), "art", m) for m in RE_ARTICULO.finditer(h)], key=lambda x: x[0])
    seccion = apartado = organismo = None
    disposiciones, fechas = [], set()
    for i, (pos, tipo, m) in enumerate(marcas):
        if tipo == "sec":
            seccion, apartado, organismo = " ".join(m.group("sec").split()), (m.group("apa") or None), None
            apartado = " ".join(apartado.split()) if apartado else None
        elif tipo == "org":
            organismo = " ".join(html_mod.unescape(m.group("org")).split())
        else:
            fin = marcas[i + 1][0] if i + 1 < len(marcas) else len(h)
            bloque = h[pos:fin]
            desc = RE_DESCRIPCION.search(bloque)
            xml = RE_XML_ORDEN.search(bloque)
            pdf = RE_PDF_ORDEN.search(bloque)
            f = m.group("f")
            fechas.add(f"{f[:4]}-{f[4:6]}-{f[6:]}")
            titulo = _texto_html(desc.group("t")) if desc else ""
            org = organismo
            if org is None and "LOCAL" in (seccion or "").upper():
                # en la sección de ayuntamientos el organismo es el municipio, primera parte del título (como en el XML)
                org = (municipio_y_materia(titulo)[0] or "").upper() or None
            disposiciones.append({
                "id": m.group("id").upper(), "numero_disposicion": m.group("k"), "titulo": titulo,
                "seccion": seccion, "apartado": apartado, "organismo": org,
                "url_html": f"{WEB}/{m.group('id')}",
                "url_xml": (WEB + xml.group("u") if xml.group("u").startswith("/") else xml.group("u")) if xml else None,
                "url_pdf": pdf.group("u") if pdf else None,
            })
    return {"numero": num.group("n") if num else None,
            "fecha": fechas.pop() if len(fechas) == 1 else (None if not fechas else "varias"),
            "disposiciones": disposiciones}


def _t(nodo: ET.Element | None, etiqueta: str) -> str | None:
    if nodo is None:
        return None
    x = nodo.findtext(etiqueta)
    return " ".join(x.split()) if x else None


def es_empleo_publico(d: dict) -> bool:
    seccion = normalizar(d.get("seccion") or "")
    apartado = normalizar(d.get("apartado") or "")
    titulo = normalizar(d.get("titulo") or "")
    if seccion.startswith("i.") and "autoridades y personal" in apartado:
        return True
    if "administracion local" in seccion:
        partes = [p.strip() for p in titulo.split(".")]
        return len(partes) >= 2 and any(m == partes[1] or partes[1].startswith(m) for m in MATERIAS_EMPLEO)
    return False


def ambito(d: dict) -> str:
    s = normalizar(d.get("seccion") or "")
    if "administracion local" in s:
        return "local"
    if "universidad" in normalizar(d.get("organismo") or "") or "universidad" in normalizar(d.get("titulo") or "")[:80]:
        return "universidad"
    if s.startswith("i."):
        return "autonomico"
    return "otro"


def municipio_y_materia(titulo: str) -> tuple[str | None, str | None, str | None]:
    partes = [p.strip() for p in titulo.split(".") if p.strip()]
    return (partes[0] if partes else None, partes[1] if len(partes) > 1 else None,
            ". ".join(partes[2:]) if len(partes) > 2 else None)


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "autonomicos" / "bocm"


def _ruta(raiz: Path, carpeta: str, d: date, ext: str = "jsonl", sufijo: str = "") -> Path:
    return _base(raiz) / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}{sufijo}.{ext}"


def _guardar(raiz: Path, d: date, sufijo: str, filas: list[dict], empleo: list[dict]) -> None:
    for carpeta, contenido in (("disposiciones", filas), ("oposiciones", empleo)):
        ruta = _ruta(raiz, carpeta, d, sufijo=sufijo)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in contenido), encoding="utf-8")


def _seleccion(filas: list[dict]) -> list[dict]:
    empleo = []
    for x in filas:
        if es_empleo_publico(x):
            t = normalizar(x["titulo"])
            mun, materia, asunto = municipio_y_materia(x["titulo"]) if ambito(x) == "local" else (None, None, None)
            modalidad = _primera(REGLAS_MODALIDAD, t)
            empleo.append({**x, "ambito": ambito(x), "municipio": mun, "materia": materia, "asunto": asunto,
                           "tipo_acto": _primera(REGLAS_ACTO, t) or "otro", "modalidad": modalidad,
                           "alcance": alcance(t, modalidad, x.get("apartado"))})
    return empleo


def leer_boletin(d: date, n: int, raiz: Path, archivo: Archivo, sufijo: str = "") -> dict | None:
    """Pide el boletín n del día d. None si no existe (404, vacío o de otro día)."""
    url = url_completo(d, n)
    resp = obtener(url, accept="text/html")
    if resp.status == 404:
        return None
    if resp.status != 200:
        return {"fecha": d.isoformat(), "status": resp.status, "resultado": "error_http",
                "alertas": [f"BOCM {d} n.º {n}: HTTP {resp.status}"]}
    s = parsear_completo(resp.contenido)
    if not s["disposiciones"] or s["fecha"] != d.isoformat() or (s["numero"] and int(s["numero"]) != n):
        return None
    captura = archivo.guardar(FUENTE, d, resp.contenido, url, "html", resp.status, resp.cabeceras)
    filas = [{**x, "fecha": d.isoformat(), "boletin": str(n), "fuente": "BOCM", "captura_sha256": captura["sha256"]}
             for x in s["disposiciones"]]
    empleo = _seleccion(filas)
    _guardar(raiz, d, sufijo, filas, empleo)
    return {"fecha": d.isoformat(), "status": 200, "resultado": "ok", "numero": str(n), "url": url,
            "sha256": captura["sha256"], "disposiciones": len(filas), "empleo_publico": len(empleo), "alertas": []}


def ultimo_numero(raiz: Path, d: date) -> tuple[int, date] | None:
    """Último boletín leído del mismo año antes de d (los números empiezan en 1 cada año)."""
    x = d - timedelta(days=1)
    while x.year == d.year and (d - x).days <= 20:
        r = _ruta(raiz, "dias", x, "json")
        if r.exists():
            inf = json.loads(r.read_text(encoding="utf-8"))
            if inf.get("resultado") == "ok" and str(inf.get("numero") or "").isdigit():
                extra = [int(json.loads(f.read_text(encoding="utf-8")).get("numero") or 0)
                         for f in r.parent.glob(f"{x:%d}-*.json")]
                return max([int(inf["numero"]), *extra]), x
        x -= timedelta(days=1)
    return None


def procesar_dia(d: date, raiz: Path, archivo: Archivo) -> dict:
    previo = ultimo_numero(raiz, d)
    if previo is None and (d - date(d.year, 1, 1)).days > 10:
        return {"fecha": d.isoformat(), "resultado": "error_formato",
                "alertas": [f"BOCM {d}: no hay boletín leído en los 20 días anteriores para saber el número"]}
    siguiente = previo[0] + 1 if previo else 1
    if d.weekday() == 6:  # domingo: no sale
        return {"fecha": d.isoformat(), "resultado": "sin_boletin", "nota": "domingo", "alertas": []}
    for n in range(siguiente, siguiente + 3):
        inf = leer_boletin(d, n, raiz, archivo)
        if inf is None:
            continue
        if inf["resultado"] == "ok" and n != siguiente:
            inf["alertas"].append(f"BOCM {d}: se esperaba el n.º {siguiente} y salió el {n}; se buscan los que faltan")
            inf["extraordinarios"] = buscar_perdidos(range(siguiente, n), previo[1] if previo else d, d, raiz, archivo)
        return inf
    inf = {"fecha": d.isoformat(), "resultado": "sin_boletin", "probados": [siguiente, siguiente + 2], "alertas": []}
    if d.weekday() < 6:
        inf["alertas"].append(f"BOCM {d}: sin boletín con los números {siguiente}-{siguiente + 2} (¿festivo?)")
    return inf


def buscar_perdidos(numeros, desde: date, hasta: date, raiz: Path, archivo: Archivo) -> list[dict]:
    """Números que faltan (extraordinarios): se prueban en cada día de desde a hasta."""
    hallados = []
    for m in numeros:
        x = desde
        while x <= hasta:
            inf = leer_boletin(x, m, raiz, archivo, sufijo=f"-{m}")
            time.sleep(PAUSA_HUECOS)  # sin pausa, la búsqueda de huecos hacía que el servidor dejara de responder
            if inf is not None:
                escribir = _ruta(raiz, "dias", x, "json", sufijo=f"-{m}")
                escribir.parent.mkdir(parents=True, exist_ok=True)
                escribir.write_text(json.dumps({**inf, "extraordinario": True}, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
                hallados.append({"numero": m, "fecha": x.isoformat(), "resultado": inf["resultado"]})
                break
            x += timedelta(days=1)
        else:
            hallados.append({"numero": m, "fecha": None, "resultado": "no_encontrado"})
    return hallados


PAUSA_HUECOS = 1.0
DIAS_ENTRE_BUSQUEDAS = 30  # un número que no aparece no se vuelve a buscar hasta pasado este plazo


def rellenar_huecos(raiz: Path, archivo: Archivo, max_minutos: float = 0, hoy: date | None = None) -> list[dict]:
    """Números que faltan en lo ya leído (estado.huecos_numeracion): se buscan entre el día del anterior y el del
    siguiente. Así se recuperan los extraordinarios de antes del 30/10/2026 (el XML por fecha no los daba)."""
    from motor.estado import huecos_numeracion

    leidos: dict[str, dict[int, date]] = {}
    for f in (_base(raiz) / "dias").rglob("*.json"):
        inf = json.loads(f.read_text(encoding="utf-8"))
        if inf.get("resultado") == "ok" and str(inf.get("numero") or "").isdigit():
            leidos.setdefault(inf["fecha"][:4], {})[int(inf["numero"])] = date.fromisoformat(inf["fecha"])
    hoy = hoy or datetime.now(MADRID).date()
    ruta_buscados = _base(raiz) / "huecos_buscados.json"
    buscados = json.loads(ruta_buscados.read_text(encoding="utf-8")) if ruta_buscados.exists() else {}
    inicio, res = time.monotonic(), []
    try:
        for anio, faltan in huecos_numeracion({a: set(v) for a, v in leidos.items()}).items():
            for m in faltan:
                if max_minutos and (time.monotonic() - inicio) / 60 > max_minutos:
                    return res
                clave = f"{anio}-{m}"
                if clave in buscados and (hoy - date.fromisoformat(buscados[clave])).days < DIAS_ENTRE_BUSQUEDAS:
                    continue
                antes = max((n for n in leidos[anio] if n < m), default=None)
                despues = min((n for n in leidos[anio] if n > m), default=None)
                if antes is None or despues is None:
                    continue
                hallado = buscar_perdidos([m], leidos[anio][antes], leidos[anio][despues], raiz, archivo)
                res += hallado
                if hallado and hallado[0]["resultado"] == "no_encontrado":
                    buscados[clave] = hoy.isoformat()
    finally:
        ruta_buscados.parent.mkdir(parents=True, exist_ok=True)
        ruta_buscados.write_text(json.dumps(buscados, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    return res


def texto_disposicion(xml: bytes) -> dict:
    raiz = ET.fromstring(xml)
    lineas = [" ".join(l.split()) for l in (raiz.findtext("texto") or "").splitlines()]
    guardadas, omitidas = parrafos_seguros([l for l in lineas if l])
    meta = raiz.find("metadatos")
    return {"titulo": _t(meta, "titulo"), "paginas": [_t(meta, "pagina_inicial"), _t(meta, "pagina_final")],
            "texto": "\n".join(guardadas), "parrafos_omitidos_por_datos_personales": omitidas}


def textos_pendientes(raiz: Path) -> list[dict]:
    lista = []
    for f in sorted((_base(raiz) / "oposiciones").glob("*/*/*.jsonl"), reverse=True):
        for linea in f.read_text(encoding="utf-8").splitlines():
            x = json.loads(linea)
            destino = _base(raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"
            if x.get("url_xml") and not destino.exists():
                lista.append(x)
    # Primero lo de acceso abierto; dentro, de lo más reciente a lo más antiguo (orden ya inverso por fichero)
    return sorted(lista, key=lambda x: 0 if x.get("alcance") in (None, "acceso") else 1)


MAX_FALLOS_SEGUIDOS = 25


def descargar_textos(raiz: Path, archivo: Archivo, max_minutos: float, pausa: float) -> tuple[int, int]:
    """Textos pendientes, de uno en uno con una pausa tras cada petición (también tras un fallo). Si fallan
    MAX_FALLOS_SEGUIDOS seguidos, se para: la fuente está caída o no deja, y no se insiste. Los tipos de fallo salen
    como aviso en GitHub (hasta el 31/10/2026 el paso no avanzaba desde el 30/10 sin decir por qué)."""
    inicio, hechos, errores, seguidos = time.monotonic(), 0, 0, 0
    tipos: Counter = Counter()
    ejemplo: dict[str, str] = {}

    def fallo(tipo: str, detalle: str) -> bool:
        nonlocal errores, seguidos
        errores, seguidos = errores + 1, seguidos + 1
        tipos[tipo] += 1
        ejemplo.setdefault(tipo, detalle[:300])
        time.sleep(pausa)
        return seguidos >= MAX_FALLOS_SEGUIDOS

    for x in textos_pendientes(raiz):
        if max_minutos and (time.monotonic() - inicio) / 60 > max_minutos:
            break
        try:
            r = obtener(x["url_xml"], accept="application/xml")
        except ConnectionError as e:
            from motor.http import ROBOTS_ESTADO
            if fallo(type(e).__name__, f"robots.txt leído así: {ROBOTS_ESTADO.get(WEB)}; {x['url_xml']}: {e}"):
                break
            continue
        if r.status != 200:
            if fallo(f"HTTP {r.status}", x["url_xml"]):
                break
            continue
        try:
            datos = texto_disposicion(r.contenido)
        except ET.ParseError:
            if fallo("no es XML", f"{x['url_xml']}: {r.cabeceras.get('content-type') or r.cabeceras.get('Content-Type')} "
                                  f"{r.contenido[:120]!r}"):
                break
            continue
        except Exception as e:  # noqa: BLE001 - un documento raro no para los demás
            if fallo(type(e).__name__, f"{x['url_xml']}: {e}"):
                break
            continue
        seguidos = 0
        d = date.fromisoformat(x["fecha"])
        captura = archivo.guardar(FUENTE + "-texto", d, r.contenido, x["url_xml"], "xml", r.status, r.cabeceras)
        destino = _base(raiz) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps({"id": x["id"], **datos, "captura_sha256": captura["sha256"],
                                       "capturado": captura["capturado"], "url": x["url_xml"]},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
        hechos += 1
        time.sleep(pausa)
    if errores:
        parado = " (parado por fallos seguidos)" if seguidos >= MAX_FALLOS_SEGUIDOS else ""
        print(f"::warning title=BOCM textos::{hechos} descargados, {errores} fallos{parado}: "
              + "; ".join(f"{t} ×{n} (p. ej. {ejemplo[t]})" for t, n in tipos.most_common(4)))
    return hechos, errores


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=date.fromisoformat, default=hoy - timedelta(days=1))
    p.add_argument("--hasta", type=date.fromisoformat, default=hoy)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--saltar-existentes", action="store_true")
    p.add_argument("--textos", action="store_true", help="descargar los textos pendientes en lugar de sumarios")
    p.add_argument("--huecos", action="store_true", help="buscar los números que faltan entre los boletines leídos")
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=0.7)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())

    if a.textos:
        hechos, errores = descargar_textos(a.salida, archivo, a.max_minutos, a.pausa)
        print(f"::notice title=BOCM textos::{hechos} descargados, {errores} errores, "
              f"{len(textos_pendientes(a.salida))} pendientes")
        return 0

    if a.huecos:
        res = rellenar_huecos(a.salida, archivo, a.max_minutos)
        print(f"BOCM huecos: {json.dumps(res, ensure_ascii=False)}")
        return 0

    inicio, informes = time.monotonic(), []
    freno = Freno()
    d = a.desde
    while d <= a.hasta:
        if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
            print("Tiempo agotado; se continúa en la siguiente ejecución")
            break
        ruta = _ruta(a.salida, "dias", d, "json")
        if a.saltar_existentes and ruta.exists() and \
                json.loads(ruta.read_text(encoding="utf-8")).get("resultado") in {"ok", "sin_boletin"}:
            d += timedelta(days=1)
            continue
        try:
            inf = procesar_dia(d, a.salida, archivo)
        except ConnectionError as e:
            inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(inf, ensure_ascii=False, indent=1), encoding="utf-8")
        informes.append(inf)
        if freno.anotar(inf):
            break
        print(f"BOCM {d}: {inf.get('resultado')} {inf.get('disposiciones', '')} disposiciones, "
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
