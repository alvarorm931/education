"""Diagnóstico del corte de textos del PDF del boletín entero (motor/provinciales/textos.py), para prueba.yml.

Lee el boletín de un día con su conector en una carpeta vacía, corta los textos de sus anuncios de empleo y dice, por
anuncio, si se encontró su título en el cuerpo y cuánto texto salió. Para los que no salen, imprime cuántas palabras
del título se encuentran y el trozo del cuerpo donde más se parece. Lo impreso pasa por el filtro de datos de personas
de las sondas y la rama sondas se anonimiza al subir; el PDF no se guarda.

Uso (con prueba.yml): python -m motor.provinciales.diagnostico_cortes boptenerife 2026-10-30 [--paginas 4]
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from datetime import date
from pathlib import Path

from motor.archivo import Archivo
from motor.autonomicos.comun import leer_jsonl
from motor.provinciales import textos as t
from motor.provinciales.sonda_pdf_texto import _seguro


def _mejor_prefijo(compacto: "t._Compacto", palabras: list[str]) -> tuple[int, int]:
    """Cuántas de las primeras palabras del título se encuentran seguidas en el cuerpo, y dónde."""
    mejor, pos = 0, -1
    for n in range(1, min(len(palabras), 30) + 1):
        i = compacto.buscar(" ".join(palabras[:n]), 0)
        if i < 0:
            break
        mejor, pos = n, i
    return mejor, pos


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("fuente", choices=sorted(t.BOLETIN_ENTERO))
    p.add_argument("fecha", type=date.fromisoformat)
    p.add_argument("--paginas", type=int, default=4, help="páginas del cuerpo que se imprimen (las primeras)")
    p.add_argument("--crudas", default="", help="páginas (1,5,9) cuyo texto con disposición se imprime tal cual")
    p.add_argument("--salida", type=Path, default=Path("diagnostico"))
    a = p.parse_args(argv)
    conector = importlib.import_module(f"motor.provinciales.{a.fuente}")
    d = a.fecha.isoformat()
    conector.main(["--desde", d, "--hasta", d, "--salida", str(a.salida)])
    base = a.salida / "datos" / "provinciales" / a.fuente
    campo = t.BOLETIN_ENTERO[a.fuente]
    empleo = [x for f in (base / "oposiciones").rglob("*.jsonl") for x in leer_jsonl(f)]
    todas = [x for f in (base / "disposiciones").rglob("*.jsonl") for x in leer_jsonl(f)]
    print(f"disposiciones {len(todas)}, de empleo {len(empleo)}")
    if not empleo:
        return 0
    url = empleo[0][campo].split("#")[0]
    r = t.obtener(url, accept="application/pdf, */*")
    print("pdf", r.status, len(r.contenido), url)
    if r.contenido[:4] != b"%PDF":
        return 0
    por_registro = a.fuente in t.POR_REGISTRO
    paginas = t.paginas_pdf_columnas(r.contenido) if por_registro else t.paginas_pdf(r.contenido)
    todas = sorted([x for x in todas if (x.get(campo) or "").split("#")[0] == url],
                   key=lambda x: (x.get("pagina") or 0, x.get("orden") or 0))
    if por_registro:
        cortes = t.cortar_por_registro(paginas, todas)
        marcas = sum(1 for pg in paginas for l in pg.splitlines() if t.RE_MARCA_REGISTRO.match(l))
        print(f"sumario: {len(t.entradas_sumario(paginas))} entradas; cuerpo: {marcas} líneas de registro")
    else:
        cortes = t.cortar(paginas, todas)
    limpias = [t.sin_entradas_de_sumario(pg) for pg in paginas]
    sumario = [n + 1 for n, pg in enumerate(limpias) if t.es_pagina_de_sumario(pg)]
    print(f"páginas {len(paginas)}; tomadas por sumario: {sumario[:40]}")
    plano = " ".join(t._plano(pg) for pg in limpias)
    compacto = t._Compacto(plano)
    for x in todas:
        es_empleo = any(e["id"] == x["id"] for e in empleo)
        corte = cortes.get(x["id"])
        palabras = t._plano(x.get("titulo") or "").split()
        n, pos = _mejor_prefijo(compacto, palabras)
        estado = f"texto {len(corte[0])} car., págs. {corte[1]}" if corte else "SIN TEXTO"
        print(f"{'*' if es_empleo else ' '} {x['id']} | {estado} | {n}/{len(palabras)} palabras del título seguidas"
              f" | título: {_seguro((x.get('titulo') or '')[:160])}")
        if es_empleo and not corte and pos >= 0:
            print("    cuerpo donde más se parece:", _seguro(plano[max(pos - 60, 0):pos + 240]))
        if es_empleo and corte:
            print("    comienzo del texto:", _seguro(" ".join(corte[0].split())[:240]))
            print("    final del texto:", _seguro(" ".join(corte[0].split())[-160:]))
    cuerpo = [n for n in range(len(paginas)) if n + 1 not in sumario]
    for n in cuerpo[:a.paginas] if not a.crudas else []:
        print(f"----- página {n + 1} (sin entradas de sumario)")
        print(_seguro(limpias[n])[:3000])
    if a.crudas:
        from pypdf import PdfReader
        import io
        lector = PdfReader(io.BytesIO(r.contenido))
        for n in [int(x) for x in a.crudas.split(",") if x.strip()]:
            print(f"----- página {n} con disposición, tal cual")
            print(_seguro(lector.pages[n - 1].extract_text(extraction_mode="layout") or "")[:6000])
    print(json.dumps({"empleo": len(empleo), "con_texto": sum(1 for e in empleo if e["id"] in cortes)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
