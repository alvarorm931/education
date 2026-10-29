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

Uso:
  python -m motor.estudios.ruct --codigos 4318301,3500355 --nivel memoria --salida ruta/
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


class Lector:
    """Sesión educada con el RUCT: identificada, una petición por segundo, originales archivados."""

    def __init__(self, archivo: Archivo | None, pausa: float = PAUSA):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = USER_AGENT
        self.archivo = archivo
        self.pausa = pausa
        self.peticiones = 0
        self.capturas: list[dict] = []

    def get(self, url: str, intentos: int = 3) -> tuple[int, str, dict | None]:
        for i in range(intentos):
            time.sleep(self.pausa)
            self.peticiones += 1
            try:
                r = self.s.get(url, timeout=40)
            except requests.RequestException:
                if i < intentos - 1:
                    time.sleep(5 * (i + 1))
                continue
            if r.status_code in (429, 500, 502, 503, 504) and i < intentos - 1:
                time.sleep(10 * (i + 1))
                continue
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


def ejecutar(codigos: list[str], raiz: Path, nivel: str, max_minutos: float) -> dict:
    archivo = Archivo(raiz / "archivo")
    lector = Lector(archivo)
    destino = raiz / "datos" / "estudios" / "masters" / "ruct"
    destino.mkdir(parents=True, exist_ok=True)
    fin = time.time() + max_minutos * 60
    hechos, errores, seguidos = 0, 0, 0
    alerta = None
    for codigo in codigos:
        if time.time() > fin:
            break
        ficha = leer_ficha(lector, codigo)
        seguidos = seguidos + 1 if "estado 0" in ficha.get("error", "") else 0
        if seguidos >= 3:  # el servidor no responde: se para en vez de agotar el tiempo
            alerta = "ALERTA RUCT: tres fichas seguidas sin respuesta del servidor; ejecución detenida"
            print(alerta, file=sys.stderr)
            break
        if "error" not in ficha and nivel == "memoria":
            ficha["memoria"] = leer_memoria(lector, ficha)
        errores += 1 if "error" in ficha else 0
        (destino / f"{codigo}.json").write_text(json.dumps(ficha, ensure_ascii=False, indent=1), encoding="utf-8")
        hechos += 1
    return {"pedidos": len(codigos), "hechos": hechos, "errores": errores, "peticiones": lector.peticiones, "alerta": alerta}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--codigos", help="códigos RUCT separados por comas")
    p.add_argument("--catalogo", help="catalogo.jsonl: lee todos sus códigos vivos")
    p.add_argument("--nivel", choices=["ficha", "memoria"], default="ficha")
    p.add_argument("--max-minutos", type=float, default=25)
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    if a.codigos:
        codigos = [c.strip() for c in a.codigos.split(",") if c.strip()]
    elif a.catalogo:
        codigos = [json.loads(l)["codigo_ruct"] for l in Path(a.catalogo).read_text(encoding="utf-8").splitlines()]
    else:
        sys.exit("Falta --codigos o --catalogo")
    print(json.dumps(ejecutar(codigos, Path(a.salida), a.nivel, a.max_minutos), ensure_ascii=False))


if __name__ == "__main__":
    main()
