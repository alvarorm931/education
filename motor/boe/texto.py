"""Texto completo de cada disposición del BOE, sin datos personales.

Desde el 30/10/2026 se lee la versión HTML (txt.php): el robots.txt del BOE prohíbe a los programas automáticos
el XML («Disallow: /diario_boe/xml.php?») y permite el HTML en castellano, salvo los documentos concretos que
retira (esos no se piden: lo comprueba motor/http.py). El XML de las descargas anteriores se sigue leyendo igual.

Uso:
  python -m motor.boe.texto --ids BOE-A-2026-20413,BOE-A-2026-20626 --salida ruta/
  python -m motor.boe.texto --pendientes --salida ruta/ --max-minutos 300

Del original se anota la huella en archivo/indices/boe-texto/ (el contenido solo se guarda con almacén privado). En datos/boe/textos/AAAA/MM/{id}.json
se guarda el texto con estas reglas:
  - tablas con datos de personas (DNI, apellidos, nombre): solo número de filas y cabecera;
  - párrafos con un documento de identidad o con el nombre de una persona («don ...»): se cuentan y no se guardan;
  - en el título, el nombre de la persona se sustituye por «[persona]»;
  - referencias a otras disposiciones (bloque «análisis» del BOE): se guardan, sirven para unir actos.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.http import obtener

URL_XML = "https://www.boe.es/diario_boe/xml.php?id={id}"   # solo para leer capturas antiguas
URL_HTML = "https://www.boe.es/diario_boe/txt.php?id={id}"
RE_ID = re.compile(r"^BOE-[AB]-\d{4}-\d+$")
FUENTE = "boe-texto"
MADRID = ZoneInfo("Europe/Madrid")

from motor.limpieza import (CABECERA_PERSONAL, RE_DOCUMENTO, limpiar_html, texto_de, tiene_nombre_de_persona,  # noqa: E402
                            titulo_sin_nombres)

RE_TITULO_HTML = re.compile(r'<h3 class="documento-tit">(.*?)</h3>', re.S)
RE_DD = re.compile(r"<dt>\s*(?P<k>[^<]+?)\s*:?\s*</dt>\s*<dd>(?P<v>.*?)</dd>", re.S)
RE_TEXTO_HTML = re.compile(r'<div id="textoxslt">(.*?)</div>\s*<!-- #textoxslt -->', re.S)
RE_ANALISIS = re.compile(r'<div id="analisis"[^>]*>(.*?)(?:<p class="linkSubir"|<!-- \.pool -->)', re.S)
RE_LI = re.compile(r"<li>(.*?)</li>", re.S)
RE_REF = re.compile(r"\(Ref\.\s*<a [^>]*>(BOE-[A-Z]-\d{4}-\d+)</a>\)", re.S)
RE_RELACION = re.compile(r"^(?P<rel>[A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ ,]+?)\s+(?=[a-záéíóúñ«(\d])")


def _limpio(nodo: ET.Element) -> str:
    return " ".join("".join(nodo.itertext()).split())


def _tabla(tabla: ET.Element) -> dict:
    filas = [[_limpio(c) for c in fila if c.tag in {"td", "th"}] for fila in tabla.iter("tr")]
    filas = [f for f in filas if any(f)]
    cabecera = filas[0] if filas else []
    contenido = " ".join(" ".join(f) for f in filas)
    personal = bool(CABECERA_PERSONAL.search(" ".join(cabecera))) or len(RE_DOCUMENTO.findall(contenido)) >= 2
    if personal:
        return {"filas": max(len(filas) - 1, 0), "cabecera": cabecera, "datos_personales": True}
    return {"filas": len(filas), "contenido": filas, "datos_personales": False}


def texto_plano(xml: bytes) -> dict:
    raiz = ET.fromstring(xml)
    meta = raiz.find("metadatos")

    def m(etiqueta: str) -> str | None:
        n = meta.find(etiqueta) if meta is not None else None
        return " ".join(n.text.split()) if n is not None and n.text else None

    parrafos, tablas, omitidos = [], [], 0
    cuerpo = raiz.find("texto")
    if cuerpo is not None:
        pila = list(cuerpo)
        while pila:
            nodo = pila.pop(0)
            if nodo.tag == "table":
                tablas.append(_tabla(nodo))
            elif nodo.tag in {"p", "li"}:
                t = _limpio(nodo)
                if not t:
                    continue
                if RE_DOCUMENTO.search(t) or tiene_nombre_de_persona(t):
                    omitidos += 1
                else:
                    parrafos.append(t)
            else:
                pila[0:0] = list(nodo)

    referencias = []
    for grupo in ("anteriores", "posteriores"):
        for ref in raiz.findall(f"analisis/referencias/{grupo}/*"):
            referencias.append({
                "sentido": grupo,
                "referencia": ref.get("referencia"),
                "relacion": _limpio(ref.find("palabra")) if ref.find("palabra") is not None else None,
                "texto": _limpio(ref.find("texto")) if ref.find("texto") is not None else None,
            })

    return {
        "titulo": titulo_sin_nombres(m("titulo")),
        "fecha_publicacion": m("fecha_publicacion"),
        "departamento": m("departamento"),
        "rango": m("rango"),
        "texto": "\n".join(parrafos),
        "tablas": tablas,
        "parrafos_omitidos_por_datos_personales": omitidos,
        "referencias": referencias,
    }


def texto_plano_html(html: bytes | str) -> dict:
    """Lo mismo que texto_plano() desde la versión HTML del documento (txt.php)."""
    h = html.decode("utf-8", errors="replace") if isinstance(html, bytes) else html
    titulo = RE_TITULO_HTML.search(h)
    meta = {texto_de(m.group("k")).lower(): texto_de(m.group("v")) for m in RE_DD.finditer(h)}
    cuerpo = RE_TEXTO_HTML.search(h)
    limpio = limpiar_html(cuerpo.group(1)) if cuerpo else {"texto": "", "tablas": [],
                                                            "parrafos_omitidos_por_datos_personales": 0}
    rango = fecha = None
    referencias = []
    a = RE_ANALISIS.search(h)
    if a:
        bloque = a.group(1)
        primera = bloque.split("<h5>", 1)[0]
        for li in RE_LI.findall(primera):
            t = texto_de(li)
            if t.startswith("Rango:"):
                rango = t.split(":", 1)[1].strip()
            elif t.startswith("Fecha de publicación:"):
                d = re.search(r"(\d{2})/(\d{2})/(\d{4})", t)
                fecha = f"{d.group(3)}{d.group(2)}{d.group(1)}" if d else None
        for sentido, etiqueta in (("anteriores", "Referencias anteriores"), ("posteriores", "Referencias posteriores")):
            m = re.search(rf"<h5>{etiqueta}</h5>\s*<ul[^>]*>(.*?)</ul>", bloque, re.S)
            for li in RE_LI.findall(m.group(1)) if m else []:
                ref = RE_REF.search(li)
                t = texto_de(RE_REF.sub("", li)).rstrip(" .")
                rel = RE_RELACION.match(t)
                referencias.append({"sentido": sentido, "referencia": ref.group(1) if ref else None,
                                    "relacion": rel.group("rel").strip() if rel else None,
                                    "texto": t[rel.end():].strip() if rel else t})
    return {
        "titulo": titulo_sin_nombres(texto_de(titulo.group(1))) if titulo else None,
        "fecha_publicacion": fecha,
        "departamento": meta.get("departamento"),
        "rango": rango,
        **limpio,
        "referencias": referencias,
    }


def ruta_texto(raiz: Path, ident: str, fecha: str) -> Path:
    """fecha: AAAA-MM-DD o AAAAMMDD."""
    f = fecha.replace("-", "")
    return raiz / "datos" / "boe" / "textos" / f[:4] / f[4:6] / f"{ident}.json"


PRIORIDAD_ACTO = {"convocatoria": 0, "correccion": 0, "anulacion": 0, "admitidos": 1, "aprobados": 1, "examen": 1,
                  "tribunal": 1, "oferta_empleo": 1, "nombramiento": 2, "desierta": 2}


def pendientes(raiz: Path, dias_recientes: int = 60) -> list[tuple[str, str]]:
    """(identificador, fecha) de los anuncios de oposiciones sin texto, por orden de valor:
    1) los de los últimos `dias_recientes` días (procesos con plazo abierto o recién abierto);
    2) los de acceso abierto al público, por tipo de acto y del más reciente al más antiguo;
    3) el resto (provisión de puestos entre funcionarios, promoción interna, profesorado universitario).
    """
    filas = []
    for fichero in (raiz / "datos" / "boe" / "oposiciones").glob("*/*/*.jsonl"):
        for linea in fichero.read_text(encoding="utf-8").splitlines():
            fila = json.loads(linea)
            ident, fecha = fila.get("identificador"), fila.get("fecha")
            if ident and fecha and not ruta_texto(raiz, ident, fecha).exists():
                filas.append(fila)
    if not filas:
        return []
    corte = (date.fromisoformat(max(f["fecha"] for f in filas)) - timedelta(days=dias_recientes)).isoformat()

    def clave(f: dict) -> tuple:
        reciente = f["fecha"] >= corte
        acceso = f.get("alcance") in (None, "acceso")
        grupo = 0 if reciente else (1 if acceso else 2)
        return (grupo, PRIORIDAD_ACTO.get(f.get("tipo_acto"), 3), _inverso(f["fecha"]))

    return [(f["identificador"], f["fecha"]) for f in sorted(filas, key=clave)]


def _inverso(fecha: str) -> str:
    """Para ordenar de la fecha más reciente a la más antigua dentro de cada grupo."""
    return "".join(chr(ord("9") - ord(c) + ord("0")) if c.isdigit() else c for c in fecha)


def descargar(ident: str, raiz: Path, archivo: Archivo) -> str:
    url = URL_HTML.format(id=ident)
    resp = obtener(url, accept="text/html")
    if resp.status != 200:
        return f"HTTP {resp.status}"
    datos = texto_plano_html(resp.contenido)
    if not datos["titulo"] or not (datos["texto"] or datos["tablas"] or datos["parrafos_omitidos_por_datos_personales"]):
        return "HTML sin título o sin texto (posible cambio de formato)"
    fp = datos.get("fecha_publicacion") or ""
    fecha = date(int(fp[:4]), int(fp[4:6]), int(fp[6:8])) if len(fp) == 8 else datetime.now(MADRID).date()
    captura = archivo.guardar(FUENTE, fecha, resp.contenido, url, "html", resp.status, resp.cabeceras)
    destino = ruta_texto(raiz, ident, fecha.isoformat())
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps({"identificador": ident, **datos, "captura_sha256": captura["sha256"],
                                   "capturado": captura["capturado"], "url": url},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
    return "ok"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ids", help="identificadores separados por comas")
    p.add_argument("--pendientes", action="store_true", help="todos los anuncios de oposiciones sin texto")
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--pausa", type=float, default=0.3)
    p.add_argument("--max", type=int, default=0, help="máximo de documentos (0 = sin límite)")
    p.add_argument("--max-minutos", type=float, default=0, help="parar al llegar a este tiempo (0 = sin límite)")
    a = p.parse_args(argv)

    if a.ids:
        trabajo = [(x.strip(), "") for x in a.ids.split(",") if x.strip()]
        malos = [x for x, _ in trabajo if not RE_ID.match(x)]
        if malos:
            p.error(f"identificadores no válidos: {malos}")
    elif a.pendientes:
        trabajo = pendientes(a.salida)
    else:
        p.error("indica --ids o --pendientes")
    if a.max:
        trabajo = trabajo[: a.max]

    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    inicio, hechos, errores = time.monotonic(), 0, []
    print(f"Documentos a descargar: {len(trabajo)}")
    for i, (ident, _) in enumerate(trabajo):
        if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
            print(f"Tiempo agotado: quedan {len(trabajo) - i} para la siguiente ejecución")
            break
        try:
            r = descargar(ident, a.salida, archivo)
        except ConnectionError as e:
            r = str(e)
        if r == "ok":
            hechos += 1
        else:
            errores.append(f"{ident}: {r}")
        if i < len(trabajo) - 1:
            time.sleep(a.pausa)
    print(f"Descargados: {hechos}. Errores: {len(errores)}")
    for e in errores[:50]:
        print(" -", e)
    return 1 if errores and not hechos else 0


if __name__ == "__main__":
    sys.exit(main())
