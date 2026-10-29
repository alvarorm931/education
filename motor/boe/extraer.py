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

from motor.boe.clasificar import normalizar
from motor.boe.texto import ruta_texto
from motor.calendario import fin_de_plazo

VERSION = "plantilla_local_v1"

MESES = {m: i for i, m in enumerate(
    ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
     "noviembre", "diciembre"], start=1)}
UNIDADES = {
    "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
    "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiun": 21,
    "veintiuna": 21, "veintiuno": 21, "veintidos": 22, "veintitres": 23, "veinticuatro": 24,
    "veinticinco": 25, "veintiseis": 26, "veintisiete": 27, "veintiocho": 28, "veintinueve": 29,
    "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80,
    "noventa": 90, "cien": 100, "ciento": 100, "doscientas": 200, "doscientos": 200, "trescientas": 300,
    "trescientos": 300,
}


def numero(texto: str) -> int | None:
    t = normalizar(texto)
    if t.isdigit():
        return int(t)
    total = 0
    for parte in t.replace(" y ", " ").split():
        if parte not in UNIDADES:
            return None
        total += UNIDADES[parte]
    return total or None


def fecha_texto(dia: str, mes: str, anio: str) -> str | None:
    m = MESES.get(normalizar(mes))
    try:
        return date(int(anio), m, int(dia)).isoformat() if m else None
    except ValueError:
        return None


RE_BOLETIN = re.compile(
    r"«(?P<boletin>[^»]+)»\s*(?:número|núm\.|n\.º|nº)\s*(?P<numero>[\d.]+)\s*,\s*de\s+(?P<dia>\d{1,2})\s+de\s+"
    r"(?P<mes>[a-záéíóú]+)\s+de\s+(?P<anio>\d{4})", re.IGNORECASE)
RE_PLAZO = re.compile(
    r"plazo de presentación de solicitudes será de (?P<n>[\wáéíóú ]+?) días (?P<tipo>hábiles|naturales)", re.IGNORECASE)
RE_LINEA_PLAZA = re.compile(
    r"^(?P<n>[\wáéíóúñ ]+?)\s+plazas?\s+de\s+(?P<resto>.+)$", re.IGNORECASE)
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
    return {
        "numero": n,
        "denominacion": denominacion,
        "regimen": "laboral_fijo" if "personal laboral" in normalizar(resto) else "funcionario",
        "escala": esc.group("v").strip() if esc else None,
        "subescala": sub.group("v").strip() if sub else None,
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
            papel = "bases" if "se han publicado" in n and "bases" in n else ("extracto" if "extracto" in n else "otro")
            res["boletines_citados"].append({
                "boletin": b.group("boletin"), "numero": b.group("numero").replace(".", ""),
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
                plazo["fin_estimado"] = fin_de_plazo(pub, n, tipo).isoformat()
                plazo["calendario"] = "festivos nacionales (estimado)"
            res["plazo"] = plazo

    if not res["plazas"]:
        res["pendiente"].append("plazas")
    else:
        for p in res["plazas"]:
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


def alcance_por_turnos(plazas: list[dict]) -> str | None:
    turnos = {p["turno"] for p in plazas if p.get("turno")}
    if not turnos:
        return None
    if turnos <= {"promocion_interna", "movilidad"}:
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
        "tipo_acto": anuncio.get("tipo_acto"),
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
        acto["alcance"] = alcance_por_turnos(local["plazas"]) or acto["alcance"]
    else:
        acto["pendiente"].append("extraccion_ia")
    return acto


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
