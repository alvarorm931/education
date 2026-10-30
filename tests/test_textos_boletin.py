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


def test_salta_el_sumario_del_boletin():
    sumario = "SUMARIO\n" + "".join(f"{n} Anuncio número {n} ............................ {n}\n" for n in range(1, 6)) + \
        "2040825 Convocatoria de una plaza de Técnico Jurídico ........................ 28017\n"
    cuerpo = "AYUNTAMIENTO DE LA GUANCHA\nConvocatoria de una plaza de Técnico Jurídico\nPrimera. Objeto.\n"
    c = cortar([sumario, cuerpo], [{"id": "a", "titulo": "Convocatoria de una plaza de Técnico Jurídico"}])
    assert c["a"][1] == [2] and "Primera. Objeto" in c["a"][0] and "......" not in c["a"][0]
    # sin el título en el cuerpo, sin texto (nunca el de otro anuncio)
    assert cortar([sumario, "Otro anuncio distinto\n"], [{"id": "b", "pagina": 2, "titulo": "Bases de bombero"}]) == {}


def test_sumario_de_albacete_no_se_toma_por_el_anuncio():
    """El sumario del BOP de Albacete no lleva puntos sino «• Asunto>36»: también es sumario (30/10/2026)."""
    from motor.provinciales.textos import es_pagina_de_sumario
    pag = "\n".join(["Sección tercera. Administración Local", "Ayuntamientos", "Albacete",
                     "• Bases generales que van a regir las convocatorias>36", "• Lista de admitidos>40",
                     "• Bases específicas para cubrir la plaza de Monitor>55", "• Convocatoria de una plaza>57"])
    assert es_pagina_de_sumario(pag)
    assert not es_pagina_de_sumario("Primera.- Objeto de la convocatoria.\nSegunda.- Requisitos de los aspirantes.")


def test_pagina_con_parte_de_sumario():
    """En Tenerife y Las Palmas el sumario acaba a mitad de página: su línea con puntos no es el anuncio."""
    from motor.provinciales.textos import cortar
    pagina = ("SUMARIO\n2159757 Bases específicas y convocatoria para cubrir 5 plazas de Bombero/a Conductor "
              "............ 3\n2159758 Lista de admitidos de Auxiliar ............ 4\nAYUNTAMIENTO DE ARRECIFE\n"
              "Bases específicas y convocatoria para cubrir 5 plazas de Bombero/a Conductor\nPrimera.- Objeto: "
              "cinco plazas por oposición libre.\nSegunda.- Plazo: veinte días hábiles.\n")
    siguiente = "Lista de admitidos de Auxiliar\n1 APELLIDO APELLIDO, NOMBRE ***0000**\n"
    cortes = cortar([pagina, siguiente], [
        {"id": "a", "titulo": "Bases específicas y convocatoria para cubrir 5 plazas de Bombero/a Conductor"},
        {"id": "b", "titulo": "Lista de admitidos de Auxiliar"}])
    assert "veinte días hábiles" in cortes["a"][0] and "......" not in cortes["a"][0]
    assert cortes["b"][0].startswith("Lista de admitidos de Auxiliar")
