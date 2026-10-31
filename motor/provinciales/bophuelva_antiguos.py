"""BOP de Huelva anterior al 20/06/2023: el PDF del boletín entero de cada día, con su sumario y sus anuncios.

Formato verificado el 31/10/2026 desde el servidor de España (sondas de la página del día, 30/10 a las 23:54, y del
PDF del 19/06/2023, 31/10 a las 09:31):
  - El archivo es https://s2.diphuelva.es/servicios/bop/ (enlace «BOP Anteriores a 20/06/2023» de la sede). La página
    de cada día, servicios/bop/busqueda/?fecha=DD/MM/AAAA, enseña el boletín en un visor que carga
    /portalweb/bop/boletines/AAAAMMDD-1.pdf (el número tras el guion, por si hay más de uno ese día).
  - Las dos primeras páginas del PDF traen el sumario por secciones («ADMINISTRACIÓN LOCAL»): la entidad tras un
    guion («– Ayuntamiento de Cartaya») y, debajo, cada asunto con puntos hasta su página («Aprobación de la lista
    definitiva de admitidos y excluidos… ......... 5169»). Las páginas siguen la numeración del año.
  - Cada página del cuerpo empieza por «BOLETIN OFICIAL HUELVA N.º 115 19 de Junio de 2023 5135» (las pares, con el
    número de página delante) y acaba con el pie de firma electrónica del boletín («Diputación Provincial de Huelva.
    Boletín Oficial de la Provincia», «Documento firmado electrónicamente…», «Autenticidad verificable…»).
  - Cada anuncio empieza por la entidad en mayúsculas («EXCMA. DIPUTACIÓN PROVINCIAL DE HUELVA») y el tipo
    («RESOLUCIÓN», «ANUNCIO», «EDICTO»).
  - pypdf saca las ligaduras con espacios («de ﬁ nitivas», «modi ﬁ cación»).
  - robots.txt de s2.diphuelva.es lo cierra todo; es boletín oficial (motor/http.py, decisión del 30/10/2026). Solo
    responde desde España.

Cada asunto del sumario se casa con un anuncio que empiece en la página que dice: por orden si en esa página empiezan
tantos anuncios como asuntos, y si no por la entidad. Lo que no casa se queda sin texto (nunca con el de otro).
Los identificadores son «BOPHUELVA-AAAA-MM-DD-NNN» (orden en el sumario): este archivo no da el número de anuncio
del sistema nuevo.

Uso: python -m motor.provinciales.bophuelva_antiguos --max-minutos 30 --salida ruta/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.autonomicos.comun import Freno, escribir_json, escribir_jsonl, estado_dia, leer_jsonl, nombre_propio
from motor.boe.clasificar import normalizar
from motor.extraccion.citas import citas
from motor.http import obtener
from motor.limpieza import RE_DOCUMENTO, limpiar_texto, titulo_sin_nombres
from motor.provinciales import bophuelva as bh
from motor.provinciales.comun import CON_TEXTO, ruta_texto_pdf

INICIO = date(2022, 1, 1)
FIN = bh.INICIO - timedelta(days=1)  # 19/06/2023: desde el 20 está el sistema nuevo (bophuelva.py)
VERSION = "pdf_dia_v3"  # v2 (31/10/2026): el enlace al PDF va codificado en el visor («file=%2Fportalweb%2Fbop…»); v3: municipios bajo «AYUNTAMIENTOS» y textos sin el asunto siguiente
WEB = bh.WEB

_MESES = r"(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)"
_FECHA = rf"\d{{1,2}}\s+de\s+{_MESES}\s+de\s+\d{{4}}"
# «BOLETIN OFICIAL HUELVA N.º 115 19 de Junio de 2023 5135» y «5136 19 de Junio de 2023 BOLETIN OFICIAL HUELVA N.º 115»
RE_CABECERA = re.compile(
    rf"(?i)^\s*(?:(?P<a>\d{{1,5}})\s+{_FECHA}\s+BOLET[IÍ]N\s+OFICIAL\s+(?:DE\s+(?:LA\s+PROVINCIA\s+DE\s+)?)?HUELVA"
    rf"(?:\s+N\.?\s*[º°]?\s*\d+)?|BOLET[IÍ]N\s+OFICIAL\s+(?:DE\s+(?:LA\s+PROVINCIA\s+DE\s+)?)?HUELVA"
    rf"(?:\s+N\.?\s*[º°]?\s*\d+)?\s+{_FECHA}\s+(?P<b>\d{{1,5}}))\s*$")
RE_PIE = re.compile(r"(?i)^\s*(?:Diputaci[oó]n Provincial(?: de Huelva\.?(?: Bolet[ií]n Oficial de la Provincia)?)?\s*$|"
                    r"Documento firmado electr[oó]nicamente|Autenticidad verificable)")
RE_NUMERO_BOLETIN = re.compile(rf"(?i){_FECHA}\s+N[úu]mero\s+(?P<n>\d{{1,4}})")
# «ADMINISTRACIÓN LOCAL», «ADMINISTRACIÓN ELECTORAL» (suplementos de elecciones), «JUNTA DE ANDALUCÍA»…
RE_SECCION = re.compile(r"^(?:ADMINISTRACI[ÓO]N(?:\s+[A-ZÁÉÍÓÚÑ]+(?:\s+(?:DE|DEL|LA|DE LA)?\s*[A-ZÁÉÍÓÚÑ]+){0,3})?|"
                        r"JUNTA DE ANDALUC[ÍI]A|ANUNCIOS(?: PARTICULARES| OFICIALES)?|"
                        r"OTR[OA]S ANUNCIOS|OTRAS ADMINISTRACIONES|OTRAS ENTIDADES|DIPUTACI[ÓO]N PROVINCIAL|AYUNTAMIENTOS|JUNTAS ELECTORALES|MANCOMUNIDADES|ENTIDADES LOCALES(?: AUT[ÓO]NOMAS)?)$")
RE_ENTIDAD_SUMARIO = re.compile(r"^\s*[–—-]\s+(?P<e>\S.*)$")
# puntos hasta la página, o uno solo con dos espacios («…de empleo temporal .  5173»)
RE_FIN_ASUNTO = re.compile(r"^(?P<t>.*?)(?:\s*(?:[.…·]\s*){2,}|\s*[.…·]\s{2,})\s*(?P<p>\d{1,5})\s*$")
RE_TIPO = re.compile(r"^(?:ANUNCIOS?|RESOLUCI[ÓO]N(?:ES)?|EDICTOS?|DECRETOS?|ACUERDOS?|CORRECCI[ÓO]N(?: DE ERRORES)?|"
                     r"EXTRACTOS?|NOTIFICACI[ÓO]N(?:ES)?|INFORMACI[ÓO]N(?: P[ÚU]BLICA)?|BANDO|ORDEN|CONVOCATORIA|"
                     r"AVISO|LICITACI[ÓO]N)\b[^a-zñáéíóú]*$")


def url_dia(d: date) -> str:
    return f"{WEB}/servicios/bop/busqueda/?fecha={d:%d/%m/%Y}"


def enlaces_pdf(contenido: bytes, d: date) -> list[str]:
    """Los PDF del boletín de ese día que enlaza su página (en su orden; sin repetir)."""
    from urllib.parse import unquote
    # el visor lleva la dirección codificada: «viewer.html?file=%2Fportalweb%2Fbop%2Fboletines%2F20230619-1.pdf»
    texto = unquote(contenido.decode("latin-1", errors="replace"))
    vistos = []
    for m in re.finditer(rf"(?:https?://s2\.diphuelva\.es)?/portalweb/bop/boletines/{d:%Y%m%d}-(\d+)\.pdf", texto):
        u = f"{WEB}/portalweb/bop/boletines/{d:%Y%m%d}-{m.group(1)}.pdf"
        if u not in vistos:
            vistos.append(u)
    return vistos


_CORTAS = {"de", "la", "el", "en", "a", "y", "e", "o", "que", "los", "las", "del", "con", "por", "se", "su", "sus", "al",
           "lo", "un", "una", "para", "sin", "es"}


def sin_ligaduras(texto: str) -> str:
    """«de ﬁ nitivas» -> «definitivas», «modi ﬁ cación» -> «modificación», «la ﬁ nalidad» -> «la finalidad»."""
    def unir(m: re.Match) -> str:
        antes, lig = m.group(1), {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl"}[m.group(2)]
        palabra = re.search(r"(\w+)$", antes)
        previa = palabra.group(1).lower() if palabra else ""
        if previa and (previa not in _CORTAS or (previa == "de" and re.match(r"nitiv", m.string[m.end():]))):
            return antes + lig  # trozo de palabra delante (o «de ﬁ nitiva»): se junta
        return antes + (" " if antes and not antes.endswith(" ") and previa else "") + lig
    t = re.sub(r"(\S*)\s?([ﬁﬂﬀﬃﬄ])\s?(?=[a-záéíóúñ])", unir, texto)
    return t.replace("ﬁ", "fi").replace("ﬂ", "fl").replace("ﬀ", "ff").replace("ﬃ", "ffi").replace("ﬄ", "ffl")


def numero_de_pagina(texto: str) -> int | None:
    for lin in texto.splitlines()[:4]:
        if (m := RE_CABECERA.match(lin)):
            return int(m.group("a") or m.group("b"))
    return None


def _mayusculas(lin: str) -> bool:
    letras = [c for c in lin if c.isalpha()]
    return len(letras) >= 3 and all(c.isupper() for c in letras)


def _unir(lineas: list[str]) -> str:
    texto = ""
    for lin in lineas:
        lin = lin.strip()
        if texto.endswith("-") and lin[:1].islower():
            texto = texto[:-1] + lin
        else:
            texto = f"{texto} {lin}" if texto else lin
    return " ".join(texto.split())


def sumario(paginas: list[str]) -> list[dict]:
    """Asuntos del sumario (páginas antes de la primera con cabecera): sección, entidad, título y página."""
    lineas: list[str] = []
    for p in paginas:
        if numero_de_pagina(p) is not None:
            break
        lineas += [l for l in p.splitlines() if l.strip() and not RE_PIE.match(l)]
    out, seccion, entidad, buf, empezado = [], None, None, [], False
    k = 0
    while k < len(lineas):
        bruto = lineas[k].strip()
        lin = " ".join(bruto.split())
        k += 1
        if RE_SECCION.match(lin):
            seccion, entidad, buf, empezado = nombre_propio(lin), None, [], True
            continue
        if not empezado:
            continue
        if (m := RE_ENTIDAD_SUMARIO.match(lin)) and not buf:
            partes = [m.group("e")]
            # la entidad sigue en la línea de abajo si esta empieza en minúscula («de Huelva»)
            while k < len(lineas) and lineas[k].strip()[:1].islower() and len(lineas[k].split()) <= 5:
                partes.append(lineas[k].strip())
                k += 1
            entidad = " ".join(" ".join(partes).split())
            continue
        if (m := RE_FIN_ASUNTO.match(bruto)):  # con sus espacios: «… temporal .  5173»
            buf.append(" ".join(m.group("t").split()))
            titulo = sin_ligaduras(_unir(buf))
            if titulo:
                out.append({"seccion": seccion, "entidad": entidad, "titulo": titulo_sin_nombres(titulo[:600]),
                            "pagina": int(m.group("p"))})
            buf = []
            continue
        buf.append(lin)
    return out


def _clave_entidad(e: str | None) -> str:
    n = normalizar(sin_ligaduras(e or ""))
    n = re.sub(r"\b(?:excmo|excma|ilmo|ilma|iltre|ilustre|excelentisimo|excelentisima|ilustrisimo|ilustrisima|sr|sra)\b\.?", " ", n)
    return " ".join(re.sub(r"[^a-z0-9ñ ]+", " ", n).split())


RE_TIPO_ENTIDAD = re.compile(r"^(?:AYUNTAMIENTO|MANCOMUNIDAD|ENTIDAD|CONSORCIO|EXCM|ILMO|ILTRE|PATRONATO|INSTITUTO|"
                             r"ORGANISMO|EMPRESA|FUNDACI|SOCIEDAD|AGENCIA|COMUNIDAD|JUNTA|DIPUTACI|E\.?L\.?A)")


def cuerpo(paginas: list[str]) -> tuple[list[tuple[int, str]], list[dict]]:
    """Líneas del cuerpo con su página del boletín (sin cabeceras ni pies) y los comienzos de anuncio que se ven:
    una entidad en mayúsculas (una o dos líneas) seguida del tipo («RESOLUCIÓN», «ANUNCIO»…)."""
    lineas: list[tuple[int, str]] = []
    for p in paginas:
        num = numero_de_pagina(p)
        if num is None:
            continue
        for lin in p.splitlines():
            if not lin.strip() or RE_CABECERA.match(lin) or RE_PIE.match(lin):
                continue
            lineas.append((num, " ".join(sin_ligaduras(lin).split())))
    comienzos = []
    seccion = None
    for i, (num, lin) in enumerate(lineas):
        if RE_SECCION.match(lin):
            seccion = lin
        if not RE_TIPO.match(lin) or i == 0:
            continue
        j = i - 1
        while j >= 0 and i - j <= 2 and _mayusculas(lineas[j][1]) and not RE_SECCION.match(lineas[j][1]) \
                and not RE_TIPO.match(lineas[j][1]):
            j -= 1
        if j == i - 1:
            continue  # sin entidad encima no es un comienzo
        ini = j + 1
        if comienzos and comienzos[-1]["linea"] >= ini:
            continue
        entidad = " ".join(l for _, l in lineas[ini:i])
        # bajo «AYUNTAMIENTOS» el cuerpo solo nombra el municipio («CARTAYA»), y el sumario dice «Ayuntamiento de…»
        if seccion == "AYUNTAMIENTOS" and not RE_TIPO_ENTIDAD.match(entidad):
            entidad = "AYUNTAMIENTO DE " + entidad
        comienzos.append({"linea": ini, "pagina": lineas[ini][0], "entidad": entidad})
    return lineas, comienzos


def casar(asuntos: list[dict], comienzos: list[dict]) -> dict[int, int]:
    """Índice del asunto -> índice del comienzo: por orden en la página si coinciden en número; si no, por la entidad
    (la primera libre de esa página con la misma entidad)."""
    out: dict[int, int] = {}
    paginas = sorted({a["pagina"] for a in asuntos})
    for p in paginas:
        ia = [i for i, a in enumerate(asuntos) if a["pagina"] == p]
        ic = [j for j, c in enumerate(comienzos) if c["pagina"] == p]
        if len(ia) == len(ic) and all(_misma_entidad(asuntos[i]["entidad"], comienzos[j]["entidad"]) for i, j in zip(ia, ic)):
            out.update(zip(ia, ic))
            continue
        libres = list(ic)
        for i in ia:
            j = next((j for j in libres if _misma_entidad(asuntos[i]["entidad"], comienzos[j]["entidad"])), None)
            if j is not None:
                out[i] = j
                libres.remove(j)
    return out


def tramos_de_texto(asuntos: list[dict], comienzos: list[dict], lineas: list[tuple[int, str]],
                    casados: dict[int, int]) -> dict[int, tuple[int, int]]:
    """Índice del asunto -> (primera línea, fin) de su texto: desde su comienzo hasta el comienzo siguiente, como
    mucho hasta el final de la página donde empieza el asunto siguiente. Si el comienzo del siguiente no se vio, su
    texto (quizá una lista de personas) no puede ir en este: hasta su página, y nada si empieza en la misma."""
    out: dict[int, tuple[int, int]] = {}
    for i, j in casados.items():
        ini = comienzos[j]["linea"]
        fin = comienzos[j + 1]["linea"] if j + 1 < len(comienzos) else len(lineas)
        sig = next((b["pagina"] for b in asuntos[i + 1:] if b["pagina"] >= asuntos[i]["pagina"]), None)
        if sig is not None:
            fin = min(fin, next((k for k in range(ini, len(lineas)) if lineas[k][0] > sig), len(lineas)))
            if i + 1 < len(asuntos) and i + 1 not in casados:
                if sig <= lineas[ini][0]:
                    continue
                fin = min(fin, next((k for k in range(ini, len(lineas)) if lineas[k][0] >= sig), len(lineas)))
        out[i] = (ini, fin)
    return out


def _misma_entidad(a: str | None, b: str | None) -> bool:
    ka, kb = _clave_entidad(a), _clave_entidad(b)
    return bool(ka and kb) and (ka == kb or ka in kb or kb in ka)


def entidad_local(entidad: str | None) -> str | None:
    if not entidad:
        return None
    return nombre_propio(entidad) if entidad.isupper() else entidad


def leer_pdf(d: date, url_pdf: str, pdf: bytes, captura: dict, raiz: Path, orden_inicial: int = 0) -> dict:
    from motor.pdf import paginas as paginas_pdf
    pags = paginas_pdf(pdf)
    asuntos = sumario(pags)
    lineas, comienzos = cuerpo(pags)
    casados = casar(asuntos, comienzos)
    tramos = tramos_de_texto(asuntos, comienzos, lineas, casados)
    m = RE_NUMERO_BOLETIN.search(pags[0] if pags else "")
    numero = m.group("n") if m else None
    filas, textos = [], {}
    for i, a in enumerate(asuntos):
        x = {"orden": orden_inicial + i + 1, "seccion": a["seccion"], "entidad": entidad_local(a["entidad"]),
             "titulo": a["titulo"], "pagina": a["pagina"],
             "id": f"BOPHUELVA-{d.isoformat()}-{orden_inicial + i + 1:03d}", "fecha": d.isoformat(), "boletin": numero,
             "url_pdf": None, "url_pdf_boletin": url_pdf, "fuente": bh.SIGLAS, "captura_sha256": captura["sha256"]}
        filas.append(x)
        if i in tramos:
            ini, fin = tramos[i]
            textos[x["id"]] = ("\n".join(l for _, l in lineas[ini:fin]), sorted({p for p, _ in lineas[ini:fin]}))
    empleo = bh.seleccionar(filas)
    escribir_jsonl(bh._ruta(raiz, "disposiciones", d), _con_previos(raiz, d, filas, orden_inicial))
    escribir_jsonl(bh._ruta(raiz, "oposiciones", d), _con_previos(raiz, d, empleo, orden_inicial, carpeta="oposiciones"))
    base = bh._base(raiz)
    con_texto = 0
    for x in empleo:
        if x["id"] not in textos:
            continue
        bruto, paginas_usadas = textos[x["id"]]
        if x.get("tipo_acto") in CON_TEXTO:
            datos = {"titulo": x["titulo"], **{k: v for k, v in limpiar_texto(bruto).items() if k != "titulo"}}
        else:  # listas de personas: solo cuántas líneas traen un documento de identidad, y las citas a boletines
            datos = {"titulo": x["titulo"], "texto": None, "tablas": [], "solo_recuento": True,
                     "lineas_con_documento_de_identidad": sum(1 for l in bruto.splitlines() if RE_DOCUMENTO.search(l)),
                     "citas": citas(bruto)}
        escribir_json(ruta_texto_pdf(base, x), {"id": x["id"], **datos, "paginas": paginas_usadas,
                                                "captura_sha256": captura["sha256"],
                                                "capturado": captura.get("capturado"), "url": url_pdf})
        con_texto += 1
    inf = {"fecha": d.isoformat(), "status": 200, "resultado": "ok", "origen": "pdf_dia", "version": VERSION,
           "sha256": captura["sha256"], "url_pdf": url_pdf, "numero": numero, "disposiciones": len(filas),
           "empleo_publico": len(empleo), "textos": con_texto, "comienzos": len(comienzos),
           "casados": len(casados), "alertas": []}
    if not asuntos:
        inf["resultado"] = "sin_anuncios"
        inf["alertas"].append(f"{bh.SIGLAS} {d}: PDF sin asuntos en el sumario (posible cambio de formato)")
    elif len(casados) < len(asuntos) / 2:
        inf["alertas"].append(f"{bh.SIGLAS} {d}: solo {len(casados)} de {len(asuntos)} asuntos casan con un anuncio "
                              f"del cuerpo ({len(comienzos)} comienzos vistos)")
    return inf


def _con_previos(raiz: Path, d: date, filas: list[dict], orden_inicial: int, carpeta: str = "disposiciones") -> list[dict]:
    """Con un segundo boletín el mismo día (extraordinario), se añaden sus filas a las del primero."""
    if not orden_inicial:
        return filas
    from motor.autonomicos.comun import leer_jsonl
    ruta = bh._ruta(raiz, carpeta, d)
    previos = [x for x in leer_jsonl(ruta) if x.get("orden", 0) <= orden_inicial] if ruta.exists() else []
    return previos + filas


def procesar_dia(d: date, raiz: Path, archivo: Archivo, pausa: float) -> dict:
    url = url_dia(d)
    r = obtener(url, accept="text/html")
    if r.status == 404:
        return {"fecha": d.isoformat(), "status": 404, "resultado": "sin_boletin", "alertas": []}
    if r.status != 200:
        return {"fecha": d.isoformat(), "status": r.status, "resultado": "error_http",
                "alertas": [f"{bh.SIGLAS} {d}: página del día HTTP {r.status}"]}
    pdfs = enlaces_pdf(r.contenido, d)
    if not pdfs:
        return {"fecha": d.isoformat(), "status": 200, "resultado": "sin_boletin", "nota": "sin PDF", "version": VERSION,
                "alertas": []}
    informes, orden = [], 0
    for u in pdfs:
        time.sleep(pausa)
        rp = obtener(u, accept="application/pdf, */*")
        if rp.status == 404:
            continue
        if rp.status != 200 or rp.contenido[:4] != b"%PDF":
            return {"fecha": d.isoformat(), "status": rp.status, "resultado": "error_http",
                    "alertas": [f"{bh.SIGLAS} {d}: PDF HTTP {rp.status} ({u})"]}
        captura = archivo.guardar(bh.FUENTE + "-boletin", d, rp.contenido, u, "pdf", rp.status, rp.cabeceras)
        inf = leer_pdf(d, u, rp.contenido, captura, raiz, orden)
        orden += inf["disposiciones"]
        informes.append(inf)
    if not informes:
        return {"fecha": d.isoformat(), "status": 404, "resultado": "sin_boletin", "nota": "PDF 404", "alertas": []}
    if len(informes) == 1:
        return informes[0]
    total = {k: sum(i.get(k, 0) for i in informes) for k in ("disposiciones", "empleo_publico", "textos", "comienzos", "casados")}
    return {**informes[0], **total, "boletines": [{k: i.get(k) for k in ("url_pdf", "numero", "sha256", "disposiciones")}
                                                  for i in informes],
            "resultado": "ok" if any(i["resultado"] == "ok" for i in informes) else informes[0]["resultado"],
            "alertas": [a for i in informes for a in i.get("alertas", [])]}


def _de_version_anterior(ruta: Path) -> bool:
    try:
        inf = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return inf.get("nota") == "sin PDF" and inf.get("version") != VERSION


def _releer(ruta: Path) -> dict | None:
    """Informe de un día leído con una versión anterior en el que no casaron todos los asuntos: se vuelve a leer
    desde el PDF del almacén, sin pedirlo a la fuente."""
    try:
        inf = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if inf.get("resultado") != "ok" or inf.get("version") == VERSION or inf.get("origen") != "pdf_dia":
        return None
    return inf if (inf.get("casados") or 0) < (inf.get("disposiciones") or 0) else None


def releer_desde_almacen(d: date, raiz: Path, anterior: dict) -> dict | None:
    """Vuelve a leer el día con los PDF ya guardados; None si alguno no está en el almacén."""
    from motor.provinciales.textos import original_guardado
    urls = [b["url_pdf"] for b in anterior.get("boletines") or []] or [anterior.get("url_pdf")]
    guardados = [(u, original_guardado(raiz, bh.FUENTE + "-boletin", d.isoformat(), u)) for u in urls if u]
    if not guardados or any(g is None for _, g in guardados):
        return None
    # los textos de la lectura anterior se quitan: los que no salgan ahora no deben quedarse con el corte viejo
    previos = bh._ruta(raiz, "oposiciones", d)
    if previos.exists():
        for x in leer_jsonl(previos):
            if x.get("id", "").startswith(f"BOPHUELVA-{d.isoformat()}-"):
                ruta_texto_pdf(bh._base(raiz), x).unlink(missing_ok=True)
    informes, orden = [], 0
    for u, (pdf, captura) in guardados:
        inf = leer_pdf(d, u, pdf, captura, raiz, orden)
        orden += inf["disposiciones"]
        informes.append(inf)
    if len(informes) == 1:
        return {**informes[0], "nota": "releído desde el almacén"}
    total = {k: sum(i.get(k, 0) for i in informes) for k in ("disposiciones", "empleo_publico", "textos", "comienzos", "casados")}
    return {**informes[0], **total, "nota": "releído desde el almacén",
            "boletines": [{k: i.get(k) for k in ("url_pdf", "numero", "sha256", "disposiciones")} for i in informes],
            "alertas": [x for i in informes for x in i.get("alertas", [])]}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--desde", type=date.fromisoformat, default=INICIO)
    p.add_argument("--hasta", type=date.fromisoformat, default=FIN)
    p.add_argument("--max-minutos", type=float, default=0)
    p.add_argument("--pausa", type=float, default=1.0)
    a = p.parse_args(argv)
    archivo = Archivo(a.salida / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    inicio, informes, freno, d = time.monotonic(), [], Freno(), min(a.hasta, FIN)
    while d >= a.desde:
        ruta = bh._ruta(a.salida, "dias", d, "json")
        hecho, reintento = estado_dia(ruta)
        if hecho and _de_version_anterior(ruta):
            hecho = False  # leído con la v1, que no veía el enlace al PDF
        if hecho and (anterior := _releer(ruta)):
            try:
                nuevo = releer_desde_almacen(d, a.salida, anterior)
            except Exception as e:  # noqa: BLE001 - se queda la lectura anterior
                nuevo = None
                print(f"::warning::{bh.SIGLAS} {d}: no se pudo releer desde el almacén: {type(e).__name__}")
            if nuevo:
                escribir_json(ruta, nuevo)
                informes.append(nuevo)
        if d.weekday() >= 5 and not hecho:
            escribir_json(ruta, {"fecha": d.isoformat(), "resultado": "sin_boletin", "nota": "fin de semana",
                                 "alertas": []})
            hecho = True
        if not hecho:
            if a.max_minutos and (time.monotonic() - inicio) / 60 > a.max_minutos:
                print("Tiempo agotado; se continúa en la siguiente ejecución")
                break
            time.sleep(a.pausa)
            try:
                inf = procesar_dia(d, a.salida, archivo, a.pausa)
            except (ConnectionError, TimeoutError) as e:
                inf = {"fecha": d.isoformat(), "resultado": "fuente_inaccesible", "alertas": [str(e)]}
            except Exception as e:  # noqa: BLE001 - un PDF raro no para la carga: queda anotado para revisarlo
                inf = {"fecha": d.isoformat(), "resultado": "error_formato",
                       "alertas": [f"{bh.SIGLAS} {d}: {type(e).__name__}: {str(e)[:200]}"]}
                print(f"::warning::{inf['alertas'][0]}")
            escribir_json(ruta, inf)
            informes.append(inf)
            print(f"{bh.SIGLAS} {d} (PDF): {inf['resultado']} {inf.get('empleo_publico', '')} "
                  f"{inf.get('casados', '')}/{inf.get('disposiciones', '')}")
            if freno.anotar(inf, reintento=reintento):
                break
        d -= timedelta(days=1)
    asuntos = sum(i.get("disposiciones", 0) for i in informes)
    casados = sum(i.get("casados", 0) for i in informes)
    print(f"::notice title=BOP Huelva anteriores::{len(informes)} días, {asuntos} asuntos, {casados} con su anuncio, "
          f"{sum(i.get('empleo_publico', 0) for i in informes)} de empleo, {sum(i.get('textos', 0) for i in informes)} "
          f"textos o recuentos")
    avisos = [x for i in informes for x in i.get("alertas", [])]
    if avisos:
        print(f"::warning title=BOP Huelva anteriores::{len(avisos)} avisos; p. ej. {' | '.join(avisos[:3])}"[:3000])
    return 1 if any(i.get("resultado") in {"error_formato", "fuente_inaccesible"} for i in informes) else 0


if __name__ == "__main__":
    sys.exit(main())
