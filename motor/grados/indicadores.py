"""Indicadores de rendimiento académico de grado (SIIU, Ministerio de Ciencia, Innovación y Universidades).

El Ministerio publica en su base estadística (PC-Axis) los indicadores de grado por universidad y ámbito de estudio,
con series desde 2011-2012: abandono (primer año, segundo, tercero), cambio de estudio, abandono del sistema,
graduación, rendimiento, éxito, evaluación, eficiencia, idoneidad, nota del expediente, duración media y transición
a máster. https://www.ciencia.gob.es/Ministerio/Estadisticas/SIIU/Rendimiento.html (enlace «Indicadores de
rendimiento académico y de transición a Máster de estudiantes de Grado»).

El ámbito de estudio es el mismo campo que trae el catálogo SIIU de cada título («Ámbito de estudio»), así que la
pareja universidad × ámbito se une a cada grado. Cuando una universidad tiene varios grados en el mismo ámbito, el
dato es del conjunto de esos grados y la ficha lo dice así.

Fichero bruto: https://estadisticas.ciencia.gob.es/jaxiPx/files/_px/es/px/Universitaria/Indicadores/{edicion}/1_Grado/l0/{tabla}?nocab=1
(robots.txt del servidor: 404, sin reglas; sonda del 30/10/2026).

Uso:
  python -m motor.grados.indicadores --edicion 2025 --salida ruta/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.http import obtener

BASE = "https://estadisticas.ciencia.gob.es/jaxiPx/files/_px/es/px/Universitaria/Indicadores/{edicion}/1_Grado/l0/{tabla}?nocab=1"
FUENTE = "siiu-indicadores"
CITA = "Ministerio de Ciencia, Innovación y Universidades. Indicadores de rendimiento académico (SIIU)"
TABLAS = {
    "abandono": "Abandono_Grado_Univ.px",
    "cambio": "Cambio_Grado_Univ.px",
    "abandono_sistema": "AbandonoSUE_Grado_Univ.px",
    "graduacion": "Graduacion_Grado_Univ.px",
    "idoneidad": "Idoneidad_Grado_Univ.px",
    "rendimiento": "Rendimiento_Exito_Eval_Grado_Univ.px",
    "eficiencia": "Eficiencia_Exito_Eval_Grado_Univ.px",
    "nota_expediente": "Nota_Expediente_Grado_Univ.px",
    "duracion": "Duracion_Grado_Univ.px",
    "transicion_master": "Transicion_G_M_Univ.px",
}


# --------------------------------------------------------------------------------------------- PC-Axis


def _cadenas(valor: str) -> list[str]:
    return re.findall(r'"((?:[^"]|"")*)"', valor)


def leer_px(texto: str) -> dict:
    """Lee un fichero PC-Axis: metadatos, variables (STUB y HEADING) con sus valores y la matriz DATA.

    Formato: CLAVE[("variable")]=valor; con cadenas entre comillas que pueden seguir en varias líneas. Los datos van
    en orden de filas: la última variable de HEADING es la que cambia más deprisa."""
    i = texto.find("DATA=")
    if i < 0:
        raise ValueError("fichero PC-Axis sin DATA")
    cabecera, datos = texto[:i], texto[i + 5:]
    meta: dict = {}
    valores: dict[str, list[str]] = {}
    for m in re.finditer(r'([A-Z][A-Z0-9-]*)(?:\[[^\]]*\])?(?:\("([^"]*)"\))?=(.*?);\s*(?=[A-Z][A-Z0-9-]*(?:\[|\(|=)|$)',
                         cabecera, re.S):
        clave, variable, valor = m.group(1), m.group(2), m.group(3)
        if clave == "VALUES" and variable:
            valores[variable] = _cadenas(valor)
        elif clave in ("STUB", "HEADING"):
            meta[clave] = _cadenas(valor)
        elif not variable:
            cad = _cadenas(valor)
            meta[clave] = "".join(cad) if cad else valor.strip()
    numeros = re.findall(r'"[^"]*"|[^\s;"]+', datos.split(";")[0])
    return {"meta": meta, "variables": meta.get("STUB", []) + meta.get("HEADING", []), "valores": valores,
            "datos": numeros}


def _valor(s: str) -> float | None:
    s = s.strip('"')
    if s in {".", "..", "...", "-", ""}:
        return None
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def filas(px: dict, filtro: dict[str, str] | None = None):
    """Recorre la matriz como filas {variable: valor, ..., "valor": número}."""
    variables = px["variables"]
    tam = [len(px["valores"][v]) for v in variables]
    total = 1
    for t in tam:
        total *= t
    if len(px["datos"]) != total:
        raise ValueError(f"DATA tiene {len(px['datos'])} valores y la matriz {total}")
    idx = [0] * len(variables)
    for n in range(total):
        fila = {v: px["valores"][v][idx[k]] for k, v in enumerate(variables)}
        if not filtro or all(fila.get(k) == v for k, v in filtro.items()):
            fila["valor"] = _valor(px["datos"][n])
            yield fila
        for k in range(len(variables) - 1, -1, -1):  # la última variable cambia más deprisa
            idx[k] += 1
            if idx[k] < tam[k]:
                break
            idx[k] = 0


# ---------------------------------------------------------------------------------------------- ejecución


def ejecutar(edicion: str, raiz: Path, tablas: list[str]) -> dict:
    archivo = Archivo(raiz / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    destino = raiz / "datos" / "estudios" / "grados" / "indicadores"
    destino.mkdir(parents=True, exist_ok=True)
    res = {}
    for nombre in tablas:
        url = BASE.format(edicion=edicion, tabla=TABLAS[nombre])
        time.sleep(1)
        r = obtener(url, timeout=120, limite_total=600)
        if r.status != 200:
            res[nombre] = f"HTTP {r.status}"
            continue
        cap = archivo.guardar(FUENTE, date.today(), r.contenido, url, "px", r.status, r.cabeceras)
        texto = r.contenido.decode("iso-8859-15", "replace")
        px = leer_px(texto)
        sexo = next((v for v in px["variables"] if v.lower() == "sexo"), None)
        filtro = {sexo: "Ambos sexos"} if sexo else None
        n = 0
        capturado = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with (destino / f"{nombre}.jsonl").open("w", encoding="utf-8") as f:
            for fila in filas(px, filtro):
                if fila["valor"] is None:
                    continue
                fila.pop(sexo, None)
                fila["fuente"] = {"cita": CITA, "url": url, "sha256": cap["sha256"], "capturado": capturado,
                                  "creado": px["meta"].get("CREATION-DATE")}
                f.write(json.dumps(fila, ensure_ascii=False) + "\n")
                n += 1
        res[nombre] = {"filas": n, "variables": px["variables"],
                       "periodos": sorted(px["valores"].get("Periodo", []))[-3:],
                       "indicadores": px["valores"].get("Indicador", [])}
    (destino / "resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--edicion", default="2025")
    p.add_argument("--tablas", default=",".join(TABLAS))
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    try:
        res = ejecutar(a.edicion, Path(a.salida), [t for t in a.tablas.split(",") if t])
    except ValueError as e:
        print(f"ALERTA indicadores SIIU: {e}", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
