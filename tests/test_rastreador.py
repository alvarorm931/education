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


class _R:
    def __init__(self, status, cuerpo, ctype="text/html", url=""):
        self.status_code, self.headers, self.url = status, {"content-type": ctype}, url
        self.content = cuerpo if isinstance(cuerpo, bytes) else cuerpo.encode()
        self.text = self.content.decode("latin-1")  # lo que haría requests sin charset en la cabecera


def test_texto_de_corrige_la_codificacion():
    r1 = _R(200, "<title>Máster Universitario</title>".encode("utf-8"))
    assert r1.text != "<title>Máster Universitario</title>"  # el fallo que había: «MÃ¡ster»
    assert r.texto_de(r1) == "<title>Máster Universitario</title>"
    r2 = _R(200, '<meta charset="iso-8859-1"><p>Máster</p>'.encode("latin-1"))
    assert "Máster" in r.texto_de(r2)


def test_redireccion_a_otro_dominio_y_www(monkeypatch):
    """ub.es no responde; www.ub.es redirige a www.ub.edu, que es la web real: sus programas cuentan."""
    ns = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
    sm = f'<urlset {ns}><url><loc>https://www.ub.edu/estudis/masters/master-en-dret</loc></url></urlset>'
    ficha = ("<title>Màster en Dret</title><h1>Màster universitari en Dret</h1><p>60 crèdits ECTS. Preu: 2.100 €. "
             "Places: 40. Preinscripció i admissió. Pla d'estudis. Barcelona</p>")

    def falso_get(self, url, timeout=25, allow_redirects=True):
        if url.startswith("https://ub.es"):
            raise r.requests.ConnectionError("sin DNS")
        if url == "https://www.ub.es/robots.txt":
            return _R(200, "User-agent: *\nAllow: /\nSitemap: https://www.ub.edu/sm.xml\n", "text/plain",
                      "https://www.ub.edu/robots.txt")
        if url == "https://www.ub.edu/sm.xml":
            return _R(200, sm, "application/xml", url)
        if url.endswith("tdmrep.json"):
            return _R(404, "", "text/html", url)
        return _R(200, ficha.encode("utf-8"), "text/html", url)

    monkeypatch.setattr(r.requests.Session, "get", falso_get)
    res = r.rastrear("https://ub.es", None, muestra=2, pausa=0)
    assert res["base_final"] == "https://www.ub.edu"
    assert res["dominios_propios"] == ["ub.edu", "ub.es"]
    assert res["programas"] == ["https://www.ub.edu/estudis/masters/master-en-dret"]
    assert res["verificado"] and res["espana"] and res["dominio"] == "ub.es"


def test_robots_por_servidor_y_error_de_servidor(monkeypatch):
    pedidas = []

    def falso_get(self, url, timeout=25, allow_redirects=True):
        pedidas.append(url)
        if url == "https://x.es/robots.txt":
            return _R(200, "User-agent: *\nAllow: /\n", "text/plain", url)
        if url == "https://postgrado.x.es/robots.txt":
            return _R(200, "User-agent: *\nDisallow: /\n", "text/plain", url)
        if url == "https://caido.x.es/robots.txt":
            return _R(503, "", "text/html", url)
        return _R(200, "<html></html>", "text/html", url)

    monkeypatch.setattr(r.requests.Session, "get", falso_get)
    d = r.Dominio("https://x.es", None, pausa=0)
    d.leer_robots()
    assert d.get("https://x.es/master") is not None
    assert d.get("https://postgrado.x.es/master-en-y") is None  # su propio robots.txt lo prohíbe
    assert d.get("https://caido.x.es/master") is None  # robots.txt con error de servidor: no se rastrea
    assert "https://postgrado.x.es/master-en-y" not in pedidas and "https://caido.x.es/master" not in pedidas


def test_listados_de_la_portada_y_enlaces_por_texto(monkeypatch):
    """Universidad sin sitemap: la portada enlaza al listado de másteres y este a fichas cuya URL no dice «máster»."""
    portada = '<a href="/estudios/masteres">Másteres</a><a href="/noticias/x">Noticias</a>'
    listado = "".join(f'<a href="/titulacion?id={i}">Máster Universitario en Materia {i}</a>' for i in range(6))
    listado += '<a href="/titulacion?id=99">Programa de Doctorado en Física</a>'
    ficha = ("<title>Universidad X</title><h1>Máster Universitario en Materia</h1><p>60 ECTS. Plazas: 30. "
             "Preinscripción. Plan de estudios. Precio por crédito. Sevilla</p>")

    def falso_get(self, url, timeout=25, allow_redirects=True):
        if url.endswith("/robots.txt"):
            return _R(200, "User-agent: *\nAllow: /\n", "text/plain", url)
        if url.endswith((".xml", "tdmrep.json")):
            return _R(404, "", "text/html", url)
        if url == "https://x.es/":
            return _R(200, portada, url=url)
        if url == "https://x.es/estudios/masteres":
            return _R(200, listado, url=url)
        return _R(200, ficha, url=url)

    monkeypatch.setattr(r.requests.Session, "get", falso_get)
    res = r.rastrear("https://x.es", None, muestra=3, pausa=0)
    assert res["listados_visitados"] == ["https://x.es/estudios/masteres"]
    assert res["urls_programa"] == 6 and "https://x.es/titulacion?id=99" not in res["programas"]
    assert "https://x.es/estudios/masteres" not in res["programas"]  # el listado no es una ficha
    assert res["verificado"]


def test_paginas_que_no_son_fichas():
    assert not r.es_programa("https://www.ugr.es/estudiantes/master-doctorados/programa-doctorado-matematicas")
    assert not r.es_programa("https://www.udit.es/masterclass-de-david-chumilla/")
    assert not r.es_programa("https://www.ie.edu/our-news/carmen-panadero-master-real-estate/")
    assert not r.es_programa("https://www.urv.cat/en/studies/master/faq/62/es-un-master-oficial/")
    assert r.es_programa("https://www.urv.cat/ca/estudis/masters/oferta/advocacia-procura/")
    noticia = ("<title>El Máster en X, entre los mejores</title><h1>El Máster en X, entre los mejores</h1>"
               "<p>ECTS créditos matrícula precio plazas</p>")
    assert not r.medir_pagina(noticia, "https://x.es/2024/05/master-x")["es_programa"]
    ugr = ("<title>Máster Universitario en Psicología Jurídica | Universidad de Granada</title>"
           "<h1>Máster Universitario en Psicología Jurídica</h1><p>Admisión. 60 créditos. Matrícula.</p>")
    assert r.medir_pagina(ugr, "https://www.ugr.es/estudiantes/master-doctorados/master-psicologia")["es_programa"]
    doct = "<title>Programa de Doctorado en Matemáticas</title><p>Admisión créditos matrícula precio plazas</p>"
    assert not r.medir_pagina(doct, "https://x.es/doctorado")["es_programa"]


def test_web_principal():
    p = {"dominio": "uab.cat", "webs": ["https://caiac.uab.cat", "https://www.uab.cat/politiques-sociologia/"]}
    assert r.web_principal(p) == "https://www.uab.cat/politiques-sociologia/"
    assert r.web_principal({"dominio": "x.es", "webs": []}) == "https://x.es"
