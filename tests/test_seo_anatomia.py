"""Pruebas de motor/seo/anatomia.py sin red: tipos de página, medidas de una página, sitemaps y rastreo."""

import gzip

from motor.seo import anatomia

HTML = """<!doctype html><html lang="es"><head><title>Calendario laboral 2026 de Baena</title>
<meta name="description" content="Festivos de Baena">
<link rel="canonical" href="https://ejemplo.com/calendario-laboral/2026/cordoba/baena/">
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[
 {"@type":"FAQPage","mainEntity":[{"@type":"Question","name":"a"},{"@type":"Question","name":"b"}]},
 {"@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Inicio"},
  {"@type":"ListItem","position":2,"item":{"@id":"x","name":"Calendario"}}]}]}</script>
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js"></script>
<script src="/_astro/app.js" type="module"></script>
</head><body>
<header><nav><a href="/">Inicio</a><a href="/sueldos/">Sueldos</a></nav></header>
<nav aria-label="Migas de pan"><a href="/calendario-laboral/2026/">2026</a></nav>
<main><h1>Calendario laboral 2026 de Baena</h1><p>Actualizado el 3 de marzo de 2026. Fuente: BOE.</p>
<table><tr><th>Fecha</th><th>Fiesta</th></tr><tr><td>1 de enero</td><td>Año Nuevo</td></tr></table>
<a href="/calendario-laboral/2026/cordoba/lucena/">Lucena</a>
<a href="https://www.boe.es/x" rel="nofollow">BOE</a><img src="/a.webp" alt="mapa" loading="lazy"></main>
<footer><a href="/aviso-legal/">Aviso legal</a></footer></body></html>""".encode()


def test_tipos_de_pagina():
    urls = [f"https://ejemplo.com/calendario-laboral/{a}/{p}/{p}-{m}/" for a in (2026, 2027)
            for p in ("cordoba", "jaen", "sevilla", "huelva", "cadiz", "malaga", "almeria", "granada", "soria") for m in ("x1", "x2", "x3", "x4")]
    urls += [f"https://ejemplo.com/sueldos/{o}/2026/" for o in ("a", "b", "c", "d", "e", "f", "g", "h", "i")]
    urls += ["https://ejemplo.com/aviso-legal/"]
    v = anatomia.aprender_tipos(urls)
    assert anatomia.tipo_de(urls[0], v) == "/calendario-laboral/{año}/{s3}/{s4}/"
    assert anatomia.tipo_de("https://ejemplo.com/sueldos/carpintero/2026/", v) == "/sueldos/{s2}/{año}/"
    assert anatomia.tipo_de("https://ejemplo.com/aviso-legal/", v) == "/aviso-legal/"
    assert anatomia.tipo_de("https://ejemplo.com/", v) == "/"


def test_normalizar():
    assert anatomia.normalizar("https://www.ejemplo.com/a/#x", "ejemplo.com") == "https://www.ejemplo.com/a/"
    assert anatomia.normalizar("https://otro.com/a/", "ejemplo.com") is None
    assert anatomia.normalizar("https://ejemplo.com/img/a.png", "ejemplo.com") is None


def test_analizar_pagina():
    m, enlaces, tj = anatomia.analizar_pagina(HTML, "https://ejemplo.com/calendario-laboral/2026/cordoba/baena/",
                                              "ejemplo.com")
    assert m["faq_preguntas"] == 2
    assert m["migas_ld"] == ["Inicio", "Calendario"]
    assert m["ld_tipos"]["FAQPage"] == 1
    assert "Astro" in m["tecnologia"]
    assert "adsbygoogle" in m["terceros"]["anuncios"]
    assert m["tablas"][0] == {"filas": 2, "columnas": 2, "caption": False}
    assert "boe.es" in m["fuentes_citadas"] and m["enlaces_oficiales"] == ["boe.es"]
    assert m["actualizado"] and m["fechas_texto"] >= 2
    assert m["imagenes"]["lazy"] == 1 and m["imagenes"]["formatos"] == {"webp": 1}
    zonas = dict((u.rsplit("/", 2)[-2] or "raiz", z) for u, z in enlaces)
    assert zonas["lucena"] == "contenido" and zonas["aviso-legal"] == "pie" and zonas["2026"] == "migas"
    assert zonas["sueldos"] == "menu"
    assert m["enlaces"]["dominios_externos"] == {"boe.es": 1} and m["enlaces"]["rel"] == {"nofollow": 1}
    assert len(tj) > 5


class _Resp:
    def __init__(self, url, cuerpo, estado=200, tipo="text/html"):
        self.url, self.status_code, self._c = url, estado, cuerpo
        self.headers = {"content-type": tipo}

    def iter_content(self, n):
        yield self._c

    def close(self):
        pass


class _Sesion:
    def __init__(self, paginas):
        self.paginas = paginas

    def get(self, url, **kw):
        if url in self.paginas:
            return _Resp(url, *self.paginas[url])
        return _Resp(url, b"no", 404)


def test_sitemaps_y_rastreo(monkeypatch):
    monkeypatch.setattr(anatomia, "comprobar_robots", lambda url, sesion=None: None)
    indice = b"""<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://ejemplo.com/s1.xml.gz</loc></sitemap></sitemapindex>"""
    hoja = gzip.compress(b"""<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://ejemplo.com/</loc><lastmod>2026-10-01</lastmod></url>
      <url><loc>https://ejemplo.com/calendario-laboral/2026/cordoba/baena/</loc><lastmod>2026-10-02</lastmod></url>
      </urlset>""")
    portada = b'<html><body><main><a href="/calendario-laboral/2026/cordoba/baena/">Baena</a></main></body></html>'
    sesion = _Sesion({"https://ejemplo.com/sitemap.xml": (indice, 200, "application/xml"),
                      "https://ejemplo.com/s1.xml.gz": (hoja, 200, "application/gzip"),
                      "https://ejemplo.com/": (portada,),
                      "https://ejemplo.com/calendario-laboral/2026/cordoba/baena/": (HTML,)})
    cliente = anatomia.Cliente(sesion, pausa=0)
    sm = anatomia.leer_sitemaps(cliente, ["https://ejemplo.com/sitemap.xml"])
    assert len(sm["filas"]) == 2 and sm["archivos"][0]["indice"]
    v = anatomia.aprender_tipos([f["url"] for f in sm["filas"]])
    res = anatomia.resumen_sitemaps(sm["filas"], v)
    assert sum(t["urls"] for t in res["tipos"].values()) == 2
    assert res["lastmod_por_mes"] == {"2026-10": 2}
    paginas, tejas_tipo, errores = anatomia.rastrear(cliente, "https://ejemplo.com/", "ejemplo.com", v, 10, 5,
                                                     {f["url"] for f in sm["filas"]})
    assert [p["profundidad"] for p in paginas if p["estado"] == 200] == [0, 1]
    assert any(p["estado"] == 404 for p in paginas)  # enlaces del menú que no existen en el ejemplo
    baena = next(p for p in paginas if "baena" in p["url"])
    assert baena["en_sitemap"] and baena["faq_preguntas"] == 2


def test_parecido_por_tipo():
    from motor.seo.similitud import tejas
    a = tejas("calendario laboral de baena con sus fiestas locales del año y la tabla de festivos nacionales")
    b = tejas("calendario laboral de lucena con sus fiestas locales del año y la tabla de festivos nacionales")
    r = anatomia.parecido_por_tipo({"/x/": [a, b]})
    assert 0 < r["/x/"]["jaccard_medio"] < 1 and r["/x/"]["parte_comun_a_todas"] > 0.5
