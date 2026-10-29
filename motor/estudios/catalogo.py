"""Catálogo de títulos oficiales del Ministerio (SIIU), base del universo de másters.

Fuente: «Clasificaciones estadísticas universitarias» del Ministerio de Ciencia, Innovación y Universidades
(https://www.ciencia.gob.es/Ministerio/Estadisticas/SIIU/Clasificaciones.html). Cuatro hojas XLSX anuales:
  - titulaciones: cada título oficial (código RUCT de 7 cifras) × unidad/centro, con situación,
    presencialidad e idioma extranjero;
  - rama: rama de enseñanza, campo, ISCED 2013 y ámbito de cada título;
  - centros: código de 8 cifras, municipio y tipo (propio/adscrito) de cada unidad;
  - universidades: código de 3 cifras, tipo, presencialidad y comunidad.

Los enlaces cambian cada año (llevan un identificador interno), por eso se descubren en la página.

Uso:
  python -m motor.estudios.catalogo --salida ruta/
Escribe:
  archivo/siiu-clasificaciones/...            originales intactos con huella
  datos/estudios/masters/catalogo.jsonl       un título de máster por línea (simples y dobles)
  datos/estudios/masters/catalogo_resumen.json
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

from motor.archivo import Archivo
from motor.http import obtener

PAGINA = "https://www.ciencia.gob.es/Ministerio/Estadisticas/SIIU/Clasificaciones.html"
FUENTE = "siiu-clasificaciones"
CITA = "Ministerio de Ciencia, Innovación y Universidades. Sistema Integrado de Información Universitaria (SIIU)"

# Fichero → (texto que identifica el enlace en la página, columna que identifica la fila de cabecera, hoja)
FICHEROS = {
    "titulaciones": ("Titulaciones en universidades españolas, por unidad", "Código de la titulación", 0),
    "rama": ("Titulaciones según rama, ISCED 2013", "Código de la titulación", None),
    "centros": ("Centros / Unidades impartiendo titulaciones", "Código de la unidad", 0),
    "universidades": ("Universidades españolas, por tipo", "Código de la universidad", 0),
}
NIVELES_MASTER = {"Máster": "simple", "Estudio Conjunto de Master": "doble"}
SITUACIONES_VIVAS = {"Activo", "En proceso de extinción"}


class ErrorCatalogo(Exception):
    pass


def descubrir(html: str, base: str = PAGINA) -> dict[str, str]:
    """Devuelve {fichero: url} buscando cada enlace .xlsx por el texto que lo acompaña."""
    enlaces = re.findall(r'<a\b[^>]*href="([^"]+\.xlsx?)"[^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL)
    encontrados = {}
    for nombre, (texto, _, _) in FICHEROS.items():
        for href, etiqueta in enlaces:
            limpio = " ".join(re.sub(r"<[^>]+>", " ", etiqueta).split())
            if texto.lower() in limpio.lower():
                encontrados[nombre] = urljoin(base, href.replace("&amp;", "&"))
                break
    faltan = set(FICHEROS) - set(encontrados)
    if faltan:
        raise ErrorCatalogo(f"No se encuentran en la página los enlaces de: {', '.join(sorted(faltan))}")
    return encontrados


def _celda(v) -> str | None:
    if v is None:
        return None
    s = " ".join(str(v).split())
    return s or None


def filas(xlsx: bytes, clave: str, hoja: int | None = 0) -> list[dict]:
    """Lee una hoja localizando la fila de cabecera por el nombre de una columna.

    Si hoja es None, usa la primera hoja que tenga esa columna y la columna «Rama de la enseñanza»
    o «Ámbito de estudio» (el fichero de rama trae dos hojas con la misma clave).
    """
    import openpyxl

    libro = openpyxl.load_workbook(io.BytesIO(xlsx), read_only=True, data_only=True)
    hojas = libro.worksheets if hoja is None else [libro.worksheets[hoja]]
    combinado: dict[str, dict] = {}
    salida: list[dict] = []
    for ws in hojas:
        todas = list(ws.iter_rows(values_only=True))
        cab = next((i for i, f in enumerate(todas) if f and clave in [_celda(c) for c in f]), None)
        if cab is None:
            continue
        nombres = [_celda(c) or f"col{i}" for i, c in enumerate(todas[cab])]
        datos = [dict(zip(nombres, (_celda(c) for c in f))) for f in todas[cab + 1:] if f and any(f)]
        datos = [d for d in datos if d.get(clave)]
        if hoja is not None:
            return datos
        for d in datos:  # rama: se combinan las hojas por código de título
            combinado.setdefault(d[clave], {}).update({k: v for k, v in d.items() if v is not None})
    if hoja is None and combinado:
        salida = list(combinado.values())
    if not salida:
        raise ErrorCatalogo(f"No se encuentra la cabecera «{clave}»: posible cambio de formato")
    return salida


def componentes_doble(nombre: str) -> list[str]:
    """«PCEO Máster Universitario en A / Máster Universitario en B» → [«Máster Universitario en A», ...]."""
    s = re.sub(r"^PCEO\s+", "", nombre)
    partes = re.split(r"\s+/\s+(?=Máster)", s)
    return [p.strip() for p in partes if p.strip()]


def construir(titulaciones: list[dict], rama: list[dict], centros: list[dict], universidades: list[dict],
              curso: str) -> list[dict]:
    """Un registro por título de máster (código), con todas sus imparticiones (centro × modalidad)."""
    por_rama = {r["Código de la titulación"]: r for r in rama}
    por_univ = {u["Universidad"]: u for u in universidades}
    por_centro: dict[tuple, list[dict]] = defaultdict(list)
    for c in centros:
        por_centro[(c["Universidad"], c["Unidad"])].append(c)

    titulos: dict[str, dict] = {}
    for t in titulaciones:
        tipo = NIVELES_MASTER.get(t.get("Nivel académico") or "")
        if not tipo:
            continue
        codigo = t["Código de la titulación"]
        r = por_rama.get(codigo, {})
        u = por_univ.get(t["Universidad"], {})
        reg = titulos.get(codigo)
        if reg is None:
            reg = titulos[codigo] = {
                "codigo_ruct": codigo,
                "tipo": tipo,
                "nombre_oficial": t.get("Nombre de la titulación (RUCT)"),
                "situacion": t.get("Situación"),
                "universidad": t["Universidad"],
                "universidad_codigo": u.get("Código de la universidad"),
                "universidad_tipo": t.get("Tipo de universidad"),
                "universidad_comunidad": u.get("Comunidad autónoma"),
                "rama": r.get("Rama de la enseñanza"),
                "campo_codigo": r.get("Código campo"),
                "campo": r.get("Campo de estudio"),
                "isced_codigo": r.get("Código ISCED 2013"),
                "isced": r.get("(Ámbito de estudio) ISCED 2013"),
                "ambito": r.get("Ámbito de estudio"),
                "componentes": componentes_doble(t.get("Nombre de la titulación (RUCT)") or "") if tipo == "doble" else [],
                "imparticiones": [],
                "fuente": {"cita": CITA, "curso": curso},
            }
        candidatos = por_centro.get((t["Universidad"], t["Unidad"]), [])
        codigos = sorted({c["Código de la unidad"] for c in candidatos})
        reg["imparticiones"].append({
            "unidad": t.get("Unidad"),
            "unidad_codigo": codigos[0] if len(codigos) == 1 else None,
            "unidad_codigos_posibles": codigos if len(codigos) > 1 else [],
            "municipio": candidatos[0].get("Municipio de la unidad") if len(codigos) == 1 else None,
            "unidad_tipo": t.get("Tipo de unidad"),
            "unidad_modalidad": candidatos[0].get("Modalidad de la Unidad") if len(codigos) == 1 else None,
            "presencialidad": t.get("Presencialidad de la titulación"),
            "idioma_extranjero": t.get("Idioma extranjero"),
        })
    return sorted(titulos.values(), key=lambda x: (x["universidad"], x["codigo_ruct"]))


def resumen(catalogo: list[dict]) -> dict:
    vivos = [t for t in catalogo if t["situacion"] in SITUACIONES_VIVAS]
    activos = [t for t in catalogo if t["situacion"] == "Activo"]
    return {
        "titulos": len(catalogo),
        "por_situacion": dict(Counter(t["situacion"] for t in catalogo)),
        "activos_por_tipo": dict(Counter(t["tipo"] for t in activos)),
        "activos_por_universidad_tipo": dict(Counter(t["universidad_tipo"] for t in activos if t["tipo"] == "simple")),
        "imparticiones_activas": sum(len(t["imparticiones"]) for t in activos),
        "presencialidad_imparticiones_activas": dict(Counter(i["presencialidad"] for t in activos for i in t["imparticiones"])),
        "universidades_con_master_vivo": len({t["universidad"] for t in vivos}),
        "imparticiones_sin_codigo_de_centro": sum(1 for t in catalogo for i in t["imparticiones"] if not i["unidad_codigo"]),
    }


def ejecutar(raiz: Path) -> dict:
    archivo = Archivo(raiz / "archivo")
    hoy = date.today()
    pagina = obtener(PAGINA)
    if pagina.status != 200:
        raise ErrorCatalogo(f"Página de clasificaciones: estado {pagina.status}")
    archivo.guardar(FUENTE, hoy, pagina.contenido, PAGINA, "html", pagina.status, pagina.cabeceras)
    urls = descubrir(pagina.contenido.decode("utf-8", "replace"))
    leidos = {}
    for nombre, url in urls.items():
        time.sleep(1)
        r = obtener(url)
        if r.status != 200:
            raise ErrorCatalogo(f"{nombre}: estado {r.status} en {url}")
        reg = archivo.guardar(FUENTE, hoy, r.contenido, url, "xlsx", r.status, r.cabeceras)
        _, clave, hoja = FICHEROS[nombre]
        leidos[nombre] = filas(r.contenido, clave, hoja)
        leidos[nombre + "_captura"] = {"url": url, "sha256": reg["sha256"], "capturado": reg["capturado"]}
    curso = _curso(leidos["titulaciones_captura"]["url"], hoy)
    catalogo = construir(leidos["titulaciones"], leidos["rama"], leidos["centros"], leidos["universidades"], curso)
    for t in catalogo:
        t["fuente"]["url"] = leidos["titulaciones_captura"]["url"]
        t["fuente"]["sha256"] = leidos["titulaciones_captura"]["sha256"]
        t["fuente"]["capturado"] = leidos["titulaciones_captura"]["capturado"]
    destino = raiz / "datos" / "estudios" / "masters"
    destino.mkdir(parents=True, exist_ok=True)
    with (destino / "catalogo.jsonl").open("w", encoding="utf-8") as f:
        for t in catalogo:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    res = resumen(catalogo)
    res["capturas"] = {k[:-8]: v for k, v in leidos.items() if k.endswith("_captura")}
    (destino / "catalogo_resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def _curso(url: str, hoy: date) -> str:
    m = re.search(r"-(20\d\d)\.xlsx", url)
    inicio = int(m.group(1)) if m else (hoy.year if hoy.month >= 9 else hoy.year - 1)
    return f"{inicio}-{inicio + 1}"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    try:
        res = ejecutar(Path(a.salida))
    except ErrorCatalogo as e:
        print(f"ALERTA catálogo SIIU: {e}", file=sys.stderr)
        sys.exit(2)
    print(json.dumps({k: v for k, v in res.items() if k != "capturas"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
