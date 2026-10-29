"""Prueba de humo de los conectores del BOC (Canarias) y del BOPV (País Vasco) contra las fuentes reales.

Uso (desde GitHub Actions, porque el espacio de trabajo no llega a los boletines):
  python -m motor.autonomicos.humo2 --salida ruta/

Procesa un boletín de 2026 y otro de 2022 de cada fuente y descarga tres textos de cada una, con muy pocas
peticiones. Escribe humo.json y termina con código 1 si algún conector falla.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import date
from pathlib import Path

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos import boc, bopv
from motor.autonomicos.comun import descargar_textos
from motor.http import obtener


def _textos(modulo, raiz: Path, archivo: Archivo) -> dict:
    pend = modulo.textos_pendientes(raiz)[:3]
    hechos, errores = descargar_textos(pend, lambda x: modulo.ruta_texto(raiz, x), lambda x: x["url_html"],
                                       modulo.texto_disposicion, archivo, modulo.FUENTE, 2, 0.5,
                                       accept="text/html", ext="html")
    muestras = []
    for x in pend:
        r = modulo.ruta_texto(raiz, x)
        if r.exists():
            t = json.loads(r.read_text(encoding="utf-8"))
            muestras.append({"id": x["id"], "titulo": (t.get("titulo") or "")[:120],
                             "caracteres": len(t.get("texto") or ""), "inicio": (t.get("texto") or "")[:200],
                             "tablas": len(t.get("tablas") or []),
                             "omitidos": t.get("parrafos_omitidos_por_datos_personales")})
    return {"hechos": hechos, "errores": errores, "muestras": muestras}


def prueba_boc(raiz: Path, archivo: Archivo) -> dict:
    r = obtener(boc.url_anio(2026), accept="text/html")
    lista = boc.boletines_del_anio(r.contenido.decode("utf-8", errors="replace"))
    r22 = obtener(boc.url_anio(2022), accept="text/html")
    lista22 = boc.boletines_del_anio(r22.contenido.decode("utf-8", errors="replace"))
    ultimo, fecha = lista[-1]
    return {"boletines_2026": len(lista), "boletines_2022": len(lista22), "ultimo": [ultimo, fecha],
            "ultimo_boletin": boc.procesar_boletin(2026, ultimo, fecha, raiz, archivo),
            "boletin_2022_001": boc.procesar_boletin(2022, 1, dict(lista22)[1], raiz, archivo),
            "inexistente": obtener(boc.url_boletin(2026, 999), accept="text/html").status,
            "textos": _textos(boc, raiz, archivo)}


def prueba_bopv(raiz: Path, archivo: Archivo) -> dict:
    return {"boletin_2026_207": bopv.procesar_boletin(2026, 207, raiz, archivo),
            "boletin_2026_208_con_hasta_hoy": bopv.procesar_boletin(2026, 208, raiz, archivo, date.today()),
            "boletin_2022_001": bopv.procesar_boletin(2022, 1, raiz, archivo),
            "inexistente_2026_999": bopv.procesar_boletin(2026, 999, raiz, archivo),
            "textos": _textos(bopv, raiz, archivo)}


def prueba_bucles(raiz: Path) -> dict:
    """Los bucles principales sobre tres días de 2022 (pocas peticiones)."""
    r = raiz / "bucles"
    codigos = {"boc": boc.main(["--desde", "2022-01-03", "--hasta", "2022-01-05", "--salida", str(r), "--pausa", "0.5"]),
               "bopv": bopv.main(["--desde", "2022-01-03", "--hasta", "2022-01-05", "--salida", str(r), "--pausa", "0.5"])}
    informes = {f.relative_to(r).as_posix(): json.loads(f.read_text(encoding="utf-8")).get("resultado")
                for f in sorted(r.rglob("boletines/*/*.json"))}
    return {"codigos": codigos, "informes": informes}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    a = p.parse_args(argv)
    raiz, archivo = a.salida, Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    resultado, fallos = {}, 0
    pruebas = (("boc", lambda: prueba_boc(raiz, archivo)), ("bopv", lambda: prueba_bopv(raiz, archivo)),
               ("bucles", lambda: prueba_bucles(raiz)))
    for nombre, prueba in pruebas:
        try:
            resultado[nombre] = prueba()
            print(nombre, json.dumps(resultado[nombre], ensure_ascii=False)[:1500])
        except Exception:
            fallos += 1
            resultado[nombre] = {"error": traceback.format_exc()}
            print(nombre, "ERROR\n", resultado[nombre]["error"])
    (raiz / "humo.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
