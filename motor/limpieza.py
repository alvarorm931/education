"""Limpieza de textos oficiales: se conserva el contenido y se retiran los datos de personas.

Reglas (las mismas para todas las fuentes):
  - tabla con cabecera de datos personales (DNI, NIF, apellidos, nombre...) o con dos o más documentos
    de identidad: se guarda solo el número de filas y la cabecera;
  - párrafo con un documento de identidad o con el nombre de una persona precedido de tratamiento
    («don Antonio García», «D.ª María», «Sra. Puig»): se cuenta y no se guarda;
  - en los títulos, el nombre de la persona se sustituye por «[persona]» (nombramientos individuales);
  - el resto del texto se guarda íntegro.
Los municipios que empiezan por «Don» o «Doña» (Don Benito, Doña Mencía...) no son personas.
"""

from __future__ import annotations

import html
import re

RE_DOCUMENTO = re.compile(
    r"(\b\d{8}\s?[A-Z]\b|\b[XYZ]\d{7}\s?[A-Z]\b|\*{2,}\d{3,5}\*{1,}|\b\d{3,4}\*{3,}|\*{3,}\d{4}[A-Z]?\b|\bX{3,}\d{3,}X*)"
)
CABECERA_PERSONAL = re.compile(r"\b(dni|nif|nie|apellidos|nombre|documento|pasaporte)\b", re.IGNORECASE)
RE_BLOQUE = re.compile(r"<table\b.*?</table>|<(p|li|h\d)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
RE_FILA = re.compile(r"<tr\b.*?</tr>", re.IGNORECASE | re.DOTALL)
RE_CELDA = re.compile(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)
RE_ETIQUETA = re.compile(r"<[^>]+>")
_MAY = "A-ZÁÉÍÓÚÑÀÈÒÇ"
_PAL = rf"[{_MAY}][\w’'-]+"
RE_TRATAMIENTO = re.compile(
    rf"(?<![\w.])(?P<t>(?i:don|doña|dona|dña\.?|d\.ª|dª|d\.|sr\.|sra\.|señor|señora|senyor|senyora))\s+"
    rf"(?P<n>{_PAL}(?:\s+(?:(?:de|del|de\s+la|de\s+las|de\s+los|y|i|e)\s+)?{_PAL}){{0,5}})")


def _municipios_con_tratamiento() -> set[str]:
    try:
        import json as _json
        from pathlib import Path as _Path
        datos = _json.loads((_Path(__file__).parent / "catalogo" / "datos" / "municipios_ine_2026.json")
                            .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {n.lower() for _, n in datos["municipios"] if n.split()[0].lower() in {"don", "doña", "dona"}}


MUNICIPIOS_CON_TRATAMIENTO = _municipios_con_tratamiento()


def _es_persona(m: re.Match) -> bool:
    frase = f"{m.group('t')} {m.group('n')}".lower()
    if any(frase.startswith(x) for x in MUNICIPIOS_CON_TRATAMIENTO):
        return False
    # «D.» seguido de mayúsculas suele ser el apartado de un sumario («D. OTRAS DISPOSICIONES»), no una persona
    if m.group("t").lower() == "d." and m.group("n").split()[0].isupper():
        return False
    return True


def tiene_nombre_de_persona(texto: str) -> bool:
    return any(_es_persona(m) for m in RE_TRATAMIENTO.finditer(texto or ""))


def titulo_sin_nombres(titulo: str | None) -> str | None:
    """«... por la que se nombra Catedrático de Universidad a don Antonio García López.» ->
    «... por la que se nombra Catedrático de Universidad a [persona].»"""
    if not titulo:
        return titulo
    return RE_TRATAMIENTO.sub(lambda m: "[persona]" if _es_persona(m) else m.group(0), titulo)


def texto_de(fragmento: str) -> str:
    return " ".join(html.unescape(RE_ETIQUETA.sub(" ", fragmento)).replace("\xa0", " ").split())


def tabla(filas: list[list[str]]) -> dict:
    filas = [f for f in filas if any(f)]
    cabecera = filas[0] if filas else []
    contenido = " ".join(" ".join(f) for f in filas)
    if CABECERA_PERSONAL.search(" ".join(cabecera)) or len(RE_DOCUMENTO.findall(contenido)) >= 2:
        return {"filas": max(len(filas) - 1, 0), "cabecera": cabecera, "datos_personales": True}
    return {"filas": len(filas), "contenido": filas, "datos_personales": False}


def parrafos_seguros(parrafos: list[str]) -> tuple[list[str], int]:
    guardados, omitidos = [], 0
    for p in parrafos:
        if not p:
            continue
        if RE_DOCUMENTO.search(p) or tiene_nombre_de_persona(p):
            omitidos += 1
        else:
            guardados.append(p)
    return guardados, omitidos


def limpiar_html(fragmento_html: str) -> dict:
    """Texto, tablas y recuento de omisiones a partir de HTML de un boletín."""
    parrafos, tablas = [], []
    for m in RE_BLOQUE.finditer(fragmento_html or ""):
        bloque = m.group(0)
        if bloque[:6].lower() == "<table":
            filas = [[texto_de(c) for c in RE_CELDA.findall(f)] for f in RE_FILA.findall(bloque)]
            tablas.append(tabla(filas))
        else:
            parrafos.append(texto_de(bloque))
    guardados, omitidos = parrafos_seguros(parrafos)
    return {"texto": "\n".join(guardados), "tablas": tablas, "parrafos_omitidos_por_datos_personales": omitidos}


def con_datos_personales(limpio: dict) -> bool:
    """El original tenía datos de personas (y por eso no se guarda en el archivo público, solo su huella)."""
    return bool(limpio.get("parrafos_omitidos_por_datos_personales") or limpio.get("lineas_omitidas_por_datos_personales")
                or any(t.get("datos_personales") for t in limpio.get("tablas") or []))


RE_FIN_PARRAFO = re.compile(r"[.:;]\s*$")


def limpiar_texto(texto: str, ignorar: re.Pattern | None = None) -> dict:
    """Texto plano (p. ej. extraído de un PDF): se rehacen los párrafos uniendo las líneas, se quitan cabeceras y
    pies repetidos (`ignorar`) y se omiten las líneas con documentos de identidad y los párrafos con nombres."""
    parrafos, actual, lineas_omitidas = [], [], 0
    for linea in (texto or "").splitlines():
        lin = " ".join(linea.split())
        if not lin:
            if actual:
                parrafos.append(" ".join(actual))
                actual = []
            continue
        if ignorar is not None and ignorar.match(lin):
            continue
        if RE_DOCUMENTO.search(lin):
            lineas_omitidas += 1
            continue
        if actual and actual[-1].endswith("-") and lin[:1].islower():
            actual[-1] = actual[-1][:-1] + lin
        else:
            actual.append(lin)
        if RE_FIN_PARRAFO.search(lin):
            parrafos.append(" ".join(actual))
            actual = []
    if actual:
        parrafos.append(" ".join(actual))
    guardados, omitidos = parrafos_seguros(parrafos)
    return {"texto": "\n".join(guardados), "tablas": [], "parrafos_omitidos_por_datos_personales": omitidos,
            "lineas_omitidas_por_datos_personales": lineas_omitidas}
