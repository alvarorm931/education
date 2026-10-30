"""Auditoría técnica de la competencia: lo que un buscador ve de cada web que hoy ocupa nuestras búsquedas.

Para cada dominio, sin descargar más que unas pocas páginas y respetando su robots.txt para nuestro agente:
- **robots.txt**: a qué robots de búsqueda, de IA y de entrenamiento cierra la puerta (quien cierra a OAI-SearchBot
  no sale en ChatGPT; quien cierra a PerplexityBot, en Perplexity), si Cloudflare antepone su robots.txt
  (`Content-signal`) y qué sitemaps declara.
- **Tamaño**: cuántas direcciones declara en sus sitemaps (contadas en una muestra de sus archivos y estimadas para
  el resto).
- **Portada y tres páginas de sus sitemaps**: si el contenido está en el HTML sin JavaScript, qué datos
  estructurados usa (JobPosting, Course, FAQPage…), si pide correo o teléfono, si hay fechas visibles, canónica,
  noindex y tamaño.
- **Velocidad real** (CrUX, a través de la API pública de PageSpeed Insights): percentil 75 de LCP, INP y CLS del
  dominio en móvil.

Uso (desde GitHub; el espacio de trabajo de Claude no llega a esas webs):
    python -m motor.seo.competencia --salida carpeta/ [--dominios a.es,b.com] [--sin-velocidad]
Solo lee lo publicado y nada que su robots.txt prohíba a nuestro agente; no guarda textos de las páginas, solo
medidas.
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import lxml.html
import requests
from lxml import etree

from motor.http import RobotsProhibe, comprobar_robots
from motor.robots import Robots

AGENTE = "PortalEstudiosOposiciones/0.1 (analisis SEO; pocas paginas por dominio)"
DOMINIOS = {
    # Oposiciones
    "redopositor.com": "oposiciones", "preparaoposiciones.com": "oposiciones", "opositatest.com": "oposiciones",
    "adams.es": "oposiciones", "cef.es": "oposiciones", "oposiciones.es": "oposiciones",
    "administracion.gob.es": "oficial", "csif.es": "oposiciones",
    # Estudios
    "educaweb.com": "estudios", "emagister.com": "estudios", "yaq.es": "estudios", "notasdecorte.es": "estudios",
    "dondeestudiar.eu": "estudios", "uniscopio.com": "estudios", "mastermania.com": "estudios",
    "aprendemas.com": "estudios", "universia.net": "estudios", "tesify.es": "estudios",
    "gradopedia.com": "estudios", "todofp.es": "oficial",
    # Modelo de referencia del proyecto
    "convenioslaborales.com": "modelo",
}
ROBOTS = ["Googlebot", "Bingbot", "OAI-SearchBot", "ChatGPT-User", "Claude-SearchBot", "Claude-User",
          "PerplexityBot", "GPTBot", "ClaudeBot", "Google-Extended", "Applebot-Extended", "CCBot",
          "Meta-ExternalAgent", "Amazonbot", "Bytespider"]
MARCAS_JS = {"__NEXT_DATA__": "Next.js", "__NUXT__": "Nuxt", "ng-version": "Angular", "data-reactroot": "React",
             "data-server-rendered": "Vue SSR", "wp-content": "WordPress", "/_astro/": "Astro"}
PSI = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def pedir(sesion, url, limite=20 * 1024 * 1024):
    comprobar_robots(url, sesion)
    r = sesion.get(url, headers={"User-Agent": AGENTE}, timeout=30, stream=True)
    datos = b""
    for trozo in r.iter_content(65536):
        datos += trozo
        if len(datos) > limite:
            break
    r.close()
    if datos[:2] == b"\x1f\x8b":
        try:
            datos = gzip.decompress(datos)
        except OSError:
            pass
    return r, datos


def robots_info(texto: str) -> dict:
    lineas = [l.split("#", 1)[0].strip() for l in texto.splitlines()]
    return {
        "cerrado_a": [b for b in ROBOTS if not Robots(texto, agente=b).permite("https://x/")],
        "content_signal": any(l.lower().startswith("content-signal") for l in lineas),
        "crawl_delay": any(l.lower().startswith("crawl-delay") for l in lineas),
        "sitemaps": [l.split(":", 1)[1].strip() for l in lineas if l.lower().startswith("sitemap:")],
        "bytes": len(texto.encode()),
    }


def analizar_html(html: bytes, url: str) -> dict:
    try:
        arbol = lxml.html.document_fromstring(html)
    except (etree.ParserError, ValueError):
        return {"error": "HTML ilegible"}
    for el in arbol.xpath("//script | //style | //noscript | //template"):
        el.drop_tree()
    cuerpo = arbol.find("body")
    texto = re.sub(r"\s+", " ", cuerpo.text_content() if cuerpo is not None else "").strip()
    crudo = html.decode("utf-8", errors="replace")
    tipos = []
    for bloque in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', crudo, re.S | re.I):
        tipos += re.findall(r'"@type"\s*:\s*"([^"]+)"', bloque)
    host = urlparse(url).netloc.removeprefix("www.")
    enlaces = [a.get("href", "") for a in arbol.xpath("//a[@href]")]
    internos = [h for h in enlaces if urlparse(urljoin(url, h)).netloc.removeprefix("www.") == host]
    metas = {m.get("name", "").lower(): m.get("content", "") for m in arbol.xpath("//meta[@name]")}
    entradas = [i.get("type", "").lower() + ":" + (i.get("name") or "").lower() for i in arbol.xpath("//input")]
    return {
        "bytes": len(html),
        "palabras_sin_js": len(texto.split()),
        "titulo": (arbol.findtext(".//title") or "").strip()[:120],
        "h1": len(arbol.xpath("//h1")),
        "canonica": [l.get("href") for l in arbol.xpath("//link[@rel='canonical']")],
        "robots": metas.get("robots", ""),
        "datos_estructurados": sorted(set(tipos)),
        "pide_correo": any("email" in e or "correo" in e for e in entradas),
        "pide_telefono": any(e.startswith("tel:") or "telefono" in e or "phone" in e for e in entradas),
        "fechas_visibles": len(arbol.xpath("//time")) + len(re.findall(r"actualizad[oa]", texto, re.I)),
        "enlaces_internos": len(internos),
        "almohadillas": sum(1 for h in enlaces if h.startswith("#") and len(h) <= 2 or h.startswith("#!")),
        "tecnologia": sorted({v for k, v in MARCAS_JS.items() if k in crudo}),
        "hreflang": len(arbol.xpath("//link[@hreflang]")),
    }


def muestra_sitemaps(sesion, mapas: list[str], rng: random.Random, max_archivos: int = 6) -> dict:
    salida = {"indices": 0, "archivos": 0, "contados": 0, "urls_contadas": 0, "estimadas": 0, "muestra": [],
              "lastmod_presente": 0, "changefreq_o_priority": False, "errores": []}
    pendientes, hojas = list(mapas[:5]), []
    vistos = set()
    while pendientes and len(vistos) < 40:
        m = pendientes.pop(0)
        if m in vistos:
            continue
        vistos.add(m)
        try:
            r, datos = pedir(sesion, m)
            raiz = etree.fromstring(datos)
        except RobotsProhibe:
            salida["errores"].append(f"{m}: robots.txt lo prohíbe a nuestro agente")
            continue
        except Exception as e:
            salida["errores"].append(f"{m}: {type(e).__name__}")
            continue
        nombre = etree.QName(raiz).localname
        locs = [e.text.strip() for e in raiz.iter("{*}loc") if e.text]
        if nombre == "sitemapindex":
            salida["indices"] += 1
            hijos = locs
            salida["archivos"] += len(hijos)
            # Muestra repartida: primero, último y al azar
            elegidos = sorted(set(hijos[:1] + hijos[-1:] + rng.sample(hijos, min(len(hijos), max_archivos))))
            pendientes += elegidos[:max_archivos]
            hojas.append(("indice", m, len(hijos)))
        else:
            salida["contados"] += 1
            salida["urls_contadas"] += len(locs)
            salida["lastmod_presente"] += sum(1 for _ in raiz.iter("{*}lastmod"))
            salida["changefreq_o_priority"] |= any(True for _ in raiz.iter("{*}priority")) or \
                any(True for _ in raiz.iter("{*}changefreq"))
            salida["muestra"] += rng.sample(locs, min(len(locs), 2))
    if salida["contados"]:
        media = salida["urls_contadas"] / salida["contados"]
        archivos = max(salida["archivos"], salida["contados"])
        salida["estimadas"] = round(media * archivos)
    salida["muestra"] = salida["muestra"][:12]
    return salida


def velocidad(sesion, url: str) -> dict:
    try:
        r = sesion.get(PSI, params={"url": url, "strategy": "mobile", "category": "performance"}, timeout=120)
    except requests.RequestException as e:
        return {"error": type(e).__name__}
    if r.status_code != 200:
        return {"error": f"HTTP {r.status_code}"}
    d = r.json()
    salida = {}
    for clave, nombre in (("originLoadingExperience", "origen"), ("loadingExperience", "portada")):
        metricas = d.get(clave, {}).get("metrics", {})
        if metricas:
            salida[nombre] = {
                "lcp_ms": metricas.get("LARGEST_CONTENTFUL_PAINT_MS", {}).get("percentile"),
                "inp_ms": metricas.get("INTERACTION_TO_NEXT_PAINT", {}).get("percentile"),
                "cls": (metricas.get("CUMULATIVE_LAYOUT_SHIFT_SCORE", {}).get("percentile") or 0) / 100,
                "categoria": d.get(clave, {}).get("overall_category"),
            }
    lh = d.get("lighthouseResult", {}).get("categories", {}).get("performance", {})
    salida["laboratorio_rendimiento"] = lh.get("score")
    return salida


def analizar_dominio(dominio: str, sesion, rng, con_velocidad=True) -> dict:
    salida: dict = {"dominio": dominio, "grupo": DOMINIOS.get(dominio, "")}
    base = None
    for intento in (f"https://www.{dominio}", f"https://{dominio}"):
        try:
            r = sesion.get(intento + "/robots.txt", headers={"User-Agent": AGENTE}, timeout=20)
            base = intento
            salida["robots_estado"] = r.status_code
            salida["robots"] = robots_info(r.text if r.status_code == 200 else "")
            break
        except requests.RequestException as e:
            salida["robots_error"] = type(e).__name__
    if base is None:
        return salida
    try:
        r, html = pedir(sesion, base + "/")
        salida["portada"] = {"estado": r.status_code, "final": r.url, "servidor": r.headers.get("server", ""),
                             "cloudflare": "cf-ray" in {k.lower() for k in r.headers}} | analizar_html(html, r.url)
    except RobotsProhibe:
        salida["portada"] = {"error": "robots.txt prohíbe la portada a nuestro agente"}
    except requests.RequestException as e:
        salida["portada"] = {"error": type(e).__name__}
    mapas = salida.get("robots", {}).get("sitemaps") or [base + "/sitemap.xml"]
    salida["sitemaps"] = muestra_sitemaps(sesion, mapas, rng)
    paginas = []
    for url in salida["sitemaps"]["muestra"][:3]:
        time.sleep(1)
        try:
            r, html = pedir(sesion, url)
            paginas.append({"url": url, "estado": r.status_code} | analizar_html(html, r.url))
        except RobotsProhibe:
            paginas.append({"url": url, "error": "robots.txt la prohíbe a nuestro agente"})
        except requests.RequestException as e:
            paginas.append({"url": url, "error": type(e).__name__})
    salida["paginas"] = paginas
    if con_velocidad:
        salida["velocidad"] = velocidad(sesion, base + "/")
    return salida


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Auditoría técnica de la competencia")
    p.add_argument("--dominios", help="separados por comas (por defecto, la lista del módulo)")
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--sin-velocidad", action="store_true")
    a = p.parse_args(argv)
    dominios = [d.strip() for d in a.dominios.split(",")] if a.dominios else list(DOMINIOS)
    sesion = requests.Session()
    rng = random.Random(20261030)
    a.salida.mkdir(parents=True, exist_ok=True)
    resultados = []
    for d in dominios:
        res = analizar_dominio(d, sesion, rng, not a.sin_velocidad)
        resultados.append(res)
        cerr = res.get("robots", {}).get("cerrado_a", [])
        print(f"{d}: cierra a {', '.join(cerr) or 'nadie'} · ~{res.get('sitemaps', {}).get('estimadas', 0)} URL")
        (a.salida / "competencia.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=1),
                                                   encoding="utf-8")
        time.sleep(2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
