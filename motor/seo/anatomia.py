"""Anatomía de un sitio: cómo está construido por dentro un sitio de SEO programático.

Para un dominio (por ejemplo, el modelo de referencia del proyecto, convenioslaborales.com) mide, sin guardar sus
textos:
- **Edad**: alta del dominio (RDAP), primer certificado (registro público de certificados, crt.sh), primeras
  capturas de la Wayback Machine y presencia en los índices de Common Crawl.
- **Inventario**: todas las direcciones de sus sitemaps con su `lastmod`, agrupadas en tipos de página
  (`/calendario-laboral/{año}/{s3}/{s4}/`), con cuántas hay de cada tipo y cuándo cambiaron.
- **Arquitectura**: rastreo en anchura desde la portada (una petición por segundo, respetando robots.txt para
  nuestro agente), profundidad de clic de cada tipo, quién enlaza a quién y desde qué zona de la página (menú,
  contenido, pie), y páginas enlazadas que no están en los sitemaps.
- **Plantillas**: de cada tipo, títulos, encabezados, palabras, tablas, datos estructurados, fechas visibles,
  fuentes citadas, imágenes, guiones de terceros, anuncios, gestor de consentimiento y analítica; y cuánto texto
  comparten las páginas del mismo tipo (lo que es plantilla y lo que es dato propio).
- **Servidor**: redirecciones (http, www, barra final, mayúsculas), respuesta a una dirección inexistente,
  respuestas 304, cabeceras de caché, ads.txt, llms.txt y security.txt.
- **Velocidad**: CrUX si hay clave (`CRUX_API_KEY`) o PageSpeed sin clave; con `--navegador`, laboratorio con
  Chromium en móvil lento (LCP, CLS, peso y peticiones de terceros) y qué añade JavaScript al contenido.
- **Popularidad pública**: puesto en la lista Tranco, si aparece.

Uso (desde GitHub, con el flujo «SEO, análisis bajo demanda»):
    python -m motor.seo.anatomia --dominio convenioslaborales.com --salida carpeta/ [--max-paginas 450]
        [--por-tipo 4] [--navegador]
Deja anatomia.json (resumen), paginas.jsonl (una línea por página analizada), enlaces.jsonl (grafo interno del
rastreo) y sitemap.csv.gz (direcciones, tipo y lastmod).
"""

from __future__ import annotations

import argparse
import collections
import csv
import gzip
import io
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import lxml.html
import numpy as np
import requests
from lxml import etree

from motor.http import RobotsProhibe, comprobar_robots
from motor.seo.competencia import AGENTE, ROBOTS, robots_info
from motor.seo.similitud import jaccard, tejas

PAUSA = 1.0
ANO = re.compile(r"^(19|20)\d\d$")
NUMERO = re.compile(r"^\d+$")
EXT_NO_HTML = re.compile(r"\.(png|jpe?g|gif|webp|avif|svg|ico|css|js|mjs|json|xml|txt|pdf|zip|gz|woff2?|ttf|mp4|"
                         r"webm|mp3|csv|xlsx?|docx?)$", re.I)
MARCAS = {
    # tecnología
    "/_astro/": "Astro", "__NEXT_DATA__": "Next.js", "/_next/": "Next.js", "__NUXT__": "Nuxt", "/_nuxt/": "Nuxt",
    "wp-content": "WordPress", "data-reactroot": "React", "ng-version": "Angular", "/_app/immutable/": "SvelteKit",
    "gatsby": "Gatsby", "hugo": "Hugo", "data-astro-cid": "Astro", "eleventy": "Eleventy",
}
TERCEROS = {
    "anuncios": ["adsbygoogle", "pagead2.googlesyndication.com", "securepubads.g.doubleclick.net", "googletag",
                 "prebid", "amazon-adsystem.com", "taboola", "outbrain", "ezoic", "mediavine", "adthrive", "seedtag",
                 "sunmedia", "richaudience", "adform"],
    "consentimiento": ["fundingchoicesmessages.google.com", "cookiebot", "didomi", "quantcast", "onetrust",
                       "cookieyes", "iubenda", "cookielaw", "consentmanager", "usercentrics", "klaro"],
    "analitica": ["googletagmanager.com", "google-analytics.com", "gtag(", "plausible.io", "umami",
                  "static.cloudflareinsights.com", "matomo", "clarity.ms", "hotjar", "simpleanalytics",
                  "posthog", "fathom", "goatcounter", "vercel-insights", "pirsch"],
    "afiliacion": ["awin1.com", "tradedoubler", "amzn.to", "amazon.es/", "tag=", "clk.", "partner"],
}
FUENTES = ["boe.es", "regcon", "mites.gob.es", "trabajo.gob.es", "seg-social.es", "sepe.es", "ine.es",
           "boletin oficial", "boletín oficial", "bop ", "fuente:", "fuentes:"]
CAB = ["server", "cache-control", "cf-cache-status", "age", "last-modified", "etag", "x-robots-tag", "content-type",
       "content-encoding", "vary", "strict-transport-security", "x-powered-by", "content-security-policy", "link",
       "x-frame-options", "referrer-policy", "permissions-policy", "alt-svc", "nel", "report-to"]


# ---------------------------------------------------------------------------------------------------- peticiones

class Cliente:
    """Una petición por segundo, con robots.txt para nuestro agente y la cuenta de lo pedido."""

    def __init__(self, sesion=None, pausa: float = PAUSA):
        self.sesion = sesion or requests.Session()
        self.pausa = pausa
        self.ultima = 0.0
        self.peticiones = 0
        self.prohibidas = 0

    def get(self, url: str, seguir: bool = True, cabeceras: dict | None = None, robots: bool = True,
            limite: int = 15 * 1024 * 1024, timeout: float = 30):
        if robots:
            comprobar_robots(url, self.sesion)
        espera = self.pausa - (time.monotonic() - self.ultima)
        if espera > 0:
            time.sleep(espera)
        self.ultima = time.monotonic()
        self.peticiones += 1
        r = self.sesion.get(url, headers={"User-Agent": AGENTE, **(cabeceras or {})}, timeout=timeout,
                            allow_redirects=seguir, stream=True)
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


# ------------------------------------------------------------------------------------------- tipos de página

def normalizar(url: str, host: str) -> str | None:
    """Dirección interna sin fragmento; None si es de otro sitio o no es una página."""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or p.netloc.lower().removeprefix("www.") != host:
        return None
    if EXT_NO_HTML.search(p.path):
        return None
    return urlunparse(("https", p.netloc.lower(), p.path or "/", "", p.query, ""))


def segmentos(url: str) -> list[str]:
    return [s for s in urlparse(url).path.split("/") if s]


def aprender_tipos(urls: list[str], minimo_distintos: int = 8) -> dict:
    """Plantilla de dirección de cada grupo (primer segmento y profundidad): las posiciones con muchos valores
    distintos son variables ({s3}); los años, {año}; los números, {n}; el resto, literales."""
    grupos: dict = collections.defaultdict(list)
    for u in urls:
        s = segmentos(u)
        grupos[(s[0] if s else "", len(s))].append(s)
    variables = {}
    for clave, lista in grupos.items():
        n = len(lista)
        var = set()
        for i in range(1, clave[1]):
            distintos = len({s[i] for s in lista})
            if distintos >= minimo_distintos or (n >= 4 and distintos / n > 0.5 and distintos > 2):
                var.add(i)
        variables[clave] = var
    return variables


def tipo_de(url: str, variables: dict) -> str:
    s = segmentos(url)
    if not s:
        return "/"
    var = variables.get((s[0], len(s)), set(range(1, len(s))))
    partes = []
    for i, x in enumerate(s):
        if ANO.match(x):
            partes.append("{año}")
        elif NUMERO.match(x):
            partes.append("{n}")
        elif i in var:
            partes.append("{s%d}" % (i + 1))
        else:
            partes.append(x)
    return "/" + "/".join(partes) + "/"


# ----------------------------------------------------------------------------------------------- sitemaps

def leer_sitemaps(cliente: Cliente, mapas: list[str], max_archivos: int = 400) -> dict:
    filas, archivos, errores = [], [], []
    pendientes, vistos = list(mapas), set()
    con_imagenes = 0
    while pendientes and len(vistos) < max_archivos:
        m = pendientes.pop(0)
        if m in vistos:
            continue
        vistos.add(m)
        try:
            r, datos = cliente.get(m)
            raiz = etree.fromstring(datos)
        except RobotsProhibe:
            errores.append(f"{m}: robots.txt lo prohíbe a nuestro agente")
            continue
        except Exception as e:  # XML roto, red…
            errores.append(f"{m}: {type(e).__name__}")
            continue
        if etree.QName(raiz).localname == "sitemapindex":
            hijos = [(e.findtext("{*}loc") or "").strip() for e in raiz.findall("{*}sitemap")]
            archivos.append({"sitemap": m, "indice": True, "hijos": len(hijos)})
            pendientes += [h for h in hijos if h]
            continue
        n = 0
        for e in raiz.findall("{*}url"):
            loc = (e.findtext("{*}loc") or "").strip()
            if not loc:
                continue
            n += 1
            imgs = len(e.findall("{http://www.google.com/schemas/sitemap-image/1.1}image"))
            con_imagenes += imgs > 0
            filas.append({"url": loc, "lastmod": (e.findtext("{*}lastmod") or "").strip(),
                          "changefreq": (e.findtext("{*}changefreq") or "").strip(),
                          "priority": (e.findtext("{*}priority") or "").strip(), "imagenes": imgs,
                          "sitemap": m.rsplit("/", 1)[-1]})
        archivos.append({"sitemap": m, "indice": False, "urls": n, "bytes": len(datos),
                         "comprimido": m.endswith(".gz")})
    return {"filas": filas, "archivos": archivos, "errores": errores, "con_imagenes": con_imagenes}


def resumen_sitemaps(filas: list[dict], variables: dict) -> dict:
    por_tipo: dict = collections.defaultdict(lambda: {"urls": 0, "lastmod": collections.Counter(),
                                                      "anos_en_url": collections.Counter(), "ejemplos": []})
    for f in filas:
        t = tipo_de(f["url"], variables)
        f["tipo"] = t
        x = por_tipo[t]
        x["urls"] += 1
        x["lastmod"][f["lastmod"][:10] or "sin lastmod"] += 1
        anos = [s for s in segmentos(f["url"]) if ANO.match(s)]
        x["anos_en_url"][anos[0] if anos else "-"] += 1
        if len(x["ejemplos"]) < 3:
            x["ejemplos"].append(f["url"])
    salida = {}
    for t, x in sorted(por_tipo.items(), key=lambda kv: -kv[1]["urls"]):
        fechas = sorted(k for k in x["lastmod"] if k != "sin lastmod")
        salida[t] = {"urls": x["urls"], "lastmod_min": fechas[0] if fechas else None,
                     "lastmod_max": fechas[-1] if fechas else None, "fechas_distintas": len(fechas),
                     "fecha_mas_repetida": x["lastmod"].most_common(1)[0] if x["lastmod"] else None,
                     "sin_lastmod": x["lastmod"].get("sin lastmod", 0),
                     "anos_en_url": dict(x["anos_en_url"]), "ejemplos": x["ejemplos"]}
    meses = collections.Counter(f["lastmod"][:7] for f in filas if f["lastmod"])
    return {"tipos": salida, "lastmod_por_mes": dict(sorted(meses.items())),
            "con_changefreq": sum(1 for f in filas if f["changefreq"]),
            "con_priority": sum(1 for f in filas if f["priority"])}


# ------------------------------------------------------------------------------------------------- páginas

def _texto(el) -> str:
    return re.sub(r"\s+", " ", " ".join(el.itertext()) if el is not None else "").strip()


def _zona(a) -> str:
    """Dónde está el enlace: menú, migas, contenido, lateral o pie."""
    for anc in a.iterancestors():
        tag = anc.tag if isinstance(anc.tag, str) else ""
        etiqueta = (anc.get("aria-label") or "").lower()
        clases = (anc.get("class") or "").lower() + " " + (anc.get("id") or "").lower()
        if tag == "nav" and ("miga" in etiqueta or "breadcrumb" in etiqueta or "breadcrumb" in clases):
            return "migas"
        if tag == "footer":
            return "pie"
        if tag == "header":
            return "cabecera"
        if tag == "nav":
            return "menu"
        if tag == "aside":
            return "lateral"
        if tag in ("main", "article"):
            return "contenido"
    return "otro"


def analizar_pagina(html: bytes, url: str, host: str) -> tuple[dict, list[tuple[str, str]], np.ndarray]:
    """Medidas de una página, sus enlaces internos (dirección, zona) y sus tejas de texto (solo en memoria)."""
    crudo = html.decode("utf-8", errors="replace")
    try:
        arbol = lxml.html.document_fromstring(html)
    except (etree.ParserError, ValueError):
        return {"error": "HTML ilegible"}, [], np.empty(0, dtype=np.uint64)
    m: dict = {"bytes_html": len(html)}
    m["titulo"] = (arbol.findtext(".//title") or "").strip()[:160]
    metas = {(x.get("name") or x.get("property") or "").lower(): x.get("content", "")
             for x in arbol.xpath("//meta[@name or @property]")}
    m["descripcion_len"] = len(metas.get("description", ""))
    m["robots"] = metas.get("robots", "")
    m["generador"] = metas.get("generator", "")
    m["og"] = sorted(k for k in metas if k.startswith("og:"))[:12]
    m["twitter"] = bool([k for k in metas if k.startswith("twitter:")])
    m["canonica"] = [x.get("href") for x in arbol.xpath("//link[@rel='canonical']")]
    m["hreflang"] = len(arbol.xpath("//link[@hreflang]"))
    m["preload"] = len(arbol.xpath("//link[@rel='preload' or @rel='preconnect' or @rel='dns-prefetch']"))
    m["manifest"] = bool(arbol.xpath("//link[@rel='manifest']"))
    m["lang"] = arbol.get("lang", "")

    # Datos estructurados
    tipos, faq, migas, fechas_ld = [], 0, [], []
    for bloque in arbol.xpath("//script[@type='application/ld+json']"):
        try:
            d = json.loads(bloque.text or "")
        except ValueError:
            tipos.append("JSON-LD ilegible")
            continue
        pila = [d]
        while pila:
            x = pila.pop()
            if isinstance(x, list):
                pila += x
            elif isinstance(x, dict):
                t = x.get("@type")
                for tt in (t if isinstance(t, list) else [t]):
                    if tt:
                        tipos.append(tt)
                if t == "FAQPage":
                    faq += len(x.get("mainEntity") or [])
                if t == "BreadcrumbList":
                    migas = []
                    for i in x.get("itemListElement") or []:
                        if isinstance(i, dict):
                            item = i.get("item")
                            nombre = i.get("name") or (item.get("name") if isinstance(item, dict) else "")
                            migas.append(str(nombre or "")[:60])
                for k in ("datePublished", "dateModified"):
                    if x.get(k):
                        fechas_ld.append(f"{k}={str(x[k])[:25]}")
                pila += [v for v in x.values() if isinstance(v, (dict, list))]
    m["ld_tipos"] = dict(collections.Counter(tipos))
    m["faq_preguntas"] = faq
    m["migas_ld"] = migas
    m["fechas_ld"] = sorted(set(fechas_ld))[:6]
    m["microdatos"] = sorted({x.get("itemtype", "").rsplit("/", 1)[-1] for x in arbol.xpath("//*[@itemtype]")})

    # Recursos (antes de quitar los scripts)
    scripts = arbol.xpath("//script")
    externos = [s.get("src") for s in scripts if s.get("src")]
    hosts_js = sorted({urlparse(urljoin(url, s)).netloc for s in externos} - {""})
    m["scripts"] = {"total": len(scripts), "externos": len(externos), "en_linea_bytes":
                    sum(len(s.text or "") for s in scripts if not s.get("src") and
                        s.get("type") != "application/ld+json"),
                    "async_o_defer": sum(1 for s in scripts if s.get("async") is not None or s.get("defer") is not None),
                    "modulo": sum(1 for s in scripts if s.get("type") == "module"), "hosts": hosts_js}
    hojas = arbol.xpath("//link[@rel='stylesheet']")
    m["css"] = {"externas": len(hojas), "en_linea_bytes": sum(len(s.text or "") for s in arbol.xpath("//style")),
                "hosts": sorted({urlparse(urljoin(url, h.get("href", ""))).netloc for h in hojas})}
    m["recursos_rutas"] = sorted({"/" + (segmentos(urljoin(url, x))[:1] or [""])[0] + "/"
                                  for x in externos + [h.get("href", "") for h in hojas]
                                  if urlparse(urljoin(url, x)).netloc.removeprefix("www.") == host})[:10]
    bajo = crudo.lower()
    m["tecnologia"] = sorted({v for k, v in MARCAS.items() if k.lower() in bajo})
    m["terceros"] = {g: sorted({k for k in lista if k in bajo}) for g, lista in TERCEROS.items()}
    m["iframes"] = sorted({urlparse(urljoin(url, f.get("src", ""))).netloc for f in arbol.xpath("//iframe")})

    imgs = arbol.xpath("//img")
    exts = collections.Counter((re.search(r"\.([a-z0-9]{3,4})(\?|$)", (i.get("src") or "").lower()) or
                                [None, "otra"])[1] for i in imgs)
    m["imagenes"] = {"total": len(imgs), "con_alt": sum(1 for i in imgs if (i.get("alt") or "").strip()),
                     "lazy": sum(1 for i in imgs if i.get("loading") == "lazy"),
                     "con_medidas": sum(1 for i in imgs if i.get("width") and i.get("height")),
                     "formatos": dict(exts), "picture": len(arbol.xpath("//picture")),
                     "svg_en_linea": len(arbol.xpath("//svg"))}
    entradas = arbol.xpath("//input | //select | //textarea")
    m["formularios"] = {"forms": len(arbol.xpath("//form")), "campos": len(entradas),
                        "correo": sum(1 for i in entradas if "mail" in ((i.get("type") or "") + (i.get("name") or ""))
                                      .lower()),
                        "numericos": sum(1 for i in entradas if (i.get("type") or "") in ("number", "range")),
                        "botones": len(arbol.xpath("//button"))}
    m["details_cerrados"] = len(arbol.xpath("//details[not(@open)]"))
    m["ocultos_hidden"] = len(arbol.xpath("//*[@hidden]"))

    # Enlaces
    enlaces, ext_dom, rels = [], collections.Counter(), collections.Counter()
    zonas = collections.Counter()
    for a in arbol.xpath("//a[@href]"):
        href = a.get("href", "").strip()
        if href.startswith(("mailto:", "tel:", "javascript:")) or href in ("", "#"):
            continue
        absoluta = urljoin(url, href)
        n = normalizar(absoluta, host)
        for r in (a.get("rel") or "").split():
            rels[r] += 1
        if n:
            z = _zona(a)
            enlaces.append((n, z))
            zonas[z] += 1
        else:
            dom = urlparse(absoluta).netloc.lower().removeprefix("www.")
            if dom and dom != host:
                ext_dom[dom] += 1
    m["enlaces"] = {"internos": len(enlaces), "internos_distintos": len({e for e, _ in enlaces}),
                    "con_parametros": sum(1 for e, _ in enlaces if "?" in e),
                    "por_zona": dict(zonas), "externos": sum(ext_dom.values()),
                    "dominios_externos": dict(ext_dom.most_common(15)), "rel": dict(rels)}

    # Texto (sin scripts ni estilos)
    for el in arbol.xpath("//script | //style | //noscript | //template | //svg"):
        el.drop_tree()
    cuerpo = arbol.find("body")
    principal = (arbol.xpath("//main") or arbol.xpath("//article") or [cuerpo])[0]
    texto = _texto(cuerpo)
    texto_p = _texto(principal)
    m["palabras"] = len(texto.split())
    m["palabras_principal"] = len(texto_p.split())
    m["tiene_main"] = bool(arbol.xpath("//main"))
    m["encabezados"] = [(h.tag, _texto(h)[:90]) for h in arbol.xpath("//h1|//h2|//h3")][:45]
    m["h_cuenta"] = {t: len(arbol.xpath(f"//{t}")) for t in ("h1", "h2", "h3", "h4")}
    tablas = arbol.xpath("//table")
    m["tablas"] = [{"filas": len(t.xpath(".//tr")), "columnas": max((len(r.xpath("./th|./td"))
                                                                     for r in t.xpath(".//tr")), default=0),
                    "caption": bool(t.xpath(".//caption"))} for t in tablas][:12]
    m["listas"] = {"ul_ol": len(arbol.xpath("//ul|//ol")), "li": len(arbol.xpath("//li")),
                   "dl": len(arbol.xpath("//dl"))}
    m["parrafos"] = len(arbol.xpath("//p"))
    m["cifras"] = len(re.findall(r"\b\d[\d.,]*\b", texto_p))
    m["importes_euro"] = len(re.findall(r"\d[\d.,]*\s?(?:€|euros?)", texto_p, re.I))
    m["fechas_texto"] = len(re.findall(r"\b\d{1,2}(?: de)? (?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
                                       r"septiembre|setiembre|octubre|noviembre|diciembre)\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b",
                                       texto_p, re.I))
    bajo_t = texto.lower()
    m["actualizado"] = re.findall(r"(?:actualizad[oa]|última actualización|revisad[oa])[^.]{0,60}", texto, re.I)[:3]
    m["time"] = [t.get("datetime") or _texto(t)[:30] for t in arbol.xpath("//time")][:6]
    m["fuentes_citadas"] = sorted({f for f in FUENTES if f in bajo_t + " " + " ".join(ext_dom)})
    m["enlaces_oficiales"] = sorted(d for d in ext_dom if d.endswith((".gob.es", "boe.es", ".gov", "europa.eu"))
                                    or re.search(r"(^|\.)(bop|bo[a-z]{1,3}|dog[cv]?|bocm|regcon)\.", d))
    m["autoria"] = sorted({k for k in ("autor", "redactado por", "revisado por", "escrito por", "equipo", "sobre nosotros",
                                       "quiénes somos", "metodología", "aviso legal", "contacto") if k in bajo_t})
    return m, enlaces, tejas(texto_p)


# -------------------------------------------------------------------------------------------- comprobaciones

def comprobar_servidor(cliente: Cliente, dominio: str, ejemplo: str | None) -> dict:
    s: dict = {}

    def cadena(url):
        pasos = []
        for _ in range(6):
            try:
                r, _ = cliente.get(url, seguir=False, robots=False, limite=4096)
            except requests.RequestException as e:
                pasos.append(f"{url} → error {type(e).__name__}")
                break
            pasos.append(f"{url} → {r.status_code}")
            if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                url = urljoin(url, r.headers["location"])
                continue
            break
        return pasos

    for v in (f"http://{dominio}/", f"http://www.{dominio}/", f"https://www.{dominio}/", f"https://{dominio}/"):
        s[v] = cadena(v)
    try:
        r, _ = cliente.get(f"https://{dominio}/no-existe-{random.randint(10**6, 10**7)}/", limite=200_000)
        s["inexistente"] = {"estado": r.status_code, "cache": r.headers.get("cache-control")}
    except (requests.RequestException, RobotsProhibe) as e:
        s["inexistente"] = {"error": type(e).__name__}
    if ejemplo:
        sin_barra = ejemplo.rstrip("/")
        s["sin_barra_final"] = cadena(sin_barra) if sin_barra != ejemplo else ["ya sin barra"]
        p = urlparse(ejemplo)
        s["mayusculas"] = cadena(urlunparse(p._replace(path=p.path.upper())))
        try:
            r, _ = cliente.get(ejemplo, limite=5_000_000)
            cab = {k.lower(): v for k, v in r.headers.items()}
            s["cabeceras_ejemplo"] = {k: cab.get(k) for k in CAB if k in cab}
            cond = {}
            if cab.get("etag"):
                cond["If-None-Match"] = cab["etag"]
            if cab.get("last-modified"):
                cond["If-Modified-Since"] = cab["last-modified"]
            if cond:
                r2, _ = cliente.get(ejemplo, cabeceras=cond, limite=5_000_000)
                s["respuesta_condicional"] = {"enviado": sorted(cond), "estado": r2.status_code}
            else:
                s["respuesta_condicional"] = {"enviado": [], "estado": "sin ETag ni Last-Modified"}
        except (requests.RequestException, RobotsProhibe) as e:
            s["cabeceras_ejemplo"] = {"error": type(e).__name__}
    for ruta in ("/ads.txt", "/llms.txt", "/llms-full.txt", "/.well-known/security.txt", "/humans.txt",
                 "/manifest.webmanifest", "/site.webmanifest", "/feed.xml", "/rss.xml", "/feed/", "/index.xml"):
        try:
            r, d = cliente.get(f"https://{dominio}{ruta}", limite=400_000)
            tipo = r.headers.get("content-type", "")
            info = {"estado": r.status_code, "tipo": tipo.split(";")[0], "bytes": len(d)}
            if ruta == "/ads.txt" and r.status_code == 200 and "html" not in tipo:
                lineas = [l.split("#")[0].strip() for l in d.decode("utf-8", "replace").splitlines()]
                filas = [l.split(",") for l in lineas if l.count(",") >= 2]
                info["vendedores"] = dict(collections.Counter(f[0].strip().lower() for f in filas).most_common(30))
                info["directos"] = sum(1 for f in filas if f[2].strip().upper() == "DIRECT")
                info["revendedores"] = sum(1 for f in filas if f[2].strip().upper() == "RESELLER")
                info["otras_lineas"] = [l for l in lineas if l and l.count(",") < 2][:10]
            if ruta.startswith("/llms") and r.status_code == 200 and "html" not in tipo:
                info["lineas"] = len(d.splitlines())
            s[ruta] = info
        except (requests.RequestException, RobotsProhibe) as e:
            s[ruta] = {"error": type(e).__name__}
    return s


def edad_y_popularidad(sesion, dominio: str) -> dict:
    cab = {"User-Agent": AGENTE}
    e: dict = {}
    try:
        r = sesion.get(f"https://rdap.org/domain/{dominio}", headers=cab, timeout=60)
        d = r.json() if r.status_code == 200 else {}
        e["rdap"] = {"estado": r.status_code,
                     "eventos": {x.get("eventAction"): x.get("eventDate") for x in d.get("events", [])},
                     "registrador": next((v[3] for ent in d.get("entities", []) if "registrar" in ent.get("roles", [])
                                          for v in (ent.get("vcardArray") or [None, []])[1] if v and v[0] == "fn"),
                                         None),
                     "servidores_dns": [n.get("ldhName") for n in d.get("nameservers", [])]}
    except (requests.RequestException, ValueError) as x:
        e["rdap"] = {"error": type(x).__name__}
    try:
        r = sesion.get("https://crt.sh/", params={"q": dominio, "output": "json"}, headers=cab, timeout=90)
        certs = r.json() if r.status_code == 200 else []
        nombres = collections.Counter()
        for c in certs:
            for n in (c.get("name_value") or "").split("\n"):
                nombres[n.strip().lower()] += 1
        desde = sorted(c.get("not_before", "") for c in certs if c.get("not_before"))
        e["certificados"] = {"estado": r.status_code, "total": len(certs), "primero": desde[0] if desde else None,
                             "ultimo": desde[-1] if desde else None, "nombres": dict(nombres.most_common(25)),
                             "emisores": dict(collections.Counter((c.get("issuer_name") or "")
                                                                  .split("O=")[-1].split(",")[0]
                                                                  for c in certs).most_common(5))}
    except (requests.RequestException, ValueError) as x:
        e["certificados"] = {"error": type(x).__name__}
    try:
        r = sesion.get("https://web.archive.org/cdx/search/cdx", headers=cab, timeout=120,
                       params={"url": dominio, "matchType": "domain", "output": "json", "fl": "timestamp,original,statuscode",
                               "collapse": "timestamp:8", "limit": "5000"})
        filas = r.json()[1:] if r.status_code == 200 and r.content.strip() else []
        e["wayback"] = {"capturas_dias": len(filas), "primera": filas[0][0] if filas else None,
                        "primera_url": filas[0][1] if filas else None,
                        "por_mes": dict(sorted(collections.Counter(f[0][:6] for f in filas).items()))}
    except (requests.RequestException, ValueError) as x:
        e["wayback"] = {"error": type(x).__name__}
    try:
        indices = sesion.get("https://index.commoncrawl.org/collinfo.json", headers=cab, timeout=60).json()[:8]
        cc = {}
        for ind in indices:
            r = sesion.get(ind["cdx-api"], params={"url": f"{dominio}/*", "output": "json", "limit": "3000",
                                                   "fl": "url"}, headers=cab, timeout=120)
            cc[ind["id"]] = len([l for l in r.text.splitlines() if l.startswith("{")]) if r.status_code == 200 else \
                f"HTTP {r.status_code}"
            time.sleep(1)
        e["commoncrawl"] = cc
    except (requests.RequestException, ValueError, KeyError) as x:
        e["commoncrawl"] = {"error": type(x).__name__}
    try:
        r = sesion.get(f"https://tranco-list.eu/api/ranks/domain/{dominio}", headers=cab, timeout=60)
        d = r.json() if r.status_code == 200 else {}
        ranks = d.get("ranks") or []
        e["tranco"] = {"estado": r.status_code, "dias_en_lista": len(ranks),
                       "mejor": min((x.get("rank") for x in ranks), default=None),
                       "ultimo": ranks[-1] if ranks else None, "primero": ranks[0] if ranks else None}
    except (requests.RequestException, ValueError) as x:
        e["tranco"] = {"error": type(x).__name__}
    return e


def crux(sesion, origen: str) -> dict:
    clave = os.environ.get("CRUX_API_KEY", "").strip()
    salida = {}
    if clave:
        for factor in ("PHONE", "DESKTOP"):
            try:
                r = sesion.post("https://chromeuxreport.googleapis.com/v1/records:queryRecord", params={"key": clave},
                                json={"origin": origen, "formFactor": factor}, timeout=60)
                if r.status_code != 200:
                    salida[factor] = {"estado": r.status_code}
                    continue
                met = r.json().get("record", {}).get("metrics", {})
                salida[factor] = {k: v.get("percentiles", {}).get("p75") for k, v in met.items()}
            except (requests.RequestException, ValueError) as x:
                salida[factor] = {"error": type(x).__name__}
        return {"fuente": "CrUX API"} | salida
    from motor.seo.competencia import velocidad
    return {"fuente": "PageSpeed Insights sin clave"} | velocidad(sesion, origen + "/")


def laboratorio(urls: list[str]) -> list[dict]:
    """LCP, CLS, peso y peticiones en móvil lento con Chromium; palabras sin y con JavaScript."""
    from playwright.sync_api import sync_playwright

    from motor.seo.renderizado import MEDIDOR, MOVIL, RED_LENTA

    salida = []
    with sync_playwright() as p:
        nav = p.chromium.launch()
        for url in urls:
            try:
                ctx = nav.new_context(**MOVIL)
                pagina = ctx.new_page()
                peticiones = []
                pagina.on("requestfinished", lambda q: peticiones.append(q))
                cdp = ctx.new_cdp_session(pagina)
                cdp.send("Network.enable")
                cdp.send("Network.emulateNetworkConditions", RED_LENTA)
                cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
                pagina.add_init_script(MEDIDOR)
                t0 = time.monotonic()
                pagina.goto(url, wait_until="load", timeout=90_000)
                carga = time.monotonic() - t0
                pagina.wait_for_timeout(4000)
                cwv = pagina.evaluate("window.__cwv")
                nav_t = pagina.evaluate("JSON.stringify(performance.getEntriesByType('navigation')[0] || {})")
                pintado = pagina.evaluate("JSON.stringify(performance.getEntriesByType('paint'))")
                palabras_dom = pagina.evaluate("(document.body.innerText || '').split(/\\s+/).filter(Boolean).length")
                host = urlparse(url).netloc
                tipos, bytes_tipo, terceros = collections.Counter(), collections.Counter(), collections.Counter()
                total = 0
                for q in peticiones:
                    try:
                        tam = (q.sizes() or {}).get("responseBodySize", 0) or 0
                    except Exception:
                        tam = 0
                    total += tam
                    tipos[q.resource_type] += 1
                    bytes_tipo[q.resource_type] += tam
                    h = urlparse(q.url).netloc
                    if h and h != host:
                        terceros[h] += 1
                navj = json.loads(nav_t)
                fcp = next((x["startTime"] for x in json.loads(pintado) if x.get("name") == "first-contentful-paint"),
                           None)
                salida.append({"url": url, "lcp_ms": round(cwv["lcp"]), "cls": round(cwv["cls"], 4),
                               "fcp_ms": round(fcp) if fcp else None,
                               "ttfb_ms": round(navj.get("responseStart", 0)) if navj else None,
                               "carga_s": round(carga, 2), "peticiones": len(peticiones),
                               "bytes": total, "por_tipo": dict(tipos), "bytes_por_tipo": dict(bytes_tipo),
                               "terceros": dict(terceros.most_common(20)), "palabras_con_js": palabras_dom})
                ctx.close()
            except Exception as x:  # una página que no carga no para el resto
                salida.append({"url": url, "error": f"{type(x).__name__}: {str(x)[:200]}"})
        nav.close()
    return salida


# ------------------------------------------------------------------------------------------------- análisis

def parecido_por_tipo(tejas_por_tipo: dict[str, list]) -> dict:
    """Cuánto texto comparten las páginas de un mismo tipo: media de Jaccard por pares y parte común a todas."""
    salida = {}
    for t, lista in tejas_por_tipo.items():
        lista = [x for x in lista if len(x)]
        if len(lista) < 2:
            continue
        pares = [jaccard(a, b) for i, a in enumerate(lista[:25]) for b in lista[i + 1:25]]
        comun = lista[0]
        for x in lista[1:]:
            comun = np.intersect1d(comun, x, assume_unique=True)
        media = sum(len(x) for x in lista) / len(lista)
        salida[t] = {"paginas": len(lista), "jaccard_medio": round(sum(pares) / len(pares), 3),
                     "jaccard_max": round(max(pares), 3),
                     "parte_comun_a_todas": round(len(comun) / media, 3) if media else None}
    return salida


def rastrear(cliente: Cliente, inicio: str, host: str, variables: dict, max_paginas: int, por_tipo_max: int,
             en_sitemap: set) -> tuple[list[dict], dict[str, list], list[str]]:
    """Anchura desde la portada, con tope por tipo para ver todos los tipos y no solo el más numeroso."""
    cola = collections.deque([(inicio, 0, None)])
    vistos = {inicio}
    paginas, tejas_tipo, errores = [], collections.defaultdict(list), []
    por_tipo = collections.Counter()
    while cola and len(paginas) < max_paginas:
        url, prof, desde = cola.popleft()
        t = tipo_de(url, variables)
        if por_tipo[t] >= por_tipo_max and url != inicio:
            continue
        try:
            r, html = cliente.get(url)
        except RobotsProhibe:
            cliente.prohibidas += 1
            continue
        except requests.RequestException as e:
            errores.append(f"{url}: {type(e).__name__}")
            continue
        final = normalizar(r.url, host) or r.url
        info = {"url": url, "final": final, "estado": r.status_code, "profundidad": prof, "tipo": t,
                "en_sitemap": url in en_sitemap, "desde": desde,
                "cabeceras": {k: r.headers.get(k) for k in ("cache-control", "cf-cache-status", "age",
                                                             "last-modified", "etag", "x-robots-tag")
                              if r.headers.get(k)}}
        if r.status_code != 200 or "html" not in r.headers.get("content-type", ""):
            paginas.append(info)
            continue
        por_tipo[t] += 1
        medidas, enlaces, tj = analizar_pagina(html, final, host)
        info |= medidas
        destinos = collections.Counter()
        zonas_tipo = collections.Counter()
        for dest, zona in enlaces:
            td = tipo_de(dest, variables)
            destinos[td] += 1
            zonas_tipo[f"{td}|{zona}"] += 1
            if dest not in vistos:
                vistos.add(dest)
                cola.append((dest, prof + 1, url))
        info["enlaces_a_tipos"] = dict(destinos)
        info["enlaces_tipo_zona"] = dict(zonas_tipo)
        info["destinos"] = sorted({d for d, _ in enlaces})
        tejas_tipo[t].append(tj)
        paginas.append(info)
    return paginas, tejas_tipo, errores


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Anatomía de un sitio de SEO programático")
    p.add_argument("--dominio", required=True)
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--max-paginas", type=int, default=450)
    p.add_argument("--por-tipo", type=int, default=40, help="tope de páginas analizadas por tipo en el rastreo")
    p.add_argument("--muestra-tipo", type=int, default=4, help="páginas por tipo de sitemap que faltan por ver")
    p.add_argument("--navegador", action="store_true")
    a = p.parse_args(argv)
    dominio = a.dominio.lower().removeprefix("www.")
    a.salida.mkdir(parents=True, exist_ok=True)
    cliente = Cliente()
    rng = random.Random(20261031)
    res: dict = {"dominio": dominio, "medido": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "agente": AGENTE}

    print("edad y popularidad…", flush=True)
    res["edad"] = edad_y_popularidad(cliente.sesion, dominio)

    r, d = cliente.get(f"https://{dominio}/robots.txt", robots=False)
    base = urlparse(r.url)
    origen = f"{base.scheme}://{base.netloc}"
    host = base.netloc.lower().removeprefix("www.")
    texto_robots = d.decode("utf-8", "replace") if r.status_code == 200 else ""
    res["robots"] = {"estado": r.status_code, "texto": texto_robots[:5000]} | robots_info(texto_robots)

    print("sitemaps…", flush=True)
    mapas = res["robots"]["sitemaps"] or [origen + "/sitemap.xml"]
    sm = leer_sitemaps(cliente, mapas)
    filas = sm["filas"]
    variables = aprender_tipos([f["url"] for f in filas])
    res["sitemaps"] = {"archivos": sm["archivos"], "errores": sm["errores"], "urls": len(filas),
                       "urls_distintas": len({f["url"] for f in filas}), "con_imagenes": sm["con_imagenes"]} | \
        resumen_sitemaps(filas, variables)
    with gzip.open(a.salida / "sitemap.csv.gz", "wt", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["url", "tipo", "lastmod", "changefreq", "priority", "imagenes", "sitemap"])
        for x in filas:
            w.writerow([x["url"], x["tipo"], x["lastmod"], x["changefreq"], x["priority"], x["imagenes"],
                        x["sitemap"]])
    en_sitemap = {normalizar(f["url"], host) for f in filas}

    print("rastreo desde la portada…", flush=True)
    paginas, tejas_tipo, errores = rastrear(cliente, origen + "/", host, variables, a.max_paginas, a.por_tipo,
                                            en_sitemap)
    vistos = {x["url"] for x in paginas}
    # Tipos de los sitemaps que el rastreo no vio lo bastante
    analizados = collections.Counter(x["tipo"] for x in paginas if "palabras" in x)
    por_tipo_urls = collections.defaultdict(list)
    for f in filas:
        por_tipo_urls[f["tipo"]].append(normalizar(f["url"], host))
    for t, urls in por_tipo_urls.items():
        faltan = a.muestra_tipo - analizados[t]
        candidatas = [u for u in urls if u and u not in vistos]
        for u in rng.sample(candidatas, min(len(candidatas), max(0, faltan))):
            try:
                r, html = cliente.get(u)
            except (RobotsProhibe, requests.RequestException) as e:
                errores.append(f"{u}: {type(e).__name__}")
                continue
            info = {"url": u, "final": r.url, "estado": r.status_code, "profundidad": None, "tipo": t,
                    "en_sitemap": True, "desde": "sitemap"}
            if r.status_code == 200 and "html" in r.headers.get("content-type", ""):
                medidas, enlaces, tj = analizar_pagina(html, r.url, host)
                info |= medidas
                info["enlaces_a_tipos"] = dict(collections.Counter(tipo_de(dd, variables) for dd, _ in enlaces))
                info["enlaces_tipo_zona"] = dict(collections.Counter(f"{tipo_de(dd, variables)}|{z}"
                                                                     for dd, z in enlaces))
                info["destinos"] = sorted({dd for dd, _ in enlaces})
                tejas_tipo[t].append(tj)
            paginas.append(info)

    with open(a.salida / "paginas.jsonl", "w", encoding="utf-8") as f:
        for x in paginas:
            f.write(json.dumps({k: v for k, v in x.items() if k != "destinos"}, ensure_ascii=False) + "\n")
    with open(a.salida / "enlaces.jsonl", "w", encoding="utf-8") as f:
        for x in paginas:
            if x.get("destinos") is not None:
                f.write(json.dumps({"url": x["url"], "tipo": x["tipo"], "profundidad": x["profundidad"],
                                    "destinos": x["destinos"]}, ensure_ascii=False) + "\n")

    prof = collections.defaultdict(list)
    for x in paginas:
        if x.get("profundidad") is not None:
            prof[x["tipo"]].append(x["profundidad"])
    res["rastreo"] = {"paginas": len(paginas), "analizadas": sum(1 for x in paginas if "palabras" in x),
                      "peticiones": cliente.peticiones, "prohibidas_por_robots": cliente.prohibidas,
                      "errores": errores[:50],
                      "estados": dict(collections.Counter(x["estado"] for x in paginas)),
                      "fuera_de_sitemap": sorted({x["url"] for x in paginas if not x["en_sitemap"]})[:200],
                      "profundidad_minima_por_tipo": {t: min(v) for t, v in prof.items()}}
    res["parecido_por_tipo"] = parecido_por_tipo(tejas_tipo)

    print("servidor…", flush=True)
    ejemplo = next((x["url"] for x in paginas if x.get("estado") == 200 and x["url"] != origen + "/"), None)
    res["servidor"] = comprobar_servidor(cliente, dominio, ejemplo)
    res["velocidad_real"] = crux(cliente.sesion, origen)
    if a.navegador:
        print("laboratorio con Chromium…", flush=True)
        urls = [origen + "/"]
        for t in list(res["sitemaps"]["tipos"])[:6]:
            u = next((x["url"] for x in paginas if x["tipo"] == t and x.get("estado") == 200), None)
            if u and u not in urls:
                urls.append(u)
        res["laboratorio"] = laboratorio(urls)
    (a.salida / "anatomia.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str),
                                            encoding="utf-8")
    print(f"{dominio}: {len(filas)} direcciones en sitemaps, {len(res['sitemaps']['tipos'])} tipos, "
          f"{res['rastreo']['analizadas']} páginas analizadas, {cliente.peticiones} peticiones", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
