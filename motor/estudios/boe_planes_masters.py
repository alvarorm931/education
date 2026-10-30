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
import re
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


RE_PLAN = re.compile(r"(?i)de la (?P<uni>Universi[dt]a[dt]\b.+?|Universidade\b.+?|Mondragon Unibertsitatea|[^,]*Unibertsitatea),"
                     r".*?plan(?:es)? de estudios? de (?P<nombre>M[áa]ster Universitario.+?)\.?\s*$")


def _clave_uni(s: str) -> str:
    import unicodedata

    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\b(universidad|universitat|universidade|unibertsitatea|de|del|la|las|los|d|l|i|y|e)\b", " ", s)
    return " ".join(re.findall(r"[a-z0-9]+", s))


def ids_por_nombre(resoluciones: list[dict], catalogo: list[dict]) -> dict[str, list[str]]:
    """Planes y modificaciones de plan del BOE (2022-2026) unidos al código por universidad y nombre: solo si un
    único máster activo de esa universidad tiene ese nombre confirmado (fichas_masters.comprobar_nombre)."""
    from motor.estudios.fichas_masters import comprobar_nombre

    por_uni: dict[str, list[dict]] = {}
    for t in catalogo:
        if t.get("situacion") == "Activo":
            por_uni.setdefault(_clave_uni(t.get("universidad")), []).append(t)
    out: dict[str, list[str]] = {}
    for r in resoluciones:
        if r.get("tipo") not in ("plan", "plan_modif"):
            continue
        m = RE_PLAN.search(r.get("titulo") or "")
        if not m:
            continue
        cu = _clave_uni(m.group("uni"))
        candidatos = [t for k, ts in por_uni.items() if k and (k == cu or k in cu or cu in k) for t in ts]
        buenos = [t for t in candidatos if comprobar_nombre(t["nombre_oficial"], m.group("nombre"))[0] == "confirmado"
                  and comprobar_nombre(m.group("nombre"), t["nombre_oficial"])[0] == "confirmado"]
        if len(buenos) == 1:
            out.setdefault(r["identificador"], []).append(buenos[0]["codigo_ruct"])
    return out


def cmd_textos(ruct: list[Path], salida: Path, desde: int, hasta: int | None, max_minutos: float,
               ya: set[str] | None = None, por_nombre: dict[str, list[str]] | None = None) -> dict:
    from motor.archivo import Archivo, solo_huella_por_defecto
    from motor.boe.texto import descargar

    ids = sorted(set(ids_de_ruct(ruct)) | set(por_nombre or {}))[desde:hasta]
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


def cmd_medir(textos: Path, ruct: list[Path], salida: Path, por_nombre: dict[str, list[str]] | None = None) -> dict:
    por_id = ids_de_ruct(ruct)
    union = {i: "ficha_ruct" for i in por_id}
    for i, cs in (por_nombre or {}).items():
        if i not in por_id:
            por_id[i], union[i] = cs, "nombre_y_universidad"
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
        filas.append({"identificador": ident, "codigos_ruct": por_id[ident], "union": union[ident], "titulo": doc.get("titulo"),
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
        s.add_argument("--resoluciones", help="resoluciones de máster del BOE (lista JSON con identificador, título, tipo)")
        s.add_argument("--catalogo", help="catálogo para unir las resoluciones por universidad y nombre")
        s.add_argument("--salida", required=True)
    a = p.parse_args()
    por_nombre = None
    if a.resoluciones and a.catalogo:
        por_nombre = ids_por_nombre(json.loads(Path(a.resoluciones).read_text(encoding="utf-8")),
                                    json.loads(Path(a.catalogo).read_text(encoding="utf-8")))
    if a.orden == "textos":
        res = cmd_textos([Path(x) for x in a.ruct], Path(a.salida), a.desde, a.hasta, a.max_minutos, por_nombre=por_nombre)
        res["medicion"] = cmd_medir(Path(a.salida) / "datos" / "boe" / "textos", [Path(x) for x in a.ruct], Path(a.salida),
                                    por_nombre)
    else:
        res = cmd_medir(Path(a.textos), [Path(x) for x in a.ruct], Path(a.salida), por_nombre)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
