import json

from motor.estudios import qedu_masters
from motor.grados import qedu


def test_tarjetas_y_detalles_de_master_van_a_su_carpeta(monkeypatch, tmp_path):
    pedidas = []

    def post(self, campos):
        pedidas.append(campos)
        if campos["action"] == "tarjeta":
            return [{"codTitula": "4310193", "codCentro": "30013645", "codUniv": "036", "nivel": "MASTER"}], None
        if campos["action"] == "detalle":
            return {"titulacion": "Máster Universitario en Finanzas", "precio": "33,62", "plazas": "40",
                    "ambito": "409", "nivel": "MASTER"}, None
        return {"tasaAfiliacion": "80,5%"}, None

    monkeypatch.setattr(qedu.Qedu, "post", post)
    monkeypatch.setattr(qedu, "PAUSA", 0)
    qedu_masters.tarjetas(tmp_path)
    assert pedidas[0]["niveles"] == "'MASTER','MASTERD'"
    t = tmp_path / "datos/estudios/masters/qedu/qedu_tarjetas_master.jsonl"
    assert t.exists() and not (tmp_path / "datos/estudios/grados").exists()
    res = qedu_masters.detalles(tmp_path, t, 0, None, 5)
    d = tmp_path / "datos/estudios/masters/qedu" / res["fichero"]
    fila = json.loads(d.read_text(encoding="utf-8").split("\n")[0])
    assert res["fichero"] == "qedu_detalles_master_0_fin.jsonl"
    assert fila["detalle"]["precio_credito"] == 33.62 and fila["detalle"]["plazas"] == 40
    assert fila["insercion"]["tasa_afiliacion"] == 80.5
