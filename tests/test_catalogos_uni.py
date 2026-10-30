from motor.estudios import catalogos_uni as cu


def test_emparejar_un_enlace_por_master_y_sin_ambiguedades():
    masters = [{"codigo_ruct": "4310001", "nombre": "Máster Universitario en Química Orgánica por la Universidad X"},
               {"codigo_ruct": "4310002", "nombre": "Máster Universitario en Física Teórica por la Universidad X"},
               {"codigo_ruct": "4310003", "nombre": "Máster Universitario en Historia del Arte por la Universidad X"}]
    enlaces = [("https://u.es/master/quimica-organica", "Química Orgánica"),
               ("https://u.es/master/fisica-teorica", "Más información"),          # por la dirección
               ("https://u.es/master/historia", "Historia del Arte y Física Teórica"),  # nombra dos: el mejor
               ("https://u.es/masteres", "Másteres")]
    filas, cuentas = cu.emparejar(enlaces, masters)
    por = {f["codigo_ruct"]: f["url"] for f in filas}
    assert por["4310001"] == "https://u.es/master/quimica-organica"
    assert por["4310002"] == "https://u.es/master/fisica-teorica"
    assert all(f["grupo"] == "oficial" and f["estado_emparejado"] == "catalogo_universidad" for f in filas)


def test_slug_de_la_direccion():
    assert cu._slug("https://u.es/estudios/master-en-quimica-organica/") == "master en quimica organica"
