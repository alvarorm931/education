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
from collections import Counter, defaultdict
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


# Listas de precios que cada universidad publica fuera de lo que enlazan sus páginas de grado o su sitemap, halladas
# a mano en su web oficial (código de universidad del RUCT → URL). Se leen igual que las demás, con robots.txt.
# Las del 30/10/2026 por la tarde salen de una búsqueda dirigida en el dominio de cada universidad (sin copias de
# terceros); solo cursos 2025-2026 o posteriores. Cada documento dice su curso y la ficha lo muestra.
URLS_CONOCIDAS = {
    "031": ["https://www.unav.edu/admision-y-ayudas/grado/cuanto-cuesta-estudiar-en-la-universidad",
            "https://en.unav.edu/admission-and-financial-aid/degree/cuanto-cuesta-estudiar-en-la-universidad-"],
    # Universidad Europea: tablas de honorarios de grado 2025-2026 (Madrid, Valencia y Alicante, Málaga)
    "053": ["https://universidadeuropea.com/resources/media/documents/TARIFARIO_GRADO_2025_26_v04.pdf"],
    "082": ["https://universidadeuropea.com/resources/media/documents/Honorarios_Academicos_Grados_2025-26_UEV.pdf"],
    "107": ["https://universidadeuropea.com/resources/media/documents/Tarifas_Grado_Malaga_2025-2026.pdf"],
    # Alfonso X: honorarios de UAX Online 2025-2026 y de UAX Mare Nostrum 2026-2027
    "047": ["https://www.uax.com/download/36836/file/AF_HONORARIOS_ACADEMICOS_UAX_ONLINE_210_X_297_2025_26_V2%20%C3%9A"
            "LTIMA%20VERSION.pdf",
            # Villanueva de la Cañada: honorarios académicos de grado 2026-2027 (hallado el 30/10 por la noche)
            "https://www.uax.com/download/71554/file/HONORARIOS_ACADEMICOS_GRADO%202026_27.pdf"],
    "106": ["https://www.uax.com/en/download/74149/file/AF_HONORARIOS_ACADEMICOS_DE_GRADOS_UAX_MARE_NOSTRUM__210_X_297_"
            "2026_27_V2.pdf"],
    # Deusto: tasas de primer curso de grado 2026-2027 (página general)
    "030": ["https://www.deusto.es/es/inicio/estudia/condiciones-economicas/grado/proximo-curso/tasas-primer-curso"],
    # Pontificia de Salamanca: tasas de grado 2026-2027, nuevo ingreso
    "032": ["https://adminpro.upsa.es/uploads/Tasas_Grados_26_27_e6a7c2a872.pdf"],
    # IE Universidad: tasa anual por programa de grado (el fichero es del curso 2027-2028)
    "057": ["https://docs.ie.edu/Admissions/Tasas_IE_University_27-28.pdf"],
    # Cardenal Herrera-CEU: honorarios de nuevo estudiante por campus (la dirección fija cambia de curso: huella y fecha)
    "067": ["https://www.uchceu.es/docs/nuevo-alumno/tasas-academicas/grado/campus-valencia.pdf",
            "https://www.uchceu.es/docs/nuevo-alumno/tasas-academicas/grado/facultad-derecho-empresa-ciencias-politicas.pdf",
            "https://www.uchceu.es/docs/nuevo-alumno/tasas-academicas/grado/campus-elche.pdf",
            "https://www.uchceu.es/docs/nuevo-alumno/tasas-academicas/grado/campus-castellon.pdf"],
    # Mondragon: precio por grado en su página de precios (importe anual previsto 2027-2028). La tabla central
    # (/es/informacion/becas-ayudas/precios-grados) no cuadra con estas páginas (8.520 € frente a 143 €/ECTS × 60 =
    # 8.580 € en Informática y Mecánica, 30/10): no se usa.
    "061": ["https://mondragon.edu/grado-ingenieria-biomedica/precios-becas-ayudas"] + [
        f"https://www.mondragon.edu/es/{g}" for g in (
            "grado-ingenieria-mecanica/precios-becas-ayudas", "grado-ingenieria-informatica/precios-becas-ayudas",
            "grado-ingenieria-mecatronica/precios-becas-ayudas",
            "grado-ingenieria-electronica-industrial/precios-becas-ayudas",
            "grado-ingenieria-diseno-industrial-desarrollo-producto/precios-becas-ayudas",
            "grado-ingenieria-energia/precios-becas-ayudas", "grado-ingenieria-organizacion-industrial/precios-becas-ayudas",
            "grado-administracion-direccion-empresas/precio-becas-ayudas",
            "grado-business-data-analytics/precio-becas-y-ayudas",
            "grado-humanidades-digitales-globales/precios-becas-ayudas",
            "grado-comunicacion-audiovisual/precio-becas-ayudas", "grado-educacion-primaria/precio-becas-ayudas",
            "grados-educacion-infantil/precio-becas-ayudas",
            "grado-liderazgo-emprendedor-innovacion/precios-becas-ayudas",
            "grado-gastronomia-artes-culinarias/precios-becas-ayudas")],
    # Halladas el 30/10 por la noche (búsqueda dirigida en el dominio de cada universidad, sin copias de terceros).
    # Camilo José Cela: tarifario de grados 2026-2027 y fichas de precio de los grados de Salud (cada una dice su curso)
    "065": ["https://ucjc.edu/pdfs/aula/becas/precios-grados-26-27.pdf"] + [
        f"https://www.ucjc.edu/pdfs/estudios/{f}.pdf" for f in (
            "grado_en_medicina", "grado_en_farmacia", "grado_en_fisioterapia_prof", "grado_en_odontologia",
            "grado_en_nutricion_humana_dietetica", "doble_grado_en_nutricion_humana_dietetica_fisioterapia")] + [
        f"https://ucjc.edu/pdfs/estudios/{f}.pdf" for f in (
            "grado_en_CCAFYD", "grado_en_enfermeria", "doble_grado_en_enfermeria_fisioterapia")],
    # Euneiz: información académica con el precio de cada titulación (2027-2028)
    "098": ["https://www.euneiz.com/informacion-academica/"],
    # Intercontinental de la Empresa (UIE): precio de primer curso en la página de cada grado
    "097": [f"https://uie.edu/grado/{g}/" for g in (
        "grado-en-administracion-y-direccion-de-empresas-de-uie", "grado-en-psicologia", "grado-en-matematica-aplicada",
        "grado-en-fisioterapia", "grado-en-biomedicina", "doble-grado-en-derecho-y-administracion-de-negocios-digitales",
        "grado-en-enfermeria", "grado-en-derecho")],
    # Abat Oliba CEU: precio en la página de cada grado
    "070": ["https://www.uaoceu.es/grado-en-psicolog%C3%ADa", "https://www.uaoceu.es/grado-medicina"],
    # Comillas: precio en la página de cada grado (ejemplos; el resto, con el rastreo de su web)
    "033": ["https://www.comillas.edu/grados/grado-en-derecho-e-1/",
            "https://www.comillas.edu/grados/grado-en-ingenieria-en-tecnologias-industriales-giti/"],
}


# Curso de documentos conocidos cuyo curso no se puede leer bien solo (comprobado a mano): Mondragon da en sus
# páginas de precio «Precio del ECTS: 143 €» con la llamada «Previsión para el curso 2027-28. Será ratificado por el
# Consejo Rector en julio de 2027», y cita 2026-27 en otra llamada (la cuota del Consejo Social).
CURSO_CONOCIDO = {u: {"curso": "2027-2028", "nota": "previsión de la universidad para el curso 2027-2028, pendiente de "
                                                    "ratificar por su Consejo Rector"}
                  for u in URLS_CONOCIDAS["061"]}


# Cómo leer las listas conocidas cuyo formato se comprobó a mano: una fila por grado con su importe anual (o de 60
# créditos), que es el mayor de la fila (las demás cifras son reserva, matrícula o el crédito).
LECTURA_CONOCIDA = {
    # «TASAS TITULACIONES OFICIALES DE GRADO 2026-2027»: Enfermería 9.240 € por 60 ECTS
    "https://adminpro.upsa.es/uploads/Tasas_Grados_26_27_e6a7c2a872.pdf": "importe_anual_mayor_de_la_linea",
    # «Programa de grado / Tasa anual»: una cifra por programa
    "https://docs.ie.edu/Admissions/Tasas_IE_University_27-28.pdf": "importe_anual_mayor_de_la_linea",
    # Euneiz, «Coste de Matrículas de Grado … CURSO 2027-2028»: por titulación, «Coste/crédito anual» (comprobado
    # el 30/10/2026); el curso son 60 créditos
    "https://www.euneiz.com/informacion-academica/": "credito_anual_de_la_tabla",
}


def elegir_conocidas(ya: set[str], extra: dict[str, list[str]] | None = None) -> list[dict]:
    salida = []
    for cod, urls in {**URLS_CONOCIDAS, **(extra or {})}.items():
        for u in urls:
            if u not in ya:
                ya.add(u)
                salida.append({"codigo_universidad": cod, "url": u, "origen": "lista_conocida",
                               **({"lectura": LECTURA_CONOCIDA[u]} if u in LECTURA_CONOCIDA else {})})
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
                x = {"universidad": d.get("universidad"), "codigo_universidad": d.get("codigo"),
                     "web": d.get("web"), "url": url, "origen": origen}
                if d.get("centro"):
                    # rastreo de la web de un centro (web_privadas --por-centros): sus grados son los del centro y los
                    # que el rastreo unió a una página suya (varios centros con la misma web)
                    x.update(centro=d["centro"], centro_adscrito=bool(d.get("centro_adscrito")),
                             grados_rastreo=sorted(d.get("fichas") or {}))
                salida.append(x)
    return salida


def grados_por_codigo(catalogo: list[dict]) -> dict[str, list[dict]]:
    """Código de rastreo → grados activos: el de una universidad privada (3 cifras) y el de un centro de cualquier
    universidad («{universidad}{centro}», como en web_privadas.objetivos_centros)."""
    por: dict[str, list] = defaultdict(list)
    for t in catalogo:
        if t["situacion"] != "Activo" or t["clase"] not in ("grado", "doble"):
            continue
        for u in t["universidades"]:
            if not u.get("codigo"):
                continue
            if u["tipo"] == "Privada":
                por[u["codigo"]].append(t)
            for i in t.get("imparticiones") or []:
                if i.get("situacion") == "Activo" and i.get("unidad_codigo") and i.get("universidad") == u["nombre"]:
                    clave = f"{u['codigo']}{i['unidad_codigo']}"
                    if t not in por[clave]:
                        por[clave].append(t)
    return por


BLOQUE = re.compile(r"(?is)</(?:p|li|h[1-6]|div|section|article|dt|dd|caption|table)>|<br\s*/?>")


CIFRA_EUROPEA = re.compile(r"(?<![\d.,])\d{1,3}(?:\.\d{3})*,\d{2}(?![\d,])")


def diagnostico_html(html: str) -> dict:
    """Por qué una página de precios no da ninguna línea con importe, sin guardar su texto: cuántas tablas y filas
    trae, cuántas cifras con decimales hay a la vista y cuántas dentro de scripts (tablas que se pintan con
    JavaScript) o de plantillas."""
    scripts = " ".join(re.findall(r"(?is)<script\b.*?</script>", html))
    plantillas = " ".join(re.findall(r"(?is)<template\b.*?</template>", html))
    visible = "\n".join(lineas_html(html))
    return {"bytes": len(html), "tablas": len(re.findall(r"(?i)<table\b", html)),
            "filas": len(re.findall(r"(?i)<tr\b", html)), "cifras_visibles": len(CIFRA_EUROPEA.findall(visible)),
            "cifras_en_scripts": len(CIFRA_EUROPEA.findall(scripts)),
            "cifras_en_plantillas": len(CIFRA_EUROPEA.findall(plantillas)),
            "iframes": len(re.findall(r"(?i)<iframe\b", html)), "euro": "€" in visible}


def lineas_html(html: str) -> list[str]:
    """Texto visible de una página en líneas: una por párrafo o elemento de lista y una por fila de tabla, con las
    celdas separadas por « | » (para leer cada importe con el rótulo de su columna)."""
    texto = re.sub(r"(?is)<(script|style|noscript|svg|head)\b.*?</\1>", " ", html)
    # los párrafos o saltos dentro de una celda («<td><p>Trabajo Social</p></td>») no parten la fila
    texto = re.sub(r"(?is)<tr\b.*?</tr>", lambda m: BLOQUE.sub(" ", m.group()), texto)
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


COLUMNA_DE_DINERO = re.compile(r"(?i)precio|importe|matr[íi]cula|\btotal\b|plazos?|cuotas?|honorarios|tasas?|"
                               r"ense[ñn]anza|docencia|mensualidad")
BECA = re.compile(r"(?i)\bbecas?\b|\bbecad[oa]s?\b|\bbecarios?\b")
SOLO_UNIDADES = re.compile(r"(?i)\b(?:ects|cr[ée]ditos?|horas?|cursos?|años?|semestres?|totales?)\b")


def grado_de_fichero(url: str, grados: list[dict]) -> str | None:
    """PDF de un solo grado por el nombre del fichero («…/grado_en_medicina.pdf»): solo si empieza por «grado» o
    «doble_grado» y su nombre casa con un único grado de la universidad."""
    nombre = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
    if not re.match(r"(?i)(?:doble[_-])?grado[_-]", nombre):
        return None
    return grado_de_url(re.sub(r"\.pdf$", "/", url.split("?")[0], flags=re.I).replace("_", "-"), grados)


def extraer(paginas: list[str], grados: list[dict], de_la_pagina: str | None = None) -> dict:
    """Importes por grado de un PDF o una página de precios (una cadena por página, con saltos de línea; en las
    tablas HTML las celdas van separadas por « | » y cada importe toma el tipo del rótulo de su columna)."""
    precios: dict[str, list] = defaultdict(list)
    con_importe, muestra, previa, rotulo = 0, [], "", None
    curso, cabecera = None, None
    bloque, ultimo = 0, None
    # tablas cuyas celdas dan el importe sin «€» («1.278,00»): valen si la página habla de euros y la tabla tiene
    # cabecera con rótulos de importe (matrícula, plazos, total…)
    euros = bool(re.search(r"€|\beuros?\b", " ".join(paginas), re.I))
    curso_linea, cursos_de_importes = None, Counter()  # el curso escrito más cerca (antes) de cada importe
    for n, pagina in enumerate(paginas, 1):
        if not curso and (m := CURSO_DOC.search(pagina)):
            curso = f"{m.group(1)}-20{m.group(2)}"
        for linea in (x.strip() for x in pagina.split("\n")):
            if not linea:
                continue
            if m := list(CURSO_DOC.finditer(linea)):
                curso_linea = f"{m[-1].group(1)}-20{m[-1].group(2)}"
            # sin «€» ni «euros» en la página (Deusto): vale si la cabecera rotula columnas de dinero («MATRÍCULA»,
            # «8 PLAZOS ENSEÑANZA», «TOTAL») y la cifra lleva céntimos
            if cabecera and (euros or any(COLUMNA_DE_DINERO.search(c) for c in cabecera)) and " | " in linea:
                linea = re.sub(r"(?<=\| )(\d{1,3}(?:\.\d{3})*,\d{2})(?= \||$)", r"\1 €", linea)
            hallados = list(IMPORTE.finditer(linea))
            celdas = [c.strip() for c in linea.split(" | ")]
            if not hallados:
                if len(celdas) >= 2 and any(tipo_rotulo(c) for c in celdas):
                    cabecera = celdas
                if tipo_rotulo(linea) and len(linea) < 120:
                    rotulo = tipo_rotulo(linea)
                # el nombre de la línea de encima: no vale una celda de solo unidades («60 ECTS», «240 créditos»)
                if re.search(r"[A-Za-zÁÉÍÓÚáéíóú]{4}", SOLO_UNIDADES.sub(" ", linea)):
                    previa = linea
                continue
            con_importe += 1
            texto_sin = IMPORTE.sub(" ", linea)
            if BECA.search(texto_sin):
                continue  # «Educación Primaria (Becas Marqués de Lozoya)»: el precio con beca no es el del grado
            codigo = grado_de(linea, grados)
            # una línea de solo cifras, o con solo el rótulo del importe («Coste/crédito anual 147,50 €»), es del
            # grado de la línea de texto anterior
            solo_rotulo = len(texto_sin.strip()) < 40 and bool(tipo_rotulo(texto_sin)) and not grado_de(texto_sin, grados)
            if codigo:
                bloque += 1  # cada línea con nombre de grado abre un bloque; las de solo cifras que siguen, también suyas
            elif not re.search(r"[A-Za-zÁÉÍÓÚáéíóú]{4}", texto_sin) or solo_rotulo:
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
                # «1 100 €» o «1. 100 €» (el texto del PDF parte la cifra): el espacio normal no separa miles (también
                # «10 983 €», diez cuotas de 983 €); se guarda la otra lectura y solo vale si con ella cuadran las cifras
                # del bloque (fichas.precio_por_cuentas_con_miles)
                miles = (re.search(r"(?<![\d.,])(\d{1,2})(?:\s{0,2}\.\s{0,2}|\s{1,3})$", antes)
                         if re.fullmatch(r"\d{3}", m.group("e") or "") and not m.group("d") else None)
                precios[codigo].append({"valor": valor, "tipo": tipo, "verosimil": bool(tipo) and bajo <= valor <= alto,
                                        "pagina": n, "bloque": bloque,
                                        **({"miles_con_espacio": int(miles.group(1)) * 1000 + valor} if miles else {}),
                                        # forma de lo que precede a una cifra de tres dígitos (9 = dígito, _ = espacio, a = letra),
                                        # sin texto: para ver cómo parte el PDF las cifras
                                        **({"antes_forma": re.sub(r"[^\W\d_]", "a", re.sub(r"\s", "_", re.sub(r"\d", "9", antes[-5:])))}
                                           if re.fullmatch(r"\d{3}", m.group("e") or "") else {}),
                                        "linea_sha256": hashlib.sha256(linea.encode()).hexdigest()[:16]})
                if curso_linea:
                    cursos_de_importes[curso_linea] += 1
    # una página que cita varios cursos («becas 2026-2027», «importe anual previsto 2027-2028»): vale el que va
    # escrito antes de sus importes; si no hay, el primero del documento
    if cursos_de_importes:
        curso = cursos_de_importes.most_common(1)[0][0]
    return {"curso_documento": curso, "lineas_con_importe": con_importe, "grados": dict(precios), "muestra": muestra}


def pedir_con_motivo(d, url: str):
    """Pide una dirección y, si no hay respuesta, dice por qué: límite de peticiones al servidor, robots.txt que lo
    prohíbe, robots.txt que no responde (entonces no se rastrea) o el error de conexión."""
    from motor.estudios.rastreador import _origen

    limite = lambda: getattr(d, "peticiones", 0) >= getattr(d, "max_peticiones", float("inf"))  # noqa: E731
    if limite():
        return None, "limite_de_peticiones_al_servidor"
    if hasattr(d, "robots_ok_para") and not d.robots_ok_para(url):
        rp = getattr(d, "robots", {}).get(_origen(url))
        return None, "robots_txt_no_responde" if rp is not None and rp.disallow_all else "robots_txt_lo_prohibe"
    antes = dict(getattr(d, "estados", {}))
    r = d.get(url, guardar=False)
    if r is not None:
        return r, None
    nuevos = [k for k, v in getattr(d, "estados", {}).items() if v > antes.get(k, 0)]
    return None, nuevos[0] if nuevos else ("limite_de_peticiones_al_servidor" if limite() else "sin_respuesta")


def ejecutar(catalogo: list[dict], rastreos: Path, salida: Path, max_minutos: float = 50,
             cc: Path | None = None, extra: dict[str, list[str]] | None = None, previas: Path | None = None,
             releer: set[str] | None = None, solo: set[str] | None = None) -> dict:
    from motor.estudios.rastreador import Dominio

    archivo = Archivo(salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    destino = salida / "datos" / "estudios" / "grados" / "tarifas_grado"
    destino.mkdir(parents=True, exist_ok=True)
    por_u = grados_por_codigo(catalogo)
    por_cod = {t["codigo"]: t for t in catalogo}
    fin = time.time() + max_minutos * 60
    resultados, dominios = [], {}
    elegidos = elegir(rastreos)
    de_centro = {p["codigo_universidad"]: {k: p[k] for k in ("centro", "centro_adscrito", "grados_rastreo")}
                 for p in elegidos if p.get("centro")}
    elegidos += [{**p, **de_centro.get(p["codigo_universidad"], {})}
                 for p in elegir_cc(cc, {p["url"] for p in elegidos})]
    elegidos += elegir_conocidas({p["url"] for p in elegidos}, extra)
    # solo lo nuevo: las direcciones que una ejecución anterior ya pidió (con respuesta) no se vuelven a pedir
    ya = urls_previas(previas) - (releer or set())  # releer: las que cambió la forma de leerlas
    elegidos = [p for p in elegidos if p["url"] not in ya]
    if solo:  # una ejecución dirigida: solo estas universidades o centros (código de rastreo)
        elegidos = [p for p in elegidos if p["codigo_universidad"] in solo]
    for p in elegidos:
        if time.time() > fin:
            break
        r_url = p["url"]
        host = re.sub(r"^https?://([^/]+).*$", r"\1", r_url)
        d = dominios.setdefault(host, Dominio("https://" + host, archivo, pausa=1.0, max_peticiones=40))
        r, motivo = pedir_con_motivo(d, r_url)
        res = {**{k: v for k, v in p.items() if k != "grados_rastreo"}, "estado": r.status_code if r is not None else None, "capturado": date.today().isoformat()}
        if motivo:
            res["motivo"] = motivo
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
                gs = list(por_u.get(p["codigo_universidad"], []))
                gs += [por_cod[c] for c in p.get("grados_rastreo") or [] if c in por_cod and por_cod[c] not in gs]
                res.update(extraer(paginas, gs, grado_de_fichero(r_url, gs) if es_pdf else grado_de_url(r_url, gs)))
                if es_html and not res.get("lineas_con_importe"):
                    res["diagnostico"] = diagnostico_html(r.text)
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
                       ("pdf_de_pagina_de_grado", "pagina_de_precios", "common_crawl", "lista_conocida")},
        "leidos": sum(1 for x in resultados if x.get("paginas")),
        "con_algun_grado": sum(1 for x in resultados if x.get("grados")),
        "grados_con_importe": len({c for x in resultados for c in (x.get("grados") or {})}),
        "grados_con_importe_verosimil": len({c for x in resultados for c, v in (x.get("grados") or {}).items()
                                             if any(i["verosimil"] for i in v)}),
        "por_universidad": dict(sorted(
            {u: len({c for x in resultados if (x.get("universidad") or x["codigo_universidad"]) == u
                      for c in (x.get("grados") or {})})
             for u in {x.get("universidad") or x["codigo_universidad"] for x in resultados}}.items(),
            key=lambda kv: -kv[1])),
    }
    (destino / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    return resumen


def urls_previas(carpeta: Path | None) -> set[str]:
    """Direcciones con respuesta (de cualquier código) en los tarifas.jsonl de ejecuciones anteriores."""
    ya: set[str] = set()
    for f in sorted(carpeta.rglob("tarifas_grado/tarifas.jsonl")) if carpeta else []:
        for linea in f.read_text(encoding="utf-8").splitlines():
            if linea.strip():
                x = json.loads(linea)
                if x.get("estado") is not None:
                    ya.add(x["url"])
    return ya


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--catalogo", required=True)
    p.add_argument("--rastreos", required=True, help="carpeta con …/web_privadas/{código}.json")
    p.add_argument("--cc", help="carpeta con …/cc_precios/urls_*.jsonl (cc_precios.py)")
    p.add_argument("--previas", help="carpeta con …/tarifas_grado/tarifas.jsonl de ejecuciones anteriores (no se repiten)")
    p.add_argument("--releer", action="append", default=[], help="dirección ya pedida que se vuelve a leer")
    p.add_argument("--max-minutos", type=float, default=50)
    p.add_argument("--solo", action="append", default=[], help="código de universidad o centro (se puede repetir)")
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    cat = [json.loads(x) for x in Path(a.catalogo).read_text(encoding="utf-8").splitlines() if x.strip()]
    print(json.dumps(ejecutar(cat, Path(a.rastreos), Path(a.salida), a.max_minutos, Path(a.cc) if a.cc else None,
                              previas=Path(a.previas) if a.previas else None, releer=set(a.releer),
                              solo=set(a.solo) or None),
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
