"""Censo de proveedores de másters: une todas las fuentes en una tabla única por dominio.

Fuentes:
  - censo del RUCT (motor/estudios/centros_ruct.py): universidades, centros propios y adscritos, centros
    extranjeros autorizados, enseñanzas artísticas superiores y Defensa, con su web;
  - catálogo SIIU (motor/estudios/catalogo.py): qué centros imparten másters oficiales;
  - Common Crawl (motor/estudios/commoncrawl.py): dominios con páginas de programa de posgrado;
  - rastreador (motor/estudios/rastreador.py): verificación en la web del propio centro.

Cada proveedor recibe un identificador propio que no cambia nunca («prov-» + 10 cifras hexadecimales de
la huella del dominio registrado con el que entró). Si cambia de dominio, se añade el nuevo a «dominios»
y el identificador se mantiene.

Estado de cada proveedor:
  - oficial: está en el RUCT (universidad o centro);
  - candidato: aparece en Common Crawl con páginas de programa y pasa los filtros de país e idioma;
  - verificado: el rastreador encontró páginas de programa en su propia web;
  - descartado: con el motivo (país, ruido, agregador, sin programas).

Uso:
  python -m motor.estudios.censo --centros ruta/centros --commoncrawl ruta/commoncrawl --salida ruta/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

# Dominios de primer nivel de países hispanohablantes distintos de España: su oferta no es la nuestra.
TLD_OTROS_PAISES = {"ar", "mx", "co", "cl", "pe", "ve", "ec", "bo", "py", "uy", "gt", "hn", "sv", "ni", "cr", "pa",
                    "do", "cu", "pr", "br", "pt", "us", "it", "fr", "de"}
TLD_GENERICOS = {"com", "net", "org", "edu", "eu", "education", "school", "academy", "online", "info", "college",
                 "university", "global", "pro", "io", "es"}
# Directorios, agregadores y medios: hablan de másters ajenos; no son proveedores.
AGREGADORES = re.compile(
    r"emagister|educaweb|mastermania|mundoposgrado|educaedu|educations|cursosycarreras|cursosgratuitos|yaq\.es|"
    r"aulaformacion|universia|blogspot|wordpress\.com|elmundo|elpais|expansion|abc\.es|20minutos|europapress|"
    r"lavanguardia|eleconomista|cincodias|magisnet|forbes|rankia|wikipedia|linkedin|facebook|youtube|"
    r"twitter|instagram|indeed|infojobs|glassdoor|tripadvisor|amazon|aliexpress|ebay|milanuncios|wallapop|"
    r"noticia|cronica|diario|periodico|revista|news|blog|portalparados|becasen|becasycursos|parainmigrantes|"
    r"psicologiaymente|que\.es$|tesify|cursosbaratos|uscflix|google\.com|github|gitlab|wuolah|wuidy|"
    r"educaformacion|estudiaradistancia|estudiaronline|universidadesni", re.I)
SUFIJOS_DOBLES = ("edu.es", "com.es", "org.es", "gob.es", "nom.es")


def dominio_registrado(url_o_host: str) -> str:
    host = urlparse(url_o_host if "://" in url_o_host else "https://" + url_o_host).netloc.lower().split(":")[0]
    host = host.removeprefix("www.")
    partes = host.split(".")
    if len(partes) >= 3 and ".".join(partes[-2:]) in SUFIJOS_DOBLES:
        return ".".join(partes[-3:])
    return ".".join(partes[-2:]) if len(partes) >= 2 else host


def id_proveedor(dominio: str) -> str:
    return "prov-" + hashlib.sha256(dominio.encode()).hexdigest()[:10]


def filtro_candidato(d: dict) -> str | None:
    """Motivo de descarte de un dominio de Common Crawl, o None si es candidato."""
    tld = (d.get("tld") or "").lower()
    if AGREGADORES.search(d["dominio"]):
        return "agregador_o_medio"
    if tld in TLD_OTROS_PAISES:
        return "otro_pais"
    if tld != "es" and tld not in TLD_GENERICOS:
        return "otro_pais"
    if tld != "es" and not any(i.startswith("spa") for i in d.get("idiomas", [])):
        return "idioma"
    if d.get("paginas", 0) < 2:
        return "una_sola_pagina"
    return None


def construir(centros: list[dict], cc: list[dict]) -> list[dict]:
    provs: dict[str, dict] = {}

    def alta(dominio: str, base: dict) -> dict:
        p = provs.get(dominio)
        if p is None:
            p = provs[dominio] = {"id": id_proveedor(dominio), "dominio": dominio, "dominios": [dominio],
                                  "nombres": [], "tipos": [], "ruct": [], "fuentes": [], "senales": {},
                                  "estado": None, "motivo": None}
        for k in ("nombres", "tipos", "fuentes"):
            for v in base.get(k, []):
                if v and v not in p[k]:
                    p[k].append(v)
        return p

    for u in centros:
        tipo_u = u.get("grupo") if u.get("grupo") != "universidad" else f"universidad_{(u.get('tipo') or '').split(' ')[0].lower()}"
        if u.get("web"):
            p = alta(dominio_registrado(u["web"]), {"nombres": [u.get("nombre")], "tipos": [tipo_u], "fuentes": ["ruct"]})
            p["ruct"].append({"universidad": u.get("codigo")})
            p["estado"] = "oficial"
        for c in u.get("centros", []):
            if not c.get("web"):
                continue
            vinc = (c.get("vinculacion") or "").lower()
            tipo_c = f"centro_{vinc}" if u.get("grupo") == "universidad" else tipo_u
            p = alta(dominio_registrado(c["web"]), {"nombres": [c.get("nombre")], "tipos": [tipo_c], "fuentes": ["ruct"]})
            p["ruct"].append({"universidad": u.get("codigo"), "centro": c.get("codigo")})
            p["estado"] = "oficial"

    for d in cc:
        motivo = filtro_candidato(d)
        dom = d["dominio"]
        if motivo and dom not in provs:
            continue
        p = alta(dom, {"fuentes": ["commoncrawl"]})
        s = p["senales"]
        s["cc_paginas"] = s.get("cc_paginas", 0) + d.get("paginas", 0)
        s["cc_ejemplos"] = (s.get("cc_ejemplos", []) + d.get("ejemplos", []))[:5]
        if p["estado"] is None:
            p["estado"] = "candidato"
    return sorted(provs.values(), key=lambda p: (p["estado"] != "oficial", -p["senales"].get("cc_paginas", 0)))


def leer_jsonl(carpeta: Path, patron: str) -> list[dict]:
    filas = []
    for f in sorted(carpeta.glob(patron)):
        filas += [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    return filas


def ejecutar(centros_dir: Path, cc_dir: Path | None, salida: Path) -> dict:
    centros = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(centros_dir.glob("[0-9][0-9][0-9].json"))]
    cc = leer_jsonl(cc_dir, "dominios_*.jsonl") if cc_dir else []
    # el mismo dominio en varios crawls: se suman páginas
    por_dom: dict[str, dict] = {}
    for d in cc:
        if not d.get("dominio"):  # hosts que son IP o sin dominio registrado
            continue
        x = por_dom.setdefault(d["dominio"], {**d, "paginas": 0, "ejemplos": []})
        x["paginas"] += d["paginas"]
        x["ejemplos"] = (x["ejemplos"] + d.get("ejemplos", []))[:8]
        x["idiomas"] = sorted(set(x.get("idiomas", [])) | set(d.get("idiomas", [])))
    provs = construir(centros, list(por_dom.values()))
    destino = salida / "datos" / "estudios" / "censo"
    destino.mkdir(parents=True, exist_ok=True)
    with (destino / "proveedores.jsonl").open("w", encoding="utf-8") as f:
        for p in provs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    descartes = Counter(filtro_candidato(d) for d in por_dom.values() if filtro_candidato(d))
    res = {"proveedores": len(provs), "por_estado": dict(Counter(p["estado"] for p in provs)),
           "tipos_oficiales": dict(Counter(t for p in provs for t in p["tipos"])),
           "dominios_commoncrawl": len(por_dom), "descartes_commoncrawl": dict(descartes)}
    (destino / "resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--centros", required=True)
    p.add_argument("--commoncrawl")
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    print(json.dumps(ejecutar(Path(a.centros), Path(a.commoncrawl) if a.commoncrawl else None, Path(a.salida)),
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
