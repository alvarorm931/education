"""Descargas educadas: identificadas, con reintentos limitados, sin martillear a las fuentes y dentro de lo que
permite su robots.txt.

robots.txt (RFC 9309): antes de la primera petición a un servidor se lee el suyo (con la misma sesión que usa el
conector) y no se pide nada que prohíba a nuestro agente. Si no se puede leer por un error de servidor o de red,
se trata como prohibido (RFC 9309, 2.3.1.4); un 4xx o una página HTML en su lugar es que no hay reglas. Una
dirección prohibida lanza RobotsProhibe (un ConnectionError: los conectores lo anotan como fuente inaccesible y
paran tras varios seguidos). Auditoría de todas las fuentes: motor/robots_auditoria.py."""

from __future__ import annotations

import os
import ssl
import re
import tempfile
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter

from motor.robots import Robots

USER_AGENT = "PortalEstudiosOposiciones/0.1 (motor de datos publicos; peticiones moderadas)"
REINTENTABLES = {429, 500, 502, 503, 504}
CERTIFICADOS = Path(__file__).parent / "certificados"


@lru_cache(maxsize=1)
def paquete_ca() -> str:
    """Raíces de certifi (o las del entorno) más los intermedios públicos de motor/certificados/, para los
    servidores oficiales que no envían su cadena completa. La verificación sigue activa."""
    import certifi

    base = os.environ.get("REQUESTS_CA_BUNDLE") or certifi.where()
    extra = sorted(CERTIFICADOS.glob("*.pem"))
    if not extra:
        return base
    destino = Path(tempfile.gettempdir()) / f"motor-ca-{os.getpid()}.pem"
    destino.write_text(Path(base).read_text(encoding="utf-8") + "\n" +
                       "\n".join(p.read_text(encoding="utf-8") for p in extra), encoding="utf-8")
    return str(destino)


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
        ctx = ssl.create_default_context(cafile=paquete_ca())
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


class RobotsProhibe(ConnectionError):
    """La dirección está prohibida para nuestro agente en el robots.txt del servidor."""


_ROBOTS: dict[str, Robots] = {}
ROBOTS_ESTADO: dict[str, str] = {}  # cómo se leyó cada robots.txt (para la auditoría y los avisos)
ROBOTS_TEXTO: dict[str, str] = {}   # su texto, como prueba de lo que decía ese día


def _origen(url: str) -> str:
    from urllib.parse import urlparse

    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}".lower()


def robots_de(url: str, sesion: requests.Session | None = None) -> Robots:
    """Reglas del servidor de url (se leen una vez por ejecución)."""
    origen = _origen(url)
    if origen not in _ROBOTS:
        reglas, estado = None, "sin intentos"
        # Con la sesión del conector y, si falla la conexión, con la de cifrados TLS compatibles (DOGC)
        for http in [sesion or requests.Session(), sesion_tls_compatible()]:
            for _ in range(2):
                try:
                    r = http.get(origen + "/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=20,
                                 verify=paquete_ca())
                except requests.RequestException as e:
                    estado = f"error de conexión: {type(e).__name__}"
                    time.sleep(2)
                    continue
                tipo = (r.headers.get("content-type") or "").lower()
                if r.status_code >= 500:
                    estado = f"HTTP {r.status_code}"
                    time.sleep(2)
                    continue
                if r.status_code == 200 and "html" not in tipo:
                    reglas, estado = Robots(r.text), "HTTP 200"
                    ROBOTS_TEXTO[origen] = r.text[:100_000]
                else:
                    reglas, estado = Robots(), f"HTTP {r.status_code}{' (HTML)' if 'html' in tipo else ''}: sin reglas"
                break
            if reglas is not None:
                break
        _ROBOTS[origen] = reglas if reglas is not None else Robots(todo_prohibido=True)
        ROBOTS_ESTADO[origen] = estado
    return _ROBOTS[origen]


# Servicios de datos que su responsable documenta para que se consulten o descarguen con programas, aunque su
# robots.txt (pensado para buscadores) lo cierre todo. Solo con cita literal de la documentación oficial; cada
# fuente nueva aquí la decide Álvaro.
EXCEPCIONES_ROBOTS = {
    "https://data.commoncrawl.org": (
        "«To access data from outside the Amazon cloud, via HTTP(S), the new URL prefix "
        "https://data.commoncrawl.org/ – must be used»", "https://commoncrawl.org/the-data/get-started/", "2026-10-30"),
    "https://index.commoncrawl.org": (
        "«The index is served from index.commoncrawl.org» · «the CDXJ index is free to access or download for anybody»",
        "https://commoncrawl.org/cdxj-index", "2026-10-30"),
}


# Boletines oficiales que se leen aunque su robots.txt lo cierre: decisión de Álvaro del 30/10/2026 («podemos usar
# los datos»). Publican disposiciones y actos de organismos públicos, que no son objeto de propiedad intelectual, y
# la ley de reutilización los hace reutilizables (BASE_BOLETINES). Solo estas direcciones, con las mismas peticiones
# moderadas e identificadas de siempre y sin guardar datos de personas. El resto de servidores, incluidas las webs
# de los centros de estudios, sigue con su robots.txt.
BASE_BOLETINES = (
    ("«No son objeto de propiedad intelectual las disposiciones legales o reglamentarias y sus correspondientes "
     "proyectos, las resoluciones de los órganos jurisdiccionales y los actos, acuerdos, deliberaciones y dictámenes "
     "de los organismos públicos»", "Real Decreto Legislativo 1/1996 (Ley de Propiedad Intelectual), art. 13",
     "https://www.boe.es/buscar/act.php?id=BOE-A-1996-8930#a13"),
    ("«Los documentos de los sujetos previstos en el artículo 2 serán reutilizables en los términos previstos en esta "
     "ley»", "Ley 37/2007, de reutilización de la información del sector público, art. 4.1",
     "https://www.boe.es/buscar/act.php?id=BOE-A-2007-19814#a4"),
)
BOLETINES_OFICIALES = {
    "https://analisis.datosabiertos.jcyl.es/api/explore/v2.1/catalog/datasets/bocyl": "BOCYL (API de datos abiertos)",
    "https://bocyl.jcyl.es/boletines/": "BOCYL (textos)",
    "https://portaldogc.gencat.cat/eadop-rest/api/dogc": "DOGC (API del portal)",
    "https://www.caib.es/eboibfront/": "BOIB",
    "https://docm.jccm.es/docm/": "DOCM (sumarios por fecha)",
    "https://docm.jccm.es/portaldocm/": "DOCM",
    "https://bop.diba.cat/": "BOP de Barcelona",
    "https://www.dip-alicante.es/bop2/": "BOP de Alicante (PDF)",
    "https://bop.dacoruna.gal/bopportal/": "BOP de A Coruña",
    "https://boppo.depo.gal/": "BOP de Pontevedra",
    "https://bop.dipucr.es/": "BOP de Ciudad Real",
    "https://se1.dipucr.es:4443/SIGEM_BuscadorDocsWeb/": "BOP de Ciudad Real (PDF)",
    "https://bop.diputoledo.es/": "BOP de Toledo",
    "https://miprincipado.asturias.es/bopa/": "BOPA (textos)",
    "https://www.boplaspalmas.com/": "BOP de Las Palmas",
    "https://www.boplaspalmas.net/": "BOP de Las Palmas (redirige de .com a .net)",
    "https://ebop.diputaciolleida.cat/": "BOP de Lleida",
    "https://www.dip-badajoz.es/bop/": "BOP de Badajoz",
    "https://sede.diphuelva.es/": "BOP de Huelva (robots.txt no responde)",
    "https://s2.diphuelva.es/servicios/bope_web/": "BOP de Huelva (desde el 20/06/2023)",
    "https://s2.diphuelva.es/servicios/bop/": "BOP de Huelva (hasta el 20/06/2023)",
    "https://s2.diphuelva.es/lib/bope/": "BOP de Huelva (sumarios por fecha)",
    "https://bop.dipcas.es/": "BOP de Castellón (robots.txt no responde)",
    "https://www.bopcadiz.org/": "BOP de Cádiz (robots.txt no responde)",
    "https://bop.dpz.es/": "BOP de Zaragoza (robots.txt no responde)",
}
DECISION_BOLETINES = ("Álvaro", "2026-10-30")
# Documentos concretos que el boletín cierra en su robots.txt para proteger datos de personas (el BOPA tiene más de 600
# reglas con el código de la disposición): esos se respetan siempre, también en los boletines de la lista anterior.
CODIGO_DOCUMENTO = {"https://miprincipado.asturias.es": re.compile(r"(?<![\d-])(\d{4}-\d{5})(?![\d])")}


def retirado_por_privacidad(url: str, sesion: requests.Session | None = None) -> str | None:
    """La regla de robots.txt que cierra ese documento concreto (por su código), si la hay."""
    patron = CODIGO_DOCUMENTO.get(_origen(url))
    m = patron.search(url) if patron else None
    if not m:
        return None
    return next((ruta for permite, ruta, _ in robots_de(url, sesion).reglas if not permite and m.group(1) in ruta), None)


def boletin_oficial(url: str) -> str | None:
    """Nombre del boletín si url es de un boletín oficial que se lee aunque su robots.txt lo cierre."""
    u = url.lower().split("://", 1)[-1]  # da igual http o https
    return next((v for k, v in BOLETINES_OFICIALES.items() if u.startswith(k.split("://", 1)[-1])), None)


def comprobar_robots(url: str, sesion: requests.Session | None = None) -> None:
    from urllib.parse import urlparse

    if urlparse(url).path == "/robots.txt" or _origen(url) in EXCEPCIONES_ROBOTS:
        return
    if boletin_oficial(url):
        regla = retirado_por_privacidad(url, sesion)
        if regla:
            raise RobotsProhibe(f"robots.txt de {_origen(url)} cierra este documento concreto ({regla})")
        return
    permitido, regla = robots_de(url, sesion).regla(url)
    if not permitido:
        raise RobotsProhibe(f"robots.txt de {_origen(url)} no permite {url} ({regla})")


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
    cabeceras_extra: dict[str, str] | None = None,
) -> Respuesta:
    """Descarga una URL. Reintenta solo errores transitorios (red, 429, 5xx) con espera creciente.

    formulario: si se indica, la petición es POST con esos campos (algunas API oficiales solo aceptan POST).
    cabeceras_extra: cabeceras que pide un portal (p. ej. las de una petición AJAX de JSF).
    limite_total: segundos máximos para recibir la respuesta entera (el timeout de requests es por lectura y un
    servidor que envía muy despacio podría bloquear la ejecución).
    """
    cabeceras = {"User-Agent": USER_AGENT, **(cabeceras_extra or {})}
    if accept:
        cabeceras["Accept"] = accept
    http = sesion or requests.Session()
    comprobar_robots(url, http)
    ultimo_error: Exception | None = None
    for intento in range(intentos):
        try:
            if formulario is None:
                r = http.get(url, headers=cabeceras, timeout=timeout, stream=True, verify=paquete_ca())
            else:
                r = http.post(url, data=formulario, headers=cabeceras, timeout=timeout, stream=True,
                              verify=paquete_ca())
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
