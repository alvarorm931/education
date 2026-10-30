"""Control SEO (motor/seo): una web de ejemplo que cumple la ley y, a partir de ella, un error sembrado por prueba."""

import json
from datetime import date
from pathlib import Path

import pytest

from motor.seo import sitemaps as sm
from motor.seo.control import Control, aplicar, huella_texto, main
from motor.seo.similitud import grupos_parecidos

BASE = "https://ejemplo.es"
HOY = date(2026, 10, 30)
PROCESO_A = "/oposiciones/auxiliar-administrativo/ayuntamiento-de-villaejemplo/2026/"
PROCESO_B = "/oposiciones/policia-local/ayuntamiento-de-otroejemplo/2026/"
LUGAR = "/oposiciones/en/villaejemplo/"


def html(ruta, titulo, descripcion, cuerpo, tipo, robots="", head=""):
    meta_robots = f'<meta name="robots" content="{robots}">' if robots else ""
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titulo}</title><meta name="description" content="{descripcion}">
<link rel="canonical" href="{BASE}{ruta}">{meta_robots}<link rel="stylesheet" href="/css/web.css">{head}</head>
<body><header><a href="/">Inicio</a> <a href="/oposiciones/">Oposiciones</a></header>
<main data-tipo="{tipo}">{cuerpo}</main>
<footer><a href="/metodologia/">Cómo hacemos esta web</a></footer></body></html>"""


PORTADA = ('<link rel="icon" href="/favicon.png"><script type="application/ld+json">{"@context": '
           '"https://schema.org", "@type": "WebSite", "name": "Ejemplo", "url": "https://ejemplo.es/"}</script>')


def dato(clave, valor, fuente="https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-21007", fecha="2026-10-28"):
    return (f'<p data-dato="{clave}"><span data-valor>{valor}</span> · <a data-fuente href="{fuente}">Fuente</a>'
            f' · <time datetime="{fecha}">{fecha}</time></p>')


def proceso(ruta, puesto, convocante, plazas, plazo="2026-11-20", marcado=True, extra=""):
    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "JobPosting", "title": f"{puesto} en {convocante}",
        "description": f"Proceso selectivo de {puesto}", "datePosted": "2026-10-28", "validThrough": plazo,
        "hiringOrganization": {"@type": "Organization", "name": convocante},
        "jobLocation": {"@type": "Place", "address": {"@type": "PostalAddress", "addressLocality": "Villaejemplo",
                                                      "addressCountry": "ES"}},
    }, ensure_ascii=False)
    cuerpo = (f'<nav aria-label="Migas de pan"><a href="/oposiciones/">Oposiciones</a></nav>'
              f'<nav aria-label="Migas de pan por lugar"><a href="{LUGAR}">Villaejemplo</a></nav>'
              f"<h1>{puesto} en {convocante}</h1>" + dato("convocante", convocante) + dato("plazas", plazas)
              + dato("plazo", f"hasta el {plazo}") + extra
              + '<p data-actualizado>Actualizado el <time datetime="2026-10-28">28/10/2026</time></p>')
    head = f'<script type="application/ld+json">{jsonld}</script>' if marcado else ""
    return html(ruta, f"{puesto} en {convocante} (2026)", f"{plazas} plazas de {puesto} en {convocante}: plazo, "
                f"requisitos y fuente oficial.", cuerpo, "proceso", head=head)


def sitio_bueno(raiz: Path) -> list[dict]:
    paginas = {
        "/": html("/", "Estudios y oposiciones en España", "Toda la información abierta sobre estudios y "
                  "oposiciones.", f'<h1>Ejemplo</h1><a href="{LUGAR}">Oposiciones en Villaejemplo</a> '
                  '<a href="/metodologia/">Metodología</a>', "inicio", head=PORTADA),
        "/oposiciones/": html("/oposiciones/", "Oposiciones con plazo abierto", "Todas las convocatorias con su "
                              "plazo y su fuente.", f'<h1>Oposiciones</h1><ul><li><a href="{PROCESO_A}">Auxiliar '
                              f'administrativo</a></li><li><a href="{PROCESO_B}">Policía local</a></li></ul>',
                              "listado"),
        PROCESO_A: proceso(PROCESO_A, "Auxiliar administrativo", "Ayuntamiento de Villaejemplo", "3"),
        PROCESO_B: proceso(PROCESO_B, "Policía local", "Ayuntamiento de Otroejemplo", "12",
                           extra="<p>Pruebas físicas, examen teórico y entrevista personal. Hace falta el permiso "
                                 "de conducir B y el título de bachiller.</p>"),
        LUGAR: html(LUGAR, "Oposiciones en Villaejemplo", "Procesos selectivos convocados por el Ayuntamiento de "
                    "Villaejemplo.", f'<h1>Villaejemplo</h1><a href="{PROCESO_A}">Auxiliar administrativo, 3 '
                    'plazas</a>', "lugar"),
        "/metodologia/": html("/metodologia/", "Cómo hacemos esta web", "Quién hace la web, de dónde salen los "
                              "datos y qué se revisa a mano.", "<h1>Metodología</h1><p>Los datos salen de los "
                              "boletines oficiales y se revisan.</p>", "metodologia"),
    }
    for ruta, contenido in paginas.items():
        destino = raiz / ruta.lstrip("/") / "index.html"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(contenido, encoding="utf-8")
    (raiz / "css").mkdir()
    (raiz / "css" / "web.css").write_text("body{font-family:sans-serif}", encoding="utf-8")
    (raiz / "favicon.png").write_bytes(b"\x89PNG")
    (raiz / "404.html").write_text(html("/404/", "No existe", "No existe.", "<h1>No existe</h1>", "legal",
                                        robots="noindex"), encoding="utf-8")
    (raiz / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {BASE}/sitemap.xml\n", encoding="utf-8")
    manifiesto = [{"ruta": r, "tipo": t, "plantilla": t, "lastmod": "2026-10-28", "textos_ia": []}
                  for r, t in [("/", "inicio"), ("/oposiciones/", "listado"), (PROCESO_A, "proceso"),
                               (PROCESO_B, "proceso"), (LUGAR, "lugar"), ("/metodologia/", "metodologia")]]
    sm.generar({m["ruta"]: m["lastmod"] for m in manifiesto}, BASE, raiz)
    return manifiesto


@pytest.fixture
def web(tmp_path):
    raiz = tmp_path / "web"
    raiz.mkdir()
    return raiz, sitio_bueno(raiz)


def control(raiz, manifiesto, **kw):
    return Control(raiz, BASE, manifiesto, hoy=HOY, **kw)


def fallos(informe, regla=None, bloqueantes=False):
    return [f for f in informe.fallos if (regla is None or f.regla == regla)
            and (not bloqueantes or f.consecuencia in ("no_publicar", "plantilla"))]


def reescribir(raiz, ruta, cambio):
    archivo = raiz / ruta.lstrip("/") / "index.html"
    archivo.write_text(cambio(archivo.read_text(encoding="utf-8")), encoding="utf-8")


def test_sitio_que_cumple_la_ley(web):
    raiz, man = web
    inf = control(raiz, man).ejecutar()
    assert not inf.fallos, [(f.regla, f.ruta, f.detalle) for f in inf.fallos]
    assert not inf.bloquea and inf.indexables == 6


def test_novedades_de_2026(web):
    raiz, man = web
    # Metaetiqueta de robots en el cuerpo: Google la respeta desde marzo de 2026
    reescribir(raiz, "/oposiciones/", lambda h: h.replace("</main>", '<meta name="robots" content="noindex"></main>'))
    # Dato dentro de data-nosnippet: no sale en el fragmento ni en las respuestas con IA
    reescribir(raiz, PROCESO_B, lambda h: h.replace('<p data-dato="plazas">', '<p data-nosnippet data-dato="plazas">'))
    # Más de 2 MB: Googlebot no lee el resto
    reescribir(raiz, LUGAR, lambda h: h.replace("</main>", "<p>" + "x " * (1100 * 1024) + "</p></main>"))
    # Portada sin WebSite y con icono SVG
    reescribir(raiz, "/", lambda h: h.replace(PORTADA, '<link rel="icon" href="/icono.svg">'))
    inf = control(raiz, man).ejecutar()
    assert any("no es indexable" in f.detalle for f in fallos(inf, "sitemaps"))
    assert any("data-nosnippet" in f.detalle for f in fallos(inf, "indexacion", bloqueantes=True))
    assert [f.ruta for f in fallos(inf, "tamano_html", bloqueantes=True)] == [LUGAR]
    d = " ".join(f.detalle for f in fallos(inf, "portada"))
    assert "WebSite" in d and "SVG no" in d


def test_titulos_de_pura_plantilla(tmp_path):
    raiz = tmp_path / "web"
    raiz.mkdir()
    man = sitio_bueno(raiz)
    enlaces = []
    for i in range(25):
        ruta = f"/oposiciones/en/pueblo-{i}/"
        destino = raiz / ruta.lstrip("/") / "index.html"
        destino.parent.mkdir(parents=True)
        destino.write_text(html(ruta, f"Todas las oposiciones y bolsas de empleo en Pueblo{i}",
                                f"Procesos de Pueblo{i}: {i} plazas.", f'<p>Pueblo{i} tiene {i} procesos '
                                f'propios con datos {i * 7} distintos.</p><a href="{PROCESO_A}">Proceso</a>', "lugar"))
        enlaces.append(f'<a href="{ruta}">P{i}</a>')
        man.append({"ruta": ruta, "tipo": "lugar", "plantilla": "lugar", "lastmod": "2026-10-28"})
    reescribir(raiz, "/oposiciones/", lambda h: h.replace("</main>", "".join(enlaces) + "</main>"))
    inf = control(raiz, man).ejecutar()
    assert any("solo cambian en uno o dos datos" in f.detalle for f in fallos(inf, "rastreo"))


def test_sin_datos_minimos_sale_con_noindex(web):
    raiz, man = web
    reescribir(raiz, PROCESO_A, lambda h: h.replace('data-dato="plazas"', 'data-x="plazas"'))
    c = control(raiz, man)
    inf = c.ejecutar()
    assert [f.ruta for f in fallos(inf, "datos_minimos")] == [PROCESO_A]
    assert inf.acciones["noindex"] == [PROCESO_A]
    aplicar(raiz, inf, c.paginas)
    assert '<meta name="robots" content="noindex">' in (raiz / PROCESO_A.lstrip("/") / "index.html").read_text()
    # Ya no indexable: ahora sobra en el sitemap
    inf2 = control(raiz, man).ejecutar()
    assert any("no es indexable" in f.detalle for f in fallos(inf2, "sitemaps"))


def test_lugar_sin_procesos(web):
    raiz, man = web
    reescribir(raiz, LUGAR, lambda h: h.replace(f'href="{PROCESO_A}"', 'href="/oposiciones/"'))
    inf = control(raiz, man).ejecutar()
    assert any("ficha de proceso" in f.detalle for f in fallos(inf, "datos_minimos"))


def test_tipo_sin_declarar(web):
    raiz, man = web
    man = [m | {"tipo": "grado"} if m["ruta"] == LUGAR else m for m in man]
    inf = control(raiz, man).ejecutar()
    assert fallos(inf, "datos_minimos", bloqueantes=True)


def test_titulo_repetido_y_huecos(web):
    raiz, man = web
    reescribir(raiz, PROCESO_B, lambda h: h.replace("Policía local en Ayuntamiento de Otroejemplo (2026)</title>",
                                                    "Auxiliar administrativo en Ayuntamiento de Villaejemplo (2026)"
                                                    "</title>"))
    reescribir(raiz, LUGAR, lambda h: h.replace("<title>Oposiciones en Villaejemplo", "<title>Oposiciones en {{ lugar }}"))
    reescribir(raiz, "/oposiciones/", lambda h: h.replace('content="Todas las convocatorias', 'content="None ,'))
    inf = control(raiz, man).ejecutar()
    detalles = " ".join(f.detalle for f in fallos(inf, "titulo"))
    assert "repetido" in detalles and "hueco" in detalles
    assert fallos(inf, "descripcion", bloqueantes=True)


def test_canonica_y_direccion(web):
    raiz, man = web
    reescribir(raiz, PROCESO_B, lambda h: h.replace(f'canonical" href="{BASE}{PROCESO_B}"',
                                                    f'canonical" href="{BASE}{PROCESO_A}"'))
    otra = raiz / "Oposiciones" / "BOE-A-2026-21007" / "index.html"
    otra.parent.mkdir(parents=True)
    otra.write_text(html("/Oposiciones/BOE-A-2026-21007/", "Otra", "Otra.", "<p>x</p>", "listado",
                         robots="noindex"), encoding="utf-8")
    inf = control(raiz, man + [{"ruta": "/Oposiciones/BOE-A-2026-21007/", "tipo": "listado"}]).ejecutar()
    assert any("no apunta a sí misma" in f.detalle for f in fallos(inf, "canonica"))
    d = [f.detalle for f in fallos(inf, "direccion")][0]
    assert "mayúsculas" in d and "códigos" in d


def test_enlaces(web):
    raiz, man = web
    reescribir(raiz, LUGAR, lambda h: h.replace("</main>", '<a href="#">Ver más</a><a href="/no-existe/">x</a>'
                                                 '<a href="/oposiciones">y</a><a href="javascript:void(0)">z</a>'
                                                 '<a href="/metodologia/index.html">m</a></main>'))
    inf = control(raiz, man).ejecutar()
    d = " ".join(f.detalle for f in fallos(inf, "enlaces"))
    for esperado in ("almohadilla", "enlace roto a «/no-existe/»", "sin la barra final", "JavaScript", "index.html"):
        assert esperado in d


def test_huerfana(web):
    raiz, man = web
    nueva = raiz / "oposiciones" / "huerfana" / "index.html"
    nueva.parent.mkdir()
    nueva.write_text(html("/oposiciones/huerfana/", "Huérfana", "Nadie la enlaza.", "<p>Listado sin enlaces</p>",
                          "listado"), encoding="utf-8")
    inf = control(raiz, man + [{"ruta": "/oposiciones/huerfana/", "tipo": "listado", "lastmod": "2026-10-28"}]).ejecutar()
    assert [f.ruta for f in fallos(inf, "enlace_entrante")] == ["/oposiciones/huerfana/"]


def test_fuente_y_fecha(web):
    raiz, man = web
    reescribir(raiz, PROCESO_B, lambda h: h.replace(
        '<p data-dato="plazas"><span data-valor>12</span> · <a data-fuente href="https://www.boe.es/diario_boe/txt.'
        'php?id=BOE-A-2026-21007">Fuente</a> · <time datetime="2026-10-28">2026-10-28</time></p>',
        '<p data-dato="plazas"><span data-valor>12</span></p>'))
    inf = control(raiz, man).ejecutar()
    d = " ".join(f.detalle for f in fallos(inf, "fuente_fecha"))
    assert "sin enlace visible a su fuente" in d and "sin fecha visible" in d


def test_fuente_en_nota(web):
    raiz, man = web
    reescribir(raiz, PROCESO_B, lambda h: h.replace(
        '<p data-dato="plazas"><span data-valor>12</span> · <a data-fuente href="https://www.boe.es/diario_boe/txt.'
        'php?id=BOE-A-2026-21007">Fuente</a> · <time datetime="2026-10-28">2026-10-28</time></p>',
        '<p data-dato="plazas" data-fuente="f1">12 plazas</p><ol><li id="f1"><a href="https://www.boe.es/">BOE</a>,'
        ' <time datetime="2026-10-28">28/10/2026</time></li></ol>'))
    inf = control(raiz, man).ejecutar()
    assert not fallos(inf, "fuente_fecha")


def test_robots_txt(web):
    raiz, man = web
    (raiz / "robots.txt").write_text("User-agent: *\nAllow: /\nDisallow: /css/\n\nUser-agent: GPTBot\nDisallow: /\n"
                                     "\nCrawl-delay: 5\n", encoding="utf-8")
    inf = control(raiz, man).ejecutar()
    d = " ".join(f.detalle for f in fallos(inf, "robots_txt"))
    assert "GPTBot no puede rastrear 6" in d and "recursos" in d and "no declara el sitemap" in d
    assert "Crawl-delay" in d


def test_jobposting(web):
    raiz, man = web
    jsonld = '<script type="application/ld+json">{"@context":"https://schema.org","@type":"JobPosting","title":"x"}</script>'
    reescribir(raiz, "/oposiciones/", lambda h: h.replace("</head>", jsonld + "</head>"))
    reescribir(raiz, PROCESO_B, lambda h: h.replace('"validThrough": "2026-11-20"', '"validThrough": "2026-10-01"'))
    c = control(raiz, man)
    inf = c.ejecutar()
    d = " ".join(f.detalle for f in fallos(inf, "jobposting"))
    assert "tipo «listado»" in d and "plazo cerrado" in d
    assert all(f.consecuencia == "sin_marcado" for f in fallos(inf, "jobposting"))
    aplicar(raiz, inf, c.paginas)
    assert "ld+json" not in (raiz / "oposiciones" / "index.html").read_text()
    assert not fallos(control(raiz, man).ejecutar(), "jobposting")


def test_marcado_que_no_se_ve(web):
    raiz, man = web
    reescribir(raiz, PROCESO_A, lambda h: h.replace('"name": "Ayuntamiento de Villaejemplo"',
                                                    '"name": "Ayuntamiento de Otro Sitio"'))
    reescribir(raiz, LUGAR, lambda h: h.replace("</head>", '<script type="application/ld+json">{"@context": '
                                                "\"https://schema.org\", \"@type\": \"Dataset\",}</script></head>"))
    inf = control(raiz, man).ejecutar()
    d = " ".join(f.detalle for f in fallos(inf) if f.regla in ("jobposting", "datos_estructurados"))
    assert "no se ve en la página" in d and "JSON no válido" in d


def test_similitud():
    plantilla = ("Oposiciones en {} con el plazo, las plazas, los requisitos y la fuente oficial de cada proceso "
                 "selectivo convocado por el ayuntamiento. Consulta también las bolsas de empleo y los exámenes de "
                 "años anteriores, y recibe un aviso cuando se publique una convocatoria nueva.")
    textos = {f"/oposiciones/en/{p}/": plantilla.format(p) for p in ("villa-a", "villa-b", "villa-c")}
    textos["/oposiciones/en/distinta/"] = "Un texto que no se parece en nada a los demás, con datos propios."
    grupos = grupos_parecidos(textos, 0.8)
    assert len(grupos) == 1 and len(grupos[0]["paginas"]) == 3


def test_similitud_en_el_sitio(web):
    raiz, man = web
    cuerpo = ("<h1>Oposiciones</h1><p>Consulta el plazo, las plazas, los requisitos y la fuente oficial de cada proceso"
              " selectivo, con aviso cuando se publique una convocatoria nueva y los exámenes de años anteriores.</p>")
    for n in ("a", "b"):
        destino = raiz / "oposiciones" / f"lista-{n}" / "index.html"
        destino.parent.mkdir()
        destino.write_text(html(f"/oposiciones/lista-{n}/", f"Lista {n}", f"Lista {n}.", cuerpo, "listado"))
        reescribir(raiz, "/oposiciones/", lambda h, n=n: h.replace("</ul>", f'<li><a href="/oposiciones/lista-{n}/">'
                                                                          f"L{n}</a></li></ul>"))
    extra = [{"ruta": f"/oposiciones/lista-{n}/", "tipo": "listado", "lastmod": "2026-10-28"} for n in "ab"]
    inf = control(raiz, man + extra).ejecutar()
    assert "2 páginas indexables casi iguales" in fallos(inf, "similitud")[0].detalle


def test_lastmod(web):
    raiz, man = web
    c = control(raiz, man)
    estado = c.ejecutar().estado
    # Misma página, otra fecha: se cambió la fecha sin cambiar el dato
    man2 = [m | {"lastmod": "2026-10-29"} if m["ruta"] == PROCESO_A else m for m in man]
    inf = control(raiz, man2, estado_anterior=estado).ejecutar()
    assert any("sin que cambie el contenido" in f.detalle for f in fallos(inf, "lastmod"))
    assert any("en el sitemap" in f.detalle for f in fallos(inf, "lastmod"))
    # Cambiar solo la fecha visible de «actualizado» no cambia la huella
    reescribir(raiz, PROCESO_B, lambda h: h.replace('data-actualizado>Actualizado el <time datetime="2026-10-28">',
                                                    'data-actualizado>Actualizado el <time datetime="2026-10-28">x'))
    assert control(raiz, man).ejecutar().estado[PROCESO_B]["huella"] == estado[PROCESO_B]["huella"]


def test_sitemap_con_changefreq(web):
    raiz, man = web
    archivo = raiz / "sitemap-oposiciones-1.xml"
    archivo.write_text(archivo.read_text().replace("</lastmod>", "</lastmod><changefreq>daily</changefreq>", 1))
    inf = control(raiz, man).ejecutar()
    assert any("changefreq" in f.detalle for f in fallos(inf, "sitemaps"))


def test_sitemaps_se_parten():
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as d:
        escritos = sm.generar({f"/oposiciones/p{i}/": "2026-10-28" for i in range(5)} | {"/master/x/": "2026-10-01"},
                              BASE, Path(d), max_url=2)
        assert escritos == ["sitemap.xml", "sitemap-master-1.xml", "sitemap-oposiciones-1.xml",
                            "sitemap-oposiciones-2.xml", "sitemap-oposiciones-3.xml"]
        tipo, entradas, problemas = sm.leer(Path(d) / "sitemap.xml")
        assert tipo == "sitemapindex" and len(entradas) == 4 and not problemas


def test_redirecciones_y_cabeceras(web):
    raiz, man = web
    (raiz / "_redirects").write_text(f"/viejo/ /intermedio/ 301\n/intermedio/ {PROCESO_A} 301\n/temporal/ /\n"
                                     f"/oposiciones/ /otra/ 301\n", encoding="utf-8")
    (raiz / "_headers").write_text("/oposiciones/*\n  X-Robots-Tag: noindex\n/css/*\n  Cache-Control: max-age=60\n")
    inf = control(raiz, man).ejecutar()
    d = " ".join(f.detalle for f in fallos(inf, "redirecciones"))
    assert "cadena de 2 saltos" in d and "código 302" in d and "sigue existiendo" in d and "no existe" in d
    assert "4 páginas indexables" in fallos(inf, "cabeceras")[0].detalle


def test_ventanas_y_nosnippet(web):
    raiz, man = web
    reescribir(raiz, LUGAR, lambda h: h.replace("</main>", '</main><div role="dialog">Suscríbete</div>'
                                                 '<div role="dialog" hidden>Mi plan</div>')
               .replace("</head>", '<meta name="robots" content="max-snippet:0"></head>'))
    inf = control(raiz, man).ejecutar()
    assert len(fallos(inf, "ventanas")) == 1
    assert fallos(inf, "indexacion", bloqueantes=True)


def test_textos_con_ia(web):
    raiz, man = web
    texto = "Procesos selectivos convocados por el Ayuntamiento de Villaejemplo."
    man = [m | {"textos_ia": [texto]} if m["ruta"] == LUGAR else m for m in man]
    inf = control(raiz, man).ejecutar()
    assert fallos(inf, "ia_revisada", bloqueantes=True)
    inf = control(raiz, man, revisiones=[{"huella": huella_texto(texto), "revisado_por": "Álvaro"}]).ejecutar()
    assert not fallos(inf, "ia_revisada")
    assert fallos(control(raiz, []).ejecutar(), "ia_revisada", bloqueantes=True)  # sin manifiesto no se publica


def test_linea_de_ordenes(web, tmp_path):
    raiz, man = web
    m = tmp_path / "paginas.jsonl"
    m.write_text("\n".join(json.dumps(x) for x in man), encoding="utf-8")
    reescribir(raiz, PROCESO_A, lambda h: h.replace('data-dato="plazas"', 'data-x="plazas"'))
    informe, estado = tmp_path / "informe.json", tmp_path / "estado.json"
    codigo = main(["--sitio", str(raiz), "--base", BASE, "--manifiesto", str(m), "--hoy", "2026-10-30", "--aplicar",
                   "--generar-sitemaps", "--informe", str(informe), "--estado-nuevo", str(estado)])
    datos = json.loads(informe.read_text())
    assert codigo == 0, datos["fallos"]
    assert datos["acciones"]["noindex"] == [PROCESO_A] and datos["indexables"] == 5
    assert PROCESO_A not in (raiz / "sitemap-oposiciones-1.xml").read_text()
    assert PROCESO_A in json.loads(estado.read_text())


# ---------------------------------------------------------------- con navegador
def _chromium():
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            pw.chromium.launch().close()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _chromium(), reason="sin Chromium")
def test_navegador(web):
    from motor.seo.renderizado import comprobar_con_navegador

    raiz, man = web
    script = ("<script>document.querySelector('main').insertAdjacentHTML('beforeend', '<p>' + 'contenido que solo "
              "existe con javascript '.repeat(12) + Array.from({length: 40}, (_, i) => 'palabra' + i).join(' ') + "
              "'</p>'); const m = document.createElement('meta'); m.name = 'robots'; m.content = 'noindex'; "
              "document.head.appendChild(m);</script>")
    reescribir(raiz, LUGAR, lambda h: h.replace("</body>", script + "</body>"))
    ventana = ('<div style="position:fixed;inset:0;background:#000c">Déjanos tu correo</div>'
               '<script>setTimeout(() => document.querySelector("main").insertAdjacentHTML("afterbegin", '
               '"<div style=\\"height:600px\\">Anuncio</div>"), 400)</script>')
    reescribir(raiz, "/metodologia/", lambda h: h.replace("</body>", ventana + "</body>"))
    c = control(raiz, man)
    c.ejecutar()
    f = comprobar_con_navegador(raiz, c, por_plantilla=1)
    por_regla = {}
    for x in f:
        por_regla.setdefault(x.regla, []).append((x.ruta, x.detalle))
    assert any(r == LUGAR for r, _ in por_regla["contenido_html"])
    assert any(r == LUGAR for r, _ in por_regla["indexacion"])
    assert any(r == "/metodologia/" for r, _ in por_regla["ventanas"])
    assert any("CLS" in d and "metodologia" in d for _, d in por_regla["velocidad"])
    assert all(r != PROCESO_A for r, _ in por_regla.get("contenido_html", []))


# ---------------------------------------------------------------- avisos a buscadores
def test_cambios_para_avisar():
    from motor.seo.notificar import cambios

    anterior = {"/a/": {"huella": "1", "lastmod": "2026-10-01", "indexable": True, "empleo": True},
                "/b/": {"huella": "2", "lastmod": "2026-10-01", "indexable": True, "empleo": False},
                "/c/": {"huella": "3", "lastmod": "2026-10-01", "indexable": True, "empleo": True}}
    nuevo = {"/a/": {"huella": "1", "lastmod": "2026-10-01", "indexable": True, "empleo": False},  # plazo cerrado
             "/b/": {"huella": "9", "lastmod": "2026-10-29", "indexable": True, "empleo": False},
             "/d/": {"huella": "4", "lastmod": "2026-10-29", "indexable": True, "empleo": True}}
    c = cambios(anterior, nuevo)
    assert c["actualizadas"] == ["/b/", "/d/"] and c["retiradas"] == ["/c/"]
    assert c["empleo_actualizadas"] == ["/a/", "/d/"] and c["empleo_retiradas"] == ["/c/"]


# ---------------------------------------------------------------- vigilancia del sitio publicado
class Respuesta:
    def __init__(self, codigo=200, cuerpo=b"", cabeceras=None):
        self.status_code, self.content, self.headers = codigo, cuerpo, cabeceras or {}

    @property
    def text(self):
        return self.content.decode("utf-8")

    def json(self):
        return json.loads(self.content)


class SesionFalsa:
    """Sirve la web de ejemplo como si estuviera publicada en https://ejemplo.es."""

    def __init__(self, raiz, cambios=None):
        self.raiz, self.cambios, self.pedidas = raiz, cambios or {}, []

    def get(self, url, headers=None, allow_redirects=False, timeout=None, params=None):
        from urllib.parse import urlparse

        self.pedidas.append((url, headers.get("User-Agent", "")))
        if url in self.cambios:
            return self.cambios[url](headers or {})
        u = urlparse(url)
        if u.scheme == "http" or u.netloc != "ejemplo.es":
            return Respuesta(301, cabeceras={"Location": "https://ejemplo.es/"})
        archivo = self.raiz / (u.path.lstrip("/") + ("index.html" if u.path.endswith("/") else ""))
        if not archivo.is_file():
            return Respuesta(404, b"no existe")
        cab = {"ETag": '"x"'}
        if (headers or {}).get("If-None-Match") == '"x"':
            return Respuesta(304, cabeceras=cab)
        return Respuesta(200, archivo.read_bytes(), cab)

    def post(self, *a, **k):
        raise AssertionError("sin claves no se llama a ninguna API")


def vigilar(raiz, sesion, generado=True):
    from motor.seo.vigilancia import Vigilancia

    return Vigilancia(BASE, raiz if generado else None, sesion=sesion, hoy=HOY, certificado=False,
                      entorno={}).ejecutar()


def test_vigilancia_sitio_sano(web):
    raiz, _ = web
    inf = vigilar(raiz, SesionFalsa(raiz))
    assert not inf.alertas, [(h.comprobacion, h.detalle, h.url) for h in inf.alertas]
    assert inf.metricas["urls_en_sitemaps"] == 6


def test_vigilancia_detecta_cloudflare_y_bloqueos(web):
    raiz, _ = web
    robots_cf = ("Content-signal: search=yes, ai-train=no, use=reference\nUser-agent: GPTBot\nDisallow: /\n\n"
                 + (raiz / "robots.txt").read_text())
    pagina = (raiz / PROCESO_A.lstrip("/") / "index.html").read_bytes().replace(
        b"</body>", b'<script src="/cdn-cgi/scripts/5c5dd728/cloudflare-static/email-decode.min.js"></script></body>')

    def portada(h):
        if "OAI-SearchBot" in h.get("User-Agent", ""):
            return Respuesta(403, b"bloqueado")
        return Respuesta(200, (raiz / "index.html").read_bytes())

    cambios = {
        f"{BASE}/robots.txt": lambda h: Respuesta(200, robots_cf.encode()),
        f"{BASE}{PROCESO_A}": lambda h: Respuesta(200, pagina),
        f"{BASE}/": portada,
        "https://www.ejemplo.es/": lambda h: Respuesta(302, cabeceras={"Location": "https://ejemplo.es/"}),
    }
    inf = vigilar(raiz, SesionFalsa(raiz, cambios))
    d = " ".join(h.detalle for h in inf.alertas)
    for esperado in ("Content-signal", "prohíbe a GPTBot", "no es el generado", "ofuscación de correos",
                     "OAI-SearchBot recibe 403", "responde 302"):
        assert esperado in d, esperado


def test_vigilancia_soft404_y_noindex_servido(web):
    raiz, _ = web

    class Soft404(SesionFalsa):
        def get(self, url, headers=None, **k):
            r = super().get(url, headers=headers, **k)
            if r.status_code == 404:
                return Respuesta(200, (self.raiz / "index.html").read_bytes())
            if url == f"{BASE}{LUGAR}":
                r.headers["X-Robots-Tag"] = "noindex"
            return r

    inf = vigilar(raiz, Soft404(raiz), generado=False)
    d = " ".join(h.detalle for h in inf.alertas)
    assert "soft 404" in d and "X-Robots-Tag: noindex" in d


# ---------------------------------------------------------------- dominio
def test_nombres_de_dominio():
    from motor.seo.dominio import revisar_nombre

    assert revisar_nombre("lumbre.es") == []
    assert any("carácter oficial" in p for p in revisar_nombre("oposicionesboe.es"))
    assert any("palabras clave" in p for p in revisar_nombre("oposicionesmasters.es"))
    assert any("guiones" in p for p in revisar_nombre("mi-portal24.es"))
    assert any("no es .es" in p for p in revisar_nombre("lumbre.com"))


def test_historial_de_dominio(monkeypatch):
    from motor.seo import dominio as dm

    class Sesion:
        def get(self, url, params=None, headers=None, timeout=None):
            if "available" in url:
                return Respuesta(200, json.dumps({"archived_snapshots": {"closest": {"timestamp": "20190101"}}}).encode())
            if "cdx/search" in url:
                return Respuesta(200, json.dumps([["timestamp", "original"], ["2019", "http://x.es/casino"]]).encode())
            if "collinfo" in url:
                return Respuesta(200, json.dumps([{"id": "CC-MAIN-2026-43", "cdx-api": "https://cc/idx"}]).encode())
            return Respuesta(200, b"")

    monkeypatch.setattr(dm.socket, "getaddrinfo", lambda *a: (_ for _ in ()).throw(dm.socket.gaierror()))
    h = dm.historial("x.es", Sesion())
    assert h["wayback_anos"] == ["2019"] and h["resuelve"] is False
    assert dm.veredicto(h, []).startswith("tiene historial")
