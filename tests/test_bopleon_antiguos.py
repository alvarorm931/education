"""BOP de León, boletines anteriores al 17/02/2025: lista por fechas y sumario del PDF entero (formato del 30/10/2026)."""

from motor.provinciales import bopleon as le

LISTA = ('<ul class="listado"><li class="elementoListado"><div class="contenido_elemento">'
         '<a href="/export/sites/bop/publica/boletines-anteriores/.galleries/Boletines-Anteriores/2384737_20220105.pdf" '
         'title="BOP 3/2022" class="enlace_elemento" target="_blank">Ir al detalle</a>'
         '<h3 class="titulo_elemento">BOP 3/2022</h3><div class="container">Boletín núm. 3 de 05/01/2022</div></div></li>'
         '<li><a href="/export/sites/bop/publica/boletines-anteriores/.galleries/Boletines-Anteriores/2384724_20220104.pdf" '
         'title="BOP 2/2022" class="enlace_elemento">Ir al detalle</a><div>Boletín núm. 2 de 04/01/2022</div></li></ul>'
         ).encode()

SUMARIO_1 = """S U M A R I O
Edita:      Imprenta Provincial. complejo San ca yetano.
Teléfono:       987 225 263.
Página web:  www.dipuleon.es/bop
E-mail:           boletin@dipuleon.es
Miércoles, 5 de enero de 2022 . Número 3
JUNTAS ELECTORALES
Junta Electoral de Zona de Astorga
Relación de locales públicos para actos de la campaña electoral ............................................................ 3
ADMINISTRACIÓN LOCAL
Ayuntamientos
Alija del Infantado
Bases de la convocatoria para la provisión de una plaza de Auxiliar Administrativo ...................... 4
Castilfalé
Lista provisional de admitidos y excluidos del proceso selectivo de una plaza de Operario de Servicios
Múltiples, por concurso-oposición ...................................................................................... 5
Riaño
Notificación a interesados en recurso contencioso administrativo interpuesto contra esta Administración 6
"""
SUMARIO_2 = """Mancomunidades de Municipios
Mancomunidad Municipal para el Saneamiento Integral de León y su Alfoz – Saleal
Aprobación inicial del Presupuesto para el ejercicio 2022 ........................................................................ 6
"""
CUERPO = ["Junta Electoral de Zona de Astorga\nrelación de locales públicos para actos de la campaña electoral\nSalón de actos.",
           "Alija del Infantado\nBases de la convocatoria para la provisión de una plaza de Auxiliar Administrativo\n"
           "Primera.- Objeto. Plazo de presentación: veinte días naturales.",
           "Castilfalé\nLista provisional de admitidos y excluidos del proceso selectivo de una plaza de Operario de "
           "Servicios Múltiples, por concurso-oposición\n1 GARCIA LOPEZ, MARIA ***1234**\nBases en el Boletín Oficial "
           "de la Provincia de León n.º 200, de 20 de octubre de 2021.",
           "Riaño\nNotificación a interesados en recurso contencioso administrativo\nSaleal\nAprobación inicial."]


def test_lista_de_boletines_anteriores():
    assert le.lista_antiguos(LISTA) == [
        {"numero": 2, "fecha": "2022-01-04", "url_pdf": "https://bop.dipuleon.es/export/sites/bop/publica/"
                                                        "boletines-anteriores/.galleries/Boletines-Anteriores/2384724_20220104.pdf"},
        {"numero": 3, "fecha": "2022-01-05", "url_pdf": "https://bop.dipuleon.es/export/sites/bop/publica/"
                                                        "boletines-anteriores/.galleries/Boletines-Anteriores/2384737_20220105.pdf"}]


def test_sumario_del_pdf_entero():
    e = le.sumario_antiguo([SUMARIO_1, SUMARIO_2] + CUERPO)
    assert [(x["seccion"], x["grupo"], x["entidad"], x["pagina"]) for x in e] == [
        ("Juntas Electorales", None, "Junta Electoral de Zona de Astorga", 3),
        ("Administración Local", "Ayuntamientos", "Alija del Infantado", 4),
        ("Administración Local", "Ayuntamientos", "Castilfalé", 5),
        ("Administración Local", "Ayuntamientos", "Riaño", 6),
        ("Administración Local", "Mancomunidades de Municipios",
         "Mancomunidad Municipal para el Saneamiento Integral de León y su Alfoz – Saleal", 6)]
    assert e[2]["titulo"] == ("Lista provisional de admitidos y excluidos del proceso selectivo de una plaza de "
                              "Operario de Servicios Múltiples, por concurso-oposición")
    empleo = le.seleccionar([{**x, "id": str(i), "fecha": "2022-01-05"} for i, x in enumerate(e)])
    assert [x["entidad"] for x in empleo] == ["Alija del Infantado", "Castilfalé"]
    assert empleo[0]["convocante"]["nombre"] == "Alija del Infantado"


def test_procesar_antiguo_textos_sin_nombres(tmp_path, monkeypatch):
    import json

    from motor.archivo import Archivo
    from motor.http import Respuesta
    monkeypatch.setattr(le, "obtener", lambda url, accept=None: Respuesta(url, 200, b"%PDF-1.4", {}))
    monkeypatch.setattr("motor.provinciales.textos.paginas_pdf", lambda c: [SUMARIO_1, SUMARIO_2] + CUERPO)
    b = le.lista_antiguos(LISTA)[1]
    inf = le.procesar_antiguo(b, tmp_path, Archivo(tmp_path / "archivo"))
    assert (inf["resultado"], inf["disposiciones"], inf["empleo_publico"], inf["textos"]) == ("ok", 5, 2, 2)
    base = tmp_path / "datos" / "provinciales" / "bopleon" / "textos" / "2022" / "01"
    bases = json.loads((base / "BOPLEON-2022-3-002.json").read_text(encoding="utf-8"))
    assert "veinte días naturales" in bases["texto"]
    lista = json.loads((base / "BOPLEON-2022-3-003.json").read_text(encoding="utf-8"))
    assert lista["texto"] is None and "GARCIA" not in json.dumps(lista, ensure_ascii=False)
    assert lista["citas"][0]["fecha"] == "2021-10-20"


def test_reprocesar_desde_el_almacen(tmp_path, monkeypatch):
    """Los días leídos con una versión vieja se releen del original del almacén, sin pedirlos a la fuente."""
    import json

    from motor.autonomicos.comun import escribir_json, escribir_jsonl
    dia = tmp_path / "datos" / "provinciales" / "bopleon" / "dias" / "2022" / "01" / "05.json"
    escribir_json(dia, {"fecha": "2022-01-05", "numero": 3, "origen": "boletines_anteriores", "resultado": "ok",
                        "sha256": "abc"})
    escribir_jsonl(tmp_path / "archivo" / "indices" / "bopleon" / "2022-01.jsonl",
                   [{"sha256": "abc", "clave": "bopleon/2022/01/05/abc.pdf.gz", "url": "https://bop.dipuleon.es/x.pdf",
                     "capturado": "2026-10-30T14:00:00+00:00"}])
    leidas = []

    class Almacen:
        def leer(self, clave):
            leidas.append(clave)
            return b"%PDF-1.4"

    monkeypatch.setattr("motor.almacen.Almacen", Almacen)
    monkeypatch.setattr("motor.provinciales.textos.paginas_pdf", lambda c: [SUMARIO_1, SUMARIO_2] + CUERPO)
    monkeypatch.setattr(le, "obtener", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no se pide a la fuente")))
    le.main(["--reprocesar-antiguos", "--salida", str(tmp_path)])
    inf = json.loads(dia.read_text(encoding="utf-8"))
    assert leidas == ["bopleon/2022/01/05/abc.pdf.gz"] and inf["version"] == le.VERSION_ANTIGUOS
    assert inf["empleo_publico"] == 2 and inf["capturado"] == "2026-10-30T14:00:00+00:00"
    le.main(["--reprocesar-antiguos", "--salida", str(tmp_path)])  # ya al día: no se vuelve a leer
    assert len(leidas) == 1
