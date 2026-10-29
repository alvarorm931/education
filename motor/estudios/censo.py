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
    r"educaformacion|estudiaradistancia|estudiaronline|universidadesni|universidadesvirtuales|mastersportal|"
    r"studyportals|topuniversities|masterstudies|findamasters|keystone|hotcourses", re.I)
# El patrón de Common Crawl es amplio a propósito (no perder escuelas). Para entrar en el censo como candidato,
# al menos una URL de ejemplo debe nombrar un programa como palabra («/master-en-x», «/mba/», «experto-
# universitario») y no ser ruido conocido («remastered», «ticketmaster», «master-plan», ramas de código).
URL_FUERTE = re.compile(
    r"(^|[/_-])m[aàá]ster(es|s)?[-_](?!(control|slave|key|keys|file|files|data|node|nodes|branch|switch|volume|boot|"
    r"card|class|plan|chef|piece|mind|cylinder|record|recording|tape|copy|bedroom|suite|bath|list|page|sheet|sword|"
    r"ball|cleanse|lock|password|bus|clock|mode|server|db|series|cup|league|edition|collection|bundle|kit|pack|"
    r"tour|race|swim|golf|tennis|chess|game|games)\b)[a-z%]{2,}|"
    r"/(m[aàá]ster(es|s)?|m%c3%a[01]ster(es)?|mba|postgrados?|posgrados?|postgraus?|masterra|mestrados?|m[aà]sters)(/|$)|"
    r"(^|[/_-])(executive-)?mba([/_-]|$)|(^|[/_-])(postgrado|posgrado|postgrau|mestrado)[-_][a-z]{3,}|"
    r"t[ií]tulos?[-_]propios?|formaci[oó]n?[-_]permanente|formacio[-_]continua|experto[-_]universitario|"
    r"especialista[-_]universitario|estudis[-_]propis|executive[-_]education|masterra[-_]|m%c3%a1ster", re.I)
URL_RUIDO = re.compile(
    r"remaster|ticketmaster|mastercard|master-?class|masterchef|scrum-?master|master-?plan|master-?rubric|"
    r"webmaster|quizmaster|paymaster|postmaster|toastmaster|grandmaster|game-?master|headmaster|"
    r"/(master|main)/(src|lib|docs?|blob|tree|raw|include|test)|\.(md|txt)$|"
    r"/(noticias?|news|blog|actualidad|actualitat|foro|forum|member|members|events?|eventos?|tag|category|"
    r"producto|product|shop|tienda)/|msc[-_ %20]+(cruises|cruceros|magnifica|ship)", re.I)
SUFIJOS_DOBLES = ("edu.es", "com.es", "org.es", "gob.es", "nom.es",
                  "co.uk", "ac.uk", "org.uk", "com.ar", "edu.ar", "org.ar", "com.mx", "edu.mx", "org.mx", "com.co",
                  "edu.co", "com.br", "edu.br", "com.pe", "edu.pe", "com.ve", "com.ec", "edu.ec", "com.uy", "edu.uy",
                  "com.py", "com.bo", "com.do", "edu.do", "com.gt", "com.pa", "com.pr", "com.au", "edu.au")
HOST_VALIDO = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$")


def dominio_registrado(url_o_host: str) -> str:
    host = urlparse(url_o_host if "://" in url_o_host else "https://" + url_o_host).netloc.lower().split(":")[0]
    host = host.removeprefix("www.")
    partes = host.split(".")
    if len(partes) >= 3 and ".".join(partes[-2:]) in SUFIJOS_DOBLES:
        return ".".join(partes[-3:])
    return ".".join(partes[-2:]) if len(partes) >= 2 else host


def web_valida(web: str | None) -> str | None:
    """La web tal como la da el registro, si es una dirección real (el RUCT trae a veces códigos o texto)."""
    if not web or not isinstance(web, str):
        return None
    w = web.strip()
    w = w if "://" in w else "https://" + w
    host = urlparse(w).netloc.lower().split(":")[0]
    return w if HOST_VALIDO.match(host) else None


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
    idiomas = {i.split(",")[0] for i in d.get("idiomas", []) if i}
    if tld != "es" and not idiomas & {"spa", "cat", "eus", "glg", "-"}:
        return "idioma"
    if tld != "es" and d.get("paginas", 0) < 2:  # un .com con una sola mención es casi siempre ruido
        return "una_sola_pagina"
    ejemplos = d.get("ejemplos") or []
    if ejemplos and not any(url_de_programa(u) for u in ejemplos):
        return "sin_url_de_programa"
    return None


def url_de_programa(url: str) -> bool:
    ruta = urlparse(url).path  # la consulta (?utm_…) no cuenta
    return bool(URL_FUERTE.search(ruta)) and not URL_RUIDO.search(ruta)


def construir(centros: list[dict], cc: list[dict]) -> list[dict]:
    provs: dict[str, dict] = {}

    def alta(dominio: str, base: dict) -> dict:
        p = provs.get(dominio)
        if p is None:
            p = provs[dominio] = {"id": id_proveedor(dominio), "dominio": dominio, "dominios": [dominio],
                                  "webs": [], "nombres": [], "tipos": [], "ruct": [], "fuentes": [], "senales": {},
                                  "estado": None, "motivo": None}
        for k in ("webs", "nombres", "tipos", "fuentes"):
            for v in base.get(k, []):
                if v and v not in p[k]:
                    p[k].append(v)
        return p

    for u in centros:
        tipo_u = u.get("grupo") if u.get("grupo") != "universidad" else f"universidad_{(u.get('tipo') or '').split(' ')[0].lower()}"
        web_u = web_valida(u.get("web"))
        if web_u:  # la web real del registro (con www. o en otro dominio), no solo el dominio registrado
            p = alta(dominio_registrado(web_u), {"webs": [web_u], "nombres": [u.get("nombre")], "tipos": [tipo_u],
                                                 "fuentes": ["ruct"]})
            p["ruct"].append({"universidad": u.get("codigo")})
            p["estado"] = "oficial"
        for c in u.get("centros", []):
            web_c = web_valida(c.get("web"))
            if not web_c:
                continue
            vinc = (c.get("vinculacion") or "").lower()
            tipo_c = f"centro_{vinc}" if u.get("grupo") == "universidad" else tipo_u
            p = alta(dominio_registrado(web_c), {"webs": [web_c], "nombres": [c.get("nombre")], "tipos": [tipo_c],
                                                 "fuentes": ["ruct"]})
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


def unir_alias(provs: list[dict], grupos: list[set[str]]) -> list[dict]:
    """Une los proveedores que son la misma web: el rastreador ve que un dominio redirige a otro
    (uab.es → uab.cat, ehu.es → ehu.eus). Se queda el identificador del principal (el de la universidad,
    o el de más referencias del RUCT) y los demás quedan en «ids_unidos» para no perder ninguna referencia."""
    por_dom = {p["dominio"]: p for p in provs}
    padre = {d: d for d in por_dom}

    def raiz(d: str) -> str:
        while padre[d] != d:
            padre[d] = padre[padre[d]]
            d = padre[d]
        return d

    for g in grupos:
        dentro = [d for d in g if d in por_dom and not AGREGADORES.search(d)]
        for d in dentro[1:]:
            padre[raiz(d)] = raiz(dentro[0])
    conjuntos: dict[str, list[dict]] = {}
    for d, p in por_dom.items():
        conjuntos.setdefault(raiz(d), []).append(p)
    salida = []
    for miembros in conjuntos.values():
        if len(miembros) == 1:
            salida.append(miembros[0])
            continue
        miembros.sort(key=lambda p: (not any("centro" not in r for r in p["ruct"]), -len(p["ruct"]),
                                     -p["senales"].get("cc_paginas", 0), p["dominio"]))
        jefe = miembros[0]
        for otro in miembros[1:]:
            for k in ("dominios", "webs", "nombres", "tipos", "fuentes"):
                jefe[k] += [v for v in otro[k] if v not in jefe[k]]
            jefe["ruct"] += [r for r in otro["ruct"] if r not in jefe["ruct"]]
            s = jefe["senales"]
            s["cc_paginas"] = s.get("cc_paginas", 0) + otro["senales"].get("cc_paginas", 0)
            s["cc_ejemplos"] = (s.get("cc_ejemplos", []) + otro["senales"].get("cc_ejemplos", []))[:5]
            jefe.setdefault("ids_unidos", []).append(otro["id"])
            if otro["estado"] == "oficial":
                jefe["estado"] = "oficial"
        salida.append(jefe)
    return sorted(salida, key=lambda p: (p["estado"] != "oficial", -p["senales"].get("cc_paginas", 0)))


def alias_de_rastreo(carpetas: list[Path]) -> list[set[str]]:
    """Grupos de dominios que el rastreador vio como una sola web (redirecciones)."""
    grupos = []
    for c in carpetas:
        for f in c.rglob("oferta_web/*.json"):
            r = json.loads(f.read_text(encoding="utf-8"))
            propios = set(r.get("dominios_propios") or [])
            if len(propios) > 1:
                grupos.append(propios)
    return grupos


def enlazados_de_rastreo(carpetas: list[Path]) -> dict[str, list[str]]:
    """Dominios enlazados desde las páginas de «centros colaboradores» o «entidades colaboradoras» de
    universidades y escuelas: así aparecen las academias que venden títulos propios ajenos y no usan
    «máster» en sus URL. Dominio → ids de los proveedores que los enlazan."""
    salida: dict[str, list[str]] = {}
    for c in carpetas:
        for f in c.rglob("oferta_web/*.json"):
            r = json.loads(f.read_text(encoding="utf-8"))
            origen = (r.get("centro") or {}).get("id")
            for dom in r.get("enlaces_colaboradores") or []:
                salida.setdefault(dom, [])
                if origen and origen not in salida[dom]:
                    salida[dom].append(origen)
    return salida


def leer_jsonl(carpeta: Path, patron: str) -> list[dict]:
    filas = []
    for f in sorted(carpeta.glob(patron)):
        filas += [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    return filas


def ejecutar(centros_dir: Path, cc_dir: Path | None, salida: Path, rastreos: list[Path] | None = None) -> dict:
    centros = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(centros_dir.glob("[0-9][0-9][0-9].json"))]
    cc = leer_jsonl(cc_dir, "dominios_*.jsonl") if cc_dir else []
    # el mismo dominio en varios crawls: se suman páginas
    por_dom: dict[str, dict] = {}
    for d in cc:
        if not d.get("dominio"):  # hosts que son IP o sin dominio registrado
            continue
        x = por_dom.setdefault(d["dominio"], {**d, "paginas": 0, "ejemplos": []})
        x["paginas"] += d["paginas"]
        # sin repetir y primero las que nombran un programa (los ejemplos de un crawl pueden ser todos del blog)
        todos = list(dict.fromkeys(x["ejemplos"] + d.get("ejemplos", [])))
        x["ejemplos"] = sorted(todos, key=lambda u: not url_de_programa(u))[:12]
        x["idiomas"] = sorted(set(x.get("idiomas", [])) | set(d.get("idiomas", [])))
    provs = construir(centros, list(por_dom.values()))
    # candidatos que entran por estar enlazados como colaboradores (aunque Common Crawl no los vea)
    ya = {d: p for p in provs for d in p["dominios"]}
    for dom, origenes in sorted(enlazados_de_rastreo(rastreos or []).items()):
        tld = dom.rsplit(".", 1)[-1]
        if dom in ya:
            ya[dom]["senales"]["colaborador_de"] = origenes
            continue
        if AGREGADORES.search(dom) or tld in TLD_OTROS_PAISES or (tld != "es" and tld not in TLD_GENERICOS):
            continue
        provs.append({"id": id_proveedor(dom), "dominio": dom, "dominios": [dom], "webs": [], "nombres": [],
                      "tipos": [], "ruct": [], "fuentes": ["colaborador"], "senales": {"colaborador_de": origenes},
                      "estado": "candidato", "motivo": None})
    antes = len(provs)
    provs = unir_alias(provs, alias_de_rastreo(rastreos or []))
    destino = salida / "datos" / "estudios" / "censo"
    destino.mkdir(parents=True, exist_ok=True)
    with (destino / "proveedores.jsonl").open("w", encoding="utf-8") as f:
        for p in provs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    descartes = Counter(filtro_candidato(d) for d in por_dom.values() if filtro_candidato(d))
    res = {"proveedores": len(provs), "por_estado": dict(Counter(p["estado"] for p in provs)),
           "tipos_oficiales": dict(Counter(t for p in provs for t in p["tipos"])),
           "dominios_commoncrawl": len(por_dom), "descartes_commoncrawl": dict(descartes),
           "unidos_por_redireccion": antes - len(provs),
           "candidatos_por_enlace_de_colaborador": sum(1 for p in provs if p["fuentes"] == ["colaborador"])}
    (destino / "resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--centros", required=True)
    p.add_argument("--commoncrawl")
    p.add_argument("--rastreo", action="append", default=[], help="carpeta con resultados del rastreador (alias)")
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    print(json.dumps(ejecutar(Path(a.centros), Path(a.commoncrawl) if a.commoncrawl else None, Path(a.salida),
                              [Path(x) for x in a.rastreo]),
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
