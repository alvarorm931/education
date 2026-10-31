"""BOP de Ourense: boletín del día por la API y texto de un edicto (respuestas reales del 29/10/2026 y del 03/01/2022;
en el edicto de nombramiento se ha retirado el nombre de la persona)."""

from datetime import date
from pathlib import Path

from motor.provinciales import bopourense as o

FIX = Path(__file__).parent / "fixtures"


def test_urls():
    assert o.url_dia(date(2026, 10, 29)).endswith("/portalapi/api/boletin/getFecha/20261029")
    assert o.url_edicto(353077).endswith("/portalapi/api/edicto/descargar/html/353077/es")


def test_dia():
    b = o.leer_dia((FIX / "bopourense_20261029.json").read_bytes())[0]
    assert (b["numero"], b["fecha"], len(b["anuncios"]), b["extraordinario"]) == (208, "2026-10-29", 18, False)
    sel = o.seleccionar([{**x, "id": x["numero_anuncio"]} for x in b["anuncios"]])
    assert [x["tipo_acto"] for x in sel] == ["nombramiento", "nombramiento", "convocatoria", "convocatoria"]
    b = o.leer_dia((FIX / "bopourense_20220103.json").read_bytes())[0]
    assert (b["numero"], b["fecha"], len(b["anuncios"])) == (1, "2022-01-03", 8)
    assert o.seleccionar([{**x, "id": x["numero_anuncio"]} for x in b["anuncios"]]) == []  # un curso no es empleo


def test_edicto():
    t = o.leer_edicto((FIX / "bopourense_edicto_353077.html").read_bytes(), {"tipo_acto": "convocatoria"})
    assert t["entidad"] == "AYUNTAMIENTO DE SAN CIBRAO DAS VIÑAS" and "personal laboral fijo" in t["texto"]
    t = o.leer_edicto((FIX / "bopourense_edicto_353096.html").read_bytes(), {"tipo_acto": "nombramiento"})
    assert t["entidad"] == "AYUNTAMIENTO DE A ARNOIA" and t["texto"] is None and t["solo_recuento"]
    c = o.convocante(t["entidad"], "IV. ENTIDADES LOCALES")
    assert (c["nombre"], c["provincia"]) == ("A Arnoia", "Ourense")
    assert o.convocante(None, "I. DIPUTACIÓN PROVINCIAL DE OURENSE")["tipo"] == "Diputación Provincial"


# Sumario del PDF del boletín entero del 30/01/2023 (sin maquetar: los edictos no tienen texto propio)
SUMARIO_2023 = """Dep. legal: OR-1/1958 · Franqueo concertado 30/2
Boletín oficial
provincia de ourense
n.º 24 · luns, 30 xaneiro 2023
suMario
i. deputación provincial de ourense
Exposición pública dos padróns e listas cobratorias da taxa ........... 2
iv. entidades locais
Barbadás
Convocatoria e bases de selección do proceso selectivo
para a provisión, mediante interinidade, do posto de traballo .............. 3
I. DIPUTACIÓN PROVINCIAL DE OURENSE
Exposición pública de los padrones y listas cobratorias de la tasa
por el suministro de agua ........... 2
IV . ENTIDADES LOCALES
Barbadás
Convocatoria y bases de selección del proceso selectivo
para la provisión, mediante interinidad, del puesto de trabajo
reservado a funcionarios/as de Administración Local ............. 15
Chandrexa de Queixa
Corrección de errores en la convocatoria del proceso de selección
para cubrir una plaza de auxiliar administrativo/a .................................... 27
Rúa (A)
Exposición pública del padrón de la tasa por el servicio ...................... 28
"""


def test_entidad_del_sumario_del_pdf():
    e = o.sumario_pdf([SUMARIO_2023])
    assert [(x["entidad"], x["pagina"]) for x in e] == [(None, 2), ("Barbadás", 15), ("Chandrexa de Queixa", 27),
                                                       ("Rúa (A)", 28)]
    edictos = [{"id": "E1", "titulo": "Convocatoria y bases de selección del proceso selectivo para la provisión, "
                                      "mediante interinidad, del puesto de trabajo reservado"},
               {"id": "E2", "titulo": "Corrección de errores en la convocatoria del proceso de selección para cubrir "
                                      "una plaza de auxiliar administrativo/a"},
               {"id": "E3", "titulo": "Exposición pública del padrón de la tasa por el servicio de suministro"},
               {"id": "E4", "titulo": "Otro asunto que no está"}]
    ents = o.entidades_de_paginas([SUMARIO_2023], edictos)
    assert ents == {"E1": "Ayuntamiento de Barbadás", "E2": "Ayuntamiento de Chandrexa de Queixa",
                    "E3": "Ayuntamiento de A Rúa"}
    c = o.convocante(ents["E3"], "IV. ENTIDADES LOCALES")
    assert (c["nombre"], c["provincia"]) == ("A Rúa", "Ourense")
    b = o.leer_dia((FIX / "bopourense_20220103.json").read_bytes())[0]
    assert b["maquetado"] is False and b["id_boletin"] == 67594
