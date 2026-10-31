"""Sonda: el texto de unas páginas de un PDF de boletín ya guardado en el almacén, con varios lectores (pypdf y, si se
pueden instalar, pypdfium2 y pdfminer.six), para elegir el que lee bien un boletín cuyas fuentes pypdf no entiende
(BOP de Albacete, 31/10/2026: sumario y títulos con letras que faltan). Lo impreso pasa por el filtro de datos de
personas de las sondas; el PDF no se guarda.

Uso (prueba.yml con originales=s3): python -m motor.provinciales.sonda_pdf_motores bopalbacete 2022-11-11 --paginas 2,8
"""

from __future__ import annotations

import argparse
import io
import subprocess
import sys
from pathlib import Path

from motor.autonomicos.comun import leer_jsonl
from motor.provinciales import textos as t
from motor.provinciales.diagnostico_cortes import _desde_datos
from motor.provinciales.sonda_pdf_texto import _seguro


def _indice(fuente: str, fecha: str, salida: Path) -> None:
    import urllib.request
    from motor.provinciales.diagnostico_cortes import RAMA
    ruta = f"archivo/indices/{fuente}-boletin/{fecha[:7]}.jsonl"
    with urllib.request.urlopen(urllib.request.Request(RAMA + ruta, headers={"User-Agent": "motor-education-sonda"}),
                                timeout=60) as r:
        contenido = r.read()
    (salida / ruta).parent.mkdir(parents=True, exist_ok=True)
    (salida / ruta).write_bytes(contenido)


def _instalar(paquete: str) -> bool:
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", paquete], capture_output=True, text=True)
    return r.returncode == 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("fuente")
    p.add_argument("fecha")
    p.add_argument("--paginas", default="1,2")
    p.add_argument("--url", help="el PDF por su dirección (con el índice de capturas de fuente-boletin de ese mes)")
    p.add_argument("--salida", type=Path, default=Path("sonda"))
    a = p.parse_args(argv)
    filas = []
    if a.url:
        _indice(a.fuente, a.fecha, a.salida)
        url = a.url
    else:
        _desde_datos(a.fuente, a.fecha, a.salida)
        campo = t.BOLETIN_ENTERO[a.fuente]
        base = a.salida / "datos" / "provinciales" / a.fuente
        filas = [x for f in (base / "oposiciones").rglob("*.jsonl") for x in leer_jsonl(f)]
        if not filas:
            print("sin anuncios de empleo ese día")
            return 0
        url = filas[0][campo].split("#")[0]
    guardado = t.original_guardado(a.salida, a.fuente + "-boletin", a.fecha, url)
    if not guardado:
        print("el PDF no está en el almacén:", url)
        return 0
    pdf = guardado[0]
    numeros = [int(n) for n in a.paginas.split(",") if n.strip()]
    print("pdf", len(pdf), url)
    print("títulos del día:", [_seguro(x.get("titulo") or "")[:90] for x in filas[:4]])

    from motor.pdf import paginas as paginas_pypdf
    plano = paginas_pypdf(pdf)
    for n in numeros:
        print(f"===== pypdf, página {n}")
        print(_seguro(plano[n - 1])[:2500])

    if _instalar("pypdfium2"):
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(pdf)
        for n in numeros:
            print(f"===== pypdfium2, página {n}")
            print(_seguro(doc[n - 1].get_textpage().get_text_range())[:2500])
    else:
        print("pypdfium2 no se pudo instalar")

    if _instalar("pdfminer.six"):
        from pdfminer.high_level import extract_text
        for n in numeros:
            print(f"===== pdfminer.six, página {n}")
            print(_seguro(extract_text(io.BytesIO(pdf), page_numbers=[n - 1]))[:2500])
    else:
        print("pdfminer.six no se pudo instalar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
