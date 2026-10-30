"""Unión de actos posteriores con su proceso (motor/union.py), con títulos reales del BOE y de los BOP."""

from datetime import date

from motor import union as u


def test_piezas_del_titulo():
    assert u.disposicion("Resolución de 15 de julio de 2026, de la Subsecretaría, por la que se convoca", "2026-07-20") \
        == ("2026-07-15", None)
    assert u.disposicion("Orden PJC/154/2024, de 19 de febrero, por la que se corrigen errores", "2024-02-25") \
        == ("2024-02-19", "PJC/154/2024")
    assert u.cita_convocatoria("Resolución de 5 de marzo de 2023, de la Subsecretaría, por la que se modifica la "
                               "composición del Tribunal del proceso selectivo, convocado por Resolución de 21 de "
                               "diciembre de 2022.", "2023-03-10") == ("2022-12-21", None)
    assert u.cita_convocatoria("relación de aprobados del proceso convocado por Orden HFP/123/2026, de 2 de marzo",
                               "2026-09-01") == ("2026-03-02", "HFP/123/2026")
    assert u.organo("Resolución de 16 de julio de 2026, del Instituto Nacional de Gestión Sanitaria, por la que") \
        == "instituto nacional de gestion sanitaria"
    assert u.expediente("procedimiento para seleccionar una plaza de superintendente/a (exp. AJT/37548/2022).") \
        == "AJT/37548/2022"


def test_puesto_del_titulo():
    assert u.puesto("Relación definitiva de admitidos y excluidos para la provisión, por oposición libre, de 4 plazas "
                    "de Auxiliar Administrativo. Nombramiento del Tribunal") == "auxiliar-administrativo"
    assert u.puesto("Nombramiento de funcionaria de carrera (Técnica de Exacciones y Rentas).") == "tecnico-exacciones-rentas"
    assert u.puesto("NOMBRAMIENTO FUNCIONARIO DE CARRERA INSPECTOR DE POLICÍA LOCAL.") == "inspector-policia-local"
    assert u.puesto("Lista provisional del proceso para la selección de un Notificador mediante") == "notificador"
    # la provincia entre paréntesis y «plazas vacantes» no son puestos
    assert u.puesto("Resolución de 6 de mayo de 2026, del Ayuntamiento de Baena (Córdoba), referente a la "
                    "convocatoria para proveer varias plazas vacantes.") is None


def _proc(ident, titulo, apertura, claves_puesto=(), total=None):
    return {"id": ident, "titulo": titulo, "apertura_plazo": apertura, "estado": "plazo_cerrado", "total_plazas": total,
            "plazas": [{"puesto_clave": k} for k in claves_puesto], "otras_publicaciones": [],
            "actos": [{"id": ident.split(":", 1)[-1], "fecha": apertura, "tipo": "convocatoria"}]}


def test_unir_por_convocante_y_puesto_y_por_cita():
    procesos = [
        _proc("bop:1", "Bases de la convocatoria de 4 plazas de Auxiliar Administrativo", "2025-03-01",
              ["auxiliar-administrativo"], 4),
        _proc("bop:2", "Bases de la convocatoria de una plaza de Arquitecto", "2025-03-01", ["arquitecto"], 1),
        _proc("boe:A", "Resolución de 21 de diciembre de 2022, de la Subsecretaría, por la que se convoca proceso "
                       "selectivo para ingreso en el Cuerpo de Ingenieros de Minas del Estado", "2022-12-28",
              ["ingenieros-minas-estado"]),
    ]
    origenes = {"bop:1": {"convocante": "huesca"}, "bop:2": {"convocante": "huesca"}, "boe:A": {}}
    actos = [
        {"id": "x1", "fecha": "2025-06-10", "tipo_acto": "admitidos", "convocante": "huesca",
         "titulo": "Relación definitiva de admitidos y excluidos para la provisión de 4 plazas de Auxiliar Administrativo"},
        {"id": "x2", "fecha": "2023-03-10", "tipo_acto": "tribunal", "convocante": None,
         "titulo": "Resolución de 5 de marzo de 2023, de la Subsecretaría, por la que se modifica la composición del "
                   "Tribunal, convocado por Resolución de 21 de diciembre de 2022."},
        {"id": "x3", "fecha": "2025-06-10", "tipo_acto": "admitidos", "convocante": "teruel",
         "titulo": "Lista de admitidos de una plaza de Arquitecto"},
    ]
    clave = lambda a: [a["convocante"]] if a.get("convocante") else []  # noqa: E731
    recuento, huerfanos = u.unir(procesos, origenes, actos, clave)
    assert recuento["convocante_puesto"] == 1 and recuento["cita_convocatoria"] == 1
    assert [a["id"] for a in procesos[0]["actos"]] == ["1", "x1"]
    assert [a["id"] for a in procesos[2]["actos"]] == ["A", "x2"]
    assert [h["id"] for h in huerfanos] == ["x3"]  # otro convocante: no se une, va a la cola
    u.fase_y_estado(procesos[0], date(2026, 10, 30))
    assert (procesos[0]["fase"], procesos[0]["estado"]) == ("admitidos_definitivo", "admitidos_definitivo")


def test_procesos_por_anio(tmp_path):
    """procesos y huérfanos van por años (un solo fichero pasaba de los 100 MB de GitHub) y se leen igual."""
    from motor import procesos as pr
    (tmp_path / "procesos.jsonl").write_text('{"id": "viejo"}\n', encoding="utf-8")
    filas = [{"id": "a", "apertura_plazo": "2023-05-01"}, {"id": "b", "actos": [{"fecha": "2025-01-02"}]},
             {"id": "c", "fecha": "2023-12-31"}]
    indice = pr.escribir_por_anio(tmp_path, "procesos", filas)
    assert set(indice) == {"2023", "2025"} and indice["2023"]["lineas"] == 2
    assert not (tmp_path / "procesos.jsonl").exists()
    assert [x["id"] for x in pr.leer_por_anio(tmp_path, "procesos")] == ["a", "c", "b"]


def test_puesto_del_texto_cuando_el_titulo_no_lo_dice():
    texto = ("AYUNTAMIENTO DE RIVAS-VACIAMADRID\nPersonal\nPor Decreto de Alcaldía 123/2024 se ha resuelto nombrar "
             "funcionario de carrera, en la plaza de Agente de Policía Local, a quien ha superado el proceso.")
    assert u.puesto_en_texto(texto) == "policia-local"
    assert u.puesto_en_texto(None) is None
    procesos = [_proc("bocm:1", "Bases de 2 plazas de Agente de Policía Local", "2024-01-10", ["policia-local"], 2),
                _proc("bocm:2", "Bases de una plaza de Arquitecto", "2024-01-10", ["arquitecto"], 1)]
    origenes = {"bocm:1": {"convocante": "rivas"}, "bocm:2": {"convocante": "rivas"}}
    actos = [{"id": "n1", "fecha": "2024-09-10", "tipo_acto": "nombramiento", "convocante": "rivas",
              "titulo": "Rivas-Vaciamadrid. Personal. Nombramiento funcionario carrera", "puesto_texto": "policia-local"}]
    recuento, huerfanos = u.unir(procesos, origenes, actos, lambda a: [a["convocante"]])
    assert [a["id"] for a in procesos[0]["actos"]][-1] == "n1" and not huerfanos
