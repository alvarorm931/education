from motor.grados import asignaturas as asg


def test_clave_sin_numeracion():
    assert asg.clave_asignatura("Derecho Civil I") == asg.clave_asignatura("Derecho civil II")
    assert asg.clave_asignatura("Estadística") != asg.clave_asignatura("Estadística Aplicada")


def _a(n, c=6, t="obligatoria", curso=1):
    return {"nombre": n, "creditos": c, "tipo": t, "curso": curso}


def test_comparar_tres_universidades():
    planes = {
        "A": [_a("Derecho Civil I"), _a("Derecho Romano"), _a("Derecho Penal", curso=2), _a("Criminología Forense")],
        "B": [_a("Derecho civil II"), _a("Derecho Romano"), _a("Derecho Penal", curso=2), _a("Deporte", t="optativa")],
        "C": [_a("Derecho Civil"), _a("Derecho Penal", curso=2), _a("Historia del Derecho")],
    }
    r = asg.comparar(planes)
    comunes = {x["asignatura"]: x["titulos"] for x in r["asignaturas_comunes"]}
    assert comunes["Derecho Penal"] == 3 and comunes["Derecho Romano"] == 2
    assert r["por_titulo"]["A"]["asignaturas_solo_aqui"] == ["Criminología Forense"]
    assert r["por_titulo"]["A"]["porcentaje_comun"] == 75.0  # 18 de 24 créditos no optativos
    assert r["por_titulo"]["B"]["asignaturas_solo_aqui"] == []  # la optativa no cuenta
    assert r["por_titulo"]["C"]["primer_curso"] == ["Derecho Civil", "Historia del Derecho"]
