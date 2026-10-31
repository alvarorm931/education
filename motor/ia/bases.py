"""Datos de las bases de cada proceso selectivo con Claude (lote de la API de Anthropic), con cita literal comprobada.

De cada proceso se toma el texto de sus bases (motor/procesos.py): en los procesos locales, las bases publicadas en el
boletín provincial o autonómico (no sus correcciones); en los demás, el texto del anuncio de origen (BOE, boletín
autonómico), que en el Estado, las comunidades y las universidades trae las bases enteras. Se pide a Claude Haiku, en
lote, que devuelva los campos de CAMPOS, cada uno con su valor y la frase literal de la que sale. Después, sin IA, se
comprueba que la cita está de verdad en el texto (las mismas comprobaciones que la extracción de másters,
motor/estudios/extraer.py); si no está, el valor no se acepta y queda en «rechazados» con su motivo.

Los textos son de boletines oficiales y ya están limpios de datos de personas (motor/limpieza.py), así que el
resultado, con sus citas, va a la rama de datos: datos/oposiciones/extraccion/AAAA/<proceso>.json, con el documento de
origen (id, URL, huella del texto), el modelo y la fecha. Solo se extrae lo que no se ha extraído ya con el mismo texto.

Precios (https://platform.claude.com/docs/en/about-claude/pricing, consultado el 30/10/2026), Claude Haiku 5.5 en lote
y peticiones de hasta 100.000 tokens: entrada 0,05 $/MTok, salida 0,25 $/MTok. Cada lote deja su uso y su coste en
datos/oposiciones/extraccion/lotes/.

Uso (extraccion-bases.yml; la clave ANTHROPIC_API_KEY solo en ese paso):
  python -m motor.ia.bases lote --datos ruta/ --n 40 --estados plazo_abierto --esperar-min 50 --salida ruta/
  python -m motor.ia.bases retomar --lote-json ruta/lote.json --datos ruta/ --salida ruta/
  python -m motor.ia.bases preparar --datos ruta/ --n 40 --salida ruta/      # solo el fichero del lote, sin la API
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from motor.autonomicos.actos import texto_de
from motor.estudios import extraer as ex

MODELO = "claude-haiku-5-5"
API = ex.API
MAX_TOKENS = 4000
MAX_CARACTERES = 70_000   # unos 18.000 tokens; si el texto es más largo, el principio y el final (el temario va al final)
PRECIO = {"input_tokens": 0.05, "output_tokens": 0.25, "cache_creation_input_tokens": 0.125,
          "cache_read_input_tokens": 0.01}  # $ por millón de tokens, lote; la caché a precio normal (cota superior)

CAMPOS = {
    "denominacion": "denominación de la plaza, cuerpo, escala o categoría",
    "grupo": "grupo o subgrupo de clasificación (A1, A2, B, C1, C2, E / agrupaciones profesionales)",
    "vinculo": "funcionario de carrera | personal laboral fijo | funcionario interino | laboral temporal | otro",
    "sistema": "oposición | concurso-oposición | concurso",
    "plazas_total": "número total de plazas convocadas",
    "plazas_turno_libre": "plazas de turno libre",
    "plazas_promocion_interna": "plazas de promoción interna",
    "plazas_discapacidad": "plazas reservadas a personas con discapacidad",
    "titulacion": "titulación exigida",
    "otros_requisitos": "otros requisitos de los aspirantes (edad, nacionalidad, carné, idioma…), 30 palabras como máximo",
    "idioma_cooficial": "conocimiento exigido o valorado de lengua cooficial (catalán, valenciano, gallego, euskera) y nivel",
    "tasa_euros": "importe de la tasa o derechos de examen en euros (turno general)",
    "exenciones_tasa": "exenciones o reducciones de la tasa, 25 palabras como máximo",
    "plazo_solicitudes": "plazo para presentar solicitudes y desde cuándo cuenta",
    "presentacion": "dónde y cómo se presentan las solicitudes (sede electrónica, registro), 25 palabras como máximo",
    "publicaciones": "dónde se publicarán las listas y los anuncios del proceso (tablón, sede, web, boletín)",
    "ejercicios": "lista de los ejercicios de la oposición, cada uno en 12 palabras como máximo (hasta 8)",
    "temas": "número de temas del temario",
    "meritos": "méritos que se valoran en el concurso y su puntuación máxima, 30 palabras como máximo",
    "bolsa": "si con el proceso se crea una bolsa o lista de espera (sí/no y para qué)",
    "practicas_o_curso": "periodo de prácticas o curso selectivo tras aprobar",
}
NUMERICOS = {"plazas_total", "plazas_turno_libre", "plazas_promocion_interna", "plazas_discapacidad", "tasa_euros",
             "temas"}
SISTEMA = (
    "Eres un extractor de datos para un portal informativo de oposiciones. Lees las bases de un proceso selectivo "
    "publicadas en un boletín oficial y devuelves SOLO un objeto JSON compacto, sin saltos de línea ni texto fuera "
    "del JSON. Reglas: "
    "1) Solo lo que dice el texto; nada inventado ni deducido. "
    "2) Incluye SOLO los campos que aparecen en el texto; los que no aparecen no se escriben. "
    "3) Cada campo es {\"v\": valor, \"c\": \"cita\"}, donde la cita es una frase copiada exactamente del texto, "
    "de 3 a 25 palabras, que contiene el dato. "
    "4) Números (plazas, temas) e importes en euros, como número. "
    "5) Si las bases son de varias plazas distintas, los datos son los de la primera y «denominacion» es la lista. "
    "6) Si el texto no son unas bases ni una convocatoria, devuelve {\"no_son_bases\":true}."
)


_EN_EL_ANUNCIO: dict[str, dict[str, str]] = {}  # BOJA y BOA: el texto va en el propio anuncio (oposiciones/)


def texto_anuncio(raiz: Path, fuente: str, xid: str, fecha: str) -> str | None:
    """Texto guardado de un anuncio: del BOE (datos/boe/textos), de un boletín (textos/) o, en BOJA y BOA, del propio
    registro del anuncio."""
    if fuente == "boe":
        from motor.boe.texto import ruta_texto
        r = ruta_texto(raiz, xid, fecha)
        try:
            return json.loads(r.read_text(encoding="utf-8")).get("texto") if r.exists() else None
        except ValueError:
            return None
    t = texto_de(raiz, fuente, {"id": xid, "fecha": fecha})
    if t or fuente not in ("boja", "boa"):
        return t
    if fuente not in _EN_EL_ANUNCIO:
        from motor.autonomicos.actos import _base
        _EN_EL_ANUNCIO[fuente] = {}
        for f in (_base(raiz, fuente) / "oposiciones").rglob("*.jsonl"):
            for l in f.open(encoding="utf-8"):
                if '"texto": "' in l:
                    x = json.loads(l)
                    _EN_EL_ANUNCIO[fuente][str(x.get("id"))] = x.get("texto")
    return _EN_EL_ANUNCIO[fuente].get(xid)


def _documento(raiz: Path, p: dict) -> dict | None:
    """El texto de las bases del proceso: {id, fuente, url, fecha, texto}; None si no lo hay."""
    for o in p.get("otras_publicaciones") or []:
        titulo = (o.get("titulo") or "").lower()
        if o.get("tipo") not in ("convocatoria", "bases") or not o.get("tiene_texto") or \
                re.match(r"\W*(correcci|rectific|modific|anuncio de correcci)", titulo):
            continue
        fuente, _, xid = o["id"].partition(":")
        t = texto_anuncio(raiz, fuente, xid, o["fecha"])
        if t and len(t) > 800:
            return {"id": o["id"], "fuente": o.get("fuente"), "url": o.get("url"), "fecha": o["fecha"], "texto": t}
    fuente, _, xid = (p.get("id") or "").partition(":")
    if fuente == "boe" and p.get("ambito") == "local":
        return None  # el BOE solo trae el extracto de las bases locales
    origen = next((a for a in p.get("actos") or [] if a.get("id") in (xid, p.get("id"))), None)
    if not origen:
        return None
    t = texto_anuncio(raiz, fuente, xid, origen["fecha"])
    if t and len(t) > 800:
        return {"id": p["id"], "fuente": origen.get("fuente"), "url": origen.get("url"), "fecha": origen["fecha"],
                "texto": t}
    return None


def recortar(texto: str) -> str:
    if len(texto) <= MAX_CARACTERES:
        return texto
    return texto[:int(MAX_CARACTERES * 0.7)] + "\n[…]\n" + texto[-int(MAX_CARACTERES * 0.3):]


def huella(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def nombre_fichero(proceso_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", proceso_id)


def ruta_resultado(raiz: Path, p: dict) -> Path:
    anio = (p.get("apertura_plazo") or p.get("fecha") or next((a.get("fecha") for a in p.get("actos") or []), "")
            or "0000")[:4]
    return raiz / "datos" / "oposiciones" / "extraccion" / anio / f"{nombre_fichero(p['id'])}.json"


def ya_extraido(raiz: Path, p: dict, h: str) -> bool:
    r = ruta_resultado(raiz, p)
    try:
        return r.exists() and json.loads(r.read_text(encoding="utf-8")).get("documento", {}).get("huella") == h
    except ValueError:
        return False


def retirar_caducados(raiz: Path) -> int:
    """Borra los resultados cuyo texto de origen ya no es el mismo (se rehízo o pasó a «sin texto» por dudoso): son
    datos derivados y se vuelven a extraer del texto nuevo, si lo hay."""
    n = 0
    for f in (raiz / "datos" / "oposiciones" / "extraccion").glob("[0-9]*/*.json"):
        try:
            doc = json.loads(f.read_text(encoding="utf-8")).get("documento") or {}
        except ValueError:
            continue
        if doc.get("huella") and _texto_documento(raiz, {"documento": doc}) is None:
            f.unlink()
            n += 1
    return n


def elegir(raiz: Path, n: int, estados: set[str]) -> list[tuple[dict, dict]]:
    """Procesos de esos estados, los más recientes primero, con texto de bases y sin extraer con ese texto."""
    procesos = []
    for f in sorted((raiz / "datos" / "oposiciones" / "procesos").glob("*.jsonl"), reverse=True):
        for l in f.open(encoding="utf-8"):
            p = json.loads(l)
            if not estados or p.get("estado") in estados:
                procesos.append(p)
    procesos.sort(key=lambda p: p.get("apertura_plazo") or "", reverse=True)
    out = []
    for p in procesos:
        doc = _documento(raiz, p)
        if not doc:
            continue
        doc["huella"] = huella(doc["texto"])
        if ya_extraido(raiz, p, doc["huella"]):
            continue
        out.append((p, doc))
        if len(out) >= n:
            break
    return out


def peticion(custom_id: str, doc: dict) -> dict:
    esquema = "\n".join(f"- {k}: {v}" for k, v in CAMPOS.items())
    return {"custom_id": custom_id, "params": {
        "model": MODELO, "max_tokens": MAX_TOKENS, "thinking": {"type": "disabled"},
        "output_config": {"effort": "low"},
        "system": [{"type": "text", "text": SISTEMA + "\nCampos:\n" + esquema, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": f"Fuente: {doc.get('fuente')} {doc.get('url') or ''}\n\nTEXTO:\n"
                                                 f"{recortar(doc['texto'])}"}]}}


def verificar(respuesta: dict, texto: str) -> tuple[dict, dict]:
    """(aceptados, rechazados): un valor se acepta solo si su cita está en el texto y, si es un número, sale de ella."""
    base = ex._norma(texto)
    laxa = None
    aceptados, rechazados = {}, {}
    for campo in CAMPOS:
        dato = respuesta.get(campo)
        if not isinstance(dato, dict) or dato.get("v") in (None, "", []):
            continue
        valor, cita = dato.get("v"), str(dato.get("c") or "")
        nivel = None
        if len(cita.split()) >= 2:
            if ex.cita_en_texto(cita, base):
                nivel = "literal"
            else:
                laxa = ex._laxa(base) if laxa is None else laxa
                nivel = ex.nivel_cita(cita, base, laxa)
        if nivel is None:
            rechazados[campo] = {"motivo": "cita_no_literal", "valor": valor, "cita": cita}
            continue
        if campo in NUMERICOS:
            num = ex.como_numero(valor)
            if num is None:
                rechazados[campo] = {"motivo": "valor_no_numerico", "valor": valor, "cita": cita}
                continue
            if not ex.numero_en_cita(num, cita) and not _numero_en_letra(num, cita):
                rechazados[campo] = {"motivo": "valor_no_en_cita", "valor": valor, "cita": cita}
                continue
            valor = num
        aceptados[campo] = {"valor": valor, "cita": cita, "nivel": nivel}
    if "temas" not in aceptados and (contados := temas_contados(texto)):
        aceptados["temas"] = contados
        rechazados.pop("temas", None)
    return aceptados, rechazados


RE_TEMA = re.compile(r"(?im)^\s*(?:tema|gaia)\s*(?:n[úu]m\.?|n\.?\s?º)?\s*(\d{1,3})\s*[.\-:–ºª)]")


def temas_contados(texto: str) -> dict | None:
    """Número de temas contando los «Tema 1.», «Tema 2.»… del temario (sin IA): el último de una serie que empieza en
    1 y en la que están casi todos; la cita es la línea del último tema."""
    nums = [(int(m.group(1)), m.start()) for m in RE_TEMA.finditer(texto or "")]
    vistos = {n for n, _ in nums}
    if 1 not in vistos:
        return None
    n = 1
    while n + 1 in vistos or (n + 2 in vistos and n + 3 in vistos):
        n += 1
    if n < 3 or len({k for k in vistos if k <= n}) < 0.8 * n:
        return None
    pos = max(p for k, p in nums if k == n)
    linea = " ".join(texto[pos:pos + 200].split("\n", 1)[0].split())
    return {"valor": n, "cita": linea[:160], "nivel": "contado"}


UNIDADES = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
            "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16,
            "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiun": 21, "veintiuno": 21,
            "veintiuna": 21, "veintidos": 22, "veintitres": 23, "veinticuatro": 24, "veinticinco": 25,
            "veintiseis": 26, "veintisiete": 27, "veintiocho": 28, "veintinueve": 29,
            # catalán, valenciano y gallego
            "dues": 2, "duas": 2, "tres": 3, "quatre": 4, "cinc": 5, "sis": 6, "set": 7, "vuit": 8, "huit": 8,
            "nou": 9, "deu": 10, "onze": 11, "dotze": 12, "tretze": 13, "catorze": 14, "quinze": 15, "vint": 20,
            "vinte": 20, "unha": 1}
DECENAS = {"treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90,
           "trenta": 30, "quaranta": 40, "cinquanta": 50, "seixanta": 60, "setanta": 70, "vuitanta": 80,
           "noranta": 90, "trinta": 30, "corenta": 40, "cincuenta": 50, "sesenta": 60}
CENTENAS = {"cien": 100, "ciento": 100, "doscientos": 200, "doscientas": 200, "trescientos": 300, "trescientas": 300,
            "cuatrocientos": 400, "cuatrocientas": 400, "quinientos": 500, "quinientas": 500, "cent": 100}


def numeros_en_letra(texto: str) -> set[int]:
    """Números escritos con letra en un texto: «dos plazas», «noventa temas», «ciento veinte», «treinta y dos»."""
    import unicodedata
    t = "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower()) if unicodedata.category(c) != "Mn")
    palabras = re.findall(r"[a-zñ]+", t)
    out, actual, k = set(), None, 0
    while k < len(palabras):
        w = palabras[k]
        if w in CENTENAS:
            actual = (actual or 0) + CENTENAS[w]
        elif w in DECENAS:
            actual = (actual or 0) + DECENAS[w]
        elif w in UNIDADES and (actual is None or actual % 10 == 0):
            actual = (actual or 0) + UNIDADES[w]
        elif w in ("y", "i", "e") and actual is not None and k + 1 < len(palabras) and palabras[k + 1] in UNIDADES:
            pass
        else:
            if actual is not None:
                out.add(actual)
                actual = None
                if w in UNIDADES:
                    continue  # otro número que empieza aquí («treinta y dos, dues»)
        k += 1
    if actual is not None:
        out.add(actual)
    return out


def _numero_en_letra(num, cita: str) -> bool:
    """El número escrito con letra en la cita."""
    return num in numeros_en_letra(cita)


def _api(metodo: str, url: str, **kw) -> requests.Response:
    r = requests.request(metodo, url, headers=ex._cabeceras(), timeout=kw.pop("timeout", 120), **kw)
    if r.status_code >= 400:
        sys.exit(f"API {r.status_code}: {r.text[:800]}")  # el cuerpo del error nunca lleva la clave
    return r


def coste(uso: dict) -> float:
    return sum(uso.get(k, 0) * p for k, p in PRECIO.items()) / 1_000_000


def _respuesta_json(crudo: str) -> dict | None:
    s = crudo.strip()
    if s.startswith("```"):
        s = re.sub(r"^```\w*\s*|\s*```$", "", s)
    try:
        d = json.loads(s)
    except ValueError:
        m = re.search(r"\{.*\}", s, re.S)
        try:
            d = json.loads(m.group(0)) if m else None
        except ValueError:
            d = None
    return d if isinstance(d, dict) else None


def preparar(raiz: Path, n: int, estados: set[str], carpeta: Path) -> tuple[Path, Path]:
    elegidos = elegir(raiz, n, estados)
    carpeta.mkdir(parents=True, exist_ok=True)
    lote, indice = carpeta / "lote.jsonl", carpeta / "indice.json"
    filas, info = [], {}
    for k, (p, doc) in enumerate(elegidos):
        cid = f"p{k:05d}"
        filas.append(json.dumps(peticion(cid, doc), ensure_ascii=False))
        info[cid] = {"proceso": p["id"], "ruta": str(ruta_resultado(raiz, p).relative_to(raiz)),
                     "documento": {k2: doc[k2] for k2 in ("id", "fuente", "url", "fecha", "huella")}}
    lote.write_text("\n".join(filas) + ("\n" if filas else ""), encoding="utf-8")
    indice.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Lote con {len(filas)} procesos")
    return lote, indice


def recoger(raiz: Path, b: dict, indice: dict, salida: Path) -> dict:
    """Comprueba cada respuesta contra su texto y escribe un resultado por proceso; devuelve el resumen del lote."""
    r = _api("GET", b["results_url"], timeout=300)
    uso_total = {k: 0 for k in PRECIO}
    aceptados = rechazados = no_bases = errores = 0
    por_campo: dict[str, int] = {}
    textos = {}
    for linea in r.text.splitlines():
        if not linea.strip():
            continue
        x = json.loads(linea)
        info = indice.get(x.get("custom_id"))
        if not info:
            continue
        res = x.get("result") or {}
        if res.get("type") != "succeeded":
            errores += 1
            continue
        msg = res.get("message") or {}
        for k in PRECIO:
            uso_total[k] += (msg.get("usage") or {}).get(k, 0) or 0
        crudo = "".join(c.get("text", "") for c in msg.get("content") or [] if c.get("type") == "text")
        d = _respuesta_json(crudo)
        if d is None:
            errores += 1
            continue
        if d.get("no_son_bases"):
            no_bases += 1
        if info["documento"]["id"] not in textos:
            textos[info["documento"]["id"]] = _texto_documento(raiz, info)
        texto = textos[info["documento"]["id"]] or ""
        acept, rech = verificar(d, texto) if texto else ({}, {})
        aceptados += len(acept)
        rechazados += len(rech)
        for c in acept:
            por_campo[c] = por_campo.get(c, 0) + 1
        destino = salida / info["ruta"]
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps({
            "proceso": info["proceso"], "documento": info["documento"], "modelo": MODELO,
            "extraido": datetime.now(timezone.utc).isoformat(timespec="seconds"), "lote": b.get("id"),
            "no_son_bases": bool(d.get("no_son_bases")), "campos": acept, "rechazados": rech,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
    resumen = {"lote": b.get("id"), "estado": b.get("processing_status"), "resultados": b.get("request_counts"),
               "tokens": uso_total, "coste_usd": round(coste(uso_total), 6),
               "procesos": len(indice), "campos_aceptados": aceptados, "campos_rechazados": rechazados,
               "aceptados_por_campo": dict(sorted(por_campo.items(), key=lambda kv: -kv[1])),
               "no_son_bases": no_bases, "errores": errores, "modelo": MODELO,
               "precios": "https://platform.claude.com/docs/en/about-claude/pricing (30/10/2026)"}
    if resumen["procesos"]:
        resumen["coste_por_proceso_usd"] = round(resumen["coste_usd"] / resumen["procesos"], 6)
    return resumen


def _texto_documento(raiz: Path, info: dict) -> str | None:
    """El mismo texto que se envió (comprobado por su huella), leído otra vez de la copia de la rama de datos."""
    doc = info["documento"]
    fuente, _, xid = doc["id"].partition(":")
    t = texto_anuncio(raiz, fuente, xid, doc.get("fecha") or "")
    return t if t and huella(t) == doc["huella"] else None


def esperar(batch_id: str, minutos: float) -> dict:
    fin = time.time() + minutos * 60
    while True:
        b = _api("GET", f"{API}/{batch_id}", timeout=60).json()
        print(f"{datetime.now(timezone.utc):%H:%M:%S} {b.get('processing_status')} {b.get('request_counts')}")
        if b.get("processing_status") == "ended" or time.time() > fin:
            return b
        time.sleep(30)


def _guardar_resumen(salida: Path, resumen: dict) -> None:
    d = salida / "datos" / "oposiciones" / "extraccion" / "lotes"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.json").write_text(
        json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    print("::notice title=Extracción de bases::" + json.dumps(
        {k: resumen.get(k) for k in ("lote", "estado", "procesos", "coste_usd", "coste_por_proceso_usd",
                                     "campos_aceptados", "campos_rechazados", "no_son_bases", "errores")},
        ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("orden", choices=["lote", "retomar", "preparar"])
    p.add_argument("--datos", type=Path, required=True, help="copia de la rama de datos")
    p.add_argument("--salida", type=Path, required=True, help="dónde se escriben los resultados (la misma copia)")
    p.add_argument("--n", type=int, default=40)
    p.add_argument("--estados", default="plazo_abierto")
    p.add_argument("--esperar-min", type=float, default=50)
    p.add_argument("--lote-json", type=Path)
    p.add_argument("--trabajo", type=Path, default=Path("extraccion-bases"),
                   help="lote enviado e índice (fuera de la rama de datos)")
    a = p.parse_args(argv)
    trabajo = a.trabajo
    lotes = a.salida / "datos" / "oposiciones" / "extraccion" / "lotes"
    if a.orden in ("lote", "preparar"):
        if a.orden == "lote":
            print(f"Resultados retirados porque su texto cambió: {retirar_caducados(a.datos)}")
        lote, ruta_indice = preparar(a.datos, a.n, {e for e in a.estados.split(",") if e}, trabajo)
        if a.orden == "preparar" or not lote.read_text(encoding="utf-8").strip():
            return 0
        reqs = [json.loads(l) for l in lote.read_text(encoding="utf-8").splitlines() if l.strip()]
        b = _api("POST", API, json={"requests": reqs}).json()
        indice = json.loads(ruta_indice.read_text(encoding="utf-8"))
        # Si no termina a tiempo, se retoma con este fichero (solo ids, rutas y huellas; ningún texto)
        lotes.mkdir(parents=True, exist_ok=True)
        pendiente = lotes / f"pendiente-{b['id']}.json"
        pendiente.write_text(json.dumps({"id": b["id"], "indice": indice}, ensure_ascii=False), encoding="utf-8")
        print(f"Lote enviado: {b['id']}")
        b = esperar(b["id"], a.esperar_min)
    else:
        pendiente = a.lote_json
        info = json.loads(pendiente.read_text(encoding="utf-8"))
        indice = info["indice"]
        b = esperar(info["id"], a.esperar_min)
    if b.get("processing_status") != "ended":
        print(f"::warning title=Extracción de bases::el lote {b.get('id')} no ha terminado; se retoma con "
              f"--lote-json {pendiente}")
        return 0
    resumen = recoger(a.datos, b, indice, a.salida)
    _guardar_resumen(a.salida, resumen)
    pendiente.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
