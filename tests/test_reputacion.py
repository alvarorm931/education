from motor.estudios.reputacion import posicion


def test_orden_por_reputacion():
    assert posicion("Barcelona") < posicion("Autónoma de Barcelona") < posicion("Complutense de Madrid")
    assert posicion("Autónoma de Barcelona") != posicion("Barcelona")  # gana la clave más larga
    assert posicion("Politècnica de València") < posicion("València (Estudi General)")
    assert posicion("Pública de Navarra") == posicion("Jaén") > posicion("Navarra")
    assert posicion("Católica de Valencia San Vicente Mártir") == posicion("Internacional de La Rioja")
