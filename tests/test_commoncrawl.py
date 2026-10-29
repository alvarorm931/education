import re

from motor.estudios import commoncrawl as cc


def _ok(ruta):
    return bool(re.search(cc.PATRON_RUTA[4:], ruta, re.I)) and not re.search(cc.EXCLUIR[4:], ruta, re.I)


def test_descubrimiento_amplio():
    for ruta in ["/master-en-direccion-financiera/", "/masters/data-science", "/postgrado/mba-executive",
                 "/formacion-permanente/experto-universitario-en-compliance", "/estudios/titulo-propio",
                 "/es/master-universitario-en-psicologia", "/ca/postgrau/", "/estudis-propis/", "/m%C3%A0ster-en-dret",
                 "/apply-now/?campus=Barcelona&programs=Master%20in%20Sports", "/blog/becas-de-master",
                 "/formacion-continua/", "/msc-in-finance"]:
        assert _ok(ruta), ruta


def test_ruido_fuera():
    for ruta in ["/masterclass-de-cocina", "/rolex/yacht-master/m1", "/estreno-masterchef-celebrity",
                 "/pagar-con-mastercard", "/grado-en-derecho", "/repo/master/src/main.c", "/renault/master/furgon"]:
        assert not _ok(ruta), ruta
