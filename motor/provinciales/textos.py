"""Textos de los anuncios de empleo de los BOP sin descarga propia de textos. Mismas reglas que el resto: en listas de
personas (fuera de CON_TEXTO) solo el recuento de líneas con documento de identidad.

  - Con un PDF por anuncio (url_pdf): Zamora, BOTHA, Ávila, Jaén y Salamanca.
  - Con el PDF del boletín entero: Lugo y Palencia (página de cada anuncio), Tenerife y Las Palmas (sin página: se
    busca el título). Se descarga el boletín una vez y se corta el texto de cada anuncio de empleo desde su título
    hasta el título del anuncio siguiente; si no se encuentra el título, sin texto (nunca el de otro anuncio).

Uso: python -m motor.provinciales.textos FUENTE --salida ruta/ [--max-minutos 30]
"""

from __future__ import annotations

import argparse
import io
import logging
import re
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import escribir_json, leer_jsonl
from motor.boe.clasificar import normalizar
from motor.extraccion.citas import citas
from motor.http import obtener
from motor.limpieza import RE_DOCUMENTO, limpiar_texto
from motor.provinciales.comun import CON_TEXTO, descargar_textos_pdf, ruta_texto_pdf

# BOP con un PDF por anuncio y sin descarga de textos en su conector
CON_PDF_POR_ANUNCIO = {"bopzamora", "bopalava", "bopavila", "bopjaen", "bopsalamanca"}
# BOP con el PDF del boletín entero: campo con su dirección
BOLETIN_ENTERO = {"boplugo": "url_pdf", "boppalencia": "url_pdf", "boptenerife": "url_pdf",
                  "boplaspalmas": "url_pdf_boletin"}


def _plano(s: str) -> str:
    return re.sub(r"[^a-z0-9ñ]+", " ", normalizar(s or "")).strip()


def paginas_pdf(contenido: bytes) -> list[str]:
    from pypdf import PdfReader
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    return [p.extract_text() or "" for p in PdfReader(io.BytesIO(contenido)).pages]


RE_INDICE = re.compile(r"\.{5,}|…{2,}|(?:\. ){4,}")


def _posicion(plano: str, titulo: str, desde: int) -> int:
    """Dónde empieza el título (sus primeras palabras) en el texto plano del boletín, desde una posición."""
    palabras = _plano(titulo).split()
    for n in (12, 8, 5):
        if len(palabras) >= min(n, 4):
            i = plano.find(" ".join(palabras[:n]), desde)
            if i >= 0:
                return i
    return -1


def es_pagina_de_sumario(pagina: str) -> bool:
    """Página del sumario del propio boletín: muchas líneas con puntos hasta el número de página o de registro."""
    lineas = [l for l in pagina.splitlines() if l.strip()]
    con_puntos = sum(1 for l in lineas if RE_INDICE.search(l))
    return con_puntos >= 4 and con_puntos >= 0.2 * len(lineas)


def cortar(paginas: list[str], anuncios: list[dict]) -> dict[str, tuple[str, list[int]]]:
    """Texto de cada anuncio del boletín (en su orden): de su título al del siguiente. Con «pagina», la búsqueda
    empieza en su página. Si el título no aparece, el anuncio se queda sin texto (nunca con el de otro)."""
    # Las páginas del sumario se dejan en blanco (con su largo) para no confundir sus títulos con los del cuerpo
    planos = [" " * len(_plano(p)) if es_pagina_de_sumario(p) else _plano(p) for p in paginas]
    inicio_pag, acumulado = [], 0
    for p in planos:
        inicio_pag.append(acumulado)
        acumulado += len(p) + 1
    plano = " ".join(planos)
    posiciones, desde = [], 0
    for x in anuncios:
        pag = x.get("pagina")
        base = inicio_pag[pag - 1] if isinstance(pag, int) and 0 < pag <= len(inicio_pag) else desde
        i = _posicion(plano, x.get("titulo") or "", max(base, desde) if not isinstance(pag, int) else base)
        posiciones.append(i)
        if i >= 0:
            desde = i + 1
    out = {}
    for k, x in enumerate(anuncios):
        i = posiciones[k]
        siguiente = next((p for p in posiciones[k + 1:] if p > i), -1) if i >= 0 else -1
        if i >= 0:
            # Sin anuncio siguiente localizado, como mucho hasta el final de la página siguiente a la de inicio
            pag_ini = max(n for n, ini in enumerate(inicio_pag) if ini <= i)
            tope = inicio_pag[pag_ini + 2] if pag_ini + 2 < len(inicio_pag) else len(plano)
            fin = siguiente if siguiente > i else tope
            pags = [n + 1 for n, ini in enumerate(inicio_pag) if ini <= fin and ini + len(planos[n]) >= i]
        else:
            # Sin el título no se sabe dónde empieza ni acaba: mejor sin texto que con el de otro anuncio
            continue
        # El texto se toma de las páginas originales (con sus saltos de línea), recortado a lo que toca si se puede
        bruto = "\n".join(paginas[n - 1] for n in pags if 0 < n <= len(paginas))
        if i >= 0:
            ini_txt = _posicion_bruto(bruto, x.get("titulo") or "")
            sig_t = anuncios[k + 1].get("titulo") if k + 1 < len(anuncios) else None
            fin_txt = _posicion_bruto(bruto, sig_t, ini_txt + 1) if sig_t else -1
            bruto = bruto[max(ini_txt, 0):fin_txt if fin_txt > ini_txt else None]
        out[x["id"]] = (bruto, pags)
    return out


def _posicion_bruto(bruto: str, titulo: str | None, desde: int = 0) -> int:
    """Posición aproximada del título en el texto original: la primera línea que contiene sus primeras palabras."""
    if not titulo:
        return -1
    clave = " ".join(_plano(titulo).split()[:5])
    if not clave:
        return -1
    pos = 0
    for linea in bruto.splitlines(keepends=True):
        if pos >= desde and (_plano(linea + " " + bruto[pos + len(linea):pos + len(linea) + 200]).startswith(clave)
                             or clave in _plano(linea)):
            return pos
        pos += len(linea)
    return -1


def textos_boletin_entero(raiz: Path, fuente: str, archivo: Archivo, max_minutos: float, pausa: float) -> tuple[int, int, int]:
    base = raiz / "datos" / "provinciales" / fuente
    campo = BOLETIN_ENTERO[fuente]
    pendientes: dict[str, list[dict]] = defaultdict(list)
    for f in sorted((base / "oposiciones").glob("*/*/*.jsonl"), reverse=True):
        for x in leer_jsonl(f):
            if x.get(campo) and not ruta_texto_pdf(base, x).exists():
                pendientes[(x[campo].split("#")[0], x["fecha"])].append(x)
    inicio, hechos, errores = time.monotonic(), 0, 0
    for (url, fecha), lista in pendientes.items():
        if max_minutos and (time.monotonic() - inicio) / 60 > max_minutos:
            break
        todas = [x for f in (base / "disposiciones").glob(f"{fecha[:4]}/{fecha[5:7]}/{fecha[8:10]}*.jsonl")
                 for x in leer_jsonl(f) if (x.get(campo) or "").split("#")[0] == url]
        todas.sort(key=lambda x: (x.get("pagina") or 0, x.get("orden") or 0))
        if not todas:
            continue
        time.sleep(pausa)
        try:
            r = obtener(url, accept="application/pdf, */*")
        except (ConnectionError, TimeoutError):
            errores += len(lista)
            continue
        if r.status != 200 or r.contenido[:4] != b"%PDF":
            errores += len(lista)
            continue
        captura = archivo.guardar(fuente + "-boletin", date.fromisoformat(fecha), r.contenido, url, "pdf", r.status,
                                  r.cabeceras)
        try:
            cortes = cortar(paginas_pdf(r.contenido), todas)
        except Exception:  # un PDF mal formado no detiene la carga
            errores += len(lista)
            continue
        for x in lista:
            if x["id"] not in cortes:
                errores += 1
                continue
            bruto, pags = cortes[x["id"]]
            if x.get("tipo_acto") in CON_TEXTO:
                datos = {"titulo": x.get("titulo"), **{k: v for k, v in limpiar_texto(bruto).items() if k != "titulo"}}
            else:
                datos = {"titulo": x.get("titulo"), "texto": None, "tablas": [], "solo_recuento": True,
                         "lineas_con_documento_de_identidad": sum(1 for l in bruto.splitlines() if RE_DOCUMENTO.search(l)),
                         "citas": citas(bruto)}
            escribir_json(ruta_texto_pdf(base, x), {"id": x["id"], **datos, "paginas": pags,
                                                    "captura_sha256": captura["sha256"],
                                                    "capturado": captura["capturado"], "url": url})
            hechos += 1
    total = sum(len(v) for v in pendientes.values())
    return hechos, errores, total - hechos


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("fuente", choices=sorted(CON_PDF_POR_ANUNCIO | set(BOLETIN_ENTERO)))
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    if a.fuente in BOLETIN_ENTERO:
        hechos, errores, pendientes = textos_boletin_entero(a.salida, a.fuente, archivo, a.max_minutos, a.pausa)
    else:
        hechos, errores, pendientes = descargar_textos_pdf(a.salida / "datos" / "provinciales" / a.fuente, a.fuente,
                                                           archivo, a.max_minutos, a.pausa, accept="application/pdf, */*")
    print(f"{a.fuente} textos: {hechos} descargados, {errores} errores, {pendientes} pendientes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
