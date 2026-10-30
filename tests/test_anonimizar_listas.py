"""El anonimizador de las sondas (rama pública) también tapa listas de personas y nombres con entidades HTML."""

from motor.mantenimiento.anonimizar import anonimizar_texto


def test_listas_en_mayusculas():
    t, n = anonimizar_texto("<td>1</td><td>GIMÉNEZ CARRO, ANA BELÉN</td><td>***1234**</td>")
    assert "GIMÉNEZ" not in t and "ANA BELÉN" not in t and n == 2
    t, n = anonimizar_texto("1 GARCÍA DE LA FUENTE, JOSÉ LUIS ***1234**\n2 PÉREZ PÉREZ, MARÍA 12345678Z")
    assert "GARCÍA" not in t and "JOSÉ" not in t and "MARÍA" not in t
    # Fuera de una tabla o de una línea con documento, un título en mayúsculas con coma se queda como está
    x = "DEPARTAMENTO DE HACIENDA, INTERIOR Y ADMINISTRACIÓN PÚBLICA"
    assert anonimizar_texto(x) == (x, 0)


def test_lo_institucional_no_se_toca():
    for x in ("AYUNTAMIENTO DE MADRID, CONCEJALÍA", "BOLETÍN OFICIAL DE CANTABRIA, NÚM", "CUERPO DE GESTIÓN, GRUPO A2"):
        assert anonimizar_texto(x) == (x, 0)


def test_celdas_y_entidades():
    t, _ = anonimizar_texto("<td>Giménez Carro, Ana Belén</td>")
    assert "Giménez" not in t
    t, _ = anonimizar_texto("por el que se nombra a do&ntilde;a Cristina Fern&aacute;ndez Rabanillo, como directora")
    assert "Cristina" not in t and "Fern&aacute;ndez" not in t
