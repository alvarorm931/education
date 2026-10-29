from pathlib import Path

from motor.estudios import catalogo as cat

F = Path(__file__).parent / "fixtures" / "siiu"


def _leer(nombre):
    _, clave, hoja = cat.FICHEROS[nombre]
    return cat.filas((F / f"{nombre}.xlsx").read_bytes(), clave, hoja)


def _catalogo():
    return cat.construir(_leer("titulaciones"), _leer("rama"), _leer("centros"), _leer("universidades"), "2025-2026")


def test_solo_masters_simples_y_dobles():
    c = {t["codigo_ruct"]: t for t in _catalogo()}
    assert "2500094" not in c  # grado
    assert c["4318301"]["tipo"] == "simple"
    assert c["7500155"]["tipo"] == "doble"
    assert c["7500155"]["componentes"] == ["Máster Universitario en Ingeniería de Telecomunicación",
                                            "Máster Universitario en Ciberseguridad"]


def test_union_con_rama_universidad_y_centro():
    t = {t["codigo_ruct"]: t for t in _catalogo()}["4318301"]
    assert t["universidad"] == "Politécnica de Madrid" and t["universidad_codigo"] == "025"
    assert t["rama"] == "Ingeniería y Arquitectura"
    assert t["universidad_comunidad"] == "Madrid (Comunidad de)"
    i = t["imparticiones"][0]
    assert i["unidad_codigo"] == "28026870"  # coincide con la ficha del RUCT
    assert i["presencialidad"] == "Estudio presencial"


def test_codigos_como_texto_con_ceros():
    centros = _leer("centros")
    assert all(isinstance(c["Código de la unidad"], str) and len(c["Código de la unidad"]) == 8 for c in centros)


def test_descubrir_enlaces():
    html = ('<ul><li><a href="/dam/jcr:1/Titulaciones_unidad_presenc-2025.xlsx">Titulaciones en universidades españolas, '
            'por unidad/centro, presencialidad e idioma extranjero. Curso 2025-2026 (xls)</a></li>'
            '<li><a href="/dam/jcr:2/rama.xlsx">Titulaciones según <b>rama, ISCED 2013</b>, ámbito</a></li>'
            '<li><a href="/dam/jcr:3/c.xlsx">Centros / Unidades impartiendo titulaciones, por ubicación</a></li>'
            '<li><a href="/dam/jcr:4/u.xlsx">Universidades españolas, por tipo, presencialidad</a></li></ul>')
    u = cat.descubrir(html)
    assert u["titulaciones"] == "https://www.ciencia.gob.es/dam/jcr:1/Titulaciones_unidad_presenc-2025.xlsx"
    assert cat._curso(u["titulaciones"], None) == "2025-2026"


def test_resumen():
    r = cat.resumen(_catalogo())
    assert r["activos_por_tipo"]["doble"] >= 1
    assert r["imparticiones_sin_codigo_de_centro"] == 0
