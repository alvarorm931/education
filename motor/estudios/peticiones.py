"""Lista de centros a los que pedir los datos que no publican (docs/estrategia-informacion-cerrada.md, §3.4).

Antes de la extracción ya se sabe, por la medición de sus fichas, qué centros piden el correo y no dan ningún
importe. Esta lista ordena a quién pedir primero: más fichas de programa y más fichas tras formulario. No guarda
datos de personas: el canal de contacto se elige después entre los institucionales del centro.

Las peticiones se envían cuando el portal tenga dirección pública (§3.4) y las envía Álvaro desde la cuenta
del portal; el motor solo prepara la lista y registra respuestas en `facilitados.jsonl`.

Uso:
  python -m motor.estudios.peticiones --censo proveedores.jsonl --rastreo carpeta [--rastreo …] --salida ruta/
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

CAMPOS_SI_FALTA = {
    "precio_total": lambda m: m.get("importes_euros", 0) == 0 and not m.get("precio_jsonld"),
    "metodologia": lambda m: not m.get("temas", {}).get("metodologia"),
    "evaluacion": lambda m: not m.get("temas", {}).get("evaluacion"),
    "plazas": lambda m: not m.get("temas", {}).get("plazas"),
    "horario": lambda m: not m.get("temas", {}).get("horario"),
    "asignaturas": lambda m: not m.get("temas", {}).get("asignaturas"),
}


def prioridad(prov: dict, r: dict) -> dict | None:
    fichas = [m for m in r.get("muestra", []) if m.get("es_programa")]
    if not fichas or r.get("reserva_tdm"):
        return None
    tras_formulario = [m for m in fichas if m.get("formulario_pide_correo") and CAMPOS_SI_FALTA["precio_total"](m)]
    faltan = Counter(c for m in fichas for c, f in CAMPOS_SI_FALTA.items() if f(m))
    return {
        "id": prov["id"], "dominio": prov["dominio"], "estado": prov["estado"], "tipos": prov.get("tipos", []),
        "urls_programa": r.get("urls_programa", 0), "fichas_medidas": len(fichas),
        "fichas_correo_sin_precio": len(tras_formulario),
        "campos_que_faltan": sorted(c for c, n in faltan.items() if n * 2 >= len(fichas)),  # en la mitad o más
        "ejemplo": (tras_formulario or fichas)[0]["url"],
        "veto_robots": bool(r.get("veto_robots")),
    }


def ejecutar(censo: Path, rastreos: list[Path], salida: Path) -> dict:
    provs = {json.loads(l)["id"]: json.loads(l) for l in censo.read_text(encoding="utf-8").splitlines() if l.strip()}
    ultimo: dict[str, dict] = {}
    for c in rastreos:
        for f in sorted(c.rglob("oferta_web/*.json")):
            r = json.loads(f.read_text(encoding="utf-8"))
            i = (r.get("centro") or {}).get("id")
            if i in provs:
                ultimo[i] = r
    filas = []
    for i, r in ultimo.items():
        p = provs[i]
        if p["estado"] not in ("oficial", "verificado"):
            continue
        x = prioridad(p, r)
        if x and (x["fichas_correo_sin_precio"] or x["campos_que_faltan"]):
            filas.append(x)
    filas.sort(key=lambda x: (-x["fichas_correo_sin_precio"] / x["fichas_medidas"], -x["urls_programa"]))
    destino = salida / "datos" / "estudios" / "peticiones"
    destino.mkdir(parents=True, exist_ok=True)
    with (destino / "centros_a_pedir.jsonl").open("w", encoding="utf-8") as f:
        for x in filas:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    return {"centros": len(filas), "con_precio_tras_formulario": sum(1 for x in filas if x["fichas_correo_sin_precio"]),
            "campos": dict(Counter(c for x in filas for c in x["campos_que_faltan"]))}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--censo", required=True)
    p.add_argument("--rastreo", action="append", default=[])
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    print(json.dumps(ejecutar(Path(a.censo), [Path(x) for x in a.rastreo], Path(a.salida)), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
