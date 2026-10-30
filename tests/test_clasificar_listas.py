"""Títulos de listas de personas que se clasificaban con un tipo que guarda el texto (revisión de la rama de datos,
30/10/2026), en castellano, catalán, gallego y euskera. Las listas solo guardan el recuento."""

from motor.autonomicos.comun import clasificar
from motor.provinciales.comun import CON_TEXTO


def test_listas_no_guardan_texto():
    for t in ("Listas provisionales de admitidos en las plazas de administrativo; operario; ayudantes de cocina",
              "LISTADO ADMITIDOS Y EXLCUIDOS BOLSA FUNCIONARIOS INTERINOS ARQUITECTO", "RESOLUCION PROVISIONAL ADMITIDOS",
              "APROBACIÓN PROVISIONAL DE LA RELACIÓN DE ASPIRANTES PARA UNA PLAZA DE TÉCNICO AUXILIAR DE BIBLIOTECA",
              "Anuncio de la publicación de la relación definitiva de persona seleccionada y puesto adjudicado",
              "Resultado definitivo del proceso de selección de personal laboral fijo de una plaza de administrativo.",
              "Baremación definitiva selección de cinco Conductores Recolectores de Residuos",
              "Calificaciones del proceso de selección de un Trabajador Social",
              "Adjudicación de plazas del proceso selectivo excepcional de estabilización.",
              "Selección del aspirante aprobado en el proceso selectivo de una plaza de Arquitecto A1.",
              "Constitución lista de espera Trabajador/a Social.",
              "ACTA DE CONSTITUCIÓN Y VALORACIÓN DE MÉRITOS EN EL PROCESO SELECTIVO DE PLAZA DE PEON",
              "Adjudicació de places en el marc dels processos d'estabilització de l'ocupació temporal",
              "Resultats definitius del procés selectiu d'una plaça d'auxiliar administratiu",
              "LISTAXE DE PERSOAS ADMITIDAS, TRIBUNAL E DATA DE CONSTITUCIÓN PARA A COBERTURA DE 3 PRAZAS",
              "RESULTADOS DO PROCEDEMENTO SELECTIVO DE AUXILIAR DE AXUDA NO FOGAR COMO PERSOAL LABORAL FIXO",
              "Publicación adxudicación de 4 postos de policía do Concello da Coruña",
              "Aprobación definitiva listaxe de espera aos efectos de chamamentos en postos interinos",
              "Onartuen eta baztertuen behin-behineko zerrenda. Administrari laguntzailea",
              "ANUNCIO del resultado definitivo del proceso de selección de una plaza de peón"):
        assert clasificar(t)["tipo_acto"] not in CON_TEXTO, t


def test_bases_y_convocatorias_siguen_con_texto():
    for t in ("BASES REGULADORAS Y CONVOCATORIA DE PROCESO SELECTIVO PARA LA FORMACIÓN DE LISTA DE ESPERA DE CONDUCTOR",
              "Aprobación de las bases que regulan la convocatoria para la creación de una bolsa de trabajo de Aparejador",
              "CONVOCATORIA E BASES PARA A ELABORACIÓN DUNHA LISTAXE DE EMPREGO DE TÉCNICO/A DE PROXECTOS",
              "Aprovació de les bases i la convocatòria per a la creació d'una borsa de treball de monitor/a",
              "Bases para la provisión de 3 plazas por concurso incluidas en oferta de empleo aprobada al amparo de la Ley"):
        assert clasificar(t)["tipo_acto"] in CON_TEXTO, t
