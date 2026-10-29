"""Censo de centros del RUCT: todas las universidades y grupos de centros, y cada centro con su ficha.

El RUCT agrupa los centros bajo «universidades» (código de 3 cifras). Además de las universidades hay
grupos que no lo son: centros autorizados para impartir Enseñanzas Artísticas Superiores (099), centros
dependientes del Ministerio de Defensa (086), centros extranjeros autorizados por cada comunidad (091 Madrid,
093 Andalucía, 095 País Vasco, 096 C. Valenciana, 101 Cataluña, 092 Cantabria, 105 Aragón) y «Otros
centros de nivel universitario» (000).

De cada universidad: tipo, CIF, ánimo de lucro, administración responsable, sede, web.
De cada centro: código de 8 cifras, tipo, calificación jurídica, vinculación (propio o adscrito), domicilio,
municipio, provincia, comunidad y web.

Uso:
  python -m motor.estudios.centros_ruct --salida ruta/                       # todo
  python -m motor.estudios.centros_ruct --universidades 025,033 --salida ruta/
  python -m motor.estudios.centros_ruct --desde 0 --hasta 60 --salida ruta/  # por tramos (orden de la lista)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from motor.archivo import Archivo
from motor.estudios.ruct import BASE, CITA, Lector, _txt, campos

URL_LISTA = BASE + "consultauniversidades?actual=universidades"
URL_UNIV = BASE + "universidad.action?codigoUniversidad={u}&actual=universidades"
URL_CENTROS = BASE + "universidadcentros.action?codigoUniversidad={u}&actual=universidades"
URL_CENTRO = BASE + "centro.action?codigoUniversidad={u}&codigoCentro={c}&actual=centros"

GRUPOS_NO_UNIVERSITARIOS = {
    "000": "otros_centros_nivel_universitario",
    "086": "defensa",
    "099": "ensenanzas_artisticas_superiores",
    "091": "extranjero_autorizado", "092": "extranjero_autorizado", "093": "extranjero_autorizado",
    "095": "extranjero_autorizado", "096": "extranjero_autorizado", "101": "extranjero_autorizado",
    "105": "extranjero_autorizado",
}


def lista_universidades(pagina: str) -> list[dict]:
    """Opciones del desplegable de universidades (código de 3 cifras y nombre)."""
    m = re.search(r'(?is)<select[^>]*name="codigoUniversidad"[^>]*>(.*?)</select>', pagina)
    if not m:
        return []
    salida = []
    for codigo, nombre in re.findall(r'(?is)<option value="(\d{3})"[^>]*>(.*?)</option>', m.group(1)):
        salida.append({"codigo": codigo, "nombre": _txt(nombre),
                       "grupo": GRUPOS_NO_UNIVERSITARIOS.get(codigo, "universidad")})
    return salida


def _ficha(pagina: str) -> dict:
    c = campos(pagina)
    return {k: (v if v != "" else None) for k, v in c.items()}


def parsear_universidad(pagina: str) -> dict:
    c = _ficha(pagina)
    return {
        "acronimo": c.get("acronimo"), "tipo": c.get("tipo"), "cif": c.get("cif"),
        "animo_de_lucro": c.get("con_animo_de_lucro"),
        "administracion": c.get("administracion_educativa_responsable"),
        "domicilio": c.get("domicilio"), "codigo_postal": c.get("codigo_postal"), "municipio": c.get("municipio"),
        "provincia": c.get("provincia"), "comunidad": c.get("comunidad_autonoma"),
        "web": _web(c.get("url")), "correo": c.get("e_mail"), "telefono": c.get("telefono_1"),
        "norma_creacion": {k: c.get(k) for k in ("tipo_boletin", "tipo_disposicion", "fecha_disposicion", "fecha_publicacion")},
    }


def parsear_centro(pagina: str) -> dict:
    c = _ficha(pagina)
    return {
        "tipo_centro": c.get("tipo_de_centro"), "calificacion": c.get("calificacion_juridica"),
        "vinculacion": c.get("naturaleza_vinculacion"),
        "domicilio": c.get("domicilio"), "codigo_postal": c.get("codigo_postal"), "localidad": c.get("localidad"),
        "municipio": c.get("municipio"), "provincia": c.get("provincia"), "comunidad": c.get("comunidad_autonoma"),
        "web": _web(c.get("url")), "telefono": c.get("telefono_1"),
    }


def _web(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    return url if url.startswith("http") else "https://" + url.lstrip("/")


def centros_de_lista(pagina: str) -> list[dict]:
    """Centros enlazados en la lista de una universidad: código y nombre."""
    vistos, salida = set(), []
    for m in re.finditer(r'(?is)<a[^>]*href="[^"]*centro\.action[^"]*codigoCentro=(\w+)[^"]*"[^>]*>(.*?)</a>', pagina):
        cod, nombre = m.group(1), _txt(m.group(2))
        if cod not in vistos:
            vistos.add(cod)
            salida.append({"codigo": cod, "nombre": nombre or None})
    return salida


def paginas_siguientes(pagina: str) -> list[str]:
    """Enlaces de paginación (displaytag): parámetro d-NNN-p."""
    enlaces = re.findall(r'href="([^"]*d-\d+-p=\d+[^"]*)"', pagina)
    return sorted({e.replace("&amp;", "&") for e in enlaces})


def ejecutar(raiz: Path, codigos: list[str] | None, desde: int, hasta: int | None, max_minutos: float) -> dict:
    archivo = Archivo(raiz / "archivo")
    lector = Lector(archivo)
    destino = raiz / "datos" / "estudios" / "centros"
    destino.mkdir(parents=True, exist_ok=True)
    fin = time.time() + max_minutos * 60
    estado, pagina, _ = lector.get(URL_LISTA)
    if estado != 200:
        return {"alerta": f"RUCT no responde (estado {estado})"}
    todas = lista_universidades(pagina)
    if not todas:
        return {"alerta": "lista de universidades vacía: posible cambio de formato"}
    elegidas = [u for u in todas if u["codigo"] in codigos] if codigos else todas[desde:hasta]
    (destino / "lista_universidades.json").write_text(json.dumps(todas, ensure_ascii=False, indent=1), encoding="utf-8")
    hechos, centros_total, fallos = 0, 0, []
    ahora = lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    for u in elegidas:
        if time.time() > fin:
            break
        registro = dict(u)
        est, p, _ = lector.get(URL_UNIV.format(u=u["codigo"]))
        if est == 200:
            registro.update(parsear_universidad(p))
        # lista de centros, con todas sus páginas
        centros, cola, vistas = [], [URL_CENTROS.format(u=u["codigo"])], set()
        while cola and time.time() < fin:
            url = cola.pop(0)
            if url in vistas:
                continue
            vistas.add(url)
            est, p, _ = lector.get(url)
            if est != 200:
                fallos.append(url)
                continue
            for c in centros_de_lista(p):
                if c["codigo"] not in {x["codigo"] for x in centros}:
                    centros.append(c)
            for sig in paginas_siguientes(p):
                if not re.search(r"d-\d+-[os]=", sig):
                    cola.append(re.sub(r";jsessionid=\w+", "", urljoin(url, sig)))
        for c in centros:
            if time.time() > fin:
                break
            est, p, _ = lector.get(URL_CENTRO.format(u=u["codigo"], c=c["codigo"]))
            if est == 200:
                c.update(parsear_centro(p))
            else:
                fallos.append(c["codigo"])
            c["fuente"] = {"cita": CITA, "url": URL_CENTRO.format(u=u["codigo"], c=c["codigo"]), "capturado": ahora()}
        registro["centros"] = centros
        registro["fuente"] = {"cita": CITA, "url": URL_UNIV.format(u=u["codigo"]), "capturado": ahora()}
        (destino / f"{u['codigo']}.json").write_text(json.dumps(registro, ensure_ascii=False, indent=1), encoding="utf-8")
        hechos += 1
        centros_total += len(centros)
    return {"universidades_en_lista": len(todas), "pedidas": len(elegidas), "hechas": hechos,
            "centros": centros_total, "fallos": len(fallos), "peticiones": lector.peticiones}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--universidades")
    p.add_argument("--desde", type=int, default=0)
    p.add_argument("--hasta", type=int)
    p.add_argument("--max-minutos", type=float, default=27)
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    codigos = [c.strip() for c in a.universidades.split(",")] if a.universidades else None
    res = ejecutar(Path(a.salida), codigos, a.desde, a.hasta, a.max_minutos)
    print(json.dumps(res, ensure_ascii=False))
    if res.get("alerta"):
        print("ALERTA " + res["alerta"], file=sys.stderr)


if __name__ == "__main__":
    main()
