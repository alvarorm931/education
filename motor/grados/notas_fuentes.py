"""Notas de corte de grado de cada distrito: localizar y guardar los documentos oficiales (fase 1 de las notas).

Cada comunidad (o universidad) publica sus notas de corte a su manera: PDF por curso y por adjudicación, datos
abiertos (Cataluña, Universidad de Murcia) o formularios (distrito único andaluz). Aquí, desde las páginas índice y
los ficheros oficiales conocidos de cada distrito (investigados el 30/10/2026, docs/modelo-grados.md §notas):

1. se leen las páginas índice con el lector cortés (robots.txt de cada servidor, una petición por segundo) y se
   anotan sus enlaces a documentos de notas (PDF, CSV, JSON, XLSX) y sus formularios (campos y opciones);
2. se bajan los documentos; el original va al almacén privado con su huella sha256;
3. de cada documento se mide lo necesario para escribir su lector: formato, páginas, curso que dice, filas con una
   nota (número con decimales entre 5 y 14) y una muestra de esas filas (titulación, centro, cupo y nota son datos,
   no texto de autor; nunca hay datos de personas en estas listas).

La fase 2 (notas_corte.py) lee cada formato y une cada fila con su título y centro del catálogo.

Uso:
  python -m motor.grados.notas_fuentes --salida ruta/ [--solo madrid,cataluna] [--max-minutos 50] [--filas 80]
                                       [--extra distrito=url …]
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import tempfile
import time
from collections import defaultdict
from datetime import date
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse

from motor.archivo import Archivo, solo_huella_por_defecto

FUENTE = "notas-corte"
MAX_DOC = 25_000_000
MUESTRA_FILAS = 80
# Lectura óptica (tesseract) de los PDF que son imágenes sin texto (UPV/EHU desde 2022-23); se activa con --ocr
OCR = {"activo": False}
# PDF de texto que se leen como imagen (con --ocr): sus tablas escriben cada fila en un solo bloque de texto y solo
# la lectura óptica daría la posición de cada cifra. Probado con la evolución de Burgos el 30/10: a 300 ppp la tabla
# apaisada de letra pequeña y celdas coloreadas sale ilegible («222», «2020» por 2022), así que no se usa.
OCR_SIEMPRE: tuple[str, ...] = ()
# Posición de cada fragmento de texto de los PDF con notas (tablas con celdas vacías); se activa con --posiciones
POSICIONES = {"activo": False}
NOTA = re.compile(r"(?<![\d.,])(?:1[0-4]|[5-9])[.,]\d{2,3}(?![\d.,])")
CURSO = re.compile(r"\b(20[12]\d)\s*[-/–_]\s*(?:20)?([12]\d)\b")
ENLACE = re.compile(r"""(?is)<a\b[^>]*?href\s*=\s*["']([^"'#]+)["'][^>]*>(.*?)</a>""")
DOC = re.compile(r"(?i)\.(pdf|csv|xlsx?|json)(?:$|[?;])|/files/|/documents/|\.ashx|download|/resource/")
DE_NOTAS = re.compile(r"(?i)nota|corte|tall|admis|chamamento|llamamiento|adjudic|asignaci|cupo|plazas|preinscrip")
# Listas de personas (admitidos, lista de espera, excluidos, tablón de la sede): nunca se piden ni se guardan
# (CLAUDE.md: de las listas de admitidos solo se cuenta). Si un documento trae DNI o NIE, tampoco se guarda.
PERSONAS = re.compile(r"(?i)(?:lista|listado)s?[_ -]?\d|espera|admitid|excluid|tabl[oó]n|/sede/|adjudicad[oa]s|"
                      r"seleccionad|nominal")
DNI = re.compile(r"\b\d{8}[A-HJ-NP-TV-Z]\b|\*{3}\d{4}\*{1,3}|\b[XYZ]\d{7}[A-Z]\b")

# Semillas por distrito: páginas índice (se leen sus enlaces y formularios) y ficheros oficiales ya localizados.
# «patrones»: ficheros con la dirección de un curso, para los cursos que no enlaza ninguna página.
CURSOS = ["2021-2022", "2022-2023", "2023-2024", "2024-2025", "2025-2026", "2026-2027"]
SEMILLAS: dict[str, dict] = {
    "madrid": {
        "nombre": "Distrito único de Madrid (universidades públicas)",
        "indices": ["https://www.uc3m.es/grado/admision/notas-corte", "https://www.ucm.es/notas-de-corte"],
        "ficheros": ["https://www.uc3m.es/grado/media/grado/doc/archivo/doc_notas-corte-2425/"
                     "dum-notas-de-corte-2024-2025---extraordinaria.pdf"]},
    "cataluna": {
        "nombre": "Cataluña · Generalitat, datos abiertos (Socrata)",
        "ficheros": ["https://analisi.transparenciacatalunya.cat/api/views/usyn-hngc.json",
                     "https://analisi.transparenciacatalunya.cat/resource/usyn-hngc.json?$limit=50000",
                     "https://analisi.transparenciacatalunya.cat/api/views/bvmc-igg6.json",
                     "https://analisi.transparenciacatalunya.cat/resource/bvmc-igg6.json?$limit=50000"]},
    "andalucia": {
        "nombre": "Distrito único andaluz",
        # consulta de cursos anteriores (formulario POST de la página; un curso cada vez, el resto «Cualquiera»)
        # el botón «Descargar» de la consulta histórica envía el formulario a g_not_cor_anteriores_csv.php
        # (libportal/js/g_funcs_js_nca.js, función BuscarPeticiones): un CSV por curso con todas las universidades
        "consultas": [{"url": f"https://www.juntadeandalucia.es/economiaconocimientoempresasyuniversidad/sguit/{r}"
                              "g_not_cor_anteriores_csv.php",
                       "campos": {"univpet": "", "familia": "", "anio": str(a), "titulpet": ""}}
                      for r in ("", "grados/") for a in range(2025, 2009, -1)],
        "indices": ["https://www.juntadeandalucia.es/economiaconocimientoempresasyuniversidad/sguit/"
                    "?q=grados&d=g_not_cor_anteriores_top.php",
                    "https://www.juntadeandalucia.es/economiaconocimientoempresasyuniversidad/sguit/convocatorias/"
                    "grados_consulta_adj/notasCorteAdj.php"],
        "ficheros": ["https://transparente.ugr.es/sites/serv/transp/public/ficheros/Acceso%20y%20Admisi%C3%B3n/2024/"
                     "Notas%20de%20corte.pdf",
                     "https://www.us.es/sites/default/files/inline-files/Notas%20Corte%20F1A2%202022%20US.pdf",
                     "https://transparencia.uca.es/wp-content/uploads/2024/10/NotasCorteTitulacionGrado-23-24.pdf"]},
    "murcia": {
        "nombre": "Universidad de Murcia · datos abiertos",
        "patrones": ["https://datos.um.es/public/nota-corte-grado-{c}/csv"],
        "indices": ["https://admision.upct.es/preinscripcion-y-matricula/admision-en-estudios-de-grado-universitarios"]},
    "valenciana": {
        "nombre": "Comunitat Valenciana (preinscripción conjunta)",
        "indices": ["https://www.uv.es/graus/admissio"],
        "ficheros": ["https://www.uv.es/graus/admissio/1_NOTAS%20CORTE%202026-2027_Adjudicaci%c3%b3n%2010%20julio.pdf"]},
    "castilla-leon": {
        "nombre": "Castilla y León (cada universidad)",
        "ficheros": ["https://www.usal.es/files/acceso/notas_corte_grados_usal2023_24_finales_web.pdf",
                     "https://usal.es/files/acceso/notas_corte_grados_usal2024_25_tras_llamamientos_web.pdf",
                     "https://unileon.es/files/2024-11/notas-de-corte-2024.pdf",
                     "https://www.unileon.es/files/2025-11/notas_de_corte_2025nw.pdf",
                     "https://admision.uva.es/export/sites/uva/2.estudios/2.03.grados/_documentos/"
                     "notas_de_corte-2025_26.pdf",
                     "https://stic.uva.es/export/sites/uva/2.estudios/2.03.grados/_documentos/"
                     "notas_corte_para_publicar_23_24.pdf",
                     "https://www.ubu.es/sites/default/files/portal_page/files/notas_de_corte_%20hasta_2026-2027.pdf"],
        "indices": ["https://www.usal.es/notas-de-corte", "https://www.ubu.es/acceso-admision-y-matricula/admision/"
                    "admision-grado"],
        "patrones": ["https://www.usal.es/files/acceso/notas_corte_grados_usal{a}_{b}_finales_web.pdf"]},
    "galicia": {
        "nombre": "Galicia · CiUG",
        "ficheros": ["https://ciug.gal/PDF/ACCESO2024/notas_corte.pdf", "https://ciug.gal/PDF/2025/ACCESO/chamamento_9.pdf"],
        "patrones": ["https://ciug.gal/PDF/ACCESO{a}/notas_corte.pdf"]},
    "pais-vasco": {
        "nombre": "UPV/EHU",
        "indices": ["https://www.ehu.eus/es/web/graduak/preinscripcion-y-admision/notas-de-corte"]},
    "canarias": {
        "nombre": "Canarias (ULPGC y ULL)",
        "ficheros": ["https://ulpgc.es/sites/default/files/ArchivosULPGC/gestion-academica/"
                     "notas_de_corte_definitivas_2024-2025.pdf",
                     "https://www.ulpgc.es/sites/default/files/ArchivosULPGC/gestion-academica/"
                     "notas_de_corte_primera_asignacion_de_plazas_2022-2023.pdf"],
        "patrones": ["https://www.ulpgc.es/sites/default/files/ArchivosULPGC/gestion-academica/"
                     "notas_de_corte_definitivas_{c}.pdf"],
        "indices": ["https://www.ull.es/admision-becas/pau/notas-de-corte/"]},
    "cantabria": {
        "nombre": "Universidad de Cantabria",
        "ficheros": ["https://web.unican.es/estudiantesuc/Documents/Estad%C3%ADsticas/Grado/"
                     "Estad%C3%ADsticas%20de%20Ordenaci%C3%B3n%20Acad%C3%A9mica/7-2%20Evoluci%C3%B3n%20Notas%20de%20Corte.pdf",
                     "https://web.unican.es/admision/Documents/Acceso/"
                     "Notas%20de%20corte%20provisionales%20comparativa%202026-27%201%c2%aa%20Lista.pdf"]},
    "castilla-la-mancha": {
        "nombre": "Universidad de Castilla-La Mancha",
        "ficheros": ["https://www.uclm.es/-/media/Files/A04-Gestion-Academica/PDFEstudiantes/NOTAS-DE-CORTE/"
                     "CURSO-2025-26/NOTA-CORTE-1-ADMISIN.ashx?la=es",
                     "https://www.uclm.es/-/media/Files/A04-Gestion-Academica/PDFEstudiantes/NOTAS-DE-CORTE/"
                     "CURSO-2023-24/Notas-de-corte-SIIU.ashx?la=es"],
        "indices": ["https://www.uclm.es/estudiantes/acceso/notas-de-corte"]},
    "extremadura": {
        "nombre": "Universidad de Extremadura",
        "ficheros": ["https://alumnado.unex.es/wp-content/uploads/sites/51/2024/10/202425notasdecorte.pdf",
                     "https://alumnado.unex.es/wp-content/uploads/sites/51/2025/10/Notas-corte-2025-2026.pdf",
                     "https://alumnado.unex.es/wp-content/uploads/sites/51/2026/07/R1_NotasCorte_2026-27.pdf"]},
    "asturias": {
        "nombre": "Universidad de Oviedo",
        "ficheros": ["https://uniovi.es/documents/39158/7ab021c3-838b-6e53-9a80-7e9c884346c7",
                     "https://uniovi.es/documents/39158/835701a7-1d81-63c0-73ee-bf833dfd17ac"]},
    "baleares": {
        "nombre": "Universitat de les Illes Balears",
        "indices": ["https://estudis.uib.cat/estudis-de-grau/Com-hi-pots-accedir/admissio/notes-de-tall/"],
        "ficheros": ["https://estudis.uib.cat/estudis-de-grau/grau/dret/GDRE-P/notesTallPla.html"]},
    "navarra": {
        "nombre": "Universidad Pública de Navarra",
        "indices": ["https://www.unavarra.es/sites/estudios/acceso-y-admision/admision-en-estudios-de-grado/"
                    "listas-de-admision.html"]},
    "la-rioja": {
        "nombre": "Universidad de La Rioja",
        "ficheros": ["https://www.unirioja.es/transparencia/archivos/estudiantes_10.pdf"]},
}


def cursos_patron(patron: str) -> list[str]:
    salida = []
    for c in CURSOS:
        a, b = c.split("-")
        salida.append(patron.format(c=c, a=a, b=b[2:]))
    return salida


def enlaces(html: str, base: str) -> list[tuple[str, str]]:
    """(url absoluta, texto del enlace) de los enlaces a documentos de notas."""
    vistos, salida = set(), []
    for href, texto in ENLACE.findall(html):
        url = urljoin(base, unescape(href.strip()))
        texto = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", unescape(texto))).strip()
        if url in vistos or not url.startswith("http"):
            continue
        if DOC.search(url) and (DE_NOTAS.search(url) or DE_NOTAS.search(texto)) \
                and not (PERSONAS.search(url) or PERSONAS.search(texto)):
            vistos.add(url)
            salida.append((url, texto[:120]))
    return salida


FORM = re.compile(r"(?is)<form\b([^>]*)>(.*?)</form>")
SELECT = re.compile(r"(?is)<select\b[^>]*name\s*=\s*[\"']([^\"']+)[\"'][^>]*>(.*?)</select>")
OPCION = re.compile(r"(?is)<option\b[^>]*value\s*=\s*[\"']([^\"']*)[\"'][^>]*>(.*?)</option>")
INPUT = re.compile(r"(?is)<input\b[^>]*name\s*=\s*[\"']([^\"']+)[\"'][^>]*>")


def formularios(html: str, base: str) -> list[dict]:
    """Formularios de la página: destino, método y campos (con las opciones de cada lista), para preparar consultas."""
    salida = []
    for attrs, cuerpo in FORM.findall(html):
        accion = re.search(r"(?i)action\s*=\s*[\"']([^\"']*)", attrs)
        metodo = re.search(r"(?i)method\s*=\s*[\"']([^\"']*)", attrs)
        listas = {n: [(v, re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", unescape(t))).strip()[:80])
                      for v, t in OPCION.findall(c)][:200] for n, c in SELECT.findall(cuerpo)}
        salida.append({"accion": urljoin(base, unescape(accion.group(1))) if accion else base,
                       "metodo": (metodo.group(1) if metodo else "get").lower(),
                       "atributos": re.sub(r"\s+", " ", attrs).strip()[:300],
                       "listas": listas, "campos": sorted(set(INPUT.findall(cuerpo))),
                       # botones y entradas con sus atributos (sin valores de usuario): para saber cómo se envía
                       "controles": [re.sub(r"\s+", " ", x)[:200] for x in
                                     re.findall(r"(?is)<(?:button|input)\b[^>]*>", cuerpo)][:30]})
    # funciones de la página que envían formularios (para reproducir la consulta)
    if salida:
        salida[0]["scripts"] = [re.sub(r"\s+", " ", x)[:300] for x in
                                re.findall(r"(?is)[^\n;{}]*(?:submit|\.action|location\.href|ajax|fetch\()[^\n;{}]*",
                                           " ".join(re.findall(r"(?is)<script\b[^>]*>(.*?)</script>", html)))][:20]
    return salida


def cuerpo_funcion(js: str, nombre: str, maximo: int = 2500) -> str | None:
    """Código de `function nombre(...) {...}` (o `nombre = function`), con las llaves emparejadas."""
    m = re.search(rf"(?:function\s+{re.escape(nombre)}\s*\(|\b{re.escape(nombre)}\s*=\s*(?:async\s+)?function\s*\()", js)
    if not m:
        return None
    i = js.find("{", m.end())
    if i < 0:
        return None
    nivel, j = 0, i
    while j < len(js):
        nivel += {"{": 1, "}": -1}.get(js[j], 0)
        if nivel == 0:
            break
        j += 1
    return js[m.start():j + 1][:maximo]


def funciones_de_envio(html: str, base: str, pedir) -> list[dict]:
    """Funciones que llaman los botones de los formularios (onclick), buscadas en los scripts de la página y en sus
    ficheros .js del mismo sitio: dicen a qué dirección y con qué campos se hace la consulta de verdad."""
    nombres = sorted(set(re.findall(r"(?i)on(?:click|submit|change)\s*=\s*[\"']\s*(?:return\s+)?([A-Za-z_$][\w$]*)\s*\(",
                                    " ".join(c for _, c in FORM.findall(html)) or html)))
    if not nombres:
        return []
    fuentes = [("pagina", " ".join(re.findall(r"(?is)<script\b[^>]*>(.*?)</script>", html)))]
    host = urlparse(base).netloc
    for src in re.findall(r"(?is)<script\b[^>]*\bsrc\s*=\s*[\"']([^\"']+)", html)[:15]:
        u = urljoin(base, unescape(src))
        if urlparse(u).netloc != host or re.search(r"(?i)jquery|bootstrap|popper|analytics|gtag|cookie", u):
            continue
        r = pedir(u)
        if r is not None and r.status_code == 200 and len(r.content) < 2_000_000:
            fuentes.append((u, r.text))
    salida = []
    for n in nombres[:8]:
        for origen, js in fuentes:
            c = cuerpo_funcion(js, n)
            if c:
                salida.append({"funcion": n, "origen": origen, "codigo": c,
                               "direcciones": sorted(set(re.findall(r"[\"']([^\"'\s]*\.(?:php|aspx?|jsp|json|csv)[^\"'\s]*)[\"']",
                                                                    c)))[:10]})
                break
        else:
            salida.append({"funcion": n, "origen": None})
    return salida


def lineas_ocr(contenido: bytes) -> list[str] | None:
    """Texto de un PDF sin capa de texto por lectura óptica: cada página a 300 ppp (pdftoppm) y tesseract en español
    con los espacios entre palabras conservados (las columnas siguen separadas). None si faltan las herramientas."""
    if not (shutil.which("pdftoppm") and shutil.which("tesseract")):
        return None
    with tempfile.TemporaryDirectory() as d:
        pdf = Path(d) / "doc.pdf"
        pdf.write_bytes(contenido)
        subprocess.run(["pdftoppm", "-r", "300", "-png", str(pdf), str(Path(d) / "p")], check=True, timeout=300)
        lineas = []
        for i, img in enumerate(sorted(Path(d).glob("p*.png")), 1):
            r = subprocess.run(["tesseract", str(img), "stdout", "-l", "spa", "--psm", "6",
                                "-c", "preserve_interword_spaces=1"], capture_output=True, text=True, timeout=300)
            lineas += [f"### página {i} (lectura óptica)"] + [x.rstrip() for x in r.stdout.splitlines()]
        return lineas


def posiciones_pdf(contenido: bytes, max_paginas: int = 40) -> list[dict]:
    """Cada fragmento de texto del PDF con su posición en la página (x en puntos desde el texto más a la izquierda de
    la página, y desde abajo),
    agrupados en líneas por su altura. Para las tablas con celdas vacías, donde el texto en una línea no dice a qué
    columna va cada cifra: el lector la asigna por la x de los rótulos de la cabecera. Usa el mismo cálculo de
    posiciones que el modo de disposición de pypdf: la posición es la de cada bloque de texto del PDF (BT…ET), así
    que solo sirve si cada celda es su propio bloque (no en la tabla de Burgos, que escribe una fila entera en uno)."""
    from pypdf import PdfReader
    from pypdf._text_extraction import _layout_mode
    from pypdf.generic import ContentStream

    lector = PdfReader(io.BytesIO(contenido))
    salida = []
    for i, p in enumerate(lector.pages[:max_paginas], 1):
        try:
            ops = iter(ContentStream(p["/Contents"].get_object(), lector, "bytes").operations)
            grupos = _layout_mode.text_show_operations(ops, p._layout_mode_fonts(), True, None)
            por_y = _layout_mode.y_coordinate_groups(grupos, None) if grupos else {}
        except Exception:  # noqa: BLE001 - una página rota (o una versión de pypdf sin esa API) no para el resto
            continue
        lineas = []
        for y in sorted(por_y, reverse=True):
            trozos = sorted([round(float(g["tx"]), 1), g["text"].strip()] for g in por_y[y] if g["text"].strip())
            if trozos:
                lineas.append({"y": round(float(y), 1), "trozos": trozos})
        salida.append({"pagina": i, "lineas": lineas})
    return salida


def posiciones_ocr(contenido: bytes) -> list[dict]:
    """Lo mismo que `posiciones_pdf` para un PDF de imágenes: cada palabra que lee tesseract con su posición (x del
    borde izquierdo, texto y ancho, en píxeles a 300 ppp), agrupadas por la línea que detecta tesseract."""
    if not (shutil.which("pdftoppm") and shutil.which("tesseract")):
        return []
    salida = []
    with tempfile.TemporaryDirectory() as d:
        pdf = Path(d) / "doc.pdf"
        pdf.write_bytes(contenido)
        subprocess.run(["pdftoppm", "-r", "300", "-png", str(pdf), str(Path(d) / "p")], check=True, timeout=300)
        for i, img in enumerate(sorted(Path(d).glob("p*.png")), 1):
            r = subprocess.run(["tesseract", str(img), "stdout", "-l", "spa", "--psm", "6", "tsv"],
                               capture_output=True, text=True, timeout=300)
            lineas: dict[tuple, dict] = {}
            for fila in r.stdout.splitlines()[1:]:
                c = fila.split("\t")
                if len(c) < 12 or not c[11].strip():
                    continue
                clave = (int(c[2]), int(c[3]), int(c[4]))
                ln = lineas.setdefault(clave, {"y": int(c[7]), "trozos": []})
                ln["trozos"].append([int(c[6]), c[11].strip(), int(c[8])])  # x, texto, ancho
            salida.append({"pagina": i, "ocr": True,
                           "lineas": sorted(({"y": v["y"], "trozos": sorted(v["trozos"])} for v in lineas.values()),
                                            key=lambda z: z["y"])})
    return salida


def lineas_documento(contenido: bytes, formato: str, forzar_ocr: bool = False) -> tuple[list[str], int | None]:
    """Líneas de texto de un documento (PDF con la disposición de columnas; CSV/JSON/HTML tal cual). Con
    `forzar_ocr`, un PDF de texto se lee también como imagen (tablas que escriben una fila entera en un bloque)."""
    if formato == "pdf":
        from pypdf import PdfReader

        lector = PdfReader(io.BytesIO(contenido))
        lineas = []
        for i, p in enumerate(lector.pages, 1):
            try:
                t = p.extract_text(extraction_mode="layout") or ""
            except Exception:  # noqa: BLE001 - versiones de pypdf sin modo de disposición
                t = p.extract_text() or ""
            # se conservan los espacios: la columna de cada cifra sale de su posición en la línea
            lineas += [f"### página {i}"] + [x.rstrip() for x in t.splitlines()]
        con_cifras = sum(1 for x in lineas if re.search(r"\d", x) and not x.startswith("### "))
        if OCR["activo"] and (forzar_ocr or con_cifras < 3 * len(lector.pages)):
            # PDF de imágenes (o de trazos) sin texto: lectura óptica
            ocr = lineas_ocr(contenido)
            if ocr:
                return ocr, len(lector.pages)
        return lineas, len(lector.pages)
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:  # CSV de hojas de cálculo antiguas (Windows-1252)
        texto = contenido.decode("cp1252", errors="replace")
    if formato == "html":
        texto = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", texto)
        texto = re.sub(r"(?is)</(tr|p|li|div|h\d)>|<br\s*/?>", "\n", texto)
        texto = re.sub(r"(?is)</t[dh]>", " | ", texto)
        texto = unescape(re.sub(r"<[^>]+>", " ", texto))
    return [re.sub(r"[ \t]+", " ", x).strip() for x in texto.splitlines()], None


def formato_de(contenido: bytes, cabecera: str, url: str) -> str:
    if contenido[:4] == b"%PDF":
        return "pdf"
    if contenido[:2] == b"PK":
        return "xlsx"
    if "json" in cabecera or contenido.lstrip()[:1] in (b"[", b"{"):
        return "json"
    if "csv" in cabecera or re.search(r"[_.]csv(?:\.\w+)?$", url.lower().split("?")[0]):
        return "csv"
    return "html" if "html" in cabecera else "otro"


def medir(contenido: bytes, formato: str, filas: int = MUESTRA_FILAS, forzar_ocr: bool = False) -> dict:
    if formato == "xlsx":
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
        lineas = [" | ".join("" if v is None else str(v) for v in fila) for h in wb.worksheets
                  for fila in h.iter_rows(values_only=True)]
        paginas = None
    else:
        lineas, paginas = lineas_documento(contenido, formato, forzar_ocr)
    # en CSV y JSON cada línea es un registro (la nota va pegada a su separador): valen todas las que tienen cifras
    con_nota = [x for x in lineas if NOTA.search(x) or formato in ("csv", "json", "xlsx") and re.search(r"\d[.,]\d", x)]
    # con muchas filas pedidas se guarda el documento entero (rótulos de universidad, curso y columnas incluidos)
    guardadas = [x for x in lineas if x.strip()] if filas >= 10_000 else con_nota
    cursos = sorted({f"{a}-{int(b) + 2000 if len(b) == 2 else b}" for a, b in CURSO.findall(" ".join(lineas[:400]))})
    salida = {"paginas": paginas, "lineas": len(lineas), "filas_con_nota": len(con_nota), "cursos_que_cita": cursos[:12],
              "cabecera": [x for x in lineas[:40] if x.strip()][:25], "muestra": guardadas[:filas]}
    if POSICIONES["activo"] and formato == "pdf" and con_nota:
        ocr = bool(lineas) and "(lectura óptica)" in lineas[0]
        salida["posiciones"] = posiciones_ocr(contenido) if ocr else posiciones_pdf(contenido)
    return salida


def consultar(q: dict, archivo: Archivo, filas: int) -> dict:
    """Una consulta POST de un formulario oficial (robots.txt comprobado por motor.http.obtener), con su original."""
    from motor.http import obtener

    url = q["url"] + ("&" if "?" in q["url"] else "?") + "&".join(f"{k}={v}" for k, v in q["campos"].items())
    doc = {"url": url, "origen": "consulta", "campos": q["campos"]}
    time.sleep(2)
    try:
        r = obtener(q["url"], formulario=q["campos"], timeout=60, limite_total=180)
    except Exception as e:  # noqa: BLE001 - robots.txt o red: se anota y se sigue
        return {**doc, "estado": None, "error": f"{type(e).__name__}: {str(e)[:160]}"}
    doc["estado"] = r.status
    if r.status == 200:
        cab = (r.cabeceras or {}).get("Content-Type") or (r.cabeceras or {}).get("content-type") or "text/html"
        formato = formato_de(r.contenido, cab.lower(), url)
        medida = medir(r.contenido, formato, filas)
        if DNI.search("\n".join(medida.get("muestra") or [])):
            return {**doc, "omitido": "datos_de_personas"}
        archivo.guardar(FUENTE, date.today(), r.contenido, url, formato, r.status, None)
        doc.update(formato=formato, bytes=len(r.contenido), sha256=hashlib.sha256(r.contenido).hexdigest(), **medida)
    return doc


def ejecutar(salida: Path, solo: list[str] | None = None, max_minutos: float = 50, filas: int = MUESTRA_FILAS,
             extra: dict[str, list[str]] | None = None) -> dict:
    from motor.estudios.rastreador import Dominio

    archivo = Archivo(salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    destino = salida / "datos" / "estudios" / "grados" / "notas_fuentes"
    destino.mkdir(parents=True, exist_ok=True)
    fin = time.time() + max_minutos * 60
    dominios: dict[str, Dominio] = {}
    resumen = {}

    def pedir(url: str):
        host = urlparse(url).netloc
        d = dominios.setdefault(host, Dominio(f"https://{host}", archivo, pausa=1.5, max_peticiones=60))
        return d.get(url, guardar=False)

    for clave, s in SEMILLAS.items():
        if solo and clave not in solo:
            continue
        res = {"distrito": clave, "nombre": s["nombre"], "capturado": date.today().isoformat(), "indices": [],
               "documentos": []}
        candidatos: dict[str, str] = {u: "conocido" for u in s.get("ficheros", []) + (extra or {}).get(clave, [])}
        for p in s.get("patrones", []):
            for u in cursos_patron(p):
                candidatos.setdefault(u, "patron")
        for u in s.get("indices", []):
            if time.time() > fin:
                break
            r = pedir(u)
            info = {"url": u, "estado": r.status_code if r is not None else None}
            if r is not None and r.status_code == 200:
                ls = enlaces(r.text, r.url)
                info.update(enlaces=[{"url": a, "texto": t} for a, t in ls][:150], formularios=formularios(r.text, r.url))
                if info["formularios"]:
                    info["funciones"] = funciones_de_envio(r.text, r.url, pedir)
                for a, _ in ls[:60]:
                    candidatos.setdefault(a, "enlazado")
            res["indices"].append(info)
        fallidas: set[str] = set()
        for q in s.get("consultas", []):
            if time.time() > fin:
                break
            if q["url"] in fallidas:
                continue  # una dirección que no respondió con datos no se vuelve a pedir con otros campos
            doc = consultar(q, archivo, filas)
            res["documentos"].append(doc)
            if doc.get("estado") != 200 or doc.get("formato") == "html" and not doc.get("filas_con_nota"):
                fallidas.add(q["url"])
        for u, origen in candidatos.items():
            if time.time() > fin:
                res["sin_tiempo"] = True
                break
            if PERSONAS.search(u):
                res["documentos"].append({"url": u, "origen": origen, "omitido": "lista_de_personas"})
                continue
            r = pedir(u)
            doc = {"url": u, "origen": origen, "estado": r.status_code if r is not None else None}
            if r is not None and r.status_code == 200 and len(r.content) <= MAX_DOC:
                formato = formato_de(r.content, (r.headers.get("content-type") or "").lower(), u)
                try:
                    medida = medir(r.content, formato, filas, any(z in u for z in OCR_SIEMPRE))
                except Exception as e:  # noqa: BLE001 - un documento roto no para el resto
                    medida = {"error": f"{type(e).__name__}: {str(e)[:160]}"}
                if DNI.search("\n".join(medida.get("muestra") or []) + "\n".join(medida.get("cabecera") or [])):
                    # trae identificadores de personas: ni original ni filas
                    res["documentos"].append({**doc, "omitido": "datos_de_personas"})
                    continue
                archivo.guardar(FUENTE, date.today(), r.content, u, formato if formato != "otro" else "bin",
                                r.status_code, {k: v for k, v in r.headers.items()
                                                if k.lower() in {"content-type", "last-modified"}})
                doc.update(formato=formato, bytes=len(r.content), sha256=hashlib.sha256(r.content).hexdigest(),
                           ultima_modificacion=r.headers.get("last-modified"), **medida)
            res["documentos"].append(doc)
        (destino / f"{clave}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        resumen[clave] = {"indices_leidos": sum(1 for i in res["indices"] if i["estado"] == 200),
                          "documentos": len(res["documentos"]),
                          "bajados": sum(1 for d in res["documentos"] if d.get("sha256")),
                          "con_notas": sum(1 for d in res["documentos"] if d.get("filas_con_nota"))}
    (destino / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    return resumen


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", required=True)
    p.add_argument("--solo", help="distritos separados por comas")
    p.add_argument("--max-minutos", type=float, default=50)
    p.add_argument("--filas", type=int, default=MUESTRA_FILAS, help="filas con nota que se guardan de cada documento")
    p.add_argument("--extra", action="append", default=[], help="distrito=url: un documento más que leer")
    p.add_argument("--ocr", action="store_true", help="lectura óptica de los PDF sin texto (pdftoppm y tesseract)")
    p.add_argument("--posiciones", action="store_true", help="guarda la posición de cada fragmento de los PDF con notas")
    a = p.parse_args()
    OCR["activo"] = a.ocr
    POSICIONES["activo"] = a.posiciones
    extra: dict[str, list[str]] = defaultdict(list)
    for x in a.extra:
        k, _, u = x.partition("=")
        extra[k].append(u)
    print(json.dumps(ejecutar(Path(a.salida), a.solo.split(",") if a.solo else None, a.max_minutos, a.filas, extra),
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
