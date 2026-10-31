"""Textos de los anuncios de empleo de los BOP sin descarga propia de textos. Mismas reglas que el resto: en listas de
personas (fuera de CON_TEXTO) solo el recuento de líneas con documento de identidad.

  - Con un PDF por anuncio (url_pdf): Zamora, BOTHA, Ávila, Jaén, Salamanca y Burgos.
  - Con el PDF del boletín entero: Lugo y Palencia (página de cada anuncio), Tenerife y Las Palmas (sin página: se
    busca el título). Se descarga el boletín una vez y se corta el texto de cada anuncio de empleo desde su título
    hasta el título del anuncio siguiente; si no se encuentra el título, sin texto (nunca el de otro anuncio).

Uso: python -m motor.provinciales.textos FUENTE --salida ruta/ [--max-minutos 30]
"""

from __future__ import annotations

import argparse
import io
import logging
import re
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import escribir_json, leer_jsonl
from motor.boe.clasificar import normalizar
from motor.extraccion.citas import citas
from motor.http import obtener
from motor.limpieza import RE_DOCUMENTO, limpiar_texto
from motor.provinciales.comun import CON_TEXTO, descargar_textos_pdf, ruta_texto_pdf

# BOP con un PDF por anuncio y sin descarga de textos en su conector
CON_PDF_POR_ANUNCIO = {"bopzamora", "bopalava", "bopavila", "bopjaen", "bopsalamanca", "bopburgos"}
# BOP con el PDF del boletín entero: campo con su dirección
BOLETIN_ENTERO = {"boplugo": "url_pdf", "boppalencia": "url_pdf", "boptenerife": "url_pdf",
                  "boplaspalmas": "url_pdf_boletin", "bopalbacete": "url_pdf_boletin"}
# Cortados por el número de registro del sumario y con las columnas en orden de lectura (ver cortar_por_registro)
POR_REGISTRO = {"boptenerife"}


# Cabeceras y pies de página que no son texto del anuncio, por fuente (líneas enteras)
_DIAS = r"(?:luns|martes|m[ée]rcores|xoves|venres|s[áa]bado|domingo|lunes|mi[ée]rcoles|jueves|viernes)"
CABECERAS = {
    # BOP de Lugo: «54 Núm. 073 – sábado, 29 de marzo de 2025 BOP Lugo», «XOVES, 4 DE XULLO DE 2024 N.º 154»,
    # «R. 0816» (registro al final de cada anuncio), «Anuncio publicado en: Num BOP 73 año 2025 (…)», «Powered by TCPDF»
    "boplugo": re.compile(
        rf"(?i)^(?:(?:\d{{1,4}}\s+)?N[úu]m\.\s*\d+\s*[–-]\s*{_DIAS},?\s+\d{{1,2}}\s+de\s+\w+\s+de\s+\d{{4}}\s+BOP\s+(?:de\s+)?Lugo"
        rf"(?:\s+\d{{1,4}})?|{_DIAS},?\s+\d{{1,2}}\s+de\s+\w+\s+de\s+\d{{4}}\s+N\.?\s?º\s*\d+(?:\s+\d{{1,4}})?|R\.\s?\d{{2,5}}"
        r"|(?:Powered by TCPDF \(www\.tcpdf\.org\)\s*)?Anuncio publicado en: Num BOP .*|Powered by TCPDF.*)$"),
}
CABECERAS["boptenerife"] = re.compile(
    r"(?i)^(?:Bolet[íi]n Oficial de la Provincia de Santa Cruz de Tenerife\.\s*N[úu]mero\s+\d+.*|\d{3,6})$")
# Registro al final de cada anuncio en el BOP de Lugo («R. 0816»): marca dónde acaba un anuncio y empieza el siguiente
RE_REGISTRO = re.compile(r"(?m)^[ \t]*R\.\s?\d{2,5}[ \t]*$")


def _plano(s: str) -> str:
    return re.sub(r"[^a-z0-9ñ]+", " ", normalizar(s or "")).strip()


def paginas_pdf(contenido: bytes) -> list[str]:
    from pypdf import PdfReader
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    return [p.extract_text() or "" for p in PdfReader(io.BytesIO(contenido)).pages]


# Líneas de un sumario: puntos hasta la página o, en el BOP de Albacete, «• Asunto>36» (30/10/2026); en el de
# Tenerife también dos a cuatro puntos y la página al final («… Ayudante Técnico .... 28971», «… temporalidad .. 31443»)
RE_INDICE = re.compile(r"\.{5,}|…{2,}|(?:\. ){4,}|\S\s?>\s?\d{1,4}\s*$|(?:\s\.{2,4}|…)\s?\d{2,6}\s*$")


# Palabras del título con las que se busca: primero muchas y luego menos. En el BOP de Las Palmas muchos títulos de un
# mismo boletín empiezan igual («Bases específicas que regirán la convocatoria del proceso selectivo para la cobertura
# definitiva de una plaza de …»): con doce palabras se tomaba el anuncio de otro (30/10/2026)
LARGOS_TITULO = (24, 18, 12, 8, 5)


class _Compacto:
    """Texto plano sin espacios y, para cada letra, su posición en el plano: «DEFINITIV A» casa con «definitiva»."""

    def __init__(self, plano: str):
        self.posiciones = [k for k, c in enumerate(plano) if c != " "]
        self.texto = "".join(plano[k] for k in self.posiciones)

    def buscar(self, clave: str, desde: int) -> int:
        import bisect
        inicio = bisect.bisect_left(self.posiciones, desde)
        j = self.texto.find(clave.replace(" ", ""), inicio)
        return self.posiciones[j] if j >= 0 else -1


def _posicion(plano: str, titulo: str, desde: int, compacto: _Compacto | None = None) -> int:
    """Dónde empieza el título (sus primeras palabras) en el texto plano del boletín, desde una posición."""
    palabras = _plano(titulo).split()
    compacto = compacto or _Compacto(plano)
    for n in LARGOS_TITULO:
        if len(palabras) >= min(n, 4) and (n == 5 or len(palabras) >= n):
            i = compacto.buscar(" ".join(palabras[:n]), desde)
            if i >= 0:
                return i
    return -1


def es_pagina_de_sumario(pagina: str) -> bool:
    """Página del sumario del propio boletín: muchas líneas con puntos hasta el número de página o de registro."""
    lineas = [l for l in pagina.splitlines() if l.strip()]
    con_puntos = sum(1 for l in lineas if RE_INDICE.search(l))
    return con_puntos >= 4 and con_puntos >= 0.2 * len(lineas)


def sin_entradas_de_sumario(pagina: str) -> str:
    """Quita de una página las entradas de sumario (la línea con puntos hasta la página o «>36» y las líneas del mismo
    asunto que la preceden): en una página con parte de sumario y parte de cuerpo, el título del sumario no se toma
    por el comienzo del anuncio (pasaba en Tenerife y Las Palmas, 30/10/2026)."""
    lineas = pagina.splitlines()
    fuera = set()
    for k, l in enumerate(lineas):
        if RE_INDICE.search(l):
            fuera.add(k)
            # Una entrada que acaba en número de página puede ocupar más líneas (en Tenerife, títulos largos que
            # empiezan por el número de registro, «224574 Anuncio relativo a…»): hasta ocho, y se para en esa línea
            maximo = 8 if RE_PAGINA_FINAL.search(l) else 3
            j = k - 1
            while j >= 0 and k - j <= maximo and lineas[j].strip() and not RE_INDICE.search(lineas[j]) \
                    and not lineas[j].rstrip().endswith((".", ":", ";")):
                fuera.add(j)
                if maximo > 3 and RE_REGISTRO_INICIAL.match(lineas[j]):
                    break
                j -= 1
    return "\n".join(l for k, l in enumerate(lineas) if k not in fuera)


RE_PAGINA_FINAL = re.compile(r"(?:\.|…)\s?\d{1,6}\s*$")
RE_REGISTRO_INICIAL = re.compile(r"^\s*\d{4,7}\s+\S")


def cortar(paginas: list[str], anuncios: list[dict]) -> dict[str, tuple[str, list[int]]]:
    """Texto de cada anuncio del boletín (en su orden): de su título al del siguiente. Con «pagina», la búsqueda
    empieza en su página. Si el título no aparece, el anuncio se queda sin texto (nunca con el de otro)."""
    paginas = [sin_entradas_de_sumario(p) for p in paginas]
    # Las páginas del sumario se dejan en blanco (con su largo) para no confundir sus títulos con los del cuerpo
    planos = [" " * len(_plano(p)) if es_pagina_de_sumario(p) else _plano(p) for p in paginas]
    inicio_pag, acumulado = [], 0
    for p in planos:
        inicio_pag.append(acumulado)
        acumulado += len(p) + 1
    plano = " ".join(planos)
    compacto = _Compacto(plano)
    posiciones, desde = [], 0
    for x in anuncios:
        pag = x.get("pagina")
        base = inicio_pag[pag - 1] if isinstance(pag, int) and 0 < pag <= len(inicio_pag) else desde
        i = _posicion(plano, x.get("titulo") or "", max(base, desde) if not isinstance(pag, int) else base, compacto)
        posiciones.append(i)
        if i >= 0:
            desde = i + 1
    out = {}
    for k, x in enumerate(anuncios):
        i = posiciones[k]
        siguiente = next((p for p in posiciones[k + 1:] if p > i), -1) if i >= 0 else -1
        if i >= 0:
            # Sin anuncio siguiente localizado, como mucho hasta el final de la página siguiente a la de inicio
            pag_ini = max(n for n, ini in enumerate(inicio_pag) if ini <= i)
            tope = inicio_pag[pag_ini + 2] if pag_ini + 2 < len(inicio_pag) else len(plano)
            fin = siguiente if siguiente > i else tope
            pags = [n + 1 for n, ini in enumerate(inicio_pag) if ini <= fin and ini + len(planos[n]) >= i]
        else:
            # Sin el título no se sabe dónde empieza ni acaba (mejor sin texto que con el de otro anuncio), salvo con
            # la página y el registro del anuncio
            pag = x.get("pagina")
            por_registro = _por_registro(paginas, [pag, pag + 1], x.get("registro")) if isinstance(pag, int) else None
            if por_registro:
                out[x["id"]] = por_registro
            continue
        # Con el registro del anuncio (BOP de Lugo), de la marca «R. NNNN» anterior a la suya: así no entra el final
        # del anuncio anterior ni los siguientes aunque el título del sumario no esté igual en el cuerpo (30/10/2026)
        por_registro = _por_registro(paginas, pags, x.get("registro"))
        if por_registro:
            out[x["id"]] = por_registro
            continue
        # El texto se toma de las páginas originales (con sus saltos de línea), recortado a lo que toca si se puede
        bruto = "\n".join(paginas[n - 1] for n in pags if 0 < n <= len(paginas))
        if i >= 0:
            ini_txt = _posicion_bruto(bruto, x.get("titulo") or "")
            sig_t = anuncios[k + 1].get("titulo") if k + 1 < len(anuncios) else None
            fin_txt = _posicion_bruto(bruto, sig_t, ini_txt + 1) if sig_t else -1
            bruto = bruto[max(ini_txt, 0):fin_txt if fin_txt > ini_txt else None]
        out[x["id"]] = (bruto, pags)
    return out


def _por_registro(paginas: list[str], pags: list[int], registro) -> tuple[str, list[int]] | None:
    reg = str(registro or "").strip()
    if not reg.isdigit() or not pags:
        return None
    nums = [n for n in range(pags[0], min(pags[-1] + 1, len(paginas)) + 1) if 0 < n <= len(paginas)]
    inicios, completo = [], ""
    for n in nums:
        inicios.append(len(completo))
        completo += paginas[n - 1] + "\n"
    fin = re.search(rf"(?m)^[ \t]*R\.\s?0*{int(reg)}[ \t]*$", completo)
    if not fin:
        return None
    previas = list(RE_REGISTRO.finditer(completo, 0, fin.start()))
    ini = previas[-1].end() if previas else 0
    usadas = [n for n, i0 in zip(nums, inicios) if i0 <= fin.start() and i0 + len(paginas[n - 1]) >= ini]
    return completo[ini:fin.start()], usadas


def _posicion_bruto(bruto: str, titulo: str | None, desde: int = 0) -> int:
    """Posición aproximada del título en el texto original: la primera línea en la que empiezan sus primeras palabras
    (con más palabras primero, como en _posicion)."""
    if not titulo:
        return -1
    palabras = _plano(titulo).split()
    lineas, pos = [], 0
    for linea in bruto.splitlines(keepends=True):
        lineas.append((pos, linea))
        pos += len(linea)
    for n in LARGOS_TITULO:
        if not palabras or (n != 5 and len(palabras) < n):
            continue
        clave = " ".join(palabras[:n]).replace(" ", "")
        for p0, linea in lineas:
            if p0 < desde:
                continue
            ventana = _plano(linea + " " + bruto[p0 + len(linea):p0 + len(linea) + 40 * n]).replace(" ", "")
            if ventana.startswith(clave) or clave in _plano(linea).replace(" ", ""):
                return p0
    return -1


# --- BOP de Santa Cruz de Tenerife (31/10/2026) ---------------------------------------------------------------------
# El cuerpo va a dos columnas y el texto plano de pypdf las mezcla (una columna antes que la otra, o trozos de las dos),
# y el título del sumario no se repite en el cuerpo: cada anuncio empieza con la cabecera de su órgano, «ANUNCIO» y
# una línea con su número y su número de registro («4640 2187336»). El sumario del PDF da el registro de cada asunto
# («2187336 Anuncio relativo a la adjudicación … ...... 29612»). Así que se lee con la disposición de la página, se
# ponen las columnas en orden de lectura y se corta de la línea de registro de un anuncio a la del siguiente.

RE_MARCA_REGISTRO = re.compile(r"^\s*(\d{1,5})\s+(\d{5,8})\s*$")
RE_ENTRADA_SUMARIO = re.compile(r"^\s*(\d{5,8})\s+(\S.*)$")
RE_FIN_ENTRADA = re.compile(r"(?:\.{3,}|…{2,})\s*\d{3,6}\s*$")
RE_ENCABEZADO = re.compile(r"^\s*(?:ANUNCIO|EDICTO|ANUNCIOS?\s+\S.*)\s*$")


def columnas_en_orden(texto: str) -> str:
    """Texto de una página leída con extraction_mode="layout", con las dos columnas en orden de lectura: por tramos,
    primero la columna izquierda y luego la derecha; las líneas que cruzan el hueco entre columnas (títulos, texto a
    toda la anchura) cortan los tramos y quedan en su sitio."""
    from collections import Counter
    lineas = [l.rstrip() for l in texto.splitlines()]
    ancho = max((len(l) for l in lineas), default=0)
    # Comienzo de la columna derecha: donde más líneas tienen texto tras un hueco de tres o más espacios, hacia el centro
    inicios = Counter()
    for l in lineas:
        for m in re.finditer(r"\S {3,}(?=\S)", l):
            if 0.3 * ancho < m.end() < 0.7 * ancho:
                inicios[m.end()] += 1
    if not inicios:
        return texto
    corte, _ = max(((c, sum(n for c2, n in inicios.items() if abs(c2 - c) <= 2)) for c in inicios), key=lambda x: x[1])
    # Dos columnas solo si muchas líneas tienen el hueco en el mismo sitio: en una página a toda la anchura, el texto
    # justificado deja huecos sueltos que pueden coincidir en dos o tres líneas
    con_hueco = sum(n for c, n in inicios.items() if abs(c - corte) <= 2)
    if con_hueco < max(5, 0.2 * sum(1 for l in lineas if l.strip())):
        return texto

    def clase(l: str) -> tuple[str, tuple[str, str] | None]:
        """«partida» (con su izquierda y derecha), «ancha» (cruza el hueco) o «dudosa» (hueco de solo dos espacios)."""
        if len(l) < corte - 1:
            return "partida", (l.strip(), "")
        if not l[:corte - 2].strip():
            return "partida", ("", l.strip())
        # Un hueco que pasa por el comienzo de la columna derecha (las líneas centradas de una cabecera empiezan más
        # a la derecha; el texto justificado o una sangría mueven el comienzo unas letras)
        huecos = [m for m in re.finditer(r"\S( {2,})(?=\S)", l)
                  if m.start(1) <= corte - 2 and m.end() >= corte - 1 or corte - 4 <= m.end() <= corte + 2]
        if not huecos:
            return "ancha", None
        m = min(huecos, key=lambda m: (len(m.group(1)) < 3, abs(m.end() - corte)))
        par = (l[:m.start() + 1].strip(), l[m.end():].strip())
        return ("partida" if len(m.group(1)) >= 3 else "dudosa"), par

    clases = [clase(l) for l in lineas]
    # Una línea con un hueco de solo dos espacios es de dos columnas salvo que las de al lado crucen el hueco
    utiles = [k for k, l in enumerate(lineas) if l.strip()]
    for pos, k in enumerate(utiles):
        if clases[k][0] != "dudosa":
            continue
        vecinas = [clases[utiles[p]][0] for p in (pos - 1, pos + 1) if 0 <= p < len(utiles)]
        clases[k] = ("ancha", None) if vecinas and all(v == "ancha" for v in vecinas) else ("partida", clases[k][1])

    def volcar(filas: list[tuple[str, str]], antes_de_ancha: bool) -> list[str]:
        """Izquierda y luego derecha. Antes de un tramo a toda la anchura, las filas que siguen a la última con texto
        a la derecha son ya de ese tramo (su «ANUNCIO» y su registro, cortos), no del final de la columna izquierda."""
        ultima = max((k for k, (_, d) in enumerate(filas) if d), default=-1)
        corte_cola = len(filas)
        if antes_de_ancha and ultima >= 0:
            # Si la columna izquierda sigue más abajo que la derecha con texto corrido, es suya; la cola empieza en
            # la primera línea en blanco, «ANUNCIO» o registro
            corte_cola = next((k for k in range(ultima + 1, len(filas)) if not filas[k][0]
                               or RE_ENCABEZADO.match(filas[k][0]) or RE_MARCA_REGISTRO.match(filas[k][0])), len(filas))
        cabeza, cola = filas[:corte_cola], filas[corte_cola:]
        return ([i for i, d in cabeza if i or not d] + [d for _, d in filas if d] + [i for i, _ in cola])

    salida, filas = [], []
    for l, (tipo, p) in zip(lineas, clases):
        if tipo == "ancha":
            salida += volcar(filas, True) + [l.strip()]
            filas = []
            continue
        filas.append(p if l.strip() else ("", ""))
    salida += volcar(filas, False)
    return "\n".join(salida)


def paginas_pdf_columnas(contenido: bytes) -> list[str]:
    from pypdf import PdfReader
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    return [columnas_en_orden(p.extract_text(extraction_mode="layout") or "") for p in PdfReader(io.BytesIO(contenido)).pages]


def entradas_sumario(paginas: list[str], con_pagina: bool = False) -> list[tuple]:
    """(registro, asunto[, página del boletín]) de cada entrada del sumario, en su orden: empieza con el registro y
    acaba en los puntos y la página."""
    out, actual = [], None
    for pag in paginas:
        for l in pag.splitlines():
            if RE_MARCA_REGISTRO.match(l):
                return out  # empieza el cuerpo
            m = RE_ENTRADA_SUMARIO.match(l)
            if m and actual is None:
                actual = [m.group(1), m.group(2)]
            elif actual is not None and l.strip():
                actual[1] += " " + l.strip()
            fin = RE_FIN_ENTRADA.search(l) if actual is not None else None
            if fin:
                asunto = RE_FIN_ENTRADA.sub("", actual[1]).rstrip(" .…")
                pagina = int(re.search(r"(\d{3,6})\s*$", l).group(1))
                out.append((actual[0], asunto, pagina) if con_pagina else (actual[0], asunto))
                actual = None
    return out


def primera_pagina(paginas: list[str]) -> int | None:
    """Número de página del boletín que corresponde a la página 1 del PDF (la numeración sigue la del año): la más
    repetida entre las páginas cuyo número sale solo en una de sus primeras líneas."""
    from collections import Counter
    bases = Counter()
    for n, pag in enumerate(paginas, 1):
        for l in [x for x in pag.splitlines() if x.strip()][:3]:
            m = re.match(r"^\s*(\d{3,6})\s*$", l)
            if m:
                bases[int(m.group(1)) - n + 1] += 1
                break
    return bases.most_common(1)[0][0] if bases else None


def _parecido(a: str, b: str) -> bool:
    x, y = _plano(a).replace(" ", ""), _plano(b).replace(" ", "")
    n = min(len(x), len(y), 60)
    return n >= 12 and x[:n] == y[:n]


def cortar_por_registro(paginas: list[str], anuncios: list[dict]) -> dict[str, tuple[str, list[int]]]:
    """Texto de cada anuncio: de la línea con su registro a la cabecera del anuncio siguiente. El registro sale del
    sumario del PDF, casando cada asunto con su entrada en el mismo orden. Sin registro o sin su línea, sin texto."""
    sumario = entradas_sumario(paginas, con_pagina=True)
    registro, j = {}, 0
    for x in anuncios:
        for k in range(j, min(j + 4, len(sumario))):
            if _parecido(x.get("titulo") or "", sumario[k][1]):
                registro[x["id"]], j = sumario[k][0], k + 1
                break
    base = primera_pagina(paginas)
    lineas, pagina_de = [], []
    for n, pag in enumerate(paginas, 1):
        for l in pag.splitlines():
            lineas.append(l)
            pagina_de.append(n)
    marcas = [(k, m.group(2)) for k, l in enumerate(lineas) if (m := RE_MARCA_REGISTRO.match(l))]
    posicion = {}
    for k, reg in marcas:
        posicion.setdefault(reg, k)
    siguientes = {k: (marcas[i + 1][0] if i + 1 < len(marcas) else len(lineas)) for i, (k, _) in enumerate(marcas)}
    # Anuncios del sumario cuya línea de registro no se encuentra (p. ej. la mezcla con la otra columna): el anuncio
    # anterior no puede llegar a su página, porque se llevaría su texto
    perdidos = sorted(p - base + 1 for r, _, p in sumario if r not in posicion) if base else []
    inicio_pag = {}
    for k, n in enumerate(pagina_de):
        inicio_pag.setdefault(n, k)
    out = {}
    for x in anuncios:
        reg = registro.get(x["id"])
        if reg not in posicion:
            continue
        ini = posicion[reg]
        fin = siguientes[ini]
        pag_ini, pag_fin = pagina_de[ini], pagina_de[min(fin, len(lineas)) - 1]
        dentro = [p for p in perdidos if pag_ini <= p <= pag_fin]
        if dentro and dentro[0] == pag_ini:
            continue  # empieza en la misma página que uno perdido: no se sabe dónde acaba (mejor sin texto)
        if dentro:
            fin = inicio_pag.get(dentro[0], fin)
        if fin < len(lineas):
            # Fuera la cabecera del anuncio siguiente: «ANUNCIO» y, antes, su órgano, servicio y sección (líneas sin
            # punto final), como mucho doce
            f = fin - 1
            while f > ini and not lineas[f].strip():
                f -= 1
            if f > ini and RE_ENCABEZADO.match(lineas[f]):
                f -= 1
                vistas = 0
                while f > ini + 1 and vistas < 12 and not lineas[f].rstrip().endswith((".", ":", ";", ")")):
                    vistas += bool(lineas[f].strip())  # las líneas en blanco de la disposición no cuentan
                    f -= 1
                fin = f + 1
        else:
            fin = min(fin, next((k for k in range(ini, len(lineas)) if pagina_de[k] > pagina_de[ini] + 2), fin))
        out[x["id"]] = ("\n".join(lineas[ini + 1:fin]), sorted(set(pagina_de[ini:fin])))
    return out


def original_guardado(raiz: Path, fuente: str, fecha: str, url: str) -> tuple[bytes, dict] | None:
    """El PDF de esa URL si ya se guardó en el almacén (por el índice del archivo), con los datos de su captura."""
    from motor.archivo import almacen_por_defecto
    indice = raiz / "archivo" / "indices" / fuente / f"{fecha[:7]}.jsonl"
    if not indice.exists():
        return None
    reg = next((x for x in leer_jsonl(indice) if x.get("url") == url and x.get("clave") and x.get("status") == 200), None)
    almacen = almacen_por_defecto() if reg else None
    if not almacen:
        return None
    try:
        contenido = almacen.leer(reg["clave"])
    except Exception:  # noqa: BLE001 - si no se puede leer, se pide a la fuente
        return None
    return (contenido, {"sha256": reg["sha256"], "capturado": reg.get("capturado")}) if contenido[:4] == b"%PDF" else None


def textos_boletin_entero(raiz: Path, fuente: str, archivo: Archivo, max_minutos: float, pausa: float) -> tuple[int, int, int]:
    base = raiz / "datos" / "provinciales" / fuente
    campo = BOLETIN_ENTERO[fuente]
    pendientes: dict[str, list[dict]] = defaultdict(list)
    for f in sorted((base / "oposiciones").glob("*/*/*.jsonl"), reverse=True):
        for x in leer_jsonl(f):
            if x.get(campo) and not ruta_texto_pdf(base, x).exists():
                pendientes[(x[campo].split("#")[0], x["fecha"])].append(x)
    inicio, hechos, errores = time.monotonic(), 0, 0
    for (url, fecha), lista in pendientes.items():
        if max_minutos and (time.monotonic() - inicio) / 60 > max_minutos:
            break
        todas = [x for f in (base / "disposiciones").glob(f"{fecha[:4]}/{fecha[5:7]}/{fecha[8:10]}*.jsonl")
                 for x in leer_jsonl(f) if (x.get(campo) or "").split("#")[0] == url]
        todas.sort(key=lambda x: (x.get("pagina") or 0, x.get("orden") or 0))
        if not todas:
            continue
        # Si el PDF ya está en el almacén (una pasada anterior), se lee de allí: no se vuelve a pedir a la fuente
        guardado = original_guardado(raiz, fuente + "-boletin", fecha, url)
        if guardado:
            contenido, captura = guardado
        else:
            time.sleep(pausa)
            try:
                r = obtener(url, accept="application/pdf, */*")
            except (ConnectionError, TimeoutError):
                errores += len(lista)
                continue
            if r.status != 200 or r.contenido[:4] != b"%PDF":
                errores += len(lista)
                continue
            contenido = r.contenido
            captura = archivo.guardar(fuente + "-boletin", date.fromisoformat(fecha), r.contenido, url, "pdf",
                                      r.status, r.cabeceras)
        try:
            if fuente in POR_REGISTRO:
                cortes = cortar_por_registro(paginas_pdf_columnas(contenido), todas)
            else:
                cortes = cortar(paginas_pdf(contenido), todas)
        except Exception:  # un PDF mal formado no detiene la carga
            errores += len(lista)
            continue
        for x in lista:
            if x["id"] not in cortes:
                errores += 1
                continue
            bruto, pags = cortes[x["id"]]
            if x.get("tipo_acto") in CON_TEXTO:
                datos = {"titulo": x.get("titulo"),
                         **{k: v for k, v in limpiar_texto(bruto, CABECERAS.get(fuente)).items() if k != "titulo"}}
            else:
                datos = {"titulo": x.get("titulo"), "texto": None, "tablas": [], "solo_recuento": True,
                         "lineas_con_documento_de_identidad": sum(1 for l in bruto.splitlines() if RE_DOCUMENTO.search(l)),
                         "citas": citas(bruto)}
            escribir_json(ruta_texto_pdf(base, x), {"id": x["id"], **datos, "paginas": pags,
                                                    "captura_sha256": captura["sha256"],
                                                    "capturado": captura["capturado"], "url": url})
            hechos += 1
    total = sum(len(v) for v in pendientes.values())
    return hechos, errores, total - hechos


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("fuente", choices=sorted(CON_PDF_POR_ANUNCIO | set(BOLETIN_ENTERO)))
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    if a.fuente in BOLETIN_ENTERO:
        hechos, errores, pendientes = textos_boletin_entero(a.salida, a.fuente, archivo, a.max_minutos, a.pausa)
    else:
        hechos, errores, pendientes = descargar_textos_pdf(a.salida / "datos" / "provinciales" / a.fuente, a.fuente,
                                                           archivo, a.max_minutos, a.pausa, accept="application/pdf, */*")
    print(f"{a.fuente} textos: {hechos} descargados, {errores} errores, {pendientes} pendientes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
