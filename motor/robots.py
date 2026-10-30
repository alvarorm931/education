"""robots.txt según la RFC 9309 (https://www.rfc-editor.org/rfc/rfc9309), con comodines.

urllib.robotparser compara solo prefijos: no entiende «Disallow: /*.pdf» ni «Disallow: *.pdf» ni «$», que sí usan
fuentes como el BOP de Pontevedra. Aquí: grupo del agente (si no lo hay, el de «*»), y gana la regla que casa con
más caracteres; si empatan una Allow y una Disallow, gana Allow (RFC 9309, 2.2.2).
"""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

AGENTE = "PortalEstudiosOposiciones"


def _patron(ruta: str) -> re.Pattern:
    fin = ruta.endswith("$")
    cuerpo = re.escape(ruta[:-1] if fin else ruta).replace(r"\*", ".*")
    return re.compile(cuerpo + ("$" if fin else ""))


class Robots:
    def __init__(self, texto: str = "", agente: str = AGENTE, todo_prohibido: bool = False):
        self.todo_prohibido = todo_prohibido
        grupos: list[tuple[list[str], list[tuple[bool, str]]]] = []
        agentes, reglas, en_reglas = [], [], False
        for linea in texto.splitlines():
            linea = linea.split("#", 1)[0].strip()
            if ":" not in linea:
                continue
            clave, valor = (x.strip() for x in linea.split(":", 1))
            clave = clave.lower()
            if clave == "user-agent":
                if en_reglas:
                    grupos.append((agentes, reglas))
                    agentes, reglas, en_reglas = [], [], False
                agentes.append(valor.lower())
            elif clave in ("allow", "disallow"):
                en_reglas = True
                if valor:
                    reglas.append((clave == "allow", valor if valor.startswith(("/", "*")) else "/" + valor))
        if agentes:
            grupos.append((agentes, reglas))
        a = agente.lower()
        propias = [r for ags, r in grupos if any(x != "*" and x in a for x in ags)]
        generales = [r for ags, r in grupos if "*" in ags]
        elegidas = propias or generales
        self.reglas = [(permite, ruta, _patron(ruta)) for grupo in elegidas for permite, ruta in grupo]

    def permite(self, url: str) -> bool:
        if self.todo_prohibido:
            return False
        p = urlparse(url)
        ruta = unquote(p.path or "/") + ("?" + p.query if p.query else "")
        mejor, permitido = -1, True
        for permite, texto, patron in self.reglas:
            if patron.match(ruta):
                largo = len(texto)
                if largo > mejor or (largo == mejor and permite):
                    mejor, permitido = largo, permite
        return permitido
