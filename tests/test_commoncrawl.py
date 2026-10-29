import re

from motor.estudios import commoncrawl as cc


def _ok(ruta):
    return bool(re.search(cc.PATRON_RUTA[4:], ruta, re.I)) and not re.search(cc.EXCLUIR[4:], ruta, re.I)


def test_patron_programas():
    for ruta in ["/master-en-direccion-financiera/", "/masters/data-science", "/postgrado/mba-executive",
                 "/formacion-permanente/experto-universitario-en-compliance", "/estudios/titulo-propio",
                 "/mba/", "/es/master-universitario-en-psicologia-general-sanitaria"]:
        assert _ok(ruta), ruta
    for ruta in ["/masterclass-de-cocina", "/rolex/yacht-master/m1", "/estreno-masterchef-celebrity",
                 "/pagar-con-mastercard", "/blog/master", "/grado-en-derecho"]:
        assert not _ok(ruta), ruta
