"""Archivo de originales: cada descarga se guarda intacta, con su huella sha256, y nunca se borra.

Estructura: {raiz}/{fuente}/{AAAA}/{MM}/{DD}/{sha256}.{ext}
Índice de capturas (una línea por captura): {raiz}/indice.jsonl
"""

from __future__ import annotations

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
    ) -> dict:
        sha = hashlib.sha256(contenido).hexdigest()
        carpeta = self.raiz / fuente / f"{fecha_ref:%Y}" / f"{fecha_ref:%m}" / f"{fecha_ref:%d}"
        ruta = carpeta / f"{sha}.{ext}"
        nuevo = not ruta.exists()
        if nuevo:
            carpeta.mkdir(parents=True, exist_ok=True)
            ruta.write_bytes(contenido)
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
