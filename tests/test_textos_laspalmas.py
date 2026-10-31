"""BOP de Las Palmas: el texto de cada anuncio, del registro con puntos del anterior al suyo (formato del PDF del
30/10/2026 en modo «layout»; textos inventados)."""
from motor.limpieza import limpiar_texto
from motor.provinciales import textos as t

SUMARIO1 = """                   BOLETÍN OFICIAL DE LA PROVINCIA DE
                                                                  LAS PALMAS
Año CI                                                                Viernes, 30 de octubre de 2026        Número 130
                                                                             SUMARIO
NÚMERO
REGISTRO                                                                                                          PÁGINA
              III. ADMINISTRACIÓN LOCAL
              EXCMO. CABILDO INSULAR DE FUERTEVENTURA
  2198627 Expediente de Modificación de Créditos número 52/2026 ..........................................      18639
              EXCMO. CABILDO INSULAR DE GRAN CANARIA
  2196984  Lista definitiva de admitidos/as y excluidos/as de 1 plaza de Agente de Medio Ambiente (OEP 2018) ......  18639
  2200508 Bases para cubrir 2 plazas de Técnico de Administración General por concurso-oposición, en
              el turno libre y por el sistema de estabilización.............................................      18640
"""
SUMARIO2 = """   18638                                                              Boletín Oficial de la Provincia de Las Palmas. Número 130, viernes 30 de octubre de 2026
              ILUSTRE AYUNTAMIENTO DE INGENIO
2202972A Modificación de la ordenanza fiscal reguladora del impuesto sobre construcciones (IP-1)..........          18641
2202972B Modificación de la ordenanza fiscal reguladora de la tasa de servicios urbanísticos (TS-10)......          18641
              ILUSTRE AYUNTAMIENTO DE TEROR
  2198178 Convocatoria de 1 plaza de Administrativo por promoción interna .......................................      18641
"""
P18639 = """Boletín Oficial de la Provincia de Las Palmas. Número 130, viernes 30 de octubre de 2026                    18639
                                              III. ADMINISTRACIÓN LOCAL
                            EXCMO. CABILDO INSULAR DE FUERTEVENTURA
                                                                ANUNCIO
3.466
  Se hace público que el Pleno aprobó definitivamente el Expediente de Modificación de Créditos número 52/2026.
                                                                                                                                    2.198.627
                            EXCMO. CABILDO INSULAR DE GRAN CANARIA
                                                                ANUNCIO
3.467
  Se aprueba la lista definitiva de admitidos de la plaza de Agente de Medio Ambiente.
  1. ***1234** Persona Inventada Uno
                                                                                                                                    2.196.984
"""
P18640 = """   18640                                                              Boletín Oficial de la Provincia de Las Palmas. Número 130, viernes 30 de octubre de 2026
                                                                ANUNCIO
3.468
  BASES PARA CUBRIR DOS PLAZAS DE TÉCNICO DE ADMINISTRACIÓN GENERAL.
  Primera. Objeto. Dos plazas del grupo A1 por concurso-oposición.
  Segunda. Requisitos: título de grado en Derecho.
"""
P18641 = """Boletín Oficial de la Provincia de Las Palmas. Número 130, viernes 30 de octubre de 2026                    18641
  Tercera. Plazo: veinte días hábiles.
                                                                                                                                    2.200.508
                            ILUSTRE AYUNTAMIENTO DE INGENIO
  Se aprueban definitivamente las ordenanzas fiscales IP-1 y TS-10.
                                                                                                                                    2.202.972
                            ILUSTRE AYUNTAMIENTO DE TEROR
  Convocatoria de una plaza de Administrativo por promoción interna. Plazo: diez días.
                                                                                                                                    2.198.178
"""
PAGINAS = [SUMARIO1, SUMARIO2, P18639, P18640, P18641]
ANUNCIOS = [
    {"id": "LP-1", "titulo": "Expediente de Modificación de Créditos número 52/2026"},
    {"id": "LP-2", "titulo": "Lista definitiva de admitidos/as y excluidos/as de 1 plaza de Agente de Medio Ambiente (OEP 2018)"},
    {"id": "LP-3", "titulo": "Bases para cubrir 2 plazas de Técnico de Administración General por concurso-oposición, en el turno"},
    {"id": "LP-4", "titulo": "Modificación de la ordenanza fiscal reguladora del impuesto sobre construcciones (IP-1)"},
    {"id": "LP-5", "titulo": "Modificación de la ordenanza fiscal reguladora de la tasa de servicios urbanísticos (TS-10)"},
    {"id": "LP-6", "titulo": "Convocatoria de 1 plaza de Administrativo por promoción interna"},
]


def test_sumario_con_registros_y_partes():
    s, n = t.entradas_sumario_final(PAGINAS)
    assert n == 2
    assert [(r, p) for r, _, p in s] == [("2198627", 18639), ("2196984", 18639), ("2200508", 18640),
                                         ("2202972", 18641), ("2202972", 18641), ("2198178", 18641)]
    assert s[2][1].endswith("en el turno libre y por el sistema de estabilización")


def test_corte_por_registro_final():
    cortes = t.cortar_por_registro_final(PAGINAS, ANUNCIOS)
    bases, paginas = cortes["LP-3"]
    assert "Primera. Objeto" in bases and "Tercera. Plazo" in bases and "Agente de Medio Ambiente" not in bases
    assert paginas == [4, 5]
    assert "Administrativo por promoción interna" in cortes["LP-6"][0] and "IP-1" not in cortes["LP-6"][0]
    # las dos partes de un mismo registro comparten su anuncio
    assert cortes["LP-4"][0] == cortes["LP-5"][0] and "ordenanzas fiscales" in cortes["LP-4"][0]
    limpio = limpiar_texto(bases, t.CABECERAS["boplaspalmas"])["texto"]
    assert "Boletín Oficial de la Provincia" not in limpio and "2.200.508" not in limpio and "3.468" not in limpio


def test_sin_la_marca_del_anterior_no_hay_texto():
    sin_marca = [p.replace("2.196.984", "") for p in PAGINAS]
    cortes = t.cortar_por_registro_final(sin_marca, ANUNCIOS)
    assert "LP-2" not in cortes and "LP-3" not in cortes  # el texto de LP-3 empezaría en el de LP-2
    assert "LP-1" in cortes and "LP-6" in cortes
