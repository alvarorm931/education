"""Alcance con las reglas vigentes del título (motor/boe/clasificar.py: alcance_vigente) y oferta pública de empleo."""

from motor.autonomicos.comun import clasificar
from motor.boe.clasificar import alcance_vigente


def test_oferta_publica_de_empleo():
    assert clasificar("ANUNCIO sobre aprobación de la oferta pública de empleo para el 2023.")["tipo_acto"] == "oferta_empleo"
    assert clasificar("Aprobación de la oferta extraordinaria de empleo de estabilización")["tipo_acto"] == "oferta_empleo"
    # Lo que cita la oferta sigue siendo lo que es
    assert clasificar("Lista provisional de admitidos y excluidos de una plaza de la oferta pública de empleo 2023"
                      )["tipo_acto"] == "admitidos"


def test_no_seleccion_y_provision():
    assert alcance_vigente("Cese funcionario interino (Decreto 004/2022, de 13 de enero).", "otro", None, "acceso") \
        == "no_seleccion"
    assert alcance_vigente("Madrid. Personal. Área de Gobierno de Hacienda y Personal. Relación puestos trabajo", "otro",
                           None, "acceso") == "no_seleccion"
    assert alcance_vigente("Resolución 325/2024, de la Dirección General de Relaciones Municipales, por la que se confiere "
                           "nombramiento accidental para el puesto de Secretaría-Intervención de la Mancomunidad de Uribe "
                           "Kosta.", "nombramiento", None, "acceso") == "provision_puestos"
    assert alcance_vigente("Concurso de traslados. Corrección de errores de la Resolución de 13 de junio de 2025",
                           "correccion", None, None) == "provision_puestos"


def test_lo_de_un_proceso_sigue_en_acceso():
    assert alcance_vigente("Nombramiento de funcionario de carrera y cese de funcionario interino", "nombramiento", None,
                           "acceso") == "acceso"
    assert alcance_vigente("Corrección de errores de las bases de una plaza de Administrativo (complemento de destino 22)",
                           "correccion", None, "acceso") == "acceso"
    # Lo que el epígrafe ya dejaba fuera no vuelve
    assert alcance_vigente("Lista de admitidos", "admitidos", None, "docente_universitario") == "docente_universitario"
    assert alcance_vigente(None, "otro", None, None) is None


def test_texto_guardado_vacio_no_para_los_actos(tmp_path):
    from motor.autonomicos.actos import recuento_de, ruta_texto, texto_de
    from motor.autonomicos.comun import escribir_json
    x = {"id": "BOP-SE-2025-1", "fecha": "2025-03-04"}
    r = ruta_texto(tmp_path, "bopsevilla", x)
    r.parent.mkdir(parents=True)
    r.write_text("", encoding="utf-8")
    assert texto_de(tmp_path, "bopsevilla", x) is None and recuento_de(tmp_path, "bopsevilla", x) is None
    escribir_json(r, {"texto": "hola"})
    assert texto_de(tmp_path, "bopsevilla", x) == "hola" and not list(r.parent.glob(".*.tmp"))
