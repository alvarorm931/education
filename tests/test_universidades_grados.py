from motor.grados import universidades as un


def test_universidad_desde_sus_fichas():
    fichas = [{"clase": "grado", "rama": "CSJ", "modalidades": ["Estudio presencial"],
               "universidades": [{"nombre": "Granada", "codigo": "008", "tipo": "Pública", "comunidad": "Andalucía"}],
               "centros": [{"codigo": "1", "nota_corte": 8.0, "plazas": 100}, {"codigo": "2", "nota_corte": 5.0, "plazas": 50}]},
              {"clase": "doble", "rama": None, "modalidades": ["Estudio presencial"],
               "universidades": [{"nombre": "Granada", "codigo": "008", "tipo": "Pública", "comunidad": "Andalucía"}],
               "centros": [{"codigo": "1", "nota_corte": 10.0, "plazas": 20}]}]
    u = un.construir(fichas, {"008": {"web": "https://www.ugr.es", "nombre": "Universidad de Granada"}}, {})[0]
    assert (u["grados"], u["dobles"], u["plazas_nuevo_ingreso"], u["web"]) == (1, 1, 170, "https://www.ugr.es")
    assert u["nota_corte_mediana"] == 9.0 and u["ofertas_con_nota_de_corte_mayor_de_5"] == 2
