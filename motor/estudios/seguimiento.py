"""Estado de cada campo esencial de cada máster, siguiente paso y fecha de la próxima comprobación.

Es la pieza que mantiene al día lo que los centros dan solo al registrarse
(docs/estrategia-informacion-cerrada.md, §4 y §5). Para cada página de programa junta:
  - los hechos extraídos con cita comprobada (motor/estudios/extraer.py),
  - la medición de la página (rastreador: si el formulario pide correo, PDF de precios, precio en Schema.org),
  - los datos de fuentes oficiales (RUCT, decretos de precios) y los facilitados por el centro a petición,
y decide para cada campo de dónde sale el dato, qué hacer a continuación y cuándo volver a mirar.

Uso:
  python -m motor.estudios.seguimiento --hechos hechos.jsonl --extraidas paginas_extraidas.jsonl
         --medidas medidas.jsonl [--oficiales oficiales.jsonl] [--facilitados facilitados.jsonl]
         --salida ruta/ [--hoy AAAA-MM-DD]

«facilitados.jsonl» es el registro de peticiones a centros con respuesta: {"url_programa", "campo",
"valor", "fecha", "canal"}; «oficiales.jsonl», los datos de fuente oficial ya unidos a la página del
programa: {"url_programa", "campo", "valor", "fuente", "url", "capturado"}.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

# Lo esencial para elegir un máster (y lo que más se esconde tras el formulario).
ESENCIALES = ["precio_total", "asignaturas", "metodologia", "evaluacion", "horario", "plazas", "plazo_admision",
              "descuentos_becas", "tipo_titulo", "universidad_que_expide"]
VISIBLES = {"publicado_ficha", "documento_publico", "fuente_oficial"}  # se ve sin dar datos
SIGUIENTE = {
    "sin_comprobar": "extraer",
    "en_revision": "revisar_cita",
    "solo_con_registro": "buscar_documento_publico_o_fuente_oficial_y_despues_pedir_al_centro",
    "no_publicado": "buscar_documento_publico_o_fuente_oficial_y_despues_pedir_al_centro",
    "publicado_ficha": "vigilar_cambios",
    "documento_publico": "vigilar_cambios",
    "fuente_oficial": "vigilar_boletin_o_registro",
    "facilitado_centro": "pedir_actualizacion_antes_de_la_admision",
}
# Días hasta la próxima comprobación, en temporada de admisión y fuera de ella.
FRECUENCIA = {
    "facilitado_centro": (365, 365),
    "fuente_oficial": (30, 90),
    "solo_con_registro": (14, 30),
    "no_publicado": (14, 30),
}
MESES_TEMPORADA = {1, 2, 3, 4, 5, 6, 7, 8, 9}  # preinscripción de enero a septiembre en la mayoría


def en_temporada(hoy: date, hechos: dict[str, dict]) -> bool:
    """Admisión abierta o cercana: si el centro da un plazo, manda él; si no, el calendario habitual."""
    plazo = (hechos.get("plazo_admision") or {}).get("valor")
    if isinstance(plazo, dict) and plazo.get("hasta"):
        try:
            return date.fromisoformat(plazo["hasta"]) >= hoy
        except ValueError:
            pass
    return hoy.month in MESES_TEMPORADA


def estado_campo(campo: str, hecho: dict | None, medida: dict, oficial: dict | None, facilitado: dict | None) -> dict:
    """El mejor origen disponible para un campo, de más fuerte a más débil."""
    if hecho and hecho.get("estado") == "aceptado":
        doc = str(hecho.get("url", "")).lower().split("?")[0].endswith((".pdf", ".xlsx", ".xls", ".docx"))
        return {"estado": "documento_publico" if doc else "publicado_ficha", "valor": hecho["valor"],
                "fuente_url": hecho.get("url"), "cita": hecho.get("cita"), "capturado": hecho.get("extraido", "")[:10]}
    if oficial:
        return {"estado": "fuente_oficial", "valor": oficial["valor"], "fuente_url": oficial.get("url"),
                "fuente": oficial.get("fuente"), "capturado": oficial.get("capturado")}
    if facilitado:
        return {"estado": "facilitado_centro", "valor": facilitado["valor"], "fecha_respuesta": facilitado.get("fecha"),
                "canal": facilitado.get("canal")}
    if hecho and hecho.get("estado") == "revision":
        return {"estado": "en_revision", "valor_propuesto": hecho.get("valor_propuesto"), "cita": hecho.get("cita")}
    if not medida.get("extraido"):
        return {"estado": "sin_comprobar"}
    # Extraído y sin dato: si la página pide el correo, el dato está tras el registro.
    return {"estado": "solo_con_registro" if medida.get("formulario_pide_correo") else "no_publicado"}


def proxima(estado: str, temporada: bool, hoy: date) -> date:
    dentro, fuera = FRECUENCIA.get(estado, (7, 30))
    return hoy + timedelta(days=dentro if temporada else fuera)


def seguir(url: str, hechos: dict[str, dict], medida: dict, oficiales: dict[str, dict],
           facilitados: dict[str, dict], hoy: date) -> dict:
    temporada = en_temporada(hoy, hechos)
    campos = {}
    for c in ESENCIALES:
        e = estado_campo(c, hechos.get(c), medida, oficiales.get(c), facilitados.get(c))
        e["siguiente_paso"] = SIGUIENTE[e["estado"]]
        e["comprobado"] = hoy.isoformat()
        e["proxima_comprobacion"] = proxima(e["estado"], temporada, hoy).isoformat()
        campos[c] = e
    visibles = sum(1 for e in campos.values() if e["estado"] in VISIBLES)
    comprobados = sum(1 for e in campos.values() if e["estado"] != "sin_comprobar")
    return {"url": url, "temporada_admision": temporada, "campos": campos,
            # indicador de transparencia: qué parte de lo esencial se ve sin dar datos (solo si se ha mirado todo)
            "transparencia": round(visibles / len(ESENCIALES), 2) if comprobados == len(ESENCIALES) else None,
            "pedir_al_centro": sorted(c for c, e in campos.items() if e["estado"] in {"solo_con_registro", "no_publicado"}),
            "proxima_comprobacion": min(e["proxima_comprobacion"] for e in campos.values())}


def _jsonl(ruta: Path | None) -> list[dict]:
    if not ruta:
        return []
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]


def ejecutar(hechos: Path, medidas: Path, salida: Path, oficiales: Path | None = None,
             facilitados: Path | None = None, hoy: date | None = None, extraidas: Path | None = None) -> dict:
    hoy = hoy or date.today()
    por_url: dict[str, dict[str, dict]] = defaultdict(dict)
    for h in _jsonl(hechos):
        previo = por_url[h["url"]].get(h["campo"])
        if previo is None or (previo.get("estado") != "aceptado" and h.get("estado") == "aceptado"):
            por_url[h["url"]][h["campo"]] = h
    med = {m["url"]: m for m in _jsonl(medidas)}
    no_programa = set()
    for x in _jsonl(extraidas):  # páginas ya pasadas por la extracción, tengan o no datos
        if x.get("no_es_programa"):
            no_programa.add(x["url"])
        med.setdefault(x["url"], {})["extraido"] = True
    for url in por_url:
        med.setdefault(url, {})["extraido"] = True
    ofi: dict[str, dict] = defaultdict(dict)
    for o in _jsonl(oficiales):
        ofi[o["url_programa"]][o["campo"]] = o
    fac: dict[str, dict] = defaultdict(dict)
    for f in _jsonl(facilitados):
        fac[f["url_programa"]][f["campo"]] = f
    salida.mkdir(parents=True, exist_ok=True)
    cuentas, pedir = Counter(), Counter()
    with (salida / "seguimiento.jsonl").open("w", encoding="utf-8") as fh:
        for url in sorted((set(med) | set(por_url)) - no_programa):
            s = seguir(url, por_url.get(url, {}), med.get(url, {}), ofi.get(url, {}), fac.get(url, {}), hoy)
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")
            cuentas.update(e["estado"] for e in s["campos"].values())
            pedir.update(s["pedir_al_centro"])
    return {"paginas": len((set(med) | set(por_url)) - no_programa), "no_programa": len(no_programa),
            "estados": dict(cuentas), "campos_a_pedir": dict(pedir)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--hechos", required=True)
    p.add_argument("--medidas", required=True)
    p.add_argument("--extraidas")
    p.add_argument("--oficiales")
    p.add_argument("--facilitados")
    p.add_argument("--salida", required=True)
    p.add_argument("--hoy")
    a = p.parse_args()
    res = ejecutar(Path(a.hechos), Path(a.medidas), Path(a.salida), Path(a.oficiales) if a.oficiales else None,
                   Path(a.facilitados) if a.facilitados else None, date.fromisoformat(a.hoy) if a.hoy else None,
                   Path(a.extraidas) if a.extraidas else None)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
