from motor.grados import qedu

# Respuestas reales de QEDU (sonda del 30/10/2026): Derecho en la Complutense y Psicología en Vic
DETALLE = {"titulacion": "Grado en Derecho", "nombreCentro": "Facultad de Derecho", "tipoCentro": "Propio",
           "modalidad": "Presencial", "idiomaextranjero": "No", "plazas": "709", "tasas": "65,67",
           "enlace": "https://www.ucm.es/estudios/grado", "tipoUniversidad": "Pública",
           "nombreUniversidad": "Universidad Complutense de Madrid", "ccaa": "Madrid (Comunidad de)",
           "provincia": "Madrid", "creditos": "240", "precio": "16,92 €", "notaCorte": "8,44", "notaCorteAnt": "8,88",
           "notaAdmision": "9,97", "ambito": "380", "nivel": "GRADO", "anioActual": "2025-2026",
           "anioAnterior": "2024-2025"}
INSERCION = {"tasaAfiliacion": "65,67%", "porcentajeAutonomos": "5,09%", "porcentajeIndefinidos": "90,59%",
             "porcentajeCotizacion": "50,6%", "baseMedia": "29 115,69 €"}


def test_numeros():
    assert qedu.numero("65,67%") == 65.67
    assert qedu.numero("29 115,69 €") == 29115.69
    assert qedu.numero("16,92 €") == 16.92
    assert qedu.numero("N/D") is None and qedu.numero("N/A") is None and qedu.numero(None) is None
    assert qedu.numero("1.234,5") == 1234.5


def test_detalle():
    d = qedu.limpiar_detalle(DETALLE)
    assert d["plazas"] == 709 and d["nota_corte"] == 8.44 and d["nota_corte_anterior"] == 8.88
    assert d["nota_media_admision"] == 9.97 and d["precio_credito"] == 16.92 and d["tasa_afiliacion"] == 65.67
    assert d["curso"] == "2025-2026" and d["ambito"] == "380"
    privada = qedu.limpiar_detalle({**DETALLE, "precio": "N/D", "notaAdmision": "N/D"})
    assert privada["precio_credito"] is None and privada["nota_media_admision"] is None


def test_insercion():
    assert qedu.limpiar_insercion(INSERCION) == {"tasa_afiliacion": 65.67, "autonomos": 5.09, "indefinidos": 90.59,
                                                 "cotizacion_adecuada": 50.6, "base_media_cotizacion": 29115.69}


def test_consultas_por_post(monkeypatch):
    pedidas = []

    class R:
        status = 200
        contenido = b'[{"codTitula": "2500828", "codCentro": "28027001", "codUniv": "010"}]'
        cabeceras = {}

    monkeypatch.setattr(qedu, "obtener", lambda url, **kw: pedidas.append((url, kw["formulario"])) or R())
    q = qedu.Qedu(archivo=None, pausa=0)
    datos, _ = q.tarjetas()
    assert datos[0]["codTitula"] == "2500828"
    url, campos = pedidas[0]
    assert url == qedu.URL and campos["action"] == "tarjeta" and campos["niveles"] == "'GRADO','GRADOD'"
    assert len(campos["ambitos"].split(",")) == 35
