"""Extracción de la ficha de un programa de máster desde la web de su centro, con cita literal comprobada.

Para cada página de programa (capturada y guardada antes por el rastreador) se pide a Claude Haiku, en
lote, que devuelva los campos de la ficha. Cada campo lleva el valor y la frase literal de la página de la
que sale. Después, sin IA, se comprueba que la cita está de verdad en el texto: si no está, el valor no se
acepta y el campo va a revisión. Así se cumple la regla de la guía: «frase literal obligatoria que se
comprueba en el texto».

El resultado son hechos (una línea por campo) con su captura de origen; la ficha se calcula después desde
los hechos vigentes (docs/modelo-masters.md, §6).

Uso:
  python -m motor.estudios.extraer preparar --paginas ruta/paginas.jsonl --salida ruta/   # crea el lote
  python -m motor.estudios.extraer enviar --lote ruta/lote.jsonl                           # ANTHROPIC_API_KEY
  python -m motor.estudios.extraer recoger --id msgbatch_... --paginas ... --salida ruta/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests

from motor.limpieza import limpiar_html

API = "https://api.anthropic.com/v1/messages/batches"
MODELO = os.environ.get("MODELO_EXTRACCION", "claude-haiku-5-5")
MAX_CARACTERES = 60_000  # páginas largas: se recorta por el final (pie, avisos legales)

CAMPOS = {
    "nombre": "nombre exacto del programa",
    "tipo_titulo": "máster universitario oficial | máster de formación permanente / título propio | máster no universitario | experto | especialista | otro",
    "universidad_que_expide": "universidad que expide el título, si la hay",
    "centro_que_imparte": "escuela o centro que lo imparte, si es distinto de la universidad",
    "creditos_ects": "número de créditos ECTS",
    "duracion": "duración (meses, cursos, horas)",
    "modalidad": "presencial | semipresencial | online | varias",
    "sedes": "ciudades o campus",
    "idioma": "idioma o idiomas de impartición",
    "fecha_inicio": "fecha o mes de inicio de la próxima edición",
    "plazo_admision": "fechas de preinscripción o admisión",
    "horario": "horario y si es compatible con trabajar",
    "plazas": "número de plazas",
    "precio_total": "importe total en euros",
    "precio_credito": "importe por crédito en euros",
    "reserva_matricula": "importe de reserva de plaza o matrícula",
    "descuentos_becas": "becas, ayudas, descuentos o financiación",
    "requisitos_acceso": "titulación previa y requisitos de acceso",
    "proceso_admision": "pruebas, entrevista o criterios de selección",
    "asignaturas": "lista de asignaturas o módulos, con créditos si aparecen",
    "practicas": "prácticas en empresa: si hay, duración y créditos",
    "tfm": "trabajo fin de máster: créditos",
    "metodologia": "cómo se imparte: clases, casos, proyectos, sesiones en directo…",
    "evaluacion": "sistema de evaluación, con porcentajes si aparecen",
    "habilita_profesion": "si habilita para una profesión regulada",
    "salidas": "salidas profesionales que declara el centro",
}
SISTEMA = (
    "Eres un extractor de datos para un portal informativo. Lees la página web de un programa de posgrado "
    "y devuelves SOLO JSON. Reglas: 1) Solo lo que dice el texto; nada inventado ni deducido. "
    "2) Para cada campo: {\"valor\": ..., \"cita\": \"frase literal copiada exactamente del texto, de 3 a 40 "
    "palabras\"}. 3) Si un dato no aparece, el campo es null. 4) Importes en euros como número. "
    "5) «asignaturas» es una lista de {\"nombre\", \"creditos\"} y su cita es la de la primera. "
    "6) Si la página no es la de un programa concreto, devuelve {\"no_es_programa\": true}."
)


def _norma(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = re.sub(r"[“”«»\"'’`´]", "", s)
    return " ".join(s.split())


def texto_de_pagina(html: str) -> str:
    limpio = limpiar_html(html)
    partes = [limpio.get("texto", "")]
    for t in limpio.get("tablas", []):
        for fila in t.get("contenido", []) or []:
            partes.append(" | ".join(fila))
    return "\n".join(p for p in partes if p)[:MAX_CARACTERES]


def peticion(custom_id: str, url: str, texto: str) -> dict:
    esquema = "\n".join(f"- {k}: {v}" for k, v in CAMPOS.items())
    return {
        "custom_id": custom_id,
        "params": {
            "model": MODELO,
            "max_tokens": 3000,
            "system": [{"type": "text", "text": SISTEMA + "\nCampos:\n" + esquema, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": f"URL: {url}\n\nTEXTO DE LA PÁGINA:\n{texto}"}],
        },
    }


def id_pagina(url: str, sha: str) -> str:
    return hashlib.sha256(f"{url}|{sha}".encode()).hexdigest()[:40]


def verificar(respuesta: dict, texto: str) -> list[dict]:
    """Un hecho por campo; solo se acepta el valor si la cita está literalmente en el texto."""
    base = _norma(texto)
    hechos = []
    for campo in CAMPOS:
        dato = respuesta.get(campo)
        if not isinstance(dato, dict) or dato.get("valor") in (None, "", []):
            continue
        cita = dato.get("cita") or ""
        ok = len(cita.split()) >= 2 and _norma(cita) in base
        hechos.append({"campo": campo, "valor": dato.get("valor") if ok else None,
                       "valor_propuesto": None if ok else dato.get("valor"),
                       "cita": cita, "cita_verificada": ok, "estado": "aceptado" if ok else "revision"})
    return hechos


def _json_de(texto: str) -> dict:
    m = re.search(r"\{.*\}", texto, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except ValueError:
        return {}


# ----------------------------------------------------------------------------------------- órdenes


def preparar(paginas: Path, salida: Path) -> dict:
    """paginas.jsonl: {"url", "sha256", "html"} por línea (o "ruta" a la captura)."""
    salida.mkdir(parents=True, exist_ok=True)
    n, reservadas = 0, 0
    with (salida / "lote.jsonl").open("w", encoding="utf-8") as f:
        for linea in paginas.read_text(encoding="utf-8").splitlines():
            p = json.loads(linea)
            if p.get("reserva_tdm"):  # el titular reservó la minería de datos: no se procesa, solo se enlaza
                reservadas += 1
                continue
            html = p.get("html") or Path(p["ruta"]).read_text(encoding="utf-8", errors="replace")
            texto = texto_de_pagina(html)
            f.write(json.dumps(peticion(id_pagina(p["url"], p["sha256"]), p["url"], texto), ensure_ascii=False) + "\n")
            n += 1
    return {"peticiones": n, "excluidas_por_reserva_tdm": reservadas}


def _cabeceras() -> dict:
    clave = os.environ.get("ANTHROPIC_API_KEY")
    if not clave:
        sys.exit("Falta ANTHROPIC_API_KEY (secreto de GitHub)")
    return {"x-api-key": clave, "anthropic-version": "2023-06-01", "content-type": "application/json"}


def enviar(lote: Path) -> dict:
    reqs = [json.loads(l) for l in lote.read_text(encoding="utf-8").splitlines()]
    r = requests.post(API, headers=_cabeceras(), json={"requests": reqs}, timeout=120)
    r.raise_for_status()
    return r.json()


def recoger(batch_id: str, paginas: Path, salida: Path, esperar_min: float = 50) -> dict:
    fin = time.time() + esperar_min * 60
    while True:
        b = requests.get(f"{API}/{batch_id}", headers=_cabeceras(), timeout=60).json()
        if b.get("processing_status") == "ended" or time.time() > fin:
            break
        time.sleep(60)
    if b.get("processing_status") != "ended":
        return {"estado": b.get("processing_status"), "cuentas": b.get("request_counts")}
    textos = {}
    for linea in paginas.read_text(encoding="utf-8").splitlines():
        p = json.loads(linea)
        html = p.get("html") or Path(p["ruta"]).read_text(encoding="utf-8", errors="replace")
        textos[id_pagina(p["url"], p["sha256"])] = (p, texto_de_pagina(html))
    r = requests.get(b["results_url"], headers=_cabeceras(), timeout=300)
    salida.mkdir(parents=True, exist_ok=True)
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cuentas = {"paginas": 0, "hechos": 0, "aceptados": 0, "revision": 0, "no_programa": 0, "errores": 0}
    with (salida / "hechos.jsonl").open("w", encoding="utf-8") as f:
        for linea in r.text.splitlines():
            x = json.loads(linea)
            if x["result"]["type"] != "succeeded" or x["custom_id"] not in textos:
                cuentas["errores"] += 1
                continue
            pagina, texto = textos[x["custom_id"]]
            datos = _json_de("".join(c.get("text", "") for c in x["result"]["message"]["content"]))
            cuentas["paginas"] += 1
            if datos.get("no_es_programa"):
                cuentas["no_programa"] += 1
                continue
            for h in verificar(datos, texto):
                h.update({"url": pagina["url"], "captura_sha256": pagina["sha256"], "modelo": MODELO,
                          "extraido": ahora, "lote": batch_id})
                f.write(json.dumps(h, ensure_ascii=False) + "\n")
                cuentas["hechos"] += 1
                cuentas["aceptados" if h["estado"] == "aceptado" else "revision"] += 1
    return cuentas


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("orden", choices=["preparar", "enviar", "recoger"])
    p.add_argument("--paginas")
    p.add_argument("--lote")
    p.add_argument("--id")
    p.add_argument("--salida")
    a = p.parse_args()
    if a.orden == "preparar":
        res = preparar(Path(a.paginas), Path(a.salida))
    elif a.orden == "enviar":
        res = enviar(Path(a.lote))
    else:
        res = recoger(a.id, Path(a.paginas), Path(a.salida))
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
