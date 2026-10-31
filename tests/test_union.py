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
    assert u.puesto("Nombramiento de funcionaria de carrera (Técnica de Exacciones y Rentas).") == "tecnico-exaccion-renta"
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


def test_huerfano_de_convocatoria_anterior_al_archivo():
    actos = [{"id": "z1", "fecha": "2022-02-10", "tipo_acto": "admitidos", "convocante": "soria",
              "titulo": "Lista de admitidos de la plaza de Conserje, convocada por Resolución de 3 de noviembre de 2021"},
             {"id": "z2", "fecha": "2022-02-10", "tipo_acto": "admitidos", "convocante": "soria",
              "titulo": "Lista de admitidos de la plaza de Peón", "citas": [{"boletin": "BOE", "fecha": "2015-10-31"}]}]
    _, huerfanos = u.unir([], {}, actos, lambda a: [a["convocante"]])
    assert [h["motivo"] for h in huerfanos] == ["anterior_al_archivo", "sin_candidato"]


def test_mas_formas_de_nombrar_el_puesto():
    assert u.puesto("Nombramiento y toma de posesión como Administrativo del Ayuntamiento de Numancia") == "administrativo"
    assert u.puesto("LISTADO DEFINITIVO ADMITIDOS Y EXCLUIDOS TRABAJADOR/A SOCIAL CTA") == "trabajador-social"
    assert u.puesto("Nomenament d'administratives. Decret d'Alcaldia núm. 2026-1134.") == "administrativo"
    assert u.puesto("Nombramiento de funcionario de carrera, Técnico Medio Ambiente, A2 (Estabilización).") == \
        "tecnico-medio-ambiente"
    assert u.puesto("relació de persones admeses i excloses per a la convocatòria d'una plaça de peó/na") == "peon"
    assert u.puesto("LISTADO DEFINITIVO DE ADMITIDOS/AS Y EXCLUIDOS/AS") is None
    assert u.puesto("Nombramiento de funcionarios de carrera.") is None


def test_puesto_parecido_no_une_y_deja_la_candidata():
    procesos = [_proc("bop:7", "Bases de una plaza de Operario de Servicios Múltiples de Deportes", "2025-03-01",
                      ["operario-servicio-multiple-deporte"], 1)]
    actos = [{"id": "y1", "fecha": "2025-06-10", "tipo_acto": "admitidos", "convocante": "teruel",
              "titulo": "Lista de admitidos de la plaza de Operario de Servicios Múltiples"}]
    recuento, huerfanos = u.unir(procesos, {"bop:7": {"convocante": "teruel"}}, actos, lambda a: [a["convocante"]])
    assert not recuento.get("convocante_puesto_parecido")
    assert huerfanos[0]["motivo"] == "puesto_parecido_sin_confirmar" and huerfanos[0]["candidatos"] == ["bop:7"]


def test_convocatoria_unica_pero_demasiado_antigua():
    procesos = [_proc("bop:8", "Bases de una plaza de Arquitecto", "2022-02-01", ["arquitecto"], 1)]
    actos = [{"id": "z9", "fecha": "2024-06-10", "tipo_acto": "admitidos", "convocante": "huesca",
              "titulo": "Lista de admitidos de una plaza de Arquitecto"},
             {"id": "z8", "fecha": "2024-06-10", "tipo_acto": "aprobados", "convocante": "huesca",
              "titulo": "Aprobados de una plaza de Arquitecto"}]
    recuento, huerfanos = u.unir(procesos, {"bop:8": {"convocante": "huesca"}}, actos, lambda a: [a["convocante"]])
    assert [h["motivo"] for h in huerfanos] == ["convocante_puesto_lejano"] and huerfanos[0]["candidatos"] == ["bop:8"]
    assert recuento["convocante_puesto"] == 1  # el de aprobados sí: puede llegar años después


def test_puesto_del_texto_nunca_guarda_una_persona():
    """Revisión del 31/10/2026: «nombramiento de Juan…» o «funcionaria en prácticas a Doña Ana…» se guardaban como
    puesto. En el texto solo valen «plaza de X» y «como X», sin nombres."""
    assert u.puesto_en_texto("Visto el expediente, se resuelve el nombramiento de Juan Antonio López Martínez, "
                             "funcionario de carrera.") is None
    assert u.puesto_en_texto("Se ha nombrado funcionaria en prácticas a Doña Ana López Ruiz.") is None
    assert u.puesto_en_texto("PO 575/2025 Carmen María Morote Castellano administrativo") is None
    assert u.puesto_en_texto("nombrar a D. Pedro Pérez como Técnico de Gestión") == "tecnico-gestion"
    assert u.puesto("Nombramiento de Margarita Bujosa Pocoví") is None
    assert u.puesto("RESOLUCIÓN por la que se modifica el plazo máximo de 10 plazas") is None


def test_cuerpo_del_estado_con_otro_ministerio():
    conv = ("Resolución de 3 de junio de 2025, de la Subsecretaría, por la que se convoca proceso selectivo para "
            "ingreso, por el sistema general de acceso libre, en el Cuerpo Superior de Meteorólogos del Estado.")
    p = {**_proc("boe:M", conv, "2025-06-10"), "ambito": "estatal"}
    q = u.puesto(conv)
    assert q
    p["plazas"] = [{"puesto_clave": q}]
    nombra = ("Resolución de 16 de enero de 2026, de la Secretaría de Estado de Función Pública, por la que se nombra "
              "personal funcionario de carrera, por el sistema general de acceso libre, del Cuerpo Superior de "
              "Meteorólogos del Estado.")
    actos = [{"id": "n1", "fecha": "2026-01-20", "tipo_acto": "nombramiento", "ambito": "estatal", "fuente": "BOE",
              "convocante": "funcion publica", "titulo": nombra}]
    origenes = {"boe:M": {"convocante": "transicion ecologica"}}
    clave = lambda a: [a["convocante"]] if a.get("convocante") else []  # noqa: E731
    recuento, huerfanos = u.unir([p], origenes, actos, clave)
    assert recuento["cuerpo_estatal"] == 1 and not huerfanos
    # con dos convocatorias del mismo cuerpo en la ventana, no se elige
    p2 = {**p, "id": "boe:M2", "apertura_plazo": "2025-11-10",
          "actos": [{"id": "M2", "fecha": "2025-11-10", "tipo": "convocatoria"}]}
    recuento, huerfanos = u.unir([{**p, "actos": list(p["actos"][:1])}, p2], {"boe:M": {}, "boe:M2": {}},
                                 [dict(actos[0])], clave)
    assert not recuento.get("cuerpo_estatal") and len(huerfanos) == 1
