"""Guías docentes de los másteres oficiales: evaluación (con sus porcentajes) y metodología de cada asignatura.

La guía docente es pública y obligatoria antes de la matrícula (RD 822/2021, art. 9.3) y es la fuente de la
evaluación por asignatura cuando la memoria del RUCT no la trae (formato RD 822/2021) o aún no se ha leído
(docs/fuentes-guias-docentes.md). Aquí, sin conectores por universidad:

1. descubrir: en las páginas de máster oficial ya leídas (originales del almacén privado) se recogen los enlaces
   a guías docentes (PDF o HTML) por su enlace o su texto («guía docente», «guia docent», «teaching guide»,
   SIGMA DOA, «guiasdocentes»…), del mismo centro, como mucho MAX_POR_MASTER por máster;
2. lote: se piden con el lector cortés (robots.txt, una petición por segundo y servidor); el original va al
   almacén privado; Claude Haiku, con salida estructurada, devuelve la asignatura, sus créditos y cada sistema
   de evaluación con su porcentaje y una frase literal; sin IA se comprueba que la frase está en el texto y que el
   porcentaje sale de ella. Ni nombres de profesores ni correos: el esquema no los pide y no se guardan.

Lo público: URL de la guía, código RUCT, asignatura, créditos, sistemas con porcentaje, metodología, huellas.
Nunca el texto ni las citas.

Uso:
  python -m motor.estudios.guias descubrir --capturadas carpeta [--capturadas …] --salida ruta/
  python -m motor.estudios.guias lote --guias ruta/…/guias_descubiertas.jsonl [--desde 0 --hasta 4000] --salida ruta/
  python -m motor.estudios.guias retomar --lote-json ruta/…/lote.json --salida ruta/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

from motor.estudios import extraer, tarifas

MAX_POR_MASTER = 12
MAX_CARACTERES = 40_000
MAX_TOKENS = 4000

RE_ENLACE = re.compile(r"""(?is)<a\b[^>]*href\s*=\s*["']([^"'#]+)["'][^>]*>(.*?)</a>""")
# por el enlace o por su texto
GUIA = re.compile(r"(?i)gu[ií]a[s]?[\s_-]*docent|guies[\s_-]*docents|guia[\s_-]*docent|teaching[\s_-]*guide|"
                  r"course[\s_-]*guide|guiadocente|guiasdocentes|guias_docentes|guies/public|pladocent|"
                  r"/doa/consultaPublica|comun_gauss/publico/guias|fatwirepub/guias|guiasdocentes-api|pdfGuia|"
                  r"generaFicha|estudispdf/guia|syllabus|programa[\s_-]+de[\s_-]+la[\s_-]+asignatura|ficha[\s_-]+de[\s_-]+la[\s_-]+asignatura")
NO_GUIA = re.compile(r"(?i)normativa|reglamento|calendario|horario|tfm[-_ ]?gu[ií]a|gu[ií]a[-_ ]?(del?[-_ ]?)?(tfm|estudiante|"
                     r"alumno|matr[ií]cula|pr[aá]cticas|acogida|admisi)|plantilla|modelo")

SISTEMA = (
    "Lees el texto de una guía docente (programa) de una asignatura de un máster universitario. Si no es la guía de "
    "una asignatura concreta, es_guia=false y el resto vacío. Si lo es, devuelve: asignatura (nombre tal cual), "
    "creditos (número tal cual o vacío), curso_academico (p. ej. 2025-2026, o vacío), evaluacion: cada sistema o "
    "prueba de evaluación con su peso (porcentaje tal cual: «40», «40 %», «30-50»), y una cita copiada exactamente "
    "del texto que contiene ese sistema y su peso (de 3 a 30 palabras); metodologia: hasta 8 métodos o actividades "
    "formativas, nombre corto tal cual. Nunca nombres de personas, correos ni teléfonos. Solo lo que dice el texto.")
ESQUEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["es_guia", "asignatura", "creditos", "curso_academico", "evaluacion", "metodologia"],
    "properties": {
        "es_guia": {"type": "boolean"},
        "asignatura": {"type": "string"},
        "creditos": {"type": "string"},
        "curso_academico": {"type": "string"},
        "evaluacion": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["sistema", "peso", "cita"],
            "properties": {"sistema": {"type": "string"}, "peso": {"type": "string"}, "cita": {"type": "string"}}}},
        "metodologia": {"type": "array", "items": {"type": "string"}},
    },
}
RE_PORCENTAJE = re.compile(r"(?<![\d.,])(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:%|por\s*ciento|percent)", re.I)
RE_RANGO_PORCENTAJE = re.compile(r"(?<![\d.,])(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:%\s*)?(?:-|–|a|y|al)\s*\d{1,3}(?:[.,]\d{1,2})?\s*(?:%|por\s*ciento)", re.I)


def porcentaje_en_cita(v: float, cita: str) -> bool:
    """El peso sale de la cita como porcentaje («40 %», «40%», «40 por ciento», o el primero de «30-50 %»): «test
    de 40 preguntas: 60 %» da 60, no 40; «mínimo 5 sobre 10» no da nada."""
    nums = [float(x.replace(",", ".")) for x in RE_PORCENTAJE.findall(cita or "")]
    nums += [float(x.replace(",", ".")) for x in RE_RANGO_PORCENTAJE.findall(cita or "")]
    return any(abs(v - n) < 0.005 for n in nums)


RE_PESO = re.compile(r"^\s*(\d{1,3}(?:[.,]\d+)?)\s*%?\s*(?:[-–a]\s*(\d{1,3}(?:[.,]\d+)?)\s*%?)?\s*$")


def peso(texto: str) -> tuple[float | None, float | None]:
    """«40», «40 %», «30-50 %», «30 a 50» → (mínimo, máximo); lo demás → (None, None)."""
    m = RE_PESO.match(str(texto or ""))
    if not m:
        return None, None
    a = float(m.group(1).replace(",", "."))
    b = float(m.group(2).replace(",", ".")) if m.group(2) else a
    if not (0 <= a <= 100 and 0 <= b <= 100) or b < a:
        return None, None
    return a, b


# ------------------------------------------------------------------------------------------ descubrir


def enlaces_de_guia(html: str, url: str) -> list[str]:
    from html import unescape
    from urllib.parse import urljoin, urlparse

    from motor.estudios.censo import dominio_registrado

    propio = dominio_registrado(urlparse(url).netloc)
    out = []
    for href, texto in RE_ENLACE.findall(html or ""):
        href = unescape(href.strip())
        if href.lower().startswith(("mailto:", "tel:", "javascript:")):
            continue
        texto = re.sub(r"<[^>]+>", " ", texto)
        if not (GUIA.search(href) or GUIA.search(texto)) or NO_GUIA.search(href + " " + texto):
            continue
        u = urljoin(url, href)
        pu = urlparse(u)
        if "/." in pu.path:  # «/content/../master/…»: la ruta normalizada (robots.txt mira la ruta real)
            import posixpath

            u = pu._replace(path=posixpath.normpath(pu.path)).geturl()
        if dominio_registrado(urlparse(u).netloc) == propio and u not in out:
            out.append(u)
    return out


def descubrir(capturadas: list[Path], salida: Path, hilos: int = 16) -> dict:
    """Las guías enlazadas desde las páginas de máster oficial ya leídas (con su código RUCT)."""
    from concurrent.futures import ThreadPoolExecutor

    claves, meta = {}, {}
    for c in capturadas:
        for f in sorted(c.rglob("paginas_capturadas.jsonl")):
            for x in tarifas_jsonl(f):
                if (x.get("clave") or "").endswith(".html.gz"):
                    claves[x["url"]] = x["clave"]
        for f in sorted(c.rglob("paginas_extraidas.jsonl")):
            for x in tarifas_jsonl(f):
                if x.get("grupo") == "oficial" and not x.get("no_es_programa"):
                    meta[x["url"]] = sorted(set(meta.get(x["url"], [])) | set(x.get("codigos_ruct") or []))
    guarda = extraer.Guarda()
    if not guarda.activa:
        return {"error": "sin almacén privado"}
    trabajo = [(u, claves[u]) for u in sorted(meta) if u in claves]

    def uno(kv):
        url, clave = kv
        try:
            return url, enlaces_de_guia(guarda.almacen.leer(clave).decode("utf-8", "replace"), url)
        except Exception:  # noqa: BLE001
            return url, []

    por_master: dict[str, list[str]] = defaultdict(list)
    cuentas = Counter()
    with ThreadPoolExecutor(max_workers=hilos) as ex:
        for url, guias in ex.map(uno, trabajo):
            cuentas["paginas"] += 1
            cuentas["paginas_con_guias"] += bool(guias)
            for cod in meta[url]:
                for g in guias:
                    if g not in por_master[cod]:
                        por_master[cod].append(g)
    filas = []
    for cod, gs in sorted(por_master.items()):
        cuentas["masters_con_guias"] += 1
        cuentas["guias_encontradas"] += len(gs)
        filas += [{"url": g, "codigo_ruct": cod} for g in gs[:MAX_POR_MASTER]]
    # una guía que cuelga de varios másters (asignatura compartida) se pide una vez
    por_url: dict[str, dict] = {}
    for f in filas:
        por_url.setdefault(f["url"], {"url": f["url"], "codigos_ruct": []})["codigos_ruct"].append(f["codigo_ruct"])
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "guias_descubiertas.jsonl").write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in por_url.values()),
                                                     encoding="utf-8")
    return {**cuentas, "guias_a_pedir": len(por_url)}


def tarifas_jsonl(f: Path) -> list[dict]:
    return [json.loads(l) for l in f.read_text(encoding="utf-8").split("\n") if l.strip()]


# ---------------------------------------------------------------------------------------------- lote


def capturar(filas: list[dict], guarda: extraer.Guarda, hilos: int, fin: float, navegador: bool = False) -> list[dict]:
    """PDF con el capturador de tarifas; HTML con el de la extracción (y su texto sin menús ni nombres)."""
    pdf = [f for f in filas if re.search(r"(?i)\.pdf(\?|$)|pdfGuia|/pdf\b|estudispdf", f["url"])]
    html = [f for f in filas if f not in pdf]
    out = tarifas.capturar_pdfs([{**f, "dominio": None, "proveedor": None} for f in pdf], guarda, hilos=hilos, fin=fin) if pdf else []
    if html:
        por_url = {f["url"]: f for f in html}
        # SIGMA DOA y otras plataformas pintan la guía con JavaScript: con --navegador, Chromium (sin pasar antibots)
        for p in extraer.capturar(list(por_url), hilos=hilos, guarda=guarda, fin=fin, navegador=navegador):
            g = {**por_url[p["url"]], **{k: v for k, v in p.items() if k != "texto"}}
            if p.get("texto"):
                g["texto"] = p["texto"]
            out.append(g)
    return out


def peticion(cid: str, url: str, texto: str) -> dict:
    return {"custom_id": cid, "params": {
        "model": extraer.MODELO, "max_tokens": MAX_TOKENS,
        "system": [{"type": "text", "text": SISTEMA, "cache_control": {"type": "ephemeral"}}],
        "thinking": extraer.PENSAMIENTO,
        "output_config": {"effort": extraer.ESFUERZO, "format": {"type": "json_schema", "schema": ESQUEMA}},
        "messages": [{"role": "user", "content": f"URL: {url}\n\nTexto de la guía:\n{texto[:MAX_CARACTERES]}"}]}}


def verificar(datos: dict, texto: str) -> dict:
    """Solo quedan los sistemas cuya cita está en el texto y cuyo peso sale de ella."""
    base = extraer._norma(texto)
    laxa = extraer._laxa(base)
    sistemas, cuentas = [], Counter()
    for x in (datos.get("evaluacion") or [])[:20]:
        cita = str(x.get("cita") or "")
        a, b = peso(x.get("peso"))
        nivel = extraer.nivel_cita(cita, base, laxa) if len(cita.split()) >= 2 else None
        if nivel is None:
            cuentas["cita_no_literal"] += 1
            continue
        if a is None or not all(porcentaje_en_cita(v, cita) for v in {a, b}):
            cuentas["peso_no_en_cita"] += 1
            continue
        sistemas.append({"sistema": str(x.get("sistema") or "")[:160], "min": a, "max": b, "cita_nivel": nivel,
                         "cita_sha256": hashlib.sha256(extraer._norma(cita).encode()).hexdigest()})
        cuentas["sistemas_aceptados"] += 1
    total = sum(s["max"] for s in sistemas)
    return {"asignatura": str(datos.get("asignatura") or "")[:200],
            "creditos": extraer.como_numero(datos.get("creditos")),
            "curso_academico": str(datos.get("curso_academico") or "")[:20],
            "evaluacion": sistemas,
            # pesos fijos que suman 100: la evaluación está entera
            "evaluacion_completa": bool(sistemas) and all(s["min"] == s["max"] for s in sistemas) and abs(total - 100) < 0.5,
            "metodologia": [str(m)[:120] for m in (datos.get("metodologia") or [])[:8] if m],
            "cuentas": dict(cuentas)}


def lote(guias: Path, salida: Path, desde: int = 0, hasta: int | None = None, esperar_min: float = 40,
         max_minutos: float = 55, hilos: int = 16, guarda: extraer.Guarda | None = None, navegador: bool = False) -> dict:
    t0 = time.time()
    guarda = guarda if guarda is not None else extraer.Guarda()
    filas = tarifas_jsonl(guias)[desde:hasta]
    capt = capturar(filas, guarda, hilos, t0 + (max_minutos - 18) * 60, navegador)
    salida.mkdir(parents=True, exist_ok=True)
    peticiones, por_id, enviado, cuentas = [], {}, [], Counter()
    with (salida / "guias_capturadas.jsonl").open("w", encoding="utf-8") as f:
        for c in capt:
            texto = c.pop("texto", None)
            cuentas["pedidas"] += 1
            if not texto:
                cuentas[c.get("motivo") or "sin_texto"] += 1
            elif len(texto) < 300 or not re.search(r"\d\s*%|\d{2}\s*por\s*ciento", texto):
                cuentas["sin_porcentajes"] += 1  # sin un solo porcentaje no hay evaluación que leer
                c["motivo"] = "sin_porcentajes"
            else:
                cid = "g" + hashlib.sha256((c["url"] + (c.get("sha256") or "")).encode()).hexdigest()[:24]
                por_id[cid] = (c, texto)
                peticiones.append(peticion(cid, c["url"], texto))
                enviado.append({"custom_id": cid, "url": c["url"], "sha256": c.get("sha256"), "texto": texto,
                                "codigos_ruct": c.get("codigos_ruct")})
                cuentas["enviadas"] += 1
            f.write(json.dumps({k: v for k, v in c.items() if k != "html"}, ensure_ascii=False) + "\n")
    if not peticiones:
        (salida / "resumen.json").write_text(json.dumps(dict(cuentas), ensure_ascii=False, indent=1), encoding="utf-8")
        return dict(cuentas)
    r = requests.post(extraer.API, headers=extraer._cabeceras(), json={"requests": peticiones}, timeout=300)
    if r.status_code >= 400:
        return {**cuentas, "error_api": r.status_code, "detalle": r.text[:500]}
    b = r.json()
    clave = guarda.jsonl(extraer.FUENTE_EXTRACCION, enviado, "guias-enviado.jsonl", f"anthropic-batch:{b['id']}/guias")
    (salida / "lote.json").write_text(json.dumps({"id": b["id"], "clave_enviado": clave}), encoding="utf-8")
    fin = min(t0 + max_minutos * 60, time.time() + esperar_min * 60)
    while b.get("processing_status") != "ended" and time.time() < fin:
        time.sleep(30)
        b = requests.get(f"{extraer.API}/{b['id']}", headers=extraer._cabeceras(), timeout=60).json()
    if b.get("processing_status") != "ended":
        res = {**cuentas, "estado_lote": b.get("processing_status"), "id": b["id"],
               "siguiente": "guias retomar con lote.json de esta ejecución"}
        (salida / "resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        return res
    return procesar(b, por_id, salida, guarda, cuentas)


def procesar(b: dict, por_id: dict, salida: Path, guarda: extraer.Guarda, cuentas: Counter) -> dict:
    res = requests.get(b["results_url"], headers=extraer._cabeceras(), timeout=600)
    if guarda.activa:
        guarda.original(extraer.FUENTE_EXTRACCION, res.content, "guias-resultados.jsonl",
                        f"anthropic-batch:{b['id']}/guias-resultados")
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    dolares = 0.0
    salida.mkdir(parents=True, exist_ok=True)
    with (salida / "guias.jsonl").open("w", encoding="utf-8") as fo:
        for linea in res.text.split("\n"):
            if not linea.strip():
                continue
            x = json.loads(linea)
            if x["result"]["type"] != "succeeded" or x["custom_id"] not in por_id:
                cuentas["resultado_" + x["result"]["type"]] += 1
                continue
            msg = x["result"]["message"]
            dolares += extraer.coste(msg.get("usage", {}))
            c, texto = por_id[x["custom_id"]]
            datos = extraer._json_de("".join(k.get("text", "") for k in msg["content"] if k.get("type") == "text"))
            if not datos.get("es_guia"):
                cuentas["no_es_guia"] += 1
                continue
            try:
                v = verificar(datos, texto)
            except Exception as e:  # noqa: BLE001 - un documento raro no tira la tanda ya pagada
                cuentas["error_" + type(e).__name__] += 1
                continue
            for k, n in v.pop("cuentas").items():
                cuentas[k] += n
            cuentas["guias"] += 1
            cuentas["guias_con_evaluacion"] += bool(v["evaluacion"])
            cuentas["guias_con_evaluacion_completa"] += v["evaluacion_completa"]
            fo.write(json.dumps({**v, "url": c["url"], "codigos_ruct": c.get("codigos_ruct"), "captura_sha256": c.get("sha256"),
                                 "extraido": ahora, "modelo": extraer.MODELO, "lote": b["id"]}, ensure_ascii=False) + "\n")
    resumen = {**cuentas, "id": b["id"], "coste_usd": round(dolares, 6), "almacen": dict(guarda.cuentas)}
    (salida / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    return resumen


def retomar(lote_json: Path, salida: Path, esperar_min: float = 30) -> dict:
    guarda = extraer.Guarda()
    info = json.loads(lote_json.read_text(encoding="utf-8"))
    por_id = {e["custom_id"]: ({"url": e["url"], "sha256": e.get("sha256"), "codigos_ruct": e.get("codigos_ruct")}, e["texto"])
              for e in guarda.leer_jsonl(info["clave_enviado"])}
    b = requests.get(f"{extraer.API}/{info['id']}", headers=extraer._cabeceras(), timeout=60).json()
    fin = time.time() + esperar_min * 60
    while b.get("processing_status") != "ended" and time.time() < fin:
        time.sleep(30)
        b = requests.get(f"{extraer.API}/{info['id']}", headers=extraer._cabeceras(), timeout=60).json()
    if b.get("processing_status") != "ended":
        return {"estado_lote": b.get("processing_status"), "id": info["id"]}
    return procesar(b, por_id, salida, guarda, Counter({"retomado": 1}))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("orden", choices=["descubrir", "lote", "retomar"])
    p.add_argument("--capturadas", action="append", default=[])
    p.add_argument("--guias")
    p.add_argument("--desde", type=int, default=0)
    p.add_argument("--hasta", type=int)
    p.add_argument("--lote-json")
    p.add_argument("--esperar-min", type=float, default=40)
    p.add_argument("--max-minutos", type=float, default=55)
    p.add_argument("--hilos", type=int, default=16)
    p.add_argument("--navegador", action="store_true", help="lote: guías en HTML que se pintan con JavaScript")
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    base = Path(a.salida) / "datos" / "estudios" / "masters" / "guias"
    if a.orden == "descubrir":
        res = descubrir([Path(x) for x in a.capturadas], base)
    elif a.orden == "lote":
        res = lote(Path(a.guias), base / f"tramo_{a.desde}", a.desde, a.hasta, a.esperar_min, a.max_minutos, a.hilos,
                   navegador=a.navegador)
    else:
        lj = Path(a.lote_json)  # una carpeta por lote: dos retomas en la misma ejecución no se pisan
        res = retomar(lj, base / ("retomado_" + json.loads(lj.read_text(encoding="utf-8"))["id"][-16:]), a.esperar_min)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
