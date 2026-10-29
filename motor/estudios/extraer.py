"""Extracción de la ficha de un programa de máster desde la web de su centro, con cita literal comprobada.

Para cada página de programa (capturada y guardada antes por el rastreador) se pide a Claude Haiku, en
lote, que devuelva los campos de la ficha. Cada campo lleva el valor y la frase literal de la página de la
que sale. Después, sin IA, se comprueba que la cita está de verdad en el texto: si no está, el valor no se
acepta y el campo va a revisión. Así se cumple la regla de la guía: «frase literal obligatoria que se
comprueba en el texto».

El resultado son hechos (una línea por campo) con su captura de origen; la ficha se calcula después desde
los hechos vigentes (docs/modelo-masters.md, §6).

Uso:
  python -m motor.estudios.extraer lote --muestra muestra.jsonl --salida ruta/ [--esperar-min 45]
      # todo en una ejecución: descarga cortés de cada página (robots.txt, reserva TDM), lote de la API,
      # espera, comprobación de citas y coste real; no guarda ninguna página, solo su huella
  python -m motor.estudios.extraer preparar --paginas ruta/paginas.jsonl --salida ruta/   # crea el lote
  python -m motor.estudios.extraer enviar --lote ruta/lote.jsonl                           # ANTHROPIC_API_KEY
  python -m motor.estudios.extraer recoger --id msgbatch_... --paginas ... --salida ruta/
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import os
import re
import sys
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

from motor.limpieza import parrafos_seguros

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


RE_FUERA = re.compile(r"(?is)<!--.*?-->|<(script|style|noscript|svg|nav|footer|template|iframe|form)\b.*?</\1>|<head\b.*?</head>")
RE_BLOQUE_WEB = re.compile(r"(?i)</?(p|div|li|ul|ol|h[1-6]|section|article|aside|header|main|dd|dt|dl|br|tr|table|"
                           r"tbody|thead|blockquote|figcaption|summary|details)\b[^>]*>")
RE_CELDA_FIN = re.compile(r"(?i)</t[dh]\s*>")
TIPOS_LD = {"Course", "EducationalOccupationalProgram", "CourseInstance", "Product", "Offer", "AggregateOffer"}


def _ld_lineas(html: str) -> list[str]:
    """Datos estructurados del programa (Schema.org) como líneas citables: el precio a veces solo está ahí."""
    lineas = []
    for bloque in re.findall(r'(?is)<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html or ""):
        try:
            d = json.loads(bloque.strip())
        except (ValueError, TypeError):
            continue
        pila = d if isinstance(d, list) else d.get("@graph", [d]) if isinstance(d, dict) else []
        while pila:
            x = pila.pop(0)
            if not isinstance(x, dict):
                continue
            tipos = x.get("@type") if isinstance(x.get("@type"), list) else [x.get("@type")]
            if set(map(str, tipos)) & TIPOS_LD:
                campos = {k: x.get(k) for k in ("name", "price", "lowPrice", "highPrice", "priceCurrency",
                                                 "timeRequired", "educationalCredentialAwarded", "numberOfCredits",
                                                 "courseMode", "startDate", "inLanguage") if isinstance(x.get(k), (str, int, float))}
                if campos:
                    lineas.append(f"Schema.org {'/'.join(map(str, tipos))}: " + "; ".join(f"{k}={v}" for k, v in campos.items()))
            for k in ("offers", "hasCourseInstance", "educationalCredentialAwarded"):
                v = x.get(k)
                pila += v if isinstance(v, list) else [v] if isinstance(v, dict) else []
    return lineas


def texto_de_pagina(html: str) -> str:
    """Texto visible de una página web, por líneas, sin menús, pies, formularios ni código; las tablas como
    «celda | celda». Se quitan las líneas con nombres de personas (motor.limpieza) y se añaden los datos
    estructurados del programa. Es lo que ve el modelo y donde se comprueba cada cita."""
    h = RE_FUERA.sub(" ", html or "")
    h = RE_CELDA_FIN.sub(" | ", h)
    h = RE_BLOQUE_WEB.sub("\n", h)
    h = re.sub(r"<[^>]+>", " ", h)
    lineas, previa = [], None
    for linea in html_lib.unescape(h).replace("\xa0", " ").splitlines():
        linea = " ".join(linea.split()).strip(" |")
        if linea and linea != previa:
            lineas.append(linea)
            previa = linea
    guardadas, _ = parrafos_seguros(lineas)
    return "\n".join(guardadas + _ld_lineas(html))[:MAX_CARACTERES]


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
        motivo = None if ok else "cita_no_literal"
        if ok and campo in NUMERICOS and not numero_en_cita(dato.get("valor"), cita):
            ok, motivo = False, "valor_no_en_cita"  # cita literal, pero el número no sale de ella
        hechos.append({"campo": campo, "valor": dato.get("valor") if ok else None,
                       "valor_propuesto": None if ok else dato.get("valor"),
                       "cita": cita, "cita_verificada": ok, "estado": "aceptado" if ok else "revision", "motivo": motivo})
    return hechos


NUMERICOS = {"creditos_ects", "plazas", "precio_total", "precio_credito", "reserva_matricula"}


def numero_en_cita(valor, cita: str) -> bool:
    """9800 está en «9.800 €», «9800€» o «9,800»; 60 en «60 ECTS». Valores no numéricos: no se comprueban."""
    try:
        v = float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return True
    numeros = set()
    for m in re.findall(r"\d[\d.,\s]*\d|\d", cita):
        m = m.replace(" ", "")
        for cand in (m.replace(".", "").replace(",", "."), m.replace(",", ""), m.replace(".", "").replace(",", "")):
            try:
                numeros.add(float(cand))
            except ValueError:
                pass
    return any(abs(v - n) < 0.005 for n in numeros)


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
    with (salida / "hechos.jsonl").open("w", encoding="utf-8") as f, \
            (salida / "paginas_extraidas.jsonl").open("w", encoding="utf-8") as fp:
        for linea in r.text.splitlines():
            x = json.loads(linea)
            if x["result"]["type"] != "succeeded" or x["custom_id"] not in textos:
                cuentas["errores"] += 1
                continue
            pagina, texto = textos[x["custom_id"]]
            datos = _json_de("".join(c.get("text", "") for c in x["result"]["message"]["content"]))
            cuentas["paginas"] += 1
            # una línea por página, tenga o no datos: «extraída y sin precio» no es lo mismo que «sin mirar»
            fp.write(json.dumps({"url": pagina["url"], "captura_sha256": pagina["sha256"], "extraido": ahora,
                                 "no_es_programa": bool(datos.get("no_es_programa")), "lote": batch_id},
                                ensure_ascii=False) + "\n")
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


# Precios del lote (Message Batches, 50 % del precio estándar), dólares por millón de tokens, para prompts de
# hasta 100.000 tokens y por encima. Fuente: https://platform.claude.com/docs/en/about-claude/pricing
# (consultada el 30/10/2026). Si cambian, se cambian aquí: el coste se recalcula con los tokens guardados.
PRECIOS_LOTE = {
    "claude-haiku-5-5": {"hasta_100k": {"entrada": 0.05, "salida": 0.25, "escritura_cache": 0.0625, "lectura_cache": 0.005},
                         "mas_de_100k": {"entrada": 0.25, "salida": 1.25, "escritura_cache": 0.3125, "lectura_cache": 0.025}},
}


def coste(uso: dict, modelo: str = MODELO) -> float:
    """Dólares de una petición del lote según su uso (tokens de entrada, caché y salida)."""
    ent = uso.get("input_tokens", 0)
    esc = uso.get("cache_creation_input_tokens", 0) or 0
    lec = uso.get("cache_read_input_tokens", 0) or 0
    sal = uso.get("output_tokens", 0)
    tramo = PRECIOS_LOTE[modelo]["hasta_100k" if ent + esc + lec <= 100_000 else "mas_de_100k"]
    return (ent * tramo["entrada"] + esc * tramo["escritura_cache"] + lec * tramo["lectura_cache"]
            + sal * tramo["salida"]) / 1_000_000


def capturar(urls: list[str], pausa: float = 1.0) -> list[dict]:
    """Descarga cada página con el lector cortés del rastreador (robots.txt de cada servidor, una petición por
    segundo y servidor) y la devuelve en memoria. Nada se escribe en disco: solo se registra la huella."""
    from motor.estudios.rastreador import Dominio, reserva_tdm, texto_de
    from urllib.parse import urlparse

    por_host: dict[str, list[str]] = {}
    for u in urls:
        por_host.setdefault(urlparse(u).netloc, []).append(u)
    paginas = []
    for host, lista in por_host.items():
        d = Dominio(f"https://{host}", None, pausa=pausa, max_peticiones=len(lista) + 4)
        for u in lista:
            r = d.get(u)
            fila = {"url": u, "estado_http": getattr(r, "status_code", None)}
            if r is None:
                fila["motivo"] = "robots_o_sin_respuesta"
            elif r.status_code == 200 and "html" in (r.headers.get("content-type") or ""):
                html = texto_de(r)
                fila.update({"sha256": hashlib.sha256(r.content).hexdigest(), "html": html,
                             "reserva_tdm": reserva_tdm(dict(r.headers), html)})
            else:
                fila["motivo"] = "no_html_o_error"
            paginas.append(fila)
    return paginas


def lote(muestra: Path, salida: Path, esperar_min: float = 45, max_paginas: int | None = None) -> dict:
    """Prueba o tanda completa en una sola ejecución: capturar, enviar, esperar, comprobar citas y medir coste."""
    filas = list({f["url"]: f for f in (json.loads(l) for l in muestra.read_text(encoding="utf-8").splitlines()
                                          if l.strip())}.values())[:max_paginas]
    meta = {f["url"]: f for f in filas}
    paginas = capturar([f["url"] for f in filas])
    salida.mkdir(parents=True, exist_ok=True)
    peticiones, textos, cuentas = [], {}, Counter()
    with (salida / "paginas_capturadas.jsonl").open("w", encoding="utf-8") as f:
        for pg in paginas:
            cuentas["pedidas"] += 1
            if pg.get("html") is None:
                cuentas[pg.get("motivo", "error")] += 1
            elif pg["reserva_tdm"]:
                cuentas["reserva_tdm"] += 1
            else:
                texto = texto_de_pagina(pg["html"])
                cid = id_pagina(pg["url"], pg["sha256"])
                textos[cid] = (pg, texto)
                peticiones.append(peticion(cid, pg["url"], texto))
                cuentas["enviadas"] += 1
                pg["caracteres_texto"] = len(texto)
            f.write(json.dumps({k: v for k, v in pg.items() if k != "html"}, ensure_ascii=False) + "\n")
    if not peticiones:
        return dict(cuentas)
    r = requests.post(API, headers=_cabeceras(), json={"requests": peticiones}, timeout=120)
    if r.status_code >= 400:
        return {**cuentas, "error_api": r.status_code, "detalle": r.text[:500]}
    b = r.json()
    (salida / "lote.json").write_text(json.dumps({"id": b["id"], "creado": b.get("created_at"), "peticiones": len(peticiones),
                                                  "modelo": MODELO}, ensure_ascii=False), encoding="utf-8")
    t0, fin = time.time(), time.time() + esperar_min * 60
    while b.get("processing_status") != "ended" and time.time() < fin:
        time.sleep(30)
        b = requests.get(f"{API}/{b['id']}", headers=_cabeceras(), timeout=60).json()
    cuentas["minutos_lote"] = round((time.time() - t0) / 60, 1)
    if b.get("processing_status") != "ended":
        return {**cuentas, "estado_lote": b.get("processing_status"), "id": b["id"]}
    res = requests.get(b["results_url"], headers=_cabeceras(), timeout=300)
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    uso_total, dolares, campos = Counter(), 0.0, Counter()
    motivos = Counter()
    with (salida / "hechos.jsonl").open("w", encoding="utf-8") as fh, \
            (salida / "paginas_extraidas.jsonl").open("w", encoding="utf-8") as fp:
        for linea in res.text.splitlines():
            x = json.loads(linea)
            if x["result"]["type"] != "succeeded" or x["custom_id"] not in textos:
                cuentas["resultado_" + x["result"]["type"]] += 1
                continue
            msg = x["result"]["message"]
            uso = msg.get("usage", {})
            for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
                uso_total[k] += uso.get(k, 0) or 0
            dolares += coste(uso)
            if msg.get("stop_reason") == "max_tokens":
                cuentas["cortadas_por_max_tokens"] += 1
            pagina, texto = textos[x["custom_id"]]
            datos = _json_de("".join(c.get("text", "") for c in msg["content"] if c.get("type") == "text"))
            cuentas["extraidas"] += 1
            if not datos:
                cuentas["json_ilegible"] += 1
            fp.write(json.dumps({"url": pagina["url"], "captura_sha256": pagina["sha256"], "extraido": ahora,
                                 "no_es_programa": bool(datos.get("no_es_programa")), "lote": b["id"],
                                 "uso": uso, "coste_usd": round(coste(uso), 6),
                                 **{k: meta.get(pagina["url"], {}).get(k) for k in ("proveedor", "grupo", "codigo_ruct")}},
                                ensure_ascii=False) + "\n")
            if datos.get("no_es_programa"):
                cuentas["no_es_programa"] += 1
                continue
            for h in verificar(datos, texto):
                h.update({"url": pagina["url"], "captura_sha256": pagina["sha256"], "modelo": MODELO,
                          "extraido": ahora, "lote": b["id"]})
                # la cita es texto ajeno: hasta tener el archivo privado no sale del trabajo; queda su huella
                # (para comprobarla después contra la página) y su longitud
                cita = h.pop("cita", "") or ""
                h["cita_sha256"] = hashlib.sha256(_norma(cita).encode()).hexdigest() if cita else None
                h["cita_palabras"] = len(cita.split())
                fh.write(json.dumps(h, ensure_ascii=False) + "\n")
                campos[(h["campo"], h["estado"])] += 1
                if h.get("motivo"):
                    motivos[h["motivo"]] += 1
    n = max(cuentas["extraidas"], 1)
    resumen = {**cuentas, "uso_tokens": dict(uso_total), "coste_usd": round(dolares, 6),
               "coste_usd_por_pagina": round(dolares / n, 6),
               "tokens_entrada_por_pagina": round(uso_total["input_tokens"] / n),
               "tokens_salida_por_pagina": round(uso_total["output_tokens"] / n),
               "hechos_aceptados": sum(v for (c, e), v in campos.items() if e == "aceptado"),
               "hechos_revision": sum(v for (c, e), v in campos.items() if e == "revision"),
               "motivos_revision": dict(motivos),
               "por_campo": {c: {e: v for (c2, e), v in campos.items() if c2 == c} for c in CAMPOS}}
    (salida / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    return resumen


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("orden", choices=["lote", "preparar", "enviar", "recoger"])
    p.add_argument("--muestra", help="lote: JSONL con {url, proveedor, grupo, codigo_ruct}")
    p.add_argument("--esperar-min", type=float, default=45)
    p.add_argument("--max-paginas", type=int)
    p.add_argument("--paginas")
    p.add_argument("--lote")
    p.add_argument("--id")
    p.add_argument("--salida")
    a = p.parse_args()
    if a.orden == "lote":
        res = lote(Path(a.muestra), Path(a.salida) / "datos" / "estudios" / "extraccion", a.esperar_min, a.max_paginas)
    elif a.orden == "preparar":
        res = preparar(Path(a.paginas), Path(a.salida))
    elif a.orden == "enviar":
        res = enviar(Path(a.lote))
    else:
        res = recoger(a.id, Path(a.paginas), Path(a.salida))
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
