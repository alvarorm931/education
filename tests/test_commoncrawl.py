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


def test_dominios_de_censo_y_consolidar_urls(tmp_path):
    import json
    from motor.estudios import commoncrawl as cc
    f = tmp_path / "p.jsonl"
    f.write_text("\n".join(json.dumps(x) for x in [
        {"estado": "oficial", "dominios": ["uab.es", "uab.cat"]}, {"estado": "candidato", "dominios": ["x.com"]}]))
    assert cc.dominios_de_censo(f, ("oficial",)) == ["uab.cat", "uab.es"]
    d = tmp_path / "c"
    d.mkdir()
    (d / "00001.urls.jsonl").write_text(json.dumps({"dominio": "uab.cat", "url": "https://www.uab.cat/master-a"}) + "\n")
    (d / "00002.urls.jsonl").write_text(json.dumps({"dominio": "uab.cat", "url": "https://www.uab.cat/master-a"}) + "\n" +
                                        json.dumps({"dominio": "uab.cat", "url": "https://www.uab.cat/master-b"}) + "\n")
    assert cc.consolidar_urls(d) == [{"dominio": "uab.cat", "urls": ["https://www.uab.cat/master-a", "https://www.uab.cat/master-b"]}]


def test_sin_secretos():
    from motor.estudios import commoncrawl as cc
    u = "https://bucket.s3.amazonaws.com/master.pdf?AWSAccessKeyId=AKIAABCDEFGHIJKLMNOP&Signature=x"
    assert cc.sin_secretos(u) == "https://bucket.s3.amazonaws.com/master.pdf"
    assert cc.sin_secretos("https://x.es/master/AKIAABCDEFGHIJKLMNOP/") == "https://x.es/master/[retirado]/"
    assert cc.sin_secretos("https://x.es/master-en-finanzas?o=2") == "https://x.es/master-en-finanzas?o=2"
