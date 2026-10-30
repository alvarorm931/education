"""Conjunto final de másteres: todo lo capturado, unido por máster, con fuente, URL y fecha de cada dato.

Junta, sin pedir nada a ninguna fuente:
  - catálogo SIIU (y altas del BOE): identidad, universidad, rama, ámbito y cada impartición (centro, municipio,
    presencialidad, idioma extranjero);
  - RUCT, ficha: créditos por tipo, verificación, acreditaciones, plan en el BOE; memoria: habilitación para
    profesión regulada, plazas verificadas y modalidades por centro, idiomas, acceso y admisión, plan entero
    (módulos, materias y asignaturas con ECTS y carácter), evaluación con sus ponderaciones, actividades con sus
    horas y presencialidad, metodologías y contenidos;
  - QEDU, por impartición del curso: plazas, precio del crédito, modalidad, enlace oficial e inserción laboral;
  - webs de los centros (fichas_masters.py, con tarifas en PDF): precio, horario, fechas, becas, salidas, etc.

Cada campo: {valor, fuente, url, capturado} y, si otra fuente da otro valor, «alternativas». La fuente oficial
manda (orden en PRIORIDAD); lo calculado se dice («calculado» y cómo). Fecha estable: con --anterior, un dato que
no ha cambiado conserva su fecha de captura; solo cambia si cambia el dato (CLAUDE.md, ley SEO punto 2).

Datos mínimos para indexar un máster (docs/ley-seo.md): asignaturas y precio. El que no los tiene se genera
igual, con «indexable: false» y lo que le falta.

Salidas: masters_oficiales.jsonl, programas_no_oficiales.jsonl, resumen.json (cobertura por campo y fuente).

Uso:
  python -m motor.estudios.conjunto_masters --catalogo catalogo_final.json --altas boe_altas.jsonl \
      --ruct carpeta [--ruct …] --qedu carpeta [--qedu …] --fichas fichas.jsonl [--anterior conjunto/] --salida ruta/
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

CITAS = {
    "catalogo": "Ministerio de Ciencia, Innovación y Universidades. Sistema Integrado de Información Universitaria (SIIU)",
    "ruct": "Ministerio de Ciencia, Innovación y Universidades. Registro de Universidades, Centros y Títulos (RUCT)",
    "qedu": "Ministerio de Ciencia, Innovación y Universidades. Qué Estudiar y Dónde en la Universidad (QEDU)",
    "boe": "Agencia Estatal Boletín Oficial del Estado",
    "web": "Página del propio centro",
    "tarifa": "Tarifa publicada por el propio centro",
    "guia": "Guía docente publicada por la universidad",
    "calculado": "Cálculo del portal con datos oficiales",
}
URL_SIIU = "https://www.ciencia.gob.es/Ministerio/Estadisticas/SIIU/Clasificaciones.html"
URL_QEDU = "https://www.ciencia.gob.es/qedu.html"

# Qué fuente manda en cada campo (la primera que lo tiene). Las demás quedan como alternativas si dicen otra cosa.
PRIORIDAD = {
    "creditos_ects": ("ruct", "catalogo", "web"),
    "modalidad": ("ruct", "qedu", "catalogo", "web"),
    "plazas": ("qedu", "ruct", "web"),
    "idioma": ("ruct", "qedu", "web"),
    "precio_credito": ("qedu", "web", "tarifa"),
    "precio_total": ("web", "tarifa", "calculado"),
    "asignaturas": ("ruct", "boe", "web"),
    "evaluacion": ("ruct", "guia", "web"),
    "metodologia": ("ruct", "web"),
    "requisitos_acceso": ("ruct", "web"),
    "habilita_profesion": ("ruct", "web"),
    "practicas": ("ruct", "web"),
    "tfm": ("ruct", "web"),
    "universidad_que_expide": ("catalogo", "web"),
    "tipo_titulo": ("catalogo", "web"),
}
NUMERICOS = {"creditos_ects", "plazas", "precio_credito", "precio_total", "reserva_matricula"}
MODALIDAD_QEDU = {"1": "presencial", "2": "semipresencial", "3": "a distancia"}
ESTADOS_WEB_OFICIAL = {"confirmado", "probable_oficial", "confirmado_por_nombre"}
MAX_CONTENIDOS = 3000   # caracteres de contenidos por materia
MAX_TEXTO_ACCESO = 8000
AÑO_ANTIGUO = 2023      # una página que solo habla de cursos de 2023 o antes está, casi seguro, sin actualizar


# Además de lo que ya retira motor.limpieza (tratamientos, nombramientos, documentos de identidad): títulos
# académicos delante de un nombre («Dr. Juan Pérez», «Prof.ª Ana Ruiz») y direcciones de correo, que en las memorias
# suelen ser de personas (coordinación del máster).
RE_TITULO_PERSONA = re.compile(r"(?<![\w.])(?:Dr|Dra|Drª|Prof|Profa|Prof\.ª|Profª)\.?\s+[A-ZÁÉÍÓÚÑ][\wáéíóúñ'-]+\s+[A-ZÁÉÍÓÚÑ]")
RE_CORREO = re.compile(r"(?<![\w.+-])([\w.+-]+)@([\w-]+\.[\w.-]*\w)")
# Buzones de una oficina o servicio (no de una persona): se dejan
BUZON = re.compile(r"(?i)^(info|informacion|información|admisi[oó]n|admisiones|admissions?|admissio|administraci[oó]n|"
                   r"secretar[ií]a|secretaria\w*|master\w*|m[aá]ster\w*|posgrado\w*|postgrado\w*|contacto|contact|"
                   r"jefatura|escola|escuela|matr[ií]cula\w*|becas?|ayudas|comunicaci[oó]n|atenci[oó]n\w*|alumn\w*|"
                   r"estudiantes?|students?|formaci[oó]n|formacio|cursos?|campus\w*|oficina\w*|registro|hola|"
                   r"inscripci[oó]n\w*|inscripciones|preinscripci[oó]n|orientaci[oó]n|calidad|empleo|practicas|"
                   r"pr[aá]cticas|online|programas?|coordinaci[oó]n\w*|direcci[oó]n|international\w*|internacional\w*)"
                   r"([._-]\w+)*$")
PRIVACIDAD = Counter()


def _correo(m: re.Match) -> str:
    if BUZON.match(m.group(1)):
        return m.group(0)
    PRIVACIDAD["correos_retirados"] += 1
    return "[correo]"


def seguro(texto: str | None) -> str | None:
    """El texto sin datos de personas: fuera los párrafos con nombres (motor.limpieza o «Dr./Dra./Prof.» delante
    de un nombre) y las direcciones de correo que no son el buzón de un servicio (se cuentan en PRIVACIDAD)."""
    if not texto:
        return texto
    from motor.limpieza import parrafos_seguros

    lineas, omitidas = parrafos_seguros(texto.split("\n"))
    fuera = [x for x in lineas if RE_TITULO_PERSONA.search(x)]
    PRIVACIDAD["parrafos_retirados"] += omitidas + len(fuera)
    return "\n".join(RE_CORREO.sub(_correo, x) for x in lineas if x not in fuera) or None


def _jsonl(ruta: Path) -> list[dict]:
    if not ruta.exists():
        return []
    datos = gzip.decompress(ruta.read_bytes()) if ruta.suffix == ".gz" else ruta.read_bytes()
    return [json.loads(x) for x in datos.decode("utf-8").split("\n") if x.strip()]


def _hoy() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def campo(valor, fuente: str, url: str | None, capturado: str | None, **extra) -> dict:
    return {"valor": valor, "fuente": fuente, "url": url, "capturado": capturado, **{k: v for k, v in extra.items() if v is not None}}


RE_ID_CATALOGO = re.compile(r"^\s*(?:[A-Z]{1,4}[-.]?\d{1,3}|\d{1,3})[.)\-:]?\s+(?=\S)")


def _limpia_id(s: str) -> str:
    """«3 Clases teóricas», «SE1 Asistencia», «MD3. Seminarios» → sin el número del catálogo del RUCT."""
    return RE_ID_CATALOGO.sub("", s or "", count=1).strip()


# ------------------------------------------------------------------------------------------- cargas


def cargar_ruct(carpetas: list[Path]) -> dict[str, dict]:
    """código → ficha del RUCT (con memoria si alguna lectura la trae), la más reciente."""
    out: dict[str, dict] = {}
    for c in carpetas:
        for f in sorted(list(c.rglob("ruct/*.json")) + list(c.rglob("ruct_memoria/*.json"))):
            if f.name.startswith("resumen"):
                continue
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except ValueError:
                continue
            cod = d.get("codigo")
            if not cod or "error" in d:
                continue
            previa = out.get(cod)
            tiene_memoria = isinstance(d.get("memoria"), dict) and not d["memoria"].get("error")
            previa_memoria = previa is not None and isinstance(previa.get("memoria"), dict) and not previa["memoria"].get("error")
            fecha = (d.get("fuente") or {}).get("capturado") or ""
            if previa is None or (tiene_memoria and not previa_memoria) or \
                    (tiene_memoria == previa_memoria and fecha >= ((previa.get("fuente") or {}).get("capturado") or "")):
                if previa_memoria and not tiene_memoria:
                    d = {**d, "memoria": previa["memoria"]}
                out[cod] = d
    return out


def cargar_qedu(carpetas: list[Path]) -> dict[str, list[dict]]:
    """código → imparticiones del curso según QEDU (tarjeta + detalle + inserción)."""
    tarjetas: dict[tuple, dict] = {}
    detalles: dict[tuple, dict] = {}
    for c in carpetas:
        for f in sorted(c.rglob("qedu_tarjetas_master.jsonl")):
            for t in _jsonl(f):
                tarjetas[(t["codTitula"], t["codCentro"], t["codUniv"])] = t
        for f in sorted(c.rglob("qedu_detalles_master_*.jsonl")):
            for d in _jsonl(f):
                detalles[(d["codTitula"], d["codCentro"], d["codUniv"])] = d
    out: dict[str, list[dict]] = defaultdict(list)
    for k, t in tarjetas.items():
        d = detalles.get(k, {})
        det = d.get("detalle") or {}
        out[k[0]].append({
            "centro": det.get("centro") or t.get("nombreCentro"), "centro_codigo": t["codCentro"],
            "universidad": t.get("nombreUniversidad"), "tipo_centro": det.get("tipo_centro") or t.get("tipoCentro"),
            "provincia": t.get("provincia"), "curso": det.get("curso") or t.get("anio"),
            "modalidad": det.get("modalidad") or MODALIDAD_QEDU.get(str(t.get("modalidad"))),
            "idioma_extranjero": det.get("idioma_extranjero"), "plazas": det.get("plazas"),
            "creditos": det.get("creditos"), "precio_credito": det.get("precio_credito"), "enlace": det.get("enlace"),
            "insercion": d.get("insercion"),
            "capturado": (d.get("fuente") or t.get("fuente") or {}).get("capturado"),
            "con_detalle": bool(det),
        })
    return out


def cargar_boe_planes(carpetas: list[Path]) -> dict[str, dict]:
    """código → plan publicado en el BOE (boe_planes_masters.py), el único del documento o el comprobado."""
    out: dict[str, dict] = {}
    for c in carpetas:
        for f in sorted(c.rglob("boe_planes_masters.jsonl")):
            for d in _jsonl(f):
                planes = [p for p in d.get("planes") or [] if p.get("filas_plan")]
                if len(planes) != 1:  # varios planes en una resolución: sin saber cuál es cuál, ninguno
                    continue
                nuevo = {**planes[0], "identificador": d["identificador"], "url": d.get("url"), "union": d.get("union"),
                         "capturado": d.get("capturado"), "fecha_publicacion": d.get("fecha_publicacion")}
                for cod in d.get("codigos_ruct") or []:
                    # el plan vigente: el comprobado más reciente (un plan nuevo o una modificación que lo publica entero)
                    previo = out.get(cod)
                    if previo is None or (bool(nuevo.get("comprobacion")), nuevo.get("fecha_publicacion") or "") >= \
                            (bool(previo.get("comprobacion")), previo.get("fecha_publicacion") or ""):
                        out[cod] = nuevo
    return out


def campos_boe(plan: dict | None) -> dict[str, dict]:
    if not plan:
        return {}
    tipo = {"basica": "Básica", "obligatoria": "Obligatoria", "optativa": "Optativa", "practicas": "Prácticas externas",
            "tfg": "Trabajo fin de máster"}
    filas = [{"nombre": f.get("nombre"), "caracter": tipo.get(f.get("tipo")) or f.get("caracter"), "ects": f.get("creditos"),
              "curso": f.get("curso"), "semestre": f.get("semestre"), "modulo": f.get("modulo")}
             for f in plan["filas_plan"] if f.get("nombre")]
    nota = ("plan publicado en el BOE" + (f" el {plan['fecha_publicacion'][:4]}" if plan.get("fecha_publicacion") else "")
            + ("; la suma de créditos cuadra con su tabla" if plan.get("comprobacion") else "; sin comprobar la suma"))
    return {"asignaturas": campo(filas, "boe", plan.get("url"), plan.get("capturado"), nota=nota,
                                 comprobado=plan.get("comprobacion"))} if filas else {}


def cargar_guias(carpetas: list[Path]) -> dict[str, list[dict]]:
    """código → guías docentes leídas (guias.py), una por URL (la última)."""
    por_url: dict[str, dict] = {}
    for c in carpetas:
        for f in sorted(c.rglob("guias.jsonl")):
            for g in _jsonl(f):
                if g.get("evaluacion") and (g["url"] not in por_url or g["extraido"] >= por_url[g["url"]]["extraido"]):
                    por_url[g["url"]] = g
    out: dict[str, list[dict]] = defaultdict(list)
    for g in por_url.values():
        for cod in g.get("codigos_ruct") or []:
            out[cod].append(g)
    return out


def campos_guias(gs: list[dict]) -> dict[str, dict]:
    if not gs:
        return {}
    gs = sorted(gs, key=lambda g: g.get("asignatura") or "")
    fecha = max(g.get("extraido") or "" for g in gs) or None
    por_asig = [{"asignatura": g.get("asignatura"), "ects": g.get("creditos"), "curso": g.get("curso_academico") or None,
                 "sistemas": [{"sistema": x["sistema"], "min": x["min"], "max": x["max"]} for x in g["evaluacion"]],
                 "metodologia": g.get("metodologia") or None, "url": g["url"]} for g in gs]
    por = {}
    for g in gs:
        for x in g["evaluacion"]:
            k = x["sistema"].strip().lower()
            y = por.setdefault(k, {"sistema": x["sistema"].strip(), "min": x["min"], "max": x["max"], "materias": 0})
            y["min"], y["max"], y["materias"] = min(y["min"], x["min"]), max(y["max"], x["max"]), y["materias"] + 1
    url = gs[0]["url"] if len(gs) == 1 else None
    return {
        "evaluacion_por_asignatura": campo(por_asig, "guia", url, fecha, nota=f"{len(gs)} guías docentes"),
        "evaluacion": campo({"sistemas": sorted(por.values(), key=lambda x: -x["materias"]), "con_ponderacion": True,
                             "por": "asignatura"}, "guia", url, fecha,
                            nota="sistemas de las guías docentes leídas, con el peso mínimo y máximo que les dan"),
    }


def cargar_web(fichas: Path) -> tuple[dict[str, dict], list[dict]]:
    oficiales, otros = {}, []
    for f in _jsonl(fichas):
        if f.get("grupo") == "oficial":
            if f.get("codigo_ruct") and f.get("comprobacion_nombre") in ESTADOS_WEB_OFICIAL:
                oficiales[f["codigo_ruct"]] = f
        elif f.get("es_master") is not False:
            otros.append(f)
    return oficiales, otros


# ------------------------------------------------------------------------------------- del RUCT


def _hojas(plan: list[dict]) -> list[dict]:
    """Asignaturas del plan; si una materia no se divide (o no se leyeron sus asignaturas), la materia misma."""
    out = []
    for b in plan:
        for m in b.get("materias", []):
            asig = m.get("asignaturas") or []
            if asig:
                out += [{"nombre": a.get("nombre"), "caracter": a.get("caracter"), "ects": a.get("ects"),
                         "temporalidad": a.get("unidad_temporal"), "materia": m.get("nombre"), "modulo": b.get("nombre")}
                        for a in asig if a.get("nombre")]
            elif m.get("hijos"):
                out += [{"nombre": h.get("nombre"), "caracter": None, "ects": None, "temporalidad": None,
                         "materia": m.get("nombre"), "modulo": b.get("nombre")} for h in m["hijos"] if h.get("nombre")]
            elif m.get("nombre"):
                out.append({"nombre": m["nombre"], "caracter": m.get("caracter"), "ects": m.get("ects"),
                            "temporalidad": m.get("unidad_temporal"), "materia": None, "modulo": b.get("nombre")})
    return out


def _plan(plan: list[dict]) -> list[dict]:
    salida = []
    for b in plan:
        materias = []
        for m in b.get("materias", []):
            materias.append({
                "nombre": m.get("nombre"), "caracter": m.get("caracter"), "ects": m.get("ects"),
                "temporalidad": m.get("unidad_temporal"),
                "periodos": sorted((m.get("despliegue") or {}).keys(), key=lambda x: int(x) if str(x).isdigit() else 99),
                "asignaturas": [{"nombre": a.get("nombre"), "caracter": a.get("caracter"), "ects": a.get("ects")}
                                for a in (m.get("asignaturas") or [])] or
                               [{"nombre": h.get("nombre")} for h in (m.get("hijos") or [])],
                "evaluacion": [{"sistema": e.get("sistema"), "min": e.get("ponderacion_min"), "max": e.get("ponderacion_max")}
                               for e in (m.get("evaluacion") or [])],
                "actividades": [{"actividad": a.get("actividad"), "horas": a.get("horas"),
                                 "presencialidad": a.get("presencialidad")} for a in (m.get("actividades") or [])],
                "contenidos": seguro("\n".join(m.get("contenidos") or [])[:MAX_CONTENIDOS]) or None,
            })
        salida.append({"modulo": b.get("nombre"), "ects": b.get("ects"), "materias": materias})
    return salida


def _evaluacion(plan: list[dict], catalogo: list[str]) -> dict | None:
    """Sistemas de evaluación del título con la ponderación mínima y máxima que les da cada materia."""
    por = {}
    for b in plan:
        for m in b.get("materias", []):
            for e in m.get("evaluacion") or []:
                s = (e.get("sistema") or "").strip().rstrip(":").strip()
                if not s:
                    continue
                x = por.setdefault(s, {"sistema": s, "min": None, "max": None, "materias": 0})
                x["materias"] += 1
                for k, v in (("min", e.get("ponderacion_min")), ("max", e.get("ponderacion_max"))):
                    if v is not None:
                        x[k] = v if x[k] is None else (min(x[k], v) if k == "min" else max(x[k], v))
    if por:
        return {"sistemas": sorted(por.values(), key=lambda x: -x["materias"]), "con_ponderacion": True}
    if catalogo:
        return {"sistemas": [{"sistema": _limpia_id(s)} for s in catalogo], "con_ponderacion": False}
    return None


def _presencialidad(plan: list[dict]) -> float | None:
    horas = pres = 0.0
    for b in plan:
        for m in b.get("materias", []):
            for a in m.get("actividades") or []:
                if a.get("horas") and a.get("presencialidad") is not None:
                    horas += a["horas"]
                    pres += a["horas"] * a["presencialidad"] / 100
    return round(100 * pres / horas, 1) if horas else None


def campos_ruct(r: dict) -> dict[str, dict]:
    url = (r.get("fuente") or {}).get("url")
    fecha = (r.get("fuente") or {}).get("capturado")
    out: dict[str, dict] = {}
    cr = r.get("creditos") or {}
    if cr.get("total"):
        out["creditos_ects"] = campo(cr["total"], "ruct", url, fecha)
        out["creditos_por_tipo"] = campo({k: v for k, v in cr.items() if k != "total" and v is not None}, "ruct", url, fecha)
    if cr.get("practicas_externas") is not None:
        out["practicas"] = campo(f"Sí, {cr['practicas_externas']:g} ECTS" if cr["practicas_externas"] else "No",
                                 "ruct", url, fecha)
    if cr.get("tfm"):
        out["tfm"] = campo(f"{cr['tfm']:g} ECTS", "ruct", url, fecha)
    calidad = {"fecha_verificacion": r.get("fecha_verificacion"), "curso_inicio": r.get("curso_inicio"),
               "acreditaciones": r.get("acreditaciones") or [], "extincion": r.get("extincion") or [],
               "nivel": r.get("nivel"), "meces": r.get("meces")}
    out["verificacion_y_acreditacion"] = campo(calidad, "ruct", url, fecha)
    boe = (r.get("boe") or {}).get("plan") or {}
    if boe.get("identificador"):
        out["plan_en_boe"] = campo({"identificador": boe["identificador"], "fecha": boe.get("fecha")}, "boe",
                                   f"https://www.boe.es/buscar/doc.php?id={boe['identificador']}", fecha)
    m = r.get("memoria")
    if not isinstance(m, dict) or m.get("error"):
        return out
    bas = m.get("basicos") or {}
    if bas.get("habilita_profesion_regulada"):
        si = bas["habilita_profesion_regulada"].strip().lower().startswith("s")
        out["habilita_profesion"] = campo(("Sí: " + bas["profesion"]) if si and bas.get("profesion") else ("Sí" if si else "No"),
                                          "ruct", url, fecha)
    centros = m.get("centros") or []
    modalidades = sorted({x for c in centros for x in (c.get("modalidades") or [])})
    if modalidades:
        out["modalidad"] = campo(", ".join(modalidades), "ruct", url, fecha)
    idiomas = sorted({x.capitalize() for c in centros for x in (c.get("idiomas") or [])})
    if idiomas:
        out["idioma"] = campo(", ".join(idiomas), "ruct", url, fecha)
    plazas = [c.get("plazas_total") or c.get("plazas_nuevo_ingreso") for c in centros]
    if any(plazas):
        out["plazas_verificadas"] = campo(sum(p for p in plazas if p), "ruct", url, fecha,
                                          nota="máximo de plazas de nuevo ingreso que fija la memoria verificada",
                                          por_centro=[{"centro_codigo": c.get("codigo"), "plazas": c.get("plazas_total"),
                                                       "por_modalidad": c.get("plazas_por_modalidad") or None,
                                                       "modalidades": c.get("modalidades")} for c in centros])
    plan = m.get("plan") or []
    hojas = _hojas(plan)
    if hojas:
        out["asignaturas"] = campo(hojas, "ruct", url, fecha)
        out["plan"] = campo(_plan(plan), "ruct", url, fecha)
    ev = _evaluacion(plan, (m.get("catalogos") or {}).get("sistemas") or [])
    if ev:
        out["evaluacion"] = campo(ev, "ruct", url, fecha)
    met = [_limpia_id(x) for x in (m.get("catalogos") or {}).get("metodologias") or [] if x]
    if met:
        out["metodologia"] = campo(met, "ruct", url, fecha)
    act = [_limpia_id(x) for x in (m.get("catalogos") or {}).get("actividades") or [] if x]
    if act:
        out["actividades_formativas"] = campo(act, "ruct", url, fecha)
    p = _presencialidad(plan)
    if p is not None:
        out["presencialidad_horas"] = campo(p, "calculado", url, fecha,
                                            nota="porcentaje de horas presenciales sobre las horas de las actividades de la memoria")
    acceso = (m.get("acceso") or {}).get("textos") or []
    acceso = seguro("\n\n".join(acceso)[:MAX_TEXTO_ACCESO]) if acceso else None
    if acceso:
        out["requisitos_acceso"] = campo(acceso, "ruct", url, fecha)
    descripcion = seguro("\n".join(m.get("descripcion_plan") or [])[:MAX_TEXTO_ACCESO])
    if descripcion:
        out["descripcion_plan"] = campo(descripcion, "ruct", url, fecha)
    if m.get("universidades") and len(m["universidades"]) > 1:
        out["universidades_participantes"] = campo([u.get("nombre") for u in m["universidades"]], "ruct", url, fecha)
    return out


# ------------------------------------------------------------------------------------------ de QEDU


def campos_qedu(imps: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    con = [i for i in imps if i.get("con_detalle")]
    if not imps:
        return out
    fecha = max((i.get("capturado") or "") for i in imps) or None
    precios = sorted({i["precio_credito"] for i in con if i.get("precio_credito")})
    if precios:
        out["precio_credito"] = campo(precios[0] if len(precios) == 1 else {"desde": precios[0], "hasta": precios[-1]},
                                      "qedu", URL_QEDU, fecha, nota="primera matrícula, curso " + str(con[0].get("curso")))
    plazas = [i["plazas"] for i in con if i.get("plazas")]
    if plazas:
        out["plazas"] = campo(sum(plazas), "qedu", URL_QEDU, fecha, nota="plazas ofertadas en el curso, suma de centros")
    mods = sorted({i["modalidad"] for i in imps if i.get("modalidad")})
    if mods:
        out["modalidad"] = campo(", ".join(m.lower() for m in mods), "qedu", URL_QEDU, fecha)
    ins = [i["insercion"] for i in con if i.get("insercion") and any(v is not None for v in i["insercion"].values())]
    if ins:
        out["insercion_laboral"] = campo(ins[0], "qedu", URL_QEDU, fecha,
                                         nota="del título; afiliación a la Seguridad Social de los titulados")
    enlaces = sorted({i["enlace"] for i in con if i.get("enlace")})
    if enlaces:
        out["web_oficial"] = campo(enlaces[0] if len(enlaces) == 1 else enlaces, "qedu", URL_QEDU, fecha)
    return out


# ------------------------------------------------------------------------------------------- de la web


def campos_web(f: dict) -> dict[str, dict]:
    out = {}
    fuentes = f.get("fuentes") or []
    for nombre, c in (f.get("campos") or {}).items():
        fu = fuentes[c["fuente"]] if isinstance(c.get("fuente"), int) and c["fuente"] < len(fuentes) else {}
        tipo = "tarifa" if fu.get("pagina") == "documento" else "web"
        valor = c.get("valor")
        if isinstance(valor, str) and nombre != "nombre":
            valor = seguro(valor)
            if not valor:
                continue
        out[nombre] = campo(valor, tipo, fu.get("url"), fu.get("extraido"), cita_sha256=c.get("cita_sha256"),
                            cita_nivel=c.get("cita_nivel"), curso=fu.get("curso"))
    return out


def pagina_antigua(campos: dict) -> bool:
    """La página habla de fechas o cursos y todos son de AÑO_ANTIGUO o antes."""
    años = []
    for k in ("fecha_inicio", "plazo_admision", "precio_total", "precio_credito"):
        v = (campos.get(k) or {}).get("valor")
        if isinstance(v, str):
            años += [int(a) for a in re.findall(r"\b(20[0-3]\d)\b", v)]
    return bool(años) and max(años) <= AÑO_ANTIGUO


# ---------------------------------------------------------------------------------------- composición


def _igual(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) < 0.01
    return json.dumps(a, ensure_ascii=False, sort_keys=True).lower() == json.dumps(b, ensure_ascii=False, sort_keys=True).lower()


def unir(por_fuente: dict[str, dict[str, dict]]) -> dict[str, dict]:
    """Un valor por campo según PRIORIDAD (o el orden de por_fuente); los distintos, como alternativas."""
    nombres = []
    for d in por_fuente.values():
        nombres += [n for n in d if n not in nombres]
    out = {}
    for n in nombres:
        orden = PRIORIDAD.get(n) or tuple(por_fuente)
        orden = tuple(orden) + tuple(f for f in por_fuente if f not in orden)
        elegidos = [por_fuente[f][n] for f in orden if f in por_fuente and n in por_fuente[f]
                    and por_fuente[f][n].get("valor") not in (None, "", [], {})]
        if not elegidos:
            continue
        principal = dict(elegidos[0])
        alt = [{"valor": e["valor"], "fuente": e["fuente"], "url": e.get("url")} for e in elegidos[1:]
               if not _igual(e["valor"], principal["valor"]) and not isinstance(e["valor"], (list, dict))]
        if alt:
            principal["alternativas"] = alt
        out[n] = principal
    return out


def precio_calculado(campos: dict) -> dict | None:
    pc, cr = campos.get("precio_credito"), campos.get("creditos_ects")
    if not pc or not cr or not isinstance(pc.get("valor"), (int, float)) or not isinstance(cr.get("valor"), (int, float)):
        return None
    return campo(round(pc["valor"] * cr["valor"], 2), "calculado", pc.get("url"), pc.get("capturado"),
                 nota=f"precio del crédito en primera matrícula ({pc['valor']:g} €, {pc['fuente']}) × "
                      f"{cr['valor']:g} créditos ({cr['fuente']}); sin tasas de secretaría ni seguro")


def datos_minimos(campos: dict) -> list[str]:
    falta = []
    if not campos.get("asignaturas"):
        falta.append("asignaturas")
    if not (campos.get("precio_total") or campos.get("precio_credito")):
        falta.append("precio")
    return falta


def oficial(cod: str, cat: dict, ruct: dict | None, imps: list[dict], web: dict | None,
            fecha_catalogo: str | None = None, universidades: dict[str, str] | None = None,
            plan_boe: dict | None = None, guias: list[dict] | None = None) -> dict:
    url_cat = (cat.get("fuente") or {}).get("url") or URL_SIIU
    fecha_cat = (cat.get("fuente") or {}).get("capturado") or fecha_catalogo
    nombre_uni = (universidades or {}).get(cat.get("universidad_codigo") or "") or \
        next((i.get("universidad") for i in imps if i.get("universidad")), None) or cat.get("universidad")
    por_fuente: dict[str, dict] = {}
    if ruct:
        r = campos_ruct(ruct)
        por_fuente["ruct"] = {k: v for k, v in r.items() if v["fuente"] == "ruct"}
        por_fuente["boe"] = {k: v for k, v in r.items() if v["fuente"] == "boe"}
        calc = {k: v for k, v in r.items() if v["fuente"] == "calculado"}
    else:
        calc = {}
    por_fuente.setdefault("boe", {}).update(campos_boe(plan_boe))
    por_fuente["qedu"] = campos_qedu(imps)
    pres = sorted({i.get("presencialidad") for i in cat.get("imparticiones") or [] if i.get("presencialidad")})
    por_fuente["catalogo"] = {
        "tipo_titulo": campo("máster universitario oficial", "catalogo", url_cat, fecha_cat),
        "universidad_que_expide": campo(nombre_uni, "catalogo", url_cat, fecha_cat),
        **({"modalidad": campo(", ".join(p.replace("Estudio ", "").lower() for p in pres), "catalogo", url_cat, fecha_cat)}
           if pres else {}),
    }
    w = campos_web(web) if web else {}
    por_fuente["web"] = {k: v for k, v in w.items() if v["fuente"] == "web"}
    por_fuente["tarifa"] = {k: v for k, v in w.items() if v["fuente"] == "tarifa"}
    por_fuente["calculado"] = calc
    por_fuente["guia"] = campos_guias(guias or [])
    # la evaluación de la memoria sin ponderaciones (formato RD 822/2021) cede ante la de las guías, que las tienen
    ev = por_fuente.get("ruct", {}).get("evaluacion")
    if ev and not ev["valor"].get("con_ponderacion") and "evaluacion" in por_fuente["guia"]:
        por_fuente["ruct"] = {k: v for k, v in por_fuente["ruct"].items() if k != "evaluacion"}
        por_fuente["ruct_catalogo"] = {"evaluacion": ev}
    campos = unir(por_fuente)
    if "precio_total" not in campos:
        pc = precio_calculado(campos)
        if pc:
            campos["precio_total"] = pc
    falta = datos_minimos(campos)
    return {
        "id": f"ruct:{cod}", "tipo": "oficial", "codigo_ruct": cod,
        "nombre": cat.get("nombre_oficial") or (ruct or {}).get("nombre"),
        "universidad": nombre_uni, "universidad_tipo": cat.get("universidad_tipo"),
        "comunidad": cat.get("universidad_comunidad"), "rama": cat.get("rama") or (ruct or {}).get("rama"),
        "ambito": cat.get("ambito"), "situacion": cat.get("situacion"), "origen": cat.get("origen", "catalogo_siiu"),
        "imparticiones": [{"centro": i.get("unidad"), "centro_codigo": i.get("unidad_codigo"), "municipio": i.get("municipio"),
                           "tipo_centro": i.get("unidad_modalidad"), "presencialidad": i.get("presencialidad"),
                           "idioma_extranjero": i.get("idioma_extranjero"),
                           "qedu": next((q for q in imps if q["centro_codigo"] == i.get("unidad_codigo")), None)}
                          for i in cat.get("imparticiones") or []]
                         + [{"centro": q["centro"], "centro_codigo": q["centro_codigo"], "qedu": q} for q in imps
                            if q["centro_codigo"] not in {i.get("unidad_codigo") for i in cat.get("imparticiones") or []}],
        "en_oferta_del_curso": bool(imps),
        "campos": campos,
        "paginas_web": (web or {}).get("paginas") or [],
        "pagina_web_antigua": pagina_antigua(w) if w else None,
        "datos_minimos_faltan": falta, "indexable": not falta,
        "fuentes_usadas": sorted({c["fuente"] for c in campos.values()}),
    }


def no_oficial(grupo: list[dict]) -> dict:
    """Un programa (mismo centro, nombre y tipo) con sus páginas: manda la que más campos tiene."""
    grupo = sorted(grupo, key=lambda f: (-len(f.get("campos") or {}), f.get("url") or ""))
    f = grupo[0]
    por_fuente = {"web": {}, "tarifa": {}}
    for g in grupo:
        for k, v in campos_web(g).items():
            por_fuente[v["fuente"]].setdefault(k, v)
    campos = unir(por_fuente)
    falta = datos_minimos(campos)
    return {
        "id": f.get("programa") or f.get("clave"), "tipo": "no_oficial", "nombre": (campos.get("nombre") or {}).get("valor"),
        "centro": f.get("centro"), "tipo_centro": f.get("tipo_centro"), "proveedor": f.get("proveedor"),
        "dominio": f.get("dominio"), "es_master": f.get("es_master"), "url": f.get("url"),
        "otras_paginas": [g.get("url") for g in grupo[1:]],
        "campos": campos, "pagina_web_antigua": pagina_antigua(campos),
        "datos_minimos_faltan": falta, "indexable": not falta,
        "fuentes_usadas": sorted({c["fuente"] for c in campos.values()}),
    }


def huella(valor) -> str:
    return hashlib.sha256(json.dumps(valor, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]


def fechas_estables(registros: list[dict], anterior: dict[str, dict], hoy: str) -> Counter:
    """El dato que no cambia conserva la fecha de captura que tenía; el nuevo o cambiado la toma de su fuente. La
    fecha de la pasada va solo en resumen.json («generado»): así un conjunto sin cambios es el mismo fichero."""
    cuentas = Counter()
    for r in registros:
        previo = (anterior.get(r["id"]) or {}).get("campos") or {}
        for n, c in r["campos"].items():
            h = huella(c["valor"])
            c["huella"] = h
            p = previo.get(n)
            if p and p.get("huella") == h and p.get("capturado"):
                c["capturado"] = p["capturado"]
                cuentas["sin_cambios"] += 1
            else:
                c["capturado"] = c.get("capturado") or hoy
                cuentas["cambiados" if p else "nuevos"] += 1
        cuentas["retirados"] += sum(1 for n in previo if n not in r["campos"])
    return cuentas


def _anterior(carpeta: Path | None) -> dict[str, dict]:
    if not carpeta:
        return {}
    out = {}
    for nombre in ("masters_oficiales.jsonl", "programas_no_oficiales.jsonl"):
        for ruta in (carpeta / nombre, carpeta / (nombre + ".gz")):
            for r in _jsonl(ruta):
                out[r["id"]] = r
    return out


def ejecutar(catalogo: Path, salida: Path, altas: Path | None = None, ruct: list[Path] = (), qedu: list[Path] = (),
             fichas: Path | None = None, anterior: Path | None = None, fecha_catalogo: str | None = None,
             boe: list[Path] = (), guias: list[Path] = ()) -> dict:
    texto = catalogo.read_text(encoding="utf-8").strip()
    filas = json.loads(texto) if texto.startswith("[") else [json.loads(l) for l in texto.split("\n") if l.strip()]
    fecha_catalogo = fecha_catalogo or datetime.fromtimestamp(catalogo.stat().st_mtime, timezone.utc).date().isoformat()
    cat = {t["codigo_ruct"]: t for t in filas if t.get("situacion") == "Activo"}
    todos = {t["codigo_ruct"] for t in filas}
    r_ruct = cargar_ruct(list(ruct))
    r_qedu = cargar_qedu(list(qedu))
    r_boe = cargar_boe_planes(list(boe))
    r_guias = cargar_guias(list(guias))
    # nombre completo de cada universidad (el catálogo da «Sevilla»; QEDU, «Universidad de Sevilla»)
    universidades = {}
    for c, imps in r_qedu.items():
        cu = (cat.get(c) or {}).get("universidad_codigo")
        for i in imps:
            if cu and i.get("universidad"):
                universidades.setdefault(cu, i["universidad"])
    por_nombre = {}
    for t in filas:
        for n in (t.get("universidad"), universidades.get(t.get("universidad_codigo") or "")):
            if n:
                por_nombre.setdefault(n.lower(), t)
    if altas:
        for a in _jsonl(altas):
            if a["codigo_ruct"] not in todos:
                u = por_nombre.get((a.get("universidad") or "").lower(), {})
                cat.setdefault(a["codigo_ruct"], {
                    "codigo_ruct": a["codigo_ruct"], "nombre_oficial": a.get("nombre"), "universidad": a.get("universidad"),
                    "universidad_codigo": u.get("universidad_codigo"), "universidad_tipo": u.get("universidad_tipo"),
                    "universidad_comunidad": u.get("universidad_comunidad"),
                    "situacion": "Activo", "origen": "boe_alta", "imparticiones": [],
                    "fuente": {"url": f"https://www.boe.es/buscar/doc.php?id={a.get('boe')}", "capturado": a.get("fecha")}})
    web_of, web_no = cargar_web(fichas) if fichas else ({}, [])
    hoy = _hoy()
    oficiales = [oficial(c, cat[c], r_ruct.get(c), r_qedu.get(c, []), web_of.get(c), fecha_catalogo, universidades,
                         r_boe.get(c), r_guias.get(c)) for c in sorted(cat)]
    por_programa: dict[str, list[dict]] = defaultdict(list)
    for f in web_no:
        por_programa[f.get("programa") or f.get("clave")].append(f)
    programas = [no_oficial(g) for _, g in sorted(por_programa.items())]
    prev = _anterior(anterior)
    fechas = fechas_estables(oficiales + programas, prev, hoy)
    salida.mkdir(parents=True, exist_ok=True)
    for nombre, regs in (("masters_oficiales.jsonl.gz", oficiales), ("programas_no_oficiales.jsonl.gz", programas)):
        datos = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in regs).encode("utf-8")
        (salida / nombre).write_bytes(gzip.compress(datos, mtime=0))

    def cobertura(regs: list[dict]) -> dict:
        por = defaultdict(Counter)
        for r in regs:
            for n, c in r["campos"].items():
                por[n][c["fuente"]] += 1
        return {n: {"total": sum(v.values()), **dict(v)} for n, v in sorted(por.items(), key=lambda x: -sum(x[1].values()))}

    resumen = {
        "generado": hoy,
        "oficiales": len(oficiales),
        "oficiales_con_ruct_ficha": sum(1 for c in cat if c in r_ruct),
        "oficiales_con_ruct_memoria": sum(1 for c in cat if isinstance((r_ruct.get(c) or {}).get("memoria"), dict)
                                          and not r_ruct[c]["memoria"].get("error")),
        "oficiales_en_qedu": sum(1 for c in cat if r_qedu.get(c)),
        "oficiales_con_plan_boe": sum(1 for c in cat if c in r_boe),
        "oficiales_con_guias": sum(1 for c in cat if c in r_guias),
        "oficiales_con_web": sum(1 for c in cat if c in web_of),
        "oficiales_indexables": sum(1 for r in oficiales if r["indexable"]),
        "oficiales_faltan": dict(Counter(x for r in oficiales for x in r["datos_minimos_faltan"])),
        "oficiales_por_titularidad": {t: {"total": sum(1 for r in oficiales if r["universidad_tipo"] == t),
                                          "indexables": sum(1 for r in oficiales if r["universidad_tipo"] == t and r["indexable"])}
                                      for t in ("Pública", "Privada")},
        "programas_no_oficiales": len(programas),
        "programas_master": sum(1 for p in programas if p.get("es_master")),
        "programas_indexables": sum(1 for p in programas if p["indexable"]),
        "paginas_web_antiguas": {"oficiales": sum(1 for r in oficiales if r.get("pagina_web_antigua")),
                                 "no_oficiales": sum(1 for p in programas if p.get("pagina_web_antigua"))},
        "fechas": dict(fechas),
        "privacidad": dict(PRIVACIDAD),
        "cobertura_oficiales": cobertura(oficiales),
        "cobertura_no_oficiales": cobertura(programas),
        "fuentes": CITAS,
    }
    (salida / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    return resumen


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--catalogo", required=True)
    p.add_argument("--altas")
    p.add_argument("--ruct", action="append", default=[])
    p.add_argument("--qedu", action="append", default=[])
    p.add_argument("--fichas")
    p.add_argument("--boe", action="append", default=[], help="carpetas con boe_planes_masters.jsonl")
    p.add_argument("--guias", action="append", default=[], help="carpetas con guias.jsonl (guias.py)")
    p.add_argument("--anterior")
    p.add_argument("--fecha-catalogo", help="fecha de descarga del catálogo SIIU (por defecto, la del fichero)")
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    res = ejecutar(Path(a.catalogo), Path(a.salida), Path(a.altas) if a.altas else None, [Path(x) for x in a.ruct],
                   [Path(x) for x in a.qedu], Path(a.fichas) if a.fichas else None, Path(a.anterior) if a.anterior else None,
                   a.fecha_catalogo, [Path(x) for x in a.boe], [Path(x) for x in a.guias])
    print(json.dumps({k: v for k, v in res.items() if not k.startswith("cobertura")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
