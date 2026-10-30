"""Credenciales temporales de AWS para el almacén de originales, renovadas solas durante ejecuciones largas.

En GitHub Actions (también en el servidor de España, que es un ejecutor de GitHub) el flujo con
«permissions: id-token: write» puede pedir en cualquier momento un token OIDC a GitHub y canjearlo en STS por
credenciales del rol education-originales-github (claude/infraestructura.md), sin claves guardadas en ningún sitio.
Esas credenciales duran una hora y los trabajos de boletines duran hasta seis: aquí se renuevan antes de caducar
(botocore las refresca cuando faltan menos de 15 minutos).

Fuera de GitHub Actions se usa la cadena normal de boto3 (variables de entorno, perfil, rol de la instancia).
"""

from __future__ import annotations

import os

ROL = "arn:aws:iam::369017477131:role/education-originales-github"
REGION = "eu-south-2"
DURACION = 3600  # la máxima que permite el rol


def _token_github() -> str:
    import requests

    url = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"] + "&audience=sts.amazonaws.com"
    r = requests.get(url, headers={"Authorization": "bearer " + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]},
                     timeout=30)
    r.raise_for_status()
    return r.json()["value"]


def _renovar(region: str, rol: str) -> dict:
    import boto3
    from botocore import UNSIGNED
    from botocore.config import Config

    sts = boto3.client("sts", region_name=region, config=Config(signature_version=UNSIGNED))
    sesion = f"motor-{os.environ.get('GITHUB_RUN_ID', 'local')}-{os.environ.get('GITHUB_JOB', '')}"[:64]
    c = sts.assume_role_with_web_identity(RoleArn=rol, RoleSessionName=sesion, WebIdentityToken=_token_github(),
                                          DurationSeconds=DURACION)["Credentials"]
    return {"access_key": c["AccessKeyId"], "secret_key": c["SecretAccessKey"], "token": c["SessionToken"],
            "expiry_time": c["Expiration"].isoformat()}


def cliente_s3(region: str = REGION, rol: str | None = None):
    """Cliente de S3 con credenciales que se renuevan solas en GitHub Actions; si no, el de boto3 por defecto."""
    import boto3

    if not (os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL") and os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN")):
        return boto3.client("s3", region_name=region)
    import botocore.session
    from botocore.credentials import RefreshableCredentials

    rol = rol or os.environ.get("MOTOR_ROL_ORIGINALES", ROL)
    credenciales = RefreshableCredentials.create_from_metadata(
        metadata=_renovar(region, rol), refresh_using=lambda: _renovar(region, rol),
        method="assume-role-with-web-identity")
    sesion = botocore.session.get_session()
    sesion._credentials = credenciales
    return boto3.Session(botocore_session=sesion).client("s3", region_name=region)
