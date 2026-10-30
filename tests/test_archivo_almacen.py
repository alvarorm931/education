"""Archivo de originales con el almacén S3: el original va al almacén, nunca a la carpeta local (rama pública)."""

import io
from datetime import date

import pytest

pytest.importorskip("botocore")
from botocore.exceptions import ClientError  # noqa: E402

from motor.almacen import Almacen  # noqa: E402
from motor.archivo import Archivo, leer_original  # noqa: E402


class S3Simulado:
    def __init__(self):
        self.objetos, self.puts = {}, 0

    def put_object(self, Bucket, Key, Body, IfNoneMatch=None, **k):
        self.puts += 1
        assert IfNoneMatch == "*"  # toda escritura es condicional
        if Key in self.objetos:
            raise ClientError({"Error": {"Code": "PreconditionFailed"}, "ResponseMetadata": {"HTTPStatusCode": 412}},
                              "PutObject")
        self.objetos[Key] = Body

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.objetos[Key])}


def test_archivo_va_al_almacen_y_no_al_disco(tmp_path):
    s3 = S3Simulado()
    alm = Almacen("x", cliente=s3)
    arch = Archivo(tmp_path / "archivo", indice_por_fuente=True, almacen=alm)
    r1 = arch.guardar("bocm", date(2026, 10, 29), b"<html>original</html>", "https://u", "html", 200)
    r2 = arch.guardar("bocm", date(2026, 10, 29), b"<html>original</html>", "https://u", "html", 200)
    assert r1["nuevo"] and not r2["nuevo"] and r1["clave"] == f"bocm/2026/10/29/{r1['sha256']}.html.gz"
    assert s3.puts == 1  # la segunda ni se intenta: ya se guardó en esta ejecución
    otra = Archivo(tmp_path / "otra", almacen=alm)
    assert not otra.guardar("bocm", date(2026, 10, 29), b"<html>original</html>", "https://u", "html", 200)["nuevo"]
    assert leer_original(r1, alm) == b"<html>original</html>"
    assert not [p for p in (tmp_path / "archivo").rglob("*") if p.suffix == ".gz"]
    assert (tmp_path / "archivo" / "indices" / "bocm" / "2026-10.jsonl").exists()


def test_fallo_del_almacen_no_para_el_motor(tmp_path):
    class Caido(S3Simulado):
        def put_object(self, **k):
            raise ClientError({"Error": {"Code": "AccessDenied"}, "ResponseMetadata": {"HTTPStatusCode": 403}},
                              "PutObject")

    arch = Archivo(tmp_path, almacen=Almacen("x", cliente=Caido()))
    for i in range(6):
        r = arch.guardar("f", date(2026, 1, 1), bytes([i]), "u", "html", 200)
    assert r["solo_huella"] and arch.almacen is None  # tras 5 fallos seguidos, solo huella


def test_almacen_solo_si_se_pide(tmp_path, monkeypatch):
    monkeypatch.delenv("MOTOR_ORIGINALES", raising=False)
    assert Archivo(tmp_path).almacen is None


def test_credenciales_se_renuevan_en_github(monkeypatch):
    """En GitHub Actions el cliente pide credenciales a STS con el token OIDC y las renueva antes de caducar."""
    from datetime import datetime, timedelta, timezone

    from motor import credenciales_aws as c

    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", "https://token.invalid/?x=1")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "t")
    llamadas = []

    def renovar(region, rol):
        llamadas.append(rol)
        caduca = datetime.now(timezone.utc) + timedelta(minutes=5 if len(llamadas) == 1 else 60)
        return {"access_key": f"AK{len(llamadas)}", "secret_key": "s", "token": "t", "expiry_time": caduca.isoformat()}

    monkeypatch.setattr(c, "_renovar", renovar)
    s3 = c.cliente_s3()
    credenciales = s3._request_signer._credentials
    assert credenciales.get_frozen_credentials().access_key == "AK2"  # a 5 minutos de caducar: se renueva
    assert llamadas == [c.ROL, c.ROL]
