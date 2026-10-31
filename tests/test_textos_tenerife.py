"""BOP de Santa Cruz de Tenerife: columnas en orden de lectura y corte por el número de registro del sumario
(formato del boletín del 30/10/2026, sonda de prueba.yml)."""
from motor.provinciales import textos as t

IZQ = ["ante la Jurisdicción Contencioso-Administrativa,", "en el plazo de dos meses.",
       "Santana Pérez, documento firmado electrónicamente.", "Consejería Insular de Presidencia,", "ANUNCIO",
       "4641 2206854", "La Dirección Insular de Recursos Humanos,", "ha aprobado la RELACIÓN DEFINITIVA de",
       "aspirantes admitidos."]
DER = ["III. ADMINISTRACIÓN LOCAL", "CABILDO INSULAR DE TENERIFE", "ANUNCIO", "4640 2187336",
       "El Consejo de Gobierno del Excmo. Cabildo Insular", "de Tenerife, nombra a la persona del puesto",
       "se firma por delegación."]


def _pagina_layout() -> str:
    filas = [" Boletín Oficial de la Provincia de Santa Cruz de Tenerife. Número 130, Viernes 30 de octubre de 2026",
             " " * 70 + "29612", ""]
    for k in range(len(IZQ)):
        izq = IZQ[k] if k < len(IZQ) else ""
        der = DER[k] if k < len(DER) else ""
        filas.append((izq.ljust(78) + der).rstrip())
    filas += ["", "ANUNCIO", "4642 2198207",
              "En relación con la convocatoria pública del Concurso Regional de Mieles Casa de la Miel de Tenerife, ejercicio",
              "de resolución del Consejero con Delegación en Sector Primario, se aprueba."]
    return "\n".join(filas)


def test_columnas_en_orden_de_lectura():
    lineas = t.columnas_en_orden(_pagina_layout()).splitlines()
    i = lineas.index
    # Toda la columna izquierda, luego la derecha y después el tramo a toda la anchura
    assert i("aspirantes admitidos.") < i("III. ADMINISTRACIÓN LOCAL") < i("se firma por delegación.") < i("4642 2198207")
    assert lineas[i("4642 2198207") - 1] == "ANUNCIO"
    # Sin columnas, el texto no cambia
    assert t.columnas_en_orden("una línea\notra línea") == "una línea\notra línea"


SUMARIO = """SUMARIO
NÚMERO
REGISTRO PÁGINA
III. ADMINISTRACIÓN LOCAL
CABILDO INSULAR DE TENERIFE
2187336 Anuncio relativo a la adjudicación por el sistema de libre designación, del puesto de trabajo “DP2 Director/a de la
Oficina de Proyectos con financiación europea” .................................................. 29612
2206854 Anuncio relativo a la corrección de la fecha de celebración del primer ejercicio de la fase de oposición de la
convocatoria pública de 50 plazas de Técnico/a de Administración General ............................... 29612
2198207 Anuncio relativo a la modificación de la fecha de celebración del acto de entrega de los premios ......... 29614
2999999 Anuncio relativo a otro asunto que no está en el cuerpo de este boletín ..................................... 29620
"""


def test_corte_por_registro():
    anuncios = [
        {"id": "A1", "titulo": "Anuncio relativo a la adjudicación por el sistema de libre designación, del puesto de "
                               "trabajo “DP2 Director/a de la Oficina de Proyectos con financiación europea”"},
        {"id": "A2", "titulo": "Anuncio relativo a la corrección de la fecha de celebración del primer ejercicio de la "
                               "fase de oposición"},
        {"id": "A3", "titulo": "Anuncio relativo a la modificación de la fecha de celebración del acto de entrega"},
        {"id": "A4", "titulo": "Anuncio relativo a otro asunto que no está en el cuerpo de este boletín"},
        {"id": "A5", "titulo": "Asunto que no está en el sumario"},
    ]
    assert [r for r, _ in t.entradas_sumario([SUMARIO])] == ["2187336", "2206854", "2198207", "2999999"]
    cortes = t.cortar_por_registro([SUMARIO, t.columnas_en_orden(_pagina_layout())], anuncios)
    assert set(cortes) == {"A1", "A2", "A3"}
    a1, a2 = cortes["A1"][0], cortes["A2"][0]
    assert a1.startswith("El Consejo de Gobierno") and a1.rstrip().endswith("se firma por delegación.")
    assert "Mieles" not in a1 and "ANUNCIO" not in a1
    # El del registro 2206854 acaba antes de la cabecera del anuncio siguiente (sección, entidad y «ANUNCIO»)
    assert a2.startswith("La Dirección Insular") and a2.rstrip().endswith("aspirantes admitidos.")
    assert "CABILDO" not in a2 and cortes["A2"][1] == [2]
    assert "Mieles" in cortes["A3"][0]


def test_no_se_lleva_el_texto_de_un_anuncio_sin_registro_encontrado():
    sumario = ("SUMARIO\n2100001 Anuncio relativo a las bases de una plaza de Auxiliar Administrativo del Ayuntamiento "
               "....... 101\n2100002 Anuncio relativo a la oferta de empleo público del Organismo Autónomo de Deportes "
               "....... 102\n")
    p2 = "101\nAYUNTAMIENTO DE ARONA\nANUNCIO\n4649 2100001\nPrimera. Objeto de las bases de la plaza.\nSegunda."
    # La línea de registro del segundo no se reconoce (mezclada con otra cosa)
    p3 = "102\nAYUNTAMIENTO DE ARONA\nANUNCIO\n4650 texto 2100002\nSe aprueba la oferta de empleo público."
    anuncios = [{"id": "B1", "titulo": "Anuncio relativo a las bases de una plaza de Auxiliar Administrativo"},
                {"id": "B2", "titulo": "Anuncio relativo a la oferta de empleo público del Organismo Autónomo"}]
    cortes = t.cortar_por_registro([sumario, p2, p3], anuncios)
    assert t.primera_pagina([sumario, p2, p3]) == 100
    assert set(cortes) == {"B1"} and "oferta" not in cortes["B1"][0] and cortes["B1"][1] == [2]

    # Pegado a texto de la otra columna, pero al comienzo de la línea tras el número del anuncio: se reconoce
    p3 = "102\nAYUNTAMIENTO DE ARONA\nANUNCIO\n4650 2100002 texto pegado\nSe aprueba la oferta de empleo público."
    cortes = t.cortar_por_registro([sumario, p2, p3], anuncios)
    assert cortes["B2"][0].strip() == "Se aprueba la oferta de empleo público." and "oferta" not in cortes["B1"][0]
