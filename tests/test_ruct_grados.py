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


def test_robots_no_legible_es_prohibido(monkeypatch):
    # RFC 9309: si robots.txt no se puede leer por error de red o de servidor, no se pide nada
    monkeypatch.setitem(http._ROBOTS, "https://www.educacion.gob.es", Robots(todo_prohibido=True))
    lector = ruct_grados.LectorConRobots(archivo=None, pausa=0)
    monkeypatch.setattr(lector.s, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debe pedir")))
    assert lector.get("https://www.educacion.gob.es/ruct/x")[0] == 0


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
