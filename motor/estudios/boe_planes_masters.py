"""Planes de estudios de los másteres oficiales publicados en el BOE: asignaturas con créditos y carácter.

La ficha del RUCT de cada máster da el identificador BOE de su plan («Plan Estudios en el BOE»), así que la unión
con el código es exacta, sin parecido de nombres. Los textos se piden en la versión HTML del BOE (su robots.txt la
permite; motor/boe/texto.py, que ya retira los párrafos con datos personales), uno cada dos segundos.

Las tablas se leen con el lector de planes de grados (motor/grados/boe_grados.py, sin modificarlo): reconoce
también «TFM» y «Trabajo Fin de Máster». Un plan cuenta como comprobado si la suma de sus filas cuadra con su
propia tabla de créditos por tipo; si no, se guarda igual, marcado. El plan del BOE es el de la verificación y sus
modificaciones publicadas: si el RUCT tiene una memoria posterior, manda la memoria (conjunto_masters.py).

Uso:
  python -m motor.estudios.boe_planes_masters textos --ruct carpeta [--ruct …] [--desde 0 --hasta 800] --salida ruta/
  python -m motor.estudios.boe_planes_masters medir --textos ruta/datos/boe/textos --ruct carpeta --salida ruta/
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

FUENTE_CITA = "Agencia Estatal Boletín Oficial del Estado"
PAUSA = 2.0


def ids_de_ruct(carpetas: list[Path]) -> dict[str, list[str]]:
    """Identificador BOE del plan → códigos RUCT que lo tienen en su ficha."""
    from motor.estudios.conjunto_masters import cargar_ruct

    out: dict[str, list[str]] = {}
    for cod, f in sorted(cargar_ruct(carpetas).items()):
        ident = (((f.get("boe") or {}).get("plan") or {}).get("identificador") or "").strip()
        if ident.startswith("BOE-"):
            out.setdefault(ident, []).append(cod)
    return out


def cmd_textos(ruct: list[Path], salida: Path, desde: int, hasta: int | None, max_minutos: float,
               ya: set[str] | None = None) -> dict:
    from motor.archivo import Archivo, solo_huella_por_defecto
    from motor.boe.texto import descargar

    ids = sorted(ids_de_ruct(ruct))[desde:hasta]
    ids = [i for i in ids if i not in (ya or set())]
    archivo = Archivo(salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    fin = time.monotonic() + max_minutos * 60
    hechos, errores = 0, []
    for ident in ids:
        if time.monotonic() > fin:
            errores.append(f"tiempo agotado: quedan {len(ids) - hechos - len(errores)}")
            break
        try:
            r = descargar(ident, salida, archivo)
        except ConnectionError as e:
            r = str(e)[:200]
        if r == "ok":
            hechos += 1
        else:
            errores.append(f"{ident}: {r}")
        time.sleep(PAUSA)
    return {"pedidos": len(ids), "descargados": hechos, "errores": len(errores), "primeros_errores": errores[:20]}


def leer_plan(doc: dict) -> list[dict]:
    """Cada plan del documento (una resolución puede traer varios) con sus filas y su comprobación."""
    from motor.grados import boe_grados as bg

    out = []
    for parte in bg.separar_planes(doc):
        m = bg.medir_plan(parte)
        filas = m.pop("filas_plan")
        out.append({**m, "titulo_plan": parte.get("titulo_grado"), "parte": parte.get("parte"),
                    "filas_plan": [{k: f.get(k) for k in ("nivel", "nombre", "creditos", "tipo", "caracter", "curso",
                                                          "semestre", "modulo") if f.get(k) is not None} for f in filas]})
    return out


def cmd_medir(textos: Path, ruct: list[Path], salida: Path) -> dict:
    por_id = ids_de_ruct(ruct)
    destino = salida / "datos" / "estudios" / "masters"
    destino.mkdir(parents=True, exist_ok=True)
    filas, cuentas = [], {"documentos": 0, "planes": 0, "con_asignaturas": 0, "comprobados": 0, "codigos": 0}
    for ruta in sorted(textos.rglob("*.json")):
        try:
            doc = json.loads(ruta.read_text(encoding="utf-8"))
        except ValueError:
            continue
        ident = doc.get("identificador")
        if ident not in por_id:
            continue
        cuentas["documentos"] += 1
        planes = leer_plan(doc)
        # varios planes en una resolución: sin el título de cada uno no se sabe cuál es de cada código; se guarda
        # el documento con todos y la ficha solo usa uno si es el único
        for p in planes:
            cuentas["planes"] += 1
            cuentas["con_asignaturas"] += bool(p["filas_plan"])
            cuentas["comprobados"] += bool(p["comprobacion"])
        filas.append({"identificador": ident, "codigos_ruct": por_id[ident], "titulo": doc.get("titulo"),
                      "fecha_publicacion": doc.get("fecha_publicacion"), "url": doc.get("url"),
                      "capturado": doc.get("capturado"), "captura_sha256": doc.get("captura_sha256"),
                      "cita": FUENTE_CITA, "planes": planes})
        cuentas["codigos"] += len(por_id[ident])
    (destino / "boe_planes_masters.jsonl").write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in filas),
                                                       encoding="utf-8")
    (destino / "boe_planes_masters_resumen.json").write_text(json.dumps(cuentas, ensure_ascii=False, indent=1),
                                                             encoding="utf-8")
    return cuentas


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="orden", required=True)
    t = sub.add_parser("textos")
    t.add_argument("--desde", type=int, default=0)
    t.add_argument("--hasta", type=int)
    t.add_argument("--max-minutos", type=float, default=50)
    m = sub.add_parser("medir")
    m.add_argument("--textos", required=True)
    for s in (t, m):
        s.add_argument("--ruct", action="append", default=[])
        s.add_argument("--salida", required=True)
    a = p.parse_args()
    if a.orden == "textos":
        res = cmd_textos([Path(x) for x in a.ruct], Path(a.salida), a.desde, a.hasta, a.max_minutos)
        res["medicion"] = cmd_medir(Path(a.salida) / "datos" / "boe" / "textos", [Path(x) for x in a.ruct], Path(a.salida))
    else:
        res = cmd_medir(Path(a.textos), [Path(x) for x in a.ruct], Path(a.salida))
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
