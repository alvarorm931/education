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

from motor.limpieza import RE_DOCUMENTO, RE_TRATAMIENTO, _es_persona


def _nombre_falso(n: str) -> str:
    falso = " ".join(["Nombre", "Apellido", "Segundo"][: max(1, min(3, len(n.split())))])
    return falso.upper() if n.isupper() else falso


def anonimizar_texto(t: str) -> tuple[str, int]:
    n = 0

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
