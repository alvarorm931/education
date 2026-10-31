import json
import re

from motor.grados import memorias_web as mw


def test_rutas_de_memorias_de_grado():
    si = ["/export/sites/uni/.galleries/docs/Memoria_Verificada_Grado_Derecho.pdf",
          "/calidad/memorias/grado-en-historia.pdf", "/documents/MEMORIA-VERIFICACION-GIQ.pdf",
          "/estudis/mem%c3%b2ria-grau-dret.pdf"]
    no = ["/memoria-anual-2023.pdf", "/memoria_master_finanzas.pdf", "/memorias/memoria-economica-2022.pdf",
          "/grado/plan-de-estudios.pdf", "/memoria_verificacion.html"]
    for r in si:
        assert re.search(mw.INCLUIR, r.lower()) and not re.search(mw.EXCLUIR, r.lower()), r
    for r in no:
        assert not (re.search(mw.INCLUIR, r.lower()) and not re.search(mw.EXCLUIR, r.lower())), r


def test_despliegue_por_columnas():
    cab = "ECTS Semestral 1        ECTS Semestral 2        ECTS Semestral 3"
    val = "                        6                       6"
    assert mw.despliegue_de_lineas(cab, val) == {"2": 6.0, "3": 6.0}
    assert mw.despliegue_de_lineas("ECTS Semestral 7", "   9") == {"7": 9.0}


def test_plan_de_texto_con_tres_niveles():
    # disposición inventada con los rótulos de la aplicación del Ministerio (no es texto de ninguna memoria)
    lineas = """5.5 NIVEL 1: Formación Básica
5.5.1 Datos Básicos del Nivel 1
NIVEL 2: Matemáticas
5.5.1.1 Datos Básicos del Nivel 2
CARÁCTER        Básica
ECTS NIVEL 2    12
DESPLIEGUE TEMPORAL: Semestral
ECTS Semestral 1        ECTS Semestral 2        ECTS Semestral 3
6                       6
NIVEL 3: Cálculo
5.5.1.1.1 Datos Básicos del Nivel 3
CARÁCTER        ECTS ASIGNATURA        DESPLIEGUE TEMPORAL
Básica          6                      Semestral
ECTS Semestral 1        ECTS Semestral 2
6
NIVEL 3: Álgebra
CARÁCTER        ECTS ASIGNATURA        DESPLIEGUE TEMPORAL
Básica          6                      Semestral
ECTS Semestral 1        ECTS Semestral 2
                        6
5.5 NIVEL 1: Trabajo Fin de Grado
NIVEL 2: Trabajo Fin de Grado
CARÁCTER        Trabajo Fin de Grado / Máster
ECTS NIVEL 2    12
DESPLIEGUE TEMPORAL: Semestral
ECTS Semestral 7        ECTS Semestral 8
                        12""".splitlines()
    r = mw.plan_de_texto(lineas)
    assert r["cobertura"] == {"modulos": 2, "materias": 2, "asignaturas": 2, "con_caracter": 3, "con_ects": 3,
                              "con_despliegue": 3}
    m = r["plan"][0]["materias"][0]
    assert m["nombre"] == "Matemáticas" and m["ects"] == 12.0 and m["despliegue"] == {"1": 6.0, "2": 6.0}
    assert [(a["nombre"], a["caracter"], a["ects"], a["despliegue"]) for a in m["asignaturas"]] == [
        ("Cálculo", "Básica", 6.0, {"1": 6.0}), ("Álgebra", "Básica", 6.0, {"2": 6.0})]
    t = r["plan"][1]["materias"][0]
    assert t["caracter"] == "Trabajo Fin de Grado / Máster" and t["despliegue"] == {"8": 12.0}
    assert r["plan"][0]["ects"] == 12.0 and r["plan"][1]["ects"] == 12.0
    # con la misma forma que la memoria del RUCT, el plan se comprueba igual
    from motor.grados.fichas import plan_de_memoria

    p = plan_de_memoria({"creditos": {"total": 24.0, "optativos": 0.0}, "fuente": {},
                         "memoria": {"cod": "x", "avisos": [], "plan": r["plan"]}})
    assert p["suma_sin_optativas"] == 24.0 and p["comprobacion"] == "con_creditos_del_ruct"


def test_cabecera_de_la_memoria():
    texto = "Identificador : 2501234\nFecha : 15/06/2021\nDenominación del Título Graduado o Graduada en Historia por la Universidad X"
    assert mw.IDENTIFICADOR.findall(texto) == ["2501234"] and mw.FECHA.findall(texto) == ["15/06/2021"]
    assert mw.DENOMINACION.search(texto).group(1) == "Graduado o Graduada en Historia"


def test_urls_repartidas_por_servidor(tmp_path):
    d = tmp_path / "a" / "datos" / "estudios" / "grados" / "memorias_web"
    d.mkdir(parents=True)
    filas = [{"dominio": dom, "url": f"https://www.{dom}/{i}/memoria.pdf"} for dom in ("ua.es", "ub.edu", "uca.es")
             for i in range(3)]
    (d / "urls_x_0_1.jsonl").write_text("\n".join(json.dumps(x) for x in filas + filas[:2]), encoding="utf-8")
    todas = mw.urls_de(tmp_path, None)
    assert len(todas) == 9
    (d / "memorias_1_x.jsonl").write_text(json.dumps({"url": filas[0]["url"], "estado": 200}), encoding="utf-8")
    assert len(mw.urls_de(tmp_path, None)) == 8  # ya pedida en una lectura anterior
    (d / "memorias_1_x.jsonl").unlink()
    partes = [mw.urls_de(tmp_path, (i, 2)) for i in range(2)]
    assert sum(len(p) for p in partes) == 9
    assert not {x["dominio"] for x in partes[0]} & {x["dominio"] for x in partes[1]}


def test_dominios_de_las_universidades():
    doms = mw.dominios()
    assert doms["ucm.es"]["universidad"] == "Universidad Complutense de Madrid" and len(doms) > 90


def test_enlaces_a_memorias_de_una_pagina_de_calidad():
    html = """<ul>
      <li><a href="/doc/grau-dret/memoria-verificada.pdf">Memòria verificada</a></li>
      <li><a href="https://www.u.es/docs/G_Historia.pdf">Memoria de verificación del título</a></li>
      <li><a href="/doc/master-x/memoria.pdf">Memoria del máster</a></li>
      <li><a href="/doc/memoria-anual-2024.pdf">Memoria anual</a></li>
      <li><a href="/doc/plan.pdf">Plan de estudios</a></li>
      <li><a href="/grado/informe.html">Informe de verificación</a></li>
    </ul>"""
    assert mw.enlaces_a_memorias(html, "https://www.u.es/grado/calidad") == [
        "https://www.u.es/doc/grau-dret/memoria-verificada.pdf", "https://www.u.es/docs/G_Historia.pdf"]
