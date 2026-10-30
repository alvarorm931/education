"""Diagnóstico de un sumario del BOE: compara lo que lee motor.boe.sumario.parsear con lo que trae el XML.

Sirve para comprobar si el lector se deja disposiciones (p. ej. planes de estudios de 2010 que no aparecen en el
histórico). Solo pide el sumario de los días indicados (una petición por día) y escribe un resumen con los
títulos de universidades: datos públicos del BOE, sin datos personales.

Uso: python -m motor.grados.diagnostico_sumario --dias 2010-03-23 [2010-03-24 ...] --salida out
"""

from __future__ import annotations

import argparse
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from motor.boe.sumario import ACCEPT, parsear, url_sumario
from motor.grados.boe_grados import tipo_acto
from motor.http import obtener


def diagnosticar(d: date) -> dict:
    r = obtener(url_sumario(d), accept=ACCEPT)
    res: dict = {"dia": d.isoformat(), "status": r.status, "bytes": len(r.contenido or b"")}
    if r.status != 200:
        return res
    xml = r.contenido
    res["items_en_xml"] = len(re.findall(rb"<item[\s>]", xml))
    try:
        s = parsear(xml)
        res["items_leidos"] = len(s.items)
        res["planes_leidos"] = [it.get("identificador") for it in s.items if tipo_acto(it.get("titulo") or "")]
    except Exception as e:  # noqa: BLE001 - diagnóstico
        res["error_parsear"] = f"{type(e).__name__}: {str(e)[:200]}"
    raiz = ET.fromstring(xml)
    rutas: dict[str, int] = {}
    universidades = []

    def recorrer(nodo, ruta):
        for h in nodo:
            r2 = f"{ruta}/{h.tag}"
            if h.tag == "item":
                rutas[ruta] = rutas.get(ruta, 0) + 1
                titulo = (h.findtext("titulo") or "").strip()
                if "Universidad" in titulo or "Universitat" in titulo:
                    universidades.append({"identificador": h.findtext("identificador"), "ruta": ruta,
                                          "titulo": titulo[:200], "tipo_acto": tipo_acto(titulo)})
            else:
                recorrer(h, r2)

    recorrer(raiz, raiz.tag)
    res["rutas_de_items"] = rutas
    res["universidades"] = universidades[:60]
    return res


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dias", nargs="+", required=True, type=date.fromisoformat)
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    salida = []
    for d in a.dias:
        salida.append(diagnosticar(d))
        time.sleep(1.5)
    destino = Path(a.salida) / "datos" / "estudios" / "grados" / "diagnostico"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "sumarios.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps([{k: v for k, v in x.items() if k != "universidades"} for x in salida], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
