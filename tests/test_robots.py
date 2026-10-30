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
