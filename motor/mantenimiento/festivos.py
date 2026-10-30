"""Festivos de cada comunidad autónoma, desde la resolución anual de la Dirección General de Trabajo en el BOE
(«por la que se publica la relación de fiestas laborales para el año AAAA»).

La tabla del BOE (verificada el 30/10/2026 en las de 2022 a 2027) tiene una columna por comunidad, de Andalucía a la
Ciudad de Melilla, y una fila por fiesta («19 San José.») bajo el nombre de su mes; cada comunidad marca con «*»,
«**» o «***» las que celebra (nacionales, nacionales que asume o propias). Los festivos locales no están.

Uso: python -m motor.mantenimiento.festivos ruta/BOE-A-2025-21667.json [...] --salida motor/catalogo/datos/festivos.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from motor.boe.clasificar import normalizar
from motor.extraccion.texto_es import MESES

# Columna del BOE -> código INE de la comunidad (motor/catalogo/territorio.py)
COLUMNAS = [("andalucia", "01"), ("aragon", "02"), ("asturias", "03"), ("balears", "04"), ("canarias", "05"),
            ("cantabria", "06"), ("castilla-la mancha", "08"), ("castilla la mancha", "08"), ("castilla y leon", "07"),
            ("cataluna", "09"), ("extremadura", "11"), ("galicia", "12"), ("madrid", "13"), ("murcia", "14"),
            ("navarra", "15"), ("pais vasco", "16"), ("rioja", "17"), ("valenciana", "10"), ("ceuta", "18"),
            ("melilla", "19")]
RE_ANIO = re.compile(r"fiestas laborales para el a[ñn]o (\d{4})")
RE_FILA = re.compile(r"^(\d{1,2})\s+(.+?)\.?$")


def codigo_columna(nombre: str) -> str | None:
    n = normalizar(re.sub(r"\(\d+\)", "", nombre)).strip()
    return next((c for k, c in COLUMNAS if k in n), None)


def festivos_de_resolucion(d: dict) -> dict:
    """{"anio", "fuente", "url", "capturado", "comunidades": {código: [{"fecha", "fiesta"}]}}."""
    m = RE_ANIO.search(normalizar(d.get("titulo") or ""))
    if not m:
        raise ValueError("el título no es el de la relación de fiestas laborales")
    anio = int(m.group(1))
    tabla = next((t["contenido"] for t in d.get("tablas") or [] if len(t.get("contenido") or []) > 5), None)
    if not tabla:
        raise ValueError("sin la tabla de fiestas")
    i = next(k for k, f in enumerate(tabla) if sum(1 for c in f if codigo_columna(c)) >= 15)
    codigos = [codigo_columna(c) for c in tabla[i]]
    comunidades: dict[str, list[dict]] = {c: [] for c in codigos if c}
    mes = None
    for fila in tabla[i + 1:]:
        if not fila or not fila[0].strip():
            continue
        primera = normalizar(fila[0]).strip(" .")
        if primera in MESES and not any(x.strip() for x in fila[1:]):
            mes = MESES[primera]
            continue
        f = RE_FILA.match(fila[0].strip())
        if not f or mes is None:
            continue
        dia = date(anio, mes, int(f.group(1))).isoformat()
        marcas = fila[1:][-len(codigos):]
        for c, marca in zip(codigos, marcas):
            if c and marca.strip().startswith("*"):
                comunidades[c].append({"fecha": dia, "fiesta": f.group(2).strip()})
    return {"anio": anio, "fuente": d.get("identificador"), "url": d.get("url"), "capturado": d.get("capturado"),
            "comunidades": comunidades}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("textos", nargs="+", type=Path, help="textos del BOE ya guardados (datos/boe/textos/…/{id}.json)")
    p.add_argument("--salida", type=Path, default=Path("motor/catalogo/datos/festivos.json"))
    a = p.parse_args(argv)
    datos = json.loads(a.salida.read_text(encoding="utf-8")) if a.salida.exists() else {
        "descripcion": "Festivos de cada comunidad autónoma (fiestas laborales publicadas cada año en el BOE). "
                       "Fuente: Agencia Estatal Boletín Oficial del Estado.", "anios": {}}
    for ruta in a.textos:
        r = festivos_de_resolucion(json.loads(ruta.read_text(encoding="utf-8")))
        datos["anios"][str(r["anio"])] = r
        print(r["anio"], r["fuente"], {c: len(v) for c, v in r["comunidades"].items()})
    datos["anios"] = dict(sorted(datos["anios"].items()))
    a.salida.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
