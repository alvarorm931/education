"""Descargas educadas: identificadas, con reintentos limitados y sin martillear a las fuentes."""

from __future__ import annotations

import ssl
import time
from dataclasses import dataclass, field

import requests
from requests.adapters import HTTPAdapter

USER_AGENT = "PortalEstudiosOposiciones/0.1 (motor de datos publicos; peticiones moderadas)"
REINTENTABLES = {429, 500, 502, 503, 504}


class _AdaptadorTLS(HTTPAdapter):
    """Adaptador con la lista de cifrados por defecto de OpenSSL.

    Python 3.10+ solo ofrece cifrados con secreto perfecto hacia delante; algunos servidores oficiales (DOGC)
    solo aceptan otros cifrados TLS 1.2 que OpenSSL sigue considerando seguros. Se mantiene la verificación del
    certificado y del nombre del servidor.
    """

    def __init__(self, cifrados: str = "DEFAULT", **kwargs):
        self.cifrados = cifrados
        super().__init__(**kwargs)

    def _contexto(self) -> ssl.SSLContext:
        import certifi

        ctx = ssl.create_default_context(cafile=certifi.where())
        ctx.set_ciphers(self.cifrados)
        return ctx

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = self._contexto()
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        kwargs["ssl_context"] = self._contexto()
        return super().proxy_manager_for(*args, **kwargs)


def _leer_con_limite(r: requests.Response, limite: float) -> bytes:
    fin = time.monotonic() + limite
    trozos = []
    for trozo in r.iter_content(chunk_size=65536):
        trozos.append(trozo)
        if time.monotonic() > fin:
            r.close()
            raise TimeoutError(f"respuesta de {r.url} sin terminar tras {limite:.0f} s")
    return b"".join(trozos)


def sesion_tls_compatible(cifrados: str = "DEFAULT") -> requests.Session:
    s = requests.Session()
    s.mount("https://", _AdaptadorTLS(cifrados))
    return s


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
    formulario: dict[str, str] | None = None,
    limite_total: float = 180.0,
) -> Respuesta:
    """Descarga una URL. Reintenta solo errores transitorios (red, 429, 5xx) con espera creciente.

    formulario: si se indica, la petición es POST con esos campos (algunas API oficiales solo aceptan POST).
    limite_total: segundos máximos para recibir la respuesta entera (el timeout de requests es por lectura y un
    servidor que envía muy despacio podría bloquear la ejecución).
    """
    cabeceras = {"User-Agent": USER_AGENT}
    if accept:
        cabeceras["Accept"] = accept
    http = sesion or requests.Session()
    ultimo_error: Exception | None = None
    for intento in range(intentos):
        try:
            if formulario is None:
                r = http.get(url, headers=cabeceras, timeout=timeout, stream=True)
            else:
                r = http.post(url, data=formulario, headers=cabeceras, timeout=timeout, stream=True)
            if r.status_code in REINTENTABLES and intento < intentos - 1:
                r.close()
                espera = float(r.headers.get("Retry-After", pausa_base * (2**intento)))
                time.sleep(min(espera, 60))
                continue
            contenido = _leer_con_limite(r, limite_total)
            utiles = {k: v for k, v in r.headers.items() if k.lower() in {"etag", "last-modified", "content-type", "date"}}
            return Respuesta(url=r.url, status=r.status_code, contenido=contenido, cabeceras=utiles)
        except (requests.RequestException, TimeoutError) as e:  # red caída, timeout, DNS, respuesta interminable
            ultimo_error = e
            if intento < intentos - 1:
                time.sleep(pausa_base * (2**intento))
    raise ConnectionError(f"No se pudo descargar {url} tras {intentos} intentos: {ultimo_error}")
