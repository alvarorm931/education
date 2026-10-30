"""robots.txt con comodines (RFC 9309): lo que urllib.robotparser no entiende."""

from motor.robots import Robots

PONTEVEDRA = """User-Agent: *
Sitemap: https://www.boppo.depo.gal/sitemap.xml
Disallow: /web/boppo/detalle/-/boppo/
Disallow: /bop-v2-portlet/
Disallow: *.pdf
Disallow: /*.pdf
Disallow: /login
"""


def test_comodines_y_prefijos():
    r = Robots(PONTEVEDRA)
    assert r.permite("https://boppo.depo.gal/es")
    assert not r.permite("https://boppo.depo.gal/web/boppo/detalle/-/boppo/2026/10/29/2026075016")
    assert not r.permite("https://boppo.depo.gal/web/boppo/sumario.bop.PONTEVEDRA.20261029.pdf")


def test_grupo_propio_allow_y_fin():
    r = Robots("User-agent: *\nDisallow: /\n\nUser-agent: PortalEstudiosOposiciones\nDisallow: /privado/\n"
               "Allow: /privado/publico$\n")
    assert r.permite("https://x.es/bop/2026")
    assert not r.permite("https://x.es/privado/a")
    assert r.permite("https://x.es/privado/publico") and not r.permite("https://x.es/privado/publico/b")


def test_coruna():
    r = Robots("User-Agent: *\nDisallow: /bop/\nDisallow: /bopportal/publicado\nDisallow: /bopportal/cambioBoletin.do\n")
    assert r.permite("https://bop.dacoruna.gal/bopportal/cambioBoletin?fechaInput=28%2f10%2f2026")
    assert not r.permite("https://bop.dacoruna.gal/bopportal/publicado/2026/10/30/2026_0000006961.html")
    assert Robots(todo_prohibido=True).permite("https://x.es/") is False


def test_obtener_no_pide_lo_prohibido(monkeypatch):
    import pytest

    from motor import http

    monkeypatch.setitem(http._ROBOTS, "https://www.uncentro.es", Robots("User-agent: *\nAllow: /\nDisallow: /privado/\n"))
    pedidas = []
    monkeypatch.setattr(http.requests.Session, "get", lambda self, url, **k: pedidas.append(url))
    with pytest.raises(http.RobotsProhibe):
        http.obtener("https://www.uncentro.es/privado/master")
    assert pedidas == []  # ni una petición


def test_robots_ilegible_es_prohibido(monkeypatch):
    from motor import http

    def falla(self, url, **k):
        raise http.requests.ConnectionError("sin red")

    monkeypatch.setattr(http.requests.Session, "get", falla)
    monkeypatch.setattr(http.time, "sleep", lambda s: None)
    http._ROBOTS.pop("https://nadie.example", None)
    assert http.robots_de("https://nadie.example/x").permite("https://nadie.example/x") is False


def test_excepcion_documentada(monkeypatch):
    from motor import http

    monkeypatch.setitem(http._ROBOTS, "https://data.commoncrawl.org", Robots("User-Agent: *\nDisallow: /\n"))
    http.comprobar_robots("https://data.commoncrawl.org/crawl-data/CC-MAIN-2026-43/cc-index-table.paths.gz")
    assert set(http.EXCEPCIONES_ROBOTS) == {"https://data.commoncrawl.org", "https://index.commoncrawl.org"}


def test_boletines_oficiales(monkeypatch):
    """Boletines oficiales cerrados en robots.txt: se leen solo en sus direcciones (decisión del 30/10/2026)."""
    import pytest

    from motor import http
    from motor.robots import Robots

    cerrado = Robots("User-agent: *\nDisallow: /\n")
    for origen in ("https://www.caib.es", "https://portaldogc.gencat.cat", "https://www.uncentro.es"):
        monkeypatch.setitem(http._ROBOTS, origen, cerrado)
    http.comprobar_robots("https://www.caib.es/eboibfront/es/2026/12248/713302/")
    http.comprobar_robots("https://portaldogc.gencat.cat/eadop-rest/api/dogc/documentDOGC")
    with pytest.raises(http.RobotsProhibe):
        http.comprobar_robots("https://www.caib.es/sites/otra-cosa/")  # mismo servidor, fuera del boletín
    with pytest.raises(http.RobotsProhibe):
        http.comprobar_robots("https://www.uncentro.es/master")  # webs que no son boletines: robots.txt manda
    assert http.boletin_oficial("https://BOP.DIBA.CAT/anuncis") == "BOP de Barcelona"
    assert http.boletin_oficial("http://bop.diputoledo.es/webEbop/inicio.jsp") == "BOP de Toledo"
    assert all(k.startswith("https://") and (k.endswith(("/", "?")) or "/api/" in k) for k in http.BOLETINES_OFICIALES)


def test_documentos_retirados_por_privacidad(monkeypatch):
    """Aunque el boletín se lea como boletín oficial, un documento que su robots.txt cierra por su código no se pide."""
    import pytest

    from motor import http
    from motor.robots import Robots

    monkeypatch.setitem(http._ROBOTS, "https://miprincipado.asturias.es", Robots(
        "User-agent: *\nDisallow: *.pdf$\n"
        "Disallow: */bopa/disposiciones?p_p_id=pa_sede_bopa_web_portlet_SedeBopaDispositionWeb*p_r_p_dispositionText=2016-02858*\n"))
    http.comprobar_robots("https://miprincipado.asturias.es/bopa/2026/10/29/2026-08847.pdf")
    with pytest.raises(http.RobotsProhibe):
        http.comprobar_robots("https://miprincipado.asturias.es/bopa/2016/03/01/2016-02858.pdf")
    with pytest.raises(http.RobotsProhibe):  # el resto del servidor sigue con su robots.txt
        http.comprobar_robots("https://miprincipado.asturias.es/otra/cosa.pdf")
