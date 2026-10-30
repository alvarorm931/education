from motor.grados import fichas


def _cat():
    return [{"codigo": "2500828", "clase": "grado", "nombre": "Derecho", "nombre_oficial": "Graduado o Graduada en Derecho por la Universidad Complutense de Madrid",
             "situacion": "Activo", "universidades": [{"nombre": "Complutense de Madrid", "tipo": "Pública"}],
             "universidad_tipo": "Pública", "rama": "CSJ", "campo": "Derecho", "componentes": [],
             "imparticiones": [{"situacion": "Activo", "presencialidad": "Estudio presencial", "idioma_extranjero": "No"}],
             "fuente": {"url": "u", "curso": "2025-2026", "capturado": "x"}}]


GEN = [{"id": "derecho", "nombre": "Derecho", "titulos": ["2500828"], "pagina_propia": True}]
TARJ = {("2500828", "28027001"): {"codTitula": "2500828", "codCentro": "28027001", "nombreCentro": "Facultad de Derecho",
                                  "tipoCentro": "Propio", "provincia": "Madrid", "notaCorte": "8.44", "anio": "2025-2026"}}
DET = {("2500828", "28027001"): {"detalle": {"nota_corte": 8.44, "nota_corte_anterior": 8.88, "plazas": 709.0,
                                             "precio_credito": 16.92, "creditos": 240.0, "curso": "2025-2026"},
                                 "insercion": {"tasa_afiliacion": 65.67, "base_media_cotizacion": 29115.69},
                                 "fuente": {"capturado": "2026-10-30T02:00:00+00:00"}}}
PLAN = {"identificador": "BOE-A-2024-1", "fecha": "2024-03-01", "tipo": "plan",
        "esperado_sin_optativas": 12.0, "suma_sin_optativas": 12.0,
        "distribucion": {"formacion_basica": 6, "obligatorias": 6, "optativas": 0, "total": 12},
        "plan": [{"nombre": "Derecho Romano", "tipo": "basica", "creditos": 6, "curso": 1, "semestre": 1},
                 {"nombre": "Derecho Civil I", "tipo": "obligatoria", "creditos": 6, "curso": 1, "semestre": 2}]}


def test_ficha_completa_es_indexable():
    planes = {(fichas.clave_universidad("Universidad Complutense de Madrid"), "derecho"): [PLAN]}
    f, comp = fichas.construir(_cat(), GEN, TARJ, DET, planes)
    f = f[0]
    assert f["indexable"] and f["motivos_noindex"] == []
    assert f["precio_primera_matricula"] == round(16.92 * 240, 2)
    assert f["centros"][0]["plazas"] == 709 and f["centros"][0]["insercion"]["tasa_afiliacion"] == 65.67
    assert f["plan"]["comprobado"] and len(f["plan"]["asignaturas"]) == 2
    assert comp[0]["generico"] == "derecho" and comp[0]["filas"][0]["nota_corte"] == 8.44


def test_sin_plan_ni_datos_no_indexa():
    f, _ = fichas.construir(_cat(), GEN, {}, {}, {})
    assert not f[0]["indexable"]
    assert set(f[0]["motivos_noindex"]) == {"sin asignaturas comprobadas", "sin nota de corte ni precio"}


def test_clave_universidad():
    assert fichas.clave_universidad("Universidad Complutense de Madrid") == fichas.clave_universidad("Complutense de Madrid")
    assert fichas.clave_universidad("Universitat de València (Estudi General)") == fichas.clave_universidad("València (Estudi General)")
