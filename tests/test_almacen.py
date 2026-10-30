"""El almacén nunca sobrescribe: se prueba con un S3 simulado que aplica If-None-Match como el real."""

import gzip
import io

import pytest

pytest.importorskip("botocore")
from botocore.exceptions import ClientError  # noqa: E402

from motor import almacen  # noqa: E402


def _error(codigo, estado):
    return ClientError({"Error": {"Code": codigo}, "ResponseMetadata": {"HTTPStatusCode": estado}}, "op")


class S3Simulado:
    def __init__(self):
        self.objetos = {}
        self.llamadas = []

    def put_object(self, Bucket, Key, Body, IfNoneMatch=None, **kw):
        self.llamadas.append(("put", Key, IfNoneMatch))
        if IfNoneMatch == "*" and Key in self.objetos:
            raise _error("PreconditionFailed", 412)
        self.objetos[Key] = (Body, kw.get("Metadata", {}))

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.objetos[Key][0])}

    def head_object(self, Bucket, Key, **kw):
        if Key not in self.objetos:
            raise _error("404", 404)
        return {"ServerSideEncryption": "AES256", "ContentLength": len(self.objetos[Key][0]),
                "Metadata": self.objetos[Key][1]}


def test_toda_escritura_lleva_la_condicion():
    s3 = S3Simulado()
    a = almacen.Almacen(cliente=s3)
    a.guardar("x/1", b"a")
    assert s3.llamadas == [("put", "x/1", "*")]


def test_no_sobrescribe_una_clave_existente():
    s3 = S3Simulado()
    a = almacen.Almacen(cliente=s3)
    assert a.guardar("x/1", b"original") is True
    assert a.guardar("x/1", b"otro") is False
    assert s3.objetos["x/1"][0] == b"original"


def test_conflicto_simultaneo_se_reintenta(monkeypatch):
    monkeypatch.setattr(almacen.time, "sleep", lambda s: None)
    s3 = S3Simulado()
    fallos = [_error("ConditionalRequestConflict", 409)]
    original = s3.put_object

    def put(**kw):
        if fallos:
            raise fallos.pop()
        return original(**kw)

    s3.put_object = put
    assert almacen.Almacen(cliente=s3).guardar("x/1", b"a") is True


def test_original_con_huella_y_comprimido():
    s3 = S3Simulado()
    a = almacen.Almacen(cliente=s3)
    from datetime import date

    r = a.guardar_original("boe-texto", date(2026, 10, 30), b"<html>hola</html>", "html", "https://www.boe.es/x?id=1")
    assert r.clave.startswith("boe-texto/2026/10/30/") and r.clave.endswith(".html.gz") and r.sha256 in r.clave
    assert gzip.decompress(s3.objetos[r.clave][0]) == b"<html>hola</html>"
    assert a.leer(r.clave) == b"<html>hola</html>"
    assert s3.objetos[r.clave][1]["sha256-original"] == r.sha256


def test_prueba_completa_con_simulado():
    res = almacen.prueba(almacen.Almacen(cliente=S3Simulado()))
    assert res["correcto"], res["comprobaciones"]
