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
from motor.limpieza import titulo_sin_nombres

# Castellano, catalán/valenciano y gallego (texto normalizado: sin tildes y en minúscula). «Plaça» sola no cuenta:
# también es la plaza de un pueblo («plaça de l'Ajuntament»).
RE_EMPLEO_LOCAL = re.compile(
    r"\b(plazas?|convocatoria|bases|seleccion|bolsa|oposicion|concurso|proceso selectivo|personal|funcionari\w*|"
    r"laboral fij\w*|empleo publico|oferta\w* (?:\w+ ){0,3}de empleo|tribunal|aspirantes|"
    r"places|seleccio|borsa|oposicio|concurs|proces selectiu|proces de seleccio|ocupacio publica|"
    r"oferta\w* (?:\w+ ){0,3}d'ocupacio|aspirants|prazas?|persoal|emprego publico|oferta\w* (?:\w+ ){0,3}de emprego)\b")
RE_NO_EMPLEO = re.compile(
    r"\b(subvencion\w*|licencia\w*|urbanis\w*|ordenanza\w*|presupuesto\w*|expropiacion\w*|contratacion de (?:obras|servicios|suministro)\w*|"
    r"licitacion\w*|ayudas?|premios?|becas?|cuenta general|padron|tasas?|impuestos?|proyectos? de obras?|"
    r"ejecucion de (?:las )?obras|remodelacion|relacion de puestos de trabajo|viviendas?|alquiler\w*|juez\w* de paz|"
    r"subvencio\w*|llicencia\w*|ordenanca\w*|pressupost\w*|expropiacio\w*|"
    r"contractacio de (?:les )?(?:obres|serveis|subministra)\w*|licitacio\w*|ajuts?|premis?|beques?|compte general|"
    r"padro|taxes|impostos?|projectes? d'obres?|execucio de (?:les )?obres|relacio de llocs de treball|"
    r"habitatges?|lloguer\w*|jutge\w* de pau|jutge/essa de pau|"
    r"licenza\w*|orzamento\w*|axudas?|bolsas? de estudos?|vivendas?|xuiz\w* de paz)\b")
RE_RESULTADO = re.compile(
    r"\b(funcionari[oa]s? de carrera|personal laboral fijo|proceso selectivo|pruebas selectivas|aspirantes|"
    r"funcionari\w*(?:/\w+)? de carrera|personal laboral fix|proces selectiu|proves selectives|aspirants|"
    r"funcionari[oa]s? de carreira|persoal laboral fixo|probas selectivas)\b")

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
    # Catalán y valenciano
    ("ajuntament del ", "Ayuntamiento", "el "),
    ("ajuntament dels ", "Ayuntamiento", "els "),
    ("ajuntament de ", "Ayuntamiento"),
    ("ajuntament d'", "Ayuntamiento"),
    ("diputacio de ", "Diputación Provincial"),
    ("diputacio provincial de ", "Diputación Provincial"),
    ("consell comarcal del ", "Consejo Comarcal"),
    ("consell comarcal de ", "Consejo Comarcal"),
    ("consell comarcal d'", "Consejo Comarcal"),
    ("mancomunitat ", "Mancomunidad"),
    ("consorci ", "Consorcio"),
    ("entitat municipal descentralitzada de ", "Entidad Local Menor"),
    ("entitat municipal descentralitzada d'", "Entidad Local Menor"),
    ("area metropolitana de ", "Área Metropolitana"),
    # Gallego
    ("concello da ", "Ayuntamiento", "A "),
    ("concello do ", "Ayuntamiento", "O "),
    ("concello das ", "Ayuntamiento", "As "),
    ("concello dos ", "Ayuntamiento", "Os "),
    ("concello de ", "Ayuntamiento"),
    ("deputacion provincial de ", "Diputación Provincial"),
    ("deputacion de ", "Diputación Provincial"),
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
    n = normalizar(base).replace("’", "'")
    for prefijo, tipo, *articulo in TIPOS_ENTIDAD:
        if n.startswith(prefijo):
            nombre = (articulo[0] if articulo else "") + nombre_propio(base[len(prefijo):].strip())
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
    """Escribe las filas; el nombre de una persona en el título (nombramientos, notificaciones) se sustituye."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    filas = [{**f, "titulo": titulo_sin_nombres(f["titulo"])} if f.get("titulo") else f for f in filas]
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
                     formulario: Callable[[dict], dict] | None = None, sesion=None,
                     por_registro: bool = False) -> tuple[int, int]:
    """Descarga y limpia los textos de la lista. Devuelve (hechos, errores). Reanudable: lo hecho queda escrito.

    formulario: para las API que piden el documento por POST, los campos de cada petición.
    por_registro: extraer recibe también el registro (p. ej. para no guardar el texto de una lista de personas).
    """
    inicio, hechos, errores = time.monotonic(), 0, 0
    for x in pendientes:
        if max_minutos and (time.monotonic() - inicio) / 60 > max_minutos:
            break
        u = url(x)
        try:
            r = obtener(u, accept=accept, formulario=formulario(x) if formulario else None, sesion=sesion)
        except ConnectionError:
            errores += 1
            continue
        if r.status != 200:
            errores += 1
            time.sleep(pausa)
            continue
        try:
            datos = extraer(r.contenido, x) if por_registro else extraer(r.contenido)
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
