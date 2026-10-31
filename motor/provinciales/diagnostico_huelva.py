"""Diagnóstico del lector del BOP de Huelva anterior al 20/06/2023 (bophuelva_antiguos): con el PDF del almacén (sin
pedir nada a la fuente), qué asuntos del sumario no casan con un comienzo del cuerpo y qué líneas hay en su página.
Lo impreso pasa por el filtro de datos de personas de las sondas.

Uso (prueba.yml con originales=s3): python -m motor.provinciales.diagnostico_huelva 2023-06-13 [--lineas 40]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from motor.provinciales import bophuelva_antiguos as h
from motor.provinciales import textos as t
from motor.provinciales.sonda_pdf_motores import _indice
from motor.provinciales.sonda_pdf_texto import _seguro


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("fecha", type=date.fromisoformat)
    p.add_argument("--lineas", type=int, default=40)
    p.add_argument("--salida", type=Path, default=Path("diagnostico"))
    a = p.parse_args(argv)
    d = a.fecha
    _indice("bophuelva", d.isoformat(), a.salida)
    url = f"https://s2.diphuelva.es/portalweb/bop/boletines/{d:%Y%m%d}-1.pdf"
    guardado = t.original_guardado(a.salida, "bophuelva-boletin", d.isoformat(), url)
    if not guardado:
        print("el PDF no está en el almacén:", url)
        return 0
    from motor.pdf import paginas as paginas_pdf
    pags = paginas_pdf(guardado[0])
    asuntos = h.sumario(pags)
    lineas, comienzos = h.cuerpo(pags)
    casados = h.casar(asuntos, comienzos)
    print(f"páginas {len(pags)}, asuntos {len(asuntos)}, comienzos {len(comienzos)}, casados {len(casados)}")
    for c in comienzos:
        print("  comienzo", c["pagina"], "|", _seguro(c["entidad"])[:100])
    vistas = set()
    for i, x in enumerate(asuntos):
        marca = "ok " if i in casados else "NO "
        print(marca, x["pagina"], "|", _seguro(x.get("entidad") or "")[:70], "|", _seguro(x.get("titulo") or "")[:90])
        if i not in casados and x["pagina"] not in vistas:
            vistas.add(x["pagina"])
            de_la_pagina = [l for n, l in lineas if n == x["pagina"]][:a.lineas]
            print(f"    --- estructura de la página {x['pagina']} ({len(de_la_pagina)} líneas):")
            # Solo cabeceras (mayúsculas, tipos de anuncio, secciones); del texto corrido, cuántas líneas hay
            seguidas = 0
            for l in de_la_pagina + [""]:
                cabecera = l and (h.RE_TIPO.match(l) or h.RE_SECCION.match(l) or h._mayusculas(l))
                if cabecera:
                    if seguidas:
                        print(f"       · {seguidas} líneas de texto")
                        seguidas = 0
                    print("      ", _seguro(l)[:140])
                elif l:
                    seguidas += 1
            if seguidas:
                print(f"       · {seguidas} líneas de texto")
    return 0


if __name__ == "__main__":
    sys.exit(main())
