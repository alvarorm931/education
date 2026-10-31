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


def test_dia_leido_a_medias_se_vuelve_a_leer(tmp_path):
    import json
    from motor.autonomicos.comun import estado_dia
    r = tmp_path / "d.json"
    r.write_text(json.dumps({"resultado": "ok", "alertas": ["BOP-SEVILLA 2023-03-22: 36 anuncios leídos de 72"]}))
    assert estado_dia(r) == (False, True)
    r.write_text(json.dumps({"resultado": "ok", "alertas": []}))
    assert estado_dia(r) == (True, False)
    r.write_text(json.dumps({"resultado": "error_http"}))
    assert estado_dia(r) == (False, True)


def test_bocm_textos_para_tras_fallos_seguidos(tmp_path, monkeypatch, capsys):
    import json
    from motor.archivo import Archivo
    from motor.autonomicos import bocm
    from motor.http import Respuesta
    op = tmp_path / "datos" / "autonomicos" / "bocm" / "oposiciones" / "2026" / "10" / "30.jsonl"
    op.parent.mkdir(parents=True)
    op.write_text("".join(json.dumps({"id": f"BOCM-20261030-{k}", "fecha": "2026-10-30", "alcance": "acceso",
                                      "url_xml": f"https://www.bocm.es/x/{k}.xml"}) + "\n" for k in range(60)))
    pedidas, pausas = [], []
    monkeypatch.setattr(bocm, "obtener", lambda url, **kw: pedidas.append(url) or
                        Respuesta(url, 200, b"<html>Request Rejected</html", {"content-type": "text/html"}))
    monkeypatch.setattr(bocm.time, "sleep", lambda s: pausas.append(s))
    hechos, errores = bocm.descargar_textos(tmp_path, Archivo(tmp_path / "a", solo_huella=True), 0, 0.7)
    # Se para a los 25 fallos seguidos, con pausa también tras cada fallo, y dice por qué
    assert (hechos, errores) == (0, bocm.MAX_FALLOS_SEGUIDOS) and len(pedidas) == len(pausas) == bocm.MAX_FALLOS_SEGUIDOS
    assert "no es XML" in capsys.readouterr().out


def test_textos_para_si_el_servidor_da_otra_cosa(tmp_path, monkeypatch):
    """Muchos documentos seguidos que no se pueden leer: el servidor ha dejado de darlos; no se insiste."""
    from motor.archivo import Archivo
    from motor.autonomicos import comun
    from motor.http import Respuesta
    pedidas = []
    monkeypatch.setattr(comun, "obtener", lambda url, **kw: pedidas.append(url) or Respuesta(url, 200, b"<html>bloqueo", {}))
    monkeypatch.setattr(comun.time, "sleep", lambda s: None)

    def extraer(c):
        raise ValueError("sin div.story")

    pend = [{"id": f"X{k}", "fecha": "2026-10-30"} for k in range(100)]
    hechos, errores = comun.descargar_textos(pend, lambda x: tmp_path / f"{x['id']}.json", lambda x: "https://x/" + x["id"],
                                             extraer, Archivo(tmp_path / "a", solo_huella=True), "dog", 0, 0)
    assert hechos == 0 and len(pedidas) == comun.MAX_FALLOS_SEGUIDOS_TEXTOS


def test_escribir_con_sustitutos_sueltos(tmp_path):
    import json
    from motor.autonomicos.comun import escribir_json
    r = tmp_path / "t.json"
    escribir_json(r, {"texto": "Bases\udbc0 de la plaza"})
    assert json.loads(r.read_text(encoding="utf-8"))["texto"].startswith("Bases")
