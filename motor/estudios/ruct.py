"""Conector del RUCT (Registro de Universidades, Centros y Títulos): ficha de cada título y su memoria.

Fuente: https://www.educacion.gob.es/ruct/ (Ministerio de Ciencia, Innovación y Universidades). Sin API ni
descarga masiva: se leen las páginas web, una petición por segundo.

Dos niveles de lectura, para gastar solo lo necesario:
  1. ficha (1 petición por título): créditos por tipo, rama, campo, fechas de verificación y de autorización,
     enlaces al BOE del acuerdo y del plan de estudios, comunidad que autoriza, extinción, renovaciones de
     acreditación, centros (código de 8 cifras) e histórico de incidencias con el código de cada memoria;
  2. memoria vigente (de 15 a 150 peticiones por título): datos básicos (profesión regulada, conjunto,
     agencia), universidades participantes, por centro las modalidades con sus plazas y los idiomas,
     requisitos de acceso y criterios de admisión, complementos formativos, catálogo de actividades,
     metodologías y sistemas de evaluación, y el plan: módulos, materias (ECTS, carácter, despliegue) y
     asignaturas. En las memorias del formato anterior (RD 1393/2007) cada materia trae además sus horas por
     actividad con su presencialidad y la ponderación mínima y máxima de cada sistema de evaluación.

Las páginas de la memoria dependen de la sesión: el servidor recuerda qué memoria se está viendo. Por eso
cada memoria se recorre entera y en orden dentro de su propia sesión, y cada página se comprueba contra el
título esperado (si el servidor devuelve otra memoria, la página se descarta y se avisa).

Los originales siguen la política del motor (motor/archivo.py): en la rama pública solo índice y huella; enteros en
el almacén privado con MOTOR_ORIGINALES=s3. Antes de cada petición se mira robots.txt (ver REGISTRO_PUBLICO).

Uso:
  python -m motor.estudios.ruct --codigos 4318301,3500355 --nivel memoria --salida ruta/
  python -m motor.estudios.ruct --codigos-fichero codigos.txt --desde 0 --hasta 70 --nivel memoria --salida ruta/
  python -m motor.estudios.ruct --catalogo datos/estudios/masters/catalogo.jsonl --nivel ficha --salida ruta/
"""

from __future__ import annotations

import argparse
import html as htmllib
import json
import re
import sys
import time
import unicodedata
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests

from motor.archivo import Archivo
from motor.http import USER_AGENT

BASE = "https://www.educacion.gob.es/ruct/"
URL_FICHA = BASE + "estudio.action?codigoCiclo=SC&codigoTipo={tipo}&CodigoEstudio={codigo}&actual=estudios"
SOL = BASE + "solicitud/"
FUENTE = "ruct"
CITA = "Ministerio de Ciencia, Innovación y Universidades. Registro de Universidades, Centros y Títulos (RUCT)"
PAUSA = 1.0

# ----------------------------------------------------------------------------------------------- lectura


def _txt(fragmento: str | None) -> str:
    if not fragmento:
        return ""
    s = re.sub(r"(?is)<br\s*/?>|</p>|</li>", "\n", fragmento)
    s = htmllib.unescape(re.sub(r"<[^>]+>", " ", s)).replace("\xa0", " ").replace("​", "")
    lineas = [" ".join(linea.split()) for linea in s.split("\n")]
    return "\n".join(linea for linea in lineas if linea).strip()


def _clave(etiqueta: str) -> str:
    s = unicodedata.normalize("NFKD", etiqueta.lower().replace("nº", "num "))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s


def _contenido(pagina: str) -> str:
    i = pagina.find('id="contenido"')
    j = pagina.find("Ministerio de Ciencia, Innovaci", i if i >= 0 else 0)
    cuerpo = pagina[i if i >= 0 else 0: j if j > 0 else None]
    return re.sub(r"(?is)<script.*?</script>|<style.*?</style>|<noscript>.*?</noscript>", "", cuerpo)


def _valor_control(fragmento: str):
    """Valor del primer control de un fragmento: input, select, textarea o span."""
    m = re.search(r"(?is)<input\b([^>]*)>", fragmento)
    if m and "hidden" not in m.group(1):
        atributos = m.group(1)
        v = re.search(r'value="([^"]*)"', atributos)
        valor = htmllib.unescape(v.group(1)).strip() if v else ""
        if re.search(r'type="(checkbox|radio)"', atributos):
            return "checked" in atributos
        return valor
    m = re.search(r"(?is)<select\b.*?</select>", fragmento)
    if m:
        o = re.search(r"(?is)<option[^>]*selected[^>]*>(.*?)</option>", m.group(0))
        return _txt(o.group(1)) if o else ""
    m = re.search(r"(?is)<textarea\b[^>]*>(.*?)</textarea>", fragmento)
    if m:
        return _txt(m.group(1))
    m = re.search(r'(?is)<span\b(?![^>]*class="label")[^>]*>(.*?)</span>', fragmento)
    if m:
        return _txt(m.group(1))
    return _txt(fragmento)


def campos(pagina: str) -> dict:
    """Pares etiqueta → valor de los formularios de solo lectura y de la ficha."""
    salida: dict = {}
    for m in re.finditer(r"(?is)<label\b[^>]*>(.*?)</label>", _contenido(pagina)):
        bloque = m.group(1)
        e = re.search(r'(?is)<span class="label">(.*?)</span>', bloque)
        if e:
            etiqueta = _txt(e.group(1))
            resto = bloque[e.end():]
        else:  # etiqueta como texto suelto antes del control
            partes = re.split(r"(?is)(?=<input|<select|<textarea)", bloque, maxsplit=1)
            etiqueta, resto = _txt(partes[0]), (partes[1] if len(partes) > 1 else "")
        etiqueta = etiqueta.rstrip(" :*").strip()
        if not etiqueta:
            continue
        clave = _clave(etiqueta)
        valor = _valor_control(resto) if resto.strip() else ""
        if clave in salida:  # etiquetas repetidas (p. ej. «Plazas» por modalidad): se numeran
            n = 2
            while f"{clave}_{n}" in salida:
                n += 1
            clave = f"{clave}_{n}"
        salida[clave] = valor
    return salida


def tablas(pagina: str) -> list[dict]:
    """Tablas de datos (displaytag): cabecera y filas de texto; enlaces de cada fila conservados."""
    resultado = []
    for t in re.finditer(r"(?is)<table\b[^>]*>(.*?)</table>", _contenido(pagina)):
        cuerpo = t.group(1)
        if "despliegueMateria" in cuerpo or "<table" in cuerpo.lower():
            continue
        cab = [_txt(c) for c in re.findall(r"(?is)<th\b[^>]*>(.*?)</th>", cuerpo)]
        filas, enlaces = [], []
        for tr in re.findall(r"(?is)<tr\b[^>]*>(.*?)</tr>", cuerpo):
            celdas = re.findall(r"(?is)<td\b[^>]*>(.*?)</td>", tr)
            if not celdas:
                continue
            filas.append([_txt(c) for c in celdas])
            enlaces.append([htmllib.unescape(h) for h in re.findall(r'href="([^"]+)"', tr)])
        if cab or filas:
            resultado.append({"cabecera": cab, "filas": filas, "enlaces": enlaces})
    return resultado


def textos(pagina: str) -> list[str]:
    """Bloques de texto libre (descripciones de acceso, contenidos, etc.)."""
    out = []
    for m in re.finditer(r'(?is)<div class="texto-editor">(.*?)</div>\s*(?=</fieldset|<div|<fieldset|$)', _contenido(pagina)):
        t = _txt(m.group(1))
        if t:
            out.append(t)
    return out


def encabezado(pagina: str) -> dict:
    """Título y universidad que el servidor tiene en sesión (bloque «sesion»), y migas de módulo y materia."""
    res: dict = {"titulo": None, "universidad": None}
    m = re.search(r'(?is)<ul class="solicitud">\s*<li>(.*?)</li>', pagina)
    if m:
        h = _txt(m.group(1))
        u = re.search(r"\[([^\]]+)\]\s*$", h)
        res["universidad"] = u.group(1) if u else None
        res["titulo"] = re.sub(r"\s*-\s*\[[^\]]+\]\s*$", "", h).strip()
    for clase, clave in (("materia", "modulo"), ("asignatura", "materia")):
        mm = re.search(r'(?is)<ul class="' + clase + r'">\s*<li>.*?</strong>(.*?)</li>', pagina)
        if mm:
            res[clave] = _txt(mm.group(1))
    return res


def _despliegue(pagina: str) -> dict[int, float]:
    """ECTS por periodo (semestre o cuatrimestre) de una materia o asignatura."""
    out = {}
    for m in re.finditer(r'(?is)<input[^>]*name="ects"[^>]*value="([^"]*)"[^>]*id="ects(\d+)"', pagina):
        if m.group(1).strip():
            out[int(m.group(2))] = _num(m.group(1))
    return out


def _num(s) -> float | None:
    if s is None:
        return None
    s = str(s).strip().replace("%", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _fecha(s: str | None) -> str | None:
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", s or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


# --------------------------------------------------------------------------------------------- la ficha


def parsear_ficha(pagina: str) -> dict:
    c = campos(pagina)
    cuerpo = _contenido(pagina)
    h2 = re.search(r"(?is)<h2[^>]*>(.*?)</h2>", cuerpo)
    boe = {}
    for etiqueta, clave in (("Acuerdo de Consejo de Ministros en el BOE", "acuerdo"), ("Plan Estudios en el BOE", "plan")):
        m = re.search(r"(?is)" + etiqueta + r".*?(?:href=\"([^\"]+)\"[^>]*>(.*?)</a>|</label>)", cuerpo)
        if m and m.group(1):
            ident = re.search(r"(BOE-[AB]-\d{4}-\d+)", m.group(1))
            boe[clave] = {"url": m.group(1), "fecha": _fecha(_txt(m.group(2))), "identificador": ident.group(1) if ident else None}
        elif m:
            boe[clave] = None
    ficha = {
        "nombre": _txt(h2.group(1)) if h2 else None,
        "codigo": c.get("codigo_del_titulo"),
        "nivel": c.get("nivel_academico"),
        "meces": c.get("nivel_meces"),
        "rama": c.get("rama"),
        "campo": c.get("campo_de_estudio"),
        "creditos": {
            "obligatorios": _num(c.get("num_creditos_obligatorios")),
            "optativos": _num(c.get("num_creditos_optativos")),
            "practicas_externas": _num(c.get("num_creditos_en_practicas_externas")),
            "tfm": _num(c.get("num_creditos_trabajo_fin_de_grado_master")),
            "complementos_formativos": _num(c.get("num_creditos_complementos_formativos")),
            "total": _num(c.get("creditos_totales")),
        },
        "fecha_verificacion": _fecha(c.get("fecha_de_verificacion")),
        "fecha_consejo_ministros": _fecha(c.get("fecha_de_autorizacion_del_consejo_de_ministros")),
        "boe": boe,
        "curso_inicio": c.get("curso_de_inicio_de_imparticion") or None,
        "autorizaciones_ccaa": [],
        "extincion": [],
        "acreditaciones": [],
        "centros": [],
        "incidencias": [],
        "memorias": [],
    }
    for t in tablas(pagina):
        cab = " ".join(t["cabecera"]).lower()
        for fila, enlaces in zip(t["filas"], t["enlaces"]):
            if "fecha de autorizaci" in cab:
                ficha["autorizaciones_ccaa"].append({"universidad": fila[0], "ccaa_codigo": fila[1], "ccaa": fila[2],
                                                     "fecha": _fecha(fila[3]), "enlace": enlaces[0] if enlaces else None})
            elif "extinci" in cab:
                ficha["extincion"].append({"universidad": fila[0], "ccaa": fila[2] if len(fila) > 2 else None,
                                           "fecha": _fecha(" ".join(fila[3:])), "enlace": enlaces[0] if enlaces else None})
            elif "resultado" in cab and "efecto" in cab:
                ficha["acreditaciones"].append({"resultado": fila[0], "fecha": _fecha(fila[1])})
            elif "código de centro" in cab:
                ficha["centros"].append({"universidad": fila[0], "codigo": fila[1], "centro": fila[2]})
            elif "incidencia" in cab:
                cod = None
                for e in enlaces:
                    q = parse_qs(urlparse(e).query)
                    if "cod" in q:
                        cod = {"cod": q["cod"][0], "sit": q.get("sit", [None])[0]}
                ficha["incidencias"].append({"orden": fila[0], "denominacion": fila[1], "incidencia": fila[2],
                                             "fecha": _fecha(fila[3]), "memoria": cod})
    vistas = set()
    for inc in ficha["incidencias"]:
        if inc["memoria"] and inc["memoria"]["cod"] not in vistas:
            vistas.add(inc["memoria"]["cod"])
            ficha["memorias"].append(inc["memoria"])
    for m in re.finditer(r'solicitud/detalles\.action[^"]*\?cod=(\d+)&(?:amp;)?sit=(\w)', cuerpo):
        if m.group(1) not in vistas:
            vistas.add(m.group(1))
            ficha["memorias"].append({"cod": m.group(1), "sit": m.group(2)})
    return ficha


def memoria_vigente(ficha: dict) -> dict | None:
    """La última memoria publicada (sit=A) del histórico; si no hay ninguna activa, la última."""
    activas = [m for m in ficha["memorias"] if m.get("sit") == "A"]
    candidatas = activas or ficha["memorias"]
    return max(candidatas, key=lambda m: m["cod"][7:]) if candidatas else None


# -------------------------------------------------------------------------------------- la memoria


def parsear_centro(pagina: str) -> dict:
    c = campos(pagina)
    modalidades = {}
    for clave, nombre in (("presencial", "presencial"), ("semipresencial_hibrida", "semipresencial"),
                          ("a_distancia_virtual", "a_distancia")):
        if clave in c:
            modalidades[nombre] = c[clave] is True
    plazas = [c.get("plazas"), c.get("plazas_2"), c.get("plazas_3")]
    por_modalidad = {n: _num(p) for n, p in zip(("presencial", "semipresencial", "a_distancia"), plazas) if _num(p)}
    # Formato RD 1393/2007: plazas por año de implantación en lugar de por modalidad.
    por_ano = [_num(v) for k, v in c.items() if k.endswith("ano_de_implantacion") and _num(v)]
    idiomas = []
    for t in tablas(pagina):
        if any("denominaci" in x.lower() for x in t["cabecera"]):
            idiomas += [f[-1] for f in t["filas"] if f and f[-1]]
    return {
        "modalidades": [k for k, v in modalidades.items() if v],
        "plazas_por_modalidad": por_modalidad,
        "plazas_total": _num(c.get("numero_total_de_plazas_ofertadas_en_el_centro")) or (por_ano[-1] if por_ano else None),
        "plazas_nuevo_ingreso": _num(c.get("numero_de_plazas_de_nuevo_ingreso_para_primer_curso")) or (por_ano[-1] if por_ano else None),
        "plazas_por_ano_implantacion": por_ano,
        "normas_permanencia": c.get("normas_de_permanencia") or None,
        "idiomas": idiomas,
    }


def parsear_tabla_materia(pagina: str, tipo: str) -> list[dict]:
    """Actividades (horas, presencialidad) o sistemas de evaluación (ponderación mín./máx.) de una materia."""
    out = []
    for t in tablas(pagina):
        cab = [x.lower() for x in t["cabecera"]]
        for f in t["filas"]:
            if len(f) < 4:
                continue
            if tipo == "actividades" and any("horas" in x for x in cab):
                out.append({"id": f[0], "actividad": f[1], "horas": _num(f[2]), "presencialidad": _num(f[3])})
            elif tipo == "sistemas" and any("ponderaci" in x for x in cab):
                i_min = next(i for i, x in enumerate(cab) if "nima" in x)
                i_max = next(i for i, x in enumerate(cab) if "xima" in x)
                out.append({"id": f[0], "sistema": f[1], "ponderacion_min": _num(f[i_min]), "ponderacion_max": _num(f[i_max])})
    return out


def parsear_materia(pagina: str) -> dict:
    c = campos(pagina)
    nombre = c.get("denominacion")
    hijos = []
    for t in tablas(pagina):
        if [x.lower() for x in t["cabecera"][:2]] == ["id", "denominación"] or "denominación" in " ".join(t["cabecera"]).lower():
            for f, e in zip(t["filas"], t["enlaces"]):
                if len(f) >= 2 and f[0].isdigit():
                    hijos.append({"id": int(f[0]), "nombre": f[1]})
    return {
        "nombre": nombre,
        "caracter": c.get("caracter"),
        "ects": _num(c.get("ects_materia") or c.get("ects")),
        "unidad_temporal": c.get("unidad_temporal"),
        "despliegue": _despliegue(pagina),
        "hijos": hijos,
        "textos": textos(pagina),
    }


def lista_catalogo(pagina: str) -> list[dict]:
    """Catálogo de actividades, metodologías o sistemas del título (texto «ID. descripción»)."""
    c = _contenido(pagina)
    filas = []
    for t in tablas(pagina):
        for f in t["filas"]:
            if f and any(f):
                filas.append(" ".join(x for x in f if x))
    if not filas:
        bloque = _txt(c)
        filas = [linea for linea in bloque.split("\n") if re.match(r"^[A-Z]{1,4}\s?\d", linea)]
    return [{"texto": x} for x in filas]


# --------------------------------------------------------------------------------------- descarga


PAUSA_MAX = 12.0       # si el servidor pide ir más despacio, hasta una petición cada 12 segundos
ESPERA_RESPUESTA = 20  # segundos: una ficha responde en menos de uno; lo que tarda más es que no va a responder
SEGUIDAS_PARA_ACELERAR = 15


class Lector:
    """Sesión educada con el RUCT: identificada, una petición por segundo como mucho, originales archivados.

    El ritmo se adapta al servidor: cada petición que no responde o que responde 429/5xx duplica la pausa (hasta
    PAUSA_MAX) y cada SEGUIDAS_PARA_ACELERAR respuestas buenas la reducen un 20 % (nunca por debajo de la de
    partida). Medido el 30/10/2026 de día desde GitHub: el RUCT dejaba de responder tras unas 8 peticiones seguidas
    a una por segundo y volvía a los 40-50 segundos (unas 10 por minuto); de noche había atendido 24 por minuto."""

    def __init__(self, archivo: Archivo | None, pausa: float = PAUSA, adaptable: bool = True):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = USER_AGENT
        self.archivo = archivo
        self.pausa = pausa
        self.base = pausa
        self.adaptable = adaptable
        self.peticiones = 0
        self.capturas: list[dict] = []
        self._ultima = 0.0  # inicio de la última petición (reloj monótono)
        self.seguidas = 0
        self.errores: Counter = Counter()
        self.pausa_max_usada = pausa

    def _esperar_turno(self) -> None:
        """La pausa cuenta desde el inicio de la petición anterior (no la pausa más lo que tardó la respuesta)."""
        espera = self.pausa - (time.monotonic() - self._ultima)
        if espera > 0:
            time.sleep(espera)
        self._ultima = time.monotonic()

    def _frenar(self, motivo: str) -> None:
        self.errores[motivo] += 1
        self.seguidas = 0
        if self.adaptable:
            self.pausa = min(PAUSA_MAX, max(self.pausa * 2, self.base + 1))
            self.pausa_max_usada = max(self.pausa_max_usada, self.pausa)

    def _bien(self) -> None:
        self.seguidas += 1
        if self.adaptable and self.pausa > self.base and self.seguidas >= SEGUIDAS_PARA_ACELERAR:
            self.pausa = max(self.base, self.pausa * 0.8)
            self.seguidas = 0

    def get(self, url: str, intentos: int = 3) -> tuple[int, str, dict | None]:
        for i in range(intentos):
            self._esperar_turno()
            self.peticiones += 1
            try:
                r = self.s.get(url, timeout=ESPERA_RESPUESTA)
            except requests.RequestException as e:
                self._frenar(type(e).__name__)
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                self._frenar(f"HTTP {r.status_code}")
                if i < intentos - 1:
                    continue
            else:
                self._bien()
            reg = None
            if self.archivo is not None and r.status_code == 200:
                reg = self.archivo.guardar(FUENTE, date.today(), r.content, url, "html", r.status_code,
                                           {k: v for k, v in r.headers.items() if k.lower() in {"date", "content-type"}})
                self.capturas.append({"url": url, "sha256": reg["sha256"]})
            return r.status_code, r.content.decode("latin-1", "replace"), reg
        return 0, "", None


def _abs(url: str) -> str:
    return re.sub(r";jsessionid=[0-9A-Fa-f]+", "", urljoin(SOL, htmllib.unescape(url)))


def leer_ficha(lector: Lector, codigo: str, tipo: str = "M") -> dict:
    url = URL_FICHA.format(tipo=tipo, codigo=codigo)
    estado, pagina, reg = lector.get(url)
    if estado != 200 or "codigo_del_titulo" not in json.dumps(campos(pagina)):
        return {"codigo": codigo, "error": f"ficha no disponible (estado {estado})", "url": url}
    ficha = parsear_ficha(pagina)
    ficha["fuente"] = {"cita": CITA, "url": url, "sha256": reg["sha256"] if reg else None,
                       "capturado": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    return ficha


def _comprobar(pagina: str, nombre_esperado: str) -> bool:
    """El servidor muestra en cabecera el título que tiene en sesión, truncado con «...»."""
    h = encabezado(pagina)["titulo"]
    if not h:  # páginas sin bloque de sesión (p. ej. errores): no se pueden comprobar
        return False
    a = _clave(h.replace("...", ""))
    return _clave(nombre_esperado).startswith(a[: max(10, len(a) - 3)])


def leer_memoria(lector: Lector, ficha: dict, max_paginas: int = 250) -> dict:
    """Recorre la memoria vigente en orden dentro de su sesión y devuelve sus datos estructurados."""
    m = memoria_vigente(ficha)
    if not m:
        return {"error": "sin memoria publicada"}
    cod = m["cod"]
    nombre = ficha["nombre"] or ""
    avisos: list[str] = []
    lector.s.cookies.clear()
    lector.get(ficha["fuente"]["url"])  # la ficha abre la sesión
    estado, p, _ = lector.get(f"{SOL}detalles.action?cod={cod}&sit={m['sit']}&actual=menu.solicitud.basicos")
    if estado != 200 or not _comprobar(p, nombre):
        return {"cod": cod, "error": f"memoria no disponible o de otro título (estado {estado})"}

    def pagina(ruta: str) -> str | None:
        if lector.peticiones > inicio + max_paginas:
            avisos.append(f"límite de {max_paginas} páginas alcanzado")
            return None
        estado, p, _ = lector.get(SOL + ruta if not ruta.startswith("http") else ruta)
        if estado != 200:
            avisos.append(f"{ruta[:80]}: estado {estado}")
            return None
        if not _comprobar(p, nombre):
            avisos.append(f"{ruta[:80]}: el servidor devolvió otro título; descartada")
            return None
        return p

    inicio = lector.peticiones
    basicos_pagina = p
    basicos = campos(p)
    memoria: dict = {
        "cod": cod,
        "regimen": ficha.get("nivel"),
        "basicos": {
            "denominacion": basicos.get("denominacion_espec"),
            "conjunto": basicos.get("titulo_conjunto"),
            "convenio": basicos.get("descripcion_del_convenio"),
            "habilita_profesion_regulada": basicos.get("habilita_para_profesion_regulada"),
            "condicion_acceso_titulo_profesional": basicos.get("condicion_de_acceso_para_titulo_profesional"),
            "agencia": basicos.get("agencia_evaluadora"),
            "mencion_dual": basicos.get("mencion_dual"),
            "profesion": basicos.get("profesion_regulada") or basicos.get("profesion"),
        },
        "centros": [],
        "acceso": {},
        "catalogos": {},
        "plan": [],
        "avisos": avisos,
    }
    # universidades y centros
    p = pagina(f"universidades?actual=menu.solicitud.universidades&cod={cod}")
    if p:
        memoria["universidades"] = []
        for t in tablas(p):
            for f, e in zip(t["filas"], t["enlaces"]):
                if len(f) >= 2 and re.fullmatch(r"\d{3}", f[0] or ""):
                    memoria["universidades"].append({"codigo": f[0], "nombre": f[1]})
        centros = sorted(set(re.findall(r"codCentro=(\d{8})", p)))
        for cc in centros:
            uni = re.search(r"codUniversidad=(\d{3})&(?:amp;)?codCentro=" + cc, p)
            ruta = (f"datosCentro!consulta.action?codUniversidad={uni.group(1)}&codCentro={cc}&actual=menu.solicitud.datosCentro"
                    if uni else f"datosCentro?actual=menu.solicitud.datosCentro&codCentro={cc}")
            pc = pagina(ruta)
            if pc:
                memoria["centros"].append({"codigo": cc, **parsear_centro(pc)})
    # acceso y admisión
    p = pagina(f"accesoAdmision!requisitos?actual=menu.solicitud.accesoAdmision.requisitos&cod={cod}")
    if p:
        # La página reúne requisitos, criterios, apoyo, reconocimiento de créditos y complementos formativos.
        memoria["acceso"]["textos"] = textos(p)
    # catálogos del título
    for clave, ruta in (("actividades", "actividades?actual=menu.solicitud.planificacion.actividades"),
                        ("metodologias", "metodologias?actual=menu.solicitud.planificacion.metodologias"),
                        ("sistemas", "sistemas?actual=menu.solicitud.planificacion.sistemas")):
        p = pagina(f"{ruta}&cod={cod}")
        if p:
            memoria["catalogos"][clave] = textos(p) or [x["texto"] for x in lista_catalogo(p)]
    p = pagina(f"resultados?actual=menu.solicitud.resultados&cod={cod}")
    if p:
        memoria["resultados_aprendizaje"] = [{"codigo": f[0], "descripcion": f[1], "tipo": f[-1]}
                                             for t in tablas(p) for f in t["filas"] if len(f) >= 3]
    # descripción del plan (estructura, coordinación, movilidad): está en el menú de las memorias que la tienen
    if "descripcionplan" in basicos_pagina:
        p = pagina(f"descripcionplan?actual=menu.solicitud.planificacion.descripcion&cod={cod}")
        if p:
            memoria["descripcion_plan"] = textos(p)
    # plan: módulos → materias → asignaturas
    p = pagina(f"modulos?actual=menu.solicitud.planificacion.modulos&cod={cod}")
    modulos = sorted({int(x) for x in re.findall(r"codModulo=(\d+)", p or "")} - {0})
    for mod in modulos or [0]:
        pm = pagina(f"datosModulo!consulta.action?codModulo={mod}&actual=menu.solicitud.planificacion.materias") if mod else \
            pagina(f"datosModulo?actual=menu.solicitud.planificacion.materiasSin&codModulo={mod}")
        if not pm:
            continue
        info_mod = parsear_materia(pm)
        bloque = {"modulo": mod, "nombre": info_mod["nombre"], "ects": info_mod["ects"], "materias": []}
        materias = sorted({int(x) for x in re.findall(r"codModulo=" + str(mod) + r"&(?:amp;)?codMateria=(\d+)", pm)} |
                          {int(x) for x in re.findall(r"codMateria=(\d+)&(?:amp;)?codModulo=" + str(mod) + r"\b", pm)})
        for mat in materias:
            pmat = pagina(f"datosMateria!consulta.action?codModulo={mod}&codMateria={mat}&actual=menu.solicitud.planificacion.materias.datos")
            if not pmat:
                continue
            materia = parsear_materia(pmat)
            materia["id"] = mat
            if "actividadesMateria" in pmat:
                pa = pagina(f"actividadesMateria?actual=menu.solicitud.planificacion.materias.actividades&codMateria={mat}&codModulo={mod}")
                materia["actividades"] = parsear_tabla_materia(pa, "actividades") if pa else []
            if "sistemasMateria" in pmat:
                ps = pagina(f"sistemasMateria?actual=menu.solicitud.planificacion.materias.sistemas&codMateria={mat}&codModulo={mod}")
                materia["evaluacion"] = parsear_tabla_materia(ps, "sistemas") if ps else []
            if "datosMateria!contenidos" in pmat:
                pc = pagina(f"datosMateria!contenidos?tipo=C&actual=menu.solicitud.planificacion.materias.contenidos&codMateria={mat}&codModulo={mod}")
                materia["contenidos"] = textos(pc) if pc else []
            asignaturas = sorted({int(x) for x in re.findall(r"codAsignatura=(\d+)", pmat)})
            materia["asignaturas"] = []
            for a in asignaturas:
                pas = pagina(f"datosAsignatura!consulta.action?codModulo={mod}&codMateria={mat}&codAsignatura={a}"
                             f"&actual=menu.solicitud.planificacion.materias.asignatura")
                if pas:
                    info = parsear_materia(pas)
                    materia["asignaturas"].append({"id": a, **{k: info[k] for k in ("nombre", "caracter", "ects", "unidad_temporal", "despliegue")}})
            bloque["materias"].append(materia)
        memoria["plan"].append(bloque)
    materias = [m for b in memoria["plan"] for m in b["materias"]]
    memoria["cobertura"] = {
        "materias": len(materias),
        "asignaturas": sum(len(m.get("asignaturas", [])) for m in materias),
        "materias_con_evaluacion": sum(1 for m in materias if m.get("evaluacion")),
        "materias_con_actividades": sum(1 for m in materias if m.get("actividades")),
        "centros_con_plazas": sum(1 for c in memoria["centros"] if c.get("plazas_total")),
    }
    memoria["paginas"] = lector.peticiones - inicio + 2
    return memoria


# ------------------------------------------------------------------------------------------ ejecución


MAX_PAGINAS = 400   # una memoria de máster de 120 créditos con muchas asignaturas pasa de 250 páginas
# Cada nivel en su carpeta: así se sabe, solo por los nombres de fichero de la rama sondas, qué códigos están ya
# leídos en cada nivel (hechos_en_sondas) y cada tramo sigue por el siguiente pendiente.
CARPETA = {"ficha": "ruct", "memoria": "ruct_memoria"}


def hechos_en_sondas(nivel: str, desde_sello: str = "") -> set[str]:
    """Códigos ya leídos en ese nivel según los nombres de fichero de la rama sondas (sin bajar su contenido).
    Solo cuentan las carpetas de ejecución con sello igual o posterior a desde_sello."""
    import subprocess

    subprocess.run(["git", "fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", "sondas"], check=True)
    nombres = subprocess.run(["git", "ls-tree", "-r", "--name-only", "FETCH_HEAD"], check=True, capture_output=True,
                             text=True).stdout.split("\n")
    return codigos_en_rutas(nombres, nivel, desde_sello)


def codigos_en_rutas(rutas: list[str], nivel: str, desde_sello: str = "") -> set[str]:
    patron = re.compile(r"^([^/]+)/datos/estudios/masters/" + CARPETA[nivel] + r"/(\d{7})\.json$")
    return {m.group(2) for r in rutas if (m := patron.match(r)) and m.group(1) >= desde_sello}
PAUSA_CORTE = 120   # segundos de espera cuando el servidor deja de responder
PAUSAS_MAX = 5

# Registro público por norma: «tendrá carácter público y de registro administrativo» (RD 1509/2008, art. 1.1) y «la
# consulta al RUCT será pública» (art. 7). Su robots.txt no responde (30/10/2026, desde GitHub y desde España) y la
# RFC 9309 manda tratar eso como prohibido. Excepción del proyecto (la misma que en motor/grados/ruct_grados.py y
# en los boletines oficiales): solo en estas rutas y SOLO mientras robots.txt no se pueda leer; si un día responde,
# manda lo que diga. Una petición por segundo, identificada.
REGISTRO_PUBLICO = BASE
DECISION_RUCT = ("Mandato de Álvaro del 30/10/2026 a las 02:51 («de mí nada, sigue, hay que sacar toda la info»), "
                 "con el mismo criterio que los boletines oficiales", "2026-10-30")


class LectorRegistro(Lector):
    """El lector del RUCT con la comprobación de robots.txt antes de cada petición."""

    def __init__(self, archivo, pausa: float = PAUSA):
        super().__init__(archivo, pausa)
        self.prohibidas = 0
        self.robots_error: str | None = None
        self.excepcion_registro = 0

    def get(self, url: str, intentos: int = 3):
        from motor.http import RobotsProhibe, comprobar_robots, robots_de

        try:
            comprobar_robots(url, self.s)
        except RobotsProhibe as e:
            if url.startswith(REGISTRO_PUBLICO) and robots_de(url, self.s).todo_prohibido:
                self.excepcion_registro += 1  # robots.txt ilegible, no una prohibición escrita
            else:
                self.prohibidas += 1
                self.robots_error = str(e)[:300]
                return 0, "", None
        return super().get(url, intentos)


def resumen_memoria(m: dict) -> dict:
    materias = [x for b in m.get("plan", []) for x in b.get("materias", [])]
    asignaturas = [a for x in materias for a in x.get("asignaturas", [])]
    return {
        "paginas": m.get("paginas"),
        "materias": len(materias),
        "asignaturas": len(asignaturas),
        "materias_con_evaluacion": sum(1 for x in materias if x.get("evaluacion")),
        "materias_con_contenidos": sum(1 for x in materias if x.get("contenidos")),
        "centros_con_plazas": sum(1 for c in m.get("centros", []) if c.get("plazas_total")),
        "error": m.get("error"),
        "avisos": len(m.get("avisos", [])),
    }


def ejecutar(codigos: list[str], raiz: Path, nivel: str, max_minutos: float, pausa_corte: float | None = None,
             pausa: float = PAUSA) -> dict:
    """Lee la ficha (y con nivel «memoria» la memoria vigente) de cada código, en orden.

    Los originales van al archivo con la política del motor: en la rama pública solo índice y huella; enteros en el
    almacén privado con MOTOR_ORIGINALES=s3. Si el servidor deja de responder se espera y se reintenta; si no vuelve
    se para y se dice cuántos códigos quedan."""
    from collections import Counter

    from motor.archivo import solo_huella_por_defecto

    pausa_corte = PAUSA_CORTE if pausa_corte is None else pausa_corte
    archivo = Archivo(raiz / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    lector = LectorRegistro(archivo, pausa=pausa)
    destino = raiz / "datos" / "estudios" / "masters" / CARPETA[nivel]
    destino.mkdir(parents=True, exist_ok=True)
    fin = time.time() + max_minutos * 60
    hechos, errores, seguidos, alerta, pausas = 0, Counter(), 0, None, 0
    resumenes: dict[str, dict] = {}
    pendientes = list(codigos)
    fallidos: list[str] = []
    reintentado = False
    while pendientes or (fallidos and not reintentado):
        if not pendientes:  # los cortes sueltos se reintentan una vez al final
            pendientes, fallidos, reintentado, seguidos = fallidos, [], True, 0
        if time.time() > fin:
            alerta = f"tiempo agotado: quedan {len(pendientes)} códigos"
            break
        codigo = pendientes.pop(0)
        ficha = leer_ficha(lector, codigo)
        if lector.prohibidas:
            alerta = f"robots.txt: {lector.robots_error}"
            print(f"ALERTA RUCT: {alerta}", file=sys.stderr)
            pendientes.insert(0, codigo)
            break
        if "estado 0" in ficha.get("error", ""):
            seguidos += 1
            fallidos.append(codigo)
            if seguidos >= 3:
                # El RUCT tiene cortes de minutos: se espera y se reintenta lo fallido; se para si no vuelve
                pausas += 1
                if pausas > PAUSAS_MAX:
                    alerta = f"el servidor no responde tras {PAUSAS_MAX} pausas de {pausa_corte:.0f} s; detenida"
                    print(f"ALERTA RUCT: {alerta}", file=sys.stderr)
                    break
                pendientes = fallidos + pendientes
                fallidos, seguidos = [], 0
                time.sleep(pausa_corte)
            continue
        seguidos, pausas = 0, 0
        if "error" in ficha:
            errores[ficha["error"]] += 1
        elif nivel == "memoria":
            ficha["memoria"] = leer_memoria(lector, ficha, max_paginas=MAX_PAGINAS)
            resumenes[codigo] = resumen_memoria(ficha["memoria"])
        (destino / f"{codigo}.json").write_text(json.dumps(ficha, ensure_ascii=False, indent=1), encoding="utf-8")
        hechos += 1
    # lo que no se llegó a leer queda anotado para la siguiente pasada
    sin_leer = fallidos + pendientes
    if fallidos:
        errores["sin respuesta del servidor"] += len(fallidos)
    res = {"pedidos": len(codigos), "hechos": hechos, "errores": dict(errores), "peticiones": lector.peticiones,
           "fallos_de_peticion": dict(lector.errores), "pausa_final": round(lector.pausa, 2),
           "pausa_max_usada": round(lector.pausa_max_usada, 2), "alerta": alerta, "sin_leer": sin_leer,
           "peticiones_por_excepcion_de_registro_publico": lector.excepcion_registro,
           "decision_excepcion": DECISION_RUCT if lector.excepcion_registro else None, "memorias": resumenes}
    (destino / f"resumen-{nivel}-{int(time.time())}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1),
                                                                      encoding="utf-8")
    return {k: v for k, v in res.items() if k not in ("memorias", "sin_leer")} | {"sin_leer": len(sin_leer)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--codigos", help="códigos RUCT separados por comas")
    p.add_argument("--codigos-fichero", help="fichero con un código por línea (en orden de prioridad)")
    p.add_argument("--catalogo", help="catalogo.jsonl: lee todos sus códigos vivos")
    p.add_argument("--desde", type=int, default=0)
    p.add_argument("--hasta", type=int)
    p.add_argument("--nivel", choices=["ficha", "memoria"], default="ficha")
    p.add_argument("--max-minutos", type=float, default=50)
    p.add_argument("--pendientes-de-sondas", metavar="SELLO", nargs="?", const="",
                   help="quitar los códigos ya leídos en este nivel en la rama sondas (carpetas desde SELLO)")
    p.add_argument("--tramo", help="solo para distinguir tramos iguales en la matriz del flujo")
    p.add_argument("--pausa", type=float, default=PAUSA,
                   help="segundos entre peticiones de partida (el lector la sube sola si el servidor no responde)")
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    if a.codigos:
        codigos = [c.strip() for c in a.codigos.split(",") if c.strip()]
    elif a.codigos_fichero:
        codigos = Path(a.codigos_fichero).read_text(encoding="utf-8").split()
    elif a.catalogo:
        codigos = [json.loads(l)["codigo_ruct"] for l in Path(a.catalogo).read_text(encoding="utf-8").split("\n") if l.strip()]
    else:
        sys.exit("Falta --codigos, --codigos-fichero o --catalogo")
    codigos = codigos[a.desde:a.hasta]
    if a.pendientes_de_sondas is not None:
        hechos = hechos_en_sondas(a.nivel, a.pendientes_de_sondas)
        codigos = [c for c in codigos if c not in hechos]
        print(f"ya leídos en sondas ({a.nivel}): {len(hechos)}; pendientes: {len(codigos)}", file=sys.stderr)
    print(json.dumps(ejecutar(codigos, Path(a.salida), a.nivel, a.max_minutos, pausa=a.pausa), ensure_ascii=False))


if __name__ == "__main__":
    main()
