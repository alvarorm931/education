"""BOP de Castellón: boletines anteriores al carrusel del portal, desde «Boletines anteriores».

Formato verificado el 30/10/2026 desde GitHub (sondas motor/provinciales/sonda_castellon_buscador.py y
sonda_pdf_texto.py):
  - https://bop.dipcas.es/PortalBOP/boletinesAntiguos/ (JSF/PrimeFaces con sesión): el formulario buscadorForm
    busca por fechas (fechaInicialAntiguo_input y fechaFinalAntiguo_input, DD/MM/AAAA) con una petición AJAX del
    botón «Buscar», y la tabla devuelve número, fecha, referencia («B220113») y el PDF del boletín entero
    (api/descargarBoletin?idBoletin=N&idioma=es, que responde 500 si se pide «application/pdf»).
  - Para estos boletines el portal no tiene la lista de anuncios: el sumario del PDF solo nombra las entidades.
    En el cuerpo, cada anuncio empieza por su registro («00089-2022-U») tras la sección bilingüe
    («ADMINISTRACIÓ LOCAL / ADMINISTRACIÓN LOCAL», «AJUNTAMENTS / AYUNTAMIENTOS») y la entidad, en mayúsculas,
    antes del registro (la Diputación) o justo después (los ayuntamientos). El asunto es la primera frase del
    anuncio tras la entidad, el subapartado («PERSONAL») y el expediente; con él se selecciona y se clasifica.
  - robots.txt no responde; se lee como boletín oficial (motor/http.py).

Uso: python -m motor.provinciales.bopcastellon_antiguos --max-minutos 30 --salida ruta/
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin

import requests

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import Freno, escribir_json, escribir_jsonl
from motor.boe.clasificar import normalizar
from motor.extraccion.citas import citas
from motor.http import USER_AGENT, obtener
from motor.limpieza import RE_DOCUMENTO, limpiar_texto, titulo_sin_nombres
from motor.provinciales import bopcastellon as cs
from motor.provinciales.comun import CON_TEXTO
from motor.provinciales.sonda_dival import campos_formulario

ANTIGUOS = cs.WEB + "/PortalBOP/boletinesAntiguos/"
INICIO = date(2022, 1, 1)
AJAX = {"Faces-Request": "partial/ajax", "X-Requested-With": "XMLHttpRequest", "Referer": ANTIGUOS}
RE_FILA = re.compile(r'<tr data-ri="\d+"[^>]*>(.*?)</tr>', re.DOTALL)
RE_CELDA = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)
RE_PDF = re.compile(r"api/descargarBoletin\?idBoletin=(\d+)")
RE_VIEWSTATE = re.compile(r'<update id="[^"]*ViewState[^"]*"><!\[CDATA\[([^\]]+)\]\]>')
RE_REGISTRO = re.compile(r"^\d{5}-\d{4}(?:-[A-Z])?$")
RE_RUIDO = re.compile(r"^(?:B\.O\.P\s?\.?\s*DE CASTELL[ÓO]N.*|N[úu]m\.\s*\d+.*\d{4}|\d{1,4}|CVE:.*|.*Documento firmado.*)$",
                      re.IGNORECASE)
RE_EXPEDIENTE = re.compile(r"^(?:N\.?\s?º\s+de\s+expediente|Expediente|Expte\.?|Exp\.)", re.IGNORECASE)
TIPOS_ANUNCIO = {"edicto", "edicte", "anuncio", "anunci", "decreto", "decret", "resolucion", "resolucio"}


def _t(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())


def lista(x: str) -> list[dict]:
    out = []
    for f in RE_FILA.findall(x):
        celdas = [_t(c) for c in RE_CELDA.findall(f)]
        m = RE_PDF.search(f)
        fecha = re.match(r"(\d{2})/(\d{2})/(\d{4})", celdas[1]) if len(celdas) > 1 else None
        if m and fecha and celdas[0].isdigit():
            out.append({"numero": int(celdas[0]), "fecha": f"{fecha.group(3)}-{fecha.group(2)}-{fecha.group(1)}",
                        "referencia": celdas[2] if len(celdas) > 2 else None,
                        "url_pdf": f"{cs.WEB}/PortalBOP/api/descargarBoletin?idBoletin={m.group(1)}&idioma=es"})
    return out


def _mayusculas(lin: str) -> bool:
    letras = [c for c in lin if c.isalpha()]
    return len(letras) >= 3 and all(c.isupper() for c in letras)


def _castellano(lin: str) -> str:
    return lin.split(" / ", 1)[1].strip() if " / " in lin else lin.strip()


SECCIONES = ("administracion", "ayuntamientos", "a yuntamientos", "mancomunidades", "consorcios", "entidades",
             "otras entidades", "anuncios")


def _es_seccion(lin: str) -> bool:
    return normalizar(_castellano(lin)).startswith(SECCIONES)


def _seccion(lin: str) -> str:
    return _castellano(lin).replace("A YUNTAMIENTOS", "AYUNTAMIENTOS")


def anuncios(paginas: list[str]) -> list[dict]:
    """Anuncios del cuerpo (de la página 2 en adelante): sección, entidad, asunto y texto, en el orden del boletín."""
    lineas: list[str] = []
    for p in paginas[1:]:
        for l in p.splitlines():
            l = " ".join(l.split())
            if not l or RE_RUIDO.match(l):
                continue
            if lineas and _mayusculas(lineas[-1]) and lineas[-1].endswith("/") and _mayusculas(l):
                lineas[-1] = f"{lineas[-1]} {l}"  # «ADMINISTRACIÓ AUTONÒMICA /» + «ADMINISTRACIÓN AUTONÓMICA»
                continue
            lineas.append(l)
    bloques, seccion, entidad, actual = [], None, None, None
    for k, lin in enumerate(lineas):
        if RE_REGISTRO.match(lin):
            actual = {"registro": lin, "seccion": seccion, "entidad": entidad, "lineas": []}
            bloques.append(actual)
            continue
        siguiente = lineas[k + 1] if k + 1 < len(lineas) else ""
        cabecera = _mayusculas(lin) and " / " in lin and (RE_REGISTRO.match(siguiente) or _mayusculas(siguiente))
        if cabecera or actual is None:
            if _mayusculas(lin):
                if _es_seccion(lin):
                    seccion, entidad = _seccion(lin), None
                elif " / " in lin or actual is None:
                    entidad = _castellano(lin)
            if cabecera:
                actual = None
            continue
        actual["lineas"].append(lin)
    resultado = []
    for b in bloques:
        ls, i, entidad, sub = b["lineas"], 0, b["entidad"], None
        local_ayto = normalizar(b["seccion"] or "").startswith(("ayuntamientos", "a yuntamientos"))
        if ls and _mayusculas(ls[0]) and local_ayto:
            entidad, i = _castellano(ls[0]), 1
        while i < len(ls) and (_mayusculas(ls[i]) or RE_EXPEDIENTE.match(ls[i])):
            if _mayusculas(ls[i]) and normalizar(ls[i]) not in TIPOS_ANUNCIO and sub is None and not local_ayto:
                sub = ls[i]
            i += 1
        frase: list[str] = []
        for n, lin in enumerate(ls[i:], i):
            frase.append(lin)
            sig = ls[n + 1] if n + 1 < len(ls) else ""
            # Fin del asunto: punto o dos puntos, o una línea corta que no sigue a una línea entera (asunto de una
            # sola línea seguido de «Recursos Humanos», «Personal»…)
            if lin.endswith((".", ":")) or sum(len(x) for x in frase) > 260 or (len(sig) < 30 and len(lin) < 90):
                break
        titulo = " ".join(" ".join(frase).split()).strip()
        if sub and len(sub) < 60:
            titulo = f"{sub.capitalize()}. {titulo}"
        resultado.append({"numero_anuncio": b["registro"], "seccion": b["seccion"], "grupo": b["seccion"],
                          "entidad": entidad, "titulo": titulo_sin_nombres(titulo[:400]), "texto": "\n".join(ls)})
    return resultado


def es_local(x: dict) -> bool:
    s = normalizar(x.get("seccion") or "")
    return s.startswith(("administracion local", "ayuntamientos", "mancomunidades", "consorcios", "entidades"))


def convocante(x: dict) -> dict | None:
    e = x.get("entidad") or ""
    if normalizar(e).startswith(("diputacion", "diputacio")):
        return cs.convocante({"grupo": "Diputación Provincial", "entidad": None})
    return cs.convocante({"grupo": None, "entidad": e if normalizar(e).startswith("ayuntamiento") else
                          f"Ayuntamiento de {e.title()}" if e else None})


def procesar(b: dict, raiz: Path, archivo: Archivo) -> dict:
    from motor.autonomicos.comun import clasificar, es_empleo_estricto
    from motor.provinciales.textos import paginas_pdf

    d = date.fromisoformat(b["fecha"])
    r = obtener(b["url_pdf"], accept="*/*")
    inf = {"fecha": b["fecha"], "numero": b["numero"], "status": r.status, "origen": "boletines_anteriores",
           "alertas": []}
    if r.status != 200 or r.contenido[:4] != b"%PDF":
        inf["resultado"] = "error_http"
        inf["alertas"].append(f"BOP Castellón {d}: PDF HTTP {r.status}")
        return inf
    captura = archivo.guardar(cs.FUENTE, d, r.contenido, b["url_pdf"], "pdf", r.status, r.cabeceras)
    lista_a = anuncios(paginas_pdf(r.contenido))
    filas = [{**{k: v for k, v in x.items() if k != "texto"}, "id": f"BOPCASTELLON-{x['numero_anuncio']}",
              "fecha": b["fecha"], "boletin": b["numero"], "url_pdf_boletin": b["url_pdf"], "fuente": cs.SIGLAS,
              "captura_sha256": captura["sha256"]} for x in lista_a]
    empleo = []
    for x, a in zip(filas, lista_a):
        if es_empleo_estricto(x["titulo"]):
            local = es_local(x)
            empleo.append((a, {**x, "ambito": "local" if local else "otro", **clasificar(x["titulo"]),
                               "convocante": convocante(x) if local else None}))
    escribir_jsonl(cs._ruta(raiz, "disposiciones", b["fecha"], b["numero"]), filas)
    escribir_jsonl(cs._ruta(raiz, "oposiciones", b["fecha"], b["numero"]), [x for _, x in empleo])
    for a, x in empleo:
        bruto = a["texto"]
        if x.get("tipo_acto") in CON_TEXTO:
            datos = {"titulo": x["titulo"], **limpiar_texto(bruto)}
        else:
            datos = {"titulo": x["titulo"], "texto": None, "tablas": [], "solo_recuento": True,
                     "lineas_con_documento_de_identidad": sum(1 for l in bruto.splitlines() if RE_DOCUMENTO.search(l)),
                     "citas": citas(bruto)}
        ruta = cs._base(raiz) / "textos" / b["fecha"][:4] / b["fecha"][5:7] / f"{x['id']}.json"
        escribir_json(ruta, {"id": x["id"], **datos, "captura_sha256": captura["sha256"],
                             "capturado": captura["capturado"], "url": b["url_pdf"]})
    inf.update({"resultado": "ok", "sha256": captura["sha256"], "disposiciones": len(filas),
                "empleo_publico": len(empleo), "textos": len(empleo)})
    if not filas:
        inf["alertas"].append(f"BOP Castellón {d}: sin anuncios en el cuerpo (posible cambio de formato)")
    return inf


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    base = cs._base(a.salida)
    # Hasta dónde llega lo ya cargado por el carrusel: lo anterior a su primer boletín
    dias = sorted((base / "boletines").glob("*/*/*.json"))
    hasta = date.fromisoformat(f"{dias[0].parts[-3]}-{dias[0].parts[-2]}-{dias[0].name[:2]}") - timedelta(days=1) \
        if dias else date.today()
    ruta_hist = base / "antiguos.json"
    hist = json.loads(ruta_hist.read_text(encoding="utf-8")) if ruta_hist.exists() else {"tramos_completos": []}
    completos = set(hist["tramos_completos"])
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    r = obtener(ANTIGUOS, accept="text/html", sesion=s)
    try:
        accion, campos = campos_formulario(r.contenido.decode("utf-8", errors="replace"), "buscadorForm")
    except AttributeError:
        print("::warning::BOP Castellón anteriores: sin formulario de búsqueda (posible cambio de formato)")
        return 1
    url = urljoin(r.url or ANTIGUOS, accion)
    inicio, informes, freno, parar = time.monotonic(), [], Freno(), False
    while hasta >= INICIO and not parar:
        desde = max(hasta.replace(day=1), INICIO)
        clave = f"{desde}/{hasta}"
        if clave not in completos:
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                break
            time.sleep(a.pausa)
            datos = {**campos, "buscadorForm:fechaInicialAntiguo_input": f"{desde:%d/%m/%Y}",
                     "buscadorForm:fechaFinalAntiguo_input": f"{hasta:%d/%m/%Y}",
                     "javax.faces.partial.ajax": "true", "javax.faces.source": "buscadorForm:j_idt152",
                     "javax.faces.partial.execute": "@all", "buscadorForm:j_idt152": "buscadorForm:j_idt152",
                     "javax.faces.partial.render": "formListBoletinAntiguos formListAnunciosBolAnt buscadorForm"}
            rr = obtener(url, accept="application/xml", sesion=s, formulario=datos, cabeceras_extra=AJAX)
            x = rr.contenido.decode("utf-8", errors="replace")
            if (vs := RE_VIEWSTATE.search(x)):
                campos["javax.faces.ViewState"] = vs.group(1)
            boletines = lista(x) if rr.status == 200 else []
            if rr.status != 200:
                print(f"::warning::BOP Castellón anteriores {clave}: HTTP {rr.status}")
                break
            bien = 0
            for b in sorted(boletines, key=lambda b: b["fecha"], reverse=True):
                ruta = cs._ruta(a.salida, "boletines", b["fecha"], b["numero"], "json")
                if ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("resultado") == "ok":
                    bien += 1
                    continue
                if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                    parar = True
                    break
                time.sleep(a.pausa)
                try:
                    inf = procesar(b, a.salida, archivo)
                except (ConnectionError, TimeoutError) as e:
                    inf = {"fecha": b["fecha"], "resultado": "fuente_inaccesible", "alertas": [str(e)]}
                escribir_json(ruta, inf)
                informes.append(inf)
                bien += inf["resultado"] == "ok"
                print(f"BOP Castellón {b['fecha']} (anterior): {inf['resultado']} {inf.get('empleo_publico', '')}")
                if freno.anotar(inf):
                    parar = True
                    break
            if boletines and bien == len(boletines):
                completos.add(clave)
        hasta = desde - timedelta(days=1)
    escribir_json(ruta_hist, {"tramos_completos": sorted(completos)})
    print(f"BOP Castellón anteriores: {len(informes)} boletines procesados")
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
