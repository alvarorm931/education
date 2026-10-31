"""Memorias de verificación de los grados publicadas en las webs de las universidades.

El plan de muchos grados no se puede comprobar con el BOE, porque se publicó solo por materias o sin el carácter
de cada asignatura. Ese plan está en la memoria de verificación, pero el RUCT solo responde desde el servidor de
España, de una lectura en una, y tarda unos 10 segundos por página: 1.020 memorias son más de una semana (§5 de
`docs/modelo-grados.md`). Muchas universidades publican en su web el PDF que genera la aplicación del Ministerio
con la solicitud de verificación. Lleva el código del título en la cabecera de cada página («Identificador :
2501234») y el plan entero: módulos (nivel 1), materias (nivel 2) y asignaturas (nivel 3), con carácter, ECTS y
despliegue por semestres.

1. `cc`: busca en el índice en columnas de Common Crawl las URL de PDF de los dominios de las universidades cuya
   ruta habla de memoria o de verificación. Solo lee metadatos de URL, como `cc_precios`.
2. `leer`: pide esos PDF con robots.txt (una petición por segundo y servidor), guarda el original con su huella y
   saca de cada uno el código del título, la fecha y el plan, con la misma forma que la memoria leída del RUCT
   (`ruct_grados.leer_plan_memoria`). Qué versión vale y si el plan cuadra con los créditos por tipo del RUCT se
   decide al hacer las fichas, no aquí.

Uso:
  python -m motor.grados.memorias_web cc --archivos 0:20 --salida out
  python -m motor.grados.memorias_web leer --urls entrada/ --parte 0/8 --max-minutos 48 --salida out
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import time
import unicodedata
from datetime import date
from pathlib import Path

from motor.archivo import Archivo, solo_huella_por_defecto

DOMINIOS = Path(__file__).with_name("dominios_universidades.json")
FUENTE = "web-centros"  # mismo almacén que las listas de precios: el flujo no lo sube a la rama pública
MAX_PDF = 40_000_000

# Fichero con «memoria», «memòria» o «verifica…» en el nombre, o dentro de una carpeta que se llama así
INCLUIR = r"(?i)(/[^/]*(memori|mem%c3%b2ri|verifica)[^/]*\.pdf$|/(memori|mem%c3%b2ri|verifica)[^/]*/[^/]*\.pdf$)"
# memorias que no son de un grado (másters, doctorados, memorias anuales, económicas, de actividades…)
EXCLUIR = (r"(?i)/[^/]*(m[aàá]ster|m%c3%a1ster|master|doctora|posgrad|postgrau|anual|econ[oó]mic|actividad|"
           r"responsab|sostenib|presupuest|cuentas|seguimiento|investigaci|memorias?[-_ ]?(de[-_ ]?)?(curso|gesti))[^/]*$")

CONSULTA = """
SELECT url_host_registered_domain AS dominio, url, CAST(fetch_time AS VARCHAR) AS visto
FROM read_parquet('{fichero}')
WHERE subset = 'warc' AND fetch_status = 200
  AND url_host_registered_domain IN ({dominios})
  AND regexp_matches(lower(url_path), '{incluir}')
  AND NOT regexp_matches(lower(url_path), '{excluir}')
"""


def dominios() -> dict[str, dict]:
    """Dominio registrado → universidad (código y nombre)."""
    d = json.loads(DOMINIOS.read_text(encoding="utf-8"))
    return {dom: {"codigo_universidad": cu, "universidad": v["universidad"]} for cu, v in d.items()
            for dom in v["dominios"]}


def consultar(fichero: str, doms: list[str]) -> list[dict]:
    import duckdb

    from motor.estudios.commoncrawl import sin_secretos

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; SET http_retries=6; SET http_retry_wait_ms=2000;")
    lista = ",".join("'" + d.replace("'", "") + "'" for d in doms)
    filas = con.execute(CONSULTA.format(fichero=fichero, dominios=lista, incluir=INCLUIR.replace("'", "''"),
                                        excluir=EXCLUIR.replace("'", "''"))).fetchall()
    return [{"dominio": d, "url": sin_secretos(u), "visto_en_cc": str(t)[:10]} for d, u, t in filas]


def buscar_cc(crawls: list[str], desde: int, hasta: int, salida: Path, max_minutos: float) -> dict:
    from motor.estudios.commoncrawl import ficheros

    doms = dominios()
    fin = time.time() + max_minutos * 60
    urls, hechos, errores = {}, 0, []
    for crawl in crawls:
        for f in ficheros(crawl)[desde:hasta]:
            if time.time() > fin:
                break
            for intento in range(3):  # Common Crawl corta a veces con un error HTTP: dos reintentos con espera
                try:
                    for x in consultar(f, sorted(doms)):
                        urls.setdefault(x["url"], {**x, **doms.get(x["dominio"], {}), "crawl": crawl})
                    hechos += 1
                    break
                except Exception as e:  # noqa: BLE001 - un fichero que falla no para el resto
                    if intento == 2 or "HTTP" not in type(e).__name__ + str(e)[:200]:
                        errores.append(f"{f.rsplit('/', 1)[-1]}: {type(e).__name__}: {str(e)[:100]}")
                        break
                    time.sleep(15 * (intento + 1))
    destino = salida / "datos" / "estudios" / "grados" / "memorias_web"
    destino.mkdir(parents=True, exist_ok=True)
    nombre = f"urls_{'_'.join(crawls)}_{desde}_{hasta}"
    with (destino / f"{nombre}.jsonl").open("w", encoding="utf-8") as fh:
        for x in urls.values():
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")
    por_u: dict[str, int] = {}
    for x in urls.values():
        por_u[x.get("universidad") or x["dominio"]] = por_u.get(x.get("universidad") or x["dominio"], 0) + 1
    res = {"crawls": crawls, "ficheros_leidos": hechos, "errores": errores[:10], "dominios": len(doms),
           "urls": len(urls), "por_universidad": dict(sorted(por_u.items(), key=lambda kv: -kv[1]))}
    (destino / f"resumen_{nombre}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


# --------------------------------------------------------------------------------------------- lectura del PDF

IDENTIFICADOR = re.compile(r"Identificador\s*:\s*(\d{7,8})")
FECHA = re.compile(r"Fecha\s*:\s*(\d{2}/\d{2}/\d{4})")
DENOMINACION = re.compile(r"(Graduado\s+o\s+Graduada\s+en\s+[^\n]{3,200}?)(?:\s+por\s+la\s+|\s*\n)", re.I)
NIVEL = re.compile(r"^\s*(?:\d+(?:\.\d+)*\s+)?NIVEL\s*([123])\s*:\s*(.+?)\s*$", re.I)
CARACTERES = ("básica", "obligatoria", "optativa", "prácticas externas", "trabajo fin de grado / máster",
              "trabajo fin de grado", "mixto")
CARACTER = re.compile(r"^\s*CAR[ÁA]CTER\s+(" + "|".join(re.escape(c) for c in CARACTERES) + r")\b", re.I)
# fila de valores bajo «CARÁCTER  ECTS ASIGNATURA  DESPLIEGUE TEMPORAL»: «Básica  6  Semestral»
FILA_N3 = re.compile(r"^\s*(" + "|".join(re.escape(c) for c in CARACTERES) + r")\s+(\d+(?:[.,]\d+)?)\s+"
                     r"(Semestral|Anual|Cuatrimestral|Trimestral|Otra)\b", re.I)
ECTS_NIVEL = re.compile(r"ECTS\s*(?:NIVEL\s*\d|MATERIA|ASIGNATURA)\s*:?\s*(\d+(?:[.,]\d+)?)\b", re.I)
DESPLIEGUE = re.compile(r"DESPLIEGUE\s+TEMPORAL\s*:?\s*(Semestral|Anual|Cuatrimestral|Trimestral|Otra)", re.I)
CABECERA_SEM = re.compile(r"ECTS\s+(Semestral|Anual|Cuatrimestral|Trimestral)\s+(\d{1,2})", re.I)


def _num(x: str) -> float:
    return float(x.replace(",", "."))


def _caracter(c: str) -> str:
    c = c.strip()
    return c[:1].upper() + c[1:].lower() if c.lower() != "trabajo fin de grado / máster" else "Trabajo Fin de Grado / Máster"


def despliegue_de_lineas(cabecera: str, valores: str) -> dict[str, float]:
    """Une cada cifra de la fila de valores con la columna «ECTS Semestral N» que tiene encima (texto con la
    posición de cada columna conservada)."""
    cols = [(m.start(), m.end(), m.group(2)) for m in CABECERA_SEM.finditer(cabecera)]
    if not cols:
        return {}
    out = {}
    for m in re.finditer(r"\d+(?:[.,]\d+)?", valores):
        centro = (m.start() + m.end()) / 2
        col = min(cols, key=lambda c: 0 if c[0] - 2 <= centro <= c[1] + 2 else min(abs(centro - c[0]), abs(centro - c[1])))
        if col[0] - 6 <= centro <= col[1] + 6:
            out[col[2]] = out.get(col[2], 0) + _num(m.group())
    return out


def plan_de_texto(lineas: list[str]) -> dict:
    """Módulos → materias → asignaturas con carácter, ECTS, unidad temporal y despliegue, de las líneas del PDF
    (texto con columnas conservadas). Misma forma que `ruct_grados.leer_plan_memoria`."""
    plan, mod, mat, unidad = [], None, None, None
    for i, linea in enumerate(lineas):
        m = NIVEL.match(linea)
        if m:
            nivel, nombre = m.group(1), re.sub(r"\s{2,}.*$", "", m.group(2)).strip()
            unidad = {"nombre": nombre, "caracter": None, "ects": None, "unidad_temporal": None, "despliegue": {}}
            if nivel == "1":
                mod = {"modulo": len(plan) + 1, "nombre": nombre, "ects": None, "materias": [], "caracter": None,
                       "unidad_temporal": None, "despliegue": {}}
                plan.append(mod)
                mat, unidad = None, mod
            elif nivel == "2":
                if mod is None:
                    mod = {"modulo": 0, "nombre": None, "ects": None, "materias": []}
                    plan.append(mod)
                mat = {**unidad, "id": len(mod["materias"]) + 1, "asignaturas": []}
                mod["materias"].append(mat)
                unidad = mat
            else:
                if mat is None:
                    continue
                unidad = {**unidad, "id": len(mat["asignaturas"]) + 1}
                mat["asignaturas"].append(unidad)
            continue
        if unidad is None:
            continue
        if (c := CARACTER.match(linea)) and not unidad["caracter"]:
            unidad["caracter"] = _caracter(c.group(1))
        if (f := FILA_N3.match(linea)) and not unidad["caracter"]:
            unidad.update(caracter=_caracter(f.group(1)), ects=_num(f.group(2)), unidad_temporal=f.group(3).capitalize())
        if (e := ECTS_NIVEL.search(linea)) and unidad["ects"] is None:
            unidad["ects"] = _num(e.group(1))
        if (d := DESPLIEGUE.search(linea)) and not unidad["unidad_temporal"]:
            unidad["unidad_temporal"] = d.group(1).capitalize()
        if CABECERA_SEM.search(linea) and i + 1 < len(lineas) and not CABECERA_SEM.search(lineas[i + 1]):
            unidad["despliegue"].update(despliegue_de_lineas(linea, lineas[i + 1]))
    # ECTS del módulo: «ECTS NIVEL 1» no siempre viene; si no, la suma de sus materias
    for b in plan:
        for k in ("caracter", "unidad_temporal", "despliegue"):
            b.pop(k, None)
        b["ects"] = b["ects"] or (sum(x["ects"] or 0 for x in b["materias"]) or None)
    materias = [x for b in plan for x in b["materias"]]
    return {"plan": plan, "cobertura": {"modulos": len(plan), "materias": len(materias),
                                        "asignaturas": sum(len(x["asignaturas"]) for x in materias),
                                        "con_caracter": sum(1 for x in materias for h in (x["asignaturas"] or [x])
                                                            if h["caracter"]),
                                        "con_ects": sum(1 for x in materias for h in (x["asignaturas"] or [x]) if h["ects"]),
                                        "con_despliegue": sum(1 for x in materias for h in (x["asignaturas"] or [x])
                                                              if h["despliegue"])}}


def texto_por_paginas(contenido: bytes) -> list[str]:
    from pypdf import PdfReader

    lector = PdfReader(io.BytesIO(contenido))
    paginas = []
    for p in lector.pages:
        try:
            paginas.append(p.extract_text(extraction_mode="layout") or "")
        except Exception:  # noqa: BLE001 - una página rara no para el resto
            paginas.append(p.extract_text() or "")
    return paginas


def leer_memoria(contenido: bytes) -> dict:
    paginas = texto_por_paginas(contenido)
    todo = "\n".join(paginas)
    ids = sorted(set(IDENTIFICADOR.findall(todo)))
    fechas = FECHA.findall("\n".join(paginas[:3]))
    den = DENOMINACION.search(re.sub(r"[ \t]+", " ", "\n".join(paginas[:4])))
    res = {"paginas": len(paginas), "identificadores": ids, "fecha": fechas[0] if fechas else None,
           "denominacion": re.sub(r"\s+", " ", den.group(1)).strip() if den else None,
           "niveles": {n: len(re.findall(rf"(?im)^\s*(?:\d+(?:\.\d+)*\s+)?NIVEL\s*{n}\s*:", todo)) for n in "123"}}
    if res["niveles"]["2"]:
        res.update(plan_de_texto(todo.splitlines()))
    return res


def _forma(linea: str) -> str:
    """La línea con letras → a, cifras → 9 (para ver la disposición sin copiar el texto)."""
    s = unicodedata.normalize("NFKD", linea)
    return re.sub(r"\d", "9", re.sub(r"[^\W\d_]", "a", s))


def leer(urls: list[dict], salida: Path, max_minutos: float, muestras: int = 3) -> dict:
    from motor.estudios.rastreador import Dominio
    from motor.grados.tarifas_grado import pedir_con_motivo

    archivo = Archivo(salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    destino = salida / "datos" / "estudios" / "grados" / "memorias_web"
    destino.mkdir(parents=True, exist_ok=True)
    fin = time.time() + max_minutos * 60
    doms, resultados, vistos, n_muestras = {}, [], set(), 0
    for u in urls:
        if time.time() > fin:
            break
        url = u["url"]
        host = re.sub(r"^https?://([^/]+).*$", r"\1", url)
        d = doms.setdefault(host, Dominio("https://" + host, archivo, pausa=1.0, max_peticiones=150))
        r, motivo = pedir_con_motivo(d, url)
        res = {**u, "capturado": date.today().isoformat(), "estado": r.status_code if r is not None else None}
        if motivo:
            res["motivo"] = motivo
        if r is not None and r.status_code == 200 and r.content[:4] == b"%PDF" and len(r.content) <= MAX_PDF:
            huella = hashlib.sha256(r.content).hexdigest()
            res["sha256"], res["bytes"] = huella, len(r.content)
            if huella in vistos:
                res["repetido"] = True
                resultados.append(res)
                continue
            vistos.add(huella)
            archivo.guardar(FUENTE, date.today(), r.content, url, "pdf", r.status_code,
                            {k: v for k, v in r.headers.items() if k.lower() in {"content-type", "last-modified"}})
            try:
                res.update(leer_memoria(r.content))
                if res.get("niveles", {}).get("2") and n_muestras < muestras and not res.get("cobertura", {}).get("con_ects"):
                    # el lector no entendió la disposición: la forma de las líneas del plan, sin el texto
                    lineas = "\n".join(texto_por_paginas(r.content)).splitlines()
                    i = next((k for k, x in enumerate(lineas) if NIVEL.match(x)), 0)
                    res["formas_del_plan"] = [_forma(x)[:140] for x in lineas[i:i + 80]]
                    n_muestras += 1
            except Exception as e:  # noqa: BLE001 - un PDF roto no para el resto
                res["error"] = f"{type(e).__name__}: {str(e)[:150]}"
        elif r is not None and r.status_code == 200:
            res["error"] = "no_es_pdf_o_demasiado_grande"
        resultados.append(res)
    parte = f"{len(resultados)}_{hashlib.sha256(''.join(u['url'] for u in urls).encode()).hexdigest()[:8]}"
    with (destino / f"memorias_{parte}.jsonl").open("w", encoding="utf-8") as fh:
        for x in resultados:
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")
    leidos = [x for x in resultados if x.get("paginas")]
    resumen = {"urls": len(urls), "pedidas": len(resultados), "pdf_leidos": len(leidos),
               "con_identificador": sum(1 for x in leidos if x.get("identificadores")),
               "con_niveles": sum(1 for x in leidos if x.get("niveles", {}).get("2")),
               "con_plan_con_ects": sum(1 for x in leidos if (x.get("cobertura") or {}).get("con_ects")),
               "titulos": len({i for x in leidos for i in x.get("identificadores") or []}),
               "motivos": {m: sum(1 for x in resultados if x.get("motivo") == m) for m in
                           {x.get("motivo") for x in resultados if x.get("motivo")}}}
    (destino / f"resumen_{parte}.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    return resumen


def urls_de(carpeta: Path, parte: tuple[int, int] | None) -> list[dict]:
    """URL de los ficheros de `cc`, sin repetir, repartidas por servidor entre las partes (cada servidor en una)."""
    vistas, urls = set(), []
    for f in sorted(carpeta.rglob("memorias_web/urls_*.jsonl")):
        for linea in f.read_text(encoding="utf-8").splitlines():
            x = json.loads(linea)
            if x["url"] not in vistas:
                vistas.add(x["url"])
                urls.append(x)
    if parte:
        i, n = parte
        urls = [x for x in urls if int(hashlib.sha256(x["dominio"].encode()).hexdigest(), 16) % n == i]
    return sorted(urls, key=lambda x: (x.get("codigo_universidad") or "", x["url"]))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("paso", choices=["cc", "leer"])
    p.add_argument("--crawls", default="", help="crawls separados por comas: identificadores o posiciones (0 = el último)")
    p.add_argument("--archivos", default="0:400", help="ficheros del índice desde:hasta")
    p.add_argument("--urls", type=Path, help="carpeta con los urls_*.jsonl del paso cc")
    p.add_argument("--parte", default="", help="i/n: solo los servidores de la parte i de n")
    p.add_argument("--max-minutos", type=float, default=48)
    p.add_argument("--salida", type=Path, required=True)
    a = p.parse_args()
    if a.paso == "cc":
        from motor.estudios.commoncrawl import ultimo_crawl

        # «0,1,2»: los tres crawls más recientes; o sus identificadores («CC-MAIN-2026-43»)
        crawls = [ultimo_crawl(int(c)) if c.isdigit() else c for c in a.crawls.split(",") if c] or [ultimo_crawl()]
        desde, hasta = (int(x) for x in a.archivos.split(":"))
        res = buscar_cc(crawls, desde, hasta, a.salida, a.max_minutos)
    else:
        parte = tuple(int(x) for x in a.parte.split("/")) if a.parte else None
        res = leer(urls_de(a.urls, parte), a.salida, a.max_minutos)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
