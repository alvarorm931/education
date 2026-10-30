"""Tanda de prueba de la extracción de fichas con Claude (lote de la API de Anthropic): ¿funciona y cuánto cuesta?

Usa sin cambiarlas las piezas de la extracción de másters (motor/estudios/extraer.py): mismo prompt, mismo modelo,
misma comprobación de la cita literal. Lo que añade es lo que hace falta para decidir antes de la extracción masiva:
  - elige unas pocas páginas de programa de centros conocidos (rastreo ya hecho: oferta_web/*.json), las pide con el
    rastreador cortés (robots.txt, una petición por segundo, agente identificado) y comprueba que son fichas;
  - envía el lote, espera a que termine y suma los tokens que la API dice haber usado en cada petición;
  - calcula el coste con los precios oficiales de lote y lo proyecta a 1.000 y a 30.000 páginas.

Las páginas no salen del trabajo (la rama es pública y son textos ajenos): solo se publican el resumen, los
tokens por página y los valores extraídos sin su cita.

Precios (https://platform.claude.com/docs/en/about-claude/pricing, consultado el 30/10/2026), Claude Haiku 5.5 en
lote, para peticiones de hasta 100.000 tokens: entrada 0,05 $/MTok y salida 0,25 $/MTok (la mitad del precio
normal: 0,10 y 0,50). Escritura en caché de 5 minutos 0,125 $/MTok y lectura 0,01 $/MTok a precio normal; aquí se
cuentan a precio normal, sin descuento, para no quedarse cortos.

Uso:
  python -m motor.ia.prueba_extraccion --oferta ruta/oferta_web --por-dominio 2 --maximo 20 --salida ruta/
  python -m motor.ia.prueba_extraccion --recoger msgbatch_... --salida ruta/        # si el lote tardó más
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
from urllib.parse import urlparse

import requests

from motor.estudios import extraer
from motor.estudios import rastreador

# $ por millón de tokens (lote, peticiones de hasta 100.000 tokens); caché a precio normal (cota superior)
PRECIO = {"input_tokens": 0.05, "output_tokens": 0.25, "cache_creation_input_tokens": 0.125,
          "cache_read_input_tokens": 0.01}
PRECIO_FUENTE = "https://platform.claude.com/docs/en/about-claude/pricing (30/10/2026)"
UMBRAL_TOKENS = 100_000  # por encima, Haiku 5.5 cobra la entrada a 0,25 $/MTok en lote

DOMINIOS = ("www.unir.net", "www.esic.edu", "www.eae.es", "www.nebrija.com", "www.eoi.es", "www.cef.es",
            "www.obsbusiness.school", "www.structuralia.com", "www.ucam.edu", "www.ucavila.es",
            "www.iebschool.com", "www.isdi.education", "www.eude.es", "www.upm.es")
LISTADOS = ("opiniones", "collections", "course-category", "categoria", "category", "testimonios")
SUBPAGINA = ("acceso", "plan-de-estudios", "salidas-profesionales", "admision", "becas", "precio", "precios",
             "profesorado", "contacto", "metodologia", "titulacion", "requisitos", "faq", "opiniones")


def candidatos(info: dict, n: int) -> list[str]:
    """Fichas probables: la URL nombra el programa y no es una subpágina (acceso, plan de estudios…)."""
    vistos, out = set(), []
    for u in info.get("programas") or []:
        tramos = [t for t in urlparse(u).path.split("/") if t]
        if not tramos or tramos[-1].lower() in SUBPAGINA or u in vistos or any(t.lower() in LISTADOS for t in tramos):
            continue
        if rastreador.es_programa(u):
            vistos.add(u)
            out.append(u)
    # repartidas por la lista (no las n primeras, que suelen ser de la misma área)
    if len(out) > n:
        paso = len(out) / n
        out = [out[int(i * paso)] for i in range(n)]
    return out


def elegir_paginas(oferta: Path, dominios: list[str], por_dominio: int, maximo: int, carpeta: Path) -> list[dict]:
    """Pide las candidatas y se queda con las que el rastreador reconoce como ficha de programa."""
    carpeta.mkdir(parents=True, exist_ok=True)
    elegidas = []
    for dom in dominios:
        f = oferta / f"{dom}.json"
        if not f.exists() or len(elegidas) >= maximo:
            continue
        info = json.loads(f.read_text(encoding="utf-8"))
        d = rastreador.Dominio(info.get("base") or "https://" + dom, None, pausa=1.0, max_peticiones=12)
        buenas = 0
        for u in candidatos(info, por_dominio * 3):
            if buenas >= por_dominio or len(elegidas) >= maximo:
                break
            r = d.get(u, guardar=False)
            if r is None or r.status_code != 200 or "html" not in (r.headers.get("content-type") or "html"):
                continue
            html = rastreador.texto_de(r)
            medida = rastreador.medir_pagina(html, r.url)
            if not medida.get("es_programa"):
                continue
            sha = hashlib.sha256(r.content).hexdigest()
            ruta = carpeta / f"{sha[:16]}.html"
            ruta.write_text(html, encoding="utf-8")
            elegidas.append({"url": r.url, "sha256": sha, "ruta": str(ruta), "dominio": dom,
                             "reserva_tdm": rastreador.reserva_tdm(dict(r.headers), html),
                             "caracteres_visibles": medida.get("caracteres_visibles")})
            buenas += 1
        print(f"{dom}: {buenas} fichas ({dict(d.estados)})")
    return elegidas


def _api(metodo: str, url: str, **kw) -> requests.Response:
    r = requests.request(metodo, url, headers=extraer._cabeceras(), timeout=kw.pop("timeout", 120), **kw)
    if r.status_code >= 400:
        # el cuerpo del error de la API dice qué falla (clave, modelo, saldo); nunca lleva la clave
        sys.exit(f"API {r.status_code}: {r.text[:800]}")
    return r


def ajustar(reqs: list[dict], razonamiento: bool, max_tokens: int | None) -> list[dict]:
    """Claude Haiku 5.5 razona por defecto (razonamiento adaptativo, esfuerzo «medium») y ese razonamiento cuenta
    dentro de max_tokens: en la primera prueba (30/10/2026) se comió los 3.000 tokens en 16 de 20 páginas y no
    quedó respuesta. Para copiar datos con su cita no hace falta: se desactiva (permitido en Haiku 5.5 hasta el
    esfuerzo «high», https://platform.claude.com/docs/en/build-with-claude/effort)."""
    for r in reqs:
        if not razonamiento:
            r["params"]["thinking"] = {"type": "disabled"}
        if max_tokens:
            r["params"]["max_tokens"] = max_tokens
    return reqs


def enviar(lote: Path, razonamiento: bool = False, max_tokens: int | None = None) -> dict:
    reqs = ajustar([json.loads(l) for l in lote.read_text(encoding="utf-8").splitlines() if l.strip()],
                   razonamiento, max_tokens)
    return _api("POST", extraer.API, json={"requests": reqs}).json()


def esperar(batch_id: str, minutos: float) -> dict:
    fin = time.time() + minutos * 60
    while True:
        b = _api("GET", f"{extraer.API}/{batch_id}", timeout=60).json()
        print(f"{datetime.now(timezone.utc):%H:%M:%S} {b.get('processing_status')} {b.get('request_counts')}")
        if b.get("processing_status") == "ended" or time.time() > fin:
            return b
        time.sleep(30)


def diagnostico(crudo: str) -> dict:
    """Qué ocupa la respuesta, sin guardar su texto: caracteres por campo (en orden) y si va en bloque de código."""
    claves = [(m.start(), m.group(1)) for m in re.finditer(r'"(\w+)"\s*:\s*[\[{n]', crudo)
              if m.group(1) in extraer.CAMPOS or m.group(1) == "no_es_programa"]
    tramos = {}
    for i, (ini, k) in enumerate(claves):
        fin = claves[i + 1][0] if i + 1 < len(claves) else len(crudo)
        tramos[k] = tramos.get(k, 0) + fin - ini
    return {"caracteres": len(crudo), "bloque_de_codigo": crudo.lstrip().startswith("```"),
            "campos_empezados": len(tramos), "caracteres_por_campo": tramos,
            "asignaturas_elementos": crudo.count('"nombre"')}


def coste(uso: dict) -> float:
    return sum(uso.get(k, 0) * p for k, p in PRECIO.items()) / 1_000_000


def recoger(b: dict, paginas: dict[str, dict], salida: Path) -> dict:
    """Suma el uso de cada petición y comprueba las citas (si están las páginas)."""
    r = _api("GET", b["results_url"], timeout=300)
    uso_total = {k: 0 for k in PRECIO}
    filas, hechos, tipos, tipos_bloque = [], [], {}, {}
    for linea in r.text.splitlines():
        x = json.loads(linea)
        tipo = x["result"]["type"]
        tipos[tipo] = tipos.get(tipo, 0) + 1
        if tipo != "succeeded":
            filas.append({"custom_id": x["custom_id"], "resultado": tipo,
                          "error": json.dumps(x["result"].get("error"), ensure_ascii=False)[:300]})
            continue
        msg = x["result"]["message"]
        uso = {k: int(msg.get("usage", {}).get(k) or 0) for k in PRECIO}
        crudo = "".join(c.get("text", "") for c in msg.get("content", []))
        for c in msg.get("content", []):
            tipos_bloque[c.get("type")] = tipos_bloque.get(c.get("type"), 0) + 1
        for k in uso_total:
            uso_total[k] += uso[k]
        p = paginas.get(x["custom_id"])
        datos = extraer._json_de("".join(c.get("text", "") for c in msg.get("content", [])))
        fila = {"custom_id": x["custom_id"], "resultado": tipo, "url": p and p["url"], "uso": uso,
                "coste_usd": round(coste(uso), 6), "parada": msg.get("stop_reason"),
                "no_es_programa": bool(datos.get("no_es_programa")), "json_valido": bool(datos)}
        prompt = uso["input_tokens"] + uso["cache_creation_input_tokens"] + uso["cache_read_input_tokens"]
        fila["supera_100k"] = prompt > UMBRAL_TOKENS
        fila["diagnostico"] = diagnostico(crudo)
        if p and datos and not datos.get("no_es_programa"):
            texto = extraer.texto_de_pagina(Path(p["ruta"]).read_text(encoding="utf-8"))
            hs = extraer.verificar(datos, texto)
            fila["campos"] = len(hs)
            fila["aceptados"] = sum(h["estado"] == "aceptado" for h in hs)
            for h in hs:  # sin la cita: es texto de la web del centro
                hechos.append({"url": p["url"], "campo": h["campo"], "estado": h["estado"],
                               "valor": h["valor"] if h["estado"] == "aceptado" else None,
                               "cita_palabras": len((h.get("cita") or "").split())})
        filas.append(fila)
    ok = [f for f in filas if f["resultado"] == "succeeded"]
    total = coste(uso_total)
    por_pagina = total / len(ok) if ok else 0
    resumen = {
        "lote": b["id"], "modelo": extraer.MODELO,
        "tipos_de_bloque": tipos_bloque, "estado": b.get("processing_status"),
        "creado": b.get("created_at"), "terminado": b.get("ended_at"), "cuentas": b.get("request_counts"),
        "resultados": tipos, "tokens": uso_total, "coste_usd": round(total, 4),
        "coste_por_pagina_usd": round(por_pagina, 6),
        "proyeccion_usd": {"1000_paginas": round(por_pagina * 1000, 2), "30000_paginas": round(por_pagina * 30000, 2)},
        "paginas_con_json": sum(f.get("json_valido", False) for f in ok),
        "paginas_no_programa": sum(f.get("no_es_programa", False) for f in ok),
        "cortadas_por_max_tokens": sum(f.get("parada") == "max_tokens" for f in ok),
        "superan_100k_tokens": sum(f.get("supera_100k", False) for f in ok),
        "campos": len(hechos), "campos_aceptados": sum(h["estado"] == "aceptado" for h in hechos),
        "precios": {"usd_por_mtok": PRECIO, "fuente": PRECIO_FUENTE},
    }
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    (salida / "peticiones.jsonl").write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in filas),
                                             encoding="utf-8")
    (salida / "hechos_sin_cita.jsonl").write_text("".join(json.dumps(h, ensure_ascii=False) + "\n" for h in hechos),
                                                  encoding="utf-8")
    return resumen


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--oferta", type=Path, help="carpeta oferta_web del rastreo (un JSON por dominio)")
    p.add_argument("--dominios", default=",".join(DOMINIOS))
    p.add_argument("--por-dominio", type=int, default=2)
    p.add_argument("--maximo", type=int, default=20)
    p.add_argument("--esperar-min", type=float, default=75)
    p.add_argument("--recoger", help="id de un lote ya enviado")
    p.add_argument("--con-razonamiento", action="store_true", help="dejar el razonamiento adaptativo por defecto")
    p.add_argument("--max-tokens", type=int, default=8000)
    p.add_argument("--paginas-dir", type=Path, default=Path("/tmp/paginas-prueba"),
                   help="dónde quedan las páginas (fuera de lo que se publica)")
    p.add_argument("--salida", type=Path, required=True)
    a = p.parse_args(argv)
    destino = a.salida / "datos" / "ia" / "prueba_extraccion"
    destino.mkdir(parents=True, exist_ok=True)
    if a.recoger:
        b = esperar(a.recoger, a.esperar_min)
        if b.get("processing_status") != "ended":
            print(json.dumps({"lote": a.recoger, "estado": b.get("processing_status")}))
            return 0
        print(json.dumps(recoger(b, {}, destino), ensure_ascii=False))
        return 0
    paginas = elegir_paginas(a.oferta, [x for x in a.dominios.split(",") if x], a.por_dominio, a.maximo,
                             a.paginas_dir)
    if not paginas:
        sys.exit("No se ha podido leer ninguna ficha")
    lista = a.paginas_dir / "paginas.jsonl"
    lista.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in paginas), encoding="utf-8")
    prep = extraer.preparar(lista, a.paginas_dir)
    por_id = {extraer.id_pagina(x["url"], x["sha256"]): x for x in paginas if not x["reserva_tdm"]}
    (destino / "paginas.jsonl").write_text(
        "".join(json.dumps({k: x[k] for k in ("url", "sha256", "dominio", "reserva_tdm", "caracteres_visibles")},
                           ensure_ascii=False) + "\n" for x in paginas), encoding="utf-8")
    print(f"Páginas: {len(paginas)}; peticiones: {prep}")
    b = enviar(a.paginas_dir / "lote.jsonl", a.con_razonamiento, a.max_tokens)
    (destino / "lote.json").write_text(json.dumps({"id": b["id"], "enviado": b.get("created_at"),
                                                   "peticiones": prep["peticiones"], "razonamiento": a.con_razonamiento,
                                                   "max_tokens": a.max_tokens}), encoding="utf-8")
    print(f"Lote enviado: {b['id']}")
    b = esperar(b["id"], a.esperar_min)
    if b.get("processing_status") != "ended":
        print(f"El lote no ha terminado en {a.esperar_min} minutos; recoger luego con --recoger {b['id']}")
        return 0
    print(json.dumps(recoger(b, por_id, destino), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
