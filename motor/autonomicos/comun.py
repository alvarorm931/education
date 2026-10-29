"""Piezas comunes de los conectores de boletines autonómicos.

Cada conector conoce el formato de su boletín; lo que es igual para todos vive aquí:
  - clasificación del anuncio (tipo de acto, modalidad, alcance) con las mismas reglas que el BOE;
  - selección de anuncios locales de empleo público por el título;
  - convocante a partir del organismo («AYUNTAMIENTO DE MIRANDA DE EBRO (BURGOS)»);
  - escritura reproducible de ficheros JSON Lines;
  - descarga de textos pendientes con límite de tiempo, pausa entre peticiones y guardado del original.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Iterable
from datetime import date
from pathlib import Path

from motor.archivo import Archivo
from motor.boe.clasificar import REGLAS_ACTO, REGLAS_MODALIDAD, _primera, alcance, normalizar
from motor.http import obtener

RE_EMPLEO_LOCAL = re.compile(
    r"\b(plazas?|convocatoria|bases|seleccion|bolsa|oposicion|concurso|proceso selectivo|personal|funcionari\w*|"
    r"laboral fij\w*|empleo publico|oferta\w* (?:\w+ ){0,3}de empleo|tribunal|aspirantes)\b")
RE_NO_EMPLEO = re.compile(
    r"\b(subvencion\w*|licencia\w*|urbanis\w*|ordenanza\w*|presupuesto\w*|expropiacion\w*|contratacion de (?:obras|servicios|suministro)\w*|"
    r"licitacion\w*|ayudas?|premios?|becas?|cuenta general|padron|tasas?|impuestos?|proyectos? de obras?|"
    r"ejecucion de (?:las )?obras|remodelacion|relacion de puestos de trabajo)\b")
RE_RESULTADO = re.compile(
    r"\b(funcionari[oa]s? de carrera|personal laboral fijo|proceso selectivo|pruebas selectivas|aspirantes)\b")

PARTICULAS = {"de", "del", "la", "las", "los", "el", "y", "e", "en", "a", "o"}

TIPOS_ENTIDAD = (
    ("ayuntamiento de ", "Ayuntamiento"),
    ("diputacion provincial de ", "Diputación Provincial"),
    ("diputacion de ", "Diputación Provincial"),
    ("mancomunidad ", "Mancomunidad"),
    ("comunidad de villa y tierra ", "Comunidad de Villa y Tierra"),
    ("consorcio ", "Consorcio"),
    ("junta vecinal ", "Junta Vecinal"),
    ("entidad local menor ", "Entidad Local Menor"),
    ("consejo comarcal ", "Consejo Comarcal"),
    ("comarca ", "Comarca"),
    ("cabildo insular de ", "Cabildo Insular"),
    ("consell insular de ", "Consell Insular"),
    ("patronato ", "Patronato"),
)


def clasificar(titulo: str, apartado: str | None = None) -> dict:
    """Tipo de acto, modalidad y alcance con las mismas reglas que se aplican al BOE."""
    t = normalizar(titulo or "")
    modalidad = _primera(REGLAS_MODALIDAD, t)
    return {"tipo_acto": _primera(REGLAS_ACTO, t) or "otro", "modalidad": modalidad,
            "alcance": alcance(t, modalidad, apartado)}


def es_empleo_por_titulo(titulo: str) -> bool:
    t = normalizar(titulo or "")
    return bool(RE_EMPLEO_LOCAL.search(t)) and not RE_NO_EMPLEO.search(t)


def es_resultado(titulo: str) -> bool:
    return bool(RE_RESULTADO.search(normalizar(titulo or "")))


def nombre_propio(texto: str) -> str:
    """«MIRANDA DE EBRO» -> «Miranda de Ebro». Respeta tildes y partículas. Si ya viene en minúsculas y
    mayúsculas («L'Arboç», «Betxí»), se deja como está."""
    if not texto.isupper():
        return texto
    palabras = []
    for i, w in enumerate(texto.lower().split()):
        if i and w in PARTICULAS:
            palabras.append(w)
        else:
            palabras.append("-".join(p[:1].upper() + p[1:] for p in w.split("-")))
    return " ".join(palabras)


RE_PARENTESIS = re.compile(r"^(?P<nombre>.+?)\s*\((?P<provincia>[^()]+)\)\s*$")


def convocante_de_organismo(organismo: str, capitales: Iterable[str] = ()) -> dict | None:
    """«AYUNTAMIENTO DE MIRANDA DE EBRO (BURGOS)» -> tipo, nombre y provincia.

    capitales: nombres de municipio que son capital de provincia (el boletín no repite la provincia).
    """
    o = " ".join((organismo or "").split())
    if not o:
        return None
    m = RE_PARENTESIS.match(o)
    base, provincia = (m.group("nombre"), m.group("provincia")) if m else (o, None)
    n = normalizar(base)
    for prefijo, tipo in TIPOS_ENTIDAD:
        if n.startswith(prefijo):
            nombre = nombre_propio(base[len(prefijo):].strip())
            if provincia:
                prov = nombre_propio(provincia)
            elif tipo == "Diputación Provincial" or normalizar(nombre) in {normalizar(c) for c in capitales}:
                prov = nombre
            else:
                prov = None
            return {"tipo": tipo, "nombre": nombre, "provincia": prov, "organismo": o}
    return {"tipo": None, "nombre": nombre_propio(base), "provincia": nombre_propio(provincia) if provincia else None,
            "organismo": o}


def escribir_jsonl(ruta: Path, filas: list[dict]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in filas), encoding="utf-8")


def leer_jsonl(ruta: Path) -> list[dict]:
    if not ruta.exists():
        return []
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]


def escribir_json(ruta: Path, datos: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


def descargar_textos(pendientes: list[dict], destino: Callable[[dict], Path], url: Callable[[dict], str],
                     extraer: Callable[[bytes], dict], archivo: Archivo, fuente: str, max_minutos: float,
                     pausa: float, accept: str = "application/xml", ext: str = "xml",
                     formulario: Callable[[dict], dict] | None = None) -> tuple[int, int]:
    """Descarga y limpia los textos de la lista. Devuelve (hechos, errores). Reanudable: lo hecho queda escrito.

    formulario: para las API que piden el documento por POST, los campos de cada petición.
    """
    inicio, hechos, errores = time.monotonic(), 0, 0
    for x in pendientes:
        if max_minutos and (time.monotonic() - inicio) / 60 > max_minutos:
            break
        u = url(x)
        try:
            r = obtener(u, accept=accept) if formulario is None else obtener(u, accept=accept, formulario=formulario(x))
        except ConnectionError:
            errores += 1
            continue
        if r.status != 200:
            errores += 1
            time.sleep(pausa)
            continue
        try:
            datos = extraer(r.contenido)
        except Exception:  # un documento mal formado no detiene la carga; queda pendiente para revisarlo
            errores += 1
            continue
        captura = archivo.guardar(fuente + "-texto", date.fromisoformat(x["fecha"]), r.contenido, u, ext, r.status,
                                  r.cabeceras)
        escribir_json(destino(x), {"id": x["id"], **datos, "captura_sha256": captura["sha256"],
                                   "capturado": captura["capturado"], "url": u})
        hechos += 1
        time.sleep(pausa)
    return hechos, errores
