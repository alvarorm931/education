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
    "calculado": "Cálculo del portal con los datos que se indican",
    "norma": "Precio público fijado por la norma de la comunidad autónoma",
}
URL_SIIU = "https://www.ciencia.gob.es/Ministerio/Estadisticas/SIIU/Clasificaciones.html"
URL_QEDU = "https://www.ciencia.gob.es/qedu.html"

# Qué fuente manda en cada campo (la primera que lo tiene). Las demás quedan como alternativas si dicen otra cosa.
PRIORIDAD = {
    "creditos_ects": ("ruct", "qedu", "catalogo", "web"),
    # el catálogo (SIIU) dice la modalidad de cada impartición registrada; QEDU solo «semipresencial o a distancia»
    # o «varias modalidades» cuando no es presencial
    "modalidad": ("ruct", "catalogo", "qedu", "web"),
    "plazas": ("qedu", "ruct", "web"),
    "idioma": ("ruct", "qedu", "web"),
    "precio_credito": ("qedu", "norma", "web", "tarifa"),
    "precio_total": ("web", "tarifa", "calculado"),
    "asignaturas": ("ruct", "boe", "web"),
    "evaluacion": ("ruct", "guia", "web"),
    "metodologia": ("ruct", "web"),
    "requisitos_acceso": ("ruct", "web"),
    "habilita_profesion": ("ruct", "boe", "web"),
    "practicas": ("ruct", "web"),
    "tfm": ("ruct", "web"),
    "universidad_que_expide": ("catalogo", "boe", "web"),
    "tipo_titulo": ("catalogo", "boe", "web"),
}
NUMERICOS = {"creditos_ects", "plazas", "precio_credito", "precio_total", "reserva_matricula"}
# Código de modalidad de las tarjetas de QEDU → el texto que da su detalle (medido en 2.701 imparticiones con los
# dos, 30/10/2026: 1 = «Presencial», 2 = «Semi/No presencial», 4 y -1 = «Varias modalidades»)
MODALIDAD_QEDU = {"1": "presencial", "2": "semipresencial o a distancia", "4": "varias modalidades",
                  "-1": "varias modalidades"}
MODALIDAD_DETALLE = {"semi/no presencial": "semipresencial o a distancia"}
ESTADOS_WEB_OFICIAL = {"confirmado", "probable_oficial", "confirmado_por_nombre"}
MAX_CONTENIDOS = 3000   # caracteres de contenidos por materia
MAX_TEXTO_ACCESO = 8000
AÑO_ANTIGUO = 2023      # una página que solo habla de cursos de 2023 o antes está, casi seguro, sin actualizar


# Además de lo que ya retira motor.limpieza (tratamientos, nombramientos, documentos de identidad): títulos
# académicos delante de un nombre («Dr. Juan Pérez», «Prof.ª Ana Ruiz») y direcciones de correo, que en las memorias
# suelen ser de personas (coordinación del máster).
_MAY = "A-ZÁÉÍÓÚÑÀÈÒÇ"
_PAL = rf"[{_MAY}][\wáéíóúñàèòçü'’-]+"
# «Dr. Pérez», «Dra. M. Ruiz», «Prof.ª Ana Ruiz»: tras la abreviatura, una palabra que no sea una categoría
RE_TITULO_PERSONA = re.compile(rf"(?<![\w.])(?:Dr|Dra|Drª|Dr\.ª|Prof|Profa|Prof\.ª|Profª)\.?\s+(?:[{_MAY}]\.\s*)*(?P<n>{_PAL})")
NO_APELLIDO = {"titular", "titulares", "asociado", "asociada", "asociados", "ayudante", "ayudantes", "contratado",
               "contratada", "emerito", "emerita", "visitante", "colaborador", "colaboradora", "doctor", "doctora",
               "catedratico", "catedratica", "honoris", "invitado", "invitada", "agregado", "agregada", "lector",
               "lectora", "sustituto", "sustituta", "permanente", "interino", "interina", "universidad", "universitat",
               "universitario", "universitaria", "ordinario", "ordinaria", "adjunto", "adjunta", "investigador",
               "investigadora", "pleno", "plena", "honorario", "honoraria", "tutor", "tutora", "agregat", "associat"}
# «Profesora Ana Ruiz», «Doctor Juan García»: con la palabra entera, solo si sigue un nombre de pila
RE_TRATO_PERSONA = re.compile(rf"(?<![\w])(?:Doctor|Doctora|Profesor|Profesora|Professor|Professora|Docente)\s+(?P<n>{_PAL})\s+{_PAL}")
# «Coordinación: Ana Ruiz Gil», «a cargo de Juan Pérez», «formado por María López»: nombre de pila y apellido
RE_CARGO_PERSONA = re.compile(
    rf"(?i:coordinador[a]?|coordinadores|coordinaci[oó]n|coordinat\w*|director[a]?|directores|direcci[oó]n|"
    rf"responsables?|a cargo de|formad[oa]s? por|impartid[oa]s? por|integrad[oa]s? por|directed by|coordinated by|"
    rf"led by|taught by|tutor[a]?|profesorado|equipo docente|claustro)"
    rf"(?:\s+(?i:del m[aá]ster|de la titulaci[oó]n|acad[eé]mic[oa]|del programa|general))?\s*[:\-–]?\s*"
    rf"(?:(?:D\.|Dña\.|Dª|Dr\.|Dra\.|Prof\.|Profa\.)\s*)?(?P<n>{_PAL})\s+{_PAL}")
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
CLAVE_DE_ELEMENTO = ("nombre", "sistema", "asignatura", "actividad")


def _sin_tildes(t: str) -> str:
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))


def es_buzon(local: str) -> bool:
    """El buzón de un servicio («master.biologia@», «info@»), no el de una persona («master.juan@», «ana.ruiz@»)."""
    from motor.limpieza import NOMBRES_PILA

    if not BUZON.match(local):
        return False
    resto = [_sin_tildes(t) for t in re.split(r"[._-]", local.lower())[1:] if t]
    return not any(t in NOMBRES_PILA for t in resto)


def _es_nombre(palabra: str) -> bool:
    from motor.limpieza import NO_NOMBRE, NOMBRES_PILA

    w = _sin_tildes(palabra.lower().strip(".,'’"))
    return w in NOMBRES_PILA and w not in NO_NOMBRE


def con_persona(linea: str) -> re.Match | None:
    """Primera mención de una persona por su título o su cargo (lo que no ve motor.limpieza)."""
    for m in RE_TITULO_PERSONA.finditer(linea):
        if _sin_tildes(m.group("n").lower()) not in NO_APELLIDO:
            return m
    for rx in (RE_TRATO_PERSONA, RE_CARGO_PERSONA):
        for m in rx.finditer(linea):
            if _es_nombre(m.group("n")):
                return m
    return None


def _correo(m: re.Match) -> str:
    if es_buzon(m.group(1)):
        return m.group(0)
    PRIVACIDAD["correos_retirados"] += 1
    return "[correo]"


def seguro(texto: str | None) -> str | None:
    """El texto sin datos de personas: fuera los párrafos con nombres (motor.limpieza o «Dr./Dra./Prof.» delante
    de un nombre) y las direcciones de correo que no son el buzón de un servicio (se cuentan en PRIVACIDAD)."""
    if not texto:
        return texto
    from motor.limpieza import parrafos_seguros

    crudas = texto.split("\n")
    # el texto de los PDF parte las frases en líneas: el nombre puede quedar en la siguiente («Dr.» / «Pérez»)
    malo = [bool(x) and bool(parrafos_seguros([x])[1] or con_persona(x)) for x in crudas]
    fuera = {i for i, m in enumerate(malo) if m}
    for i in range(len(crudas) - 1):
        if not malo[i] and not malo[i + 1] and crudas[i] and crudas[i + 1]:
            junta = crudas[i] + " " + crudas[i + 1]
            if parrafos_seguros([junta])[1] or con_persona(junta):
                fuera.update((i, i + 1))  # la mención cruza las dos líneas
    lineas = [x for i, x in enumerate(crudas) if i not in fuera and x]
    PRIVACIDAD["parrafos_retirados"] += sum(1 for i in fuera if crudas[i])
    return "\n".join(RE_CORREO.sub(_correo, x) for x in lineas) or None


def seguro_valor(v):
    """seguro() sobre cada texto de una lista o un diccionario (asignaturas, sistemas, metodologías…)."""
    if isinstance(v, str):
        return seguro(v)
    if isinstance(v, list):
        out = []
        for x in v:
            if isinstance(x, list) and x and isinstance(x[0], str):  # [nombre, ects]
                n = seguro(x[0])
                y = [n] + x[1:] if n else None
            elif isinstance(x, dict):
                y = seguro_valor(x)
                if any(x.get(k) and not y.get(k) for k in CLAVE_DE_ELEMENTO):
                    y = None  # sin su nombre, el elemento no dice nada
            else:
                y = seguro_valor(x)
            if y not in (None, "", [], {}):
                out.append(y)
        return out
    if isinstance(v, dict):
        return {k: (x if k in ("url", "fuente", "capturado") else seguro_valor(x)) for k, x in v.items()}
    return v


# ------------------------------------------------------------------------------------- asignaturas

# Lo que el extractor escribe cuando la página no da la lista, y filas que no son una asignatura
COMENTARIO = re.compile(r"(?i)^\W*(no se (indica|especifica|detalla|menciona|incluye|muestra|proporciona)|no (est[aá]n? )?"
                        r"(especificad|indicad|disponible|consta|detallad|publicad)|sin (especificar|datos|detalle|"
                        r"informaci)|n/?a\b|ninguna?\b|desconocid|(la )?lista (completa|de asignaturas)|ver (la )?"
                        r"(web|p[aá]gina|plan)|cons[uú]ltese|consultar|pendiente|varias asignaturas|otras asignaturas|"
                        r"etc\b|\.\.\.)")
# Filas que no son una asignatura: el TFM, las prácticas, el bloque de optativas u obligatorias, un módulo o un
# semestre (empiecen como empiecen: «Prácticas Académicas Externas», «Optativas (OP)», «Módulo de Robótica») y
# cabeceras sueltas. «Optativa: Marketing digital» sí es una asignatura.
NO_ES_ASIGNATURA = re.compile(
    r"(?i)^\W*(trabajo (de )?fin(al)? de m[aá]ster|tfm\b|treball (de )?fi de m[aà]ster|master'?s? (thesis|final project)|"
    r"final master'?s? (project|thesis)|pr[aá]cticas? (externas?|en empresas?|profesionales|curriculares|acad[eé]micas)|"
    r"pr[aá]cticas\b\W*$|practicum|pr[aà]ctiques|optativ|optatividad|asignaturas optativas|obligatori|"
    r"semestre|semester|cuatrimestre|primer (curso|semestre|cuatrimestre)|"
    r"segundo (curso|semestre|cuatrimestre)|[12][ºª]? (curso|semestre)|curso \d|plan de estudios|asignaturas\b\W*$|"
    r"materias\b\W*$|total\b|cr[eé]ditos\b|ects\b)")
ASIGNATURA_CON_ETIQUETA = re.compile(r"(?i)^\W*(optativa|obligatoria)s?\s*[:–-]\s*\w{3,}")
# «Módulo 3. Evaluación y tratamiento psicológico» es contenido (así presentan el plan muchos títulos propios);
# «Módulo I», «Módulo obligatorio» o «Bloque de prácticas», no: se mira lo que queda tras la etiqueta
ETIQUETA_DE_BLOQUE = re.compile(r"(?i)^\W*(m[oó]dulo|module|bloque|block|unidad|unit|tema|parte|part)\b\s*"
                                r"(?:[\dIVXLivxl]+[ºª]?|[A-Z]\b)?\s*[.:–-]?\s*(?:(?:de|del|of)\s+)?")
BLOQUE_GENERICO = {"comun", "especifico", "especificos", "obligatorio", "obligatorios", "optativo", "optativos", "basico",
                   "fundamental", "general", "transversal", "troncal", "complementario", "complementarios", "formacion",
                   "practico", "practicas", "itinerario", "especialidad", "especializacion", "nivelacion", "introductorio",
                   "final", "trabajo", "proyecto", "contenidos", "materias", "asignaturas"}
MIN_ASIGNATURAS = 3


def nombre_de_asignatura(n) -> bool:
    """Una fila con nombre de verdad: no «No se indica», ni una letra suelta, ni solo números."""
    n = (n or "").strip() if isinstance(n, str) else ""
    return len(re.findall(r"[^\W\d_]", n)) >= 2 and not COMENTARIO.match(n)


def es_asignatura_real(n: str) -> bool:
    n = (n or "").strip()
    if not nombre_de_asignatura(n) or len(n) <= 3:
        return False
    if ASIGNATURA_CON_ETIQUETA.match(n):
        return True
    resto = ETIQUETA_DE_BLOQUE.sub("", n, count=1).strip(" .:-–()") if ETIQUETA_DE_BLOQUE.match(n) else n
    if resto != n:
        primera = _sin_tildes((re.findall(r"[^\W\d_]+", resto.lower()) or [""])[0])
        if not nombre_de_asignatura(resto) or primera in BLOQUE_GENERICO:
            return False
    return not NO_ES_ASIGNATURA.match(resto)


def asignaturas_reales(nombres: list[str]) -> int:
    return sum(1 for n in nombres if es_asignatura_real(n))


def _nombre_fila(x) -> str:
    if isinstance(x, dict):
        return x.get("nombre") or ""
    if isinstance(x, list):
        return x[0] if x and isinstance(x[0], str) else ""
    return x if isinstance(x, str) else ""


def asignaturas_validas(valor) -> list | None:
    """La lista sin filas vacías o de comentario, si quedan al menos MIN_ASIGNATURAS asignaturas de verdad (sin contar
    TFM, prácticas ni cabeceras); si no, None: la lista no basta para enseñar el plan."""
    if isinstance(valor, str):  # «Marketing; Analítica; …»
        valor = [x.strip() for x in re.split(r"\s*[;\n•·]\s*", valor) if x.strip()]
    if not isinstance(valor, list):
        return None
    filas = [x for x in valor if nombre_de_asignatura(_nombre_fila(x))]
    return filas if asignaturas_reales([_nombre_fila(x) for x in filas]) >= MIN_ASIGNATURAS else None


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
            "modalidad": (MODALIDAD_DETALLE.get((det.get("modalidad") or "").strip().lower()) or det.get("modalidad")
                          or MODALIDAD_QEDU.get(str(t.get("modalidad")))),
            "idioma_extranjero": det.get("idioma_extranjero"), "plazas": det.get("plazas"),
            "creditos": det.get("creditos"), "precio_credito": det.get("precio_credito"), "enlace": det.get("enlace"),
            "insercion": d.get("insercion"),
            "capturado": (d.get("fuente") or t.get("fuente") or {}).get("capturado"),
            "con_detalle": bool(det),
        })
    return out


def cargar_boe_planes(carpetas: list[Path]) -> dict[str, dict]:
    """código → plan publicado en el BOE (boe_planes_masters.py), el único del documento o el comprobado."""
    # cada documento, con la última medición (la unión al código puede haber cambiado: manda la más reciente)
    por_doc: dict[str, tuple] = {}
    for f in sorted((f for c in carpetas for f in c.rglob("boe_planes_masters.jsonl")), key=str):
        for d in _jsonl(f):
            clave = (d.get("medido") or "", str(f))
            if d.get("identificador") and (d["identificador"] not in por_doc or clave >= por_doc[d["identificador"]][0]):
                por_doc[d["identificador"]] = (clave, d)
    out: dict[str, dict] = {}
    for _, d in sorted(por_doc.values(), key=lambda x: x[1]["identificador"]):
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
             for f in plan["filas_plan"] if f.get("nombre") and nombre_de_asignatura(f["nombre"])]
    comp = plan.get("comprobacion")
    nota = ("plan publicado en el BOE" + (f" el {plan['fecha_publicacion'][:4]}" if plan.get("fecha_publicacion") else "")
            + ("; la suma de créditos cuadra con su tabla" if comp == "completo" else
               "; cuadran las básicas y obligatorias, no la optatividad" if comp else "; sin comprobar la suma"))
    filas = asignaturas_validas(filas)
    return {"asignaturas": campo(filas, "boe", plan.get("url"), plan.get("capturado"), nota=nota,
                                 comprobado=plan.get("comprobacion"))} if filas else {}


def cargar_tablas(carpetas: list[Path]) -> list[dict]:
    """Precios aceptados de las tarifas (tarifas.py): las tablas de precios de las universidades y los PDF de
    precios de sus dominios. Uno por URL, programa, concepto e importe (la extracción más reciente)."""
    out: dict[tuple, dict] = {}
    for c in carpetas:
        for f in sorted(c.rglob("precios.jsonl")):
            for x in _jsonl(f):
                if x.get("estado") != "aceptado" or not isinstance(x.get("importe"), (int, float)):
                    continue
                k = (x.get("url"), x.get("programa"), x.get("concepto"), x.get("importe"))
                if k not in out or str(x.get("extraido") or "") > str(out[k].get("extraido") or ""):
                    out[k] = x
    return list(out.values())


# Precio de la tabla de la universidad: el programa de la tabla tiene que ser ese máster (mismo nombre, sin ser un
# doble máster ni otro tipo de título) y de un curso que no esté pasado. Si dos filas igual de parecidas dan precios
# distintos para el mismo concepto, no se pone ninguno.
CONCEPTO_TABLA = {"total": "precio_total", "credito": "precio_credito", "reserva": "reserva_matricula"}
RE_DOBLE = re.compile(r"(?i)\b(doble|dobles|pceo|double)\b|\s\+\s")


def _curso_tabla(x: dict) -> int | None:
    años = [int(a) for a in re.findall(r"\b(20[0-3]\d)\b", f"{x.get('curso') or ''} {x.get('url') or ''}")]
    return max(años) if años else None


def campos_tabla(nombre_oficial: str | None, filas: list[dict]) -> dict[str, dict]:
    from motor.estudios.fichas_masters import comprobar_nombre

    if not nombre_oficial or not filas:
        return {}
    doble = bool(RE_DOBLE.search(nombre_oficial))
    mejores: dict[str, list[tuple]] = defaultdict(list)
    for x in filas:
        campo_ = CONCEPTO_TABLA.get(x.get("concepto"))
        año = _curso_tabla(x)
        if not campo_ or not año or año <= AÑO_ANTIGUO:
            continue
        nombres = [n for n in (x.get("programa"), x.get("programa_lista")) if n]
        if any(bool(RE_DOBLE.search(n)) != doble for n in nombres[:1]):
            continue
        resultados = [comprobar_nombre(nombre_oficial, n) for n in nombres]
        buenos = [r[1] for r in resultados if r[0] == "confirmado"]
        if buenos:
            mejores[campo_].append((max(buenos), año, x))
    out = {}
    for campo_, cands in mejores.items():
        cands.sort(key=lambda t: (-t[0], -t[1]))
        top = [t for t in cands if t[0] == cands[0][0] and t[1] == cands[0][1]]
        if len({round(t[2]["importe"], 2) for t in top}) > 1:
            DESCARTES["precio_tabla_ambiguo"] += 1
            continue
        _, año, x = top[0]
        v = x["importe"]
        if campo_ == "precio_total" and v < PRECIO_TOTAL_MINIMO or \
                campo_ == "precio_credito" and not PRECIO_CREDITO[0] <= v <= PRECIO_CREDITO[1]:
            DESCARTES["precio_tabla_imposible"] += 1
            continue
        out[campo_] = campo(v, "tarifa", x.get("url"), str(x.get("extraido") or "")[:10] or None,
                            curso=x.get("curso") or None, cita_sha256=x.get("cita_sha256"),
                            nota="tabla de precios de la universidad")
    return out


def tablas_por_universidad(filas: list[dict], por_clave: dict[str, dict], dominios: dict[str, set[str]]) -> dict[str, list[dict]]:
    """Código SIIU de universidad → sus precios de tabla: la universidad que dice la lista revisada o, en los PDF
    hallados por su dominio, la única dueña de ese dominio."""
    out: dict[str, list[dict]] = defaultdict(list)
    for x in filas:
        if x.get("universidad"):
            u = (por_clave.get(clave_universidad(x["universidad"])) or {}).get("universidad_codigo")
        else:
            dueñas = dominios.get(x.get("dominio") or "") or set()
            u = next(iter(dueñas)) if len(dueñas) == 1 else None
        if u:
            out[u].append(x)
    return out


def cargar_guias(carpetas: list[Path]) -> dict[str, list[dict]]:
    """código → guías docentes leídas (guias.py), una por URL (la última)."""
    por_url: dict[str, dict] = {}
    for c in carpetas:
        for f in sorted(c.rglob("guias.jsonl")):
            for g in _jsonl(f):
                # la lectura más reciente manda aunque ya no tenga evaluación (una comprobación posterior la quitó)
                if g["url"] not in por_url or g["extraido"] >= por_url[g["url"]]["extraido"]:
                    por_url[g["url"]] = g
    out: dict[str, list[dict]] = defaultdict(list)
    for g in por_url.values():
        if not g.get("evaluacion"):
            continue
        for cod in g.get("codigos_ruct") or []:
            out[cod].append(g)
    return out


def pesos_coherentes(sistemas: list[dict]) -> bool:
    """Los pesos de una guía caben en el 100 %: los mínimos no lo pasan y los máximos lo alcanzan (con fijos, suman
    100). Si no, a la lectura le falta o le sobra un sistema y no se publica."""
    mins = sum(x.get("min") or 0 for x in sistemas)
    maxs = sum(x.get("max") or 0 for x in sistemas)
    return bool(sistemas) and mins <= 101 and maxs >= 99


def campos_guias(gs: list[dict]) -> dict[str, dict]:
    buenas = []
    for g in gs or []:
        vistos, ev = set(), []
        for x in g.get("evaluacion") or []:  # el mismo sistema repetido en la lectura cuenta una vez
            k = ((x.get("sistema") or "").strip().lower(), x.get("min"), x.get("max"))
            if k not in vistos:
                vistos.add(k)
                ev.append(x)
        g = {**g, "evaluacion": ev}
        if not pesos_coherentes(ev):
            DESCARTES["guias_pesos_incoherentes"] += 1
            continue
        g = {**g, "evaluacion": seguro_valor(g["evaluacion"]), "metodologia": seguro_valor(g.get("metodologia"))}
        if g["evaluacion"]:
            buenas.append(g)
    gs = sorted(buenas, key=lambda g: g.get("asignatura") or "")
    if not gs:
        return {}
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


def dominio(url: str | None) -> str:
    """Dominio registrable: «www.um.es» y «estudios.um.es» → «um.es»; «x.uni.edu.es» → «uni.edu.es»."""
    from urllib.parse import urlparse

    h = urlparse(url or "").netloc.lower().split("@")[-1].split(":")[0]
    p = [x for x in h.split(".") if x]
    return ".".join(p[-3:]) if len(p) >= 3 and p[-2] in ("com", "edu", "org", "gob", "ac", "net", "co") else ".".join(p[-2:])


def clave_universidad(nombre: str | None) -> str:
    from motor.estudios.boe_planes_masters import _clave_uni

    return _clave_uni(nombre or "")


RE_POR_UNIVERSIDADES = re.compile(r"(?i)\s+por\s+(?:la|las|el|los)\s+(.+)$")


def universidades_del_nombre(nombre: str | None) -> list[str]:
    """«… por la Universidad de A Coruña y la Universidad de Vigo» → claves de las dos universidades."""
    m = RE_POR_UNIVERSIDADES.search(nombre or "")
    if not m:
        return []
    trozos = re.split(r"(?i)\s*[,;]\s*(?:y\s+|e\s+|i\s+)?(?:la\s+|las\s+|el\s+)?|\s+(?:y|e|i)\s+(?:la\s+|las\s+|el\s+)?"
                     r"(?=universi|[A-ZÁÉÍÓÚ])", m.group(1))
    return [k for k in (clave_universidad(t) for t in trozos) if k]


def nombra_otra_universidad(valor, propia: str, todas: set[str]) -> bool:
    """La web dice que expide el título otra universidad: su nombre es el de otra del catálogo, o nombra una
    universidad que no comparte palabras con la del máster («Universidad Europea» sí es «Europea de Madrid»)."""
    if not isinstance(valor, str) or not propia:
        return False
    k = clave_universidad(valor)
    if not k or k == propia:
        return False
    if k in todas:
        return True
    a, b = set(k.split()), set(propia.split())
    if a <= b or b <= a:
        return False
    return bool(re.search(r"(?i)univers|unibertsitatea", valor)) and not a & b


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
    hojas = asignaturas_validas(_hojas(plan))
    if hojas:
        out["asignaturas"] = campo(hojas, "ruct", url, fecha)
    if plan:
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
    creditos = sorted({i["creditos"] for i in con if i.get("creditos")})
    if len(creditos) == 1:
        out["creditos_ects"] = campo(creditos[0], "qedu", URL_QEDU, fecha)
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


PRECIOS = ("precio_total", "precio_credito", "reserva_matricula")
PRECIO_TOTAL_MINIMO = 300          # un máster no cuesta menos: es una tasa, la reserva o el precio de un crédito
PRECIO_CREDITO = (5, 1000)         # €/ECTS posibles (pública más barata ≈ 13; escuelas privadas, unos cientos)
DESCARTES = Counter()


def _año_curso(curso) -> int | None:
    años = [int(a) for a in re.findall(r"\b(20[0-3]\d)\b", str(curso or ""))]
    return max(años) if años else None


def campos_web(f: dict) -> dict[str, dict]:
    out = {}
    fuentes = f.get("fuentes") or []
    for nombre, c in (f.get("campos") or {}).items():
        fu = fuentes[c["fuente"]] if isinstance(c.get("fuente"), int) and c["fuente"] < len(fuentes) else {}
        tipo = "tarifa" if fu.get("pagina") == "documento" else "web"
        valor = c.get("valor")
        if nombre != "nombre" and isinstance(valor, (str, list, dict)):
            valor = seguro_valor(valor)
        if nombre == "asignaturas":
            valor = asignaturas_validas(valor)
            if valor is None:
                DESCARTES["asignaturas_web_insuficientes"] += 1
        if valor in (None, "", [], {}):
            continue
        año = _año_curso(fu.get("curso"))
        out[nombre] = campo(valor, tipo, fu.get("url"), fu.get("extraido"), cita_sha256=c.get("cita_sha256"),
                            cita_nivel=c.get("cita_nivel"), curso=fu.get("curso"),
                            antiguo=True if nombre in PRECIOS and año and año <= AÑO_ANTIGUO else None)
    pt, pc = (out.get("precio_total") or {}).get("valor"), (out.get("precio_credito") or {}).get("valor")
    if isinstance(pc, (int, float)) and not PRECIO_CREDITO[0] <= pc <= PRECIO_CREDITO[1]:
        DESCARTES["precio_credito_imposible"] += 1
        out.pop("precio_credito")
        pc = None
    if isinstance(pt, (int, float)) and (pt < PRECIO_TOTAL_MINIMO or (isinstance(pc, (int, float)) and abs(pt - pc) < 0.01)):
        DESCARTES["precio_total_imposible"] += 1
        out.pop("precio_total")
    if pagina_antigua(out):  # la página solo habla de cursos pasados: sus precios sin curso propio, también
        for k in PRECIOS:
            if k in out and "curso" not in out[k]:
                out[k]["antiguo"] = True
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


NOMBRE_FUENTE = {"qedu": "QEDU", "norma": "norma autonómica", "ruct": "RUCT", "catalogo": "SIIU", "web": "web del centro",
                 "tarifa": "tarifa del centro", "boe": "BOE"}


def precio_calculado(campos: dict) -> dict | None:
    pc, cr = campos.get("precio_credito"), campos.get("creditos_ects")
    if not pc or not cr or not isinstance(pc.get("valor"), (int, float)) or not isinstance(cr.get("valor"), (int, float)):
        return None
    oficial_ = pc["fuente"] in ("qedu", "norma")
    que = ("precio del crédito en primera matrícula" if pc["fuente"] == "qedu" else
           "precio del crédito en primera matrícula que fija la norma" if pc["fuente"] == "norma" else
           "precio del crédito que publica el centro")
    return campo(round(pc["valor"] * cr["valor"], 2), "calculado", pc.get("url"), pc.get("capturado"),
                 nota=f"{que} ({pc['valor']:g} €, {NOMBRE_FUENTE.get(pc['fuente'], pc['fuente'])}) × {cr['valor']:g} "
                      f"créditos ({NOMBRE_FUENTE.get(cr['fuente'], cr['fuente'])}); sin tasas de secretaría ni seguro",
                 base="oficial" if oficial_ and cr["fuente"] in ("ruct", "qedu", "catalogo") else "web",
                 antiguo=pc.get("antiguo"))


def poner_precio_calculado(campos: dict) -> None:
    """Sin total, el calculado; con un total de la web que no cabe con el precio oficial del crédito (fuera de la
    mitad al doble), manda el calculado y el de la web queda como alternativa."""
    calc = precio_calculado(campos)
    if not calc:
        return
    pt = campos.get("precio_total")
    if not pt:
        campos["precio_total"] = calc
    elif pt["fuente"] in ("web", "tarifa") and isinstance(pt.get("valor"), (int, float)) and calc["base"] == "oficial" \
            and not 0.5 <= pt["valor"] / calc["valor"] <= 2:
        DESCARTES["precio_total_web_incoherente"] += 1
        campos["precio_total"] = {**calc, "alternativas": [{"valor": pt["valor"], "fuente": pt["fuente"], "url": pt.get("url")}]
                                  + (pt.get("alternativas") or [])}


def datos_minimos(campos: dict) -> list[str]:
    falta = []
    if not campos.get("asignaturas"):
        falta.append("asignaturas")
    if not any(campos.get(k) and not campos[k].get("antiguo") for k in ("precio_total", "precio_credito")):
        falta.append("precio")
    return falta


# Precio del crédito en primera matrícula de los másteres de universidades públicas en las comunidades con un precio
# único (sin precio por título): habilitante y resto. Solo para estudiantes de la UE y residentes (los demás pagan
# más) y cuando QEDU no da el precio de esa impartición. Comprobado el 30/10/2026 en la copia de la norma que
# publica una universidad de la comunidad. El resto de comunidades fija precios por título o por grupos: sin la lista
# leída, no se calcula (docs/fuentes-precios-publicos.md).
PRECIO_NORMA = {
    "Cataluña": {"habilitante": 17.69, "resto": 19.37, "curso": "2026-2027",
                 "norma": "Decreto 96/2026, de 16 de junio (Generalitat de Catalunya)",
                 "url": "https://www.ub.edu/acad/matricula/decreto.pdf",
                 "excluir": r"(?i)oberta de catalunya|\bUOC\b|qu[ií]mica",  # la UOC tiene su precio; Ing. Química, excepción
                 "aviso": "estudiantes de la UE y residentes; fuera de la UE, más", "leido": "2026-10-30"},
    "Andalucía": {"habilitante": 12.62, "resto": 13.68, "curso": "2025-2026",
                  "norma": "Decreto 98/2023, de 2 de mayo (BOJA n.º 84, 5-5-2023), de la Junta de Andalucía",
                  "url": "https://masteres.ugr.es/print/pdf/node/183", "excluir": None,
                  "aviso": "la Junta bonifica el 99 % de los créditos aprobados en primera matrícula", "leido": "2026-10-30"},
}
# Másteres que habilitan para una profesión regulada (órdenes ministeriales de requisitos de verificación)
RE_HABILITANTE = re.compile(
    r"(?i)abogac[ií]a|procura\b|advocacia|profesorado de educaci[oó]n secundaria|formaci[oó]n del profesorado|"
    r"professorat|profesor de educaci[oó]n secundaria|psicolog[ií]a general sanitaria|psicologia general sanit|"
    r"ingenier[ií]a industrial|enginyeria industrial|ingenier[ií]a de telecomunicaci[oó]n|enginyeria de telecomunicaci|"
    r"caminos,? canales|camins,? canals|ingenier[ií]a aeron[aá]utica|enginyeria aeron[aà]utica|"
    r"ingenier[ií]a agron[oó]mica|enginyeria agron[oò]mica|ingenier[ií]a de montes|enginyeria de forest|"
    r"ingenier[ií]a de minas|enginyeria de mines|ingenier[ií]a naval|enginyeria naval|"
    r"en arquitectura(?:\s+por|\s*/|\s*$)|màster universitari en arquitectura(?:\s|$)")


# Títulos que habilitan para una profesión regulada, con la norma que fija sus requisitos (enlace comprobado el
# 30/10/2026). El nombre tiene que ser el de la profesión, no uno que la contenga («Ingeniería Industrial y
# Automática» no es el máster habilitante). Agronómica y Montes quedan sin marcar hasta comprobar el enlace de su
# orden.
HABILITACIONES = [
    (r"(el |la )?((acceso|pr[aá]ctica|ejercicio)( a| al| de)?( el| la| las)? (ejercicio de (la )?|profesiones de |profesi[oó]n de (la )?)?)?"
     r"(la )?(abogac[ií]a|advocacia)( i| y)?( de| a)?( la)?( procura)?",
     "Abogado y Procurador de los Tribunales (con el examen estatal de acceso)", "Ley 34/2006, de 30 de octubre",
     "https://www.boe.es/eli/es/l/2006/10/30/34/con"),
    (r"(formaci[oó]n del? )?profesorado (de|en) (la )?(educaci[oó]n |ense[nñ]anza )?secundaria.*|formaci[oó]n del profesorado|"
     r"profesor de educaci[oó]n secundaria.*|(formaci[oó] del )?professorat d.(educaci[oó] )?secund.*",
     "Profesor de Educación Secundaria, Bachillerato, Formación Profesional e Idiomas", "Orden ECI/3858/2007, de 27 de diciembre",
     "https://www.boe.es/eli/es/o/2007/12/27/eci3858"),
    (r"psicolog[ií]a general sanitaria|psicologia general sanitaria", "Psicólogo General Sanitario",
     "Orden ECD/1070/2013, de 12 de junio", "https://boe.gob.es/boe/dias/2013/06/14/pdfs/BOE-A-2013-6412.pdf"),
    (r"ingenier[ií]a industrial|enginyeria industrial", "Ingeniero Industrial", "Orden CIN/311/2009, de 9 de febrero",
     "https://www.boe.es/eli/es/o/2009/02/09/cin311"),
    (r"ingenier[ií]a de telecomunicaci[oó]n|enginyeria de telecomunicaci[oó]", "Ingeniero de Telecomunicación",
     "Orden CIN/355/2009, de 9 de febrero",
     "https://www.upc.edu/sga/es/shared/fitxers-normatives/LegislacioEstatal/habilitacions-professionals/ordre-cin-355-2009_enginyer-de-telecomunicacio"),
    (r"arquitectura", "Arquitecto", "Orden EDU/2075/2010, de 29 de julio", "https://www.uma.es/media/files/Orden_EDU_2075_2010.pdf"),
    (r"ingenier[ií]a de caminos,? canales y puertos|enginyeria de camins,? canals i ports", "Ingeniero de Caminos, Canales y Puertos",
     "Orden CIN/309/2009, de 9 de febrero", "https://boe.es/boe/dias/2009/02/18/pdfs/BOE-A-2009-2738.pdf"),
    (r"ingenier[ií]a de minas|enginyeria de mines", "Ingeniero de Minas", "Orden CIN/310/2009, de 9 de febrero",
     "https://boe.es/boe/dias/2009/02/18/pdfs/BOE-A-2009-2739.pdf"),
    (r"ingenier[ií]a aeron[aá]utica|enginyeria aeron[aà]utica", "Ingeniero Aeronáutico", "Orden CIN/312/2009, de 9 de febrero",
     "https://boe.es/boe/dias/2009/02/18/pdfs/BOE-A-2009-2741.pdf"),
    (r"ingenier[ií]a naval( y oce[aá]nica)?|enginyeria naval( i oce[aà]nica)?", "Ingeniero Naval y Oceánico",
     "Orden CIN/354/2009, de 9 de febrero",
     "https://www.upc.edu/sga/ca/shared/fitxers-normatives/LegislacioEstatal/habilitacions-professionals/ordre-cin-354-2009_enginyer-naval-i-oceanic/view"),
]


def _nucleo_nombre(nombre: str | None) -> str:
    n = re.split(r"(?i)\s+(?:por|per)\s+(?:la|las|el|los|l')\s*", nombre or "")[0].split("/")[0]
    n = re.sub(r"(?i)^\s*(m[aáà]ster|master)\s+(universitari[oa]?\s+)?(oficial\s+)?(en|de|in|d')\s*", "", n)
    n = re.sub(r"\([^)]*\)", " ", n)
    return " ".join(re.sub(r"[^\w\s']", " ", n.lower()).split())


def habilitacion(nombre: str | None) -> tuple[str, str, str] | None:
    """(profesión, norma, url) si el título es el máster habilitante de una profesión regulada."""
    if re.match(r"(?i)\s*PCEO\b", nombre or ""):
        return None
    n = _nucleo_nombre(nombre)
    for patron, profesion, norma, url in HABILITACIONES:
        if re.fullmatch(patron, n):
            return profesion, norma, url
    return None


def campos_habilitacion(nombre: str | None) -> dict[str, dict]:
    h = habilitacion(nombre)
    if not h:
        return {}
    return {"habilita_profesion": campo(f"Sí: {h[0]}", "boe", h[2], "2026-10-30",
                                        nota=f"por el nombre del título, que es el de la profesión regulada ({h[1]})")}


def campos_norma(cat: dict, nombre_uni: str | None, imps: list[dict], habilita: str | None) -> dict[str, dict]:
    """Precio del crédito por la norma de la comunidad, para una pública sin precio en QEDU."""
    n = PRECIO_NORMA.get(cat.get("universidad_comunidad") or "")
    if not n or cat.get("universidad_tipo") != "Pública" or any(i.get("precio_credito") for i in imps):
        return {}
    nombre = cat.get("nombre_oficial") or ""
    if n["excluir"] and re.search(n["excluir"], f"{nombre} {nombre_uni or ''}"):
        return {}
    if re.match(r"(?i)\s*PCEO\b", nombre) or len(re.findall(r"(?i)m[aáà]ster universitari", nombre)) > 1:
        return {}  # doble máster: cada parte puede tener su precio
    hab = habilita.lower().startswith("s") if habilita else bool(RE_HABILITANTE.search(nombre))
    tipo = "habilitante" if hab else "resto"
    return {"precio_credito": campo(n[tipo], "norma", n["url"], n["leido"],
                                   nota=f"primera matrícula, curso {n['curso']}, máster {'habilitante' if hab else 'no habilitante'}; "
                                        f"{n['norma']}; {n['aviso']}", curso=n["curso"])}


def _sin_fecha(q: dict | None) -> dict | None:
    """La impartición de QEDU sin su fecha de lectura: la fecha va en cada campo y solo cambia si cambia el dato."""
    return {k: v for k, v in q.items() if k not in ("capturado", "con_detalle")} if q else None


def oficial(cod: str, cat: dict, ruct: dict | None, imps: list[dict], web: dict | None,
            fecha_catalogo: str | None = None, universidades: dict[str, str] | None = None,
            plan_boe: dict | None = None, guias: list[dict] | None = None, ajenos: set[str] | None = None,
            tablas: list[dict] | None = None) -> dict:
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
    # un alta del BOE posterior al catálogo: su identidad la da la resolución del BOE, no el SIIU
    f_id = "boe" if cat.get("origen") == "boe_alta" else "catalogo"
    por_fuente.setdefault(f_id, {}).update({
        "tipo_titulo": campo("máster universitario oficial", f_id, url_cat, fecha_cat),
        "universidad_que_expide": campo(nombre_uni, f_id, url_cat, fecha_cat),
        **({"modalidad": campo(", ".join(p.replace("Estudio ", "").lower() for p in pres), "catalogo", url_cat, fecha_cat)}
           if pres else {}),
    })
    w = campos_web(web) if web else {}
    if ajenos:  # datos de una página en el dominio oficial de otra universidad: fuera
        w = {k: v for k, v in w.items() if dominio(v.get("url")) not in ajenos}
    por_fuente["web"] = {k: v for k, v in w.items() if v["fuente"] == "web"}
    por_fuente["tarifa"] = {**campos_tabla(cat.get("nombre_oficial"), tablas or []),
                            **{k: v for k, v in w.items() if v["fuente"] == "tarifa"}}
    por_fuente["calculado"] = calc
    por_fuente["guia"] = campos_guias(guias or [])
    hab = ((por_fuente.get("ruct") or {}).get("habilita_profesion") or {}).get("valor")
    por_fuente["norma"] = campos_norma(cat, nombre_uni, imps, hab)
    por_fuente.setdefault("boe", {}).update(campos_habilitacion(cat.get("nombre_oficial")))
    # la evaluación de la memoria sin ponderaciones (formato RD 822/2021) cede ante la de las guías, que las tienen
    ev = por_fuente.get("ruct", {}).get("evaluacion")
    if ev and not ev["valor"].get("con_ponderacion") and "evaluacion" in por_fuente["guia"]:
        por_fuente["ruct"] = {k: v for k, v in por_fuente["ruct"].items() if k != "evaluacion"}
        por_fuente["ruct_catalogo"] = {"evaluacion": ev}
    campos = unir(por_fuente)
    poner_precio_calculado(campos)
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
                           "qedu": _sin_fecha(next((q for q in imps if q["centro_codigo"] == i.get("unidad_codigo")), None))}
                          for i in cat.get("imparticiones") or []]
                         + [{"centro": q["centro"], "centro_codigo": q["centro_codigo"], "qedu": _sin_fecha(q)} for q in imps
                            if q["centro_codigo"] not in {i.get("unidad_codigo") for i in cat.get("imparticiones") or []}],
        "en_oferta_del_curso": bool(imps),
        "campos": campos,
        "paginas_web": [u for u in (web or {}).get("paginas") or [] if dominio(u) not in (ajenos or set())],
        "pagina_web_antigua": pagina_antigua(w) if w else None,
        "datos_minimos_faltan": falta, "indexable": not falta,
        "fuentes_usadas": sorted({c["fuente"] for c in campos.values()}),
    }


def no_oficial(grupo: list[dict], ident: str | None = None) -> dict:
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
        "id": ident or f.get("programa") or f.get("clave"), "tipo": "no_oficial", "nombre": (campos.get("nombre") or {}).get("valor"),
        "centro": f.get("centro"), "tipo_centro": f.get("tipo_centro"), "proveedor": f.get("proveedor"),
        "dominio": f.get("dominio"), "es_master": f.get("es_master"), "url": f.get("url"),
        "otras_paginas": [g.get("url") for g in grupo[1:]],
        "campos": campos, "pagina_web_antigua": pagina_antigua(campos),
        "datos_minimos_faltan": falta, "indexable": not falta,
        "fuentes_usadas": sorted({c["fuente"] for c in campos.values()}),
    }


# Páginas que no son la de un programa (noticias, blog, eventos) y versiones para otro país
RE_URL_NO_PROGRAMA = re.compile(r"(?i)/(blog|blogs|noticias?|news|eventos?|events?|agenda|actualidad|prensa|"
                                r"sala-de-prensa|webinars?|jornadas?|magazine|revista|podcast)(/|$)")
RE_EXTRANJERO = re.compile(
    r"(?i)\b(m[eé]xico|colombia|per[uú]|chile|argentina|ecuador|bolivia|paraguay|uruguay|venezuela|panam[aá]|"
    r"costa rica|guatemala|honduras|el salvador|nicaragua|rep[uú]blica dominicana|puerto rico|miami|bogot[aá]|"
    r"medell[ií]n|lima|quito|guayaquil|buenos aires|caracas|montevideo|cdmx|monterrey|estados unidos)\b")
RE_ESPAÑA = re.compile(
    r"(?i)\b(españa|spain|madrid|barcelona|val[eè]ncia|sevilla|m[aá]laga|bilbao|zaragoza|murcia|alicante|granada|"
    r"salamanca|valladolid|oviedo|gij[oó]n|santander|pamplona|iruña|donostia|san sebasti[aá]n|vitoria|logro[nñ]o|burgos|"
    r"le[oó]n|c[aá]diz|c[oó]rdoba|ja[eé]n|almer[ií]a|huelva|badajoz|c[aá]ceres|m[eé]rida|toledo|ciudad real|cuenca|"
    r"guadalajara|albacete|castell[oó]n|tarragona|lleida|girona|palma|mallorca|ibiza|eivissa|menorca|las palmas|"
    r"tenerife|canarias|coru[nñ]a|santiago de compostela|vigo|lugo|ourense|pontevedra|segovia|[aá]vila|soria|zamora|"
    r"palencia|huesca|teruel|cartagena|elche|getafe|legan[eé]s|alcal[aá]|m[oó]stoles|fuenlabrada|terrassa|sabadell|"
    r"reus|ceuta|melilla|villaviciosa|pozuelo|majadahonda|boadilla|alcobendas|san cugat|sant cugat)\b")
# Versiones de la página para otro país o en una lengua que no es de España («/es-lat/», «/en-intl/», «/it/»): el
# programa ya está en su versión española o no se imparte aquí
RE_VERSION_OTRO_IDIOMA = re.compile(r"(?i)^https?://[^/]+/(es-lat|en-intl|en-uae|fr|it|de|pt|zh|ru|lt|nl|pl|ar)(/|$)")
RE_NOMBRE_OFICIAL = re.compile(r"(?i)\bm[aáà]ster universitari[oa]?\b|\buniversity master\b|\bofficial master")
RE_NOMBRE_PROPIO = re.compile(r"(?i)propio|permanente|own degree|t[ií]tulo de la escuela")


def fuera_de_no_oficiales(f: dict) -> str | None:
    """Motivo para no publicar una página como programa no oficial: es un máster oficial (está en el catálogo, con
    su ficha), es de otro país o no es la página de un programa."""
    from motor.estudios.extraer import LOCALE_OTRO_PAIS
    from motor.estudios.fichas_masters import es_tipo_oficial

    url = f.get("url") or ""
    c = f.get("campos") or {}
    nombre = str((c.get("nombre") or {}).get("valor") or "")
    tipo = str((c.get("tipo_titulo") or {}).get("valor") or "")
    if es_tipo_oficial(tipo) or (RE_NOMBRE_OFICIAL.search(nombre) and not RE_NOMBRE_PROPIO.search(nombre + " " + tipo)):
        return "parece_master_oficial"
    if LOCALE_OTRO_PAIS.search(url) or RE_VERSION_OTRO_IDIOMA.search(url) or re.search(r"(?i)\bmaestr[ií]a", nombre):
        return "otro_pais"
    sedes = (c.get("sedes") or {}).get("valor")
    sedes = " · ".join(sedes) if isinstance(sedes, list) else str(sedes or "")
    if RE_EXTRANJERO.search(sedes) and not RE_ESPAÑA.search(sedes):
        return "otro_pais"
    if RE_URL_NO_PROGRAMA.search(url):
        return "no_es_pagina_de_programa"
    return None


def _clave_nombre(s: str | None) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", _sin_tildes((s or "").lower())))


def programas_no_oficiales(web_no: list[dict], prev: dict[str, dict], dominios: dict[str, set[str]] | None = None) -> list[dict]:
    """Los programas no oficiales: sin másteres oficiales repetidos, ni páginas de otro país o que no son de un
    programa; uno por dominio y nombre (las versiones de idioma o las páginas repetidas se unen); el identificador
    de la pasada anterior si alguna de sus páginas ya lo tenía, para que la página publicada no cambie de dirección."""
    por_programa: dict[str, list[dict]] = defaultdict(list)
    for f in web_no:
        motivo = fuera_de_no_oficiales(f)
        if motivo:
            DESCARTES[f"no_oficial_{motivo}"] += 1
            continue
        por_programa[f.get("programa") or f.get("clave")].append(f)
    # un programa por dominio y nombre
    por_dominio: dict[tuple, list[str]] = defaultdict(list)
    nombre_de = {}
    for k, g in por_programa.items():
        mejor = max(g, key=lambda f: len(f.get("campos") or {}))
        nombre_de[k] = _clave_nombre(((mejor.get("campos") or {}).get("nombre") or {}).get("valor"))
        por_dominio[(dominio(mejor.get("url")) or mejor.get("dominio"), nombre_de[k] or k)].append(k)
    out = []
    for _, ks in sorted(por_dominio.items()):
        if len(ks) > 1:
            DESCARTES["no_oficial_unidos_por_dominio_y_nombre"] += len(ks) - 1
        grupo = [f for k in sorted(ks) for f in por_programa[k]]
        candidatos = sorted(ks) + [f.get("clave") for f in grupo if f.get("clave")]
        ident = next((x for x in candidatos if x in prev), sorted(ks)[0])
        out.append(no_oficial(grupo, ident))
    return sorted(out, key=lambda r: r["id"])


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
            if p and p.get("huella") == h and p.get("capturado") and p.get("fuente") == c.get("fuente"):
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


# Un dominio es de las universidades cuyos másteres de una sola universidad enlaza QEDU en él (los
# interuniversitarios se enlazan en la web de la coordinadora: ucm.es tiene másteres de la Autónoma con la
# Complutense). Con dos enlaces o una décima parte basta (universidadeuropea.com es de las cuatro Europeas).
MIN_ENLACES_DUEÑA = 2
MIN_PARTE_DUEÑA = 0.10


def dominios_de_universidades(cat: dict[str, dict], r_qedu: dict[str, list[dict]]) -> dict[str, set[str]]:
    """Dominio → universidades (código SIIU) cuya web oficial es, por los enlaces de QEDU de sus másteres propios."""
    por: dict[str, Counter] = defaultdict(Counter)
    for c, imps in r_qedu.items():
        t = cat.get(c) or {}
        cu = t.get("universidad_codigo")
        if not cu or len(universidades_del_nombre(t.get("nombre_oficial"))) > 1:
            continue
        for i in imps:
            if i.get("enlace"):
                por[dominio(i["enlace"])][cu] += 1
    out = {}
    for d, cs in por.items():
        total = sum(cs.values())
        dueñas = {u for u, n in cs.items() if n >= MIN_ENLACES_DUEÑA or n / total >= MIN_PARTE_DUEÑA}
        if d and dueñas:
            out[d] = dueñas
    return out


def filtrar_web(web: dict | None, propias: set[str], dominios: dict[str, set[str]], clave_propia: str,
                claves: set[str]) -> tuple[dict | None, set[str], str | None]:
    """La ficha web de un máster oficial solo si es de su universidad (o de una que lo imparte con ella): fuera la
    que dice que lo expide otra universidad, la «probable» que no está en un dominio de la suya y los datos de
    páginas en el dominio oficial de otra. Devuelve la ficha (o None), los dominios ajenos y el motivo."""
    if not web:
        return None, set(), None
    urls = list(web.get("paginas") or []) + [fu.get("url") for fu in web.get("fuentes") or [] if fu.get("url")]
    doms = {dominio(u) for u in urls if u}
    ajenos = {d for d in doms if dominios.get(d) and not dominios[d] & propias}
    suyos = {d for d in doms if dominios.get(d) and dominios[d] & propias}
    expide = ((web.get("campos") or {}).get("universidad_que_expide") or {}).get("valor")
    if nombra_otra_universidad(expide, clave_propia, claves):
        return None, ajenos, "web_expide_otra_universidad"
    if doms and doms <= ajenos:
        return None, ajenos, "web_en_dominio_de_otra_universidad"
    if web.get("comprobacion_nombre") == "probable_oficial" and not suyos:
        return None, ajenos, "web_probable_fuera_de_su_universidad"
    return web, ajenos, None


def ejecutar(catalogo: Path, salida: Path, altas: Path | None = None, ruct: list[Path] = (), qedu: list[Path] = (),
             fichas: Path | None = None, anterior: Path | None = None, fecha_catalogo: str | None = None,
             boe: list[Path] = (), guias: list[Path] = (), fecha_altas: str | None = None,
             tablas: list[Path] = ()) -> dict:
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
    # universidad del catálogo por su clave («Universidad Autónoma de Barcelona» = «Autónoma de Barcelona»)
    por_clave: dict[str, dict] = {}
    for t in filas:
        for n in (t.get("universidad"), universidades.get(t.get("universidad_codigo") or "")):
            if n:
                por_clave.setdefault(clave_universidad(n), t)
    claves = set(por_clave)
    if altas:
        for a in _jsonl(altas):
            if a["codigo_ruct"] not in todos:
                u = por_clave.get(clave_universidad(a.get("universidad")), {})
                cat.setdefault(a["codigo_ruct"], {
                    "codigo_ruct": a["codigo_ruct"], "nombre_oficial": a.get("nombre"),
                    "universidad": u.get("universidad") or a.get("universidad"),
                    "universidad_codigo": u.get("universidad_codigo"), "universidad_tipo": u.get("universidad_tipo"),
                    "universidad_comunidad": u.get("universidad_comunidad"),
                    "situacion": "Activo", "origen": "boe_alta", "imparticiones": [],
                    # fecha de captura: la de la lectura del BOE (no la de publicación)
                    "fuente": {"url": f"https://www.boe.es/buscar/doc.php?id={a.get('boe')}",
                               "capturado": a.get("capturado") or fecha_altas or fecha_catalogo}})
    web_of, web_no = cargar_web(fichas) if fichas else ({}, [])
    hoy = _hoy()
    prev = _anterior(anterior)
    DESCARTES.clear()
    dominios = dominios_de_universidades(cat, r_qedu)
    r_tablas = tablas_por_universidad(cargar_tablas(list(tablas)), por_clave, dominios)
    oficiales = []
    for c in sorted(cat):
        t = cat[c]
        propias = {t.get("universidad_codigo")} - {None}
        for k in universidades_del_nombre(t.get("nombre_oficial")):
            u = por_clave.get(k) or next((v for kk, v in por_clave.items() if set(k.split()) <= set(kk.split())), None)
            if u and u.get("universidad_codigo"):
                propias.add(u["universidad_codigo"])
        web, ajenos, motivo = filtrar_web(web_of.get(c), propias, dominios, clave_universidad(t.get("universidad")), claves)
        if motivo:
            DESCARTES[motivo] += 1
        oficiales.append(oficial(c, t, r_ruct.get(c), r_qedu.get(c, []), web, fecha_catalogo, universidades,
                                 r_boe.get(c), r_guias.get(c), ajenos, r_tablas.get(t.get("universidad_codigo") or "")))
    programas = programas_no_oficiales(web_no, prev, dominios)
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
        "oficiales_con_precio_de_tabla": sum(1 for r in oficiales if any(
            (r["campos"].get(k) or {}).get("nota") == "tabla de precios de la universidad" for k in CONCEPTO_TABLA.values())),
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
        "descartes": dict(DESCARTES),
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
    p.add_argument("--tablas", action="append", default=[], help="carpetas con precios.jsonl de tarifas.py (tablas)")
    p.add_argument("--anterior")
    p.add_argument("--fecha-catalogo", help="fecha de descarga del catálogo SIIU (por defecto, la del fichero)")
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    res = ejecutar(Path(a.catalogo), Path(a.salida), Path(a.altas) if a.altas else None, [Path(x) for x in a.ruct],
                   [Path(x) for x in a.qedu], Path(a.fichas) if a.fichas else None, Path(a.anterior) if a.anterior else None,
                   a.fecha_catalogo, [Path(x) for x in a.boe], [Path(x) for x in a.guias],
                   tablas=[Path(x) for x in a.tablas])
    print(json.dumps({k: v for k, v in res.items() if not k.startswith("cobertura")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
