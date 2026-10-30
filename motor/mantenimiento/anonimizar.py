"""Sustituye los datos de personas de unos ficheros por datos inventados, conservando formato y codificación.

Sirve para las respuestas que guardan las sondas (rama «sondas», pública) y para los ficheros de prueba:
  - nombre precedido de tratamiento («Doña María López») -> «Doña Nombre Apellido»;
  - documento de identidad («12345678Z», «***4567**») -> los dígitos pasan a 0;
  - un PDF con datos de personas se sustituye por su texto ya anonimizado (N.cuerpo -> N.cuerpo.txt).

Uso: python -m motor.mantenimiento.anonimizar carpeta/ [carpeta2/ ...]
"""

from __future__ import annotations

import gzip
import io
import re
import sys
from pathlib import Path

from motor.limpieza import RE_DESIGNADO, RE_DOCUMENTO, RE_TRATAMIENTO, _es_designado, _es_persona


def _nombre_falso(n: str) -> str:
    falso = " ".join(["Nombre", "Apellido", "Segundo"][: max(1, min(3, len(n.split())))])
    return falso.upper() if n.isupper() else falso


_MAY = "A-ZÁÉÍÓÚÑÜÇÀÈÒÏ"
_PAL_MAY = rf"[{_MAY}][{_MAY}'’-]+"
# Listas de personas en mayúsculas, «APELLIDO APELLIDO, NOMBRE» (admitidos, aprobados, tribunales)
RE_LISTA_MAYUS = re.compile(
    rf"(?<![\w&])(?P<a>{_PAL_MAY}(?:\s+(?:DE\s+LA\s+|DE\s+LOS\s+|DEL\s+|DE\s+|Y\s+|I\s+)?{_PAL_MAY}){{0,3}}),[ \t]*"
    rf"(?P<n>{_PAL_MAY}(?:[ \t]+{_PAL_MAY}){{0,2}})(?![\w])")
# Lo que en mayúsculas y con coma no es una persona («AYUNTAMIENTO DE MADRID, CONCEJALÍA…»)
RE_NO_PERSONA = re.compile(r"(?i)\b(ayuntamiento|ajuntament|concello|diputaci|deputaci|consejer|conselleria|consell|"
                           r"junta|gobierno|govern|xunta|boletin|boletín|butllet|resoluci|anuncio|anunci|orden|ordre|"
                           r"decreto|decret|ley|llei|lei|real|bases|sumario|sumari|servicio|servei|direcci|secretar|"
                           r"universidad|universitat|seccion|sección|secció|tribunal|cuerpo|escala|grupo|plaza|plazas)")
RE_CELDA_MAYUS = re.compile(r"(?P<i><t[dh]\b[^>]*>\s*)(?P<v>[^<>]{3,90}?)(?P<f>\s*</t[dh]>)")
RE_LINEA = re.compile(r"[^\n]{1,400}")
# Celdas de tabla con «Apellido Apellido, Nombre» en minúsculas
RE_CELDA_NOMBRE = re.compile(r"(?P<i><t[dh]\b[^>]*>\s*)(?P<v>[A-ZÁÉÍÓÚÑ][a-záéíóúñü'’-]+(?:\s+(?:de\s+|del\s+|de\s+la\s+)?"
                             r"[A-ZÁÉÍÓÚÑ][a-záéíóúñü'’-]+){0,3},\s*[A-ZÁÉÍÓÚÑ][a-záéíóúñü'’-]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñü'’-]+)?)"
                             r"(?P<f>\s*</t[dh]>)")
# Tratamiento y nombre con entidades HTML («do&ntilde;a Cristina Fern&aacute;ndez»)
_PAL_ENT = r"(?:[A-ZÁÉÍÓÚÑ]|&[A-Z][a-z]+;)(?:[a-záéíóúñü'’-]|&[a-z]+;)+"
RE_TRATAMIENTO_ENT = re.compile(rf"(?P<t>\b(?:[Dd]on|[Dd]o(?:&ntilde;|ñ)a|D(?:&ntilde;|ñ)a\.?)\s+)(?P<n>{_PAL_ENT}(?:\s+(?:de\s+|del\s+)?{_PAL_ENT}){{0,3}})")


def anonimizar_texto(t: str) -> tuple[str, int]:
    n = 0

    def lista(m: re.Match) -> str:
        nonlocal n
        if RE_NO_PERSONA.search(m.group(0)) or m.group(0) == "APELLIDO APELLIDO, NOMBRE":
            return m.group(0)
        n += 1
        return "APELLIDO APELLIDO, NOMBRE"

    def celda(m: re.Match) -> str:
        nonlocal n
        if RE_NO_PERSONA.search(m.group("v")):
            return m.group(0)
        n += 1
        return m.group("i") + "Apellido Apellido, Nombre" + m.group("f")

    def entidades(m: re.Match) -> str:
        nonlocal n
        if "&" not in m.group("n"):  # sin entidades lo resuelve RE_TRATAMIENTO
            return m.group(0)
        n += 1
        return m.group("t") + "Nombre Apellido"

    # «APELLIDO APELLIDO, NOMBRE» solo donde es una lista de personas: una celda de tabla entera o una línea con un
    # documento de identidad. Fuera de ahí hay demasiados títulos en mayúsculas con coma («DEPARTAMENTO DE HACIENDA,
    # INTERIOR…»).
    t = RE_CELDA_MAYUS.sub(lambda m: m.group("i") + lista(RE_LISTA_MAYUS.fullmatch(m.group("v"))) + m.group("f")
                           if RE_LISTA_MAYUS.fullmatch(m.group("v")) else m.group(0), t)
    t = RE_LINEA.sub(lambda m: RE_LISTA_MAYUS.sub(lista, m.group(0)) if RE_DOCUMENTO.search(m.group(0)) else m.group(0), t)
    t = RE_CELDA_NOMBRE.sub(celda, t)
    t = RE_TRATAMIENTO_ENT.sub(entidades, t)

    def nombre(m: re.Match) -> str:
        nonlocal n
        if not _es_persona(m):
            return m.group(0)
        n += 1
        return m.group(0)[: m.start("n") - m.start()] + _nombre_falso(m.group("n"))

    def documento(m: re.Match) -> str:
        nonlocal n
        n += 1
        return re.sub(r"\d", "0", m.group(0))

    t = RE_TRATAMIENTO.sub(nombre, t)

    def designado(m: re.Match) -> str:  # «nombrar … a Nombre Apellido como …» (sin don ni doña)
        nonlocal n
        if not _es_designado(m):
            return m.group(0)
        n += 1
        return m.group(0)[: m.start("n") - m.start()] + _nombre_falso(m.group("n")) + m.group(0)[m.end("n") - m.start():]

    for r in RE_DESIGNADO:
        t = r.sub(designado, t)
    return RE_DOCUMENTO.sub(documento, t), n


def _texto_pdf(b: bytes) -> str:
    from pypdf import PdfReader
    return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(b)).pages)


def anonimizar_fichero(f: Path) -> int:
    crudo = f.read_bytes()
    gz = f.suffix == ".gz"
    b = gzip.decompress(crudo) if gz else crudo
    if b[:4] == b"%PDF":
        try:
            texto = _texto_pdf(b)
        except Exception:  # sin pypdf o PDF ilegible: no se puede comprobar, no se conserva
            f.unlink()
            return 1
        limpio, n = anonimizar_texto(texto)
        if n:
            f.with_name(f.name + ".txt").write_text(limpio, encoding="utf-8")
            f.unlink()
        return n
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            t = b.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    nuevo, n = anonimizar_texto(t)
    if n:
        salida = nuevo.encode(enc)
        f.write_bytes(gzip.compress(salida, mtime=0) if gz else salida)
    return n


def main(argv: list[str] | None = None) -> int:
    total = 0
    for carpeta in argv if argv is not None else sys.argv[1:]:
        for f in sorted(Path(carpeta).rglob("*")):
            if f.is_file():
                n = anonimizar_fichero(f)
                if n:
                    print(f"{f}: {n} sustituciones")
                total += n
    print("Sustituciones:", total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
