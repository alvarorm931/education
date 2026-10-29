"""Prueba de humo de los conectores autonómicos contra las fuentes reales, con muy pocas peticiones.

Uso (desde GitHub Actions, porque el espacio de trabajo no llega a los boletines):
  python -m motor.autonomicos.humo --salida ruta/

Procesa un día o un mes conocido de cada boletín y descarga tres textos de cada uno. Escribe humo.json con
lo que salió y termina con código 1 si algún conector falla.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import date
from pathlib import Path

from motor.archivo import Archivo
from motor.autonomicos import bocyl, dog, dogc, dogv
from motor.autonomicos.comun import descargar_textos


def _textos(modulo, raiz: Path, archivo: Archivo, url, **kw) -> dict:
    pend = modulo.textos_pendientes(raiz)[:3]
    hechos, errores = descargar_textos(pend, lambda x: modulo.ruta_texto(raiz, x), url, modulo.texto_disposicion,
                                       archivo, modulo.FUENTE, 2, 0.5, **kw)
    muestras = []
    for x in pend:
        r = modulo.ruta_texto(raiz, x)
        if r.exists():
            t = json.loads(r.read_text(encoding="utf-8"))
            muestras.append({"id": x["id"], "caracteres": len(t.get("texto") or ""), "inicio": (t.get("texto") or "")[:160],
                             "tablas": len(t.get("tablas") or []),
                             "omitidos": t.get("parrafos_omitidos_por_datos_personales")})
    return {"pendientes": len(modulo.textos_pendientes(raiz)) + hechos, "hechos": hechos, "errores": errores,
            "muestras": muestras}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    a = p.parse_args(argv)
    raiz, archivo = a.salida, Archivo(a.salida / "archivo")
    hoy = date.today()
    resultado, fallos = {}, 0

    pruebas = {
        "bocyl": lambda: {"mes": bocyl.procesar_mes(2026, 10, raiz, archivo, hoy),
                          "textos": _textos(bocyl, raiz, archivo, lambda x: x["url_xml"])},
        "dogv": lambda: {"calendario": len(dogv.calendario_mes(2026, 10)),
                         "dia": dogv.procesar_dia(date(2026, 10, 27), True, raiz, archivo),
                         "dia_2022": dogv.procesar_dia(date(2022, 1, 3), False, raiz, archivo),
                         "textos": _textos(dogv, raiz, archivo, lambda x: dogv.url_disposicion(x["id"]),
                                           accept="application/json", ext="json")},
        "dog": lambda: {"dia": dog.procesar_dia(date(2026, 10, 29), 207, raiz, archivo),
                        "dia_2022": dog.procesar_dia(date(2022, 1, 3), 1, raiz, archivo),
                        "textos": _textos(dog, raiz, archivo, lambda x: x["url_html"], accept="text/html", ext="html")},
        "dogc": lambda: {"calendario": len(dogc.calendario_mes(2026, 10)),
                         "calendario_2022_01": dogc.calendario_mes(2022, 1).get("2022-01-03"),
                         "dia": dogc.procesar_dia(date(2026, 10, 29), "9783", raiz, archivo),
                         "textos": _textos(dogc, raiz, archivo, lambda x: f"{dogc.API}/documentDOGC",
                                           accept="application/json", ext="json",
                                           formulario=lambda x: {"documentId": x["id"], "language": "es"})},
    }
    for nombre, prueba in pruebas.items():
        try:
            resultado[nombre] = prueba()
            print(nombre, json.dumps(resultado[nombre], ensure_ascii=False)[:600])
        except Exception:
            fallos += 1
            resultado[nombre] = {"error": traceback.format_exc()}
            print(nombre, "ERROR\n", resultado[nombre]["error"])
    (raiz / "humo.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
