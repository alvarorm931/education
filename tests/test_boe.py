import json
from datetime import date
from pathlib import Path

import pytest

from motor.archivo import Archivo, leer
from motor.boe import __main__ as cli
from motor.boe.clasificar import ambito, clasificar
from motor.boe.sumario import ErrorSumario, parsear, url_sumario
from motor.http import Respuesta

FIXTURE = Path(__file__).parent / "fixtures" / "sumario_ejemplo.xml"


def test_url_sumario():
    assert url_sumario(date(2026, 10, 28)) == "https://boe.es/datosabiertos/api/boe/sumario/20261028"


def test_parsear_items_con_y_sin_epigrafe():
    s = parsear(FIXTURE.read_bytes())
    assert s.fecha_publicacion == "20261028"
    assert [d["numero"] for d in s.diarios] == ["260"]
    assert len(s.items) == 5
    local = [i for i in s.items if i["departamento"] == "ADMINISTRACIÓN LOCAL"]
    assert len(local) == 2 and all(i["epigrafe"] is None for i in local)
    estado = next(i for i in s.items if i["identificador"] == "BOE-A-2026-90002")
    assert estado["seccion_codigo"] == "2B"
    assert estado["epigrafe"].startswith("Cuerpos y Escalas")
    assert estado["pagina_inicial"] == "3"
    assert estado["url_pdf"].endswith("BOE-A-2026-90002.pdf")


def test_parsear_rechaza_estado_no_200():
    xml = b"<response><status><code>404</code><text>No encontrado</text></status></response>"
    with pytest.raises(ErrorSumario):
        parsear(xml)


def test_parsear_rechaza_formato_cambiado():
    xml = b"<response><status><code>200</code><text>ok</text></status><data><otro/></data></response>"
    with pytest.raises(ErrorSumario):
        parsear(xml)


@pytest.mark.parametrize("dep,esperado", [
    ("ADMINISTRACIÓN LOCAL", "local"),
    ("UNIVERSIDADES", "universidad"),
    ("COMUNIDAD AUTÓNOMA DE ANDALUCÍA", "autonomico"),
    ("COMUNIDAD DE MADRID", "autonomico"),
    ("MINISTERIO DEL INTERIOR", "estatal"),
    ("CONSEJO GENERAL DEL PODER JUDICIAL", "estatal"),
])
def test_ambito(dep, esperado):
    assert ambito(dep) == esperado


def test_clasificar_convocatoria_local():
    r = clasificar({
        "departamento": "ADMINISTRACIÓN LOCAL",
        "titulo": "Resolución de 14 de octubre de 2026, del Ayuntamiento de Villaejemplo (Ciudad Real), "
                  "referente a la convocatoria para proveer tres plazas de Auxiliar Administrativo.",
    })
    assert r["ambito"] == "local"
    assert r["tipo_acto"] == "convocatoria"
    assert r["convocante"] == {"tipo": "Ayuntamiento", "nombre": "Villaejemplo", "provincia": "Ciudad Real", "organismo": None}
    assert r["plazas"] == 3
    assert r["puesto"] == "Auxiliar Administrativo"
    assert r["pendiente_revision"] == []


def test_clasificar_varias_plazas_queda_pendiente():
    r = clasificar({
        "departamento": "ADMINISTRACIÓN LOCAL",
        "titulo": "Resolución de 15 de octubre de 2026, de la Diputación Provincial de Ejemplo (Toledo), "
                  "referente a la convocatoria para proveer varias plazas.",
    })
    assert r["convocante"]["tipo"] == "Diputación Provincial"
    assert r["convocante"]["provincia"] == "Toledo"
    assert r["plazas"] is None and r["plazas_texto"] == "varias"
    assert "plazas" in r["pendiente_revision"] and "puesto" in r["pendiente_revision"]


def test_clasificar_admitidos_universidad():
    r = clasificar({
        "departamento": "UNIVERSIDADES",
        "titulo": "Resolución de 16 de octubre de 2026, de la Universidad de Ejemplo, por la que se aprueba la "
                  "relación definitiva de aspirantes admitidos y excluidos al proceso selectivo de la Escala Administrativa.",
    })
    assert r["ambito"] == "universidad"
    assert r["tipo_acto"] == "admitidos"


def test_clasificar_correccion_prevalece():
    r = clasificar({"departamento": "ADMINISTRACIÓN LOCAL",
                    "titulo": "Corrección de errores de la Resolución de 1 de octubre de 2026, del Ayuntamiento de "
                              "Pueblo (Badajoz), referente a la convocatoria para proveer una plaza de Policía Local."})
    assert r["tipo_acto"] == "correccion"
    assert r["plazas"] == 1


def test_archivo_guarda_una_vez_y_registra(tmp_path):
    a = Archivo(tmp_path)
    r1 = a.guardar("boe-sumario", date(2026, 10, 28), b"abc", "u", "xml", 200)
    r2 = a.guardar("boe-sumario", date(2026, 10, 28), b"abc", "u", "xml", 200)
    assert r1["nuevo"] and not r2["nuevo"]
    assert r1["ruta"].endswith(".xml.gz")
    assert leer(tmp_path / r1["ruta"]) == b"abc"
    assert len((tmp_path / "indice.jsonl").read_text().splitlines()) == 2


def test_cli_extremo_a_extremo(tmp_path, monkeypatch):
    contenido = FIXTURE.read_bytes()

    def falso_obtener(url, accept=None, **kw):
        if url.endswith("20261025"):  # domingo: sin BOE
            return Respuesta(url, 404, b"<response><status><code>404</code></status></response>", {})
        return Respuesta(url, 200, contenido, {"content-type": "application/xml"})

    monkeypatch.setattr(cli, "obtener", falso_obtener)
    codigo = cli.main(["--desde", "2026-10-25", "--hasta", "2026-10-26", "--salida", str(tmp_path), "--pausa", "0"])
    assert codigo == 0
    opos = (tmp_path / "datos/boe/oposiciones/2026/10/26.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(opos) == 4
    fila = json.loads(opos[0])
    assert fila["fuente"] == "boe-sumario" and len(fila["captura_sha256"]) == 64
    estado = json.loads((tmp_path / "datos/boe/estado.json").read_text(encoding="utf-8"))
    assert estado["ultimo_diario"]["numero"] == 260
    assert estado["alertas_ultima_ejecucion"] == []  # el domingo sin BOE no es alerta


# Títulos reales del BOE de octubre de 2026 (sección II.B)
@pytest.mark.parametrize("titulo,esperado", [
    ("Resolución de 23 de septiembre de 2026, del Ayuntamiento de Ciudad Real, referente a la convocatoria para proveer varias plazas.",
     {"tipo": "Ayuntamiento", "nombre": "Ciudad Real", "provincia": None, "organismo": None}),
    ("Resolución de 1 de octubre de 2026, del Ayuntamiento de Vigo (Pontevedra), Organismo Autónomo Gerencia Municipal de Urbanismo, referente a la convocatoria para proveer varias plazas.",
     {"tipo": "Ayuntamiento", "nombre": "Vigo", "provincia": "Pontevedra", "organismo": "Organismo Autónomo Gerencia Municipal de Urbanismo"}),
    ("Resolución de 14 de octubre de 2026, de la Mancomunitat de Municipis de la Safor (Valencia/València), referente a la convocatoria para proveer una plaza.",
     {"tipo": "Mancomunitat", "nombre": "Municipis de la Safor", "provincia": "Valencia/València", "organismo": None}),
    ("Resolución de 24 de septiembre de 2026, de la Entidad Sociedad Pública Municipal Limpieza y Mantenimiento de Carmona (Limancar, SLU) (Sevilla), referente a la convocatoria para proveer una plaza.",
     {"tipo": "Entidad", "nombre": "Sociedad Pública Municipal Limpieza y Mantenimiento de Carmona (Limancar, SLU)", "provincia": "Sevilla", "organismo": None}),
    ("Resolución de 25 de septiembre de 2026, de la Diputación Provincial de Soria, referente a la convocatoria para proveer una plaza.",
     {"tipo": "Diputación Provincial", "nombre": "Soria", "provincia": None, "organismo": None}),
])
def test_convocante_titulos_reales(titulo, esperado):
    assert clasificar({"departamento": "ADMINISTRACIÓN LOCAL", "titulo": titulo})["convocante"] == esperado


@pytest.mark.parametrize("titulo,epigrafe,acto,alc", [
    ("Resolución de 21 de octubre de 2026, de la Subsecretaría, por la que se convoca la provisión de puestos de trabajo por el sistema de libre designación.",
     "Procedimientos de libre designación", "convocatoria", "provision_puestos"),
    ("Resolución de 22 de octubre de 2026, de la Subsecretaría, por la que se convoca concurso general para la provisión de puestos de trabajo.",
     "Personal funcionario. Concursos", "convocatoria", "provision_puestos"),
    ("Resolución de 2 de octubre de 2026, de la Universidad de Salamanca, por la que se declara concluido el procedimiento y desierta plaza de Profesor Titular de Universidad.",
     "Cuerpos docentes universitarios", "desierta", "docente_universitario"),
    ("Resolución de 6 de octubre de 2026, del Letrado Mayor de las Cortes Generales, por la que se publica la designación del Tribunal que ha de juzgar la oposición para el Cuerpo de Ujieres de las Cortes Generales.",
     "Cuerpo de Ujieres de las Cortes Generales", "tribunal", "acceso"),
    ("Resolución de 19 de octubre de 2026, de la Universidad Nacional de Educación a Distancia, por la que se publica la oferta de empleo público de personal técnico, de gestión y de administración y servicios.",
     "Personal técnico, de gestión y de administración y servicios", "oferta_empleo", "acceso"),
    ("Resolución de 20 de octubre de 2026, de la Subsecretaría, por la que se aprueba la relación provisional de personas admitidas y excluidas, y se anuncia fecha, hora y lugar de celebración del ejercicio único del proceso selectivo.",
     "Personal laboral", "admitidos", "acceso"),
])
def test_acto_y_alcance_titulos_reales(titulo, epigrafe, acto, alc):
    r = clasificar({"departamento": "MINISTERIO DE HACIENDA", "titulo": titulo, "epigrafe": epigrafe})
    assert (r["tipo_acto"], r["alcance"]) == (acto, alc)


def test_cli_saltar_existentes(tmp_path, monkeypatch):
    llamadas = []
    contenido = FIXTURE.read_bytes()

    def falso_obtener(url, accept=None, **kw):
        llamadas.append(url)
        return Respuesta(url, 200, contenido, {})

    monkeypatch.setattr(cli, "obtener", falso_obtener)
    args = ["--desde", "2026-10-26", "--hasta", "2026-10-27", "--salida", str(tmp_path), "--pausa", "0"]
    cli.main(args)
    cli.main(args + ["--saltar-existentes"])
    assert len(llamadas) == 2  # la segunda ejecución no repite los días ya hechos
    assert (tmp_path / "datos/boe/dias/2026/10/26.json").exists()


def test_pendientes_por_prioridad(tmp_path):
    from motor.boe.texto import pendientes
    filas = [
        {"identificador": "BOE-A-2026-1", "fecha": "2026-10-28", "alcance": "provision_puestos", "tipo_acto": "convocatoria"},
        {"identificador": "BOE-A-2024-2", "fecha": "2024-03-01", "alcance": "provision_puestos", "tipo_acto": "convocatoria"},
        {"identificador": "BOE-A-2023-3", "fecha": "2023-05-01", "alcance": "acceso", "tipo_acto": "convocatoria"},
        {"identificador": "BOE-A-2025-4", "fecha": "2025-05-01", "alcance": "acceso", "tipo_acto": "aprobados"},
        {"identificador": "BOE-A-2025-5", "fecha": "2025-06-01", "alcance": "acceso", "tipo_acto": "convocatoria"},
    ]
    ruta = tmp_path / "datos/boe/oposiciones/2026/10/28.jsonl"
    ruta.parent.mkdir(parents=True)
    ruta.write_text("".join(json.dumps(f) + "\n" for f in filas))
    assert [i for i, _ in pendientes(tmp_path)] == [
        "BOE-A-2026-1",  # reciente: primero, sea lo que sea
        "BOE-A-2025-5", "BOE-A-2023-3",  # acceso, convocatorias, de más nueva a más antigua
        "BOE-A-2025-4",  # acceso, aprobados
        "BOE-A-2024-2",  # fuera del alcance de la fase 1
    ]
