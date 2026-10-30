"""Páginas de máster oficial sacadas del catálogo de másteres de cada universidad.

Para muchos títulos QEDU no da la ficha del máster sino la portada de másteres de la universidad (el mismo enlace
para decenas de títulos: «https://www.upv.es/estudios/master/index-es.html»). Esa portada los lista con enlace. Aquí
se lee la portada (y, como mucho, unas pocas páginas de listado del mismo dominio que cuelgan de ella), estática o
pintada con el navegador si no trae enlaces, y se toma cada enlace del propio dominio cuyo texto es el nombre de un
máster oficial de esa universidad que aún no tiene página (fichas_masters.comprobar_nombre: «confirmado» y un solo
máster por enlace y un solo enlace por máster). Sale una muestra para `extraer.py lote`, como las de QEDU: la
extracción vuelve a comprobar el nombre de la página contra el del RUCT.

Cortesía: robots.txt de cada servidor y una petición por segundo (rastreador.Dominio); el navegador también mira
el robots.txt de cada petición. Solo se guarda la URL de cada enlace y su texto (nada de la página).

Uso:
  python -m motor.estudios.catalogos_uni portadas --qedu carpeta [--qedu …] --catalogo catalogo.json --fichas fichas.jsonl --salida ruta/
  python -m motor.estudios.catalogos_uni leer --portadas portadas.jsonl [--navegador] --salida ruta/
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

MAX_LISTADOS = 12          # páginas de listado del mismo dominio que se siguen desde la portada
MIN_CODIGOS_PORTADA = 4    # un enlace de QEDU compartido por tantos títulos es una portada, no una ficha
RE_LISTADO = re.compile(r"(?i)m[aàá]ster|master|posgrado|postgrado|estudios|estudis|titulaci|oferta")


def portadas(qedu: list[Path], catalogo: Path, fichas: Path) -> list[dict]:
    """Portadas de másteres de cada universidad (enlace de QEDU de muchos títulos) con los másteres oficiales de esa
    universidad que no tienen página comprobada."""
    from motor.estudios.conjunto_masters import ESTADOS_WEB_OFICIAL, dominio
    from motor.estudios.extraer import _sin_seguimiento

    filas = json.loads(catalogo.read_text(encoding="utf-8"))
    cat = {t["codigo_ruct"]: t for t in filas if t.get("situacion") == "Activo"}
    con_web = set()
    for l in fichas.read_text(encoding="utf-8").split("\n"):
        if l.strip():
            f = json.loads(l)
            if f.get("grupo") == "oficial" and f.get("comprobacion_nombre") in ESTADOS_WEB_OFICIAL:
                con_web.add(f.get("codigo_ruct"))
    por_enlace: dict[str, set] = defaultdict(set)
    for c in qedu:
        for f in sorted(c.rglob("qedu_detalles_master_*.jsonl")):
            for l in f.read_text(encoding="utf-8").split("\n"):
                if l.strip():
                    d = json.loads(l)
                    e = ((d.get("detalle") or {}).get("enlace") or "").strip()
                    if e.startswith("http") and d.get("codTitula") in cat:
                        por_enlace[_sin_seguimiento(e)].add(d["codTitula"])
    out = []
    for url, cods in sorted(por_enlace.items()):
        if len(cods) < MIN_CODIGOS_PORTADA:
            continue
        # la portada es de la universidad de la mayoría de sus títulos; se buscan todos los de esa universidad
        uni = Counter(cat[c].get("universidad_codigo") for c in cods).most_common(1)[0][0]
        sin = sorted(c for c, t in cat.items() if t.get("universidad_codigo") == uni and c not in con_web)
        if sin:
            out.append({"url": url, "dominio": dominio(url), "universidad_codigo": uni,
                        "universidad": cat[sin[0]].get("universidad"),
                        "masters": [{"codigo_ruct": c, "nombre": cat[c].get("nombre_oficial")} for c in sin]})
    # una universidad con varias portadas: todas, cada una con la lista entera (se empareja una vez al final)
    return out


def paginas_qedu_sin_ficha(qedu: list[Path], catalogo: Path, fichas: Path, capturadas: list[Path]) -> list[dict]:
    """La página que QEDU da para un máster sin ficha (de uno a tres títulos) cuando no era la del programa (una
    página de facultad, de departamento…): de ella cuelga muchas veces la del máster. Se lee sin seguir listados."""
    from motor.estudios.conjunto_masters import ESTADOS_WEB_OFICIAL, dominio
    from motor.estudios.extraer import _sin_seguimiento

    cat = {t["codigo_ruct"]: t for t in json.loads(catalogo.read_text(encoding="utf-8")) if t.get("situacion") == "Activo"}
    con_web = {f.get("codigo_ruct") for f in (json.loads(l) for l in fichas.read_text(encoding="utf-8").split("\n") if l.strip())
               if f.get("grupo") == "oficial" and f.get("comprobacion_nombre") in ESTADOS_WEB_OFICIAL}
    no_programa = set()
    for c in capturadas:
        for f in sorted(c.rglob("paginas_extraidas.jsonl")):
            for l in f.read_text(encoding="utf-8").split("\n"):
                if l.strip():
                    x = json.loads(l)
                    if x.get("no_es_programa"):
                        no_programa.add(x["url"])
    por_enlace: dict[str, set] = defaultdict(set)
    for c in qedu:
        for f in sorted(c.rglob("qedu_detalles_master_*.jsonl")):
            for l in f.read_text(encoding="utf-8").split("\n"):
                if l.strip():
                    d = json.loads(l)
                    e = _sin_seguimiento(((d.get("detalle") or {}).get("enlace") or "").strip())
                    if e.startswith("http") and d.get("codTitula") in cat and d["codTitula"] not in con_web:
                        por_enlace[e].add(d["codTitula"])
    out = []
    for url, cods in sorted(por_enlace.items()):
        if len(cods) >= MIN_CODIGOS_PORTADA or url not in no_programa:
            continue
        uni = cat[sorted(cods)[0]].get("universidad_codigo")
        out.append({"url": url, "dominio": dominio(url), "universidad_codigo": uni, "seguir": False,
                    "universidad": cat[sorted(cods)[0]].get("universidad"),
                    "masters": [{"codigo_ruct": c, "nombre": cat[c].get("nombre_oficial")} for c in sorted(cods)]})
    return out


def _slug(url: str) -> str:
    return " ".join(re.split(r"[-_/.]+", urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]))


def emparejar(enlaces: list[tuple[str, str]], masters: list[dict]) -> tuple[list[dict], Counter]:
    """Un enlace por máster: el que lo nombra («confirmado») y no nombra a otro igual de bien."""
    from motor.estudios.fichas_masters import comprobar_nombre

    cuentas = Counter()
    mejor: dict[str, tuple] = {}
    for url, texto in enlaces:
        resultados = []
        for m in masters:
            for t in (texto, _slug(url)):
                estado, cob = comprobar_nombre(m["nombre"], t)
                if estado == "confirmado":
                    resultados.append((cob, m["codigo_ruct"]))
                    break
        if not resultados:
            continue
        resultados.sort(reverse=True)
        if len(resultados) > 1 and resultados[0][0] == resultados[1][0]:
            cuentas["enlace_ambiguo"] += 1
            continue
        cob, cod = resultados[0]
        if cod not in mejor or cob > mejor[cod][0]:
            mejor[cod] = (cob, url)
    filas = [{"url": u, "grupo": "oficial", "codigo_ruct": c, "codigos_ruct": [c], "estado_emparejado": "catalogo_universidad",
              "pagina": "principal", "cobertura_nombre": cob} for c, (cob, u) in sorted(mejor.items())]
    # dos másters a la misma página: no se sabe de cuál es
    por_url = Counter(f["url"] for f in filas)
    cuentas["misma_pagina_varios"] = sum(1 for f in filas if por_url[f["url"]] > 1)
    return [f for f in filas if por_url[f["url"]] == 1], cuentas


def leer(portadas_: list[dict], navegador: bool = False, max_minutos: float = 50) -> tuple[list[dict], dict]:
    from motor.estudios.conjunto_masters import dominio
    from motor.estudios.rastreador import Dominio, enlaces

    fin = time.time() + max_minutos * 60
    nav = None
    cuentas = Counter()
    por_uni: dict[str, dict] = {}
    for p in portadas_:
        u = por_uni.setdefault(p["universidad_codigo"], {"masters": {m["codigo_ruct"]: m for m in p["masters"]},
                                                         "enlaces": {}, "dominios": set(), "portadas": []})
        u["masters"].update({m["codigo_ruct"]: m for m in p["masters"]})
        u["dominios"].add(p["dominio"])
        u["portadas"].append(p["url"])
        u.setdefault("sin_listados", set())
        if p.get("seguir") is False:  # la página del máster en QEDU (no una portada): sin seguir listados
            u["sin_listados"].add(p["url"])
    for uni, u in sorted(por_uni.items()):
        for portada in u["portadas"]:
            if time.time() > fin:
                cuentas["sin_tiempo"] += 1
                break
            d = Dominio(portada, None, pausa=1.0, max_peticiones=MAX_LISTADOS + 3)
            pendientes, vistas = [portada], set()
            while pendientes and len(vistas) <= MAX_LISTADOS and time.time() < fin:
                url = pendientes.pop(0)
                if url in vistas:
                    continue
                vistas.add(url)
                html = None
                r = d.get(url, guardar=False)
                if r is not None and r.status_code == 200 and "html" in (r.headers.get("content-type") or ""):
                    html = r.text
                    cuentas["portadas_estaticas"] += 1
                ls = enlaces(html, url) if html else []
                propios = [(h, t) for h, t in ls if dominio(h) in u["dominios"]]
                if navegador and len(propios) < 15:
                    try:
                        nav = nav or __import__("motor.estudios.extraer", fromlist=["Navegador"]).Navegador()
                        pintada = nav.html(url)
                    except Exception:  # noqa: BLE001 - sin navegador se sigue con lo estático
                        pintada = None
                    if pintada:
                        cuentas["portadas_pintadas"] += 1
                        ls = enlaces(pintada, url)
                        propios = [(h, t) for h, t in ls if dominio(h) in u["dominios"]]
                for h, t in propios:
                    u["enlaces"].setdefault(h.rstrip("/"), t)
                    # listados que cuelgan de la portada (por rama, por facultad, página 2…)
                    if url == portada and portada not in u["sin_listados"] and h not in vistas and RE_LISTADO.search(h + " " + t) and \
                            len(pendientes) < MAX_LISTADOS and urlparse(h).path.count("/") <= urlparse(portada).path.count("/") + 2:
                        pendientes.append(h)
            cuentas["paginas_leidas"] += len(vistas)
    filas = []
    for uni, u in sorted(por_uni.items()):
        f, c = emparejar(list(u["enlaces"].items()), list(u["masters"].values()))
        cuentas.update(c)
        cuentas["universidades"] += 1
        cuentas["enlaces_vistos"] += len(u["enlaces"])
        filas += [{**x, "universidad_codigo": uni} for x in f]
    cuentas["masters_con_pagina"] = len(filas)
    if nav is not None:
        try:
            nav.cerrar()
        except Exception:  # noqa: BLE001
            pass
    return filas, dict(cuentas)


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="orden", required=True)
    a = sub.add_parser("portadas")
    a.add_argument("--qedu", action="append", default=[])
    a.add_argument("--catalogo", required=True)
    a.add_argument("--fichas", required=True)
    a.add_argument("--capturadas", action="append", default=[],
                   help="carpetas de extracción: añade las páginas de QEDU de un máster que no eran la del programa")
    b = sub.add_parser("leer")
    b.add_argument("--portadas", required=True)
    b.add_argument("--navegador", action="store_true")
    b.add_argument("--max-minutos", type=float, default=50)
    for s in (a, b):
        s.add_argument("--salida", required=True)
    x = p.parse_args()
    destino = Path(x.salida) / "datos" / "estudios" / "extraccion" / "catalogos_universidad"
    destino.mkdir(parents=True, exist_ok=True)
    if x.orden == "portadas":
        filas = portadas([Path(q) for q in x.qedu], Path(x.catalogo), Path(x.fichas))
        if x.capturadas:
            filas += paginas_qedu_sin_ficha([Path(q) for q in x.qedu], Path(x.catalogo), Path(x.fichas),
                                            [Path(c) for c in x.capturadas])
        (destino / "portadas.jsonl").write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in filas), encoding="utf-8")
        print(json.dumps({"portadas": len(filas), "masters": sum(len(f["masters"]) for f in filas)}, ensure_ascii=False))
    else:
        filas, cuentas = leer([json.loads(l) for l in Path(x.portadas).read_text(encoding="utf-8").split("\n") if l.strip()],
                              x.navegador, x.max_minutos)
        (destino / "oficiales_catalogo.jsonl").write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in filas),
                                                          encoding="utf-8")
        (destino / "resumen.json").write_text(json.dumps(cuentas, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(cuentas, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
