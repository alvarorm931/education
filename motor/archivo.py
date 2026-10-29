"""Archivo de originales: cada descarga se guarda intacta, con su huella sha256, y nunca se borra.

Estructura: {raiz}/{fuente}/{AAAA}/{MM}/{DD}/{sha256}.{ext}[.gz]
La huella sha256 es la del contenido original; si se comprime, se guarda en gzip sin alterar el contenido.
Índice de capturas (una línea por captura): {raiz}/indice.jsonl
"""

from __future__ import annotations

import gzip
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path


class Archivo:
    def __init__(self, raiz: Path | str):
        self.raiz = Path(raiz)

    def guardar(
        self,
        fuente: str,
        fecha_ref: date,
        contenido: bytes,
        url: str,
        ext: str,
        status: int,
        cabeceras: dict[str, str] | None = None,
        comprimir: bool = True,
    ) -> dict:
        sha = hashlib.sha256(contenido).hexdigest()
        carpeta = self.raiz / fuente / f"{fecha_ref:%Y}" / f"{fecha_ref:%m}" / f"{fecha_ref:%d}"
        ruta = carpeta / (f"{sha}.{ext}.gz" if comprimir else f"{sha}.{ext}")
        sin_comprimir = carpeta / f"{sha}.{ext}"
        nuevo = not ruta.exists() and not sin_comprimir.exists()
        if nuevo:
            carpeta.mkdir(parents=True, exist_ok=True)
            ruta.write_bytes(gzip.compress(contenido, mtime=0) if comprimir else contenido)
        elif sin_comprimir.exists():
            ruta = sin_comprimir
        registro = {
            "fuente": fuente,
            "fecha_ref": fecha_ref.isoformat(),
            "url": url,
            "status": status,
            "sha256": sha,
            "bytes": len(contenido),
            "ruta": str(ruta.relative_to(self.raiz)),
            "nuevo": nuevo,
            "capturado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "cabeceras": cabeceras or {},
        }
        self.raiz.mkdir(parents=True, exist_ok=True)
        with (self.raiz / "indice.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
        return registro

    def registrar(self, fuente: str, fecha_ref: date, contenido: bytes, url: str, status: int,
                  cabeceras: dict[str, str] | None = None) -> dict:
        """Registra huella, URL y tamaño sin guardar el contenido.

        Solo para cargas históricas grandes mientras no haya almacén externo: el original se puede volver
        a pedir a la fuente y la huella permite comprobar que es el mismo.
        """
        registro = {
            "fuente": fuente,
            "fecha_ref": fecha_ref.isoformat(),
            "url": url,
            "status": status,
            "sha256": hashlib.sha256(contenido).hexdigest(),
            "bytes": len(contenido),
            "ruta": None,
            "nuevo": False,
            "solo_huella": True,
            "capturado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "cabeceras": cabeceras or {},
        }
        self.raiz.mkdir(parents=True, exist_ok=True)
        with (self.raiz / "indice.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
        return registro


def leer(ruta: Path | str) -> bytes:
    """Devuelve el contenido original de una captura, comprimida o no."""
    ruta = Path(ruta)
    datos = ruta.read_bytes()
    return gzip.decompress(datos) if ruta.suffix == ".gz" else datos
