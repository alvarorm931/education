"""Almacén privado de originales en S3 (AWS, región España), escritura única: nunca se sobrescribe una clave.

Almacén: education-originales-finads (eu-south-2), privado, cifrado SSE-S3. Los flujos de GitHub no llevan
claves: piden credenciales temporales por OIDC al rol education-originales-github, que solo pueden asumir los
flujos de la rama main y que permite listar, leer y guardar, pero no borrar (docs: claude/infraestructura.md).

Escritura única. PutObject sí sobrescribe una clave existente, así que toda escritura va con la cabecera
If-None-Match: * («conditional writes» de S3): si la clave ya existe, S3 la rechaza con 412 Precondition Failed y
el original guardado no se toca. No se comprueba antes con HeadObject: entre la comprobación y la escritura otro
proceso podría guardar la misma clave; con la condición en la propia escritura, S3 lo resuelve de forma atómica
(https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html).

Claves: mismo esquema que motor/archivo.py, {fuente}/{AAAA}/{MM}/{DD}/{sha256}.{ext}[.gz]. Como la clave lleva la
huella del contenido, una clave nunca puede corresponder a dos contenidos distintos.

Uso:
  python -m motor.almacen prueba      sube un objeto de prueba, lo lee, comprueba la huella y que no se sobrescribe
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone

ALMACEN = os.environ.get("MOTOR_ALMACEN", "education-originales-finads")
REGION = os.environ.get("MOTOR_ALMACEN_REGION", "eu-south-2")


@dataclass
class Resultado:
    clave: str
    nuevo: bool          # False: la clave ya existía y no se ha tocado
    sha256: str
    bytes: int


def clave_original(fuente: str, fecha_ref: date, sha256: str, ext: str, comprimido: bool = True) -> str:
    return f"{fuente}/{fecha_ref:%Y}/{fecha_ref:%m}/{fecha_ref:%d}/{sha256}.{ext}{'.gz' if comprimido else ''}"


class Almacen:
    def __init__(self, nombre: str = ALMACEN, region: str = REGION, cliente=None):
        if cliente is None:
            import boto3

            cliente = boto3.client("s3", region_name=region)
        self.s3 = cliente
        self.nombre = nombre

    def guardar(self, clave: str, datos: bytes, tipo: str = "application/octet-stream",
                metadatos: dict[str, str] | None = None) -> bool:
        """Guarda datos en clave solo si no existe. Devuelve True si es nuevo y False si ya estaba."""
        from botocore.exceptions import ClientError

        for intento in range(3):
            try:
                self.s3.put_object(Bucket=self.nombre, Key=clave, Body=datos, ContentType=tipo, IfNoneMatch="*",
                                   ChecksumAlgorithm="SHA256", Metadata=metadatos or {})
                return True
            except ClientError as e:
                codigo = e.response.get("Error", {}).get("Code")
                estado = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                if codigo == "PreconditionFailed" or estado == 412:
                    return False  # ya existe: no se sobrescribe
                if (codigo == "ConditionalRequestConflict" or estado == 409) and intento < 2:
                    time.sleep(2 * (intento + 1))  # escritura simultánea de la misma clave: S3 pide reintentar
                    continue
                raise
        return False

    def guardar_original(self, fuente: str, fecha_ref: date, contenido: bytes, ext: str, url: str,
                         comprimir: bool = True) -> Resultado:
        sha = hashlib.sha256(contenido).hexdigest()
        clave = clave_original(fuente, fecha_ref, sha, ext, comprimir)
        datos = gzip.compress(contenido, mtime=0) if comprimir else contenido
        # Los metadatos de S3 solo admiten ASCII: la URL va codificada
        nuevo = self.guardar(clave, datos, "application/gzip" if comprimir else "application/octet-stream",
                             {"sha256-original": sha, "url": url.encode("ascii", "backslashreplace").decode()[:1500]})
        return Resultado(clave=clave, nuevo=nuevo, sha256=sha, bytes=len(contenido))

    def leer(self, clave: str) -> bytes:
        datos = self.s3.get_object(Bucket=self.nombre, Key=clave)["Body"].read()
        return gzip.decompress(datos) if clave.endswith(".gz") else datos

    def existe(self, clave: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.s3.head_object(Bucket=self.nombre, Key=clave)
            return True
        except ClientError as e:
            if e.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                return False
            raise

    def cabeceras(self, clave: str) -> dict:
        r = self.s3.head_object(Bucket=self.nombre, Key=clave, ChecksumMode="ENABLED")
        return {"cifrado": r.get("ServerSideEncryption"), "bytes": r.get("ContentLength"),
                "sha256_s3": r.get("ChecksumSHA256"), "metadatos": r.get("Metadata", {})}


def prueba(almacen: Almacen | None = None) -> dict:
    """Prueba de punta a punta: subir, leer, comprobar la huella, no sobrescribir y distinguir lo que no existe."""
    a = almacen or Almacen()
    ahora = datetime.now(timezone.utc)
    contenido = (f"Prueba del almacén de originales. {ahora.isoformat(timespec='seconds')} · ejecución "
                 f"{os.environ.get('GITHUB_RUN_ID', 'local')}·{os.environ.get('GITHUB_RUN_ATTEMPT', '1')} · "
                 f"{os.environ.get('RUNNER_NAME', 'sin ejecutor')}\n").encode("utf-8")
    comprobaciones: dict[str, bool] = {}
    r = a.guardar_original("pruebas-almacen", ahora.date(), contenido, "txt", "https://example.invalid/prueba")
    comprobaciones["subida_nueva"] = r.nuevo
    leido = a.leer(r.clave)
    comprobaciones["lectura_identica"] = hashlib.sha256(leido).hexdigest() == r.sha256
    # Segunda escritura en la misma clave con otro contenido: S3 tiene que rechazarla
    otra = a.guardar(r.clave, gzip.compress(b"esto no debe sustituir al original", mtime=0))
    comprobaciones["no_sobrescribe"] = otra is False
    comprobaciones["original_intacto"] = hashlib.sha256(a.leer(r.clave)).hexdigest() == r.sha256
    cab = a.cabeceras(r.clave)
    comprobaciones["cifrado_sse_s3"] = cab["cifrado"] == "AES256"
    comprobaciones["metadatos_huella"] = cab["metadatos"].get("sha256-original") == r.sha256
    comprobaciones["existe"] = a.existe(r.clave)
    comprobaciones["inexistente_da_404"] = a.existe(r.clave + ".no-existe") is False
    return {"almacen": a.nombre, "clave": r.clave, "bytes": r.bytes, "sha256": r.sha256, "cabeceras": cab,
            "comprobaciones": comprobaciones, "correcto": all(comprobaciones.values())}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] != "prueba":
        sys.exit("Uso: python -m motor.almacen prueba")
    res = prueba()
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(0 if res["correcto"] else 1)


if __name__ == "__main__":
    main()
