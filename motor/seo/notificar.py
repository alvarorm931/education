"""Avisar a los buscadores de lo que ha cambiado en cada publicación (ley SEO, regla 13).

- **IndexNow** (Bing, Yandex, Seznam, Naver, Yep y Amazon; Google no participa): las direcciones nuevas,
  cambiadas o retiradas, en tandas de 10.000 como máximo (https://www.indexnow.org/documentation). La clave es
  pública por diseño: va en `/{clave}.txt` en la raíz del sitio; se guarda como secreto `INDEXNOW_CLAVE` para no
  tenerla repetida en el código.
- **Indexing API de Google**: solo admite páginas con `JobPosting` (o vídeos en directo). Se usa para las fichas de
  procesos con plazo abierto: cuando se publica o cambia una (`URL_UPDATED`) y cuando se retira (`URL_DELETED`).
  Cupo por defecto, 200 avisos al día
  (https://developers.google.com/search/apis/indexing-api/v3/quota-pricing): primero las de plazo más corto.
  Necesita `GSC_CREDENCIALES` de una cuenta de servicio que sea propietaria de la propiedad en Search Console.

Google no necesita aviso para el resto: lee los sitemaps (con su lastmod real). El aviso por sitemap («ping») ya no
existe.

Uso: python -m motor.seo.notificar --base https://dominio.es --sitio web/ --estado-anterior a.json --estado-nuevo b.json
Sin claves, solo lista lo que avisaría.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests

INDEXNOW = "https://api.indexnow.org/indexnow"
TANDA_INDEXNOW = 10_000
CUPO_INDEXING = 200


def cambios(anterior: dict, nuevo: dict) -> dict[str, list[str]]:
    """Rutas que avisar: nuevas o cambiadas (indexables) y retiradas (ya no existen o dejan de ser indexables)."""
    salida = {"actualizadas": [], "retiradas": [], "empleo_actualizadas": [], "empleo_retiradas": []}
    for r, e in sorted(nuevo.items()):
        a = anterior.get(r)
        if e.get("indexable") and (a is None or not a.get("indexable") or a.get("huella") != e.get("huella")
                                   or a.get("lastmod") != e.get("lastmod")):
            salida["actualizadas"].append(r)
            if e.get("empleo"):
                salida["empleo_actualizadas"].append(r)
        if e.get("indexable") and a and a.get("empleo") and not e.get("empleo") and r not in salida["empleo_actualizadas"]:
            # El plazo se cerró: la página sigue, sin la oferta. Para Google es un cambio de la página (URL_UPDATED);
            # URL_DELETED es solo para páginas que desaparecen.
            salida["empleo_actualizadas"].append(r)
    for r, a in sorted(anterior.items()):
        e = nuevo.get(r)
        if a.get("indexable") and (e is None or not e.get("indexable")):
            salida["retiradas"].append(r)
            if a.get("empleo"):
                salida["empleo_retiradas"].append(r)
    return salida


def indexnow(urls: list[str], base: str, clave: str, sesion=None) -> list[int]:
    sesion = sesion or requests.Session()
    host = base.split("://", 1)[1].rstrip("/")
    codigos = []
    for i in range(0, len(urls), TANDA_INDEXNOW):
        r = sesion.post(INDEXNOW, json={"host": host, "key": clave, "keyLocation": f"{base.rstrip('/')}/{clave}.txt",
                                        "urlList": urls[i:i + TANDA_INDEXNOW]}, timeout=60)
        codigos.append(r.status_code)  # 200 o 202 = recibido
    return codigos


def indexing_api(actualizadas: list[str], retiradas: list[str], credenciales: str, cupo: int = CUPO_INDEXING):
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account

    cuenta = service_account.Credentials.from_service_account_info(
        json.loads(credenciales), scopes=["https://www.googleapis.com/auth/indexing"])
    api = AuthorizedSession(cuenta)
    resultado = []
    for url, tipo in ([(u, "URL_UPDATED") for u in actualizadas] + [(u, "URL_DELETED") for u in retiradas])[:cupo]:
        r = api.post("https://indexing.googleapis.com/v3/urlNotifications:publish", json={"url": url, "type": tipo},
                     timeout=30)
        resultado.append((url, tipo, r.status_code))
    return resultado


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Avisar a los buscadores de los cambios de una publicación")
    p.add_argument("--base", required=True)
    p.add_argument("--sitio", type=Path, required=True)
    p.add_argument("--estado-anterior", type=Path)
    p.add_argument("--estado-nuevo", type=Path, required=True)
    a = p.parse_args(argv)
    base = a.base.rstrip("/")
    anterior = json.loads(a.estado_anterior.read_text()) if a.estado_anterior and a.estado_anterior.exists() else {}
    c = cambios(anterior, json.loads(a.estado_nuevo.read_text()))
    print(json.dumps({k: len(v) for k, v in c.items()}, ensure_ascii=False))
    clave = os.environ.get("INDEXNOW_CLAVE")
    urls = [base + r for r in c["actualizadas"] + c["retiradas"]]
    if clave and urls:
        archivo = a.sitio / f"{clave}.txt"
        if not archivo.exists() or archivo.read_text(encoding="utf-8").strip() != clave:
            print(f"Falta {clave}.txt con la clave en la raíz de la web: IndexNow rechazaría el aviso")
            return 1
        print("IndexNow:", indexnow(urls, base, clave))
    credenciales = os.environ.get("GSC_CREDENCIALES")
    if credenciales and (c["empleo_actualizadas"] or c["empleo_retiradas"]):
        for fila in indexing_api([base + r for r in c["empleo_actualizadas"]],
                                 [base + r for r in c["empleo_retiradas"]], credenciales):
            print("Indexing API:", *fila)
    return 0


if __name__ == "__main__":
    sys.exit(main())
