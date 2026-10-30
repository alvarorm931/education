"""Aplica las reglas de privacidad a lo que ya está guardado en la rama de datos.

  1. Textos (datos/**/textos/*.json): los párrafos con un nombre de persona o un documento de identidad se
     retiran y se cuentan; las tablas con nombres pasan a guardar solo filas y cabecera.
  2. Títulos (cualquier campo «titulo» en datos/): el nombre de la persona se sustituye por «[persona]».
  3. Originales de boletines (archivo/{fuente}/AAAA/MM/DD/*): se retira el contenido; la huella, la URL y la
     fecha de captura siguen en archivo/indices/. Queda constancia en archivo/retirados.json.

Uso: python -m motor.mantenimiento.privacidad --salida ruta/ [--sin-retirar-originales]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from motor.limpieza import RE_DOCUMENTO, parrafos_seguros, tiene_nombre_de_persona, titulo_sin_nombres

# Carpetas de originales de los conectores de boletines (los de másters no se tocan)
FUENTES_BOLETINES = ("boe", "boja", "bocm", "bocyl", "dogv", "dog", "dogc", "boa", "doe", "boib", "borm", "boc",
                     "bopv", "docm", "bome", "bopb", "bopalicante", "bopvalencia", "bopt", "bopciudadreal", "bopgranada", "bopsevilla", "bophuesca", "boptenerife", "bopcordoba", "bopcoruna", "boppontevedra")


def _tabla_segura(t: dict) -> dict:
    if t.get("datos_personales") or not t.get("contenido"):
        return t
    celdas = " ".join(" ".join(f) for f in t["contenido"])
    if tiene_nombre_de_persona(celdas) or len(RE_DOCUMENTO.findall(celdas)) >= 1:
        return {"filas": max(len(t["contenido"]) - 1, 0), "cabecera": t["contenido"][0] if t["contenido"] else [],
                "datos_personales": True}
    return t


def limpiar_texto_guardado(d: dict) -> tuple[dict, bool]:
    cambio = False
    if d.get("titulo"):
        t = titulo_sin_nombres(d["titulo"])
        cambio |= t != d["titulo"]
        d["titulo"] = t
    if d.get("texto"):
        guardados, omitidos = parrafos_seguros(d["texto"].split("\n"))
        if omitidos:
            d["texto"] = "\n".join(guardados)
            d["parrafos_omitidos_por_datos_personales"] = d.get("parrafos_omitidos_por_datos_personales", 0) + omitidos
            cambio = True
    if d.get("tablas"):
        nuevas = [_tabla_segura(t) for t in d["tablas"]]
        cambio |= nuevas != d["tablas"]
        d["tablas"] = nuevas
    return d, cambio


def _titulos(obj):
    """Sustituye nombres en cualquier «titulo» anidado. Devuelve (objeto, cambió)."""
    if isinstance(obj, dict):
        cambio = False
        for k, v in obj.items():
            if k == "titulo" and isinstance(v, str):
                n = titulo_sin_nombres(v)
                if n != v:
                    obj[k], cambio = n, True
            elif isinstance(v, (dict, list)):
                _, c = _titulos(v)
                cambio |= c
        return obj, cambio
    if isinstance(obj, list):
        cambio = False
        for x in obj:
            _, c = _titulos(x)
            cambio |= c
        return obj, cambio
    return obj, False


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--sin-retirar-originales", action="store_true")
    a = p.parse_args(argv)
    datos, archivo = a.salida / "datos", a.salida / "archivo"
    cuenta = Counter()

    for f in datos.rglob("textos/**/*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        d, cambio = limpiar_texto_guardado(d)
        if cambio:
            f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            cuenta["textos_limpiados"] += 1
        cuenta["textos_revisados"] += 1

    for f in datos.rglob("*.jsonl"):
        lineas, cambio = [], False
        for l in f.read_text(encoding="utf-8").splitlines():
            if not l.strip():
                continue
            x, c = _titulos(json.loads(l))
            cambio |= c
            lineas.append(json.dumps(x, ensure_ascii=False))
        if cambio:
            f.write_text("".join(x + "\n" for x in lineas), encoding="utf-8")
            cuenta["ficheros_con_titulos_corregidos"] += 1

    retirados = Counter()
    if not a.sin_retirar_originales and archivo.exists():
        for carpeta in sorted(archivo.iterdir()):
            if not carpeta.is_dir() or carpeta.name == "indices":
                continue
            if carpeta.name.split("-")[0] not in FUENTES_BOLETINES:
                continue
            for f in carpeta.rglob("*"):
                if f.is_file():
                    f.unlink()
                    retirados[carpeta.name] += 1
        if retirados:
            registro = archivo / "retirados.json"
            previo = json.loads(registro.read_text(encoding="utf-8")) if registro.exists() else []
            previo.append({
                "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "motivo": "Repositorio público: los originales de boletines pueden traer datos de personas "
                          "(listas de admitidos, nombramientos). Se conservan huella, URL y fecha en archivo/indices/.",
                "por_fuente": dict(retirados),
            })
            registro.write_text(json.dumps(previo, ensure_ascii=False, indent=1), encoding="utf-8")
    cuenta["originales_retirados"] = sum(retirados.values())
    print(json.dumps(dict(cuenta), ensure_ascii=False))
    print(json.dumps(dict(retirados), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
