"""Nombres sin tratamiento que se escapaban de la limpieza (revisión de 3.000 textos de la rama de datos, 30/10/2026):
firmas, tribunales, pies de firma electrónica, listas «Apellidos, Nombre» y documentos enmascarados con asteriscos.
Los nombres de los ejemplos son inventados."""

from motor.limpieza import (RE_DOCUMENTO, limpiar_texto, parrafos_seguros, sin_pies_de_firma,
                            tiene_nombre_de_persona)


def test_firmas_y_tribunales_son_personas():
    for t in ("Peralta de Alcofea, 21 de julio de 2022. El Alcalde, Sergio Gambau Gracia.",
              "d’octubre de 2024.—La regidora delegada de Recursos Humans, Marina Rubio Rabés.",
              "Carlos Cuadrado Romay", "Secretario titular: José Vicente Ruano Vila, Secretario de esta corporación",
              "Natalia Prieto Viso Directora general de Administración Local",
              "A Pontenova, 21 de maio de 2025.- O Alcalde, Darío Campos Conde.",
              "María Rosario Romero Martín. Profesorado Titular de Universidad", "L’Alcalde José Luis Hernandez Arteseros",
              "- Vocal Suplente Segundo: Encarnación Ruiz Jarillo.", "ESTHER APRAIZ FERNÁNDEZ LA PEÑA.",
              "Presidente titular: Ismael García Burgos, inspector jefe", "Firmado por: El Alcalde. Óscar Fernández Martín.",
              "Berastegi, a 28 de noviembre de 2023.—El alcalde, Andoni Zuriarrain Iturbe. (9344)",
              "– David Vélez Vélez, personal laboral fijo del grupo", "JON ZARANDONA BORREGUERO.",
              "Presidenta suplente: M.ª Teresa Mínguez Manzano, Técnica de Administración General",
              "Fdo.: Antonio Puga Rodríguez.", "El Alcalde, Juan Pérez.", "Fdo.: Ana Torres", "Ana Torres",
              "Vocal 1 suplente Gil González, Ana Belén P. Titular de Universidad", "Sutil Barrigón, María de las Mercedes",
              "Mª del Pilar Pina Medina", "Carchuna, 9 de noviembre de 2022.-La Presidenta, fdo.: Concepción J. Abarca Cabrera.",
              "el Dr. Juan García López, catedrático", "1 PÉREZ GARCÍA, ANA", "CALDERÓN MARTÍN, MARÍA DEL CARMEN jueves",
              "Pamplona, 24 de julio de 2026.–Martín Larraza Quintana, vicerrector de Investigación.",
              "Ana Herrera Alcaldessa", "Suplente: Eva Real Barrero.", "PATRICIA ESTÉVEZ MOSTEIRO.- Non abona a taxa",
              "El Alcalde, Fdo.: Álvaro Regidor Reyes.", "Titular: Dª. Virginia Bejarano Martínez"):
        assert tiene_nombre_de_persona(t), t


def test_calles_centros_y_lugares_no_son_personas():
    for t in ("El Tribunal tendrá su sede en el Ayuntamiento, C/ Manuel Nieto Martínez, 6.",
              "el Ayuntamiento de Calvià (C/de Julià Bujosa Sans, batle, 1, 07184, Calvià)",
              "Av. Martín Alonso Pinzón, 9 | 21003 Huelva", "las universidades de A Coruña, Santiago de Compostela y Vigo",
              "Hospital Universitario Dr. Josep Trueta de Girona", "Universidad Rey Juan Carlos",
              "Universidad Miguel Hernández de Elche", "Cruz Roja Española", "Ayuntamiento de Pedro Muñoz Ciudad Real",
              "IES Pedro Mercedes de Cuenca", "S.M. el Rey Felipe VI", "Juan Carlos I", "Santa María la Real de Nieva",
              "Ayuntamiento de Santiago del Teide", "Colegio Público Miguel Hernández Gilabert",
              "Avenida Juan Ramón Jiménez Mantecón", "Castilla y León, Ana", "AYUNTAMIENTO DE SAN JAVIER SOBRE BASES",
              "calle San Vicente Mártir", "Jose Maria Arteche Mendia kalea", "Universidad Pablo de Olavide",
              "Ayuntamiento de Don Benito (Badajoz)", "del Marc Europeu Comú de Referència per a les llengües",
              "AO AMPARO DO “PLAN DE SOSTIBILIDADE TURÍSTICA EN RIBEIRA SACRA", "Tema 4. La Ley 39/2015, de 1 de octubre."):
        assert not tiene_nombre_de_persona(t), t


def test_pies_de_firma_electronica_se_quitan_del_parrafo():
    casos = [
        ("Bases. Documento firmado electrónicamente. Código Seguro de Verificación: z9VZio1Uj9 Firmado por Jefe de "
         "Sección del B.O.P. NOMBRE APELLIDO SEGUNDO el 03/03/2022 El documento consta de 32 página/s.", "SEGUNDO"),
        ("texto | Página 1 de 7 NOMBRE APELLIDO SEGUNDO (1 de 1) ALCALDESA Fecha Firma: 14/10/2026 HASH: b018ee262c4c16 sigue",
         "SEGUNDO"),
        ("Pàg. 1-1 · https://ddgi.cat/bop Document signat per NOMBRE APELLIDO - (FIRMA) en data 14/03/2025 resto", "APELLIDO"),
        ("Código Seguro De Verificación 6VOD9vm== Estado Fecha y hora Firmado Por Nombre Apellido Segundo Firmado "
         "21/03/2025 12:00:00 Observaciones Página 1/21 Url", "Segundo"),
        ("Este documento ha sido firmado por Concejala Delegada (NOMBRE APELLIDO) a las 18:24 del día 13/02/2025. Sigue",
         "APELLIDO"),
        ("SIGNAT ELECTRÒNICAMENT PER: Nombre Apellido Segundo - DNI ** (TCAT) el dia 14/08/2026 a les 13:51:57 Butlletí",
         "Segundo"),
        ("aspectes Signat per NOMBRE APELLIDO SEGUNDO (REGIDOR/A DELEGAT/DA) URL de verificació", "SEGUNDO"),
        ("Signat electrònicament per:Nombre Apellido Segundo Data: 18/02/2026 14:44:39 CET", "Segundo"),
    ]
    for texto, nombre in casos:
        limpio = sin_pies_de_firma(texto)
        assert nombre not in limpio, texto
    guardados, omitidos = parrafos_seguros(["Plazo de veinte días. Document signat per NOMBRE APELLIDO - (FIRMA) en data "
                                            "14/03/2025"])
    assert guardados == ["Plazo de veinte días."] and omitidos == 0


def test_parrafo_largo_pierde_solo_la_frase_con_el_nombre():
    """Un anuncio entero en un solo párrafo (PDF sin saltos) no se pierde por la firma: solo esa frase."""
    largo = ("Plazo de veinte días hábiles desde la publicación del extracto en el Boletín Oficial del Estado. Las "
             "solicitudes se presentarán en el registro electrónico del Ayuntamiento. Las plazas son de técnico y de "
             "auxiliar administrativo, con sus grupos y niveles. Binéfar, 9 de septiembre de 2025. La Alcaldesa, "
             "Patricia Rivera Escuder. Tribunal: Vocal: Sra. Puig Ferrer. Fin del anuncio con más detalles sobre las plazas.")
    guardados, omitidos = parrafos_seguros([largo])
    assert omitidos == 1 and "Rivera" not in guardados[0] and "Puig" not in guardados[0]
    assert "veinte días hábiles" in guardados[0] and "Fin del anuncio" in guardados[0]
    # uno corto se retira entero
    assert parrafos_seguros(["El Alcalde, Juan Pérez García."]) == ([], 1)


def test_documentos_enmascarados_con_asteriscos():
    for t in ("CARLOS APELLIDO *****365-E 321", "ARBELO LEMES, DAVID *****837R 6", "Mª Azahara Ramos 0******3-L Operario"):
        assert RE_DOCUMENTO.search(t), t
    r = limpiar_texto("Relación de vehículos\n1 GC-0290-AB RENAULT *****899-P\nPlazo de diez días.\n")
    assert "899" not in r["texto"] and r["lineas_omitidas_por_datos_personales"] == 1
