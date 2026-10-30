from motor.catalogo.territorio import municipio, provincia, provincia_de_boletin, ubicar_convocante


def test_provincias_en_todas_sus_formas():
    assert provincia("Alicante/Alacant")["codigo"] == "03"
    assert provincia("València")["nombre"] == "Valencia"
    assert provincia("La Coruña")["nombre"] == "A Coruña"
    assert provincia("Baleares")["comunidad"] == "Illes Balears"
    assert provincia("Vizcaya")["nombre"] == "Bizkaia"
    assert provincia("Atlántida") is None


def test_municipios_articulo_pospuesto_y_bilingues():
    assert municipio("El Campello")["codigo_ine"] == "03050"  # INE: «Campello, el»
    assert municipio("Elche")["codigo_ine"] == municipio("Elx")["codigo_ine"] == municipio("Elx/Elche")["codigo_ine"]
    assert municipio("Alcoi/Alcoy")["provincia"] == "Alicante"
    assert municipio("Vilanova y la Geltrú")["codigo_ine"] == "08307"
    assert municipio("Palma de Mallorca")["codigo_ine"] == "07040"


def test_nombres_repetidos_solo_con_provincia_o_comunidad():
    assert municipio("Arroyomolinos") is None  # hay uno en Madrid y otro en Cáceres
    assert municipio("Arroyomolinos", provincia_codigo="28")["codigo_ine"] == "28015"
    assert municipio("Arroyomolinos", comunidad_codigo="11")["provincia"] == "Cáceres"


def test_boletines_provinciales():
    assert provincia_de_boletin("Boletín Oficial de la Provincia de Jaén")["codigo"] == "23"
    assert provincia_de_boletin("Boletín Oficial de la Comunidad de Madrid")["nombre"] == "Madrid"
    assert provincia_de_boletin("Diario Oficial de Galicia") is None  # cuatro provincias: no se adivina


def test_ubicar_convocante():
    u = ubicar_convocante({"tipo": "Ayuntamiento", "nombre": "Valverde"}, ["BOE"],
                          [{"boletin": "Boletín Oficial de la Provincia de Santa Cruz de Tenerife"}])
    assert (u["codigo_ine"], u["provincia"], u["comunidad"]) == ("38048", "Santa Cruz de Tenerife", "Canarias")
    u = ubicar_convocante({"tipo": "Ayuntamiento", "nombre": "Arroyomolinos"}, ["BOE", "DOE"])
    assert (u["codigo_ine"], u["provincia"]) == ("10023", "Cáceres")  # el DOE dice que es el de Extremadura
    u = ubicar_convocante({"tipo": "Diputación Provincial", "nombre": "Ourense"}, ["BOE"])
    assert u["provincia"] == "Ourense" and "codigo_ine" not in u
    assert ubicar_convocante({"tipo": "Ayuntamiento", "nombre": "Arroyomolinos"}, ["BOE"]).get("provincia") is None


def test_tratamientos_y_organismo_oficial():
    from motor.catalogo.territorio import municipio, ubicar_convocante
    assert municipio("Villa de los Realejos", "38")["codigo_ine"] == "38031"
    assert municipio("La Villa de Don Fadrique", "45")["codigo_ine"] == "45186"
    u = ubicar_convocante({"tipo": "Ayuntamiento", "nombre": "Facheca", "provincia": "Alicante",
                           "organismo": "AYUNTAMIENTO FAGECA"})
    assert u["codigo_ine"] == "03067"
