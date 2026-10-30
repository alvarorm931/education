"""BOP de Granada: boletines anteriores al portal nuevo (de 2022 a junio de 2024), en «boletines anteriores».

Formato verificado el 30/10/2026 desde GitHub (sondas motor/provinciales/sonda_saga_antiguos.py y sonda_pdf_texto.py):
  - La página de resultados (/publica/boletines-anteriores/resultados-bop-anteriores/) trae los parámetros del
    listado SAGA (parametrosBase_SagaListado…, con urlAjax). El listado se filtra por año y mes con
    personalizado_bopantiguo.anio_prop_s=2023 y personalizado_bopantiguo.mes.formateado_prop_s=«03 - marzo», 15 por
    página (page=N). La fecha de indexación es la de carga, no la del boletín: por eso se filtra por año y mes.
  - Cada boletín es un PDF entero (…/Boletines-Anteriores/20230331-2023062.pdf: fecha y número). La primera página
    es el sumario a dos columnas: secciones («AYUNTAMIENTOS»), entidad en mayúsculas y asunto separados por «.-»
    («MOTRIL.-Admitidos y excluidos para una plaza de Electricista…… 17»; los asuntos siguientes de la misma
    entidad no la repiten). En el cuerpo, cada anuncio empieza por su número de registro («NÚMERO 380»), en el orden
    del sumario: de ahí sale su texto, si el número de anuncios coincide.
  - robots.txt: el listado y los PDF están permitidos.

Uso: python -m motor.provinciales.bopgranada_antiguos --max-minutos 30 --salida ruta/
     python -m motor.provinciales.bopgranada_antiguos --reprocesar --salida ruta/   # desde el almacén
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import Freno, escribir_json, escribir_jsonl, nombre_propio
from motor.boe.clasificar import normalizar
from motor.extraccion.citas import citas
from motor.http import USER_AGENT, obtener
from motor.limpieza import RE_DOCUMENTO, limpiar_texto
from motor.provinciales import saga
from motor.provinciales.bopgranada import BOLETIN
from motor.provinciales.comun import CON_TEXTO

RESULTADOS = BOLETIN.base + "/publica/boletines-anteriores/resultados-bop-anteriores/"
PRIMER_MES, ULTIMO_MES = (2022, 1), (2024, 6)
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
RE_PARAM = re.compile(r"^\s*(\w+)\s*:\s*(?:'([^']*)'|\"([^\"]*)\"|(true|false|-?\d+))\s*,?\s*$", re.MULTILINE)
RE_PDF = re.compile(r'href="(?P<u>/export/sites/bop/publica/boletines-anteriores/\.galleries/Boletines-Anteriores/'
                    r'(?P<f>\d{8})-(?P<a>\d{4})(?P<n>\d{3,4})\.pdf)"')
RE_PAGINAS = re.compile(r'class="totalPages" value="(\d+)"')
RE_ENTRADA = re.compile(r"^(?P<t>.*?)\s*\.{2,}\s*(?P<p>\d{1,3})\s*$")
RE_ENTIDAD = re.compile(r"^(?P<e>[^a-záéíóúñüç]+?)\.-\s*(?P<t>.+)$")
RE_REGISTRO = re.compile(r"(?m)^\s*N[ÚU]MERO\s+(\d{1,3}(?:\.\d{3})*|\d{4,6})\s*$")  # «NÚMERO 3.456» desde el mil
SECCIONES = {"anuncios oficiales", "administracion de justicia", "ayuntamientos", "anuncios no oficiales",
             "administracion local", "diputacion provincial", "diputacion de granada", "mancomunidades",
             "mancomunidades de municipios", "entidades locales autonomas", "consorcios", "comunidades de regantes",
             "otras entidades", "edictos", "administracion del estado", "administracion autonomica"}
LOCALES = ("ayuntamientos", "administracion local", "diputacion", "mancomunidad", "entidades locales", "consorcios")


def parametros_base(h: str) -> dict:
    i = h.find('parametrosSagaListado["parametrosBase_')
    j = h.find("};", i)
    return {m.group(1): next(g for g in m.groups()[1:] if g is not None) for m in RE_PARAM.finditer(h[i:j])} if i >= 0 else {}


def boletines(contenido: bytes) -> list[dict]:
    vistos = {}
    for m in RE_PDF.finditer(contenido.decode("utf-8", errors="replace")):
        f = m.group("f")
        vistos.setdefault(m.group("u"), {"fecha": f"{f[:4]}-{f[4:6]}-{f[6:]}", "numero": int(m.group("n")),
                                         "url_pdf": BOLETIN.base + m.group("u")})
    return sorted(vistos.values(), key=lambda b: (b["fecha"], b["numero"]))


def _es_seccion(lin: str) -> bool:
    n = normalizar(re.sub(r"\s*P[áa]g\.?\s*$", "", lin)).strip(" .")
    return n in SECCIONES or (lin.rstrip().endswith("Pág.") and lin.upper() == lin)


def sumario(paginas: list[str]) -> tuple[list[dict], int]:
    """Asuntos del sumario y el índice de la primera página del cuerpo (la primera con «NÚMERO 380»)."""
    cuerpo = next((k for k, p in enumerate(paginas) if RE_REGISTRO.search(p)), len(paginas))
    entradas, seccion, entidad, buffer, empezado = [], None, None, [], False
    for texto in paginas[:cuerpo]:
        for linea in texto.splitlines():
            lin = " ".join(linea.split())
            if not lin:
                continue
            if _es_seccion(lin):
                seccion, entidad, buffer, empezado = re.sub(r"\s*P[áa]g\.?\s*$", "", lin).strip(), None, [], True
                continue
            if not empezado:
                continue
            m = RE_ENTRADA.match(lin)
            if not m:
                buffer.append(lin)
                continue
            texto_e = " ".join(buffer + [m.group("t")]).strip()
            buffer = []
            e = RE_ENTIDAD.match(texto_e)
            if e:
                entidad, titulo = " ".join(e.group("e").split()).strip(" ."), e.group("t").strip()
            else:
                titulo = texto_e
            entradas.append({"seccion": seccion, "entidad": entidad, "titulo": titulo.strip(" ."),
                             "pagina": int(m.group("p"))})
    return entradas, cuerpo


def organismo(x: dict) -> str | None:
    e = x.get("entidad")
    if not e:
        return None
    if normalizar(x.get("seccion") or "") == "ayuntamientos" and not normalizar(e).startswith("ayuntamiento"):
        return "Ayuntamiento de " + nombre_propio(e)
    return nombre_propio(e)


def bloques(paginas: list[str], desde: int) -> list[tuple[str, str]]:
    """(número de registro, texto) de cada anuncio del cuerpo, en orden."""
    cuerpo = "\n".join(paginas[desde:])
    marcas = list(RE_REGISTRO.finditer(cuerpo))
    return [(m.group(1), cuerpo[m.start():marcas[k + 1].start() if k + 1 < len(marcas) else len(cuerpo)])
            for k, m in enumerate(marcas)]


VERSION = "antiguos_v2"  # v2 (30/10/2026): registros con punto de millar («NÚMERO 3.456»)


def procesar(b: dict, raiz: Path, archivo: Archivo) -> dict:
    d = date.fromisoformat(b["fecha"])
    r = obtener(b["url_pdf"], accept="application/pdf")
    inf = {"fecha": b["fecha"], "numero": b["numero"], "status": r.status, "origen": "boletines_anteriores",
           "alertas": []}
    if r.status != 200 or r.contenido[:4] != b"%PDF":
        inf["resultado"] = "error_http"
        inf["alertas"].append(f"BOP Granada {d}: PDF HTTP {r.status}")
        return inf
    captura = archivo.guardar(BOLETIN.fuente, d, r.contenido, b["url_pdf"], "pdf", r.status, r.cabeceras)
    return {**inf, **leer_pdf(b, r.contenido, captura, raiz)}


def leer_pdf(b: dict, pdf: bytes, captura: dict, raiz: Path) -> dict:
    from motor.provinciales.textos import paginas_pdf

    d = date.fromisoformat(b["fecha"])
    paginas = paginas_pdf(pdf)
    entradas, desde = sumario(paginas)
    trozos = bloques(paginas, desde)
    casan = len(trozos) == len(entradas)
    filas = []
    for i, x in enumerate(entradas):
        registro = trozos[i][0] if casan else None
        filas.append({**x, "organismo": organismo(x), "numero_anuncio": registro or f"{b['numero']}-{i + 1:03d}",
                      "id": f"BOPGR-{d.year}-{b['numero']}-{i + 1:03d}", "fecha": b["fecha"], "boletin": b["numero"],
                      "url_pdf_boletin": b["url_pdf"], "fuente": BOLETIN.siglas, "captura_sha256": captura["sha256"]})
    empleo = saga.seleccionar(BOLETIN, filas)
    escribir_jsonl(saga._ruta(BOLETIN, raiz, "disposiciones", d), filas)
    escribir_jsonl(saga._ruta(BOLETIN, raiz, "oposiciones", d), empleo)
    inf = {"resultado": "ok", "sha256": captura["sha256"], "capturado": captura.get("capturado"),
           "url_pdf": b["url_pdf"], "version": VERSION, "alertas": []}
    textos = 0
    if casan:
        por_id = {f["id"]: trozos[i][1] for i, f in enumerate(filas)}
        for x in empleo:
            bruto = por_id[x["id"]]
            if x.get("tipo_acto") in CON_TEXTO:
                datos = {"titulo": x["titulo"], **limpiar_texto(bruto, BOLETIN.cabecera_pdf)}
            else:
                datos = {"titulo": x["titulo"], "texto": None, "tablas": [], "solo_recuento": True,
                         "lineas_con_documento_de_identidad": sum(1 for l in bruto.splitlines() if RE_DOCUMENTO.search(l)),
                         "citas": citas(bruto)}
            escribir_json(saga.ruta_texto(BOLETIN, raiz, x), {"id": x["id"], **datos, "captura_sha256": captura["sha256"],
                                                             "capturado": captura.get("capturado"), "url": b["url_pdf"]})
            textos += 1
    elif empleo:
        inf["alertas"].append(f"BOP Granada {d}: {len(entradas)} asuntos y {len(trozos)} anuncios en el cuerpo: "
                              "sin textos")
    inf.update({"disposiciones": len(filas), "empleo_publico": len(empleo), "textos": textos})
    if not filas:
        inf["alertas"].append(f"BOP Granada {d}: sumario sin anuncios (posible cambio de formato)")
    return inf


def reprocesar(raiz: Path) -> int:
    """Vuelve a leer, desde su PDF original en el almacén (sin pedirlo a la fuente), los boletines anteriores ya
    cargados con una versión vieja del lector."""
    from motor.almacen import Almacen, clave_original
    from motor.archivo import almacen_por_defecto
    from motor.autonomicos.comun import leer_jsonl

    base, almacen, hechos, fallos = saga._base(BOLETIN, raiz), None, 0, 0
    for dia in sorted((base / "dias").glob("*/*/*.json")):
        inf = json.loads(dia.read_text(encoding="utf-8"))
        if inf.get("origen") != "boletines_anteriores" or inf.get("resultado") != "ok" or inf.get("version") == VERSION:
            continue
        d = date.fromisoformat(inf["fecha"])
        indice = raiz / "archivo" / "indices" / BOLETIN.fuente / f"{d:%Y-%m}.jsonl"
        reg = next((x for x in (leer_jsonl(indice) if indice.exists() else []) if x.get("sha256") == inf["sha256"]), {})
        try:
            almacen = almacen or almacen_por_defecto() or Almacen()  # en GitHub, credenciales OIDC
            pdf = almacen.leer(reg.get("clave") or clave_original(BOLETIN.fuente, d, inf["sha256"], "pdf"))
        except Exception as e:  # noqa: BLE001 - sin almacén se deja para otra ejecución
            fallos += 1
            if fallos >= 5:
                print(f"BOP Granada: el almacén no responde ({type(e).__name__}); se deja para otra ejecución")
                break
            continue
        b = {"fecha": inf["fecha"], "numero": inf["numero"], "url_pdf": reg.get("url") or inf.get("url_pdf")}
        try:
            nuevo = leer_pdf(b, pdf, {"sha256": inf["sha256"], "capturado": reg.get("capturado")}, raiz)
        except Exception as e:  # noqa: BLE001 - se anota y se sigue con el siguiente
            import traceback
            traceback.print_exc()
            print(f"::warning::BOP Granada {inf['fecha']}: no se pudo releer ({type(e).__name__}: {e})"[:300])
            continue
        escribir_json(dia, {**inf, **nuevo})
        hechos += 1
    print(f"BOP Granada anteriores releídos desde el almacén: {hechos}; sin original: {fallos}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    p.add_argument("--reprocesar", action="store_true", help="releer desde el almacén los ya cargados")
    a = p.parse_args(argv)
    if a.reprocesar:
        return reprocesar(a.salida)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    base = saga._base(BOLETIN, a.salida)
    ruta_hist = base / "antiguos.json"
    hist = json.loads(ruta_hist.read_text(encoding="utf-8")) if ruta_hist.exists() else {"meses_completos": []}
    completos = set(hist["meses_completos"])
    inicio, informes, freno = time.monotonic(), [], Freno()
    sesion = requests.Session()
    sesion.headers["User-Agent"] = USER_AGENT
    r = obtener(RESULTADOS, accept="text/html", sesion=sesion,
                formulario={"busqueda": "", "fechaDesde": "", "fechaHasta": "", "BusquedaInicial": ""})
    params = parametros_base(r.contenido.decode("utf-8", errors="replace"))
    if r.status != 200 or not params.get("urlAjax"):
        print("::warning::BOP Granada anteriores: la página de resultados no trae los parámetros del listado")
        return 1
    url_ajax = BOLETIN.base + params["urlAjax"]
    anio, mes, parar = *ULTIMO_MES, False
    while (anio, mes) >= PRIMER_MES and not parar:
        clave = f"{anio}-{mes:02d}"
        if clave not in completos:
            lista, pagina, total = [], 1, 1
            while pagina <= total:
                if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                    parar = True
                    break
                time.sleep(a.pausa)
                rr = obtener(url_ajax, accept="text/html", sesion=sesion, cabeceras_extra={
                    "X-Requested-With": "XMLHttpRequest", "Referer": RESULTADOS}, formulario={
                    **params, "busquedaActiva": "true", "forma_listar": "busqueda" if pagina == 1 else "carga",
                    "page": str(pagina), "personalizado_bopantiguo.anio_prop_s": str(anio),
                    "personalizado_bopantiguo.mes.formateado_prop_s": f"{mes:02d} - {MESES[mes - 1]}"})
                if rr.status != 200:
                    print(f"::warning::BOP Granada anteriores {clave}: HTTP {rr.status}")
                    parar = True
                    break
                lista += boletines(rr.contenido)
                t = RE_PAGINAS.search(rr.contenido.decode("utf-8", errors="replace"))
                total = int(t.group(1)) if t else 1
                pagina += 1
            if parar:
                break
            lista = list({x["url_pdf"]: x for x in lista}.values())
            if not lista:
                print(f"::warning::BOP Granada anteriores {clave}: el listado no trae boletines")
            bien = 0
            for b in sorted(lista, key=lambda x: x["fecha"], reverse=True):
                ruta = saga._ruta(BOLETIN, a.salida, "dias", date.fromisoformat(b["fecha"]), "json")
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
                except Exception as e:  # noqa: BLE001 - un PDF raro no para la carga: queda anotado para revisarlo
                    import traceback
                    traceback.print_exc()
                    inf = {"fecha": b["fecha"], "numero": b["numero"], "resultado": "error_formato",
                           "alertas": [f"BOP Granada {b['fecha']}: {type(e).__name__}: {e}"[:300]]}
                escribir_json(ruta, inf)
                informes.append(inf)
                bien += inf["resultado"] == "ok"
                print(f"BOP Granada {b['fecha']} (anterior): {inf['resultado']} {inf.get('empleo_publico', '')} "
                      f"{'; '.join(inf.get('alertas') or [])}")
                if freno.anotar(inf):
                    parar = True
                    break
            if lista and bien == len(lista):
                completos.add(clave)
        anio, mes = (anio, mes - 1) if mes > 1 else (anio - 1, 12)
    escribir_json(ruta_hist, {"meses_completos": sorted(completos)})
    print(f"BOP Granada anteriores: {len(informes)} boletines procesados")
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
