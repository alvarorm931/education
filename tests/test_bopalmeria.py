"""BOP de Almería: filas de la lista de la aplicación ZK (formato de la sonda del 31/10/2026; anuncios inventados)."""
import json
from datetime import date

from motor.archivo import Archivo
from motor.provinciales import bopalmeria as al

FILAS = [
    ["2026/211", "30/10/2026", "", "",
     "ADMINISTRACIÓN LOCAL\nAYUNTAMIENTO DE ALMERÍA\nAREA DE ECONOMÍA, CONTRATACIÓN Y FUNCIÓN PÚBLICA\n"
     "CONVOCATORIA ESPECÍFICA Y BASES DEL PROCESO SELECTIVO PARA LA PROVISIÓN DE UNA PLAZA DE INSPECTOR/A DE BOMBEROS, "
     "COMO PERSONAL FUNCIONARIO DE CARRERA, POR TURNO LIBRE", "2966-2026", ""],
    ["2026/211", "30/10/2026", "", "", "ADMINISTRACIÓN LOCAL\nAYUNTAMIENTO DE FIÑANA\n"
     "APROBACIÓN INICIAL DEL PRESUPUESTO GENERAL PARA EL EJERCICIO 2026", "2985-2026", ""],
    ["2026/211", "30/10/2026", "", "", "ADMINISTRACIÓN LOCAL\nAYUNTAMIENTO DE TIJOLA\n"
     "RELACIÓN DEFINITIVA DE ASPIRANTES ADMITIDOS Y EXCLUIDOS PARA UNA PLAZA DE AUXILIAR ADMINISTRATIVO", "2990-2026", ""],
    ["2026/211", "30/10/2026", "", "", "ANUNCIOS EN GENERAL Y COMUNICACIONES OFICIALES\nCOMUNIDAD DE REGANTES EJEMPLO\n"
     "CONVOCATORIA DE JUNTA GENERAL ORDINARIA", "2991-2026", ""],
    ["2026/211", "30/10/2026", "", "", "ANUNCIOS EN GENERAL Y COMUNICACIONES OFICIALES\nEMPRESA PÚBLICA DE AGUAS EJEMPLO\n"
     "CONVOCATORIA Y BASES PARA LA SELECCIÓN DE TRABAJADOR/A OPERARIO/A DE REDES PARA CUBRIR UN PUESTO", "2992-2026", ""],
]


def test_cabecera_y_filas():
    c = al.leer_cabecera(FILAS[0][4])
    assert c["seccion"] == "ADMINISTRACIÓN LOCAL" and c["organismo"] == "AYUNTAMIENTO DE ALMERÍA"
    assert c["area"].startswith("AREA DE ECONOMÍA") and c["titulo"].startswith("CONVOCATORIA ESPECÍFICA")
    xs = al.leer_filas(FILAS)
    assert [x["numero_edicto"] for x in xs] == ["2966-2026", "2985-2026", "2990-2026", "2991-2026", "2992-2026"]
    assert xs[0]["url_pdf"] == "https://app.dipalme.org/bop/services/manager/edicto/2026/2966/anuncio.pdf"
    assert xs[0]["organismo"] == "Ayuntamiento de Almería" and xs[0]["boletin"] == "211"
    empleo = al.seleccionar(xs)
    assert [x["numero_edicto"] for x in empleo] == ["2966-2026", "2990-2026", "2992-2026"]  # no la junta de regantes
    assert empleo[0]["tipo_acto"] in ("convocatoria", "bases") and empleo[1]["tipo_acto"] == "admitidos"
    assert empleo[0]["convocante"]["nombre"] == "Almería"


class AppFalsa:
    def __init__(self, filas, paginas):
        self.filas, self.paginas = filas, paginas

    def buscar(self, d):
        return self.filas, self.paginas, b"<html>lista</html>"


def test_dia(tmp_path):
    archivo = Archivo(tmp_path / "archivo", indice_por_fuente=True, solo_huella=True)
    inf = al.procesar_dia(date(2026, 10, 30), tmp_path, archivo, AppFalsa(FILAS, "[ 1 - 5 / 5 ]"))
    assert (inf["resultado"], inf["disposiciones"], inf["empleo_publico"], inf["numero"]) == ("ok", 5, 3, "211")
    assert not inf["alertas"]
    base = tmp_path / "datos" / "provinciales" / "bopalmeria"
    filas = [json.loads(l) for l in (base / "oposiciones" / "2026" / "10" / "30.jsonl").read_text().splitlines()]
    assert filas[0]["id"] == "BOPALMERIA-2026-2966" and filas[0]["fecha"] == "2026-10-30"
    assert al.textos_pendientes(tmp_path)[0]["id"] == "BOPALMERIA-2026-2966"
    # sin filas: día sin boletín; con filas ilegibles, error de formato; leídas a medias, aviso
    assert al.procesar_dia(date(2026, 11, 1), tmp_path, archivo, AppFalsa([], "[ 0 - 0 / 0 ]"))["resultado"] == "sin_boletin"
    assert al.procesar_dia(date(2026, 11, 2), tmp_path, archivo,
                           AppFalsa([["x", "y"]], "[ 1 - 1 / 1 ]"))["resultado"] == "error_formato"
    inf = al.procesar_dia(date(2026, 10, 30), tmp_path, archivo, AppFalsa(FILAS, "[ 1 - 4 / 9 ]"))
    assert inf["alertas"] and "leídos de 9" in inf["alertas"][0]
