"""Extracción de la ficha de un programa de máster desde la web de su centro, con cita literal comprobada.

Para cada página de programa (capturada y guardada antes por el rastreador) se pide a Claude Haiku, en
lote, que devuelva los campos de la ficha. Cada campo lleva el valor y la frase literal de la página de la
que sale. Después, sin IA, se comprueba que la cita está de verdad en el texto: si no está, el valor no se
acepta y el campo va a revisión. Así se cumple la regla de la guía: «frase literal obligatoria que se
comprueba en el texto».

El resultado son hechos (una línea por campo) con su captura de origen; la ficha se calcula después desde
los hechos vigentes (docs/modelo-masters.md, §6).

Uso:
  python -m motor.estudios.extraer lote --muestra muestra.jsonl --salida ruta/ [--esperar-min 45] [--hilos 12]
      # todo en una ejecución: descarga cortés de cada página (robots.txt, reserva TDM), lote de la API,
      # espera, comprobación de citas y coste real. Con MOTOR_ORIGINALES=s3, el original de cada página, lo
      # enviado, las respuestas y las citas van al almacén privado (escritura única); lo público, sin textos ajenos
  python -m motor.estudios.extraer retomar --lote-json ruta/lote.json --salida ruta/   # lote que no terminó a tiempo
  python -m motor.estudios.extraer lista-oficiales --paginas-oficiales paginas_oficiales.jsonl --salida muestra.jsonl
  python -m motor.estudios.extraer preparar --paginas ruta/paginas.jsonl --salida ruta/   # crea el lote
  python -m motor.estudios.extraer enviar --lote ruta/lote.jsonl                           # ANTHROPIC_API_KEY
  python -m motor.estudios.extraer recoger --id msgbatch_... --paginas ... --salida ruta/
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import os
import re
import sys
import threading
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

from motor.limpieza import parrafos_seguros

API = "https://api.anthropic.com/v1/messages/batches"
MODELO = os.environ.get("MODELO_EXTRACCION", "claude-haiku-5-5")
MAX_CARACTERES = 60_000  # páginas largas: se recorta por el final (pie, avisos legales)

CAMPOS = {
    "nombre": "nombre exacto del programa",
    "tipo_titulo": "máster universitario oficial | máster de formación permanente / título propio | máster no universitario | experto | especialista | otro",
    "universidad_que_expide": "universidad que expide el título, si la hay",
    "centro_que_imparte": "escuela o centro que lo imparte, si es distinto de la universidad",
    "creditos_ects": "número de créditos ECTS",
    "duracion": "duración (meses, cursos, horas)",
    "modalidad": "presencial | semipresencial | online | varias",
    "sedes": "ciudades o campus",
    "idioma": "idioma o idiomas de impartición",
    "fecha_inicio": "fecha o mes de inicio de la próxima edición",
    "plazo_admision": "fechas de preinscripción o admisión",
    "horario": "horario y si es compatible con trabajar",
    "plazas": "número de plazas",
    "precio_total": "importe total en euros",
    "precio_credito": "importe por crédito en euros",
    "reserva_matricula": "importe de reserva de plaza o matrícula",
    "descuentos_becas": "becas, ayudas, descuentos o financiación",
    "requisitos_acceso": "titulación previa y requisitos de acceso",
    "proceso_admision": "pruebas, entrevista o criterios de selección",
    "asignaturas": "lista de asignaturas o módulos, con créditos si aparecen",
    "practicas": "prácticas en empresa: si hay, duración y créditos",
    "tfm": "trabajo fin de máster: créditos",
    "metodologia": "cómo se imparte: clases, casos, proyectos, sesiones en directo…",
    "evaluacion": "sistema de evaluación, con porcentajes si aparecen",
    "habilita_profesion": "si habilita para una profesión regulada",
    "salidas": "salidas profesionales que declara el centro",
}
SISTEMA = (
    "Eres un extractor de datos para un portal informativo. Lees la página web de un programa de posgrado y "
    "devuelves SOLO un objeto JSON compacto, sin saltos de línea ni texto fuera del JSON. Reglas: "
    "1) Solo lo que dice el texto; nada inventado ni deducido. "
    "2) Incluye SOLO los campos que aparecen en el texto; los que no aparecen no se escriben. "
    "3) Cada campo es {\"v\": valor, \"c\": \"cita\"}, donde la cita es una frase copiada exactamente del texto, "
    "de 3 a 25 palabras, que contiene el dato. "
    "4) Importes en euros como número. Textos (metodología, evaluación, requisitos, horario…) de 30 palabras como "
    "máximo; listas de 8 elementos como máximo. "
    "5) «asignaturas» es una lista de [nombre, créditos o null], hasta 80, y su cita es la de la primera. "
    "6) Si la página no es la de un programa concreto, devuelve {\"no_es_programa\":true}."
)
MAX_TOKENS = 6000
# Claude Haiku 5.5 piensa por defecto (pensamiento adaptativo, esfuerzo «medium») y ese pensamiento se cobra
# como salida y cuenta en max_tokens: en la segunda prueba, 3.668 tokens de salida por página y 9 de 48
# respuestas cortadas. Para copiar datos con su cita no hace falta pensar: se desactiva y se pide esfuerzo bajo
# (https://platform.claude.com/docs/en/build-with-claude/effort, consultada el 30/10/2026).
PENSAMIENTO = {"type": "disabled"}
ESFUERZO = "low"


def _norma(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = re.sub(r"[“”«»\"'’`´]", "", s)
    return " ".join(s.split())


RE_FUERA = re.compile(r"(?is)<!--.*?-->|<(script|style|noscript|svg|nav|footer|template|iframe|form)\b.*?</\1>|<head\b.*?</head>")
RE_BLOQUE_WEB = re.compile(r"(?i)</?(p|div|li|ul|ol|h[1-6]|section|article|aside|header|main|dd|dt|dl|br|tr|table|"
                           r"tbody|thead|blockquote|figcaption|summary|details)\b[^>]*>")
RE_CELDA_FIN = re.compile(r"(?i)</t[dh]\s*>")
TIPOS_LD = {"Course", "EducationalOccupationalProgram", "CourseInstance", "Product", "Offer", "AggregateOffer"}


def _ld_lineas(html: str) -> list[str]:
    """Datos estructurados del programa (Schema.org) como líneas citables: el precio a veces solo está ahí."""
    lineas = []
    for bloque in re.findall(r'(?is)<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html or ""):
        try:
            d = json.loads(bloque.strip())
        except (ValueError, TypeError):
            continue
        pila = d if isinstance(d, list) else d.get("@graph", [d]) if isinstance(d, dict) else []
        while pila:
            x = pila.pop(0)
            if not isinstance(x, dict):
                continue
            tipos = x.get("@type") if isinstance(x.get("@type"), list) else [x.get("@type")]
            if set(map(str, tipos)) & TIPOS_LD:
                campos = {k: x.get(k) for k in ("name", "price", "lowPrice", "highPrice", "priceCurrency",
                                                 "timeRequired", "educationalCredentialAwarded", "numberOfCredits",
                                                 "courseMode", "startDate", "inLanguage") if isinstance(x.get(k), (str, int, float))}
                if campos:
                    lineas.append(f"Schema.org {'/'.join(map(str, tipos))}: " + "; ".join(f"{k}={v}" for k, v in campos.items()))
            for k in ("offers", "hasCourseInstance", "educationalCredentialAwarded"):
                v = x.get(k)
                pila += v if isinstance(v, list) else [v] if isinstance(v, dict) else []
    return lineas


def texto_de_pagina(html: str) -> str:
    """Texto visible de una página web, por líneas, sin menús, pies, formularios ni código; las tablas como
    «celda | celda». Se quitan las líneas con nombres de personas (motor.limpieza) y se añaden los datos
    estructurados del programa. Es lo que ve el modelo y donde se comprueba cada cita."""
    h = RE_FUERA.sub(" ", html or "")
    h = RE_CELDA_FIN.sub(" | ", h)
    h = RE_BLOQUE_WEB.sub("\n", h)
    h = re.sub(r"<[^>]+>", " ", h)
    lineas, previa = [], None
    for linea in html_lib.unescape(h).replace("\xa0", " ").splitlines():
        linea = " ".join(linea.split()).strip(" |")
        if linea and linea != previa:
            lineas.append(linea)
            previa = linea
    guardadas, _ = parrafos_seguros(lineas)
    return "\n".join(guardadas + _ld_lineas(html))[:MAX_CARACTERES]


def peticion(custom_id: str, url: str, texto: str) -> dict:
    esquema = "\n".join(f"- {k}: {v}" for k, v in CAMPOS.items())
    return {
        "custom_id": custom_id,
        "params": {
            "model": MODELO,
            "max_tokens": MAX_TOKENS,
            "thinking": PENSAMIENTO,
            "output_config": {"effort": ESFUERZO},
            "system": [{"type": "text", "text": SISTEMA + "\nCampos:\n" + esquema, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": f"URL: {url}\n\nTEXTO DE LA PÁGINA:\n{texto}"}],
        },
    }


def id_pagina(url: str, sha: str) -> str:
    return hashlib.sha256(f"{url}|{sha}".encode()).hexdigest()[:40]


def verificar(respuesta: dict, texto: str) -> list[dict]:
    """Un hecho por campo; solo se acepta el valor si la cita está literalmente en el texto."""
    base = _norma(texto)
    hechos = []
    for campo in CAMPOS:
        dato = respuesta.get(campo)
        if isinstance(dato, dict) and "v" in dato:  # formato compacto {"v": …, "c": …}
            dato = {"valor": dato.get("v"), "cita": dato.get("c")}
        if not isinstance(dato, dict) or dato.get("valor") in (None, "", []):
            continue
        cita = dato.get("cita") or ""
        ok = len(cita.split()) >= 2 and cita_en_texto(cita, base)
        motivo = None if ok else "cita_no_literal"
        if campo in NUMERICOS:
            n = como_numero(dato.get("valor"))
            if n is None:  # «no indicado», «consultar», «30-40»: no es un número
                ok, motivo = False, motivo or "valor_no_numerico"
            else:
                dato["valor"] = n
        if ok and campo in NUMERICOS and not numero_en_cita(dato.get("valor"), cita):
            ok, motivo = False, "valor_no_en_cita"  # cita literal, pero el número no sale de ella
        if ok and campo in PRECIOS and (MONEDA_NO_EURO.search(cita) or dato.get("valor", 0) > PRECIO_MAXIMO):
            ok, motivo = False, "moneda_no_euro_o_fuera_de_rango"
        hechos.append({"campo": campo, "valor": dato.get("valor") if ok else None,
                       "valor_propuesto": None if ok else dato.get("valor"),
                       "cita": cita, "cita_verificada": ok, "estado": "aceptado" if ok else "revision", "motivo": motivo})
    return hechos


NUMERICOS = {"creditos_ects", "plazas", "precio_total", "precio_credito", "reserva_matricula"}


def leer_numero(t: str):
    """Un número escrito como en España o en inglés: «9.800», «1.500,50», «45,50», «12,5», «12.5», «12,000.50».
    Punto o coma seguidos de exactamente tres cifras son de miles; con una o dos, decimales. Si no, None."""
    t = t.strip()
    if re.fullmatch(r"\d+", t):
        return int(t)
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", t):  # 9.800 / 1.500,50
        ent, _, dec = t.partition(",")
        return float(ent.replace(".", "") + "." + dec) if dec else int(ent.replace(".", ""))
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", t):  # 12,000 / 12,000.50
        ent, _, dec = t.partition(".")
        return float(ent.replace(",", "") + "." + dec) if dec else int(ent.replace(",", ""))
    if re.fullmatch(r"\d+[.,]\d{1,2}", t):  # 45,50 / 12.5 / 1500,50
        return float(t.replace(",", "."))
    return None


def como_numero(valor):
    """9800, «9800», «9.800», «9.800 €», «1.500,50», «12,50» → número; lo demás (texto, rangos, listas) → None."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return valor
    t = re.sub(r"€|euros?|\beur\b|ects|cr[eé]ditos?|plazas?", "", str(valor), flags=re.I).strip()
    t = re.sub(r"(?<=\d)[\s  ](?=\d{3}\b)", ".", t)  # «9 800» con espacio de miles
    if re.search(r"\s", t):
        return None
    try:
        return leer_numero(t)
    except ValueError:
        return None


RE_NUMERO_EN_TEXTO = re.compile(r"(?<![\d.,])(?:\d{1,3}(?:[.   ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)(?![\d])")


def numeros_en(texto: str) -> list[float]:
    """Los números de un texto leídos con las mismas reglas que los valores (cada uno de una sola manera)."""
    out = []
    for m in RE_NUMERO_EN_TEXTO.findall(texto or ""):
        n = leer_numero(re.sub(r"[   ]", ".", m))
        if n is not None:
            out.append(float(n))
    return out


def numero_en_cita(valor, cita: str) -> bool:
    """9800 está en «9.800 €» o «9800€»; 60 en «60 ECTS»; 45,5 en «45,50 €» (y 4550 no). Valores no numéricos:
    no se comprueban aquí (verificar ya los manda a revisión)."""
    v = como_numero(valor)
    if v is None:
        return True
    return any(abs(float(v) - n) < 0.005 for n in numeros_en(cita))


def cita_en_texto(cita: str, base_normalizada: str) -> bool:
    """La cita está literalmente en el texto y no dentro de otra palabra o número («1.500 €» no vale en «11.500 €»)."""
    c = _norma(cita)
    if not c:
        return False
    return re.search(r"(?<!\w)" + re.escape(c) + r"(?!\w)", base_normalizada) is not None


def _json_de(texto: str) -> dict:
    m = re.search(r"\{.*\}", texto, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except ValueError:
        return {}


# ----------------------------------------------------------------------------------------- órdenes


def preparar(paginas: Path, salida: Path) -> dict:
    """paginas.jsonl: {"url", "sha256", "html"} por línea (o "ruta" a la captura)."""
    salida.mkdir(parents=True, exist_ok=True)
    n, reservadas = 0, 0
    with (salida / "lote.jsonl").open("w", encoding="utf-8") as f:
        for linea in paginas.read_text(encoding="utf-8").split("\n"):
            p = json.loads(linea)
            if p.get("reserva_tdm"):  # el titular reservó la minería de datos: no se procesa, solo se enlaza
                reservadas += 1
                continue
            html = p.get("html") or Path(p["ruta"]).read_text(encoding="utf-8", errors="replace")
            texto = texto_de_pagina(html)
            f.write(json.dumps(peticion(id_pagina(p["url"], p["sha256"]), p["url"], texto), ensure_ascii=False) + "\n")
            n += 1
    return {"peticiones": n, "excluidas_por_reserva_tdm": reservadas}


def _cabeceras() -> dict:
    clave = os.environ.get("ANTHROPIC_API_KEY")
    if not clave:
        sys.exit("Falta ANTHROPIC_API_KEY (secreto de GitHub)")
    return {"x-api-key": clave, "anthropic-version": "2023-06-01", "content-type": "application/json"}


def enviar(lote: Path) -> dict:
    reqs = [json.loads(l) for l in lote.read_text(encoding="utf-8").split("\n") if l.strip()]
    r = requests.post(API, headers=_cabeceras(), json={"requests": reqs}, timeout=120)
    r.raise_for_status()
    return r.json()


def recoger(batch_id: str, paginas: Path, salida: Path, esperar_min: float = 50) -> dict:
    fin = time.time() + esperar_min * 60
    while True:
        b = requests.get(f"{API}/{batch_id}", headers=_cabeceras(), timeout=60).json()
        if b.get("processing_status") == "ended" or time.time() > fin:
            break
        time.sleep(60)
    if b.get("processing_status") != "ended":
        return {"estado": b.get("processing_status"), "cuentas": b.get("request_counts")}
    textos = {}
    for linea in paginas.read_text(encoding="utf-8").split("\n"):
        p = json.loads(linea)
        html = p.get("html") or Path(p["ruta"]).read_text(encoding="utf-8", errors="replace")
        textos[id_pagina(p["url"], p["sha256"])] = (p, texto_de_pagina(html))
    r = requests.get(b["results_url"], headers=_cabeceras(), timeout=300)
    salida.mkdir(parents=True, exist_ok=True)
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cuentas = {"paginas": 0, "hechos": 0, "aceptados": 0, "revision": 0, "no_programa": 0, "errores": 0}
    with (salida / "hechos.jsonl").open("w", encoding="utf-8") as f, \
            (salida / "paginas_extraidas.jsonl").open("w", encoding="utf-8") as fp:
        for linea in r.text.split("\n"):
            x = json.loads(linea)
            if x["result"]["type"] != "succeeded" or x["custom_id"] not in textos:
                cuentas["errores"] += 1
                continue
            pagina, texto = textos[x["custom_id"]]
            datos = _json_de("".join(c.get("text", "") for c in x["result"]["message"]["content"]))
            cuentas["paginas"] += 1
            # una línea por página, tenga o no datos: «extraída y sin precio» no es lo mismo que «sin mirar»
            fp.write(json.dumps({"url": pagina["url"], "captura_sha256": pagina["sha256"], "extraido": ahora,
                                 "json_legible": bool(datos),
                                 "texto_sha256": pagina.get("texto_sha256") or hashlib.sha256(texto.encode()).hexdigest(),
                                 "no_es_programa": bool(datos.get("no_es_programa")), "lote": batch_id},
                                ensure_ascii=False) + "\n")
            if datos.get("no_es_programa"):
                cuentas["no_programa"] += 1
                continue
            try:
                verificados = verificar(datos, texto)
            except Exception as e:  # noqa: BLE001 - una respuesta rara no tira la tanda ya pagada
                cuentas["error_verificar_" + type(e).__name__] += 1
                continue
            for h in verificados:
                h.update({"url": pagina["url"], "captura_sha256": pagina["sha256"], "modelo": MODELO,
                          "extraido": ahora, "lote": batch_id})
                f.write(json.dumps(h, ensure_ascii=False) + "\n")
                cuentas["hechos"] += 1
                cuentas["aceptados" if h["estado"] == "aceptado" else "revision"] += 1
    return cuentas


# Precios del lote (Message Batches, 50 % del precio estándar), dólares por millón de tokens, para prompts de
# hasta 100.000 tokens y por encima. Fuente: https://platform.claude.com/docs/en/about-claude/pricing
# (consultada el 30/10/2026). Si cambian, se cambian aquí: el coste se recalcula con los tokens guardados.
PRECIOS_LOTE = {
    "claude-haiku-5-5": {"hasta_100k": {"entrada": 0.05, "salida": 0.25, "escritura_cache": 0.0625, "lectura_cache": 0.005},
                         "mas_de_100k": {"entrada": 0.25, "salida": 1.25, "escritura_cache": 0.3125, "lectura_cache": 0.025}},
}


def coste(uso: dict, modelo: str = MODELO) -> float:
    """Dólares de una petición del lote según su uso (tokens de entrada, caché y salida)."""
    ent = uso.get("input_tokens", 0)
    esc = uso.get("cache_creation_input_tokens", 0) or 0
    lec = uso.get("cache_read_input_tokens", 0) or 0
    sal = uso.get("output_tokens", 0)
    tramo = PRECIOS_LOTE[modelo]["hasta_100k" if ent + esc + lec <= 100_000 else "mas_de_100k"]
    return (ent * tramo["entrada"] + esc * tramo["escritura_cache"] + lec * tramo["lectura_cache"]
            + sal * tramo["salida"]) / 1_000_000


# ------------------------------------------------------------------ almacén privado (S3, escritura única)

FUENTE_PAGINAS = "web-centros"            # mismo nombre de fuente que el rastreador
FUENTE_EXTRACCION = "extraccion-masters"  # lo enviado a la API, sus respuestas y los hechos con su cita


class Guarda:
    """Guarda en el almacén privado (motor/almacen.py) sin sobrescribir nunca: la clave lleva la huella del
    contenido y toda escritura va con If-None-Match: *. Sin almacén (MOTOR_ORIGINALES distinto de s3) no guarda
    nada y la extracción sigue igual. Tras 5 fallos seguidos deja de intentarlo en esta ejecución."""

    def __init__(self, almacen="auto"):
        self.cuentas: Counter = Counter()
        if almacen == "auto":
            from motor.archivo import almacen_por_defecto

            try:
                almacen = almacen_por_defecto()
            except Exception as e:  # noqa: BLE001 - sin credenciales: se avisa y se sigue sin copia privada
                print(f"AVISO almacén: no disponible ({type(e).__name__}: {str(e)[:200]})", flush=True)
                self.cuentas["sin_conexion"] += 1
                almacen = None
        self.almacen = almacen
        self.fallos = 0
        self._cerrojo = threading.Lock()

    @property
    def activa(self) -> bool:
        return self.almacen is not None

    def original(self, fuente: str, contenido: bytes, ext: str, url: str) -> dict:
        a = self.almacen
        if a is None:
            return {}
        try:
            r = a.guardar_original(fuente, datetime.now(timezone.utc).date(), contenido, ext, url)
        except Exception as e:  # noqa: BLE001 - sin copia privada el dato sigue; la página se puede volver a pedir
            with self._cerrojo:
                self.fallos += 1
                self.cuentas["fallos"] += 1
                if self.fallos >= 5 and self.almacen is not None:
                    print("AVISO almacén: 5 fallos seguidos; sin copia privada hasta la próxima ejecución", flush=True)
                    self.almacen = None
            return {"fallo_almacen": f"{type(e).__name__}: {str(e)[:200]}"}
        with self._cerrojo:
            self.fallos = 0
            self.cuentas["nuevos" if r.nuevo else "ya_estaban"] += 1
        return {"clave": r.clave}

    def jsonl(self, fuente: str, filas: list[dict], nombre: str, url: str) -> str | None:
        datos = "".join(json.dumps(f, ensure_ascii=False) + "\n" for f in filas).encode("utf-8")
        return self.original(fuente, datos, nombre, url).get("clave")

    def leer_jsonl(self, clave: str) -> list[dict]:
        if self.almacen is None:
            sys.exit("Sin almacén privado (MOTOR_ORIGINALES=s3 y credenciales): no se puede retomar el lote")
        return [json.loads(l) for l in self.almacen.leer(clave).decode("utf-8").split("\n") if l.strip()]


# ----------------------------------------------------------------------------------- captura cortés


def capturar(urls: list[str], pausa: float = 1.0, hilos: int = 12, guarda: Guarda | None = None,
             fin: float | None = None, procesar=None) -> list[dict]:
    """Descarga cada página con el lector cortés del rastreador: robots.txt de cada servidor y una petición por
    segundo y servidor (las de un mismo servidor van en fila; servidores distintos, a la vez). Devuelve el texto
    de cada página en memoria; el original, intacto, solo va al almacén privado. Nada se escribe en disco.
    Las páginas cuyo titular reserva la minería de textos (TDM) ni se guardan ni se procesan: solo su huella."""
    from concurrent.futures import ThreadPoolExecutor
    from urllib.parse import urlparse

    from motor.estudios.rastreador import Dominio, reserva_tdm, texto_de

    por_host: dict[str, list[str]] = {}
    for u in dict.fromkeys(urls):
        por_host.setdefault(urlparse(u).netloc, []).append(u)

    def servidor(host: str, lista: list[str]) -> list[dict]:
        filas = []
        try:
            d = Dominio(f"https://{host}", None, pausa=pausa, max_peticiones=len(lista) + 6)
        except Exception as e:  # noqa: BLE001
            return [{"url": u, "motivo": f"error_{type(e).__name__}"} for u in lista]
        for u in lista:
            if fin is not None and time.time() > fin:
                filas.append({"url": u, "motivo": "sin_tiempo"})
                continue
            try:
                r = d.get(u)
            except Exception as e:  # noqa: BLE001 - un servidor raro no para la tanda
                filas.append({"url": u, "motivo": f"error_{type(e).__name__}"})
                continue
            fila = {"url": u, "estado_http": getattr(r, "status_code", None)}
            if r is None:
                fila["motivo"] = "robots_o_sin_respuesta"
            elif r.status_code == 200 and "html" in (r.headers.get("content-type") or ""):
                html = texto_de(r)
                tdm = reserva_tdm(dict(r.headers), html)
                fila.update({"sha256": hashlib.sha256(r.content).hexdigest(), "bytes": len(r.content),
                             "reserva_tdm": tdm, "url_final": r.url if r.url != u else None})
                if not tdm:
                    fila["texto"] = (procesar or texto_de_pagina)(html)
                    if guarda is not None:
                        fila.update(guarda.original(FUENTE_PAGINAS, r.content, "html", u))
            else:
                fila["motivo"] = "no_html_o_error"
            filas.append(fila)
        return filas

    orden = sorted(por_host.items(), key=lambda kv: -len(kv[1]))  # los servidores con más páginas, primero
    with ThreadPoolExecutor(max_workers=max(1, hilos)) as ex:
        return [f for lote_host in ex.map(lambda kv: servidor(*kv), orden) for f in lote_host]


# ----------------------------------------------------------------------------- tanda de extracción

META = ("proveedor", "grupo", "codigo_ruct", "codigos_ruct", "pagina", "principal")
MIN_CARACTERES = 200  # menos texto que esto: página vacía, de aviso o que se pinta con JavaScript; no se envía


def huellas_previas(carpetas: list[Path]) -> dict[str, tuple]:
    """URL → (huella, grupo, códigos RUCT) de la última extracción buena de cada página en tandas anteriores.
    Las respuestas ilegibles o cortadas no cuentan: esa página se vuelve a enviar aunque no haya cambiado."""
    previas: dict[str, tuple] = {}
    for c in carpetas:
        for f in sorted(c.rglob("paginas_extraidas.jsonl")):
            for l in f.read_text(encoding="utf-8").split("\n"):
                if not l.strip():
                    continue
                x = json.loads(l)
                if x.get("json_legible") is False or x.get("parada") == "max_tokens":
                    continue
                if x["url"] not in previas or x["extraido"] >= previas[x["url"]][3]:
                    # la huella del texto (sin scripts ni marcas) no cambia con fechas o fichas de sesión
                    previas[x["url"]] = (x.get("texto_sha256") or x["captura_sha256"], x.get("grupo"),
                                         frozenset(x.get("codigos_ruct") or []), x["extraido"])
    return previas


def lote(muestra: Path, salida: Path, esperar_min: float = 45, max_paginas: int | None = None, desde: int = 0,
         hilos: int = 12, max_minutos: float = 52, guarda: Guarda | None = None,
         previas: dict[str, tuple] | None = None) -> dict:
    """Tanda en una ejecución: capturar, enviar el lote, esperar, comprobar citas y medir el coste real.

    Lo público (salida) lleva URL, huellas, valores y coste. Lo ajeno (el texto enviado, las respuestas con sus
    citas) va solo al almacén privado, con su clave en lote.json: si el lote no termina a tiempo, «retomar»
    lo recoge en otra ejecución sin volver a pagar ni a pedir las páginas."""
    t0 = time.time()
    fin_total = t0 + max_minutos * 60
    guarda = guarda if guarda is not None else Guarda()
    filas = list({f["url"]: f for f in (json.loads(l) for l in muestra.read_text(encoding="utf-8").split("\n")
                                          if l.strip())}.values())
    filas = filas[desde:desde + max_paginas] if max_paginas else filas[desde:]
    meta = {f["url"]: {k: f[k] for k in META if f.get(k) is not None} for f in filas}
    paginas = capturar([f["url"] for f in filas], hilos=hilos, guarda=guarda, fin=fin_total - 10 * 60)
    salida.mkdir(parents=True, exist_ok=True)
    peticiones, textos, enviado, cuentas = [], {}, [], Counter()
    with (salida / "paginas_capturadas.jsonl").open("w", encoding="utf-8") as f:
        for pg in paginas:
            cuentas["pedidas"] += 1
            texto = pg.pop("texto", None)
            if texto is None and pg.get("html") is not None and not pg.get("reserva_tdm"):
                texto = texto_de_pagina(pg["html"])
            if pg.get("reserva_tdm"):
                cuentas["reserva_tdm"] += 1
            elif texto is None:
                cuentas[pg.get("motivo", "error")] += 1
            elif previas and pg["url"] in previas and previas[pg["url"]][0] in (pg.get("sha256"), hashlib.sha256(texto.encode()).hexdigest()) \
                    and previas[pg["url"]][1] == meta.get(pg["url"], {}).get("grupo") \
                    and set(meta.get(pg["url"], {}).get("codigos_ruct") or []) <= previas[pg["url"]][2]:
                # misma página que la ya extraída (misma huella): sus hechos siguen vigentes, no se paga otra vez
                cuentas["sin_cambios"] += 1
                pg["motivo"] = "sin_cambios"
            elif len(texto) < MIN_CARACTERES:
                cuentas["sin_texto_suficiente"] += 1
                pg["motivo"] = "sin_texto_suficiente"
                pg["caracteres_texto"] = len(texto)
            else:
                cid = id_pagina(pg["url"], pg["sha256"])
                pg["texto_sha256"] = hashlib.sha256(texto.encode()).hexdigest()
                textos[cid] = (pg, texto)
                peticiones.append(peticion(cid, pg["url"], texto))
                enviado.append({"custom_id": cid, "url": pg["url"], "sha256": pg["sha256"], "texto": texto,
                                **meta.get(pg["url"], {})})
                cuentas["enviadas"] += 1
                pg["caracteres_texto"] = len(texto)
            f.write(json.dumps({k: v for k, v in pg.items() if k != "html"}, ensure_ascii=False) + "\n")
    cuentas["minutos_captura"] = round((time.time() - t0) / 60, 1)
    if not peticiones:
        return dict(cuentas)
    r = requests.post(API, headers=_cabeceras(), json={"requests": peticiones}, timeout=300)
    if r.status_code >= 400:
        return {**cuentas, "error_api": r.status_code, "detalle": r.text[:500]}
    b = r.json()
    clave_enviado = guarda.jsonl(FUENTE_EXTRACCION, enviado, "enviado.jsonl", f"anthropic-batch:{b['id']}/enviado")
    (salida / "lote.json").write_text(json.dumps({
        "id": b["id"], "creado": b.get("created_at"), "peticiones": len(peticiones), "modelo": MODELO,
        "clave_enviado": clave_enviado, "muestra": str(muestra), "desde": desde, "max_paginas": max_paginas},
        ensure_ascii=False), encoding="utf-8")
    return _esperar_y_procesar(b, textos, meta, salida, guarda, cuentas, min(fin_total, time.time() + esperar_min * 60))


def retomar(lote_json: Path, salida: Path, esperar_min: float = 50, guarda: Guarda | None = None) -> dict:
    """Recoge un lote enviado en otra ejecución con el texto exacto que se envió (guardado en el almacén)."""
    guarda = guarda if guarda is not None else Guarda()
    info = json.loads(lote_json.read_text(encoding="utf-8"))
    if not info.get("clave_enviado"):
        sys.exit("El lote no tiene copia privada de lo enviado: no se puede comprobar ninguna cita")
    textos, meta = {}, {}
    for e in guarda.leer_jsonl(info["clave_enviado"]):
        textos[e["custom_id"]] = ({"url": e["url"], "sha256": e["sha256"]}, e["texto"])
        meta[e["url"]] = {k: e[k] for k in META if e.get(k) is not None}
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "lote.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    b = requests.get(f"{API}/{info['id']}", headers=_cabeceras(), timeout=60).json()
    return _esperar_y_procesar(b, textos, meta, salida, guarda, Counter({"retomado": 1}), time.time() + esperar_min * 60)


def _esperar_y_procesar(b: dict, textos: dict, meta: dict, salida: Path, guarda: Guarda, cuentas: Counter,
                        fin: float) -> dict:
    t0 = time.time()
    while b.get("processing_status") != "ended" and time.time() < fin:
        time.sleep(30)
        b = requests.get(f"{API}/{b['id']}", headers=_cabeceras(), timeout=60).json()
    cuentas["minutos_lote"] = round((time.time() - t0) / 60, 1)
    if b.get("processing_status") != "ended":
        resumen = {**cuentas, "estado_lote": b.get("processing_status"), "id": b["id"],
                   "cuentas_lote": b.get("request_counts"), "almacen": dict(guarda.cuentas),
                   "siguiente": "retomar con lote.json de esta ejecución"}
        (salida / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
        return resumen
    res = requests.get(b["results_url"], headers=_cabeceras(), timeout=600)
    privado = {"resultados": guarda.original(FUENTE_EXTRACCION, res.content, "resultados.jsonl",
                                             f"anthropic-batch:{b['id']}/resultados").get("clave")
               if guarda.activa else None}
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    uso_total, dolares, campos = Counter(), 0.0, Counter()
    motivos, completos = Counter(), []
    with (salida / "hechos.jsonl").open("w", encoding="utf-8") as fh, \
            (salida / "paginas_extraidas.jsonl").open("w", encoding="utf-8") as fp:
        for linea in res.text.split("\n"):
            if not linea.strip():
                continue
            x = json.loads(linea)
            if x["result"]["type"] != "succeeded" or x["custom_id"] not in textos:
                cuentas["resultado_" + x["result"]["type"]] += 1
                continue
            msg = x["result"]["message"]
            uso = msg.get("usage", {})
            for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
                uso_total[k] += uso.get(k, 0) or 0
            dolares += coste(uso)
            if msg.get("stop_reason") == "max_tokens":
                cuentas["cortadas_por_max_tokens"] += 1
            pagina, texto = textos[x["custom_id"]]
            datos = _json_de("".join(c.get("text", "") for c in msg["content"] if c.get("type") == "text"))
            cuentas["extraidas"] += 1
            if not datos:
                cuentas["json_ilegible"] += 1
            bloques = Counter(c.get("type") for c in msg.get("content", []))
            cuentas["respuestas_con_pensamiento"] += 1 if bloques.get("thinking") else 0
            fp.write(json.dumps({"url": pagina["url"], "captura_sha256": pagina["sha256"], "extraido": ahora,
                                 "json_legible": bool(datos),
                                 "texto_sha256": pagina.get("texto_sha256") or hashlib.sha256(texto.encode()).hexdigest(),
                                 "no_es_programa": bool(datos.get("no_es_programa")), "lote": b["id"],
                                 "uso": uso, "coste_usd": round(coste(uso), 6), "bloques": dict(bloques),
                                 "parada": msg.get("stop_reason"),
                                 "caracteres_respuesta": sum(len(c.get("text", "")) for c in msg.get("content", [])
                                                             if c.get("type") == "text"),
                                 **meta.get(pagina["url"], {})}, ensure_ascii=False) + "\n")
            if datos.get("no_es_programa"):
                cuentas["no_es_programa"] += 1
                continue
            try:
                verificados = verificar(datos, texto)
            except Exception as e:  # noqa: BLE001 - una respuesta rara no tira la tanda ya pagada
                cuentas["error_verificar_" + type(e).__name__] += 1
                continue
            for h in verificados:
                h.update({"url": pagina["url"], "captura_sha256": pagina["sha256"], "modelo": MODELO,
                          "extraido": ahora, "lote": b["id"]})
                completos.append(dict(h))  # con su cita: solo al almacén privado
                # la cita es texto ajeno: en lo público queda su huella (para comprobarla contra el original
                # guardado) y su longitud
                cita = h.pop("cita", "") or ""
                h["cita_sha256"] = hashlib.sha256(_norma(cita).encode()).hexdigest() if cita else None
                h["cita_palabras"] = len(cita.split())
                fh.write(json.dumps(h, ensure_ascii=False) + "\n")
                campos[(h["campo"], h["estado"])] += 1
                if h.get("motivo"):
                    motivos[h["motivo"]] += 1
    privado["hechos_con_cita"] = guarda.jsonl(FUENTE_EXTRACCION, completos, "hechos.jsonl",
                                              f"anthropic-batch:{b['id']}/hechos")
    n = max(cuentas["extraidas"], 1)
    resumen = {**cuentas, "id": b["id"], "uso_tokens": dict(uso_total), "coste_usd": round(dolares, 6),
               "coste_usd_por_pagina": round(dolares / n, 6),
               "tokens_entrada_por_pagina": round(uso_total["input_tokens"] / n),
               "tokens_salida_por_pagina": round(uso_total["output_tokens"] / n),
               "hechos_aceptados": sum(v for (c, e), v in campos.items() if e == "aceptado"),
               "hechos_revision": sum(v for (c, e), v in campos.items() if e == "revision"),
               "motivos_revision": dict(motivos),
               "almacen": {**dict(guarda.cuentas), "claves_privadas": privado} if guarda.activa or guarda.cuentas else None,
               "por_campo": {c: {e: v for (c2, e), v in campos.items() if c2 == c} for c in CAMPOS}}
    (salida / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    return resumen


def lista_oficiales(paginas_oficiales: Path, salida: Path, estados: tuple[str, ...] = ("unido", "dudoso")) -> dict:
    """Muestra para extraer las fichas de los másters oficiales desde paginas_oficiales.jsonl (emparejar.py):
    una fila por URL; si una página sirve a varios códigos del RUCT (interuniversitarios), los lleva todos."""
    por_url: dict[str, dict] = {}
    cuentas = Counter()
    for l in paginas_oficiales.read_text(encoding="utf-8").split("\n"):
        if not l.strip():
            continue
        x = json.loads(l)
        cuentas[x.get("estado")] += 1
        if x.get("estado") not in estados or not x.get("url"):
            continue
        for u, tipo in [(x["url"], "principal")] + [(s, "subpagina") for s in x.get("subpaginas", [])]:
            f = por_url.setdefault(u, {"url": u, "grupo": "oficial", "estado_emparejado": x["estado"], "pagina": tipo,
                                       "codigos_ruct": [], **({"principal": x["url"]} if tipo == "subpagina" else {})})
            if x["codigo_ruct"] not in f["codigos_ruct"]:
                f["codigos_ruct"].append(x["codigo_ruct"])
            if x["estado"] == "unido":
                f["estado_emparejado"] = "unido"
            if tipo == "principal":
                f["pagina"] = "principal"
                f.pop("principal", None)
    filas = sorted(por_url.values(), key=lambda f: (f["estado_emparejado"] != "unido", f["pagina"] != "principal", f["url"]))
    for f in filas:
        f["codigo_ruct"] = f["codigos_ruct"][0]
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in filas), encoding="utf-8")
    return {"masters": dict(cuentas), "urls": len(filas),
            "urls_unido": sum(1 for f in filas if f["estado_emparejado"] == "unido"),
            "urls_con_varios_codigos": sum(1 for f in filas if len(f["codigos_ruct"]) > 1),
            "subpaginas": sum(1 for f in filas if f["pagina"] == "subpagina")}


RE_MASTER = re.compile(r"(?i)(m[aá]ster|masters?|mba|postgrado|posgrado)")
# Versiones de la web para otro país (es-CO, es-MX, en-US…): precios en otra moneda y oferta que no es de España.
LOCALE_OTRO_PAIS = re.compile(r"(?i)/(es|en|pt|fr)[-_](ar|bo|cl|co|cr|cu|do|ec|gt|hn|mx|ni|pa|pe|pr|py|sv|uy|ve|us|br|"
                              r"419|latam|la)(/|$)|/(mexico|colombia|peru|chile|argentina|ecuador|latam|latinoamerica)/")
PRECIOS = {"precio_total", "precio_credito", "reserva_matricula"}
MONEDA_NO_EURO = re.compile(r"(?i)(\$|US\s?D|\bUSD\b|\bCOP\b|\bMXN\b|\bARS\b|\bCLP\b|\bPEN\b|\bS/\.|"
                            r"\bpesos?\b|\bsoles\b|\bd[oó]lares?\b|£|\bGBP\b|\bCHF\b)")
PRECIO_MAXIMO = 100_000  # un máster de más de 100.000 € es casi siempre otra moneda o un error de lectura
RUTA_NO_FICHA = re.compile(r"(?i)/(blog|noticias?|news|actualidad|eventos?|events?|agenda|landing|prensa|press|"
                           r"tag|etiqueta|categor[ií]a|category|author|autor|wp-content|feed)/")


def _orden_ficha(u: str) -> tuple:
    """Antes lo que parece la ficha de un programa concreto (rastreador.prioridad_url), sin consulta, en castellano."""
    from motor.estudios.rastreador import prioridad_url

    return (-prioridad_url(u), not RE_MASTER.search(u), "?" in u, not re.search(r"/(es|cas|esp)(/|$)", u), len(u), u)


def _sin_seguimiento(u: str) -> str:
    """Quita de la URL los parámetros de campañas (utm_*, gclid…): es la misma página."""
    from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

    p = urlparse(u)
    if not p.query:
        return u
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
         if not re.match(r"(?i)^(utm_\w*|gclid|fbclid|mc_\w*|_ga|_gl|ref|referrer)$", k)]
    return urlunparse(p._replace(query=urlencode(q)))


def _no_es_ficha_por_url(u: str) -> bool:
    from urllib.parse import urlparse

    from motor.estudios.rastreador import NO_FICHA

    ruta = urlparse(u).path
    return bool(RUTA_NO_FICHA.search(ruta + "/")) or bool(LOCALE_OTRO_PAIS.search(ruta + "/")) \
        or bool(NO_FICHA.search(re.sub(r"[-_/]+", " ", ruta)))


def lista_no_oficiales(clasificacion: Path, rastreos: list[Path], salida: Path, por_proveedor: int = 30,
                       tramos: int = 3, desde_por_proveedor: int = 0) -> dict:
    """Fichas de máster de los proveedores aptos según la clasificación (centro con ámbito España o
    internacional): una por programa (sin repetir la misma ficha en otro idioma o modalidad, antes la de
    castellano), las de máster primero y hasta `por_proveedor` por proveedor a partir de `desde_por_proveedor`
    (tandas sucesivas sin repetir). Se reparten en `tramos` por servidor: un servidor nunca está en dos tramos, así
    los tramos pueden ir a la vez sin pasar de una petición por segundo a cada servidor."""
    import ast
    from urllib.parse import urlparse

    from motor.estudios.emparejar import raiz_programa, sin_idioma

    clas = {}
    for l in clasificacion.read_text(encoding="utf-8").split("\n"):
        if l.strip():
            c = json.loads(l)
            clas[c["id"]] = c
    ultimo: dict[str, dict] = {}
    for c in rastreos:
        for f in sorted(c.rglob("oferta_web/*.json")):
            r = json.loads(f.read_text(encoding="utf-8"))
            cen = r.get("centro") or {}
            if isinstance(cen, str):
                cen = ast.literal_eval(cen)
            if cen.get("id") in clas:
                ultimo[cen["id"]] = r
    por_host: dict[str, list[dict]] = {}
    cuentas = Counter()
    for i, c in clas.items():
        if not c.get("apto_censo"):
            continue
        ps = (ultimo.get(i) or {}).get("programas") or []
        if isinstance(ps, str):
            ps = ast.literal_eval(ps)
        fichas: dict[str, str] = {}
        for u in sorted((_sin_seguimiento(html_lib.unescape(x)) for x in ps), key=_orden_ficha):
            if _no_es_ficha_por_url(u):
                cuentas["descartadas_por_url"] += 1
                continue
            fichas.setdefault(sin_idioma(raiz_programa(u)), u)
        elegidas = list(fichas.values())[desde_por_proveedor:desde_por_proveedor + por_proveedor]
        cuentas["proveedores"] += 1
        cuentas["fichas_unicas"] += len(fichas)
        for u in elegidas:
            por_host.setdefault(urlparse(u).netloc, []).append({"url": u, "grupo": "no_oficial", "proveedor": i,
                                                                "pagina": "principal"})
    hosts = sorted(por_host, key=lambda h: -len(por_host[h]))
    cargas = [0] * tramos
    destino = [[] for _ in range(tramos)]
    for h in hosts:  # el servidor con más páginas, al tramo con menos carga
        k = cargas.index(min(cargas))
        destino[k] += por_host[h]
        cargas[k] += len(por_host[h])
    salida.mkdir(parents=True, exist_ok=True)
    for k, filas in enumerate(destino):
        (salida / f"no_oficiales_{k}.jsonl").write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in filas),
                                                        encoding="utf-8")
    return {**cuentas, "paginas": sum(cargas), "por_tramo": cargas, "servidores": len(hosts),
            "max_por_servidor": max((len(v) for v in por_host.values()), default=0)}


def lista_propios_de_oficiales(censo: Path, rastreos: list[Path], paginas_oficiales: Path, salida: Path,
                               por_proveedor: int = 30, tramos: int = 3, desde_por_proveedor: int = 0) -> dict:
    """Títulos propios (formación permanente, másters propios de centros adscritos y escuelas del RUCT: ESIC,
    Centro Garrigues, IEB…) en las webs de los proveedores oficiales: las fichas de máster de su rastreo que no
    son la página (ni una subpágina) de ningún máster oficial ya unido. La extracción dice después qué tipo de
    título es cada una (`tipo_titulo`) y descarta lo que no es ficha."""
    import ast
    from urllib.parse import urlparse

    from motor.estudios.emparejar import raiz_programa, sin_idioma

    oficiales = {}
    for l in censo.read_text(encoding="utf-8").split("\n"):
        if l.strip():
            x = json.loads(l)
            if x["estado"] == "oficial":
                oficiales[x["id"]] = x
    usadas_raiz: dict[str, set[str]] = {}
    for l in paginas_oficiales.read_text(encoding="utf-8").split("\n"):
        if l.strip():
            x = json.loads(l)
            for u in [x.get("url")] + list(x.get("subpaginas") or []) + list(x.get("urls_modalidad") or []):
                if u and x.get("estado") in ("unido", "dudoso"):
                    usadas_raiz.setdefault(urlparse(u).netloc, set()).add(sin_idioma(raiz_programa(u)))
    ultimo: dict[str, dict] = {}
    for c in rastreos:
        for f in sorted(c.rglob("oferta_web/*.json")):
            r = json.loads(f.read_text(encoding="utf-8"))
            cen = r.get("centro") or {}
            if isinstance(cen, str):
                cen = ast.literal_eval(cen)
            if cen.get("id") in oficiales:
                ultimo[cen["id"]] = r
    por_host: dict[str, list[dict]] = {}
    cuentas = Counter()
    for i, r in ultimo.items():
        ps = r.get("programas") or []
        if isinstance(ps, str):
            ps = ast.literal_eval(ps)
        fichas: dict[str, str] = {}
        for u in sorted((html_lib.unescape(x) for x in ps), key=_orden_ficha):
            if not RE_MASTER.search(u) or re.search(r"(?i)m[aá]ster(es)?[-_ ]?(universitari[oa]s?|oficial(es)?)", u):
                continue  # solo lo que nombra un máster, y no los oficiales («máster universitario»)
            if _no_es_ficha_por_url(u):
                cuentas["descartadas_por_url"] += 1
                continue
            u = _sin_seguimiento(u)
            clave = sin_idioma(raiz_programa(u))
            # misma ficha (o subpágina suya, que tiene la misma raíz) que un máster oficial ya unido. No vale «cuelga
            # de»: si un oficial quedó unido a un listado o a la portada, todo el sitio colgaría de él.
            if clave in usadas_raiz.get(urlparse(u).netloc, set()):
                cuentas["ya_unidas_a_un_oficial"] += 1
                continue
            fichas.setdefault(clave, u)
        elegidas = list(fichas.values())[desde_por_proveedor:desde_por_proveedor + por_proveedor]
        cuentas["proveedores_con_fichas"] += bool(fichas)
        cuentas["fichas_unicas"] += len(fichas)
        for u in elegidas:
            por_host.setdefault(urlparse(u).netloc, []).append({"url": u, "grupo": "propio_oficial", "proveedor": i,
                                                                "pagina": "principal"})
    hosts = sorted(por_host, key=lambda h: -len(por_host[h]))
    cargas, destino = [0] * tramos, [[] for _ in range(tramos)]
    for h in hosts:
        k = cargas.index(min(cargas))
        destino[k] += por_host[h]
        cargas[k] += len(por_host[h])
    salida.mkdir(parents=True, exist_ok=True)
    for k, filas in enumerate(destino):
        (salida / f"propios_oficiales_{k}.jsonl").write_text(
            "".join(json.dumps(f, ensure_ascii=False) + "\n" for f in filas), encoding="utf-8")
    return {**cuentas, "paginas": sum(cargas), "por_tramo": cargas, "servidores": len(hosts)}


def lista_segunda_vuelta(paginas_oficiales: Path, fichas: Path, capturadas: list[Path], salida: Path,
                         umbral: float = 0.5, por_master: int = 2) -> dict:
    """Másters oficiales sin página comprobada tras la primera extracción (no era la ficha, nombre de otro
    máster, sin nombre, página caída o sin unir): sus siguientes candidatas con puntuación >= umbral que aún no se
    han extraído. La extracción hace de verificador: solo vale la página cuyo nombre es el del RUCT
    (fichas_masters.comprobar_nombre)."""
    hechas = set()
    for c in capturadas:
        for l in c.read_text(encoding="utf-8").split("\n"):
            if l.strip():
                hechas.add(json.loads(l)["url"])
    ok = set()
    for l in fichas.read_text(encoding="utf-8").split("\n"):
        if l.strip():
            f = json.loads(l)
            if f.get("comprobacion_nombre") in ("confirmado", "probable_oficial"):
                ok.add(f["codigo_ruct"])
    filas: dict[str, dict] = {}
    cuentas = Counter()
    for l in paginas_oficiales.read_text(encoding="utf-8").split("\n"):
        if not l.strip():
            continue
        x = json.loads(l)
        if x["codigo_ruct"] in ok:
            continue
        cuentas["sin_ficha_comprobada"] += 1
        cands = ([x["candidata"]] if x.get("candidata") and x.get("puntuacion", 0) >= umbral else []) + \
                [a["url"] for a in x.get("alternativas", []) if a["puntuacion"] >= umbral]
        cands = [u for u in dict.fromkeys(cands) if u and u not in hechas][:por_master]
        cuentas["con_candidatas"] += bool(cands)
        for u in cands:
            f = filas.setdefault(u, {"url": u, "grupo": "oficial", "estado_emparejado": "segunda_vuelta",
                                     "pagina": "principal", "codigos_ruct": []})
            if x["codigo_ruct"] not in f["codigos_ruct"]:
                f["codigos_ruct"].append(x["codigo_ruct"])
    for f in filas.values():
        f["codigo_ruct"] = f["codigos_ruct"][0]
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in filas.values()), encoding="utf-8")
    return {**cuentas, "urls": len(filas)}


def lista_tercera_vuelta(censo: Path, rastreos: list[Path], cc_urls: Path | None, catalogo: Path, fichas: Path,
                         capturadas: list[Path], salida: Path, umbral: float = 0.7, max_por_web: int = 150,
                         tramos: int = 3) -> dict:
    """Universidades con pocos másters oficiales con ficha (menos del `umbral`): casi siempre webs con URL opacas
    (códigos en vez de nombres) donde la unión por URL no puede acertar. Se mandan a extraer sus páginas de
    programa aún no leídas, y la ficha se asigna después por el nombre extraído (fichas_masters.rescatar_oficiales)."""
    import ast
    from urllib.parse import urlparse

    from motor.estudios.emparejar import raiz_programa, sin_idioma

    texto = catalogo.read_text(encoding="utf-8").strip()
    cat = json.loads(texto) if texto.startswith("[") else [json.loads(l) for l in texto.split("\n") if l.strip()]
    activos = [t for t in cat if t.get("situacion", "Activo") == "Activo"]
    con_ficha = set()
    for l in fichas.read_text(encoding="utf-8").split("\n"):
        if l.strip():
            f = json.loads(l)
            if f["grupo"] == "oficial" and f.get("comprobacion_nombre") in ("confirmado", "probable_oficial", "confirmado_por_nombre"):
                con_ficha.add(f["codigo_ruct"])
    tot, ok = Counter(), Counter()
    for t in activos:
        tot[t["universidad_codigo"]] += 1
        ok[t["universidad_codigo"]] += t["codigo_ruct"] in con_ficha
    flojas = {u for u in tot if ok[u] < umbral * tot[u]}
    hechas = {json.loads(l)["url"] for c in capturadas for l in c.read_text(encoding="utf-8").split("\n") if l.strip()}
    provs = {}
    for l in censo.read_text(encoding="utf-8").split("\n"):
        if l.strip():
            x = json.loads(l)
            if x["estado"] == "oficial" and any(r.get("universidad") in flojas for r in x.get("ruct", [])):
                provs[x["id"]] = x
    urls_de: dict[str, set] = defaultdict(set)
    for c in rastreos:
        for f in sorted(c.rglob("oferta_web/*.json")):
            r = json.loads(f.read_text(encoding="utf-8"))
            cen = r.get("centro") or {}
            if isinstance(cen, str):
                cen = ast.literal_eval(cen)
            if cen.get("id") in provs:
                ps = r.get("programas") or []
                urls_de[cen["id"]].update(ast.literal_eval(ps) if isinstance(ps, str) else ps)
    if cc_urls:
        dom_a_prov = {d: i for i, x in provs.items() for d in x.get("dominios", [x["dominio"]])}
        for f in cc_urls.rglob("urls_*.jsonl"):
            for l in f.read_text(encoding="utf-8").split("\n"):
                d = json.loads(l)
                if d["dominio"] in dom_a_prov:
                    urls_de[dom_a_prov[d["dominio"]]].update(d["urls"])
    por_host: dict[str, list[dict]] = defaultdict(list)
    cuentas = Counter({"universidades_flojas": len(flojas), "webs": len(provs)})
    for i, urls in urls_de.items():
        elegidas: dict[str, str] = {}
        for u in sorted((_sin_seguimiento(html_lib.unescape(x)) for x in urls), key=_orden_ficha):
            if u in hechas or not RE_MASTER.search(u) or _no_es_ficha_por_url(u):
                continue
            elegidas.setdefault(sin_idioma(raiz_programa(u)), u)
        for u in list(elegidas.values())[:max_por_web]:
            por_host[urlparse(u).netloc].append({"url": u, "grupo": "oficial_por_nombre", "proveedor": i,
                                                 "pagina": "principal"})
    cargas, destino = [0] * tramos, [[] for _ in range(tramos)]
    for h in sorted(por_host, key=lambda h: -len(por_host[h])):
        k = cargas.index(min(cargas))
        destino[k] += por_host[h]
        cargas[k] += len(por_host[h])
    salida.mkdir(parents=True, exist_ok=True)
    for k, filas in enumerate(destino):
        (salida / f"oficiales_tercera_{k}.jsonl").write_text(
            "".join(json.dumps(f, ensure_ascii=False) + "\n" for f in filas), encoding="utf-8")
    return {**cuentas, "paginas": sum(cargas), "por_tramo": cargas, "servidores": len(por_host)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("orden", choices=["lote", "retomar", "lista-oficiales", "lista-no-oficiales", "lista-propios-oficiales",
                                     "lista-segunda-vuelta", "lista-tercera-vuelta",
                                     "preparar", "enviar", "recoger"])
    p.add_argument("--censo")
    p.add_argument("--fichas")
    p.add_argument("--catalogo")
    p.add_argument("--commoncrawl")
    p.add_argument("--capturadas", action="append", default=[])
    p.add_argument("--clasificacion")
    p.add_argument("--rastreo", action="append", default=[])
    p.add_argument("--por-proveedor", type=int, default=30)
    p.add_argument("--desde-por-proveedor", type=int, default=0)
    p.add_argument("--tramos", type=int, default=3)
    p.add_argument("--muestra", help="lote: JSONL con {url, proveedor, grupo, codigo_ruct}")
    p.add_argument("--esperar-min", type=float, default=45)
    p.add_argument("--max-paginas", type=int)
    p.add_argument("--desde", type=int, default=0)
    p.add_argument("--hilos", type=int, default=12, help="servidores a la vez (cada uno, una petición por segundo)")
    p.add_argument("--max-minutos", type=float, default=52, help="tope de la ejecución entera")
    p.add_argument("--lote-json", help="retomar: lote.json de la ejecución que envió el lote")
    p.add_argument("--previas", action="append", default=[],
                   help="lote: carpetas de tandas anteriores; las páginas con la misma huella no se vuelven a enviar")
    p.add_argument("--paginas-oficiales", help="lista-oficiales: paginas_oficiales.jsonl de emparejar.py")
    p.add_argument("--paginas")
    p.add_argument("--lote")
    p.add_argument("--id")
    p.add_argument("--salida")
    a = p.parse_args()
    # cada tramo en su carpeta (nombre de la muestra y desde dónde), para que al juntar tramos no se pisen
    base = Path(a.salida) / "datos" / "estudios" / "extraccion" if a.salida else None
    destino = base
    if base is not None and a.orden == "lote":
        destino = base / (Path(a.muestra).stem + (f"_desde{a.desde}" if a.desde else ""))
    elif base is not None and a.orden == "retomar":
        destino = base / ("retomado_" + json.loads(Path(a.lote_json).read_text(encoding="utf-8"))["id"][-16:])
    if a.orden == "lote":
        res = lote(Path(a.muestra), destino, a.esperar_min, a.max_paginas, a.desde, a.hilos, a.max_minutos,
                   previas=huellas_previas([Path(x) for x in a.previas]) if a.previas else None)
    elif a.orden == "retomar":
        res = retomar(Path(a.lote_json), destino, a.esperar_min)
    elif a.orden == "lista-no-oficiales":
        res = lista_no_oficiales(Path(a.clasificacion), [Path(x) for x in a.rastreo], Path(a.salida), a.por_proveedor,
                                 a.tramos, a.desde_por_proveedor)
    elif a.orden == "lista-tercera-vuelta":
        res = lista_tercera_vuelta(Path(a.censo), [Path(x) for x in a.rastreo], Path(a.commoncrawl) if a.commoncrawl else None,
                                   Path(a.catalogo), Path(a.fichas), [Path(x) for x in a.capturadas], Path(a.salida),
                                   tramos=a.tramos)
    elif a.orden == "lista-segunda-vuelta":
        res = lista_segunda_vuelta(Path(a.paginas_oficiales), Path(a.fichas), [Path(x) for x in a.capturadas],
                                   Path(a.salida))
    elif a.orden == "lista-propios-oficiales":
        res = lista_propios_de_oficiales(Path(a.censo), [Path(x) for x in a.rastreo], Path(a.paginas_oficiales),
                                         Path(a.salida), a.por_proveedor, a.tramos, a.desde_por_proveedor)
    elif a.orden == "lista-oficiales":
        res = lista_oficiales(Path(a.paginas_oficiales), Path(a.salida))
    elif a.orden == "preparar":
        res = preparar(Path(a.paginas), Path(a.salida))
    elif a.orden == "enviar":
        res = enviar(Path(a.lote))
    else:
        res = recoger(a.id, Path(a.paginas), Path(a.salida))
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
