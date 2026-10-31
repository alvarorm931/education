"""Conector del Butlletí Oficial de la Província de València (BOP de Valencia).

Formato verificado el 29/10/2026 desde GitHub: portal JSF/PrimeFaces con sesión (bop.dival.es).
  - GET https://bop.dival.es/bop/xhtml/portal.xhtml abre la sesión y da el formulario de búsqueda (j_idt131) con
    las fechas «Des de» / «Fins a» (filtroCalendarioIni_input / filtroCalendarioFin_input, dd/mm/aaaa).
  - Búsqueda: POST AJAX del botón «buscarBtn»; la respuesta parcial trae el listado en <update id="edictos">,
    25 anuncios por página, «Mostrant del 1 al 25 de 41».
  - Página siguiente: POST AJAX de la rejilla «list» (list_pagination, list_first, list_rows) en su formulario.
  - Cada anuncio: sección («Municipis», «Diputació»...), entidad («Ajuntament d'Agullent»), título, número de
    registro (2026/12998), fecha y número de boletín. Los identificadores j_idt del portal se leen de la página.
  - Texto: PDF estable https://bop.dival.es/bop/downloads?anuncioNumReg=2026/12998&lang=va (sin sesión).
  - Los anuncios van en valenciano (lang=va) y muchos también en castellano dentro del PDF.

Uso:
  python -m motor.provinciales.bopvalencia --salida ruta/                                   # ayer y hoy
  python -m motor.provinciales.bopvalencia --desde 2022-01-01 --max-minutos 30 --salida ruta/
  python -m motor.provinciales.bopvalencia --textos --max-minutos 30 --salida ruta/
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import (Freno, clasificar, convocante_de_organismo, descargar_textos,
                                     es_empleo_estricto, escribir_json, escribir_jsonl, leer_jsonl, estado_dia)
from motor.boe.clasificar import normalizar
from motor.http import obtener, sesion_tls_compatible
from motor.provinciales.comun import CON_TEXTO, texto_pdf

FUENTE = "bopvalencia"
SIGLAS = "BOP-VALENCIA"
MADRID = ZoneInfo("Europe/Madrid")
PORTAL = "https://bop.dival.es/bop/xhtml/portal.xhtml"
DESCARGA = "https://bop.dival.es/bop/downloads?anuncioNumReg={reg}&lang=va"
POR_PAGINA = 25
NOMBRES = ("Butlletí Oficial de la Província de València", "Boletín Oficial de la Provincia de Valencia",
           "BOPV", "Butlletí Oficial de la Província", "Boletín Oficial de la Provincia")
SECCIONES_LOCALES = {"municipis", "diputacio", "organismes autonoms", "mancomunitats municipals"}
RE_CABECERA_PDF = re.compile(
    r"^(?:N[úu]m\. \d+|P[àa]g\.|\d{2}-\d{2}-\d{4} \d+|(?:[A-ZÀÈÉÍÒÓÚ] ){3,}[A-ZÀÈÉÍÒÓÚ]|"
    r"Verificable a https://bop\.dival\.es/bop|CSV: BOPV-\d{4}/\d+)$")

RE_CELDA = re.compile(r'class="ui-datagrid-column[^"]*">(?P<c>.*?)(?=class="ui-datagrid-column|</div></div></div>\]\]>|$)',
                      re.DOTALL)
RE_SECCION = re.compile(r'seccion seccion-\d+"[^>]*>\s*<div[^>]*>(?:<a[^>]*>.*?</a>)?(?P<s>[^<]+)</div>', re.DOTALL)
RE_ENTIDAD = re.compile(r'entidad entidad-[\w-]+"[^>]*>\s*<div[^>]*>(?P<e>[^<]+)</div>', re.DOTALL)
RE_TITULO = re.compile(r'title="Anunci en PDF">(?P<t>[^<]+)</a>')
RE_REGISTRO = re.compile(r"Núm\. registre: </span>(?P<r>\d{4}/\d+)")
RE_FECHA = re.compile(r'title="Butlletí complet">(?P<d>\d{2})/(?P<m>\d{2})/(?P<a>\d{4})</span>')
RE_BOLETIN = re.compile(r'Butlletí: </span><a[^>]*>(?P<n>\d+)</a>')
RE_TOTAL = re.compile(r"Mostrant del (?P<del>\d+) al \d+ de (?P<n>\d+)")
RE_SIN_RESULTADOS = re.compile(r"trobat resultats|encontrado resultados|datagrid-empty|Mostrant del 0 al 0", re.IGNORECASE)
RE_VIEWSTATE = re.compile(r'<update id="[^"]*javax\.faces\.ViewState[^"]*"><!\[CDATA\[(?P<v>[^\]]+)\]\]>')
RE_REJILLA = re.compile(r'PrimeFaces\.cw\("DataGrid","\w+",\{id:"(?P<id>[^"]+)"[^}]*paginator')
RE_FORM_REJILLA = re.compile(
    r'<form id="(?P<f>[^"]+)"[^>]*>\s*<input type="hidden" name="(?P=f)" value="(?P=f)" />\s*<div id="(?P<r>[^"]+)"'
    r'[^>]*ui-datagrid')


class ErrorPortal(Exception):
    pass


def _texto(s: str) -> str:
    return " ".join(html.unescape(s).split())


def parsear_listado(fragmento: str) -> list[dict]:
    """Anuncios de un listado (respuesta de búsqueda o de página)."""
    anuncios = []
    for m in RE_CELDA.finditer(fragmento):
        c = m.group("c")
        t, r = RE_TITULO.search(c), RE_REGISTRO.search(c)
        if not (t and r):
            continue
        s, e, f, b = RE_SECCION.search(c), RE_ENTIDAD.search(c), RE_FECHA.search(c), RE_BOLETIN.search(c)
        reg = r.group("r")
        anuncios.append({
            "id": f"BOPVALENCIA-{reg.replace('/', '-')}", "registro": reg,
            "seccion": _texto(s.group("s")) if s else None, "organismo": _texto(e.group("e")) if e else None,
            "titulo": _texto(t.group("t")), "fecha": f"{f.group('a')}-{f.group('m')}-{f.group('d')}" if f else None,
            "boletin": b.group("n") if b else None, "url_pdf": DESCARGA.format(reg=reg), "url_html": None,
            "fuente": SIGLAS,
        })
    return list({a["id"]: a for a in anuncios}.values())


def campos_formulario(pagina: str, form_id: str) -> tuple[str, dict]:
    i = pagina.find(f'<form id="{form_id}"')
    if i < 0:
        raise ErrorPortal(f"sin formulario {form_id}: posible cambio de formato")
    j = pagina.find("</form>", i)
    f = pagina[i:j]
    accion = html.unescape(re.search(r'action="([^"]+)"', f).group(1))
    campos = {}
    for m in re.finditer(r"<input\b[^>]*>", f):
        t = m.group(0)
        n = re.search(r'name="([^"]+)"', t)
        if not n or 'type="checkbox"' in t:
            continue
        v = re.search(r'value="([^"]*)"', t)
        campos[html.unescape(n.group(1))] = html.unescape(v.group(1)) if v else ""
    for m in re.finditer(r'<select\b[^>]*name="([^"]+)"', f):
        campos.setdefault(m.group(1), "")
    return accion, campos


class Portal:
    """Sesión con el portal: abre, busca un intervalo de fechas y recorre las páginas del resultado."""

    CABECERAS = {"Faces-Request": "partial/ajax", "X-Requested-With": "XMLHttpRequest",
                 "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}

    def __init__(self, pausa: float = 1.0):
        self.sesion = sesion_tls_compatible()
        self.pausa = pausa
        self.abrir()

    def abrir(self) -> None:
        r = obtener(PORTAL, accept="text/html", sesion=self.sesion)
        if r.status != 200:
            raise ErrorPortal(f"portal HTTP {r.status}")
        pagina = r.contenido.decode("utf-8", errors="replace")
        self.form_busqueda = re.search(r'onclick="PrimeFaces\.ab\(\{s:&quot;buscarBtn&quot;,f:&quot;(\w+)&quot;', pagina)
        if not self.form_busqueda:
            raise ErrorPortal("sin botón de búsqueda: posible cambio de formato")
        accion, self.campos = campos_formulario(pagina, self.form_busqueda.group(1))
        self.url = urljoin(PORTAL, accion)
        self.viewstate = self.campos.get("javax.faces.ViewState")

    def _post(self, datos: dict):
        time.sleep(self.pausa)
        r = obtener(self.url, accept="application/xml", sesion=self.sesion, formulario=datos,
                    cabeceras_extra={**self.CABECERAS, "Referer": PORTAL})
        texto = r.contenido.decode("utf-8", errors="replace")
        if r.status != 200 or "<partial-response" not in texto:
            raise ErrorPortal(f"respuesta no reconocida (HTTP {r.status})")
        v = RE_VIEWSTATE.search(texto)
        if v:
            self.viewstate = v.group("v")
        return r, texto

    def buscar(self, desde: date, hasta: date) -> tuple[list[dict], int, list]:
        datos = dict(self.campos)
        datos.update({
            "filtroCalendarioIni_input": f"{desde:%d/%m/%Y}", "filtroCalendarioFin_input": f"{hasta:%d/%m/%Y}",
            "javax.faces.ViewState": self.viewstate, "javax.faces.partial.ajax": "true",
            "javax.faces.source": "buscarBtn", "javax.faces.partial.execute": "@all",
            "javax.faces.partial.render": "messages boletines3 edictos", "buscarBtn": "buscarBtn",
        })
        r, texto = self._post(datos)
        respuestas = [r]
        anuncios = parsear_listado(texto)
        m = RE_TOTAL.search(texto)
        total = int(m.group("n")) if m else len(anuncios)
        rejilla, form = RE_REJILLA.search(texto), RE_FORM_REJILLA.search(texto)
        paginas = math.ceil(total / POR_PAGINA)
        # La rejilla recuerda la página de la búsqueda anterior de la misma sesión: tras un día de varias páginas,
        # la búsqueda del siguiente salía por la segunda («Mostrant del 26 al…») y se perdían los 25 primeros
        # (1.132 días del histórico, del 30/10/2026). Si no empieza por el 1, se pide también la primera.
        desde_primera = not m or m.group("del") == "1"
        if not desde_primera:
            anuncios = []
        for k in range(0 if not desde_primera else 1, paginas):
            if not (rejilla and form):
                raise ErrorPortal("sin rejilla paginable: posible cambio de formato")
            lid, fid = rejilla.group("id"), form.group("f")
            r, texto = self._post({
                fid: fid, "javax.faces.ViewState": self.viewstate, "javax.faces.partial.ajax": "true",
                "javax.faces.source": lid, "javax.faces.partial.execute": lid, "javax.faces.partial.render": lid,
                f"{lid}_pagination": "true", f"{lid}_first": str(k * POR_PAGINA), f"{lid}_rows": str(POR_PAGINA),
                f"{lid}_encodeFeature": "true"})
            respuestas.append(r)
            anuncios += parsear_listado(texto)
        return list({a["id"]: a for a in anuncios}.values()), total, respuestas


def seleccionar(anuncios: list[dict]) -> list[dict]:
    out = []
    for x in anuncios:
        if normalizar(x.get("seccion") or "") not in SECCIONES_LOCALES:
            continue
        t = x["titulo"]
        if not es_empleo_estricto(t):
            continue
        org = (x.get("organismo") or "").split(" / ")[0]
        conv = convocante_de_organismo(org)
        if conv and not conv.get("provincia"):
            conv["provincia"] = "Valencia"
        out.append({**x, "ambito": "local", **clasificar(t, x.get("seccion")), "convocante": conv})
    return out


def _base(raiz: Path) -> Path:
    return raiz / "datos" / "provinciales" / FUENTE


def _ruta(raiz: Path, carpeta: str, d: date, ext: str = "jsonl") -> Path:
    return _base(raiz) / carpeta / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.{ext}"


def procesar_dia(d: date, raiz: Path, archivo: Archivo, portal: Portal) -> dict:
    informe = {"fecha": d.isoformat(), "alertas": []}
    anuncios, total, respuestas = portal.buscar(d, d)
    for r in respuestas:
        archivo.guardar(FUENTE, d, r.contenido, portal.url, "xml", r.status, r.cabeceras)
    if total == 0:
        # Solo si el portal dice que no hay resultados. El 30-31/10/2026 devolvió respuestas vacías al releer cientos
        # de días seguidos, y se daban por días sin boletín (casi todo 2022-2025, ver reparar_dias)
        if not any(RE_SIN_RESULTADOS.search(r.contenido.decode("utf-8", errors="replace")) for r in respuestas):
            raise ErrorPortal("respuesta sin anuncios y sin el aviso de que no hay resultados")
        # con el aviso del portal: reparar_dias no lo vuelve a pedir
        informe.update({"resultado": "sin_boletin", "confirmado": True})
        return informe
    del_dia = [a for a in anuncios if a["fecha"] == d.isoformat()]
    if len(del_dia) != len(anuncios):
        informe["alertas"].append(f"BOP Valencia {d}: {len(anuncios) - len(del_dia)} anuncios de otra fecha")
    empleo = seleccionar(del_dia)
    escribir_jsonl(_ruta(raiz, "disposiciones", d), del_dia)
    escribir_jsonl(_ruta(raiz, "oposiciones", d), empleo)
    informe.update({"resultado": "ok", "anuncios": total, "disposiciones": len(del_dia), "empleo_publico": len(empleo),
                    "boletin": next((a["boletin"] for a in del_dia if a.get("boletin")), None)})
    if len(anuncios) != total:
        informe["alertas"].append(f"BOP Valencia {d}: {len(anuncios)} anuncios leídos de {total}")
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


def incompleto(ruta: Path) -> bool:
    """Día dado por leído con menos anuncios de los que dice el portal («25 anuncios leídos de 50»)."""
    try:
        return any("anuncios leídos de" in a for a in json.loads(ruta.read_text(encoding="utf-8")).get("alertas") or [])
    except (OSError, ValueError):
        return False


def restaurado(ruta: Path) -> bool:
    """Día devuelto a «ok» por reparar_dias con los anuncios que ya había: la lectura de entonces pudo quedarse a
    medias (paginación) y el aviso «N anuncios leídos de M» se perdió al darlo por sin boletín."""
    try:
        return (json.loads(ruta.read_text(encoding="utf-8")).get("nota") or "").startswith("restaurado")
    except (OSError, ValueError):
        return False


def reparar_dias(raiz: Path) -> tuple[int, int]:
    """Días entre semana dados por «sin boletín» sin el aviso del portal (respuestas vacías del 30-31/10/2026): si
    ya se habían leído (sus anuncios siguen en disposiciones/), vuelven a «ok»; si no, se borra el informe y se
    vuelven a pedir. Devuelve (restaurados, por releer)."""
    restaurados = releer = 0
    for f in sorted((_base(raiz) / "dias").glob("*/*/*.json")):
        try:
            inf = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if inf.get("resultado") != "sin_boletin" or inf.get("nota") or inf.get("confirmado"):
            continue
        d = date.fromisoformat(inf["fecha"])
        if d.weekday() >= 5:
            continue
        disp = _ruta(raiz, "disposiciones", d)
        if disp.exists():
            filas = leer_jsonl(disp)
            empleo = leer_jsonl(_ruta(raiz, "oposiciones", d)) if _ruta(raiz, "oposiciones", d).exists() else []
            escribir_json(f, {"fecha": d.isoformat(), "resultado": "ok", "anuncios": len(filas),
                              "disposiciones": len(filas), "empleo_publico": len(empleo),
                              "boletin": next((x.get("boletin") for x in filas if x.get("boletin")), None),
                              "nota": "restaurado: leído antes y luego dado por sin boletín por una respuesta vacía",
                              "alertas": []})
            restaurados += 1
        else:
            f.unlink()
            releer += 1
    return restaurados, releer


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
            lambda c, x: texto_disposicion(c, x.get("tipo_acto") in CON_TEXTO), archivo, FUENTE, a.max_minutos,
            a.pausa, accept="application/pdf", ext="pdf", por_registro=True)
        print(f"BOP Valencia textos: {hechos} descargados, {errores} errores, {len(pend) - hechos} pendientes")
        return 0

    restaurados, releer = reparar_dias(a.salida)
    if restaurados or releer:
        print(f"::notice title=BOP Valencia::{restaurados} días restaurados (ya leídos) y {releer} por releer, "
              "que estaban como sin boletín por respuestas vacías del portal")
    inicio, informes, portal = time.monotonic(), [], None
    freno = Freno()
    d = a.hasta
    while d >= a.desde:  # del más reciente al más antiguo; lo ya hecho no se repite (salvo ayer y hoy)
        ruta = _ruta(a.salida, "dias", d, "json")
        hecho, reintento = estado_dia(ruta)
        if hecho and (incompleto(ruta) or restaurado(ruta)):
            # leído a medias por la paginación, o restaurado de una lectura que pudo ser a medias: se vuelve a leer
            # entero (el BOE cita bases de días restaurados con 30-40 anuncios en los que falta el municipio)
            hecho = False
        if d.weekday() >= 5 and not hecho:  # el BOP de Valencia no sale en fin de semana
            escribir_json(ruta, {"fecha": d.isoformat(), "resultado": "sin_boletin", "nota": "fin de semana",
                                 "alertas": []})
            hecho = True
        if not hecho or d >= hoy - timedelta(days=1):
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                break
            try:
                portal = portal or Portal(a.pausa)
                inf = procesar_dia(d, a.salida, archivo, portal)
            except ErrorPortal as e:
                inf = {"fecha": d.isoformat(), "resultado": "error_formato", "alertas": [f"BOP Valencia {d}: {e}"]}
                portal = None  # se abre una sesión nueva para el día siguiente
            except (ConnectionError, TimeoutError) as e:
                inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
                portal = None
            if not (inf.get("resultado") == "sin_boletin" and d >= hoy):
                escribir_json(ruta, inf)
            informes.append(inf)
            if freno.anotar(inf, reintento=reintento):
                break
            print(f"BOP Valencia {d}: {inf['resultado']} {inf.get('empleo_publico', '')}")
        d -= timedelta(days=1)
    alertas = [x for i in informes for x in i.get("alertas", [])]
    print(f"Días procesados: {len(informes)}. Alertas: {len(alertas)}")
    for x in alertas[:30]:
        print(" -", x)
    return 1 if sum(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) > 3 else 0


if __name__ == "__main__":
    sys.exit(main())
