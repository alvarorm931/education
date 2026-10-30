"""Notas de corte de grado de cada distrito, fase 2: leer cada formato y unir cada fila con su título y centro.

Entrada: lo que guarda `notas_fuentes.py` con `--filas 100000` (el documento entero en líneas, con la posición de
cada cifra; los CSV y JSON, una línea por registro), más el catálogo SIIU y QEDU. Salida, una fila por distrito,
curso, oferta, cupo y convocatoria, con la nota tal como la publica el distrito (y la fuente: URL, huella sha256 y
fecha de captura) y su unión con el título y el centro del Ministerio cuando se puede comprobar:

- **Universidad de Murcia** (CSV de datos abiertos): trae el código del título y del centro del Ministerio.
- **Madrid** (distrito único, un PDF por curso): grupos 1 a 6, convocatoria ordinaria y extraordinaria; el grupo 1
  (bachillerato y FP) es el cupo general. Código de cuatro cifras del distrito, nombre y, entre paréntesis, campus,
  centro o idioma.
- **Cataluña** (Socrata): cupo general de la preinscripción de junio con sus plazas (nota de la primera asignación,
  no la final).
- **Andalucía** (Distrito Único Andaluz, consulta histórica en CSV, un fichero por curso desde 2010-11): todas las
  universidades públicas, código de la petición, grado, centro y cinco cupos; definitivas de la convocatoria
  ordinaria. El nombre del centro decide entre centros.
- **Universidad de Salamanca** (un PDF por curso): cupo general, con el tipo del último admitido.
- **Universidad del País Vasco** (un PDF por curso, 2017-18 a 2021-22; desde 2022-23 los PDF son imágenes sin
  texto): cinco cupos por campus con la marca «E» de la convocatoria extraordinaria; el campus da los municipios.

Unión por nombre (pocos distritos traen el código): universidad, nombre normalizado del título y pistas de centro
(municipio o nombre del centro entre paréntesis); si queda más de un candidato, decide la nota de QEDU del mismo
curso (QEDU da la final de 2025-2026 y 2024-2025, redondeada a dos decimales) o las plazas. El nombre tiene que
parecerse al menos 0,8 al del catálogo (salvo que QEDU confirme la nota): los títulos ya extinguidos de los cursos
antiguos no se unen con el activo más parecido. Sin unión segura, la fila se guarda sin título y no se publica en
ninguna ficha.

Uso:
  python -m motor.grados.notas_corte --fuentes carpeta_notas_fuentes [...] --catalogo catalogo.jsonl
                                     --qedu carpeta_qedu --salida ruta/
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from motor.grados.generico import nombre_base

CITA_MADRID = "Universidades públicas de Madrid, distrito único: notas de corte (publicadas por la Universidad Carlos III)"
UNIV_MADRID = {"COMPLUTENSE": "Complutense de Madrid", "AUTÓNOMA": "Autónoma de Madrid", "AUTONOMA": "Autónoma de Madrid",
               "ALCALÁ": "Alcalá", "ALCALA": "Alcalá", "CARLOS III": "Carlos III de Madrid",
               "POLITÉCNICA": "Politécnica de Madrid", "POLITECNICA": "Politécnica de Madrid",
               "REY JUAN CARLOS": "Rey Juan Carlos"}
COMPLETA = [(g, c) for g in range(1, 6) for c in ("ordinaria", "extraordinaria")] + [(6, "extraordinaria")]
GRUPOS_MADRID = {1: "general", 2: "titulados", 3: "mayores_25", 4: "mayores_45", 5: "mayores_40", 6: "bachillerato_homologado"}
TOKEN = re.compile(r"\(\d+\)|-{3,}|\d{1,2}[.,]\d{2,3}\*?")
CABECERA = re.compile(r"Ordinaria|Extraord(?:inaria)?\.?|Extr\.|Ord\.|Ext\.")
VACIAS = {"de", "del", "la", "las", "los", "y", "e", "en", "el", "grado", "doble", "a", "por", "con", "i", "d", "l"}


def sin_acentos(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


ABREVIATURAS = {"ade": "administracion direccion empresas", "cc": "ciencias", "ing": "ingenieria", "rel": "relaciones",
               "intern": "internacionales", "com": "comunicacion", "inform": "informatica", "admon": "administracion",
               "cafyd": "ciencias actividad fisica deporte", "cafd": "ciencias actividad fisica deporte",
               "rrll": "relaciones laborales", "rrhh": "recursos humanos", "ener": "energeticos", "tecnol": "tecnologia",
               "ia": "inteligencia artificial", "gest": "gestion", "sist": "sistemas", "informac": "informacion"}
# Palabras de los nombres de grado en catalán → castellano, para unir la oferta catalana con el catálogo (en
# castellano). Solo cambia palabras sueltas; lo demás decide el parecido.
CATALAN = {
    "producte": "producto", "serveis": "servicios", "occitans": "occitanos", "analisi": "analisis",
    "documentacio": "documentacion", "energies": "energias", "contemporanies": "contemporaneas", "negoci": "negocio",
    "ambit": "ambito", "creatives": "creativas", "transformacio": "transformacion", "hoteleres": "hoteleras",
    "natura": "naturaleza",
    "informacio": "informacion", "gestio": "gestion", "comunicacio": "comunicacion", "produccio": "produccion",
    "prevencio": "prevencion", "organitzacio": "organizacion", "educacio": "educacion",
    "activitat": "actividad", "actuarials": "actuariales", "administracio": "administracion",
    "aeroespacial": "aeroespacial", "aeronautica": "aeronautica", "agraria": "agraria", "agricola": "agricola",
    "agroalimentaria": "agroalimentaria", "agronomica": "agronomica", "al": "al", "alimentacio": "alimentacion",
    "alimentaria": "alimentaria", "als": "a los", "amb": "con", "ambiental": "ambiental",
    "ambientals": "ambientales", "anglesa": "inglesa", "anglesos": "ingleses", "animacio": "animacion",
    "animal": "animal", "antiga": "antigua", "antropologia": "antropologia", "aplicacions": "aplicaciones",
    "aplicada": "aplicada", "aplicades": "aplicadas", "aprenentatge": "aprendizaje", "arqueologia": "arqueologia",
    "arquitectura": "arquitectura", "art": "arte", "artificial": "artificial", "arts": "artes",
    "audiovisual": "audiovisual", "audiovisuals": "audiovisuales", "automatica": "automatica", "belles": "bellas",
    "bens": "bienes", "biologia": "biologia", "biologiques": "biologicas", "biomedica": "biomedica",
    "biomedicina": "biomedicina", "biomediques": "biomedicas", "bioquimica": "bioquimica",
    "biosistemes": "biosistemas", "biotecnologia": "biotecnologia", "catalana": "catalana", "catalans": "catalanes",
    "ciencia": "ciencia", "ciencies": "ciencias", "cinema": "cine", "ciutat": "ciudad", "civil": "civil",
    "classica": "clasica", "classiques": "clasicas", "comptabilitat": "contabilidad",
    "computacional": "computacional", "comunicacio": "comunicacion", "comunicacions": "comunicaciones",
    "conservacio": "conservacion", "contemporania": "contemporanea", "criminologia": "criminologia",
    "culinaries": "culinarias", "culturals": "culturales", "d": "d", "dades": "datos", "de": "de", "del": "del",
    "desenvolupament": "desarrollo", "dietetica": "dietetica", "direccio": "direccion", "disseny": "diseno",
    "doble": "doble", "dret": "derecho", "economia": "economia", "edificacio": "edificacion",
    "educacio": "educacion", "electrica": "electrica", "electronica": "electronica", "els": "los",
    "emprenedoria": "emprendimiento", "empresa": "empresa", "empreses": "empresas", "en": "en", "energia": "energia",
    "enginyer": "ingeniero", "enginyeria": "ingenieria", "enologia": "enologia", "espanyola": "espanola",
    "esport": "deporte", "esports": "deportes", "estadistica": "estadistica", "estudis": "estudios",
    "farmacia": "farmacia", "filologia": "filologia", "filosofia": "filosofia", "finances": "finanzas",
    "fisica": "fisica", "fisioterapia": "fisioterapia", "forestal": "forestal", "fotonica": "fotonica",
    "francesa": "francesa", "gastronomiques": "gastronomicas", "genetica": "genetica", "geografia": "geografia",
    "geologia": "geologia", "geomatica": "geomatica", "gestio": "gestion", "global": "global", "globals": "globales",
    "grau": "grado", "hispanica": "hispanica", "historia": "historia", "hotelera": "hotelera",
    "hoteleria": "hoteleria", "humana": "humana", "humanitats": "humanidades", "humans": "humanos", "i": "y",
    "idiomes": "idiomas", "industrial": "industrial", "industrials": "industriales", "infantil": "infantil",
    "infermeria": "enfermeria", "informatica": "informatica", "innovacio": "innovacion", "integral": "integral",
    "intel": "inteligencia", "internacionals": "internacionales", "interpretacio": "interpretacion", "l": "l",
    "la": "la", "laborals": "laborales", "les": "las", "linguistica": "linguistica", "literatura": "literatura",
    "literatures": "literaturas", "llengua": "lengua", "llenguatges": "lenguajes", "llengues": "lenguas",
    "logopedia": "logopedia", "mar": "mar", "maritim": "maritimo", "marqueting": "marketing",
    "matematica": "matematica", "matematiques": "matematicas", "materials": "materiales", "mecanica": "mecanica",
    "mecatronica": "mecatronica", "medicina": "medicina", "medieval": "medieval", "mediterranies": "mediterraneas",
    "mestre": "maestro", "microbiologia": "microbiologia", "minera": "minera", "minerals": "minerales",
    "mineria": "mineria", "mines": "minas", "moderna": "moderna", "modernes": "modernas", "multimedia": "multimedia",
    "musica": "musica", "musicologia": "musicologia", "nautica": "nautica", "naval": "naval", "navals": "navales",
    "negocis": "negocios", "nutricio": "nutricion", "obert": "abierto", "ocupacional": "ocupacional",
    "odontologia": "odontologia", "optica": "optica", "optometria": "optometria", "organitzacio": "organizacion",
    "paisatge": "paisaje", "paisatgisme": "paisajismo", "pedagogia": "pedagogia", "per": "por",
    "periodisme": "periodismo", "podologia": "podologia", "politica": "politica", "politiques": "politicas",
    "prevencio": "prevencion", "primaria": "primaria", "produccio": "produccion", "programa": "programa",
    "psicologia": "psicologia", "publica": "publica", "publicitat": "publicidad", "publiques": "publicas",
    "quimica": "quimica", "recursos": "recursos", "relacions": "relaciones", "restauracio": "restauracion",
    "robotica": "robotica", "salut": "salud", "seguretat": "seguridad", "sistemes": "sistemas", "social": "social",
    "socials": "sociales", "sociologia": "sociologia", "sostenibilitat": "sostenibilidad",
    "sostenible": "sostenible", "superior": "superior", "teatrals": "teatrales", "tecnica": "tecnica",
    "tecniques": "tecnicas", "tecnologia": "tecnologia", "tecnologies": "tecnologias", "teleco": "telecomunicacion",
    "telecomunicacio": "telecomunicacion", "telematica": "telematica", "terapia": "terapia",
    "titulacio": "titulacion", "topografia": "topografia", "traduccio": "traduccion", "treball": "trabajo",
    "turisme": "turismo", "urbanisme": "urbanismo", "vehicles": "vehiculos", "veterinaria": "veterinaria",
    "videojocs": "videojuegos",
}

# Lo que acompaña al grado en la misma oferta y no cambia el título: un máster encadenado o la reserva de plaza
ANEXO_OFERTA = re.compile(r"(?i)\s*(?:\+|,\s*grau en \+)\s*(?:m[aá]ster|master|reserva de plaza).*$")


def palabras(nombre: str, catalan: bool = False) -> frozenset[str]:
    s = re.sub(r'\([^)]*\)|"[^"]*"|«[^»]*»', " ", sin_acentos(ANEXO_OFERTA.sub("", nombre)))
    if catalan:
        s = " ".join(CATALAN.get(w, w) for w in re.split(r"[\s'’,;:]+", s))
    s = re.sub(r"\b([a-z]+)\.", r"\1 ", s)
    s = " ".join(ABREVIATURAS.get(w, w) for w in re.split(r"[\s,;:]+", s))
    s = re.sub(r"\bmaestro\b|\bmagisterio\b|\bgraduado\b|\bgraduada\b", " ", s)
    s = re.sub(r"[^a-z0-9ñ ]", " ", s)
    return frozenset(ABREVIATURAS.get(w, w) if " " not in ABREVIATURAS.get(w, w) else w
                     for w in " ".join(ABREVIATURAS.get(w, w) for w in s.split()).split() if w not in VACIAS)


def partes(nombre: str) -> list[str]:
    """Los dos grados de un doble escrito «A - B», «A-B», «A / B» o «A + B» (sin lo que va entre paréntesis)."""
    base = re.sub(r"\([^)]*\)", " ", ANEXO_OFERTA.sub("", nombre))
    return [z for z in re.split(r"\s*(?:\s-\s|(?<=[A-Za-záéíóúñ.])-\s*(?=[A-ZÁÉÍÓÚ])|/|\s\+\s)\s*", base) if z.strip()]


def pistas(nombre: str) -> list[str]:
    """Lo que va entre paréntesis o comillas («Campus Villalba», «Guadalajara», «en inglés», «Facultad Medicina
    UAM», «"Gimbernat"»)."""
    return [y.strip() for x in re.findall(r'\(([^)]*)\)|"([^"]*)"|«([^»]*)»', nombre) for y in x if y.strip()]


def _nota(tok: str) -> float | None:
    m = re.match(r"(\d{1,2})[.,](\d{2,3})", tok)
    return float(f"{m.group(1)}.{m.group(2)}") if m else None


# ------------------------------------------------------------------------------------------------- Madrid

def _por_posicion(valores: list[tuple], cols: list[tuple]) -> dict[int, tuple] | None:
    """Cada cifra a la columna con el centro más cercano; None si alguna cae lejos de toda columna o dos cifras
    caen en la misma (un guion sobrante en el hueco de las llamadas se descarta)."""
    centros = [(a + b) / 2 for a, b, _, _ in cols]
    asignados: dict[int, tuple] = {}
    for v in valores:
        c = (v[1] + v[2]) / 2
        i = min(range(len(cols)), key=lambda k: abs(centros[k] - c))
        d = abs(centros[i] - c)
        if d > 8:
            return None
        if i in asignados:
            previo = asignados[i]
            d_previo = abs(centros[i] - (previo[1] + previo[2]) / 2)
            perdedor = v if d >= d_previo else previo
            if not perdedor[0].startswith("-"):
                return None
            if perdedor is previo:
                asignados[i] = v
            continue
        asignados[i] = v
    return asignados


def leer_madrid(lineas: list[str]) -> list[dict]:
    """Filas del PDF del distrito único (un curso): código, universidad, nombre y notas por grupo y convocatoria.

    Dos tablas: la completa (grupos 1 a 5 con ordinaria y extraordinaria y el 6 con extraordinaria, once columnas,
    con «-----» en las celdas sin plazas) y la de la Autónoma (grupos 1, 2 y 6, cinco columnas, con celdas vacías).
    En la completa, una fila con once cifras se lee en orden; con alguna de más (un guion en el hueco de las
    llamadas «(9)»), por la posición de cada cifra bajo su columna, y si la cabecera no tiene posiciones fiables (el
    texto del PDF pega o desordena los rótulos), solo el grupo 1, que son siempre sus dos primeras cifras. En la
    parcial, por posición bajo los rótulos «Grupo N», que van centrados sobre sus columnas. Lo dudoso se descarta."""
    filas, univ, curso = [], None, None
    grupos_cab: list[tuple] = []
    tabla, cols, fiable = None, None, False
    for linea in lineas:
        t = linea.strip()
        if t.startswith("### página"):
            tabla, cols, grupos_cab = None, None, []
            continue
        m = re.search(r"UNIVERSIDAD\s+(?:DE\s+)?([A-ZÁÉÍÓÚÑ ]+?)(?:\s+DE MADRID)?\s*(?:-|$)", t)
        if m and t.startswith("UNIVERSIDAD"):
            univ = next((v for k, v in UNIV_MADRID.items() if k in m.group(1)), None)
        m = re.search(r"CURSO\s+(20\d\d)\s*/\s*(20\d\d)", t)
        if m:
            curso = f"{m.group(1)}-{m.group(2)}"
        g = [((x.start() + x.end()) / 2, int(x.group(1))) for x in re.finditer(r"Grupo\s*(\d)", linea)]
        if len(g) >= 2:
            grupos_cab = g if [n for _, n in g] == sorted({n for _, n in g}) else []
            continue
        cab = [(x.start(), x.end(), x.group()) for x in CABECERA.finditer(linea)]
        if len(cab) >= 4:
            fiable = all(cab[k + 1][0] - cab[k][1] >= 2 for k in range(len(cab) - 1))
            if len(cab) == len(COMPLETA):
                tabla, cols = "completa", [(a, b, gr, conv) for (a, b, _), (gr, conv) in zip(cab, COMPLETA)]
            elif grupos_cab and fiable:
                # cada grupo es una «Ordinaria» con su «Extraord.» detrás, o una «Extraord.» sola (grupo 6); los
                # grupos de la cabecera se reparten en ese orden (los rótulos no siempre van centrados)
                huecos, k = [], 0
                for a, b, txt in cab:
                    if txt.startswith("Ord") or not huecos or huecos[-1][-1][2].startswith("Ext"):
                        huecos.append([])
                    huecos[-1].append((a, b, txt))
                etiquetas = [n for _, n in grupos_cab]
                if len(huecos) == len(etiquetas):
                    cols = [(a, b, gr, "ordinaria" if txt.startswith("Ord") else "extraordinaria")
                            for gr, hueco in zip(etiquetas, huecos) for a, b, txt in hueco]
                    tabla = "parcial"
                else:
                    tabla, cols = None, None
            else:
                tabla, cols = None, None
            continue
        m = re.match(r"\s*(\d{4})\s+(\S.*?)\s{2,}(?=[\d-])", linea)
        if not (m and univ and curso):
            continue
        resto = [(x.group(), x.start(), x.end()) for x in TOKEN.finditer(linea, m.end())]
        valores = [x for x in resto if not x[0].startswith("(")]
        llamadas = {}
        for tok, ini, _ in resto:
            if tok.startswith("("):
                previo = [v for v in valores if v[1] < ini]
                if previo:
                    llamadas[previo[-1][1]] = tok.strip("()")
        nombres: list[tuple] = list(COMPLETA)
        asignados: dict[int, tuple] | None
        if len(valores) == len(COMPLETA) and tabla != "parcial":
            asignados, metodo = dict(enumerate(valores)), "orden"
        elif tabla == "completa" and fiable:
            asignados, metodo = _por_posicion(valores, cols), "posicion"
            if asignados is None and len(valores) >= 2:
                asignados, metodo = {0: valores[0], 1: valores[1]}, "grupo_1"
        elif tabla == "completa" and len(valores) >= 2:
            asignados, metodo = {0: valores[0], 1: valores[1]}, "grupo_1"
        elif tabla == "parcial":
            nombres = [(gr, conv) for _, _, gr, conv in cols]
            if len(valores) == len(cols):
                asignados, metodo = dict(enumerate(valores)), "orden"
            else:
                asignados, metodo = _por_posicion(valores, cols), "posicion"
        else:
            continue
        if not asignados:
            continue
        for i, (grupo, conv) in enumerate(nombres):
            if i not in asignados:
                continue
            tok, ini, _ = asignados[i]
            filas.append({
                "distrito": "madrid", "curso": curso, "universidad": univ, "codigo_local": m.group(1),
                "titulacion": re.sub(r"\s+", " ", m.group(2)).strip(), "cupo": GRUPOS_MADRID[grupo],
                "grupo": grupo, "convocatoria": conv, "lista": "final",
                "nota": _nota(tok), "sin_plazas": tok.startswith("-"), "todos_admitidos": tok.endswith("*"),
                "llamada": llamadas.get(ini), "lectura": metodo})
    return filas


# ------------------------------------------------------------------------------------------------- Murcia

def leer_murcia(lineas: list[str]) -> list[dict]:
    """CSV de datos abiertos de la Universidad de Murcia: código del título y del centro del Ministerio."""
    texto = "\n".join(x for x in lineas if x.strip() and not x.startswith("### "))
    filas = []
    for r in csv.DictReader(io.StringIO(texto)):
        if (r.get("ciclo_titulacion") or "").strip().lower() != "grado" or not r.get("nota_corte"):
            continue
        a, b = (r.get("curso_academico") or "/").split("/")
        filas.append({
            "distrito": "murcia", "curso": f"{a}-{b}", "universidad": "Murcia",
            "codigo_local": r.get("titulacion_cod"), "titulacion": r.get("titulacion"), "centro": r.get("centro"),
            "codigo_titulo": r.get("titulacion_cod_mec"), "codigo_centro": r.get("centro_cod_mec"),
            "cupo": "general", "convocatoria": None, "lista": "final", "nota": float(r["nota_corte"]),
            "sin_plazas": False, "todos_admitidos": None})
    return filas


# ------------------------------------------------------------------------------------------------- Andalucía

CITA_ANDALUCIA = ("Junta de Andalucía, Distrito Único Andaluz: notas de corte de años anteriores (definitivas de la "
                  "convocatoria ordinaria, última lista de admitidos de noviembre)")
UNIV_ANDALUCIA = {"ALMERIA": "Almería", "CADIZ": "Cádiz", "CORDOBA": "Córdoba", "GRANADA": "Granada",
                  "HUELVA": "Huelva", "JAEN": "Jaén", "MALAGA": "Málaga", "P. OLAVIDE": "Pablo de Olavide",
                  "PABLO DE OLAVIDE": "Pablo de Olavide", "SEVILLA": "Sevilla"}
CUPOS_ANDALUCIA = {"GENERAL": "general", "TITULADOS": "titulados", "MAYORES 25": "mayores_25",
                   "MAYORES 40": "mayores_40", "MAYORES 45": "mayores_45"}


def leer_andalucia(lineas: list[str]) -> list[dict]:
    """CSV de la consulta histórica del Distrito Único Andaluz (un fichero por curso, todas las universidades
    públicas): código de la petición (título y centro), grado, centro y la nota de los cinco cupos. Son las notas
    definitivas de la convocatoria ordinaria (última lista de admitidos, en noviembre). Tras la cifra del cupo general
    puede ir «PREF» o «N.P.» (si el último admitido era preferente o no: con «N.P.» entraron todos los preferentes) y
    tras la de mayores de 25 un código (OPA, ONPA…): se guardan tal cual."""
    texto = "\n".join(x.replace("\ufeff", "").replace("ï»¿", "") for x in lineas if x.strip() and not x.startswith("### "))
    filas = []
    for r in csv.DictReader(io.StringIO(texto), delimiter=";"):
        if not (r.get("CURSO") or "").strip().isdigit() or not r.get("GRADO"):
            continue
        a = int(r["CURSO"])
        univ = UNIV_ANDALUCIA.get(sin_acentos(r.get("UNIVERSIDAD") or "").upper().strip())
        for col, cupo in CUPOS_ANDALUCIA.items():
            v = (r.get(col) or "").strip()
            m = re.match(r"(\d{1,2},\d{2,3})\s*(.*)$", v)
            if not m:
                continue
            marca = m.group(2).strip() or None
            filas.append({"distrito": "andalucia", "curso": f"{a}-{a + 1}", "universidad": univ,
                          "codigo_local": (r.get("PETICION") or "").strip() or None,
                          "titulacion": re.sub(r"\s+", " ", r["GRADO"]).strip(),
                          "centro_nombre": re.sub(r"\s+", " ", r.get("CENTRO") or "").strip() or None,
                          "cupo": cupo, "convocatoria": "ordinaria", "lista": "final", "nota": _nota(m.group(1)),
                          "sin_plazas": False,
                          "todos_admitidos": (marca == "N.P.") if cupo == "general" else None,
                          "tipo_ultimo_admitido": marca})
    return filas


# ------------------------------------------------------------------------------------------------- Salamanca

def leer_usal(lineas: list[str]) -> list[dict]:
    """Notas de corte de la Universidad de Salamanca (un PDF por curso): nombre del grado, plazas y, primero, la
    nota del grupo general con su tipo entre paréntesis («prioritaria ordinaria», «no prioritaria extraord.»: si el
    último admitido no era prioritario, entraron todos los prioritarios). Las finales y las de «tras llamamientos»
    son la última lista; la del tercer listado (curso en marcha) no lo es."""
    texto = " ".join(lineas[:60])
    m = re.search(r"CURSO\s+(20\d\d)\s*[-/]\s*(\d\d)", texto, re.I) or re.search(r"(20\d\d)-(\d\d)\b", texto)
    if not m:
        return []
    curso = f"{m.group(1)}-20{m.group(2)}"
    lista = "tercer_listado" if re.search(r"tercer\w*\s*y?\s*último\s+listado", texto, re.I) else "final"
    filas = []
    for linea in lineas:
        m = re.match(r"\s*(\S.*?\S)\s{2,}(\d{1,3})\s{2,}(\d{2}\.\d{3})\s*\(\s*([^)]*)\)", linea)
        if not m or re.search(r"(?i)graduado|plazas", m.group(1)) or re.search(r"[-–]\s*$", m.group(1)):
            continue  # cabeceras, o un doble cuyo segundo grado va en otra línea (nombre incompleto)
        tipo = re.sub(r"\s+", " ", m.group(4)).strip()
        filas.append({"distrito": "salamanca", "curso": curso, "universidad": "Salamanca", "codigo_local": None,
                      "titulacion": re.sub(r"\s+", " ", m.group(1)), "plazas": int(m.group(2)), "cupo": "general",
                      "convocatoria": None, "lista": lista, "nota": float(m.group(3)), "sin_plazas": False,
                      "todos_admitidos": tipo.lower().startswith("no prior"), "tipo_ultimo_admitido": tipo})
    return filas


# ------------------------------------------------------------------------------------------------- País Vasco

CAMPUS_EHU = {"ALAVA": ["vitoria-gasteiz"], "ARABA": ["vitoria-gasteiz"],
              "GIPUZKOA": ["donostia/san sebastian", "eibar", "elgoibar"], "BIZKAIA": ["leioa", "bilbao"]}
# Orden de las cinco casillas en todos los cursos: mayores de 25, mayores de 45, mayores de 40 con experiencia
# laboral, cupo general (bachillerato y FP) y titulados. Los rótulos de la cabecera salen desordenados en el texto
# (en 2017-18 dos campus los dan con el cupo general primero), pero las cifras no: el cupo general es siempre la cuarta
# casilla (Medicina de Bizkaia 2017-18: «5,560 * - 12,331 9,030»), y el doble de Física e Ingeniería Electrónica de
# 2020-21 da 13,124, la nota que publicó la universidad.
ORDEN_EHU = ["mayores_25", "mayores_45", "mayores_40", "general", "titulados"]


def _trocear_ehu(resto: str, n: int = 5) -> list[str] | None:
    """Las cinco casillas de una fila cuyo texto sale pegado («*8,0836,610»): todas las maneras de partirlo en n
    valores (cifra con tres decimales, o dos si no hay otra lectura; «*», «-», «─»; «E» delante de una cifra). Solo
    vale si hay una sola manera."""
    s = re.sub(r"\s+", "", resto).replace("´", "")
    lecturas: list[list[str]] = []

    def partir(i: int, hechas: list[str]) -> None:
        if len(lecturas) > 1 or len(hechas) > n:
            return
        if i == len(s):
            if len(hechas) == n:
                lecturas.append(hechas)
            return
        # una nota de admisión va de 5 a 14 (parte entera 5-9 o 10-14, sin cero delante): «8,0836,610» no se
        # lee «8,08» y «36,610», ni «6,5108,750» «6,51» y «08,750»
        for pat in (r"E?(?:1[0-4]|[5-9]),\d{3}", r"E?(?:1[0-4]|[5-9]),\d{2}", r"[*\-─]"):
            m = re.compile(pat).match(s, i)
            if m:
                partir(m.end(), hechas + [m.group()])

    partir(0, [])
    return lecturas[0] if len(lecturas) == 1 else None


def leer_ehu(lineas: list[str]) -> list[dict]:
    """Universidad del País Vasco: «Límite de plazas y nota de corte de admisión» de cada curso (las definitivas,
    tras la convocatoria extraordinaria), por campus, con las plazas y la nota de los cinco cupos. Leyenda del PDF:
    «*» plazas vacantes (entraron todos), «─» sin acceso por ese cupo, «E» nota de la convocatoria extraordinaria."""
    if any("(lectura óptica)" in x for x in lineas[:3]):
        # desde 2022-23 los PDF son imágenes: la lectura óptica confunde cifras y bordes de tabla («84%», «1omo») y
        # el orden de las casillas cambia (cupo general primero); no se usa hasta poder contrastarla
        return []
    texto = " ".join(lineas[:12])
    m = re.search(r"CURSO\s+(20\d\d)\s*[-/]\s*(?:20)?(\d\d)\b", texto) or re.search(r"\b(20\d\d)\s*[-/]\s*(?:20)?(\d\d)\b", texto)
    if not m:
        return []
    curso = f"{m.group(1)}-20{m.group(2)}"
    filas, campus, orden = [], None, None
    for linea in lineas:
        c = re.search(r"CAMPUS DE (\w+)", linea)
        if c:
            campus = c.group(1).upper()
            # una cabecera con las cinco casillas: el cupo general y cuatro porcentajes de plazas
            orden = ORDEN_EHU if (len(re.findall(r"\d% de las plazas", linea)) == 4
                                  and "Bachillerato" in linea) else None
            continue
        f = re.match(r"\s*(\S.*?\S)\s{2,}(\d{1,3})\s{2,}([\d,*\-─E´\s]+?)\s*$", linea)
        if not f or not orden or campus not in CAMPUS_EHU or not re.search(r"(?i)grado|degree|bachelor", f.group(1)):
            continue
        valores = _trocear_ehu(f.group(3))
        if not valores:
            filas.append({"distrito": "pais-vasco", "curso": curso, "titulacion": re.sub(r"\s+", " ", f.group(1)),
                          "ilegible": True})
            continue
        for cupo, v in zip(orden, valores):
            nota = _nota(v.lstrip("E")) if v[0] in "E0123456789" else None
            filas.append({"distrito": "pais-vasco", "curso": curso,
                          "universidad": "País Vasco/Euskal Herriko Unibertsitatea", "codigo_local": None,
                          "titulacion": re.sub(r"\s+", " ", f.group(1)), "campus": campus,
                          "municipios": CAMPUS_EHU[campus], "plazas": int(f.group(2)) if cupo == "general" else None,
                          "cupo": cupo, "convocatoria": "extraordinaria" if v.startswith("E") else "ordinaria",
                          "lista": "final", "nota": nota, "sin_plazas": v in "-─", "todos_admitidos": v == "*"})
    return [x for x in filas if not x.get("ilegible")]


# ------------------------------------------------------------------------------------------------- Cantabria

def leer_cantabria(lineas: list[str], posiciones: list[dict] | None) -> list[dict]:
    """«Comparativa notas de corte estudios de grado. 5 últimos cursos» de la Universidad de Cantabria (PDF de
    imagen, leído con tesseract y con la posición de cada palabra): por curso, la nota de la convocatoria ordinaria
    (junio, o julio en 2022-2023) y la de la extraordinaria (septiembre, o julio desde 2023-2024). Las celdas vacías
    no salen en el texto, así que cada cifra va a la columna cuyo rótulo tiene el centro más cerca; si alguna queda
    lejos de todas o dos caen en la misma, la fila no se usa."""
    if not posiciones or not any(p.get("ocr") for p in posiciones):
        return []
    filas = []
    for pg in posiciones:
        lns = pg.get("lineas") or []
        cursos, cols = [], []
        for ln in lns:
            texto = " ".join(t[1] for t in ln["trozos"])
            if not cursos and re.search(r"CURSO\s+20\d\d", texto):
                cursos = [f"{a}-{a + 1}" for a in map(int, re.findall(r"CURSO\s+(20\d\d)", texto))]
            elif cursos and not cols and re.search(r"JUNIO|JULIO", texto):
                cols = [(t[0] + t[2] / 2, t[1]) for t in ln["trozos"] if re.match(r"JUNIO|JULIO|SEPTIEMBRE", t[1])]
        if len(cursos) < 2 or len(cols) != 2 * len(cursos):
            continue
        paso = min(b[0] - a[0] for a, b in zip(cols, cols[1:]))
        anterior = None
        for ln in lns:
            nums = [t for t in ln["trozos"] if re.fullmatch(r"\d{1,2},\d{3}", t[1])]
            nombre = " ".join(t[1] for t in ln["trozos"] if t[0] + t[2] / 2 < cols[0][0] - paso / 2).strip()
            if not nums:
                # segunda línea de un nombre largo («Doble Grado en … y» / «Economía»)
                if anterior and nombre and not re.search(r"CURSO|JUNIO|ESTUDIOS|Universidad", nombre):
                    for x in anterior:
                        x["titulacion"] += " " + nombre
                anterior = None
                continue
            if not re.match(r"(?i)(doble\s+)?grado", nombre):
                anterior = None
                continue
            asignadas: dict[int, float] = {}
            valida = True
            for t in nums:
                c = t[0] + t[2] / 2
                k = min(range(len(cols)), key=lambda i: abs(cols[i][0] - c))
                if abs(cols[k][0] - c) > paso / 2 or k in asignadas:
                    valida = False
                    break
                asignadas[k] = _nota(t[1])
            if not valida:
                anterior = None
                continue
            anterior = []
            for k, nota in sorted(asignadas.items()):
                x = {"distrito": "cantabria", "curso": cursos[k // 2], "universidad": "Cantabria", "codigo_local": None,
                     "titulacion": nombre, "cupo": "general", "convocatoria": "ordinaria" if k % 2 == 0 else "extraordinaria",
                     "lista": "final", "nota": nota, "sin_plazas": False, "todos_admitidos": None,
                     "lectura": "optica"}
                filas.append(x)
                anterior.append(x)
    return filas


# ------------------------------------------------------------------------------------------------- Burgos

CUPOS_UBU = ["general", "titulados", "mayores_25", "mayores_40_45", "discapacidad", "deportistas"]


def leer_ubu(lineas: list[str], posiciones: list[dict] | None) -> list[dict]:
    """«Notas de corte (evolución por cursos)» de la Universidad de Burgos: plazas, titulación y, por cupo (general,
    titulados, mayores de 25, de 40 y 45, discapacidad, deportistas), la nota de seis cursos. Las celdas vacías
    (sin solicitudes) no salen en el texto y el PDF escribe cada fila en un solo bloque, así que se lee como imagen
    (`notas_fuentes`, OCR_SIEMPRE) y cada cifra va a la columna del año cuyo rótulo tiene el centro más cerca. El
    asterisco («5,000*») es que el último admitido era de un cupo no prioritario: entraron todos los prioritarios.
    A 30/10/2026 la lectura óptica de esa tabla sale ilegible y este lector no da filas: queda para una lectura a
    más resolución."""
    if not posiciones or not any(p.get("ocr") for p in posiciones):
        return []
    filas = []
    for pg in posiciones:
        lns = pg.get("lineas") or []
        cols = []
        for ln in lns:
            anios = [t for t in ln["trozos"] if re.fullmatch(r"20[12]\d", t[1])]
            if len(anios) >= 12:
                cols = [(t[0] + t[2] / 2, int(t[1])) for t in anios]
                break
        grupo = len({c[1] for c in cols})  # años por cupo (seis)
        if not cols or len(cols) % grupo or len(cols) // grupo > len(CUPOS_UBU):
            continue
        paso = min(b[0] - a[0] for a, b in zip(cols, cols[1:]))
        for ln in lns:
            ts = ln["trozos"]
            if not ts or not re.fullmatch(r"\d{1,3}", ts[0][1]):
                continue  # las filas empiezan por las plazas
            nombre = " ".join(t[1] for t in ts[1:] if t[0] + t[2] / 2 < cols[0][0] - paso / 2).strip()
            if not re.match(r"(?i)(doble\s+)?grado", nombre):
                continue
            valores, valida = {}, True
            for j, t in enumerate(ts):
                m = re.fullmatch(r"(\d{1,2},\d{3})(\*?)", t[1])
                if not m:
                    continue
                ast = bool(m.group(2)) or (j + 1 < len(ts) and ts[j + 1][1] == "*")
                c = t[0] + t[2] / 2
                k = min(range(len(cols)), key=lambda i: abs(cols[i][0] - c))
                if abs(cols[k][0] - c) > paso / 2 or k in valores:
                    valida = False
                    break
                valores[k] = (_nota(m.group(1)), ast)
            if not valida or not valores:
                continue
            for k, (nota, ast) in sorted(valores.items()):
                anio = cols[k][1]
                filas.append({"distrito": "burgos", "curso": f"{anio}-{anio + 1}", "universidad": "Burgos",
                              "codigo_local": None, "titulacion": nombre, "plazas": int(ts[0][1]) if k < grupo else None,
                              "cupo": CUPOS_UBU[k // grupo], "convocatoria": None, "lista": "final",
                              "nota": nota, "sin_plazas": False, "todos_admitidos": ast,
                              "tipo_ultimo_admitido": "no prioritario" if ast else None, "lectura": "optica"})
    return filas


# ------------------------------------------------------------------------------------------------- Cataluña

SIGLAS_CAT = {"UB": "Barcelona", "UAB": "Autónoma de Barcelona", "UPC": "Politécnica de Catalunya", "UPF": "Pompeu Fabra",
              "UdG": "Girona", "UdL": "Lleida", "URV": "Rovira i Virgili", "UVic-UCC": "Vic-Central de Catalunya",
              "UVic": "Vic-Central de Catalunya", "UOC": "Oberta de Catalunya", "UIC": "Internacional de Catalunya",
              "UAO": "Abat Oliba CEU", "URL": "Ramón Llull"}


def _registros_json(lineas: list[str]) -> list[dict]:
    salida = []
    for x in lineas:
        x = x.strip().lstrip("[").lstrip(",").rstrip("]")
        if x.startswith("{"):
            try:
                salida.append(json.loads(x))
            except json.JSONDecodeError:
                pass
    return salida


def leer_cataluna(lineas: list[str]) -> list[dict]:
    """Socrata de la Generalitat (usyn-hngc): grado, vía PAU/CFGS/FP, nota de la preinscripción de junio y plazas.
    Las filas repetidas (el mismo curso y código dos veces, iguales) se cuentan una vez."""
    filas, vistos = [], set()
    for r in _registros_json(lineas):
        if r.get("tipus_d_estudi") != "Grau" or not r.get("nota_de_tall"):
            continue
        clave = (r.get("curs_acad_mic"), r.get("codi_oferta"), r.get("via_d_acc_s"))
        if clave in vistos:
            continue
        vistos.add(clave)
        filas.append({
            "distrito": "cataluna", "curso": r.get("curs_acad_mic"),
            "universidad": SIGLAS_CAT.get(r.get("sigles_universitat_responsable") or ""),
            "codigo_local": r.get("codi_oferta"), "titulacion": r.get("nom_de_l_oferta"), "municipio": r.get("municipi"),
            "plazas": int(r["nombre_de_places"]) if (r.get("nombre_de_places") or "").isdigit() else None,
            "cupo": "general" if (r.get("via_d_acc_s") or "").lower().startswith("pau") else r.get("via_d_acc_s"),
            "convocatoria": "junio", "lista": "primera_asignacion", "nota": float(r["nota_de_tall"]),
            "sin_plazas": False, "todos_admitidos": None})
    return filas


LECTORES = {
    "cantabria": (leer_cantabria, lambda d: "Evoluci%C3%B3n%20Notas%20de%20Corte" in d["url"],
                  "Universidad de Cantabria: comparativa de notas de corte de grado de los cinco últimos cursos"),
    "madrid": (leer_madrid, lambda d: d.get("formato") == "pdf", CITA_MADRID),
    "murcia": (leer_murcia, lambda d: d.get("formato") == "csv" and "datos.um.es" in d["url"],
               "Universidad de Murcia, datos abiertos: nota de corte de grado"),
    "castilla-leon": [(leer_usal, lambda d: "usal.es/files/acceso/notas_corte" in d["url"] and d.get("formato") == "pdf",
                       "Universidad de Salamanca: notas de corte de grado"),
                      (leer_ubu, lambda d: "ubu.es/sites/default/files/portal_page/files/notas_de_corte" in d["url"],
                       "Universidad de Burgos: notas de corte (evolución por cursos)")],
    "andalucia": (leer_andalucia, lambda d: "g_not_cor_anteriores_csv.php" in d["url"] and d.get("formato") == "csv",
                  CITA_ANDALUCIA),
    "pais-vasco": (leer_ehu, lambda d: "ehu.eus" in d["url"] and d.get("formato") == "pdf",
                   "Universidad del País Vasco/Euskal Herriko Unibertsitatea: límite de plazas y nota de corte de admisión"),
    "cataluna": (leer_cataluna, lambda d: "/resource/usyn-hngc" in d["url"],
                 "Generalitat de Catalunya, datos abiertos: notas de corte de acceso a los estudios universitarios"),
}


CON_POSICIONES = {leer_cantabria, leer_ubu}


def leer_fuentes(carpetas: list[Path]) -> list[dict]:
    """Lee los documentos de cada distrito con su lector. Si un documento está en varias carpetas, gana la más
    reciente (la carpeta empieza por la fecha)."""
    docs: dict[tuple[str, str], tuple[str, dict]] = {}
    for c in carpetas:
        for f in sorted(c.rglob("notas_fuentes/*.json")):
            if f.name == "resumen.json":
                continue
            x = json.loads(f.read_text(encoding="utf-8"))
            for d in x.get("documentos") or []:
                if d.get("sha256") and d.get("muestra"):
                    clave = (x["distrito"], d["url"])
                    previo = docs.get(clave)
                    # el mismo documento (misma huella) leído dos veces: gana la lectura más completa (con
                    # posiciones o lectura óptica, más líneas); si el documento cambió, gana la captura más reciente
                    if previo and previo[1]["sha256"] == d["sha256"]:
                        mejor = (bool(d.get("posiciones")), len(d["muestra"])) > \
                            (bool(previo[1].get("posiciones")), len(previo[1]["muestra"]))
                    else:
                        mejor = not previo or str(f) > previo[0]
                    if mejor:
                        docs[clave] = (str(f), {**d, "capturado": d.get("capturado") or x.get("capturado")})
    filas = []
    for (distrito, _), (_, d) in sorted(docs.items()):
        if distrito not in LECTORES:
            continue
        lectores = LECTORES[distrito] if isinstance(LECTORES[distrito], list) else [LECTORES[distrito]]
        elegido = next(((leer, cita) for leer, vale, cita in lectores if vale(d)), None)
        if not elegido:
            continue
        leer, cita = elegido
        for fila in (leer(d["muestra"], d.get("posiciones")) if leer in CON_POSICIONES else leer(d["muestra"])):
            fila["fuente"] = {"cita": cita, "url": d["url"], "sha256": d["sha256"], "capturado": d.get("capturado")}
            filas.append(fila)
    # un mismo curso puede venir en dos documentos (el PDF ordinario y el de la extraordinaria): gana el último
    unicas: dict[tuple, dict] = {}
    for x in filas:
        unicas[(x["distrito"], x["curso"], x.get("universidad"), x["codigo_local"], x["cupo"], x.get("convocatoria"),
                x["titulacion"], x.get("campus"))] = x
    return list(unicas.values())


# ------------------------------------------------------------------------------------------------- unión

def candidatos(catalogo: list[dict], qedu: dict, tarjetas: dict | None = None) -> dict[str, list[dict]]:
    """Por universidad (nombre del catálogo): cada título activo × centro, con sus palabras, su municipio, su centro,
    si se oferta en QEDU y las notas de QEDU por curso."""
    por: dict[str, list[dict]] = defaultdict(list)
    for t in catalogo:
        if t.get("situacion") != "Activo" or t.get("clase") not in ("grado", "doble"):
            continue
        for i in t.get("imparticiones") or []:
            if i.get("situacion") != "Activo":
                continue
            u = i.get("universidad") or t["universidades"][0]["nombre"]
            clave = (t["codigo"], i.get("unidad_codigo"))
            d = (qedu.get(clave) or {}).get("detalle") or {}
            notas = {d[k_curso]: round(float(d[k_nota]), 2)
                     for k_curso, k_nota in (("curso", "nota_corte"), ("curso_anterior", "nota_corte_anterior"))
                     if d.get(k_curso) and isinstance(d.get(k_nota), (int, float))}
            comp = [palabras(nombre_base(c.get("nombre") or "")) for c in t.get("componentes") or []]
            por[u].append({"codigo": t["codigo"], "clase": t["clase"], "nombre": t["nombre"],
                           "palabras": palabras(nombre_base(t["nombre"])),
                           "palabras_componentes": frozenset().union(*comp) if comp else frozenset(),
                           "centro": i.get("unidad_codigo"), "unidad": i.get("unidad") or "",
                           "municipio": sin_acentos(i.get("municipio") or ""), "idioma": i.get("idioma_extranjero"),
                           "propio": i.get("unidad_modalidad") == "Centro propio",
                           "plazas_qedu": {d["curso"]: d["plazas"]} if d.get("curso") and d.get("plazas") else {},
                           "ofertado": tarjetas is None or clave in tarjetas, "notas_qedu": notas})
    return por


def igual_a_qedu(q: float | None, nota: float | None) -> bool:
    """QEDU da dos decimales: el distrito publica tres. Vale el redondeo o el truncado (10,545 → 10,54 o 10,55)."""
    if q is None or nota is None:
        return False
    return abs(q - round(nota, 2)) < 0.006 or abs(q - int(nota * 100 + 1e-6) / 100) < 0.006


def _parecido(a: frozenset, b: frozenset) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def _es_pista(z: str, cs: list[dict]) -> bool:
    """Una parte del nombre que es un campus o un municipio («Campus Villalba», «Móstoles»), no un grado."""
    z = sin_acentos(z).strip()
    return bool(re.match(r"campus\b|sede\b|a distancia|presencial|semipresencial|online", z)) or any(
        z and (z == c["municipio"] or z in c["municipio"].split(" (")[0]) for c in cs)


def nombre_de_centro(z: str) -> str:
    """Abreviaturas de los nombres de centro del distrito («E.T.S. de Ingeniería», «F. Ciencias», «CC. Econ.»)."""
    z = re.sub(r"(?i)\bE\.\s*T\.\s*S\.", "Escuela Técnica Superior", z)
    z = re.sub(r"(?i)\bE\.\s*P\.\s*S\.", "Escuela Politécnica Superior", z)
    z = re.sub(r"(?i)\b(?:E|ESC)\.\s", "Escuela ", z)
    z = re.sub(r"(?i)\b(?:F|FAC)\.\s", "Facultad ", z)
    z = re.sub(r"(?i)\bCC\.\s*", "Ciencias ", z)
    z = re.sub(r"(?i)\bECON\.\s*", "Económicas ", z)
    z = re.sub(r"(?i)\bEMPRES?\.?(?=\s|\)|$)", "Empresariales", z)
    return re.sub(r"(?i)\(ADS\.?\)|\(ADSCRITO\)", " ", z)


def puntuar(nombre: str, x0: dict, xs: list[dict], cs: list[dict]) -> list[tuple[float, dict, str, float]]:
    """Puntuación de cada candidato: parecido del nombre (grado entero, grado con variante o los dos grados de un
    doble), pistas de centro y, si el distrito publica la nota final, la nota de QEDU del mismo curso."""
    ca = x0["distrito"] == "cataluna"
    trozos = partes(nombre)
    pist = [sin_acentos(z) for z in pistas(nombre)] + [sin_acentos(z) for z in trozos[1:] if _es_pista(z, cs)]
    if x0.get("municipio"):
        pist.append(sin_acentos(x0["municipio"]).replace("l'", "").strip())
    pist += [sin_acentos(m) for m in x0.get("municipios") or []]  # los del campus (UPV/EHU)
    trozos = [z for z in trozos if not _es_pista(z, cs)] or trozos
    entero = palabras(" ".join(trozos), ca)
    idioma = any(re.search(r"ingl|angl|bilingu|english", z) for z in pist)
    de_doble = len(trozos) >= 2 or bool(re.search(r"(?i)doble|simultane|programa conjunto|pceo", nombre))
    # «Economía-Derecho»: cada parte es un grado de la universidad → es un doble, no «Economía» con una variante
    grados = [c["palabras"] for c in cs if c["clase"] == "grado"]
    solo_doble = len(trozos) >= 2 and all(any(_parecido(palabras(z, ca), g) >= 0.75 for g in grados) for z in trozos)
    solo_doble = solo_doble or bool(re.search(r"(?i)simultane", nombre))  # «(simultaneïtat)»: doble en Cataluña
    # un nombre que se presenta como doble («Doble Grado en Gestión de Negocios + Rel. Lab. y Rec. Hum.») no es uno
    # de sus grados con una variante, aunque la abreviatura del segundo no se reconozca
    solo_doble = solo_doble or bool(re.match(r"(?i)\s*(?:doble|double|dobles?\s+titulaci|programa conjunto|pceo)", nombre))
    salida = []
    for c in cs:
        variante = ""
        if c["clase"] == "doble" and not de_doble:
            continue  # un nombre de un solo grado no se une con un doble
        if c["clase"] == "grado" and solo_doble:
            continue
        if c["clase"] == "doble":
            s = _parecido(entero, c["palabras_componentes"] or c["palabras"]) if len(trozos) >= 2 else \
                _parecido(entero, c["palabras"])
        else:
            s = _parecido(entero, c["palabras"])
            if len(trozos) >= 2:
                s1 = _parecido(palabras(trozos[0], ca), c["palabras"]) - 0.1  # «Estudios de Asia y África-Árabe»
                if s1 > s:
                    s, variante = s1, trozos[1]
        if s < 0.6:
            continue
        extra = 0.06 if c["ofertado"] else 0.0  # entre un título que se extingue y su sucesor, el que se oferta
        for z in pist:
            if z and (z in c["municipio"] or any(w in c["municipio"] for w in z.split() if len(w) > 4)):
                extra += 0.2
            if z and len(palabras(z) & palabras(c["unidad"])) >= 2:
                extra += 0.2
        if x0.get("centro_nombre"):
            # el distrito nombra el centro (Andalucía): cuanto más se parece al de la unidad, más puntos
            extra += 0.3 * _parecido(palabras(nombre_de_centro(x0["centro_nombre"])), palabras(c["unidad"]))
        if idioma and (c["idioma"] or "").startswith("Sí"):
            extra += 0.1
        if x0["lista"] == "final" and any(
                y.get("nota") and y["nota"] > 5 and igual_a_qedu(c["notas_qedu"].get(y["curso"]), y["nota"])
                for y in xs if y["cupo"] == "general" and y.get("convocatoria") in (None, "ordinaria")):
            extra += 0.2
        salida.append((s + extra, c, variante or ("idioma" if idioma else ""), s))
    return sorted(salida, key=lambda z: -z[0])


PARECIDO_NOMBRE_MINIMO = 0.8


def unir(filas: list[dict], cands: dict[str, list[dict]]) -> Counter:
    """Pone `codigo_titulo` y `codigo_centro` (y cómo se unió) a cada fila que se puede unir con seguridad: el mejor
    candidato con parecido de al menos 0,8 y sin otro título a menos de 0,05."""
    resumen: Counter = Counter()
    por_oferta: dict[tuple, list[dict]] = defaultdict(list)
    for x in filas:
        # el mismo nombre en dos campus (ADE en Álava y en Bizkaia) son dos ofertas
        por_oferta[(x["distrito"], x.get("universidad"), x["codigo_local"], x["titulacion"], x.get("campus"))].append(x)
    for (distrito, univ, _, nombre, _), xs in por_oferta.items():
        if xs[0].get("codigo_titulo"):
            for x in xs:
                x["union"] = {"metodo": "codigo_del_ministerio"}
            resumen["codigo_del_ministerio"] += 1
            continue
        if re.search(r"(?i)\(agrupaci[oó]\)|grau obert|grado abierto", nombre):
            resumen["agrupacion_o_grado_abierto"] += 1  # primer curso común de varios grados: no es un título
            continue
        puntos = puntuar(nombre, xs[0], xs, cands.get(univ or "", []))
        if not puntos:
            resumen["sin_candidato"] += 1
            continue
        mejor = puntos[0][0]
        cerca = [z for z in puntos if z[0] >= mejor - 0.05]
        if len({z[1]["codigo"] for z in cerca}) != 1 or mejor < 0.8:
            resumen["ambigua" if len({z[1]["codigo"] for z in cerca}) > 1 else "parecido_bajo"] += 1
            continue
        centros = {z[1]["centro"] for z in cerca}
        if len(centros) > 1 and not pistas(nombre) and not xs[0].get("centro_nombre"):
            # sin campus ni centro en el nombre, el título se refiere a su centro propio (los adscritos se nombran)
            propios = [z for z in cerca if z[1]["propio"]]
            if len({z[1]["centro"] for z in propios}) == 1:
                cerca, centros = propios, {propios[0][1]["centro"]}
        _, c, variante, parecido = cerca[0]
        if parecido < PARECIDO_NOMBRE_MINIMO and not any(
                y.get("nota") and y["nota"] > 5 and igual_a_qedu(c["notas_qedu"].get(y["curso"]), y["nota"]) for y in xs):
            # el centro y la universidad empujan, pero el nombre no basta: un título ya extinguido (los históricos
            # vienen desde 2010) no se une con el activo más parecido salvo que QEDU confirme la nota
            resumen["parecido_de_nombre_bajo"] += 1
            continue
        for x in xs:
            x["codigo_titulo"] = c["codigo"]
            x["codigo_centro"] = c["centro"] if len(centros) == 1 else None
            x["union"] = {"metodo": "nombre", "puntuacion": round(mejor, 2), "parecido_nombre": round(parecido, 2), "nombre_catalogo": c["nombre"],
                          "variante": variante or None}
        resumen["nombre" if len(centros) == 1 else "nombre_sin_centro"] += 1
    # el mismo código del distrito en otro curso, con un nombre parecido (renombrado, abreviado), es la misma oferta
    por_codigo: dict[tuple, list[list[dict]]] = defaultdict(list)
    for (distrito, univ, codigo, _, _), xs in por_oferta.items():
        if codigo:
            por_codigo[(distrito, univ, codigo)].append(xs)
    for grupos in por_codigo.values():
        unidas = {(xs[0]["codigo_titulo"], xs[0].get("codigo_centro")): xs for xs in grupos if xs[0].get("codigo_titulo")}
        if len(unidas) != 1:
            continue
        (tit, cen), modelo = next(iter(unidas.items()))
        for xs in grupos:
            if xs[0].get("codigo_titulo"):
                continue
            if _parecido(palabras(xs[0]["titulacion"]), palabras(modelo[0]["titulacion"])) < 0.5:
                continue
            for x in xs:
                x["codigo_titulo"], x["codigo_centro"] = tit, cen
                x["union"] = {**modelo[0]["union"], "metodo": "mismo_codigo_otro_curso",
                              "nombre_en_ese_curso": modelo[0]["titulacion"]}
            resumen["mismo_codigo_otro_curso"] += 1
    return resumen


def nota_del_titulo(filas: list[dict]) -> dict[tuple, dict]:
    """(título, centro, curso) → la nota de corte del cupo general en la convocatoria ordinaria: la menor de sus
    ofertas (un título con menciones o grupos de idioma tiene una oferta por cada uno), que es lo que publica QEDU.
    Sin valor si todas las ofertas admitieron a todos los que lo pidieron (5,000 en el distrito)."""
    por: dict[tuple, list[dict]] = defaultdict(list)
    for x in filas:
        if x.get("codigo_titulo") and x.get("codigo_centro") and x["cupo"] == "general" \
                and x.get("convocatoria") in (None, "ordinaria", "junio") and x.get("nota") is not None:
            por[(x["codigo_titulo"], x["codigo_centro"], x["curso"])].append(x)
    return {k: {"nota": min(x["nota"] for x in xs), "ofertas": len(xs), "distrito": xs[0]["distrito"],
                "lista": xs[0]["lista"], "fuente": xs[0]["fuente"],
                # lo que el documento dice del último admitido («no prioritaria extraord.», «PREF»), tal cual
                "tipo_ultimo_admitido": min(xs, key=lambda x: x["nota"]).get("tipo_ultimo_admitido"),
                "plazas": sum(x["plazas"] for x in xs) if all(x.get("plazas") for x in xs) else None}
            for k, xs in por.items()}


CUPOS_RESERVA = {"titulados": "titulados universitarios", "mayores_25": "mayores de 25 años",
                 "mayores_40": "mayores de 40 años con experiencia laboral", "mayores_45": "mayores de 45 años"}


def notas_de_otros_cupos(filas: list[dict]) -> dict[tuple, dict]:
    """(título, centro) → {cupo: {curso: nota}} de los cupos de reserva (titulados, mayores de 25, 40 y 45) en la
    convocatoria ordinaria: la menor de las ofertas con nota, del mismo documento y la misma fila que la del cupo
    general, así que la unión con el título es la misma y se publica junto a ella si esta es publicable."""
    por: dict[tuple, list[dict]] = defaultdict(list)
    for x in filas:
        if x.get("codigo_titulo") and x.get("codigo_centro") and x["cupo"] in CUPOS_RESERVA \
                and x.get("convocatoria") in (None, "ordinaria", "junio") and x.get("nota") is not None:
            por[(x["codigo_titulo"], x["codigo_centro"], x["cupo"], x["curso"])].append(x)
    salida: dict[tuple, dict] = defaultdict(lambda: defaultdict(dict))
    for (tit, cen, cupo, curso), xs in sorted(por.items()):
        salida[(tit, cen)][cupo][curso] = {
            "nota": min(x["nota"] for x in xs), "ofertas": len(xs), "lista": xs[0]["lista"],
            "todos_admitidos": all(x.get("todos_admitidos") for x in xs), "fuente": xs[0]["fuente"]}
    return {k: {c: dict(v) for c, v in d.items()} for k, d in salida.items()}


DIFERENCIA_LISTA_POSTERIOR = 0.25


def tipo_de_contraste(q: float, nota: float) -> str:
    """Nota final del distrito frente a la de QEDU del mismo curso y centro. Además de «igual», hay dos diferencias
    que no indican una unión equivocada sino que QEDU toma la nota en otro momento del proceso (Andalucía: 511
    iguales, 65 con la del distrito algo menor y 67 con QEDU en 5,000, de 645): la del distrito es la de la última
    lista y queda por debajo de la de QEDU (menos de un cuarto de punto), o QEDU da 5,000 porque al final quedaron plazas
    libres. Cualquier otra diferencia es «distinta» y el histórico de ese título y centro no se publica."""
    if igual_a_qedu(q, nota):
        return "igual"
    if q <= 5.0005 < nota:
        return "qedu_con_plazas_libres"
    if nota < q < nota + DIFERENCIA_LISTA_POSTERIOR:
        return "lista_posterior_mas_baja"
    return "distinta"


def historico(filas: list[dict], cands: dict[str, list[dict]]) -> list[dict]:
    """Por título y centro: la nota de corte del cupo general por curso (la menor de sus ofertas, como QEDU) y el
    contraste con QEDU en los cursos que se solapan. Si en alguno no coincide (con una nota por encima de 5,000, que
    es «entraron todos»), el histórico de ese título y centro no se publica (`publicable`: false). Si ninguna nota es
    la final (Cataluña da la de la primera asignación, que no se puede contrastar con la de QEDU), solo se publica
    si las plazas del distrito y las de QEDU coinciden en el mismo curso. Cada curso lleva su tipo de lista."""
    por_cod = {(c["codigo"], c["centro"]): c for cs in cands.values() for c in cs}
    por: dict[tuple, dict] = defaultdict(dict)
    for (tit, cen, curso), v in nota_del_titulo(filas).items():
        por[(tit, cen)][curso] = v
    cupos = notas_de_otros_cupos(filas)
    salida = []
    for (tit, cen), cursos in sorted(por.items()):
        c = por_cod.get((tit, cen)) or {"notas_qedu": {}}
        contraste = Counter()
        for curso, v in cursos.items():
            q = c["notas_qedu"].get(curso)
            if q is not None and v["nota"] > 5 and v["lista"] == "final":
                contraste[tipo_de_contraste(q, v["nota"])] += 1
        finales = any(v["lista"] == "final" for v in cursos.values())
        # sin nota final que contrastar (Cataluña): vale si las plazas del distrito coinciden con las de QEDU en el
        # mismo curso, señal de que la oferta unida por el nombre es la misma
        plazas_iguales = [curso for curso, v in cursos.items() if v.get("plazas") is not None
                          and c.get("plazas_qedu", {}).get(curso) is not None
                          and abs(c["plazas_qedu"][curso] - v["plazas"]) < 0.5]
        if plazas_iguales:
            contraste["plazas_iguales"] = len(plazas_iguales)
        salida.append({"codigo_titulo": tit, "codigo_centro": cen, "distrito": next(iter(cursos.values()))["distrito"],
                       "cursos": {k: {"nota": v["nota"], "ofertas": v["ofertas"], "lista": v["lista"],
                                      **({"tipo_ultimo_admitido": v["tipo_ultimo_admitido"]}
                                         if v.get("tipo_ultimo_admitido") else {}),
                                      "fuente": v["fuente"]} for k, v in sorted(cursos.items())},
                       "contraste_qedu": dict(contraste),
                       # una nota de primera asignación (Cataluña) no se puede contrastar con la final de QEDU: no se
                       # publica hasta tener otra comprobación
                       "publicable": not contraste.get("distinta") and (finales or bool(plazas_iguales)),
                       "lista": "final" if all(v["lista"] == "final" for v in cursos.values())
                       else "varias" if finales else next(iter(cursos.values()))["lista"],
                       **({"otros_cupos": cupos[(tit, cen)]} if (tit, cen) in cupos else {})})
    return salida


def contrastar(filas: list[dict], cands: dict[str, list[dict]]) -> dict:
    """Por distrito: cuántas notas de título y centro (la menor de sus ofertas, por encima de 5) coinciden con QEDU
    en los cursos que se solapan."""
    por_cod = {(c["codigo"], c["centro"]): c for cs in cands.values() for c in cs}
    salida: dict = defaultdict(Counter)
    for (tit, cen, curso), v in nota_del_titulo(filas).items():
        c = por_cod.get((tit, cen))
        if not c or curso not in c["notas_qedu"] or v["nota"] <= 5 or v["lista"] != "final":
            continue
        salida[v["distrito"]][tipo_de_contraste(c["notas_qedu"][curso], v["nota"])] += 1
    return {k: dict(v) for k, v in salida.items()}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--fuentes", nargs="+", required=True, help="carpetas con …/notas_fuentes/*.json")
    p.add_argument("--catalogo", required=True)
    p.add_argument("--qedu", required=True, help="carpeta con qedu_detalles_*.jsonl")
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    from motor.grados.fichas import indexar_qedu

    filas = leer_fuentes([Path(x) for x in a.fuentes])
    catalogo = [json.loads(x) for x in Path(a.catalogo).read_text(encoding="utf-8").splitlines() if x.strip()]
    tarjetas, detalles = indexar_qedu(Path(a.qedu))
    cands = candidatos(catalogo, detalles, tarjetas)
    resumen = {"filas": len(filas), "ofertas_por_union": dict(unir(filas, cands)),
               "contraste_con_qedu": contrastar(filas, cands),
               "por_distrito_y_curso": {f"{d} {c}": n for (d, c), n in sorted(Counter(
                   (x["distrito"], x["curso"]) for x in filas).items())}}
    destino = Path(a.salida) / "datos" / "estudios" / "grados" / "notas_corte"
    destino.mkdir(parents=True, exist_ok=True)
    with (destino / "notas.jsonl").open("w", encoding="utf-8") as f:
        for x in sorted(filas, key=lambda z: (z["distrito"], z["curso"], z["codigo_local"] or "", z["cupo"])):
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    hist = historico(filas, cands)
    with (destino / "historico.jsonl").open("w", encoding="utf-8") as f:
        for x in hist:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    resumen["historico"] = {"titulos_y_centros": len(hist), "publicables": sum(1 for x in hist if x["publicable"]),
                            "con_cinco_cursos_o_mas": sum(1 for x in hist if x["publicable"] and len(x["cursos"]) >= 5)}
    (destino / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    (destino / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
