"""Ejecución del conector del BOE.

Uso:
  python -m motor.boe                          # hoy y ayer (hora de Madrid)
  python -m motor.boe --desde 2026-10-01 --hasta 2026-10-28
  python -m motor.boe --salida ruta/            # carpeta raíz de archivo/ y datos/

Para cada día:
  1. descarga el sumario (XML) y guarda el original intacto en archivo/boe-sumario/;
  2. extrae todas las disposiciones a datos/boe/sumarios/AAAA/MM/DD.jsonl;
  3. clasifica la sección II.B a datos/boe/oposiciones/AAAA/MM/DD.jsonl;
  4. actualiza datos/boe/estado.json y lanza alertas (día laborable sin BOE, saltos de numeración,
     cambio de formato, sección II.B vacía en día laborable).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.limpieza import titulo_sin_nombres
from motor.boe import clasificar as cl
from motor.boe.sumario import ACCEPT, ErrorSumario, parsear, url_sumario
from motor.http import obtener

MADRID = ZoneInfo("Europe/Madrid")
FUENTE = "boe-sumario"


def _escribir_jsonl(ruta: Path, filas: list[dict]) -> None:
    """Escribe las filas; el nombre de una persona en el título (nombramientos individuales) se sustituye."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8") as f:
        for fila in filas:
            if fila.get("titulo"):
                fila = {**fila, "titulo": titulo_sin_nombres(fila["titulo"])}
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")


def _ruta_dia(base: Path, d: date) -> Path:
    return base / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.jsonl"


def _ruta_informe(raiz: Path, d: date) -> Path:
    return raiz / "datos" / "boe" / "dias" / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.json"


def ya_procesado(raiz: Path, d: date) -> bool:
    ruta = _ruta_informe(raiz, d)
    if not ruta.exists():
        return False
    return json.loads(ruta.read_text(encoding="utf-8")).get("resultado") in {"ok", "sin_boletin"}


def procesar_dia(d: date, raiz: Path, archivo: Archivo, estado: dict) -> dict:
    informe = _procesar_dia(d, raiz, archivo, estado)
    ruta = _ruta_informe(raiz, d)
    # Un fallo pasajero al volver a pedir un día ya leído bien no borra lo que había (el 30/10/2026 un HTTP 500 del
    # BOE dejó como erróneos el 29 y el 30, que estaban bien): se conserva el informe bueno y se avisa
    if informe["resultado"] in {"error_http", "error_formato"} and ruta.exists():
        previo = json.loads(ruta.read_text(encoding="utf-8"))
        if previo.get("resultado") == "ok":
            print(f"{d}: {'; '.join(informe['alertas'])}; se conserva la lectura anterior, que estaba bien")
            return {**previo, "alertas": previo.get("alertas", []) + [f"{a} (se conserva la lectura anterior)"
                                                                     for a in informe["alertas"]]}
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding="utf-8")
    return informe


def _procesar_dia(d: date, raiz: Path, archivo: Archivo, estado: dict) -> dict:
    url = url_sumario(d)
    resp = obtener(url, accept=ACCEPT)
    captura = archivo.guardar(FUENTE, d, resp.contenido, url, "xml", resp.status, resp.cabeceras)
    informe = {"fecha": d.isoformat(), "status": resp.status, "sha256": captura["sha256"], "alertas": []}
    laborable = d.weekday() < 6  # el BOE sale de lunes a sábado

    if resp.status == 404:
        informe["resultado"] = "sin_boletin"
        if laborable:
            informe["alertas"].append(f"{d}: día de lunes a sábado sin sumario (¿festivo o fuente caída?)")
        return informe
    if resp.status != 200:
        informe["resultado"] = "error_http"
        informe["alertas"].append(f"{d}: HTTP {resp.status} al pedir el sumario")
        return informe

    try:
        sumario = parsear(resp.contenido)
    except ErrorSumario as e:
        informe["resultado"] = "error_formato"
        informe["alertas"].append(f"{d}: {e}")
        return informe

    capturado = captura["capturado"]
    filas = []
    for it in sumario.items:
        it.update({"fecha": d.isoformat(), "fuente": FUENTE, "captura_sha256": captura["sha256"], "capturado": capturado})
        filas.append(it)
    _escribir_jsonl(_ruta_dia(raiz / "datos" / "boe" / "sumarios", d), filas)

    oposiciones = []
    for it in filas:
        if it.get("seccion_codigo") == cl.SECCION_OPOSICIONES:
            oposiciones.append({**it, **cl.clasificar(it)})
    _escribir_jsonl(_ruta_dia(raiz / "datos" / "boe" / "oposiciones", d), oposiciones)

    # Controles de cobertura
    numeros = sorted(int(x["numero"]) for x in sumario.diarios if (x["numero"] or "").isdigit())
    anterior = estado.get("ultimo_diario")
    if numeros and anterior and anterior.get("anio") == d.year and numeros[0] > anterior["numero"] + 1 \
            and d > date.fromisoformat(anterior["fecha"]):
        informe["alertas"].append(
            f"{d}: salto de numeración del BOE ({anterior['numero']} → {numeros[0]}); revisar números no capturados")
    if numeros and (not anterior or d >= date.fromisoformat(anterior["fecha"])):
        estado["ultimo_diario"] = {"fecha": d.isoformat(), "numero": numeros[-1], "anio": d.year}
    if not filas:
        informe["alertas"].append(f"{d}: sumario sin disposiciones (posible cambio de formato)")
    if laborable and d.weekday() < 5 and not oposiciones:
        informe["alertas"].append(f"{d}: sección II.B vacía en día laborable (revisar)")

    informe.update({
        "resultado": "ok",
        "diarios": [x["numero"] for x in sumario.diarios],
        "disposiciones": len(filas),
        "oposiciones": len(oposiciones),
        "por_ambito": dict(Counter(o["ambito"] for o in oposiciones)),
        "por_acto": dict(Counter(o["tipo_acto"] for o in oposiciones)),
        "pendientes_revision": sum(1 for o in oposiciones if o["pendiente_revision"]),
    })
    return informe


def _resumen_md(informes: list[dict]) -> str:
    lineas = ["# Conector BOE", "", "| Fecha | Resultado | Disposiciones | II.B | Por ámbito | Por acto | Pendientes |",
              "|---|---|---|---|---|---|---|"]
    for i in informes:
        lineas.append(
            f"| {i['fecha']} | {i.get('resultado')} | {i.get('disposiciones', '')} | {i.get('oposiciones', '')} | "
            f"{i.get('por_ambito', '')} | {i.get('por_acto', '')} | {i.get('pendientes_revision', '')} |")
    alertas = [a for i in informes for a in i["alertas"]]
    lineas += ["", "## Alertas", ""] + ([f"- {a}" for a in alertas] or ["- Ninguna"])
    return "\n".join(lineas) + "\n"


def main(argv: list[str] | None = None) -> int:
    hoy = datetime.now(MADRID).date()
    p = argparse.ArgumentParser(description="Conector del sumario diario del BOE")
    p.add_argument("--desde", type=date.fromisoformat, default=hoy - timedelta(days=1))
    p.add_argument("--hasta", type=date.fromisoformat, default=hoy)
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--pausa", type=float, default=1.0, help="segundos entre peticiones")
    p.add_argument("--saltar-existentes", action="store_true",
                   help="no volver a pedir días ya procesados (para cargas históricas)")
    a = p.parse_args(argv)
    if a.hasta < a.desde:
        p.error("--hasta es anterior a --desde")

    raiz: Path = a.salida
    archivo = Archivo(raiz / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    ruta_estado = raiz / "datos" / "boe" / "estado.json"
    estado = json.loads(ruta_estado.read_text(encoding="utf-8")) if ruta_estado.exists() else {}

    informes = []
    d = a.desde
    while d <= a.hasta:
        if a.saltar_existentes and ya_procesado(raiz, d):
            d += timedelta(days=1)
            continue
        try:
            informes.append(procesar_dia(d, raiz, archivo, estado))
        except ConnectionError as e:
            informes.append({"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]})
        d += timedelta(days=1)
        if d <= a.hasta:
            time.sleep(a.pausa)

    estado["ultima_ejecucion"] = datetime.now(MADRID).isoformat(timespec="seconds")
    estado["alertas_ultima_ejecucion"] = [x for i in informes for x in i["alertas"]]
    ruta_estado.parent.mkdir(parents=True, exist_ok=True)
    ruta_estado.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")

    resumen = _resumen_md(informes)
    print(resumen)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(resumen)
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
