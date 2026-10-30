"""Reglas de privacidad: ningún nombre de persona ni documento de identidad en textos, títulos u originales."""
import json

from motor.archivo import Archivo
from motor.limpieza import limpiar_html, limpiar_texto, tiene_nombre_de_persona, titulo_sin_nombres
from motor.mantenimiento import privacidad


def test_nombres_con_tratamiento_y_falsos_positivos():
    for t in ("Vocal 2.º: Doña Nombre Apellido Segundo, Catedrática de la Universidad de Vigo.",
              "Presidente: D. Nombre Apellido.", "Nomenament de la Sra. Nombre Apellido com a tècnica.",
              "DON NOMBRE APELLIDO SEGUNDO"):
        assert tiene_nombre_de_persona(t), t
    for t in ("Ayuntamiento de Don Benito (Badajoz)", "Ayuntamiento de Doña Mencía", "D. OTRAS DISPOSICIONES",
              "las solicitudes se dirigirán al Sr. Subsecretario de Igualdad", "la Sra. Alcaldesa", "apartado D. del anexo"):
        assert not tiene_nombre_de_persona(t), t


def test_titulos_y_textos():
    assert titulo_sin_nombres("Resolución por la que se nombra Catedrático de Universidad a don Nombre Apellido.") == \
        "Resolución por la que se nombra Catedrático de Universidad a [persona]."
    r = limpiar_html("<p>Plazo de veinte días hábiles.</p><p>Secretaria: Doña Nombre Apellido, Escala Técnica.</p>")
    assert r["texto"] == "Plazo de veinte días hábiles." and r["parrafos_omitidos_por_datos_personales"] == 1
    r = limpiar_texto("ANUNCI\nEl termini de presentació de sol·licituds\nserà de 20 dies hàbils.\n"
                      "2026-E-RE-5948 ***000**N EXEMPTA\nPàg. 2-5\n", ignorar=__import__("re").compile(r"^Pàg\."))
    assert r["texto"] == "ANUNCI El termini de presentació de sol·licituds serà de 20 dies hàbils."
    assert r["lineas_omitidas_por_datos_personales"] == 1


def test_originales_solo_huella(tmp_path):
    a = Archivo(tmp_path, indice_por_fuente=True, solo_huella=True)
    r = a.guardar("boe-texto", __import__("datetime").date(2026, 10, 29), b"<xml/>", "https://x", "xml", 200)
    assert r["solo_huella"] and r["ruta"] is None and not list((tmp_path / "boe-texto").glob("**/*"))


def test_mantenimiento_limpia_lo_guardado(tmp_path):
    t = tmp_path / "datos/boe/textos/2026/10/BOE-A-1.json"
    t.parent.mkdir(parents=True)
    t.write_text(json.dumps({"titulo": "Se nombra a doña Nombre Apellido", "texto": "Uno.\nVocal: Don Nombre Apellido.",
                             "tablas": [{"filas": 2, "contenido": [["Cargo", "Persona"], ["Presidente", "D. Nombre Apellido"]],
                                         "datos_personales": False}]}))
    s = tmp_path / "datos/autonomicos/dogv/oposiciones/2026/10.jsonl"
    s.parent.mkdir(parents=True)
    s.write_text(json.dumps({"titulo": "Nomenament de la Sra. Nombre Apellido"}) + "\n")
    o = tmp_path / "archivo/boe-texto/2026/10/29/abc.xml.gz"
    o.parent.mkdir(parents=True)
    o.write_bytes(b"x")
    (tmp_path / "archivo/indices/boe-texto").mkdir(parents=True)
    (tmp_path / "archivo/indices/boe-texto/2026-10.jsonl").write_text("{}\n")
    assert privacidad.main(["--salida", str(tmp_path)]) == 0
    d = json.loads(t.read_text())
    assert d["titulo"] == "Se nombra a [persona]" and d["texto"] == "Uno." and d["tablas"][0]["datos_personales"]
    assert "[persona]" in s.read_text() and not o.exists()
    assert (tmp_path / "archivo/indices/boe-texto/2026-10.jsonl").exists()
    assert json.loads((tmp_path / "archivo/retirados.json").read_text())[0]["por_fuente"] == {"boe-texto": 1}


def test_anonimizar_respuestas_de_sondas(tmp_path):
    from motor.mantenimiento.anonimizar import main
    f = tmp_path / "1.cuerpo"
    f.write_bytes("<p>Vocal: Doña María López García, DNI ***4567**.</p><p>Ayuntamiento de Don Benito</p>".encode("cp1252"))
    main([str(tmp_path)])
    t = f.read_bytes().decode("cp1252")
    assert "Doña Nombre Apellido Segundo" in t and "***0000**" in t and "Don Benito" in t and "López" not in t


def test_anonimizar_nombres_junto_a_documento_y_d_mayusculas():
    """Casos que se escaparon el 30/10/2026: listas sin coma o en minúsculas fuera de tablas y «D. NOMBRE» en mayúsculas."""
    from motor.limpieza import tiene_nombre_de_persona
    from motor.mantenimiento.anonimizar import anonimizar_texto
    t, _ = anonimizar_texto("1 PEREZ HERRERO MIRIAM ***1234**\nAlcaide Díaz, Rosa Mª ***5678**\n"
                            "<p>2 Garcia Lopez Maria ***1234**</p><p>Ayuntamiento de Lugo</p>")
    assert "PEREZ" not in t and "Alcaide" not in t and "Garcia" not in t and "Ayuntamiento de Lugo" in t
    assert tiene_nombre_de_persona("• D. MANUEL SIMÓN VILLAGRASA")
    assert not tiene_nombre_de_persona("D. OTRAS DISPOSICIONES")
