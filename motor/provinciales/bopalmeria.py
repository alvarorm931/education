"""Conector del Boletín Oficial de la Provincia de Almería.

Formato verificado el 31/10/2026 desde GitHub (sondas `sonda_navegador` y `sonda_almeria`, 14:20-14:52):
  - El boletín se consulta en una aplicación ZK (https://app.dipalme.org/bop/publico.zul) que solo funciona con
    JavaScript: la lista de anuncios sale de peticiones AJAX de ZK, así que se lee con un navegador sin pantalla
    (Chromium por Playwright), identificado como el motor.
  - «Consulta de Anuncios» busca por fecha de publicación (caja «dd/mm/aaaa» con «Tipo búsqueda: Igual» y «Buscar»).
    Cada fila trae el boletín («2026/211»), la fecha, la cabecera del anuncio en líneas (sección, entidad, a veces
    el área, y el asunto) y el número de edicto («2966-2026»). Abajo, «[ 1 - 11 / 11 ]» y las páginas.
  - El PDF de cada anuncio tiene dirección fija por su edicto, sin sesión:
    https://app.dipalme.org/bop/services/manager/edicto/AAAA/NNNN/anuncio.pdf (probado con sonda_pdf_texto). El
    del boletín entero va por un enlace firmado que solo da la aplicación, y no hace falta.
  - El buscador dice que tiene anuncios desde 2010.
  - Cada búsqueda es una sola consulta a la aplicación; se espera una pausa entre días.

Uso:
  python -m motor.provinciales.bopalmeria --salida ruta/                                   # ayer y hoy
  python -m motor.provinciales.bopalmeria --desde 2022-01-01 --max-minutos 30 --salida ruta/
  python -m motor.provinciales.bopalmeria --textos --max-minutos 30 --salida ruta/
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (Freno, clasificar, convocante_de_organismo, descargar_textos, es_empleo_estricto,
                                     escribir_json, escribir_jsonl, leer_jsonl, estado_dia, nombre_propio)
from motor.boe.clasificar import normalizar
from motor.http import USER_AGENT
from motor.limpieza import titulo_sin_nombres
from motor.provinciales.comun import CON_TEXTO, texto_pdf

FUENTE = "bopalmeria"
SIGLAS = "BOP-ALMERIA"
MADRID = ZoneInfo("Europe/Madrid")
APP = "https://app.dipalme.org/bop/publico.zul"
NOMBRES = ("Boletín Oficial de la Provincia de Almería",)
# «Anuncios en general y comunicaciones oficiales» trae también las convocatorias de empresas y consorcios públicos
# (Gestión de Aguas del Levante Almeriense); el filtro de empleo deja fuera juntas de regantes y subastas
SECCIONES_LOCALES = ("administracion local", "diputacion", "otras entidades", "entidades locales", "anuncios en general")
RE_BOLETIN = re.compile(r"^(?P<a>\d{4})/(?P<n>\d{1,4})$")
RE_EDICTO = re.compile(r"^(?P<n>\d{1,6})-(?P<a>\d{4})$")
RE_PAGINAS = re.compile(r"\[\s*(?P<de>\d+)\s*-\s*(?P<a>\d+)\s*/\s*(?P<total>\d+)\s*\]")
RE_CABECERA_PDF = re.compile(
    r"^(?:B\.?O\.?P\.? (?:de )?Almer[ií]a.*|Bolet[ií]n Oficial de la Provincia de Almer[ií]a.*|P[aá]g(?:ina|\.)? \d+.*|"
    r"N[uú]m(?:ero|\.)? \d+.*|\d+|C[oó]digo Seguro de Verificaci\S*.*|https?://\S+)$", re.IGNORECASE)

# Filas de la lista: el texto de cada celda, con sus saltos de línea (la cabecera va en líneas)
JS_FILAS = """() => {
  const filas = [...document.querySelectorAll('.z-listitem')].map(f =>
    [...f.querySelectorAll('.z-listcell')].map(c => (c.innerText || '').replace(/\\u00a0/g, ' ').trim()));
  const pag = [...document.querySelectorAll('.z-paging-info')].map(e => (e.innerText || '').trim());
  const vacio = [...document.querySelectorAll('.z-listbox-emptybody, .z-emptymessage')].map(e => (e.innerText || '').trim());
  return {filas, paginas: pag, vacio};
}"""


def url_pdf(numero: int | str, anio: int | str) -> str:
    return f"https://app.dipalme.org/bop/services/manager/edicto/{anio}/{numero}/anuncio.pdf"


def _mayusculas(lin: str) -> bool:
    letras = [c for c in lin if c.isalpha()]
    return bool(letras) and all(c.isupper() for c in letras)


def leer_cabecera(texto: str) -> dict:
    """«ADMINISTRACIÓN LOCAL\\nAYUNTAMIENTO DE ALMERÍA\\nÁREA DE …\\nCONVOCATORIA …» -> sección, entidad, área y asunto.
    El asunto es la última línea (o las últimas, si el asunto ocupa varias y la entidad no)."""
    lineas = [" ".join(l.split()) for l in (texto or "").splitlines() if l.strip()]
    if not lineas:
        return {"seccion": None, "organismo": None, "area": None, "titulo": ""}
    if len(lineas) == 1:
        return {"seccion": None, "organismo": None, "area": None, "titulo": lineas[0]}
    seccion, resto = lineas[0], lineas[1:]
    if len(resto) == 1:
        return {"seccion": seccion, "organismo": None, "area": None, "titulo": resto[0]}
    entidad, resto = resto[0], resto[1:]
    area = " ".join(resto[:-1]) or None
    return {"seccion": seccion, "organismo": entidad, "area": area, "titulo": resto[-1]}


def leer_filas(filas: list[list[str]]) -> list[dict]:
    """Celdas de cada fila (boletín, fecha, miniatura del boletín, índice, cabecera, edicto, anuncio) -> anuncios."""
    out = []
    for celdas in filas:
        textos = [c for c in celdas]
        boletin = next((RE_BOLETIN.match(c) for c in textos if RE_BOLETIN.match(c)), None)
        edicto = next((RE_EDICTO.match(c) for c in textos if RE_EDICTO.match(c)), None)
        fecha = next((c for c in textos if re.match(r"^\d{2}/\d{2}/\d{4}$", c)), None)
        cabecera = max((c for c in textos if c and not RE_BOLETIN.match(c) and not RE_EDICTO.match(c) and c != fecha),
                       key=len, default="")
        if not edicto or not fecha:
            continue
        c = leer_cabecera(cabecera)
        out.append({
            "seccion": nombre_propio(c["seccion"]) if c["seccion"] and _mayusculas(c["seccion"]) else c["seccion"],
            "organismo": nombre_propio(c["organismo"]) if c["organismo"] and _mayusculas(c["organismo"]) else c["organismo"],
            "area": nombre_propio(c["area"]) if c["area"] and _mayusculas(c["area"]) else c["area"],
            "titulo": titulo_sin_nombres(c["titulo"]),
            "numero_edicto": f"{edicto.group('n')}-{edicto.group('a')}",
            "boletin": boletin.group("n") if boletin else None,
            "fecha_texto": fecha,
            "url_pdf": url_pdf(edicto.group("n"), edicto.group("a")),
        })
    return out


def seleccionar(disposiciones: list[dict]) -> list[dict]:
    out = []
    for x in disposiciones:
        if not normalizar(x.get("seccion") or "").startswith(SECCIONES_LOCALES):
            continue
        if not es_empleo_estricto(x["titulo"]):
            continue
        conv = convocante_de_organismo(x.get("organismo") or "")
        if conv and not conv.get("provincia"):
            conv["provincia"] = "Almería"
        out.append({**x, "ambito": "local", **clasificar(x["titulo"], x.get("seccion")), "convocante": conv})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "provinciales" / FUENTE


def _ruta(raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


class Aplicacion:
    """La aplicación del BOP abierta en un navegador sin pantalla; busca los anuncios de un día."""

    def __init__(self, espera_ms: int = 2500):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:  # en prueba.yml no viene instalado
            import subprocess
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "playwright"], check=True)
            from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        try:
            self._nav = self._pw.chromium.launch()
        except Exception:  # noqa: BLE001 - falta el navegador en este equipo
            _instalar_navegador()
            self._nav = self._pw.chromium.launch()
        self._ctx = self._nav.new_context(user_agent=USER_AGENT, locale="es-ES")
        self.espera = espera_ms
        self.pagina = None
        self.abrir()

    def abrir(self) -> None:
        if self.pagina:
            self.pagina.close()
        self.pagina = self._ctx.new_page()
        self.pagina.goto(APP, wait_until="networkidle", timeout=90000)
        self.pagina.wait_for_selector("input.z-datebox-input", timeout=60000)
        self.pagina.wait_for_timeout(self.espera)

    def buscar(self, d: date) -> tuple[list[list[str]], str, bytes]:
        """Filas de los anuncios publicados el día d (todas las páginas), el texto de la paginación y el HTML de la
        primera página de resultados (el original que se guarda)."""
        p = self.pagina
        caja = p.locator("input.z-datebox-input").first
        caja.fill(f"{d:%d/%m/%Y}")
        caja.press("Tab")
        p.get_by_text("Buscar", exact=True).first.click()
        p.wait_for_load_state("networkidle", timeout=60000)
        p.wait_for_timeout(self.espera)
        d0 = p.evaluate(JS_FILAS)
        html = p.content().encode("utf-8")
        filas, info = list(d0["filas"]), " ".join(d0["paginas"])
        for _ in range(60):  # páginas siguientes
            m = RE_PAGINAS.search(info)
            if not m or int(m.group("a")) >= int(m.group("total")):
                break
            sig = p.locator(".z-paging-next").first
            if not sig.count() or sig.is_disabled():
                break
            sig.click()
            p.wait_for_load_state("networkidle", timeout=60000)
            p.wait_for_timeout(self.espera)
            dn = p.evaluate(JS_FILAS)
            nuevo = " ".join(dn["paginas"])
            if nuevo == info:
                break
            filas += dn["filas"]
            info = nuevo
        return filas, info, html

    def cerrar(self) -> None:
        try:
            self._nav.close()
        finally:
            self._pw.stop()


def _instalar_navegador() -> None:
    import subprocess
    subprocess.run([sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"], check=False,
                   capture_output=True)


def procesar_dia(d: date, raiz: Path, archivo: Archivo, app: Aplicacion) -> dict:
    informe = {"fecha": d.isoformat(), "alertas": []}
    filas, paginas, html = app.buscar(d)
    m = RE_PAGINAS.search(paginas)
    total = int(m.group("total")) if m else None
    anuncios = [x for x in leer_filas(filas) if x["fecha_texto"] == f"{d:%d/%m/%Y}"]
    if not anuncios:
        if total not in (None, 0) or filas:
            informe["resultado"] = "error_formato"
            informe["alertas"].append(f"BOP Almería {d}: {len(filas)} filas sin anuncios legibles ({paginas})")
        else:
            informe["resultado"] = "sin_boletin"
        return informe
    captura = archivo.guardar(FUENTE, d, html, f"{APP}#fecha={d.isoformat()}", "html", 200, {})
    filas_d = [{**x, "id": f"BOPALMERIA-{x['numero_edicto'].split('-')[1]}-{x['numero_edicto'].split('-')[0]}",
                "fecha": d.isoformat(), "fuente": SIGLAS, "captura_sha256": captura["sha256"]} for x in anuncios]
    for x in filas_d:
        x.pop("fecha_texto", None)
    empleo = seleccionar(filas_d)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), filas_d)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    numeros = sorted({x["boletin"] for x in filas_d if x.get("boletin")})
    informe.update({"resultado": "ok", "numero": ",".join(numeros) or None, "sha256": captura["sha256"],
                    "disposiciones": len(filas_d), "empleo_publico": len(empleo), "anuncios": total})
    if total is not None and total != len(filas):
        informe["alertas"].append(f"BOP Almería {d}: {len(filas)} anuncios leídos de {total}")
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
            lambda c, x: {"titulo": x.get("titulo"), **{k: v for k, v in texto_disposicion(
                c, x.get("tipo_acto") in CON_TEXTO).items() if k != "titulo"}},
            archivo, FUENTE, a.max_minutos, a.pausa, accept="application/pdf", ext="pdf", por_registro=True)
        print(f"BOP Almería textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        return 0

    inicio, informes, freno = time.monotonic(), [], Freno()
    app = None
    try:
        d = a.hasta
        while d >= a.desde:  # del más reciente al más antiguo; lo ya hecho no se repite (salvo ayer y hoy)
            ruta = _ruta(a.salida, "dias", d, "json")
            hecho, reintento = estado_dia(ruta)
            if not hecho or d >= hoy - timedelta(days=1):
                if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                    print("Tiempo agotado; se continúa en la siguiente ejecución")
                    break
                try:
                    app = app or Aplicacion()
                    inf = procesar_dia(d, a.salida, archivo, app)
                except Exception as e:  # noqa: BLE001 - la aplicación no respondió: se abre de nuevo en el siguiente
                    inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible",
                           "alertas": [f"BOP Almería {d}: {type(e).__name__}: {str(e)[:200]}"]}
                    if app:
                        try:
                            app.abrir()
                        except Exception:  # noqa: BLE001
                            app.cerrar()
                            app = None
                if not (inf.get("resultado") == "sin_boletin" and d >= hoy):
                    escribir_json(ruta, inf)
                informes.append(inf)
                print(f"BOP Almería {d}: {inf['resultado']} {inf.get('empleo_publico', '')}")
                if freno.anotar(inf, reintento=reintento):
                    break
                time.sleep(a.pausa)
            d -= timedelta(days=1)
    finally:
        if app:
            app.cerrar()
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    for x in alertas[:30]:
        print(" -", x)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
