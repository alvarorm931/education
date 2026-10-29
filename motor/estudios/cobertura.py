"""Cobertura del censo de proveedores frente a listas de referencia independientes.

Para cada lista de `fuentes/referencia_proveedores.json` cuenta cuántos dominios están:
  - en Common Crawl (descubiertos por el patrón de URL),
  - en el censo (por cualquier fuente: RUCT o Common Crawl, aunque sea con otro dominio unido),
  - verificados por el rastreador en su propia web.
Así se ve qué capa pierde cada proveedor y se corrige esa capa, no la lista.

Uso:
  python -m motor.estudios.cobertura --censo proveedores.jsonl [--commoncrawl carpeta] [--rastreo carpeta ...]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REFERENCIA = Path(__file__).resolve().parents[2] / "fuentes" / "referencia_proveedores.json"


def medir(listas: dict, cc: set[str], censo: dict[str, dict], verificados: set[str]) -> dict:
    salida = {}
    for nombre, lista in listas.items():
        doms = list(dict.fromkeys(lista["dominios"]))
        en_censo = [d for d in doms if d in censo]
        salida[nombre] = {
            "total": len(doms),
            "en_commoncrawl": sum(1 for d in doms if d in cc),
            "en_censo": len(en_censo),
            "verificados": sum(1 for d in doms if d in censo and censo[d]["id"] in verificados),
            "faltan_en_censo": [d for d in doms if d not in censo],
            "sin_verificar": [d for d in en_censo if censo[d]["id"] not in verificados],
        }
    return salida


def ejecutar(censo: Path, cc_dir: Path | None, rastreos: list[Path], referencia: Path = REFERENCIA) -> dict:
    listas = json.loads(referencia.read_text(encoding="utf-8"))["listas"]
    provs = [json.loads(l) for l in censo.read_text(encoding="utf-8").splitlines() if l.strip()]
    por_dom = {d: p for p in provs for d in p["dominios"]}
    cc = set()
    if cc_dir:
        for f in cc_dir.glob("dominios_*.jsonl"):
            cc |= {json.loads(l).get("dominio") for l in f.read_text(encoding="utf-8").splitlines() if l.strip()}
    verificados = set()
    for c in rastreos:
        for f in c.rglob("oferta_web/*.json"):
            r = json.loads(f.read_text(encoding="utf-8"))
            if r.get("verificado"):
                verificados.add((r.get("centro") or {}).get("id"))
    return medir(listas, cc, por_dom, verificados)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--censo", required=True)
    p.add_argument("--commoncrawl")
    p.add_argument("--rastreo", action="append", default=[])
    a = p.parse_args()
    print(json.dumps(ejecutar(Path(a.censo), Path(a.commoncrawl) if a.commoncrawl else None,
                              [Path(x) for x in a.rastreo]), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
