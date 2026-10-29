"""Plazas convocadas con frases literales de convocatorias reales del BOE (2025-2026)."""

from motor.extraccion.plazas import extraer_plazas


def test_cuerpo_con_subgrupo():
    p = extraer_plazas("2.1 Se convoca proceso selectivo para cubrir cincuenta plazas del Cuerpo Especial de "
                       "Instituciones Penitenciarias, Subgrupo A2 (Código 0913) por el sistema general de acceso libre.")
    assert p["total"] == 50 and p["turno"] == "libre"
    assert p["plazas"][0]["denominacion"] == "Cuerpo Especial de Instituciones Penitenciarias"
    assert p["plazas"][0]["grupo"] == "A2"


def test_escala_universitaria():
    p = extraer_plazas("1.1 Se convocan pruebas selectivas para cubrir, por el sistema de concurso-oposición libre, doce "
                       "plazas de funcionario de carrera en la Escala Auxiliar Técnica de la Universidad de Almería "
                       "(Subgrupo C2).")
    assert p["total"] == 12
    pl = p["plazas"][0]
    assert pl["denominacion"] == "Escala Auxiliar Técnica de la Universidad de Almería" and pl["grupo"] == "C2"
    assert pl["puesto_clave"] == "escala-auxiliar-tecnico"


def test_desglose_por_categorias():
    p = extraer_plazas("2.2 En concreto, se convoca proceso selectivo para cubrir 68 plazas de acceso libre, 4 en la "
                       "categoría de Albañil, 5 en la categoría de Calefactor/a, 3 en la categoría de Carpintero/a.")
    assert p["total"] == 68
    assert [(x["numero"], x["denominacion"]) for x in p["plazas"]] == [(4, "Albañil"), (5, "Calefactor/a"),
                                                                       (3, "Carpintero/a")]


def test_categoria_laboral():
    p = extraer_plazas("1.1 Se convoca proceso selectivo para proveer una plaza de personal laboral en la categoría de "
                       "Técnico Especialista (Gestión de Datos) de la Universidad de Córdoba, Grupo III, en régimen de "
                       "Personal Laboral Fijo, por el sistema general de acceso libre.")
    assert p["total"] == 1 and p["plazas"][0]["denominacion"].startswith("Técnico Especialista")


def test_no_confunde_convocatorias_pasadas():
    assert extraer_plazas("Por Acuerdo de 15 de julio de 2025 se convocó un proceso selectivo para proveer una plaza "
                          "de personal laboral, con la categoría de Técnico.") is None
