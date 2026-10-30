"""Catálogo de grados oficiales y dobles grados (SIIU del Ministerio): el universo de carreras.

Fuente: «Clasificaciones estadísticas universitarias» del Ministerio de Ciencia, Innovación y Universidades
(https://www.ciencia.gob.es/Ministerio/Estadisticas/SIIU/Clasificaciones.html). Son los mismos cuatro XLSX
que usa el módulo de másters (motor/estudios/catalogo.py, del que se reutilizan descubrir() y filas()):
titulaciones por unidad, rama/campo/ISCED, centros y universidades.

Qué hay en el fichero de titulaciones para el primer y segundo ciclo (medido el 30/10/2026, fichero del curso
2025-2026 publicado el 06/10/2026):
  - «Grado»: títulos con código RUCT de 7 cifras. 25xxxxx = verificados con el RD 1393/2007, 15xxxxx = con el
    RD 822/2021. Además, tres familias que no son un grado normal: 00xxxxx agrupaciones de acceso de las
    universidades catalanas («(agrupació)», un primer curso común que lleva a varios grados), 77xxxxx grados
    abiertos (primer curso sin grado elegido) y 90xxxxx títulos eclesiásticos (Baccalaureatus).
  - «Programaciones Conjuntas de Estudios Oficiales» (PCEO): los dobles grados, con código 70xxxxx propio del
    SIIU. Corrige la guía, que decía que los dobles grados no tenían código oficial y llevarían uno nuestro.

Uso:
  python -m motor.grados.catalogo --salida ruta/                       descarga del Ministerio
  python -m motor.grados.catalogo --originales ruta/archivo --salida ruta/   desde originales ya archivados
Escribe:
  archivo/siiu-clasificaciones/...           originales intactos con huella (solo si descarga)
  datos/estudios/grados/catalogo.jsonl        un título por línea (grados, dobles y familias especiales)
  datos/estudios/grados/catalogo_resumen.json
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from motor.archivo import Archivo
from motor.estudios.catalogo import CITA, FICHEROS, FUENTE, PAGINA, ErrorCatalogo, _curso, descubrir, filas
from motor.http import obtener

NIVEL_GRADO = "Grado"
NIVEL_DOBLE = "Programaciones Conjuntas de Estudios Oficiales"
ORDEN_SITUACION = {"Activo": 0, "En proceso de extinción": 1, "Inactivo": 2, "Extinguido": 3}
SITUACIONES_VIVAS = {"Activo", "En proceso de extinción"}
REGIMEN = {"25": "RD 1393/2007", "15": "RD 822/2021"}

# ------------------------------------------------------------------------------------------- nombres


def sin_acentos(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def clave(s: str | None) -> str:
    """Forma de comparar nombres: minúsculas, sin acentos ni signos, espacios simples."""
    s = sin_acentos((s or "").lower()).replace("·", "")
    s = re.sub(r"[^a-z0-9ñ]+", " ", s)
    return " ".join(s.split())


VACIAS = {"de", "del", "la", "las", "el", "los", "en", "y", "e", "i", "a", "les", "l", "d", "por", "grado", "grau"}
ABREVIATURAS = {"cc": "ciencias", "ade": "administracion direccion empresas", "ing": "ingenieria"}


def _raiz(p: str) -> str:
    """Singular aproximado: «telecomunicaciones» → «telecomunicacion», «industriales» → «industrial»."""
    if len(p) > 5 and p.endswith("es") and p[-3] in "lrndj":
        return p[:-2]
    if len(p) > 4 and p.endswith("s"):
        return p[:-1]
    return p


def clave_union(s: str | None) -> str:
    """Clave más laxa para unir nombres del mismo título escritos de otra forma: sin palabras vacías, sin
    plurales y con abreviaturas habituales desplegadas («CC Ambientales» = «Ciencias Ambientales»,
    «Ingeniería de Organización» = «Ingeniería en Organización»). Solo para comparar, nunca para mostrar."""
    palabras = []
    for p in clave(s).split():
        p = ABREVIATURAS.get(p, p)
        palabras += [_raiz(x) for x in p.split() if x not in VACIAS]
    return " ".join(palabras)


def variantes_nombre(nombre: str) -> list[str]:
    """Nombre completo y, si es bilingüe («Economía / Economics», «ADE - Bachelor in …»), su parte en castellano."""
    salida = [nombre]
    partes = re.split(r"\s*/\s*|\s+-\s+|-(?=Bachelor)", nombre)
    if len(partes) > 1 and partes[0]:
        salida.append(partes[0])
    sin_par = re.sub(r"\s*\([^()]*\)\s*$", "", nombre)
    if sin_par != nombre:
        salida.append(sin_par)
    return salida


RE_POR = re.compile(r"\s+por\s+(?:la|el|las|los|les|l')\s*(?=Universi|Escuela|Escola|Facultad|Universitat|Mondrag|IE\b|"
                    r"Centro|CEU|Pontificia|Deusto|Comillas|UNED|ESIC|CUNEF|Abat|Loyola|Nebrija|EAE|Fundaci)", re.I)
# «Graduado o Graduada en X», y en los planes del BOE anteriores a 2015 «Graduado en X», «Graduado/a en X» o
# «Graduado Maestro en Educación Infantil»
RE_PREFIJO = re.compile(r"^(?:(?:Graduado o Graduada|Graduada o Graduado|Graduat o Graduada|Graduad[oa](?:/a)?|Grado|Grau)"
                        r"\s+(?:en|in)\s+|Graduad[oa](?:\s+o\s+Graduad[oa])?\s+(?=Maestr))", re.I)


def nombre_corto(nombre_oficial: str) -> str:
    """«Graduado o Graduada en Sociología por la Universidad de A Coruña» → «Sociología»."""
    s = " ".join((nombre_oficial or "").split())
    s = RE_PREFIJO.sub("", s)
    m = RE_POR.search(s)
    if m:
        s = s[: m.start()]
    return s.strip().rstrip(".")


RE_COMPONENTE = re.compile(r"^(?:Grado|Graduado o Graduada|Grau)\s+en\s+(.+?)\s*$", re.I)


def componentes_doble(nombre: str) -> list[dict]:
    """«PCEO Grado en A (Granada) / Grado en B (Plan Nuevo)» → [{nombre: A, universidad: Granada}, {nombre: B}].

    El paréntesis final es una universidad cuando el doble grado se cursa entre dos (p. ej. Granada y Málaga);
    «(Plan Nuevo)» y similares se guardan como nota.
    """
    s = re.sub(r"^PCEO\s+", "", " ".join((nombre or "").split()))
    partes = re.split(r"\s*/\s*(?=(?:Grado|Graduado|Grau)\s+en\b)", s)
    salida = []
    for p in partes:
        m = RE_COMPONENTE.match(p.strip())
        texto = m.group(1) if m else p.strip()
        por = RE_POR.search(texto)
        if por:
            texto = texto[: por.start()]
        nota = None
        par = re.search(r"\s*\(([^()]+)\)\s*$", texto)
        if par:
            nota = par.group(1).strip()
            texto = texto[: par.start()].strip()
        salida.append({"nombre": texto, "parentesis": nota})
    return salida


def clase_titulo(codigo: str, nivel: str, nombre: str) -> str:
    if nivel == NIVEL_DOBLE:
        return "doble"
    if codigo.startswith("90"):
        return "eclesiastico"
    if codigo.startswith("77") or re.search(r"grado abierto|grau obert", nombre or "", re.I):
        return "grado_abierto"
    if codigo.startswith("00") or "(agrupaci" in (nombre or "").lower():
        return "agrupacion"
    return "grado"


# ------------------------------------------------------------------------------------------- catálogo


def construir(titulaciones: list[dict], rama: list[dict], centros: list[dict], universidades: list[dict],
              curso: str) -> list[dict]:
    """Un registro por título (código), con todas sus imparticiones (universidad × centro × modalidad)."""
    por_rama = {r["Código de la titulación"]: r for r in rama}
    por_univ = {u["Universidad"]: u for u in universidades}
    por_centro: dict[tuple, list[dict]] = defaultdict(list)
    for c in centros:
        por_centro[(c["Universidad"], c["Unidad"])].append(c)

    titulos: dict[str, dict] = {}
    for t in titulaciones:
        nivel = t.get("Nivel académico") or ""
        if nivel not in (NIVEL_GRADO, NIVEL_DOBLE):
            continue
        codigo = t["Código de la titulación"]
        nombre_of = t.get("Nombre de la titulación (RUCT)") or ""
        r = por_rama.get(codigo, {})
        u = por_univ.get(t["Universidad"], {})
        reg = titulos.get(codigo)
        if reg is None:
            clase = clase_titulo(codigo, nivel, nombre_of)
            reg = titulos[codigo] = {
                "codigo": codigo,
                "clase": clase,
                "codigo_ruct": codigo if clase == "grado" else None,
                "regimen": REGIMEN.get(codigo[:2]) if clase == "grado" else None,
                "nombre_oficial": nombre_of,
                "nombre": nombre_corto(nombre_of) if clase != "doble" else
                " y ".join(c["nombre"] for c in componentes_doble(nombre_of)),
                "situacion": t.get("Situación"),
                "universidades": [],
                "universidad_tipo": t.get("Tipo de universidad"),
                "rama": r.get("Rama de la enseñanza"),
                "campo_codigo": r.get("Código campo"),
                "campo": r.get("Campo de estudio"),
                "isced_codigo": r.get("Código ISCED 2013"),
                "isced": r.get("(Ámbito de estudio) ISCED 2013"),
                "ambito": r.get("Ámbito de estudio"),
                "componentes": componentes_doble(nombre_of) if clase == "doble" else [],
                "imparticiones": [],
                "fuente": {"cita": CITA, "curso": curso},
            }
        if t["Universidad"] not in [x["nombre"] for x in reg["universidades"]]:
            reg["universidades"].append({"nombre": t["Universidad"], "codigo": u.get("Código de la universidad"),
                                         "tipo": t.get("Tipo de universidad"), "comunidad": u.get("Comunidad autónoma")})
        sit = t.get("Situación")
        if ORDEN_SITUACION.get(sit, 9) < ORDEN_SITUACION.get(reg["situacion"], 9):
            reg["situacion"] = sit
        candidatos = por_centro.get((t["Universidad"], t["Unidad"]), [])
        codigos = sorted({c["Código de la unidad"] for c in candidatos})
        uno = candidatos[0] if len(codigos) == 1 else {}
        reg["imparticiones"].append({
            "universidad": t["Universidad"],
            "unidad": t.get("Unidad"),
            "unidad_codigo": codigos[0] if len(codigos) == 1 else None,
            "unidad_codigos_posibles": codigos if len(codigos) > 1 else [],
            "municipio": uno.get("Municipio de la unidad"),
            "unidad_tipo": t.get("Tipo de unidad"),
            "unidad_modalidad": uno.get("Modalidad de la Unidad"),
            "situacion": sit,
            "presencialidad": t.get("Presencialidad de la titulación"),
            "idioma_extranjero": t.get("Idioma extranjero"),
        })
    catalogo = sorted(titulos.values(), key=lambda x: (x["universidades"][0]["nombre"], x["codigo"]))
    enlazar_dobles(catalogo)
    return catalogo


def enlazar_dobles(catalogo: list[dict]) -> None:
    """Cada componente de un doble grado se une con el grado simple de la misma universidad (o de la que diga
    el paréntesis) por nombre normalizado. Si no hay uno y solo uno, queda sin código y se cuenta."""
    indice: dict[tuple[str, str], set[str]] = defaultdict(set)
    situacion = {t["codigo"]: t["situacion"] for t in catalogo}
    for t in catalogo:
        if t["clase"] != "grado":
            continue
        for u in t["universidades"]:
            # nombre entero, parte en castellano de los bilingües y sin «(Plan nuevo)» y similares
            for v in variantes_nombre(t["nombre"]):
                indice[(clave(u["nombre"]), clave_union(v))].add(t["codigo"])
    from motor.grados.generico import nombre_base  # aquí: generico importa este módulo
    generico_idx: dict[tuple[str, str], set[str]] = defaultdict(set)
    for t in catalogo:
        if t["clase"] == "grado" and t["situacion"] == "Activo":
            for u in t["universidades"]:
                generico_idx[(clave(u["nombre"]), clave_union(nombre_base(t["nombre"])))].add(t["codigo"])
    todas = {clave(u["nombre"]): u["nombre"] for t in catalogo for u in t["universidades"]}
    for t in catalogo:
        if t["clase"] != "doble":
            continue
        unis = [u["nombre"] for u in t["universidades"]]
        for c in t["componentes"]:
            # «(Málaga)»: el componente se cursa en otra universidad; «(Plan Nuevo)»: es una nota del nombre
            otra = todas.get(clave(c["parentesis"])) if c["parentesis"] else None
            posibles_u = [otra] if otra else unis
            nombres = [c["nombre"]] if otra or not c["parentesis"] else [f"{c['nombre']} ({c['parentesis']})", c["nombre"]]
            encontrados: set[str] = set()
            for n in [v for x in nombres for v in variantes_nombre(x)]:
                for u in posibles_u:
                    encontrados |= indice.get((clave(u), clave_union(n)), set())
                if encontrados:
                    break
            if not encontrados:
                # con el nombre del grado genérico («Educación Primaria» = «Maestro en Educación Primaria»), solo
                # entre los grados activos y solo si hay uno
                for u in posibles_u:
                    encontrados |= {x for x in generico_idx.get((clave(u), clave_union(nombre_base(c["nombre"]))), set())}
                if len(encontrados) > 1:
                    encontrados = set()
            if not encontrados and not re.search(r"\bgrado en\b", c["nombre"], re.I):
                # un nombre contiene al otro («Criminología» y «Criminología y Seguridad», «Informática» e «Ingeniería
                # Informática»), solo si en la universidad hay un solo grado activo así; queda marcado para revisar
                pc = set(clave_union(nombre_base(c["nombre"])).split())
                cands = {g for u in posibles_u for (cu, kg), gs in generico_idx.items() if cu == clave(u)
                         for g in gs if pc and (pc <= set(kg.split()) or set(kg.split()) <= pc)}
                if len(cands) == 1:
                    encontrados, c["union"] = cands, "por_contencion_del_nombre"
            # Con un plan antiguo en extinción y otro activo del mismo nombre, el doble activo va con el activo.
            activos = {c for c in encontrados if situacion.get(c) == "Activo"}
            if len(encontrados) > 1 and len(activos) == 1 and t["situacion"] == "Activo":
                encontrados = activos
            vivos = sorted(encontrados)
            c["universidad"] = otra
            c["codigo"] = vivos[0] if len(vivos) == 1 else None
            c["codigos_posibles"] = vivos if len(vivos) > 1 else []


def resumen(catalogo: list[dict]) -> dict:
    activos = [t for t in catalogo if t["situacion"] == "Activo"]
    imp = [(t, i) for t in activos for i in t["imparticiones"] if i["situacion"] == "Activo"]
    dobles = [t for t in activos if t["clase"] == "doble"]
    comp = [c for t in dobles for c in t["componentes"]]
    grados = [t for t in activos if t["clase"] == "grado"]
    return {
        "titulos": len(catalogo),
        "por_clase_y_situacion": {f"{k[0]} · {k[1]}": v for k, v in
                                  sorted(Counter((t["clase"], t["situacion"]) for t in catalogo).items())},
        "activos_por_clase": dict(Counter(t["clase"] for t in activos)),
        "grados_activos_por_tipo_universidad": dict(Counter(t["universidad_tipo"] for t in grados)),
        "grados_activos_por_regimen": dict(Counter(t["regimen"] for t in grados)),
        "grados_activos_por_rama": dict(Counter(t["rama"] for t in grados).most_common()),
        "grados_activos_conjuntos_varias_universidades": sum(1 for t in grados if len(t["universidades"]) > 1),
        "imparticiones_activas_por_clase": dict(Counter(t["clase"] for t, _ in imp)),
        "imparticiones_grado_activas_por_presencialidad": dict(Counter(i["presencialidad"] for t, i in imp if t["clase"] == "grado")),
        "imparticiones_grado_activas_por_tipo_unidad": dict(Counter(i["unidad_tipo"] for t, i in imp if t["clase"] == "grado")),
        "imparticiones_grado_activas_por_modalidad_unidad": dict(Counter(i["unidad_modalidad"] for t, i in imp if t["clase"] == "grado")),
        "imparticiones_grado_activas_con_idioma_extranjero": sum(1 for t, i in imp if t["clase"] == "grado"
                                                                 and (i["idioma_extranjero"] or "").startswith("Sí")),
        "grados_activos_por_comunidad": dict(Counter(t["universidades"][0]["comunidad"] for t in grados).most_common()),
        "universidades_con_grado_activo": len({u["nombre"] for t in grados for u in t["universidades"]}),
        "dobles_componentes": len(comp),
        "dobles_componentes_unidos": sum(1 for c in comp if c.get("codigo")),
        "dobles_componentes_ambiguos": sum(1 for c in comp if c.get("codigos_posibles")),
        "imparticiones_sin_codigo_de_centro": sum(1 for t in catalogo for i in t["imparticiones"] if not i["unidad_codigo"]),
    }


# ------------------------------------------------------------------------------------------- ejecución


def _leer_originales(carpeta: Path) -> tuple[dict[str, bytes], dict[str, dict]]:
    """Lee los XLSX desde un archivo ya capturado (indice.jsonl + ficheros .gz con huella)."""
    indice = [json.loads(linea) for linea in (carpeta / "indice.jsonl").read_text(encoding="utf-8").splitlines()
              if linea.strip()]
    indice = [x for x in indice if x.get("fuente") == FUENTE]
    pagina = next(x for x in indice if x["url"] == PAGINA)
    html = gzip.decompress((carpeta / pagina["ruta"]).read_bytes()).decode("utf-8", "replace")
    urls = descubrir(html)
    contenido, capturas = {}, {}
    for nombre, url in urls.items():
        x = next((y for y in indice if y["url"] == url), None)
        if x is None:
            raise ErrorCatalogo(f"{nombre}: {url} no está en el archivo")
        contenido[nombre] = gzip.decompress((carpeta / x["ruta"]).read_bytes())
        capturas[nombre] = {"url": url, "sha256": x["sha256"], "capturado": x["capturado"]}
    return contenido, capturas


def _descargar(raiz: Path) -> tuple[dict[str, bytes], dict[str, dict]]:
    archivo = Archivo(raiz / "archivo")
    hoy = date.today()
    pagina = obtener(PAGINA)
    if pagina.status != 200:
        raise ErrorCatalogo(f"Página de clasificaciones: estado {pagina.status}")
    archivo.guardar(FUENTE, hoy, pagina.contenido, PAGINA, "html", pagina.status, pagina.cabeceras)
    contenido, capturas = {}, {}
    for nombre, url in descubrir(pagina.contenido.decode("utf-8", "replace")).items():
        time.sleep(1)
        r = obtener(url)
        if r.status != 200:
            raise ErrorCatalogo(f"{nombre}: estado {r.status} en {url}")
        reg = archivo.guardar(FUENTE, hoy, r.contenido, url, "xlsx", r.status, r.cabeceras)
        contenido[nombre] = r.contenido
        capturas[nombre] = {"url": url, "sha256": reg["sha256"], "capturado": reg["capturado"]}
    return contenido, capturas


def ejecutar(raiz: Path, originales: Path | None = None) -> dict:
    contenido, capturas = _leer_originales(originales) if originales else _descargar(raiz)
    leidos = {n: filas(contenido[n], FICHEROS[n][1], FICHEROS[n][2]) for n in FICHEROS}
    curso = _curso(capturas["titulaciones"]["url"], date.today())
    catalogo = construir(leidos["titulaciones"], leidos["rama"], leidos["centros"], leidos["universidades"], curso)
    for t in catalogo:
        t["fuente"].update({k: capturas["titulaciones"][k] for k in ("url", "sha256", "capturado")})
    destino = raiz / "datos" / "estudios" / "grados"
    destino.mkdir(parents=True, exist_ok=True)
    with (destino / "catalogo.jsonl").open("w", encoding="utf-8") as f:
        for t in catalogo:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    res = resumen(catalogo)
    res["curso"] = curso
    res["capturas"] = capturas
    (destino / "catalogo_resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", required=True)
    p.add_argument("--originales", help="carpeta archivo/ con indice.jsonl y los originales ya capturados")
    a = p.parse_args()
    try:
        res = ejecutar(Path(a.salida), Path(a.originales) if a.originales else None)
    except ErrorCatalogo as e:
        print(f"ALERTA catálogo SIIU (grados): {e}", file=sys.stderr)
        sys.exit(2)
    print(json.dumps({k: v for k, v in res.items() if k != "capturas"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
