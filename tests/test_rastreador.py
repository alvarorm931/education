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
