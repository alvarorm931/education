"""Sonda de certificados: para webs que no envían la cadena completa (falta el certificado intermedio).

Para cada servidor: lee la cadena que envía (openssl s_client), busca en el certificado la dirección del emisor
(«CA Issuers» del AIA), descarga el intermedio, lo guarda en PEM y prueba a descargar las URL indicadas con
certifi + ese intermedio. Así se puede llevar el intermedio (público) al repositorio sin desactivar la
verificación.

Uso (desde GitHub, con prueba.yml):
  python -m motor.provinciales.sonda_tls --salida ruta/ --hosts host1,host2 --urls url1,url2
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import certifi
import requests

from motor.http import USER_AGENT


def cadena(host: str) -> str:
    r = subprocess.run(["openssl", "s_client", "-connect", f"{host}:443", "-servername", host, "-showcerts"],
                       input=b"", capture_output=True, timeout=30)
    return r.stdout.decode("utf-8", "replace")


def texto_certificado(pem: str) -> str:
    r = subprocess.run(["openssl", "x509", "-noout", "-text"], input=pem.encode(), capture_output=True, timeout=30)
    return r.stdout.decode("utf-8", "replace")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--hosts", default="www.diputaciodetarragona.cat,bop.dipucr.es")
    p.add_argument("--urls", default="https://www.diputaciodetarragona.cat/ebop/,https://bop.dipucr.es/")
    a = p.parse_args(argv)
    a.salida.mkdir(parents=True, exist_ok=True)
    informe, intermedios = [], []
    for host in a.hosts.split(","):
        c = cadena(host)
        (a.salida / f"{host}.cadena.txt").write_text(c, encoding="utf-8")
        pems = re.findall(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", c, re.DOTALL)
        informe.append(f"{host}: {len(pems)} certificados en la cadena enviada")
        if not pems:
            continue
        # El intermedio que falta es el emisor de algún certificado que no viene en la cadena: se sigue el AIA
        sujetos = [re.search(r"Subject: (.*)", texto_certificado(x)).group(1) for x in pems]
        pendientes = list(pems)
        vistos = set()
        while pendientes:
            t = texto_certificado(pendientes.pop(0))
            emisor = re.search(r"Issuer: (.*)", t).group(1)
            aia = re.search(r"CA Issuers - URI:(\S+)", t)
            informe.append(f"  emisor: {emisor}; AIA: {aia.group(1) if aia else '-'}")
            if emisor in sujetos or not aia or aia.group(1) in vistos:
                continue
            vistos.add(aia.group(1))
            der = requests.get(aia.group(1), headers={"User-Agent": USER_AGENT}, timeout=30).content
            pem = der.decode() if der.startswith(b"-----BEGIN") else subprocess.run(
                ["openssl", "x509", "-inform", "der", "-outform", "pem"], input=der, capture_output=True,
                timeout=30).stdout.decode()
            nombre = re.sub(r"\W+", "_", aia.group(1).rsplit("/", 1)[-1]) + ".pem"
            (a.salida / nombre).write_text(pem, encoding="utf-8")
            intermedios.append(pem)
            sub = re.search(r"Subject: (.*)", texto_certificado(pem)).group(1)
            sujetos.append(sub)
            pendientes.append(pem)
            informe.append(f"  intermedio descargado: {nombre} ({sub})")
    paquete = a.salida / "paquete.pem"
    paquete.write_text(Path(certifi.where()).read_text(encoding="utf-8") + "\n" + "\n".join(intermedios),
                       encoding="utf-8")
    for i, u in enumerate(a.urls.split(","), 1):
        try:
            r = requests.get(u, headers={"User-Agent": USER_AGENT}, timeout=40, verify=str(paquete))
            (a.salida / f"url{i}.html").write_bytes(r.content)
            informe.append(f"url{i} {r.status_code} {len(r.content)} {r.url}")
        except requests.RequestException as e:
            informe.append(f"url{i} error {e}")
    paquete.unlink()
    (a.salida / "indice.txt").write_text("\n".join(informe) + "\n", encoding="utf-8")
    print("\n".join(informe))
    return 0


if __name__ == "__main__":
    sys.exit(main())
