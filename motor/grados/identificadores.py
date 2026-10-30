"""Direcciones estables de las páginas de grados: una tabla que solo crece.

Cada cosa con página (universidad, genérico, título, asignatura) recibe una dirección la primera vez que aparece y
la conserva siempre, aunque cambie su nombre o la forma de normalizarlo (ley SEO, regla 11: una dirección que
cambia exige redirección; mejor que no cambie). Una dirección usada no se da nunca a otra cosa, aunque la primera
desaparezca.

Formas (docs/guia.html, §05; ley SEO, regla 12: minúsculas, guiones, sin tildes ni códigos, barra final):
  /universidad/{universidad}/
  /universidad/{universidad}/grado/{grado}/          ficha de un título (grado o doble)
  /grado/{grado}/                                    el mismo grado en todas las universidades
  /carreras-con/{asignatura}/                        dónde se estudia una asignatura (la clave es la dirección:
                                                     dos nombres que dan la misma dirección son la misma página)

Si dos títulos de la misma universidad se llaman igual (sedes distintas, un plan que se extingue y su sucesor,
la versión en línea), la dirección del segundo lleva lo que los distingue: la ciudad, «online», «en-ingles» o el
año del plan; nunca un código.

Uso: python -m motor.grados.identificadores --fichas … --genericos … --asignaturas … --catalogo …
     [--tabla identificadores.json] --salida …
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from motor.grados.catalogo import clave

RE_VALIDA = re.compile(r"^/(?:[a-z0-9]+(?:-[a-z0-9]+)*/)+$")


def slug(texto: str) -> str:
    """«Administración y Dirección de Empresas» → «administracion-y-direccion-de-empresas» (con sus «y» y «de»)."""
    t = clave(texto or "")  # minúsculas, sin tildes ni signos
    return "-".join(re.findall(r"[a-z0-9]+", t))


def asignatura_con_pagina(nombre: str) -> bool:
    """Un nombre de asignatura de verdad: con palabras, no muy largo y que no sea una regla de elección."""
    return bool(re.search(r"[a-záéíóúüñ]{3}", nombre or "", re.I)) and len(nombre) <= 90 and not re.match(
        r"^(\d|elecci[oó]n|elegir|optativ|cr[eé]ditos|asignaturas?\b)", nombre, re.I) \
        and not re.search(r"\boptativ", nombre, re.I)


def nombre_url(nombre: str) -> str:
    """El nombre en castellano, sin la versión en inglés de los bilingües ni notas entre paréntesis."""
    # « / Bachelor in …» o «/ Bachelor»: sí; «Maestro/a» o «Graduado/a»: no
    n = re.split(r"\s+/\s*|/\s+(?=[A-Z])", nombre or "")[0]
    return re.sub(r"\s*\([^)]*\)", "", n).strip() or (nombre or "")


def _nombre_universidad(nombre: str) -> str:
    return re.sub(r"^(universidad|universitat|universidade|unibertsitatea)\s+(de\s+|del\s+|d')?", "", nombre or "",
                  flags=re.I)


def _distintivos(t: dict) -> list[str]:
    """Lo que puede distinguir a un título de otro del mismo nombre en la misma universidad, de más a menos
    natural para quien busca: la ciudad, la modalidad, el idioma y el régimen del plan."""
    imp = [i for i in t.get("imparticiones") or [] if i.get("situacion") == "Activo"] or t.get("imparticiones") or []
    ciudades = sorted({(i.get("municipio") or "").title() for i in imp if i.get("municipio")})
    modal = sorted({i.get("presencialidad") or "" for i in imp})
    online = any("no presencial" in m.lower() for m in modal) and not any(m.lower().startswith("estudio presencial")
                                                                            for m in modal)
    ingles = any((i.get("idioma_extranjero") or "").startswith("Sí") for i in imp)
    anio = re.search(r"/(\d{4})", t.get("regimen") or "")  # «RD 1393/2007» → plan-2007
    return [slug(" ".join(ciudades)) if ciudades else "", "online" if online else "presencial",
            "en-ingles" if ingles else "", f"plan-{anio.group(1)}" if anio else ""]


def _anio_verificacion(f: dict) -> str:
    """Año de verificación del título en el RUCT («plan-2019»): distingue un plan nuevo del anterior con el mismo
    nombre, ciudad y modalidad."""
    m = re.search(r"(\d{4})", ((f.get("ruct") or {}).get("fecha_verificacion") or ""))
    return f"plan-{m.group(1)}" if m else ""


class Tabla:
    def __init__(self, datos: dict | None = None):
        d = datos or {}
        self.rutas: dict[str, str] = dict(d.get("rutas") or {})
        self.usadas: set[str] = set(d.get("usadas") or []) | set(self.rutas.values())

    def dar(self, clave_: str, candidatas: list[str]) -> str:
        if clave_ in self.rutas:
            return self.rutas[clave_]
        for ruta in candidatas:
            if ruta and RE_VALIDA.match(ruta) and ruta not in self.usadas:
                break
        else:  # todas usadas: la primera con un ordinal libre
            base = candidatas[0].rstrip("/")
            n = 2
            while f"{base}-{n}/" in self.usadas:
                n += 1
            ruta = f"{base}-{n}/"
        self.rutas[clave_] = ruta
        self.usadas.add(ruta)
        return ruta

    def a_json(self) -> dict:
        return {"rutas": dict(sorted(self.rutas.items())), "usadas": sorted(self.usadas)}


def asignar(tabla: Tabla, fichas: list[dict], genericos: list[dict], asignaturas: list[dict],
            catalogo: list[dict]) -> dict[str, int]:
    cat = {t["codigo"]: t for t in catalogo}
    nuevas = defaultdict(int)

    def dar(k, cands):
        antes = k in tabla.rutas
        r = tabla.dar(k, cands)
        nuevas[k.split(":")[0]] += 0 if antes else 1
        return r

    # universidades
    unis = {}
    for f in fichas:
        for u in f["universidades"]:
            if u.get("codigo"):
                unis[u["codigo"]] = u["nombre"]
    ruta_uni = {c: dar(f"universidad:{c}", [f"/universidad/{slug(_nombre_universidad(n))}/"]) for c, n in sorted(unis.items())}
    # genéricos con página
    for g in sorted(genericos, key=lambda g: g["id"]):
        if g.get("pagina_propia"):
            dar(f"generico:{g['id']}", [f"/grado/{slug(nombre_url(g['nombre']))}/"])
    # títulos: primero los que no comparten nombre en su universidad, para que el nombre limpio sea del más claro
    por_nombre = defaultdict(list)
    for f in fichas:
        c = (f["universidades"][0].get("codigo") or "")
        por_nombre[(c, slug(nombre_url(f["nombre"])))].append(f)
    for (cu, s), fs in sorted(por_nombre.items()):
        base = ruta_uni.get(cu, f"/universidad/{slug(_nombre_universidad(fs[0]['universidades'][0]['nombre']))}/")
        fs = sorted(fs, key=lambda f: f["codigo"])
        if len(fs) == 1:
            dar(f"titulo:{fs[0]['codigo']}", [f"{base}grado/{s}/"])
            continue
        # el que tenga más centros activos se queda el nombre limpio; los demás, con lo que los distingue
        # un grado nuevo (alta del BOE aún fuera del catálogo) se distingue por el año de su plan
        dist = {f["codigo"]: (["", "", "", f"plan-{(f.get('alta') or {}).get('boe', '')[6:10]}"]
                              if f.get("estado") == "nuevo" else _distintivos(cat.get(f["codigo"], {})))
                + [_anio_verificacion(f)] for f in fs}
        fs.sort(key=lambda f: (-len(f.get("centros") or []), f["codigo"]))
        for i, f in enumerate(fs):
            cands = [f"{base}grado/{s}/"] if i == 0 else []
            for j in range(5):
                valores = [dist[x["codigo"]][j] for x in fs]
                if valores[i] and valores.count(valores[i]) == 1:
                    cands.append(f"{base}grado/{s}-{valores[i]}/")
            cands.append(f"{base}grado/{s}/")
            dar(f"titulo:{f['codigo']}", cands)
    # asignaturas con página (en dos títulos o más, sin los huecos genéricos)
    for a in sorted(asignaturas, key=lambda a: a["clave"]):
        n = nombre_url(a["nombre"])
        if a.get("titulos", 0) >= 2 and not a.get("generica") and asignatura_con_pagina(n):
            s_ = slug(n)
            dar(f"asignatura:{s_}", [f"/carreras-con/{s_}/"])
    return dict(nuevas)


def _leer(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--fichas", required=True, nargs="+")
    p.add_argument("--genericos", required=True)
    p.add_argument("--asignaturas", required=True)
    p.add_argument("--catalogo", required=True)
    p.add_argument("--tabla", help="tabla anterior (identificadores.json): se conserva todo lo que ya tenía")
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    tabla = Tabla(json.loads(Path(a.tabla).read_text(encoding="utf-8")) if a.tabla and Path(a.tabla).exists() else None)
    fichas = [x for f in a.fichas for x in _leer(Path(f))]
    nuevas = asignar(tabla, fichas, _leer(Path(a.genericos)), _leer(Path(a.asignaturas)), _leer(Path(a.catalogo)))
    destino = Path(a.salida) / "datos" / "estudios" / "grados"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "identificadores.json").write_text(json.dumps(tabla.a_json(), ensure_ascii=False, indent=0),
                                                  encoding="utf-8")
    print(json.dumps({"rutas": len(tabla.rutas), "nuevas": nuevas}, ensure_ascii=False))


if __name__ == "__main__":
    main()
