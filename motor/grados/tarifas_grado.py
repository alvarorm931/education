"""Precios de grado en los PDF de tarifas de las universidades privadas, sin IA.

Muchas privadas no ponen el precio en la página del grado pero publican un PDF de precios del curso (lo encuentra
web_privadas.py al leer las páginas de grado: «pdf_precio»). Aquí:

1. se eligen los PDF que por su dirección son de precios (precio, tasas, tarifas, fees, abono…) y no de otra cosa
   (guías docentes, indicadores, normativa);
2. se descargan con el lector cortés (robots.txt, una petición por segundo); el original va al archivo (almacén
   privado en GitHub Actions) con su huella;
3. se extrae el texto (pypdf) y se buscan las líneas con un importe en euros; cada línea se une con un grado de esa
   universidad si contiene todas las palabras de su nombre (o la línea anterior, cuando el importe va solo);
4. el tipo del importe (curso, crédito, total, reserva, mensual) sale de la propia línea o de la última línea de
   rótulos del documento («Precio por curso», «Reserva de plaza»…).

Lo público lleva grado, importe, tipo, curso del documento, URL del PDF y huella de la línea; no el texto.
La muestra de líneas con importe (para revisar el formato) solo se guarda en local (MOTOR_MUESTRA=1).

Uso:
  python -m motor.grados.tarifas_grado --catalogo …/catalogo.jsonl --rastreos carpeta_web_privadas --salida ruta/
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.grados.generico import nombre_base
from motor.grados.web_privadas import IMPORTE, RANGO, TIPO_IMPORTE, palabras, tipo_cercano, valor_importe

FUENTE = "web-centros"
ES_TARIFA = re.compile(r"precio|tasa|tarifa|fees?\b|abono|honorari|coste|importe|matr[ií]cula", re.I)
NO_TARIFA = re.compile(r"gu[ií]a-?docente|indicador|satisfacc|normativa|permanencia|pol[ií]tica-productos|"
                       r"asignatura|memoria|calendario|research\.|portalcientifico|investigador|/financiaciones|"
                       r"blog|/revista/|sala-de-prensa|noticia|/tags?/|formacion-profesional|ciclos?-formativ|"
                       r"master|posgrado|postgrado|/(?:int|pe|mx|co|ec|cl|ar|us|uk|it|fr|pt|br)/", re.I)  # otros países
CURSO_DOC = re.compile(r"\b(20[2-3]\d)\s*[-/–]\s*(?:20)?([2-3]\d)\b")
MAX_PDF = 12_000_000
MAX_LINEA_MUESTRA = 160
# Líneas literales de muestra para revisar el formato: solo en local (MOTOR_MUESTRA=1); la rama pública no lleva
# texto de terceros (docs/estrategia-informacion-cerrada.md §2.4)
MUESTRA = os.environ.get("MOTOR_MUESTRA") == "1"


def elegir_cc(carpeta: Path | None, ya: set[str]) -> list[dict]:
    """URL de precios halladas en el índice de Common Crawl (cc_precios.py) que no se han elegido ya."""
    salida = []
    if not carpeta:
        return salida
    for f in sorted(carpeta.rglob("cc_precios/urls_*.jsonl")):
        for linea in f.read_text(encoding="utf-8").splitlines():
            x = json.loads(linea)
            u = x["url"]
            if u in ya or not x.get("codigo") or NO_TARIFA.search(u):
                continue
            ya.add(u)
            salida.append({"universidad": x.get("universidad"), "codigo_universidad": x["codigo"], "web": x.get("web"),
                           "url": u, "origen": "common_crawl"})
    return salida


def elegir(rastreos: Path) -> list[dict]:
    """PDF de precios citados en las páginas de grado y páginas de precios del sitemap de cada universidad
    (sin repetir URL)."""
    vistos, salida = set(), []
    for f in sorted(rastreos.rglob("web_privadas/[0-9]*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for origen, urls in (("pdf_de_pagina_de_grado", d.get("pdf_precio") or []),
                             ("pagina_de_precios", d.get("urls_precio") or [])):
            for url in urls:
                if url in vistos or origen == "pdf_de_pagina_de_grado" and (not ES_TARIFA.search(url) or NO_TARIFA.search(url)):
                    continue
                vistos.add(url)
                salida.append({"universidad": d.get("universidad"), "codigo_universidad": d.get("codigo"),
                               "web": d.get("web"), "url": url, "origen": origen})
    return salida


BLOQUE = re.compile(r"(?is)</(?:p|li|h[1-6]|div|section|article|dt|dd|caption|table)>|<br\s*/?>")


def lineas_html(html: str) -> list[str]:
    """Texto visible de una página en líneas: una por párrafo o elemento de lista y una por fila de tabla, con las
    celdas separadas por « | » (para leer cada importe con el rótulo de su columna)."""
    texto = re.sub(r"(?is)<(script|style|noscript|svg|head)\b.*?</\1>", " ", html)
    texto = re.sub(r"(?is)</t[dh]>", " | ", texto)
    texto = re.sub(r"(?is)</tr>", "\n", texto)
    texto = BLOQUE.sub("\n", texto)
    texto = re.sub(r"<[^>]+>", " ", texto)
    import html as _html

    texto = _html.unescape(texto)
    salida = []
    for linea in texto.split("\n"):
        linea = " ".join(linea.split()).strip(" |")
        if linea:
            salida.append(linea)
    return salida


def texto_pdf(contenido: bytes) -> list[str]:
    from pypdf import PdfReader

    lector = PdfReader(io.BytesIO(contenido))
    return [(p.extract_text() or "") for p in lector.pages]


def objetivos(g: dict) -> list[set[str]]:
    if g["clase"] == "doble" and g.get("componentes"):
        return [set().union(*(palabras(nombre_base(c["nombre"])) for c in g["componentes"]))]
    salida = [palabras(nombre_base(g["nombre"]))]
    for parte in g["nombre"].split(" / ")[1:]:
        salida.append(palabras(parte) - {"bachelor", "degree", "in", "of", "and", "the"})
    return [o for o in salida if o]


def grado_de(linea: str, grados: list[dict]) -> str | None:
    """El grado cuyo nombre entero está en la línea; entre varios, el de nombre más largo (el más concreto).
    Los dobles exigen «doble» en la línea y los simples no tenerlo."""
    pl = palabras(linea)
    doble = bool(re.search(r"\bdobles?\b|\bdoble titulaci|\bPCEO\b|\s\+\s", linea, re.I))
    mejores = []
    for g in grados:
        if (g["clase"] == "doble") != doble:
            continue
        for o in objetivos(g):
            if o <= pl:
                mejores.append((len(o), g["codigo"]))
                break
    if not mejores:
        return None
    mejores.sort(reverse=True)
    if len(mejores) > 1 and mejores[0][0] == mejores[1][0]:
        return None  # dos grados igual de concretos en la misma línea: no se sabe de cuál es el importe
    return mejores[0][1]


def tipo_rotulo(texto: str) -> str | None:
    for tipo, patron in TIPO_IMPORTE:
        if patron.search(texto):
            return tipo
    return None


def grado_de_url(url: str, grados: list[dict]) -> str | None:
    """El grado al que pertenece una página de precios por su dirección («…/grado-gastronomia/precios»)."""
    from motor.grados.web_privadas import unir

    union = unir(grados, [re.sub(r"/(?:precios?|tasas|tarifas?|honorarios|admisiones?[-\w]*|financiacion|"
                                 r"precios-becas-ayudas|becas[-\w]*)/?$", "/", url)])
    return next(iter(union)) if len(union) == 1 else None


def extraer(paginas: list[str], grados: list[dict], de_la_pagina: str | None = None) -> dict:
    """Importes por grado de un PDF o una página de precios (una cadena por página, con saltos de línea; en las
    tablas HTML las celdas van separadas por « | » y cada importe toma el tipo del rótulo de su columna)."""
    precios: dict[str, list] = defaultdict(list)
    con_importe, muestra, previa, rotulo = 0, [], "", None
    curso, cabecera = None, None
    bloque, ultimo = 0, None
    for n, pagina in enumerate(paginas, 1):
        if not curso and (m := CURSO_DOC.search(pagina)):
            curso = f"{m.group(1)}-20{m.group(2)}"
        for linea in (x.strip() for x in pagina.split("\n")):
            if not linea:
                continue
            hallados = list(IMPORTE.finditer(linea))
            celdas = [c.strip() for c in linea.split(" | ")]
            if not hallados:
                if len(celdas) >= 2 and any(tipo_rotulo(c) for c in celdas):
                    cabecera = celdas
                if tipo_rotulo(linea) and len(linea) < 120:
                    rotulo = tipo_rotulo(linea)
                if re.search(r"[A-Za-zÁÉÍÓÚáéíóú]{4}", linea):
                    previa = linea
                continue
            con_importe += 1
            texto_sin = IMPORTE.sub(" ", linea)
            codigo = grado_de(linea, grados)
            if codigo:
                bloque += 1  # cada línea con nombre de grado abre un bloque; las de solo cifras que siguen, también suyas
            elif not re.search(r"[A-Za-zÁÉÍÓÚáéíóú]{4}", texto_sin):
                codigo = grado_de(previa, grados)
                if codigo and codigo != ultimo:
                    bloque += 1
            if not codigo and de_la_pagina:
                codigo = de_la_pagina  # página de precios de un solo grado: sus cifras son de ese grado
            ultimo = codigo or ultimo
            if MUESTRA and len(muestra) < 60 and re.search(r"grado|doble|bachelor|degree", linea + " " + previa, re.I):
                muestra.append(linea[:MAX_LINEA_MUESTRA])  # solo en pruebas locales: en sondas no va texto ajeno
            if not codigo:
                continue
            for k, m in enumerate(hallados):
                valor = valor_importe(m)
                antes = linea[hallados[k - 1].end() if k else 0:m.start()]
                despues = linea[m.end():hallados[k + 1].start() if k + 1 < len(hallados) else len(linea)]
                tipo = None
                if cabecera and len(celdas) == len(cabecera):  # columna de la tabla con su rótulo
                    j = linea[:m.start()].count(" | ")
                    tipo = tipo_rotulo(cabecera[j]) if j < len(cabecera) else None
                tipo = tipo or tipo_cercano(antes[-60:], despues[:40]) or (rotulo if len(hallados) == 1 else None)
                bajo, alto = RANGO.get(tipo, (1, 0)) if tipo else (1, 0)
                precios[codigo].append({"valor": valor, "tipo": tipo, "verosimil": bool(tipo) and bajo <= valor <= alto,
                                        "pagina": n, "bloque": bloque,
                                        "linea_sha256": hashlib.sha256(linea.encode()).hexdigest()[:16]})
    return {"curso_documento": curso, "lineas_con_importe": con_importe, "grados": dict(precios), "muestra": muestra}


def ejecutar(catalogo: list[dict], rastreos: Path, salida: Path, max_minutos: float = 50,
             cc: Path | None = None) -> dict:
    from motor.estudios.rastreador import Dominio

    archivo = Archivo(salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    destino = salida / "datos" / "estudios" / "grados" / "tarifas_grado"
    destino.mkdir(parents=True, exist_ok=True)
    por_u: dict[str, list] = defaultdict(list)
    for t in catalogo:
        if t["situacion"] == "Activo" and t["clase"] in ("grado", "doble"):
            for u in t["universidades"]:
                if u["tipo"] == "Privada" and u.get("codigo"):
                    por_u[u["codigo"]].append(t)
    fin = time.time() + max_minutos * 60
    resultados, dominios = [], {}
    elegidos = elegir(rastreos)
    elegidos += elegir_cc(cc, {p["url"] for p in elegidos})
    for p in elegidos:
        if time.time() > fin:
            break
        r_url = p["url"]
        host = re.sub(r"^https?://([^/]+).*$", r"\1", r_url)
        d = dominios.setdefault(host, Dominio("https://" + host, archivo, pausa=1.0, max_peticiones=40))
        r = d.get(r_url, guardar=False)
        res = {**p, "estado": r.status_code if r is not None else None, "capturado": date.today().isoformat()}
        es_pdf = r is not None and r.content[:4] == b"%PDF"
        es_html = r is not None and "html" in (r.headers.get("content-type") or "")
        if r is not None and r.status_code == 200 and len(r.content) <= MAX_PDF and (es_pdf or es_html):
            archivo.guardar(FUENTE, date.today(), r.content, r_url, "pdf" if es_pdf else "html", r.status_code,
                            {k: v for k, v in r.headers.items() if k.lower() in {"content-type", "last-modified"}})
            res["sha256"] = hashlib.sha256(r.content).hexdigest()
            res["formato"] = "pdf" if es_pdf else "html"
            try:
                paginas = texto_pdf(r.content) if es_pdf else ["\n".join(lineas_html(r.text))]
                res["paginas"] = len(paginas)
                gs = por_u.get(p["codigo_universidad"], [])
                res.update(extraer(paginas, gs, None if es_pdf else grado_de_url(r_url, gs)))
            except Exception as e:  # noqa: BLE001 - un documento roto no para el resto
                res["error"] = f"{type(e).__name__}: {str(e)[:120]}"
        elif r is not None and r.status_code == 200:
            res["error"] = "formato_no_leido_o_demasiado_grande"
        resultados.append(res)
    with (destino / "tarifas.jsonl").open("w", encoding="utf-8") as f:
        for x in resultados:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    resumen = {
        "pdfs_elegidos": len(resultados),
        "por_origen": {o: sum(1 for x in resultados if x.get("origen") == o) for o in
                       ("pdf_de_pagina_de_grado", "pagina_de_precios", "common_crawl")},
        "leidos": sum(1 for x in resultados if x.get("paginas")),
        "con_algun_grado": sum(1 for x in resultados if x.get("grados")),
        "grados_con_importe": len({c for x in resultados for c in (x.get("grados") or {})}),
        "grados_con_importe_verosimil": len({c for x in resultados for c, v in (x.get("grados") or {}).items()
                                             if any(i["verosimil"] for i in v)}),
        "por_universidad": dict(sorted(
            {u: len({c for x in resultados if x["universidad"] == u for c in (x.get("grados") or {})})
             for u in {x["universidad"] for x in resultados}}.items(), key=lambda kv: -kv[1])),
    }
    (destino / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    return resumen


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--catalogo", required=True)
    p.add_argument("--rastreos", required=True, help="carpeta con …/web_privadas/{código}.json")
    p.add_argument("--cc", help="carpeta con …/cc_precios/urls_*.jsonl (cc_precios.py)")
    p.add_argument("--max-minutos", type=float, default=50)
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    cat = [json.loads(x) for x in Path(a.catalogo).read_text(encoding="utf-8").splitlines() if x.strip()]
    print(json.dumps(ejecutar(cat, Path(a.rastreos), Path(a.salida), a.max_minutos, Path(a.cc) if a.cc else None),
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
