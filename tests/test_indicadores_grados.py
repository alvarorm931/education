from motor.grados import indicadores as ind

PX = '''AXIS-VERSION="2006";
CHARSET="ANSI";
TITLE="Tasas de abandono del estudio por "
"ámbito de estudio y sexo";
STUB="Universidad","Ámbito de estudio";
HEADING="Sexo","Periodo";
VALUES("Universidad")="Todas las universidades","Complutense de Madrid";
VALUES("Ámbito de estudio")="Derecho";
VALUES("Sexo")="Ambos sexos","Mujeres";
VALUES("Periodo")="2018-2019","2019-2020";
DATA=
21.5 20.1 19 18
23.19 18.75 ".." 17.2;
'''


def test_leer_px_y_orden_de_la_matriz():
    px = ind.leer_px(PX)
    assert px["variables"] == ["Universidad", "Ámbito de estudio", "Sexo", "Periodo"]
    assert px["meta"]["TITLE"].startswith("Tasas de abandono del estudio por ámbito")
    f = list(ind.filas(px, {"Sexo": "Ambos sexos"}))
    ucm = [x for x in f if x["Universidad"] == "Complutense de Madrid"]
    assert [(x["Periodo"], x["valor"]) for x in ucm] == [("2018-2019", 23.19), ("2019-2020", 18.75)]
    mujeres = [x for x in ind.filas(px, {"Sexo": "Mujeres", "Universidad": "Complutense de Madrid"})]
    assert mujeres[0]["valor"] is None and mujeres[1]["valor"] == 17.2  # «..» = dato no disponible


def test_matriz_incompleta_avisa():
    import pytest
    with pytest.raises(ValueError):
        list(ind.filas(ind.leer_px(PX.replace(' 17.2', '')), None))
