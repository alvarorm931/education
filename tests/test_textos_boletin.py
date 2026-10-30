"""Corte del texto de cada anuncio en un boletín entero en PDF (motor/provinciales/textos.py)."""

from motor.provinciales.textos import cortar


def test_cortar_por_titulo_y_pagina():
    paginas = ["BOP de Lugo núm. 249\nCONCELLO DE SARRIA\nBases da convocatoria dunha praza de auxiliar administrativo\n"
               "Primeira. Obxecto. O prazo de presentación será de vinte días hábiles.\n",
               "Segunda. Requisitos.\nCONCELLO DE MONFORTE\nLista definitiva de admitidos ao proceso de peón\n"
               "1 ***4567** Admitida\n"]
    anuncios = [{"id": "a", "pagina": 1, "titulo": "Bases da convocatoria dunha praza de auxiliar administrativo"},
                {"id": "b", "pagina": 2, "titulo": "Lista definitiva de admitidos ao proceso de peón"}]
    c = cortar(paginas, anuncios)
    texto_a, pags_a = c["a"]
    assert pags_a == [1, 2] and "vinte días hábiles" in texto_a and "Segunda. Requisitos" in texto_a
    assert "Lista definitiva" not in texto_a
    assert c["b"][0].startswith("Lista definitiva") and c["b"][1] == [2]


def test_cortar_sin_pagina():
    paginas = ["ANUNCIO\nConvocatoria de dos plazas de bombero\nTexto de bombero.\nANUNCIO\nModificación de créditos 5/2026\nTexto."]
    c = cortar(paginas, [{"id": "a", "titulo": "Convocatoria de dos plazas de bombero"},
                         {"id": "b", "titulo": "Modificación de créditos 5/2026"}])
    assert "Texto de bombero" in c["a"][0] and "créditos" not in c["a"][0]
