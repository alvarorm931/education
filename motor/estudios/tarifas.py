"""Tarifas en PDF: el precio de cada máster que el centro publica en un documento aunque la ficha lo esconda.

Muchas privadas no ponen el importe en la ficha comercial (piden el teléfono o el correo) pero publican una
tabla de precios en PDF (docs/estrategia-informacion-cerrada.md §3.2). Aquí:

1. se descargan los PDF de precios encontrados en Common Crawl (`commoncrawl.py --patron precios`) con el lector
   cortés (robots.txt de cada servidor, una petición por segundo, reserva TDM); el original va al almacén privado;
2. se extrae el texto (pypdf) y Claude Haiku, con salida estructurada, devuelve la lista de programas con su
   importe, el concepto (total, por crédito, reserva…) y la frase literal; sin IA se comprueba que la frase está
   en el PDF y que el número sale de ella;
3. cada precio se une con las fichas de máster del mismo proveedor por el nombre del programa
   (`fichas_masters.comprobar_nombre`): solo si el nombre coincide.

Lo público lleva programa, importe, concepto, curso, URL del PDF y huellas; nunca la cita.

Tablas de precios de las universidades (`--tablas`): la lista revisada a mano de las tablas (PDF o página web) que
cada universidad publica con el precio de sus másteres oficiales, en orden de reputación. Cada precio lleva la
universidad de la tabla y lo une conjunto_masters.py a sus másteres oficiales por el nombre (aunque no tengan web).

Uso:
  python -m motor.estudios.tarifas lote --pdfs precios_*.jsonl [--pdfs …] --censo proveedores.jsonl --salida ruta/
  python -m motor.estudios.tarifas lote --tablas tablas_precios.jsonl --salida ruta/
  python -m motor.estudios.tarifas unir --tarifas carpeta --fichas fichas.jsonl --salida ruta/
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

from motor.estudios import extraer

MAX_PDF = 10_000_000
MAX_CARACTERES = 80_000
POR_DOMINIO = 40  # PDF por dominio en una tanda (folletos de cada máster)
AÑO = re.compile(r"20(2[4-9]|3\d)")

SISTEMA = (
    "Lees el texto de un documento (PDF o página web) de un centro de formación. Si es una tabla o lista de precios de programas "
    "(másters, posgrados, cursos), devuelve cada programa con su importe; si no lo es, es_tarifa=false y lista "
    "vacía. Reglas: 1) solo lo que dice el texto; 2) un elemento por importe (si un programa tiene precio total y "
    "reserva, dos elementos); 3) programa: el nombre tal cual; importe: el número tal cual aparece (con sus puntos "
    "y comas); concepto: total, credito (por crédito ECTS), reserva (reserva de plaza o matrícula), mensual u otro; "
    "4) cita: frase copiada exactamente del texto que contiene el importe (y si cabe el programa), de 3 a 25 "
    "palabras; 5) curso: el curso académico del documento (p. ej. 2026-2027) o vacío; 6) como mucho 150 elementos.")
ESQUEMA = {
    "type": "object", "additionalProperties": False, "required": ["es_tarifa", "curso", "precios"],
    "properties": {
        "es_tarifa": {"type": "boolean"},
        "curso": {"type": "string"},
        "precios": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["programa", "importe", "concepto", "cita"],
            "properties": {"programa": {"type": "string"}, "importe": {"type": "string"},
                           "concepto": {"type": "string", "enum": ["total", "credito", "reserva", "mensual", "otro"]},
                           "cita": {"type": "string"}}}},
    },
}
MAX_TOKENS = 12_000


def texto_pdf(contenido: bytes) -> str:
    from pypdf import PdfReader

    try:
        paginas = PdfReader(io.BytesIO(contenido)).pages
        return "\n".join((p.extract_text() or "") for p in paginas)[:MAX_CARACTERES]
    except Exception:  # noqa: BLE001 - PDF ilegible o cifrado
        return ""


def elegir_pdfs(ficheros: list[Path], censo: Path, por_dominio: int = POR_DOMINIO) -> list[dict]:
    """Los PDF de precios de los dominios del censo (oficiales y verificados), los del curso más reciente
    primero (año en la URL), sin repetir."""
    provs = {}
    for l in censo.read_text(encoding="utf-8").split("\n"):
        if l.strip():
            p = json.loads(l)
            if p["estado"] in ("oficial", "verificado"):
                for d in p.get("dominios", [p["dominio"]]):
                    provs[d] = p
    por_dom: dict[str, set] = defaultdict(set)
    for f in ficheros:
        for l in f.read_text(encoding="utf-8").split("\n"):
            if l.strip():
                x = json.loads(l)
                if x["dominio"] in provs:
                    por_dom[x["dominio"]].update(x["urls"])

    def año(u: str) -> int:
        m = [int("20" + a) for a in AÑO.findall(u)]
        return max(m) if m else 0

    filas = []
    for d, urls in sorted(por_dom.items()):
        elegidas = sorted(urls, key=lambda u: (-año(u), len(u), u))[:por_dominio]
        filas += [{"url": u, "dominio": d, "proveedor": provs[d]["id"], "estado": provs[d]["estado"]} for u in elegidas]
    return filas


def elegir_tablas(fichero: Path) -> list[dict]:
    """Las tablas de precios revisadas (una por URL), con su universidad y el curso que dice la lista."""
    from urllib.parse import urlparse

    from motor.estudios.censo import dominio_registrado

    filas, vistas = [], set()
    for l in fichero.read_text(encoding="utf-8").split("\n"):
        if not l.strip():
            continue
        x = json.loads(l)
        u = (x.get("url") or "").strip()
        if not u.startswith("http") or u in vistas or not x.get("universidad"):
            continue
        vistas.add(u)
        filas.append({"url": u, "dominio": dominio_registrado(urlparse(u).netloc), "proveedor": None, "estado": "tabla",
                      "universidad": x["universidad"], "curso_lista": x.get("curso") or "",
                      "programa_lista": x.get("programa") or ""})
    return filas


RE_ENLACE_PDF = re.compile(r"""(?is)<a\b[^>]*href\s*=\s*["']([^"'#]+\.pdf(?:\?[^"'#]*)?)["'][^>]*>(.*?)</a>""")
TEXTO_PRECIO = re.compile(r"(?i)(tarifa|precio|preu|honorario|importe|tasas|coste|cuota|matr[ií]cula|financiaci|fees|"
                          r"tuition|folleto|brochure|dossier)")


def descubrir_en_originales(capturadas: list[Path], salida: Path, hilos: int = 16) -> dict:
    """Enlaces a PDF de precios en las páginas de programa ya leídas: se abren sus originales del almacén privado
    (las claves están en paginas_capturadas.jsonl) y se recogen los PDF cuyo enlace o nombre habla de precio,
    tarifa, matrícula o folleto. Sale en el mismo formato que commoncrawl.py --patron precios."""
    from concurrent.futures import ThreadPoolExecutor
    from html import unescape
    from urllib.parse import urljoin, urlparse

    from motor.estudios.censo import dominio_registrado

    filas = {}
    for c in capturadas:
        for f in sorted(c.rglob("paginas_capturadas.jsonl")):
            for l in f.read_text(encoding="utf-8").split("\n"):
                if l.strip():
                    x = json.loads(l)
                    if x.get("clave") and x.get("clave", "").endswith(".html.gz"):
                        filas.setdefault(x["clave"], x["url"])
    guarda = extraer.Guarda()
    if not guarda.activa:
        return {"error": "sin almacén privado"}
    cuentas: Counter = Counter()

    def uno(kv):
        clave, url = kv
        try:
            html = guarda.almacen.leer(clave).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            return url, []
        out = []
        for href, texto in RE_ENLACE_PDF.findall(html):
            href = unescape(href.strip())
            if TEXTO_PRECIO.search(href) or TEXTO_PRECIO.search(re.sub(r"<[^>]+>", " ", texto)):
                out.append(urljoin(url, href))
        return url, out

    por_dom: dict[str, set] = defaultdict(set)
    with ThreadPoolExecutor(max_workers=hilos) as ex:
        for url, pdfs in ex.map(uno, filas.items()):
            cuentas["paginas"] += 1
            for u in pdfs:
                d = dominio_registrado(urlparse(u).netloc)
                if d == dominio_registrado(urlparse(url).netloc):  # solo PDF del propio centro
                    por_dom[d].add(u)
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "precios_desde_paginas.jsonl").write_text(
        "".join(json.dumps({"dominio": d, "urls": sorted(v)}, ensure_ascii=False) + "\n" for d, v in sorted(por_dom.items())),
        encoding="utf-8")
    return {**cuentas, "dominios": len(por_dom), "pdfs": sum(len(v) for v in por_dom.values())}


def capturar_pdfs(filas: list[dict], guarda: extraer.Guarda, hilos: int = 12, fin: float | None = None) -> list[dict]:
    from concurrent.futures import ThreadPoolExecutor
    from urllib.parse import urlparse

    from motor.estudios.rastreador import Dominio

    por_host: dict[str, list[dict]] = defaultdict(list)
    for f in filas:
        por_host[urlparse(f["url"]).netloc].append(f)

    def servidor(host: str, lista: list[dict]) -> list[dict]:
        d = Dominio(f"https://{host}", None, pausa=1.0, max_peticiones=len(lista) + 6)
        out = []
        for f in lista:
            g = {**f}
            if fin is not None and time.time() > fin:
                g["motivo"] = "sin_tiempo"
                out.append(g)
                continue
            try:
                r = d.get(f["url"], timeout=40)
            except Exception as e:  # noqa: BLE001
                r, g["motivo"] = None, f"error_{type(e).__name__}"
            if r is None:
                g.setdefault("motivo", "robots_o_sin_respuesta")
            elif r.status_code == 200 and f.get("estado") == "tabla" and "html" in (r.headers.get("content-type") or "") \
                    and str(r.headers.get("tdm-reservation", "")).strip() != "1":
                # tabla de precios en una página web: su texto visible, con las tablas como «celda | celda»
                html = r.content.decode(r.encoding or "utf-8", errors="replace")
                g.update({"sha256": hashlib.sha256(r.content).hexdigest(), "bytes": len(r.content),
                          "texto": extraer.texto_de_pagina(html), "formato": "html"})
                g.update(guarda.original("web-centros", r.content, "html", f["url"]))
            elif r.status_code != 200 or not (r.content[:5] == b"%PDF-" or "pdf" in (r.headers.get("content-type") or "")):
                g.update({"motivo": "no_pdf_o_error", "estado_http": r.status_code})
            elif len(r.content) > MAX_PDF:
                g["motivo"] = "demasiado_grande"
            elif str(r.headers.get("tdm-reservation", "")).strip() == "1":
                g.update({"motivo": "reserva_tdm", "reserva_tdm": True})
            else:
                g.update({"sha256": hashlib.sha256(r.content).hexdigest(), "bytes": len(r.content),
                          "texto": texto_pdf(r.content)})
                g.update(guarda.original("web-centros", r.content, "pdf", f["url"]))
            out.append(g)
        return out

    with ThreadPoolExecutor(max_workers=hilos) as ex:
        return [x for lote_host in ex.map(lambda kv: servidor(*kv), sorted(por_host.items(), key=lambda kv: -len(kv[1])))
                for x in lote_host]


def peticion(cid: str, url: str, texto: str) -> dict:
    return {"custom_id": cid, "params": {
        "model": extraer.MODELO, "max_tokens": MAX_TOKENS,
        "system": [{"type": "text", "text": SISTEMA, "cache_control": {"type": "ephemeral"}}],
        "thinking": extraer.PENSAMIENTO,
        "output_config": {"effort": extraer.ESFUERZO, "format": {"type": "json_schema", "schema": ESQUEMA}},
        "messages": [{"role": "user", "content": f"URL: {url}\n\nTexto del documento:\n{texto}"}]}}


def verificar(datos: dict, texto: str) -> list[dict]:
    base = extraer._norma(texto)
    laxa = extraer._laxa(base)
    out = []
    for x in (datos.get("precios") or [])[:150]:
        cita = str(x.get("cita") or "")
        n = extraer.como_numero(x.get("importe"))
        # literal o con las mismas palabras y cifras en el mismo orden (las tablas web llegan como «celda | celda»)
        nivel = extraer.nivel_cita(cita, base, laxa) if len(cita.split()) >= 2 else None
        ok = nivel in ("literal", "sin_signos")
        motivo = None if ok else "cita_no_literal"
        if n is None:
            ok, motivo = False, motivo or "valor_no_numerico"
        elif ok and not extraer.numero_en_cita(n, cita):
            ok, motivo = False, "valor_no_en_cita"
        elif ok and (extraer.MONEDA_NO_EURO.search(cita) or n > extraer.PRECIO_MAXIMO):
            ok, motivo = False, "moneda_no_euro_o_fuera_de_rango"
        out.append({"programa": str(x.get("programa") or "")[:200], "importe": n if ok else None,
                    "importe_propuesto": None if ok else x.get("importe"), "concepto": x.get("concepto"),
                    "estado": "aceptado" if ok else "revision", "motivo": motivo,
                    **({"cita_nivel": nivel} if nivel and nivel != "literal" else {}),
                    "cita_sha256": hashlib.sha256(extraer._norma(cita).encode()).hexdigest() if cita else None})
    return out


def lote(pdfs: list[Path], censo: Path | None, salida: Path, esperar_min: float = 40, max_minutos: float = 52,
         hilos: int = 12, guarda: extraer.Guarda | None = None, tablas: Path | None = None) -> dict:
    t0 = time.time()
    guarda = guarda if guarda is not None else extraer.Guarda()
    filas = (elegir_pdfs(pdfs, censo) if pdfs and censo else []) + (elegir_tablas(tablas) if tablas else [])
    capt = capturar_pdfs(filas, guarda, hilos=hilos, fin=t0 + (max_minutos - 15) * 60)
    salida.mkdir(parents=True, exist_ok=True)
    peticiones, por_id, enviado, cuentas = [], {}, [], Counter()
    with (salida / "pdfs_capturados.jsonl").open("w", encoding="utf-8") as f:
        for c in capt:
            texto = c.pop("texto", None)
            cuentas["pedidos"] += 1
            if texto is None:
                cuentas[c.get("motivo", "error")] += 1
            elif len(texto) < 200 or not re.search(r"\d", texto):
                cuentas["sin_texto"] += 1  # PDF escaneado o vacío: queda para leerlo con imagen
                c["motivo"] = "sin_texto"
            else:
                cid = "t" + hashlib.sha256((c["url"] + c["sha256"]).encode()).hexdigest()[:24]
                por_id[cid] = (c, texto)
                peticiones.append(peticion(cid, c["url"], texto))
                enviado.append({"custom_id": cid, "url": c["url"], "sha256": c["sha256"], "texto": texto,
                                "proveedor": c["proveedor"], "dominio": c["dominio"],
                                **{k: c[k] for k in ("universidad", "curso_lista", "programa_lista") if c.get(k)}})
                cuentas["enviados"] += 1
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    if not peticiones:
        return dict(cuentas)
    r = requests.post(extraer.API, headers=extraer._cabeceras(), json={"requests": peticiones}, timeout=300)
    if r.status_code >= 400:
        return {**cuentas, "error_api": r.status_code, "detalle": r.text[:500]}
    b = r.json()
    clave = guarda.jsonl(extraer.FUENTE_EXTRACCION, enviado, "tarifas-enviado.jsonl", f"anthropic-batch:{b['id']}/tarifas")
    (salida / "lote.json").write_text(json.dumps({"id": b["id"], "clave_enviado": clave}), encoding="utf-8")
    fin = min(t0 + max_minutos * 60, time.time() + esperar_min * 60)
    while b.get("processing_status") != "ended" and time.time() < fin:
        time.sleep(30)
        b = requests.get(f"{extraer.API}/{b['id']}", headers=extraer._cabeceras(), timeout=60).json()
    if b.get("processing_status") != "ended":
        res = {**cuentas, "estado_lote": b.get("processing_status"), "id": b["id"]}
        (salida / "resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        return res
    return _procesar(b, por_id, salida, guarda, cuentas)


def _procesar(b: dict, por_id: dict, salida: Path, guarda: extraer.Guarda, cuentas: Counter) -> dict:
    res = requests.get(b["results_url"], headers=extraer._cabeceras(), timeout=600)
    if guarda.activa:
        guarda.original(extraer.FUENTE_EXTRACCION, res.content, "tarifas-resultados.jsonl",
                        f"anthropic-batch:{b['id']}/tarifas-resultados")
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    dolares = 0.0
    salida.mkdir(parents=True, exist_ok=True)
    with (salida / "precios.jsonl").open("w", encoding="utf-8") as fo:
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
            if msg.get("stop_reason") == "max_tokens":
                cuentas["cortados"] += 1
            if not datos.get("es_tarifa"):
                cuentas["no_es_tarifa"] += 1
                continue
            cuentas["tarifas"] += 1
            try:
                verificados = verificar(datos, texto)
            except Exception as e:  # noqa: BLE001 - un documento raro no tira la tanda ya pagada
                cuentas["error_" + type(e).__name__] += 1
                continue
            for p in verificados:
                p.update({"url": c["url"], "proveedor": c.get("proveedor"), "dominio": c.get("dominio"),
                          "curso": str(datos.get("curso") or c.get("curso_lista") or "")[:20], "captura_sha256": c["sha256"],
                          "extraido": ahora, "modelo": extraer.MODELO, "lote": b["id"]})
                if c.get("universidad"):  # tabla revisada: el precio es de esa universidad
                    p.update({"universidad": c["universidad"], "tabla": True,
                              **({"programa_lista": c["programa_lista"]} if c.get("programa_lista") else {})})
                fo.write(json.dumps(p, ensure_ascii=False) + "\n")
                cuentas["precios_" + p["estado"]] += 1
    resumen = {**cuentas, "id": b["id"], "coste_usd": round(dolares, 6), "almacen": dict(guarda.cuentas)}
    (salida / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    return resumen


def retomar(lote_json: Path, salida: Path, censo: Path | None = None, esperar_min: float = 30) -> dict:
    """Recoge un lote de tarifas ya enviado (por ejemplo, si la ejecución que lo envió se cortó), con el texto
    exacto que se envió, guardado en el almacén privado."""
    from urllib.parse import urlparse

    from motor.estudios.censo import dominio_registrado

    guarda = extraer.Guarda()
    info = json.loads(lote_json.read_text(encoding="utf-8"))
    provs = {}
    if censo:
        for l in censo.read_text(encoding="utf-8").split("\n"):
            if l.strip():
                x = json.loads(l)
                for d in x.get("dominios", [x["dominio"]]):
                    provs[d] = x["id"]
    por_id = {}
    for e in guarda.leer_jsonl(info["clave_enviado"]):
        dom = e.get("dominio") or dominio_registrado(urlparse(e["url"]).netloc)
        por_id[e["custom_id"]] = ({"url": e["url"], "sha256": e["sha256"], "dominio": dom,
                                   "proveedor": e.get("proveedor") or provs.get(dom),
                                   **{k: e[k] for k in ("universidad", "curso_lista", "programa_lista") if e.get(k)}},
                                  e["texto"])
    b = requests.get(f"{extraer.API}/{info['id']}", headers=extraer._cabeceras(), timeout=60).json()
    fin = time.time() + esperar_min * 60
    while b.get("processing_status") != "ended" and time.time() < fin:
        time.sleep(30)
        b = requests.get(f"{extraer.API}/{info['id']}", headers=extraer._cabeceras(), timeout=60).json()
    if b.get("processing_status") != "ended":
        return {"estado_lote": b.get("processing_status"), "id": info["id"]}
    return _procesar(b, por_id, salida, guarda, Counter({"retomado": 1}))


def unir(tarifas: list[Path], fichas: Path, salida: Path) -> dict:
    """Cada precio aceptado, a la ficha de máster del mismo proveedor cuyo nombre coincide (el del RUCT en los
    oficiales, el de la página en los demás). Si varias fichas coinciden igual de bien, no se une."""
    from urllib.parse import urlparse

    from motor.estudios.censo import dominio_registrado
    from motor.estudios.fichas_masters import comprobar_nombre

    precios = [json.loads(l) for t in tarifas for f in sorted(t.rglob("precios.jsonl"))
               for l in f.read_text(encoding="utf-8").split("\n") if l.strip()]
    por_prov: dict[str, list[dict]] = defaultdict(list)
    for l in fichas.read_text(encoding="utf-8").split("\n"):
        if l.strip():
            f = json.loads(l)
            nombre = f.get("nombre_oficial") or str(((f.get("campos") or {}).get("nombre") or {}).get("valor") or "")
            if not nombre or (f["grupo"] == "oficial" and f.get("comprobacion_nombre") not in
                              ("confirmado", "probable_oficial", "confirmado_por_nombre")):
                continue
            # los oficiales se buscan por el dominio de su página; los demás, por su proveedor
            claves = {f.get("proveedor")} if f.get("proveedor") else \
                {dominio_registrado(urlparse(u).netloc) for u in f.get("paginas", [])}
            for k in claves - {None, ""}:
                por_prov[k].append({"clave": f["clave"], "nombre": nombre})
    cuentas, filas = Counter(), []
    # el mismo precio puede venir de varias tandas o PDF: se queda uno por ficha y concepto, el del curso más
    # reciente (y entre iguales, la extracción más nueva)
    def curso(p: dict) -> int:
        m = [int(x) for x in re.findall(r"20\d\d", str(p.get("curso") or "") + " " + p.get("url", ""))]
        return max(m) if m else 0

    precios = sorted(precios, key=lambda p: (curso(p), p.get("extraido", "")), reverse=True)
    vistos: set = set()
    for p in precios:
        if p["estado"] != "aceptado":
            continue
        cuentas["precios_aceptados"] += 1
        candidatos = por_prov.get(p["proveedor"], []) + por_prov.get(p["dominio"], [])
        mejores = sorted(((comprobar_nombre(c["nombre"], p["programa"]), c) for c in candidatos),
                         key=lambda x: -x[0][1])
        buenos = [(e, c) for e, c in mejores if e[0] == "confirmado"]
        if len(buenos) == 1 or (len(buenos) > 1 and buenos[0][0][1] > buenos[1][0][1]):
            clave_ficha = (buenos[0][1]["clave"], p.get("concepto"))
            if clave_ficha in vistos:
                cuentas["repetidos_o_de_otro_curso"] += 1
                continue
            vistos.add(clave_ficha)
            cuentas["unidos"] += 1
            filas.append({**p, "ficha": buenos[0][1]["clave"], "cobertura_nombre": buenos[0][0][1]})
        else:
            cuentas["sin_ficha" if not buenos else "ambiguos"] += 1
    destino = salida / "datos" / "estudios" / "tarifas"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "precios_unidos.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in filas),
                                                  encoding="utf-8")
    cuentas["fichas_con_precio_de_tarifa"] = len({x["ficha"] for x in filas})
    return dict(cuentas)


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("orden", choices=["lote", "unir", "descubrir", "todo", "retomar"])
    a.add_argument("--lote-json")
    a.add_argument("--capturadas", action="append", default=[], help="carpetas con paginas_capturadas.jsonl")
    a.add_argument("--pdfs", action="append", default=[])
    a.add_argument("--censo")
    a.add_argument("--tablas", help="tablas de precios revisadas de las universidades (jsonl: url, universidad, curso)")
    a.add_argument("--tarifas", action="append", default=[])
    a.add_argument("--fichas")
    a.add_argument("--esperar-min", type=float, default=40)
    a.add_argument("--max-minutos", type=float, default=52)
    a.add_argument("--hilos", type=int, default=12)
    a.add_argument("--salida", required=True)
    x = a.parse_args()
    if x.orden == "retomar":
        print(json.dumps(retomar(Path(x.lote_json), Path(x.salida) / "datos" / "estudios" / "tarifas" / "retomado",
                                 Path(x.censo) if x.censo else None, x.esperar_min), ensure_ascii=False))
        return
    if x.orden in ("descubrir", "todo"):
        base = Path(x.salida) / "datos" / "estudios" / "tarifas"
        r = descubrir_en_originales([Path(p) for p in x.capturadas], base)
        print(json.dumps(r, ensure_ascii=False), flush=True)
        if x.orden == "descubrir":
            return
        x.pdfs = list(x.pdfs) + [str(base / "precios_desde_paginas.jsonl")]
    if x.orden in ("lote", "todo"):
        r = lote([Path(p) for p in x.pdfs], Path(x.censo) if x.censo else None,
                 Path(x.salida) / "datos" / "estudios" / "tarifas" / "lote", x.esperar_min, x.max_minutos, x.hilos,
                 tablas=Path(x.tablas) if x.tablas else None)
    else:
        r = unir([Path(p) for p in x.tarifas], Path(x.fichas), Path(x.salida))
    print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
