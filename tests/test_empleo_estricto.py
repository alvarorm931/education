"""Selección por título en los BOP sin sección de personal (Alicante, Valencia, Ciudad Real, Tenerife, SAGA).

Casos reales de los BOP de Alicante y Valencia (2022-2026). La versión anterior dejaba fuera convocatorias
evidentes («BASES CONVOCATORIA TÉCNICO/A MEDIO/A INDUSTRIAL», «OFERTA EMPLEO PÚBLICO 2022») y la de antes de esa
metía concursos de fotografía, taxis y nombramientos de tenientes de alcalde.
"""

import pytest

from motor.autonomicos.comun import es_empleo_estricto

SI = [
    "BASES CONVOCATORIA TÉCNICO/A MEDIO/A INDUSTRIAL",
    "LISTA DEFINITIVA CONVOCATORIA PSICÓLOGO/A",
    "OFERTA EMPLEO PÚBLICO 2022 AYUNTAMIENTO DE TORREMANZANAS",
    "APROVACIÓ OFERTA D´OCUPACIÓ PÚBLICA DE L´AJUNTAMENT DE MURO DE ALCOY PER A 2024",
    "BASES Y CONVOCATORIA PARA CUBRIR DOS VACANTES DE ADMINISTRATIVO DE ADMINISTRACIÓN GENERAL",
    "EDICTO CONVOCATORIA BOLSA TAG 2022.",
    "EDICTO CONVOCATORIA PLAZAS_CONSERJE CONCURSO",
    "EDICTE LLISTA DEFINITIVA TREBALLADOR/A SOCIAL (EXPT. 1135/2024)",
    "LISTADO PROVISIONAL ADMITIDOS CONCURSO DE MÉRITOS GRUPOS C1, C2 Y AP",
    "ANUNCIO LISTA DEFINITIVA, TRIBUNAL Y FECHA DE CELEBRACIÓN DEL PRIMER EJERCICIO",
    "LISTA DEFINITIVA, DESIGNACIÓN TRIBUNAL Y FECHA VALORACIÓN MÉRITOS",
    "ANUNCIO MODIFICACIÓN TRIBUNAL CALIFICADOR 2º. VOCAL TITULAR",
    "BASES ESPECÍFIQUES I CONVOCATÒRIA PER A LA PROVISIÓ EN PROPIETAT PLAÇA TÈCNIC SUPERIOR EN INFORMÀTICA, PEL TORN "
    "DE PROMOCIÓ INTERNA",
    "LLISTA DEFINITIVA ADMESOS I EXCLOSOS, TRIBUNAL I DATA PRIMER EXERCICI, PLAÇA TÈCNIC D´ACTIVITATS ESPORTIVES, TORN "
    "PROMOCIÓ INTERNA.",
    "Anunci de la Mancomunitat El Marquesat sobre l'aprovació de les bases i la convocatòria per a la formació d'una "
    "borsa de treball de treballador/a social",
    "Anunci de la Fundació Esportiva Municipal de València sobre el procés selectiu per a la cobertura definitiva de "
    "huit places d'encarregat/da d'instal·lacions",
    "EDICTO BASES PARA LA PROVISION TEMPORAL, EN COMISION DE SERVICIOS, DE 2 PUESTOS VACANTES DE OFICIAL DE POLICIA.",
    "APROBACIÓN DE BASES ESPECÍFICAS Y CONVOCATORIA PARA PROVISIÓN DEFINITIVA DE JEFATURA SERVICIO SECRETARÍA MEDIANTE "
    "SISTEMA LIBRE DESIGNACIÓN",
    "BASES GENERALES DE SELECCIÓN DE EMPLEADOS PÚBLICOS DEL AYUNTAMIENTO DE ASPE PARA EL AÑO 2022.",
    "MODIFICACIÓN ERROR MATERIAL C. MÉRITOS CORRESPONDIENTE A 2 PLAZAS DE OPERARIO APOYO CENTRO CÍVICO DEL CONVENIO "
    "COLECTIVO DE PERSONAL LABORAL",
    "REGLAMENTO BASES DE ESTABILIZACIÓN DE EMPLEO DEL AYUNTAMIENTO DE CALP.",
    "NOMBRAMIENTO AGENTES DE POLICÍA LOCAL, TURNO DE MOVILIDAD.",
    "BASES ANIMADOR/A SOCIOCULTURAL JUVENIL (C1) EXPT. 967.2024",
    # Gallego (BOP da Coruña)
    "Convocatoria e bases reguladoras para a creación dunha bolsa de traballo para a provisión con carácter temporal "
    "de traballadores/as sociais no Concello de Cabanas",
    "Nomeamento de funcionario interino administrativo, subgrupo C1, para o servizo de rexistro-padrón - DMP",
    "Aprobación de bases para a selección de catro prazas de limpiador/a municipal do Concello de Ares",
    # Temas excluidos que también son nombres de puesto o de organismo
    "CONVOCATORIA Y BASES PROVISIÓN PUESTO JEFE/A SERVICIO URBANISMO Y OBRAS POR LIBRE DESIGNACIÓN (A1)",
    "CONVOCATORIA PARA LA PROVISIÓN DE VARIOS PUESTOS DEL PATRONATO MUNICIPAL DE LA VIVIENDA DE ALICANTE POR EL SISTEMA "
    "DE LIBRE DESIGNACIÓN.",
    "BASES PROCESO SELECTIVO CONCURSO-OPOSICIÓN 1 PLAZA AUXILIAR SERVICIO DE AYUDA A DOMICILIO",
    "BASES PARA LA PROVISIÓN DEL PUESTO DE TRABAJO DE JEFE DE SERVICIO DE GESTIÓN DE SUBVENCIONES - LIBRE DESIGNACIÓN",
]

NO = [
    "CONCURSO FOTOGRAFÍA MÓVIL FIESTAS SAN PEDRO 2026",
    "BASES PARA LA OBTENCIÓN DEL PERMISO MUNICIPAL DE CONDUCTOR DE AUTO-TAXI",
    "CONVOCATORIA XXXIX CONCURSO PARA LA SELECCIÓN DEL CARTEL ANUNCIADOR DE LAS FIESTAS DE MOROS Y CRISTIANOS 2026.",
    "NOMBRAMIENTO PERSONAL EVENTUAL",
    "NOMBRAMIENTO DE TENENCIAS DE ALCALDÍA",
    "Anunci de l'Ajuntament de Vallés sobre el cessament i nomenament de tinents d'Alcaldia.",
    "ANUNCIO NOMBRAMIENTO PORTAVOCES GRUPOS MUNICIPALES",
    "ANUNCIO NOMBRAMIENTO VICEPRESIDENTE MANCOMUNIDAD LA VEGA",
    "APROBACIÓN DEFINITIVA MODIFICACIÓN PLANTILLA DE PERSONAL",
    "ANUNCIO MODIFICACIÓN RELACIÓN PUESTOS DE TRABAJO.",
    "CATÁLOGO PUESTOS DE TRABAJO DEL AYUNTAMIENTO DE ASPE AÑO 2026.",
    "APROBACIÓN INICIAL REGLAMENTO DE ORGANIZACIÓN, FUNCIONAMIENTO Y RÉGIMEN JURÍDICO DE LA POLICÍA LOCAL",
    "CONVENIO CON AYUNTAMIENTO DE CATRAL PARA COMPARTIR BOLSAS DE EMPLEO TEMPORALES",
    "DECLARACIÓN DE BIENES DE LOS MIEMBROS DE LA CORPORACIÓN MUNICIPAL 2023-2027 COMO CONSECUENCIA DE SU TOMA DE POSESIÓN",
    "Anunci de l'Ajuntament de Riba-roja de Túria sobre la informació pública del Pla de Tresoreria, exercici 2026.",
    "Anunci de l'Ajuntament de València sobre l'aprovació de la reducció horària de les terrasses en plaça del Cedre.",
    "APROBACIÓN DEFINITIVA DE LA ENAJENACIÓN DE CUATRO PLAZAS DE GARAJE PROPIEDAD DEL AYUNTAMIENTO DE ALGORFA",
    "Anunci de l'Ajuntament de Torrent sobre l'aprovació definitiva del projecte de modificació puntual dels plans "
    "parcials per a la instal·lació d'una estació d'inspecció tècnica de vehicles.",
    "CONVOCATORIA JUEZ/A DE PAZ SUPLENTE",
    "BASES PROCESO DE ADMISION ESCUELA INFANTIL MUNICIPAL CURSO 24/25",
    "RELACIÓN DE OBJETOS PERDIDOS DEPOSITADOS EN LA JEFATURA DE POLICÍA LOCAL DE ALMORADÍ EN EL AÑO 2020",
    "APROBACIÓN DEFINITIVA ORDENANZA FISCAL REGULADORA DE LA TASA POR PARTICIPAR EN PRUEBAS SELECTIVAS DE PERSONAL",
    "ANUNCIO APROBACIÓN INICIAL DE LA ORDENANZA DE FUNCIONAMIENTO DEL DRON DE POLICIA LOCAL",
    "APROBACIÓN DEFINITIVA MODIFICACIÓN COMPLEMENTO ESPECÍFICO AGENTES Y OFICIALES POLICÍA LOCAL, Y DE PLANTILLA Y "
    "RELACIÓN DE PUESTOS DE TRABAJO",
    "relacion provisional de entidades admitidas y excluidas de la convocatoria de subvenciones en regimen de "
    "concurrencia competitiva destinadas a entidades sin animo de lucro",
]


# Fuentes con sección: el filtro por título deja pasar lo inequívoco aunque el tema esté excluido
@pytest.mark.parametrize("titulo", [
    "Anuncio sobre aprobación de las bases reguladoras del proceso de selección, mediante el sistema de "
    "concurso-oposición libre, de un/a técnico/a medio/a de comercio y consumo",
    "Resolución de 17 de octubre de 2023, de la Alcaldía del Ayuntamiento de Segovia, por la que se aprueban las bases "
    "del concurso de méritos para la provisión del puesto de trabajo de jefe/a de sección de urbanismo",
    "Anuncio sobre la convocatoria de provisión externa de un puesto de trabajo en régimen de personal laboral fijo "
    "(una plaza del grupo III.1 de personal técnico de becas y ayudas)",
])
def test_por_titulo_inequivoco(titulo):
    from motor.autonomicos.comun import es_empleo_por_titulo
    assert es_empleo_por_titulo(titulo)


@pytest.mark.parametrize("titulo", SI)
def test_es_empleo(titulo):
    assert es_empleo_estricto(titulo)


@pytest.mark.parametrize("titulo", NO)
def test_no_es_empleo(titulo):
    assert not es_empleo_estricto(titulo)
