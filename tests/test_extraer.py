import json
from datetime import date
from pathlib import Path

import pytest

from motor.boe.extraer import construir_acto, extraer_local, numero
from motor.boe.texto import texto_plano
from motor.calendario import domingo_de_pascua, fin_de_plazo

REALES = {t["identificador"]: t for t in json.loads(
    (Path(__file__).parent / "fixtures" / "textos_locales_reales.json").read_text(encoding="utf-8"))}


def test_pascua():
    assert domingo_de_pascua(2026) == date(2026, 4, 5)
    assert domingo_de_pascua(2027) == date(2027, 3, 28)


@pytest.mark.parametrize("pub,dias,tipo,fin", [
    (date(2026, 10, 2), 10, "habiles", date(2026, 10, 19)),   # salta el 12 de octubre
    (date(2026, 10, 1), 20, "habiles", date(2026, 10, 30)),
    (date(2026, 10, 5), 20, "naturales", date(2026, 10, 26)),  # acaba en domingo: pasa al lunes
    (date(2026, 10, 21), 20, "habiles", date(2026, 11, 18)),
])
def test_fin_de_plazo(pub, dias, tipo, fin):
    assert fin_de_plazo(pub, dias, tipo) == fin


@pytest.mark.parametrize("txt,n", [("Tres", 3), ("veintitrés", 23), ("treinta y una", 31), ("12", 12), ("varias", None)])
def test_numero(txt, n):
    assert numero(txt) == n


def _acto(ident):
    t = REALES[ident]
    anuncio = {"identificador": ident, "fecha": t["fecha"], "titulo": t["titulo"], "ambito": "local",
               "tipo_acto": "convocatoria", "alcance": "acceso"}
    return construir_acto(anuncio, {"texto": t["texto"], "tablas": [], "referencias": []})


def test_mijas_dos_turnos_y_extracto_autonomico():
    a = _acto("BOE-A-2026-20494")
    assert a["extraccion"] == "plantilla_local_v1" and a["pendiente"] == []
    assert a["tipo_acto"] == "apertura_plazo"
    assert [(p["numero"], p["denominacion"], p["turno"], p["sistema"]) for p in a["plazas"]] == [
        (2, "Auxiliar Administrativo/a", "libre", "oposicion"),
        (1, "Auxiliar Administrativo/a", "discapacidad", "oposicion")]
    assert a["plazas"][0]["subescala"] == "Auxiliar"
    assert a["total_plazas"] == 3
    bases = [b for b in a["boletines_citados"] if b["papel"] == "bases"][0]
    assert (bases["boletin"], bases["numero"], bases["fecha"]) == ("Boletín Oficial de la Provincia de Málaga", "40", "2026-02-27")
    extracto = [b for b in a["boletines_citados"] if b["papel"] == "extracto"][0]
    assert extracto["boletin"] == "Boletín Oficial de la Junta de Andalucía" and extracto["numero"] == "172"
    assert a["plazo"]["dias"] == 10 and a["plazo"]["tipo"] == "habiles" and a["plazo"]["fin_estimado"] == "2026-10-19"


def test_santa_cruz_clase_media():
    a = _acto("BOE-A-2026-20436")
    p = a["plazas"][0]
    assert (p["numero"], p["denominacion"], p["escala"], p["subescala"], p["clase"]) == (
        3, "Trabajador/a Social", "Administración Especial", "Técnica", "Media")
    assert p["sistema"] == "concurso-oposicion" and p["turno"] == "libre"
    assert a["plazo"]["fin_estimado"] == "2026-10-30"


def test_pedraza_laboral_bases_en_autonomico_dias_naturales():
    a = _acto("BOE-A-2026-20631")
    p = a["plazas"][0]
    assert p["regimen"] == "laboral_fijo" and p["numero"] == 1
    assert a["boletines_citados"][0]["boletin"] == "Boletín Oficial de Castilla y León"
    assert a["plazo"]["tipo"] == "naturales" and a["plazo"]["fin_estimado"] == "2026-10-26"


def test_consorcio_alicante_mixto_es_acceso():
    a = _acto("BOE-A-2026-21264")
    assert a["total_plazas"] == 12
    assert {p["turno"] for p in a["plazas"]} == {"promocion_interna", "libre"}
    assert a["alcance"] == "acceso"


def test_olula_todo_promocion_interna_sale_del_alcance():
    a = _acto("BOE-A-2026-21902")
    assert a["alcance"] == "promocion_interna"
    assert a["plazo"]["fin_estimado"] == "2026-11-18"


def test_sin_texto_queda_pendiente():
    a = construir_acto({"identificador": "BOE-A-2026-1", "fecha": "2026-10-01", "ambito": "estatal"}, None)
    assert a["pendiente"] == ["texto"]


def test_texto_sin_datos_personales():
    xml = """<documento><metadatos><titulo>Lista</titulo><fecha_publicacion>20261001</fecha_publicacion></metadatos>
    <analisis><referencias><anteriores><anterior referencia="BOE-A-2026-100"><palabra>CORRECCIÓN</palabra>
    <texto>de errores de la Resolución</texto></anterior></anteriores></referencias></analisis>
    <texto><p>Se aprueba la lista provisional.</p><p>D. Fulano, con DNI ***1234**, queda nombrado.</p>
    <table><tr><td>Apellidos y nombre</td><td>DNI</td></tr><tr><td>Pérez, Ana</td><td>***5678**</td></tr>
    <tr><td>López, Juan</td><td>***9012**</td></tr></table>
    <table><tr><td>Especialidad</td><td>Plazas</td></tr><tr><td>Matemáticas</td><td>12</td></tr></table></texto></documento>"""
    d = texto_plano(xml.encode())
    assert "Fulano" not in d["texto"] and d["parrafos_omitidos_por_datos_personales"] == 1
    personal, plazas = d["tablas"]
    assert personal == {"filas": 2, "cabecera": ["Apellidos y nombre", "DNI"], "datos_personales": True}
    assert plazas["contenido"][1] == ["Matemáticas", "12"]
    assert d["referencias"][0]["referencia"] == "BOE-A-2026-100"
    assert "Pérez" not in json.dumps(d, ensure_ascii=False)
