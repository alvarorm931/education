"""Conector del BOCCE (Ceuta), con el formato verificado desde España el 30/10/2026."""

import json

from motor.autonomicos import bocce as b

PORTADA = (b'<a href="/ceuta/component/jdownloads/viewcategory/1965-2026?Itemid=534">2026</a>'
           b'<a href="/ceuta/component/jdownloads/viewcategory/1947-2025?Itemid=534">2025</a>')
ANIO = (b'<a href="/ceuta/component/jdownloads/viewcategory/1966-enero?Itemid=534">Enero</a>'
        b'<a href="/ceuta/component/jdownloads/viewcategory/1982-octubre?Itemid=534">Octubre</a>')
MES = ('<a href="/ceuta/component/jdownloads/viewdownload/1968-2026/23299-acta-c-gob-26-09-30o?Itemid=">Acta</a>'
       '<a href="/ceuta/component/jdownloads/viewdownload/1982-octubre/23304-bocce-extra51-28-10-2026?Itemid=">x</a>'
       '<a href="/ceuta/component/jdownloads/viewdownload/1982-octubre/23305-bocce-6665-30-10-2026?Itemid=">x</a>'
       '<a href="/ceuta/component/jdownloads/viewdownload/1982-octubre/23305-bocce-6665-30-10-2026?Itemid=">x</a>'
       ).encode()

SUMARIO = """Boletín Oficial 
Ciudad de Ceuta 
Viernes 
30 de Octubre de 2026 
BOCCE 
Nº6665 
SUMARIO 
CEUTA 
D.L.: CE.1-1958 
 
 Boletín Oficial de la Ciudad de Ceuta - Plaza de África S/N 1390 
AUTORIDADES Y PERSONAL 
CIUDAD AUTONOMA DE CEUTA 
2301.- Relación provisional de aspirantes admitidos y excluidos para la provisión de 
2 plazas de Policía Local, por oposición libre. Pág.1391 
2302.- Bases de la convocatoria para la provisión de 1 plaza de Técnico de 
Administración General. Pág. 1392 
ANUNCIOS 
CIUDAD AUTONOMA DE CEUTA 
2303.- Información pública de la licencia de obra en calle Real. Pág.1394 
"""
CUERPO_1 = """BOCCE Nº 6665 Viernes 30 de Octubre de 2026 
 Boletín Oficial de la Ciudad de Ceuta - Plaza de África S/N 1391 
AUTORIDADES Y PERSONAL 
CIUDAD AUTONOMA DE CEUTA 
2301.- Se aprueba la relación provisional de aspirantes admitidos: 
***1234** GARCIA LOPEZ, MARIA 
***5678** PEREZ RUIZ, JUAN 
Las bases se publicaron en el BOCCE nº 6600, de 12 de marzo de 2026. 
"""
CUERPO_2 = """BOCCE Nº 6665 Viernes 30 de Octubre de 2026 
 Boletín Oficial de la Ciudad de Ceuta - Plaza de África S/N 1392 
2302.- Bases que han de regir la convocatoria para la provisión, por oposición libre, de una plaza de Técnico de
Administración General.
Las solicitudes se presentarán en el plazo de veinte días hábiles desde el siguiente a la publicación del extracto en el
Boletín Oficial del Estado.
2303.- Se somete a información pública la licencia de obra.
"""


def test_portada_anio_y_mes():
    assert b.anios(PORTADA) == {2026: "/ceuta/component/jdownloads/viewcategory/1965-2026",
                                2025: "/ceuta/component/jdownloads/viewcategory/1947-2025"}
    assert b.meses_del_anio(ANIO) == {1: "/ceuta/component/jdownloads/viewcategory/1966-enero",
                                      10: "/ceuta/component/jdownloads/viewcategory/1982-octubre"}
    lista = b.boletines_del_mes(MES)
    assert [(x["numero"], x["fecha"], x["extraordinario"]) for x in lista] == [
        ("Extra 51", "2026-10-28", True), ("6665", "2026-10-30", False)]  # el acta no es un boletín
    assert lista[1]["url_pdf"] == ("https://www.ceuta.es/ceuta/component/jdownloads/finish/1982-octubre/"
                                   "23305-bocce-6665-30-10-2026?Itemid=0")


def test_sumario_y_textos():
    paginas = [SUMARIO, CUERPO_1, CUERPO_2]
    entradas, desde = b.sumario(paginas)
    assert desde == 1
    assert [(e["numero_anuncio"], e["pagina"], e["seccion"], e["organismo"]) for e in entradas] == [
        ("2301", 1391, "AUTORIDADES Y PERSONAL", "CIUDAD AUTONOMA DE CEUTA"),
        ("2302", 1392, "AUTORIDADES Y PERSONAL", "CIUDAD AUTONOMA DE CEUTA"),
        ("2303", 1394, "ANUNCIOS", "CIUDAD AUTONOMA DE CEUTA")]
    assert entradas[0]["titulo"].startswith("Relación provisional de aspirantes admitidos y excluidos para la "
                                            "provisión de 2 plazas de Policía Local")
    textos = b.textos_cuerpo(paginas, [e["numero_anuncio"] for e in entradas], desde)
    assert "GARCIA" in textos["2301"] and "2302" not in textos["2301"]
    assert textos["2302"].startswith("2302.- Bases") and "2303" not in textos["2302"]
    empleo = b.seleccionar([{**e, "fecha": "2026-10-30"} for e in entradas])
    assert [e["numero_anuncio"] for e in empleo] == ["2301", "2302"]
    assert empleo[0]["convocante"]["nombre"] == "Ceuta"


def test_procesar_boletin_sin_nombres(tmp_path, monkeypatch):
    """La lista de admitidos se queda en recuento y citas; las bases guardan su texto sin cabeceras de página."""
    from motor.archivo import Archivo
    from motor.http import Respuesta

    class Lector:
        def __init__(self, _):
            self.pages = [type("P", (), {"extract_text": lambda self, t=t: t})() for t in (SUMARIO, CUERPO_1, CUERPO_2)]

    import pypdf
    monkeypatch.setattr(pypdf, "PdfReader", Lector)
    monkeypatch.setattr(b, "obtener", lambda url, accept=None: Respuesta(url, 200, b"%PDF-1.4 x", {}))
    bol = b.boletines_del_mes(MES)[1]
    inf = b.procesar_boletin(bol, tmp_path, Archivo(tmp_path / "archivo"))
    assert (inf["resultado"], inf["disposiciones"], inf["empleo_publico"]) == ("ok", 3, 2)
    base = tmp_path / "datos" / "autonomicos" / "bocce" / "textos" / "2026" / "10"
    lista = json.loads((base / "BOCCE-2026-6665-2301.json").read_text(encoding="utf-8"))
    assert lista["texto"] is None and lista["solo_recuento"]
    assert lista["citas"] == [{"boletin": "BOCCE", "numero": "6600", "fecha": "2026-03-12"}]
    assert "GARCIA" not in json.dumps(lista, ensure_ascii=False)
    bases = json.loads((base / "BOCCE-2026-6665-2302.json").read_text(encoding="utf-8"))
    assert "veinte días hábiles" in bases["texto"] and "Plaza de África" not in bases["texto"]
    assert "BOCCE Nº" not in bases["texto"]
