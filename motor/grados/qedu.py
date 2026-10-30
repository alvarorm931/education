"""QEDU (Qué Estudiar y Dónde en la Universidad), del Ministerio de Ciencia, Innovación y Universidades.

Es la única fuente oficial que reúne, por grado y centro: plazas de nuevo ingreso, nota de corte final (del curso
y del anterior), nota media de admisión, créditos, precio del crédito en primera matrícula (públicas) e inserción
laboral (tasa de afiliación, autónomos, contratos indefinidos, cotización adecuada al nivel y base media de
cotización). https://www.ciencia.gob.es/qedu.html

La página pide los datos con POST a /home/qedu/main/zona02/0 (medido el 30/10/2026 con sondas desde GitHub; su
robots.txt lo permite):
  - action=tarjeta, niveles='GRADO','GRADOD', ambitos=<los 35 ámbitos>  → las 5.486 imparticiones de grado y
    doble grado del curso 2025-2026 (título × centro), con códigos oficiales de título, centro y universidad;
  - action=detalle, codTit, codCentro, codUniv                          → la ficha de una impartición;
  - action=detalleIn, codTit, codCentro, codUniv, nivel, ambito         → la inserción laboral del título;
  - action=detalleAmb, ambito, nivel                                    → la del ámbito, por sexo (comparación).

Uso:
  python -m motor.grados.qedu tarjetas --salida ruta/
  python -m motor.grados.qedu detalles --tarjetas ruta/…/qedu_tarjetas.jsonl --desde 0 --hasta 1500 --salida ruta/
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

URL = "https://www.ciencia.gob.es/home/qedu/main/zona02/0"
PAGINA = "https://www.ciencia.gob.es/qedu.html"
FUENTE = "qedu"
CITA = "Ministerio de Ciencia, Innovación y Universidades. Qué Estudiar y Dónde en la Universidad (QEDU)"
AMBITOS = ("109,143,144,149,209,213,219,228,229,309,311,314,319,320,345,349,380,409,420,440,460,480,509,580,609,"
           "620,640,709,721,723,729,760,809,813,819")
NIVELES = {"grado": "'GRADO','GRADOD'", "master": "'MASTER','MASTERD'"}
PAUSA = 1.0
SIN_DATO = {"", "N/A", "N/D", "-", "NA", "ND"}


def numero(valor) -> float | None:
    """«65,67%», «29 115,69 €», «8,44», «N/D» → 65.67, 29115.69, 8.44, None."""
    if valor is None:
        return None
    s = str(valor).strip()
    if s.upper() in SIN_DATO:
        return None
    s = re.sub(r"[%€\s ]", "", s)
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", s):  # «1.234,5»
        s = s.replace(".", "")
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def limpiar_detalle(d: dict) -> dict:
    return {
        "titulacion": d.get("titulacion"),
        "centro": d.get("nombreCentro"),
        "tipo_centro": d.get("tipoCentro"),
        "modalidad": d.get("modalidad"),
        "idioma_extranjero": d.get("idiomaextranjero"),
        "plazas": numero(d.get("plazas")),
        "tasa_afiliacion": numero(d.get("tasas")),  # en la página: «Tasa de afiliación»
        "creditos": numero(d.get("creditos")),
        "precio_credito": numero(d.get("precio")),
        "nota_corte": numero(d.get("notaCorte")),
        "nota_corte_anterior": numero(d.get("notaCorteAnt")),
        "nota_media_admision": numero(d.get("notaAdmision")),
        "curso": d.get("anioActual"),
        "curso_anterior": d.get("anioAnterior"),
        "ambito": d.get("ambito"),
        "nivel": d.get("nivel"),
        "enlace": d.get("enlace"),
    }


def limpiar_insercion(d: dict) -> dict:
    return {
        "tasa_afiliacion": numero(d.get("tasaAfiliacion")),
        "autonomos": numero(d.get("porcentajeAutonomos")),
        "indefinidos": numero(d.get("porcentajeIndefinidos")),
        "cotizacion_adecuada": numero(d.get("porcentajeCotizacion")),
        "base_media_cotizacion": numero(d.get("baseMedia")),
    }


class Qedu:
    def __init__(self, archivo: Archivo | None, pausa: float = PAUSA):
        self.archivo = archivo
        self.pausa = pausa
        self.peticiones = 0

    def post(self, campos: dict[str, str]):
        time.sleep(self.pausa)
        self.peticiones += 1
        r = obtener(URL, accept="application/json", formulario=campos, timeout=60, limite_total=240,
                    cabeceras_extra={"X-Requested-With": "XMLHttpRequest", "Referer": PAGINA})
        if r.status != 200:
            raise ConnectionError(f"QEDU {campos.get('action')}: HTTP {r.status}")
        reg = None
        if self.archivo is not None:
            # La URL del original identifica la consulta (es un POST): se anota con sus campos
            consulta = URL + "?" + "&".join(f"{k}={v}" for k, v in campos.items())
            reg = self.archivo.guardar(FUENTE, date.today(), r.contenido, consulta, "json", r.status, r.cabeceras)
        texto = r.contenido.decode("utf-8", "replace").strip()
        return (json.loads(texto) if texto else None), reg

    def tarjetas(self, nivel: str = "grado") -> tuple[list[dict], dict | None]:
        datos, reg = self.post({"action": "tarjeta", "offset": "0", "consulta": "", "niveles": NIVELES[nivel],
                                "ambitos": AMBITOS})
        return datos or [], reg

    def detalle(self, t: dict) -> tuple[dict | None, dict | None]:
        return self.post({"action": "detalle", "codTit": t["codTitula"], "codCentro": t["codCentro"],
                          "codUniv": t["codUniv"]})

    def insercion(self, t: dict, nivel: str, ambito: str) -> tuple[dict | None, dict | None]:
        return self.post({"action": "detalleIn", "codTit": t["codTitula"], "codCentro": t["codCentro"],
                          "codUniv": t["codUniv"], "nivel": nivel, "ambito": ambito})


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _destino(raiz: Path) -> Path:
    d = raiz / "datos" / "estudios" / "grados" / "qedu"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cmd_tarjetas(raiz: Path, nivel: str) -> dict:
    archivo = Archivo(raiz / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    q = Qedu(archivo)
    datos, reg = q.tarjetas(nivel)
    datos = sorted(datos, key=lambda t: (t["codTitula"], t["codCentro"], t["codUniv"]))
    capturado = _ahora()
    with (_destino(raiz) / f"qedu_tarjetas_{nivel}.jsonl").open("w", encoding="utf-8") as f:
        for t in datos:
            f.write(json.dumps({**t, "fuente": {"cita": CITA, "url": PAGINA, "capturado": capturado,
                                                "sha256": reg["sha256"] if reg else None}}, ensure_ascii=False) + "\n")
    return {"tarjetas": len(datos), "titulos": len({t["codTitula"] for t in datos}),
            "con_nota_de_corte": sum(1 for t in datos if numero(t.get("notaCorte")) is not None),
            "cursos": sorted({t.get("anio") for t in datos})}


def cmd_detalles(raiz: Path, tarjetas: Path, desde: int, hasta: int | None, max_minutos: float) -> dict:
    archivo = Archivo(raiz / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    q = Qedu(archivo)
    lista = [json.loads(x) for x in tarjetas.read_text(encoding="utf-8").splitlines() if x.strip()][desde:hasta]
    fin = time.time() + max_minutos * 60
    hechos, errores, seguidos = 0, [], 0
    salida = _destino(raiz) / f"qedu_detalles_{desde}_{hasta or 'fin'}.jsonl"
    with salida.open("w", encoding="utf-8") as f:
        for t in lista:
            if time.time() > fin:
                break
            reg: dict = {"codTitula": t["codTitula"], "codCentro": t["codCentro"], "codUniv": t["codUniv"],
                         "nivel_qedu": t.get("nivel")}
            try:
                bruto, cap = q.detalle(t)
                reg["detalle"] = limpiar_detalle(bruto or {})
                reg["detalle_bruto"] = bruto
                nivel = (bruto or {}).get("nivel") or t.get("nivel")
                ambito = ((bruto or {}).get("ambito") or "").split(",")[0]
                if ambito:
                    ins, _ = q.insercion(t, nivel, ambito)
                    reg["insercion"] = limpiar_insercion(ins) if isinstance(ins, dict) else None
                    reg["insercion_bruto"] = ins
                reg["fuente"] = {"cita": CITA, "url": PAGINA, "capturado": _ahora(),
                                 "sha256_detalle": cap["sha256"] if cap else None}
                seguidos = 0
            except (ConnectionError, ValueError) as e:
                errores.append(f"{t['codTitula']}/{t['codCentro']}: {str(e)[:150]}")
                seguidos += 1
                if seguidos >= 5:
                    print("ALERTA QEDU: cinco errores seguidos; ejecución detenida", file=sys.stderr)
                    break
                continue
            f.write(json.dumps(reg, ensure_ascii=False) + "\n")
            hechos += 1
    return {"pedidas": len(lista), "hechas": hechos, "errores": len(errores), "primeros_errores": errores[:10],
            "peticiones": q.peticiones, "fichero": salida.name}


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="orden", required=True)
    a = sub.add_parser("tarjetas")
    a.add_argument("--nivel", choices=list(NIVELES), default="grado")
    d = sub.add_parser("detalles")
    d.add_argument("--tarjetas", required=True)
    d.add_argument("--desde", type=int, default=0)
    d.add_argument("--hasta", type=int)
    d.add_argument("--max-minutos", type=float, default=52)
    for s in (a, d):
        s.add_argument("--salida", required=True)
    x = p.parse_args()
    if x.orden == "tarjetas":
        res = cmd_tarjetas(Path(x.salida), x.nivel)
    else:
        res = cmd_detalles(Path(x.salida), Path(x.tarjetas), x.desde, x.hasta, x.max_minutos)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
