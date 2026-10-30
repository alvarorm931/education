from motor import http
from motor.grados import ruct_grados
from motor.robots import Robots


class Respuesta:
    status_code = 200
    content = b"<html></html>"
    headers = {}


def test_no_pide_lo_que_prohibe_robots(monkeypatch):
    monkeypatch.setitem(http._ROBOTS, "https://www.educacion.gob.es", Robots("User-agent: *\nDisallow: /ruct/"))
    lector = ruct_grados.LectorConRobots(archivo=None, pausa=0)
    pedidas = []
    monkeypatch.setattr(lector.s, "get", lambda url, timeout=0: pedidas.append(url) or Respuesta())
    estado, pagina, _ = lector.get("https://www.educacion.gob.es/ruct/estudio.action?CodigoEstudio=2500094")
    assert estado == 0 and pedidas == [] and lector.prohibidas == 1


def test_robots_no_legible_fuera_del_registro_es_prohibido(monkeypatch):
    # RFC 9309: si robots.txt no se puede leer por error de red o de servidor, no se pide nada
    monkeypatch.setitem(http._ROBOTS, "https://www.educacion.gob.es", Robots(todo_prohibido=True))
    lector = ruct_grados.LectorConRobots(archivo=None, pausa=0)
    monkeypatch.setattr(lector.s, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debe pedir")))
    assert lector.get("https://www.educacion.gob.es/otra/ruta")[0] == 0


def test_permitido_pasa(monkeypatch):
    monkeypatch.setitem(http._ROBOTS, "https://www.educacion.gob.es", Robots("User-agent: *\nDisallow: /privado/"))
    lector = ruct_grados.LectorConRobots(archivo=None, pausa=0)
    monkeypatch.setattr(lector.s, "get", lambda url, timeout=0: Respuesta())
    assert lector.get("https://www.educacion.gob.es/ruct/x")[0] == 200


def test_muestra_estratificada():
    cat = []
    for i in range(40):
        for tipo in ("Pública", "Privada"):
            for reg, pre in (("RD 1393/2007", "25"), ("RD 822/2021", "15")):
                cat.append({"codigo": f"{pre}{tipo[1]}{i:04d}", "clase": "grado", "situacion": "Activo",
                            "universidad_tipo": tipo, "regimen": reg})
    cat += [{"codigo": f"700{i:04d}", "clase": "doble", "situacion": "Activo", "universidad_tipo": "Pública",
             "regimen": None} for i in range(5)]
    m = ruct_grados.muestra(cat, 24, 1)
    assert len(m) == 26 and len(set(m)) == 26
    assert sum(1 for c in m if c.startswith("15")) == 4 and sum(1 for c in m if c.startswith("70")) == 2


def test_registro_publico_con_robots_ilegible(monkeypatch):
    # robots.txt que no responde: el RUCT se lee como registro público, el resto del servidor no
    monkeypatch.setitem(http._ROBOTS, "https://www.educacion.gob.es", Robots(todo_prohibido=True))
    lector = ruct_grados.LectorConRobots(archivo=None, pausa=0)
    monkeypatch.setattr(lector.s, "get", lambda url, timeout=0: Respuesta())
    assert lector.get("https://www.educacion.gob.es/ruct/estudio.action?CodigoEstudio=2500094")[0] == 200
    assert lector.excepcion_registro == 1
    assert lector.get("https://www.educacion.gob.es/otra/cosa")[0] == 0


def test_registro_publico_con_prohibicion_escrita_se_respeta(monkeypatch):
    monkeypatch.setitem(http._ROBOTS, "https://www.educacion.gob.es", Robots("User-agent: *\nDisallow: /ruct/"))
    lector = ruct_grados.LectorConRobots(archivo=None, pausa=0)
    monkeypatch.setattr(lector.s, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debe pedir")))
    assert lector.get("https://www.educacion.gob.es/ruct/x")[0] == 0 and lector.excepcion_registro == 0


def test_cortes_del_servidor_se_esperan_y_se_reintenta(monkeypatch, tmp_path):
    monkeypatch.setattr(ruct_grados, "PAUSA_CORTE", 0)
    respuestas = {"A": ["ok"], "B": ["corte", "ok"], "C": ["corte", "ok"], "D": ["corte", "ok"], "E": ["ok"]}

    def ficha(lector, codigo, tipo="G"):
        r = respuestas[codigo].pop(0)
        return {"codigo": codigo, "error": "ficha no disponible (estado 0)"} if r == "corte" else {"codigo": codigo, "fuente": {}}

    monkeypatch.setattr(ruct_grados.ruct, "leer_ficha", ficha)
    res = ruct_grados.ejecutar(["A", "B", "C", "D", "E"], tmp_path, "ficha", 5)
    assert res["hechos"] == 5 and res["alerta"] is None and not res["errores"]


def test_memoria_publicable_sin_textos_largos():
    from motor.grados.ruct_grados import sin_textos
    m = {"plan": [{"materias": [{"nombre": "Anatomía", "caracter": "Básica", "ects": 6.0, "despliegue": {"1": 6.0},
                                 "textos": ["x" * 2000]}]}], "acceso": {"textos": ["y" * 400]},
         "centros": [{"normas_permanencia": "https://u.es/n.pdf", "plazas_total": 140.0}]}
    p = sin_textos(m)
    mat = p["plan"][0]["materias"][0]
    assert (mat["nombre"], mat["caracter"], mat["ects"], mat["despliegue"]) == ("Anatomía", "Básica", 6.0, {"1": 6.0})
    assert mat["textos"][0]["caracteres"] == 2000 and len(mat["textos"][0]["sha256"]) == 64
    assert p["acceso"]["textos"][0]["caracteres"] == 400
    assert p["centros"][0] == {"normas_permanencia": "https://u.es/n.pdf", "plazas_total": 140.0}


def test_plan_de_la_memoria_sin_paginas_que_no_hacen_falta(monkeypatch):
    from motor.estudios import ruct
    from motor.grados import ruct_grados as rg

    pedidas = []

    class Lector:
        peticiones = 0

        class s:
            class cookies:
                @staticmethod
                def clear():
                    pass

        def get(self, url):
            self.peticiones += 1
            pedidas.append(url)
            if "modulos?" in url:
                return 200, "codModulo=1", None
            if "datosModulo" in url:
                return 200, "codModulo=1&codMateria=7", None
            if "datosMateria" in url:
                return 200, "actividadesMateria sistemasMateria datosMateria!contenidos codAsignatura=3 codAsignatura=4", None
            return 200, "pagina", None

    monkeypatch.setattr(ruct, "_comprobar", lambda p, n: True)
    monkeypatch.setattr(ruct, "parsear_materia", lambda p: {"nombre": "x", "caracter": "Obligatoria", "ects": 6.0,
                                                            "unidad_temporal": "Semestral", "despliegue": "1"})
    ficha = {"nombre": "Grado", "nivel": "Grado", "memorias": [{"cod": "2500094ABCDEF", "sit": "A"}],
             "fuente": {"url": "https://www.educacion.gob.es/ruct/estudio?x"}}
    m = rg.leer_plan_memoria(Lector(), ficha)
    assert m["cobertura"] == {"materias": 1, "asignaturas": 2} and m["solo_plan"]
    assert not any(k in u for u in pedidas for k in ("actividadesMateria", "sistemasMateria", "contenidos",
                                                      "accesoAdmision", "resultados", "datosCentro"))
