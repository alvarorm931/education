import pytest

from motor.catalogo.puestos import grupo, normalizar_puesto


@pytest.mark.parametrize("a,b", [
    ("Agente de Policía Local", "Policía Local"),
    ("Agente de la Policia Local", "Policía Local"),
    ("Auxiliar Administrativa/o", "Auxiliar Administrativo/a"),
    ("Personal Auxiliar Administrativo/a", "Auxiliar administrativo"),
    ("Técnico/a Administración General", "Técnico de Administración General"),
    ("Bombera/o Conductor/a", "Bombero/a"),
    ("Oficial Policía Local", "Oficial de Policía Local"),
    ("Administrativo/a adscrito a Intervención", "Administrativo/va"),
    ("Asistente Social", "Trabajador/a social"),
])
def test_mismo_puesto(a, b):
    assert normalizar_puesto(a)["clave"] == normalizar_puesto(b)["clave"]


def test_especialidad_aparte():
    n = normalizar_puesto("Psicólogo/a (Especialidad Clínica)")
    assert n["clave"] == "psicologo" and n["especialidad"] == "Clínica"
    assert n["denominacion"] == "Psicólogo/a (Especialidad Clínica)"


def test_puestos_distintos_no_se_mezclan():
    assert normalizar_puesto("Auxiliar de Policía Local")["clave"] != normalizar_puesto("Policía Local")["clave"]
    assert normalizar_puesto("Arquitecto/a Técnico/a")["clave"] != normalizar_puesto("Arquitecto/a")["clave"]


@pytest.mark.parametrize("texto,escala,subescala,esperado", [
    ("grupo A, subgrupo A1, escala de Administración Especial", "Administración Especial", "Servicios Especiales", ("A1", "texto")),
    ("subescala Auxiliar", "Administración General", "Auxiliar", ("C2", "subescala")),
    ("subescala Técnica y clase Media", "Administración Especial", "Técnica", ("A2", "subescala")),
    ("subescala Servicios especiales y clase Policía Local", "Administración Especial", "Servicios especiales", (None, None)),
])
def test_grupo(texto, escala, subescala, esperado):
    assert grupo(texto, escala, subescala) == esperado
