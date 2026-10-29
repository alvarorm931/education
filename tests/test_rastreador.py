import xml.etree.ElementTree as ET

from motor.estudios import rastreador as r


def test_es_programa():
    assert r.es_programa("https://www.ucm.es/estudios/2026-27/titulo-propio?eid=3329")
    assert r.es_programa("https://www.esic.edu/postgrado/master-en-direccion-de-marketing")
    assert r.es_programa("https://x.es/formacion-permanente/experto-universitario-en-compliance/")
    assert not r.es_programa("https://x.es/noticias/abierto-el-plazo-del-master-en-finanzas/")
    assert not r.es_programa("https://x.es/docs/master-folleto.pdf")
    assert not r.es_programa("https://x.es/grado/derecho/")


def test_sitemap_indice_y_paginas():
    ns = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
    idx = ET.fromstring(f'<sitemapindex {ns}><sitemap><loc>https://x.es/s1.xml</loc></sitemap></sitemapindex>')
    assert r.urls_de_sitemap(idx) == (["https://x.es/s1.xml"], [])
    pag = ET.fromstring(f'<urlset {ns}><url><loc>https://x.es/master-a</loc></url></urlset>')
    assert r.urls_de_sitemap(pag) == ([], ["https://x.es/master-a"])
    assert r.prioridad_sitemap("https://x.es/post-sitemap.xml") > r.prioridad_sitemap("https://x.es/masters-sitemap.xml")


def test_medir_pagina():
    html = ('<html><title>Máster en Finanzas</title><script type="application/ld+json">'
            '{"@type":"Course","name":"Máster","offers":{"@type":"Offer","price":"9900","priceCurrency":"EUR"}}</script>'
            '<p>Precio: 9.900 € · 40 plazas · Becas del 20 %</p><a href="/docs/programa-master.pdf">Descarga el programa</a>'
            '<form><input type="email" name="email"><input type="tel" name="telefono"></form></html>')
    m = r.medir_pagina(html, "https://x.es/master-finanzas")
    assert m["jsonld_tipos"] == ["Course"] and m["precio_jsonld"] == {"precio": "9900", "moneda": "EUR"}
    assert m["importes_euros"] == 1 and m["temas"]["plazas"] and m["temas"]["becas"]
    assert m["formulario_pide_correo"] and m["formulario_pide_telefono"]
    assert m["pdf_guia_o_folleto"] == ["https://x.es/docs/programa-master.pdf"]


def test_robots_se_lee_y_se_respeta(monkeypatch):
    class R:
        def __init__(self, status, text, ctype="text/plain"):
            self.status_code, self.text, self.content, self.headers = status, text, text.encode(), {"content-type": ctype}

    pedidas = []

    def falso_get(self, url, timeout=25, allow_redirects=True):
        pedidas.append(url)
        if url.endswith("/robots.txt"):
            return R(200, "User-agent: *\nDisallow: /privado/\nSitemap: https://x.es/sm.xml\n")
        return R(200, "<html></html>", "text/html")

    monkeypatch.setattr(r.requests.Session, "get", falso_get)
    d = r.Dominio("https://x.es", None, pausa=0)
    assert d.leer_robots() == ["https://x.es/sm.xml"]
    assert d.get("https://x.es/privado/master") is None
    assert d.get("https://x.es/master-en-finanzas") is not None
    assert pedidas == ["https://x.es/robots.txt", "https://x.es/master-en-finanzas"]


def test_sin_sitemap_usa_enlaces_de_portada(monkeypatch):
    class R:
        def __init__(self, status, text, ctype="text/html", url=""):
            self.status_code, self.text, self.content, self.headers, self.url = status, text, text.encode(), {"content-type": ctype}, url

    portada = ('<a href="/masters/master-en-finanzas">Máster</a><a href="/blog/2024/05/x-master">blog</a>'
               '<a href="https://otro.com/master-en-y">fuera</a>')
    ficha = ("<title>Máster en Finanzas</title><h1>Máster en Finanzas</h1><p>60 ECTS. Precio 9.000 €. "
             "Plazas limitadas. Admisión abierta. Matrícula. Plan de estudios. Madrid</p>")

    def falso_get(self, url, timeout=25, allow_redirects=True):
        if url.endswith("/robots.txt"):
            return R(200, "User-agent: *\nAllow: /\n", "text/plain", url)
        if url.endswith(".xml"):
            return R(404, "", "text/html", url)
        if url == "https://x.es/":
            return R(200, portada, url=url)
        return R(200, ficha, url=url)

    monkeypatch.setattr(r.requests.Session, "get", falso_get)
    res = r.rastrear("https://x.es", None, muestra=3, pausa=0)
    assert res["via"] == "portada"
    assert res["programas"] == ["https://x.es/masters/master-en-finanzas"]
    assert res["verificado"] and res["espana"]


def test_lastmod_y_reserva_tdm():
    ns = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
    raiz = ET.fromstring(f'<urlset {ns}><url><loc>https://x.es/master-a</loc><lastmod>2026-09-01</lastmod></url>'
                         f'<url><loc>https://x.es/master-b</loc></url></urlset>')
    assert r.fechas_de_sitemap(raiz) == {"https://x.es/master-a": "2026-09-01"}
    assert r.reserva_tdm({"tdm-reservation": "1"}, "")
    assert r.reserva_tdm({}, '<meta name="tdm-reservation" content="1">')
    assert not r.reserva_tdm({}, "<html></html>")


def test_pdf_de_precios():
    html = '<a href="/docs/Tarifas_Postgrado_2026.pdf">Tarifas</a><a href="/docs/folleto.pdf">Descarga el folleto</a>'
    m = r.medir_pagina(html, "https://x.es/master")
    assert m["pdf_precio"] == ["https://x.es/docs/Tarifas_Postgrado_2026.pdf"]
