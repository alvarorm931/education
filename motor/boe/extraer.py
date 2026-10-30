"""Extracción de actos a partir de los anuncios de oposiciones del BOE y de su texto.

Uso:
  python -m motor.boe.extraer --salida ruta/

Lee datos/boe/oposiciones/ y datos/boe/textos/ y regenera por completo datos/boe/actos/AAAA/MM.jsonl.
Es reproducible: si el extractor mejora, se vuelve a ejecutar sobre todo el histórico.

Plantilla local (verificada con anuncios reales de octubre de 2026):
  En el «Boletín Oficial de la Provincia de X» número N, de D de MES de AAAA, se han publicado las bases ...
  para proveer:
  Tres plazas de Trabajador/a Social, pertenecientes a la escala ..., subescala ..., clase ...,
    por el sistema de concurso-oposición, en turno libre.
  Se ha publicado, asimismo, un extracto de la convocatoria en el «Boletín Oficial de la Junta de Andalucía» ...
  El plazo de presentación de solicitudes será de veinte días hábiles a contar desde el siguiente al de la
    publicación de esta resolución en el «Boletín Oficial del Estado».
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from motor.boe.clasificar import REGLAS_ACTO, _primera, normalizar
from motor.boe.texto import ruta_texto
from motor.calendario import etiqueta, fin_de_plazo
from motor.catalogo.territorio import comunidad_codigo
from motor.catalogo.puestos import grupo, normalizar_puesto
from motor.extraccion.plazas import extraer_plazas
from motor.extraccion.plazo import VERSION as VERSION_PLAZO, extraer_plazo
from motor.extraccion.texto_es import MESES, UNIDADES, fecha_texto, numero  # noqa: F401 (se reexportan)

VERSION = "plantilla_local_v1"
# Tipos de acto en los que el texto puede fijar (o reabrir) un plazo de solicitudes
CON_PLAZO = {"convocatoria", "bases", "modificacion", "correccion", "otro", None}

RE_BOLETIN = re.compile(
    r"«(?P<boletin>[^»]+)»\s*(?:,?\s*(?:número|núm\.|n\.º|nº)\s*(?P<numero>[\d.]+))?\s*,\s*de\s+(?P<dia>\d{1,2})\s+de\s+"
    r"(?P<mes>[a-záéíóú]+)\s+de\s+(?P<anio>\d{4})", re.IGNORECASE)
RE_PLAZO = re.compile(
    r"plazo de presentación de solicitudes será de (?P<n>[\wáéíóú ]+?) días (?P<tipo>hábiles|naturales)", re.IGNORECASE)
RE_LINEA_PLAZA = re.compile(
    r"^(?P<n>[\wáéíóúñ ]+?)\s+(?P<clase_plaza>plazas?|puestos?)\s+de\s+(?P<resto>.+)$", re.IGNORECASE)
RE_ID_BOE = re.compile(r"\bBOE-[AB]-\d{4}-\d+\b")
RE_SISTEMA = re.compile(r"por el sistema de (?P<s>concurso-oposición|concurso oposición|oposición|concurso)", re.IGNORECASE)
RE_ESCALA = re.compile(r"escala de (?P<v>[^,]+)", re.IGNORECASE)
RE_SUBESCALA = re.compile(r"subescala (?P<v>[^,]+?)(?:\s+y\s+clase|,|$)", re.IGNORECASE)
RE_CLASE = re.compile(r"clase (?P<v>[^,]+)", re.IGNORECASE)


def _turno(linea: str) -> str | None:
    t = normalizar(linea)
    if "promocion interna" in t:
        return "promocion_interna"
    if "discapacidad" in t:
        return "discapacidad"
    if "movilidad" in t:
        return "movilidad"
    if "turno restringido" in t:
        return "restringido"
    if "turno libre" in t or "acceso libre" in t:
        return "libre"
    return None


def _sistema(linea: str) -> str | None:
    m = RE_SISTEMA.search(linea)
    if not m:
        return None
    return {"concurso oposicion": "concurso-oposicion"}.get(normalizar(m.group("s")), normalizar(m.group("s")))


def plaza(linea: str) -> dict | None:
    m = RE_LINEA_PLAZA.match(linea.strip())
    if not m:
        return None
    n = numero(m.group("n"))
    if n is None:
        return None
    resto = m.group("resto")
    corte = re.search(r",\s*pertenecientes?\b|\s+de la plantilla\b|,\s*por el sistema|\s+por el sistema|,\s*en turno", resto)
    denominacion = resto[: corte.start()].strip() if corte else resto.rstrip(".").strip()
    esc, sub, cla = RE_ESCALA.search(resto), RE_SUBESCALA.search(resto), RE_CLASE.search(resto)
    escala = esc.group("v").strip() if esc else None
    subescala = sub.group("v").strip() if sub else None
    norm = normalizar_puesto(denominacion)
    g, g_fuente = grupo(linea, escala, subescala)
    return {
        "numero": n,
        "tipo": "puesto" if m.group("clase_plaza").lower().startswith("puesto") else "plaza",
        "denominacion": denominacion,
        "regimen": "laboral_fijo" if "personal laboral" in normalizar(resto) else "funcionario",
        "puesto_clave": norm["clave"],
        "puesto": norm["nombre"],
        "especialidad": norm["especialidad"],
        "grupo": g,
        "grupo_fuente": g_fuente,
        "escala": escala,
        "subescala": subescala,
        "clase": cla.group("v").strip().rstrip(".") if cla else None,
        "sistema": _sistema(resto),
        "turno": _turno(resto),
        "cita": linea.strip(),
    }


def extraer_local(texto: str, fecha_boe: str) -> dict:
    """Aplica la plantilla de anuncio local. Devuelve campos y lo que no se pudo extraer."""
    lineas = [l for l in texto.split("\n") if l.strip()]
    res: dict = {"plazas": [], "boletines_citados": [], "plazo": None, "pendiente": []}

    for l in lineas:
        for b in RE_BOLETIN.finditer(l):
            n = normalizar(l)
            if "rectificad" in n or "modificad" in n:
                papel = "rectificacion"
            elif "se han publicado" in n and "bases" in n:
                papel = "bases"
            elif "extracto" in n:
                papel = "extracto"
            else:
                papel = "otro"
            if normalizar(b.group("boletin")) == "boletin oficial del estado":
                continue
            res["boletines_citados"].append({
                "boletin": b.group("boletin"), "numero": (b.group("numero") or "").replace(".", "") or None,
                "fecha": fecha_texto(b.group("dia"), b.group("mes"), b.group("anio")), "papel": papel, "cita": l})
        p = plaza(l)
        if p:
            res["plazas"].append(p)
        m = RE_PLAZO.search(l)
        if m:
            n = numero(m.group("n"))
            tipo = "habiles" if normalizar(m.group("tipo")) == "habiles" else "naturales"
            desde_boe = "boletin oficial del estado" in normalizar(l)
            plazo = {"dias": n, "tipo": tipo, "cuenta_desde": "BOE" if desde_boe else "otro", "cita": l}
            if n and desde_boe:
                pub = date.fromisoformat(fecha_boe)
                # Festivos de la comunidad del boletín provincial que publica las bases (anuncio local)
                ccaa = comunidad_codigo(boletines=[x["boletin"] for x in res["boletines_citados"]])
                plazo["fin_estimado"] = fin_de_plazo(pub, n, tipo, ccaa).isoformat()
                plazo["calendario"] = etiqueta(pub, ccaa)
            res["plazo"] = plazo

    if not res["plazas"]:
        res["pendiente"].append("plazas")
    else:
        for p in res["plazas"]:
            if p["tipo"] == "puesto":
                continue
            if p["sistema"] is None:
                res["pendiente"].append("sistema")
            if p["turno"] is None:
                res["pendiente"].append("turno")
    if not any(b["papel"] == "bases" for b in res["boletines_citados"]):
        res["pendiente"].append("boletin_bases")
    if not res["plazo"]:
        res["pendiente"].append("plazo")
    res["pendiente"] = sorted(set(res["pendiente"]))
    return res


def es_provision(texto: str) -> bool:
    t = normalizar(texto[:600])
    return "para proveer por concurso" in t or "por libre designacion" in t


def alcance_por_turnos(plazas: list[dict]) -> str | None:
    turnos = {p["turno"] for p in plazas if p.get("turno")}
    if not turnos:
        return None
    if turnos <= {"promocion_interna", "movilidad", "restringido"}:
        return "promocion_interna"
    return "acceso"


def construir_acto(anuncio: dict, texto: dict | None) -> dict:
    acto = {
        "id": anuncio["identificador"],
        "fecha": anuncio["fecha"],
        "fuente": "BOE",
        "url": anuncio.get("url_html"),
        "url_pdf": anuncio.get("url_pdf"),
        "titulo": anuncio.get("titulo"),
        "departamento": anuncio.get("departamento"),
        "epigrafe": anuncio.get("epigrafe"),
        "ambito": anuncio.get("ambito"),
        "convocante": anuncio.get("convocante"),
        "tipo_acto": _primera(REGLAS_ACTO, normalizar(anuncio["titulo"])) or "otro" if anuncio.get("titulo")
        else anuncio.get("tipo_acto"),  # con las reglas vigentes, no con las del día de la captura
        "alcance": anuncio.get("alcance"),
        "modalidad": anuncio.get("modalidad"),
        "tiene_texto": texto is not None,
        "extraccion": "titulo",
        "pendiente": [],
    }
    if texto is None:
        acto["pendiente"].append("texto")
        return acto
    acto["referencias"] = texto.get("referencias", [])
    citados = set(RE_ID_BOE.findall(texto.get("texto") or ""))
    citados |= {r["referencia"] for r in acto["referencias"] if r.get("referencia")}
    citados.discard(anuncio["identificador"])
    acto["refiere_a"] = sorted(citados)  # clave para unir correcciones, anulaciones y modificaciones con su anuncio
    acto["tablas_con_datos_personales"] = sum(1 for t in texto.get("tablas", []) if t.get("datos_personales"))
    acto["filas_en_tablas_personales"] = sum(t.get("filas", 0) for t in texto.get("tablas", []) if t.get("datos_personales"))

    cuerpo = texto.get("texto") or ""
    if anuncio.get("ambito") == "local" and "se han publicado" in cuerpo and "plazo de presentación" in cuerpo:
        local = extraer_local(cuerpo, anuncio["fecha"])
        acto.update({
            "extraccion": VERSION,
            "tipo_acto": "apertura_plazo" if acto["tipo_acto"] in {"convocatoria", "otro", None} else acto["tipo_acto"],
            "plazas": local["plazas"],
            "total_plazas": sum(p["numero"] for p in local["plazas"]) or None,
            "boletines_citados": local["boletines_citados"],
            "plazo": local["plazo"],
            "pendiente": local["pendiente"],
        })
        if es_provision(cuerpo) or (local["plazas"] and all(p["tipo"] == "puesto" for p in local["plazas"])):
            acto["alcance"] = "provision_puestos"
        else:
            acto["alcance"] = alcance_por_turnos(local["plazas"]) or acto["alcance"]
    else:
        if acto["tipo_acto"] in CON_PLAZO:
            plazo = extraer_plazo(cuerpo, anuncio["fecha"], "Boletín Oficial del Estado")
            if plazo:
                acto["plazo"] = plazo
                acto["extraccion"] = VERSION_PLAZO
            if not plazo or not plazo.get("fin_estimado"):
                acto["pendiente"].append("plazo")
            aplicar_plazas(acto, cuerpo)
        acto["pendiente"].append("extraccion_ia")
    return acto


def aplicar_plazas(acto: dict, cuerpo: str) -> None:
    """Plazas desde la frase «se convoca proceso selectivo para cubrir N plazas del Cuerpo...»."""
    p = extraer_plazas(cuerpo)
    if not p:
        acto["pendiente"].append("plazas")
        return
    acto["total_plazas"] = p["total"]
    acto["plazas"] = p.get("plazas") or []
    acto["cita_plazas"] = p["cita"]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    a = p.parse_args(argv)
    raiz = a.salida
    por_mes: dict[str, list[dict]] = defaultdict(list)
    for fichero in sorted((raiz / "datos" / "boe" / "oposiciones").glob("*/*/*.jsonl")):
        for linea in fichero.read_text(encoding="utf-8").splitlines():
            anuncio = json.loads(linea)
            rt = ruta_texto(raiz, anuncio["identificador"], anuncio["fecha"])
            texto = json.loads(rt.read_text(encoding="utf-8")) if rt.exists() else None
            acto = construir_acto(anuncio, texto)
            por_mes[acto["fecha"][:7]].append(acto)

    total, resumen = 0, Counter()
    for mes, actos in sorted(por_mes.items()):
        destino = raiz / "datos" / "boe" / "actos" / mes[:4] / f"{mes[5:]}.jsonl"
        destino.parent.mkdir(parents=True, exist_ok=True)
        with destino.open("w", encoding="utf-8") as f:
            for acto in actos:
                f.write(json.dumps(acto, ensure_ascii=False) + "\n")
                total += 1
                resumen[acto["extraccion"]] += 1
                for x in acto["pendiente"]:
                    resumen["pendiente:" + x] += 1
    print(f"Actos: {total}")
    for k, v in sorted(resumen.items()):
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
