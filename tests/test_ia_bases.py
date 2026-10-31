"""Extracción de los datos de las bases con Claude: elección del texto, lote y comprobación de las citas (sin API)."""
import json

from motor.ia import bases as b

BASES = ("BASES PARA LA SELECCIÓN DE DOS PLAZAS DE AUXILIAR ADMINISTRATIVO DEL AYUNTAMIENTO DE CHILOECHES. "
         "Primera. Objeto. Es objeto de las presentes bases la provisión en propiedad de dos plazas de Auxiliar "
         "Administrativo, grupo C2, mediante concurso-oposición por turno libre. "
         "Segunda. Requisitos. Estar en posesión del título de Graduado en Educación Secundaria Obligatoria o "
         "equivalente. Tercera. Tasa. Los derechos de examen se fijan en 15,00 euros. "
         "Anexo. El temario consta de veinte temas. " + "Texto de relleno de las bases. " * 40)


def _datos(tmp_path):
    raiz = tmp_path
    t = raiz / "datos" / "provinciales" / "bopguadalajara" / "textos" / "2025" / "09" / "BOPGUADALAJARA-2025-2844.json"
    t.parent.mkdir(parents=True)
    t.write_text(json.dumps({"texto": BASES}))
    p = {"id": "boe:BOE-A-2026-19166", "estado": "plazo_abierto", "ambito": "local", "apertura_plazo": "2026-09-14",
         "otras_publicaciones": [
             {"id": "bopguadalajara:BOPGUADALAJARA-2025-3130", "fecha": "2025-10-23", "tipo": "convocatoria",
              "tiene_texto": True, "titulo": "CORRECCIÓN BASES PARA LA SELECCIÓN"},
             {"id": "bopguadalajara:BOPGUADALAJARA-2025-2844", "fecha": "2025-09-26", "tipo": "convocatoria",
              "tiene_texto": True, "fuente": "BOP-GUADALAJARA", "url": "https://boletin.dguadalajara.es/x.pdf",
              "titulo": "BASES PARA LA SELECCIÓN Y PROVISIÓN"}],
         "actos": [{"id": "BOE-A-2026-19166", "fecha": "2026-09-14"}]}
    f = raiz / "datos" / "oposiciones" / "procesos" / "2026.jsonl"
    f.parent.mkdir(parents=True)
    f.write_text(json.dumps(p) + "\n" + json.dumps({**p, "id": "boe:X", "estado": "plazo_cerrado"}) + "\n")
    return raiz, p


def test_eleccion_y_lote(tmp_path):
    raiz, p = _datos(tmp_path)
    elegidos = b.elegir(raiz, 10, {"plazo_abierto"})
    assert [(x["id"], d["id"]) for x, d in elegidos] == [("boe:BOE-A-2026-19166", "bopguadalajara:BOPGUADALAJARA-2025-2844")]
    lote, indice = b.preparar(raiz, 10, {"plazo_abierto"}, tmp_path / "trabajo")
    req = json.loads(lote.read_text().splitlines()[0])
    assert req["params"]["model"] == b.MODELO and req["params"]["thinking"] == {"type": "disabled"}
    assert "Primera. Objeto" in req["params"]["messages"][0]["content"]
    info = json.loads(indice.read_text())["p00000"]
    assert info["ruta"] == "datos/oposiciones/extraccion/2026/boe_BOE-A-2026-19166.json"
    assert b._texto_documento(raiz, info) == BASES
    # Ya extraído con el mismo texto: no se vuelve a pedir
    r = raiz / info["ruta"]
    r.parent.mkdir(parents=True)
    r.write_text(json.dumps({"documento": info["documento"]}))
    assert b.elegir(raiz, 10, {"plazo_abierto"}) == []


def test_verificar_citas():
    resp = {"grupo": {"v": "C2", "c": "dos plazas de Auxiliar Administrativo, grupo C2"},
            "plazas_total": {"v": 2, "c": "la provisión en propiedad de dos plazas de Auxiliar"},
            "tasa_euros": {"v": 15, "c": "Los derechos de examen se fijan en 15,00 euros"},
            "temas": {"v": 20, "c": "El temario consta de veinte temas"},
            "titulacion": {"v": "Graduado en ESO", "c": "título de Graduado en Bachillerato"},  # no está en el texto
            "plazas_turno_libre": {"v": 3, "c": "la provisión en propiedad de dos plazas de Auxiliar"}}  # 3 no sale
    acept, rech = b.verificar(resp, BASES)
    assert set(acept) == {"grupo", "plazas_total", "tasa_euros", "temas"} and acept["tasa_euros"]["valor"] == 15
    assert {k: v["motivo"] for k, v in rech.items()} == {"titulacion": "cita_no_literal",
                                                        "plazas_turno_libre": "valor_no_en_cita"}
    assert b.numeros_en_letra("CIENTO VEINTITRÉS plazas y noventa temas; treinta y dos; dues places") >= {123, 90, 32, 2}
    assert b._respuesta_json('```json\n{"grupo": {"v": "C2", "c": "x"}}\n```') == {"grupo": {"v": "C2", "c": "x"}}


def test_recorte_guarda_el_final():
    t = "A" * 60_000 + "TEMARIO" + "B" * 40_000
    r = b.recortar(t)
    assert len(r) < b.MAX_CARACTERES + 10 and r.startswith("A") and r.endswith("B")


def test_temas_contados_sin_ia():
    texto = "ANEXO I. TEMARIO\n" + "\n".join(f"Tema {k}. Materia número {k} del temario." for k in range(1, 21)) + \
        "\nANEXO II\nTema 3. Referencia suelta"
    t = b.temas_contados(texto)
    assert t["valor"] == 20 and t["cita"].startswith("Tema 20.") and t["nivel"] == "contado"
    assert b.temas_contados("Tema 1. Única materia") is None
    acept, _ = b.verificar({}, texto)
    assert acept["temas"]["valor"] == 20
