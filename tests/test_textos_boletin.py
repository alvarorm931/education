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


def test_sumario_de_tenerife_con_pocos_puntos():
    """En el BOP de Tenerife hay entradas de sumario con dos a cuatro puntos antes de la página (30/10/2026)."""
    from motor.provinciales.textos import cortar, sin_entradas_de_sumario
    pagina = ("201838 Anuncio relativo a ampliación plazo de la plaza Ayudante Técnico .... 28971\n"
              "11132 Anuncio relativo a la contratación de personal Laboral Fijo .. 31443\n"
              "AYUNTAMIENTO DE ARONA\nAnuncio relativo a la contratación de personal Laboral Fijo\n"
              "Primera.- Objeto: dos plazas.\n")
    assert "31443" not in sin_entradas_de_sumario(pagina) and "Primera.- Objeto" in sin_entradas_de_sumario(pagina)
    c = cortar([pagina], [{"id": "a", "titulo": "Anuncio relativo a la contratación de personal Laboral Fijo"}])
    assert c["a"][0].startswith("Anuncio relativo a la contratación") and "Primera.- Objeto" in c["a"][0]
    # una línea del cuerpo que acaba en cifras sin puntos no es sumario
    assert "artículo 3 de la Ley 39/2015" in sin_entradas_de_sumario("según el artículo 3 de la Ley 39/2015\nOtra.")


def test_lugo_corta_por_el_registro_de_cada_anuncio():
    """En el BOP de Lugo cada anuncio acaba con «R. NNNN»: el texto va de la marca anterior a la suya, sin el final
    del anuncio anterior ni los siguientes, aunque el título del sumario no esté igual en el cuerpo (30/10/2026)."""
    from motor.limpieza import limpiar_texto
    from motor.provinciales.textos import CABECERAS
    pagina = ("54 Núm. 073 – sábado, 29 de marzo de 2025 BOP Lugo\nSarria, 20 de marzo de 2025.- O Alcalde.\nR. 0816\n"
              "O SAVIÑAO\nAnuncio\nAprobáronse as bases para a selección de tres peóns.\nPrazo: dez días.\n"
              "Anuncio publicado en: Num BOP 73 año 2025 (29/03/2025 08:00:00)\nR. 0817\n"
              "Anuncio\nAprobáronse as bases para a selección dun cófer.\nR. 0818\nSOBER\nPadrón fiscal.\nR. 0806\n")
    anuncios = [{"id": "a", "pagina": 1, "registro": "0817", "titulo": "BASES PARA A SELECCIÓN DE 3 PEÓNS/OAS"},
                {"id": "b", "pagina": 1, "registro": "0818", "titulo": "BASES PARA A SELECCIÓN DE 1 CÓFER"}]
    c = cortar([pagina], anuncios)
    a = limpiar_texto(c["a"][0], CABECERAS["boplugo"])["texto"]
    assert a.startswith("O SAVIÑAO") and "tres peóns" in a and "Sarria" not in a and "cófer" not in a
    assert "Anuncio publicado en" not in a and "R. 08" not in a
    b = limpiar_texto(c["b"][0], CABECERAS["boplugo"])["texto"]
    assert "cófer" in b and "peóns" not in b and "Padrón" not in b
    assert limpiar_texto("XOVES, 4 DE XULLO DE 2024 N.º 154\nCONCELLOS\nTexto.", CABECERAS["boplugo"])["texto"] == "CONCELLOS Texto."
    # sin el título en el cuerpo, con la página y el registro también
    c = cortar([pagina], [{"id": "z", "pagina": 1, "registro": "0818", "titulo": "Título que no aparece en el cuerpo"}])
    assert "cófer" in c["z"][0] and "peóns" not in c["z"][0]


def test_titulos_que_empiezan_igual_en_un_mismo_boletin():
    """BOP de Las Palmas: varios anuncios con el mismo comienzo de título; cada uno se queda con el suyo."""
    comun = "Bases específicas que regirán la convocatoria del proceso selectivo para la cobertura definitiva de una plaza de"
    pagina = (f"ANUNCIO\n{comun.upper()} ARQUITECTO/A TÉCNICO, POR EL SISTEMA DE CONCURSO\nPRIMERO. Aprobar las {comun} "
              "arquitecto/a técnico.\nTexto del arquitecto.\n"
              f"ANUNCIO\n{comun.upper()} TÉCNICO/A GESTIÓN DE ADMINISTRACIÓN GENERAL\nTexto del técnico de gestión.\n"
              f"ANUNCIO\n{comun.upper()} DELINEANTE, POR EL SISTEMA DE CONCURSO\nTexto del delineante.\n")
    anuncios = [{"id": "a", "titulo": f"{comun} arquitecto/a técnico, por el sistema de concurso"},
                {"id": "b", "titulo": f"{comun} técnico/a gestión de administración general"},
                {"id": "c", "titulo": f"{comun} delineante, por el sistema de concurso"}]
    c = cortar([pagina], anuncios)
    assert "arquitecto." in c["a"][0] and "Texto del arquitecto" in c["a"][0] and "gestión" not in c["a"][0]
    assert "Texto del técnico de gestión" in c["b"][0] and "delineante" not in c["b"][0].lower()
    assert "Texto del delineante" in c["c"][0]
