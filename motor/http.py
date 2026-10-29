"""Descargas educadas: identificadas, con reintentos limitados y sin martillear a las fuentes."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import requests

USER_AGENT = "PortalEstudiosOposiciones/0.1 (motor de datos publicos; peticiones moderadas)"
REINTENTABLES = {429, 500, 502, 503, 504}


@dataclass
class Respuesta:
    url: str
    status: int
    contenido: bytes
    cabeceras: dict[str, str] = field(default_factory=dict)


def obtener(
    url: str,
    accept: str | None = None,
    intentos: int = 4,
    timeout: float = 30.0,
    pausa_base: float = 2.0,
    sesion: requests.Session | None = None,
) -> Respuesta:
    """Descarga una URL. Reintenta solo errores transitorios (red, 429, 5xx) con espera creciente."""
    cabeceras = {"User-Agent": USER_AGENT}
    if accept:
        cabeceras["Accept"] = accept
    http = sesion or requests.Session()
    ultimo_error: Exception | None = None
    for intento in range(intentos):
        try:
            r = http.get(url, headers=cabeceras, timeout=timeout)
            if r.status_code in REINTENTABLES and intento < intentos - 1:
                espera = float(r.headers.get("Retry-After", pausa_base * (2**intento)))
                time.sleep(min(espera, 60))
                continue
            utiles = {k: v for k, v in r.headers.items() if k.lower() in {"etag", "last-modified", "content-type", "date"}}
            return Respuesta(url=r.url, status=r.status_code, contenido=r.content, cabeceras=utiles)
        except requests.RequestException as e:  # red caída, timeout, DNS
            ultimo_error = e
            if intento < intentos - 1:
                time.sleep(pausa_base * (2**intento))
    raise ConnectionError(f"No se pudo descargar {url} tras {intentos} intentos: {ultimo_error}")
