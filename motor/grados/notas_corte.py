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

Unión por nombre (pocos distritos traen el código): universidad, nombre normalizado del título y pistas de centro
(municipio o nombre del centro entre paréntesis); si queda más de un candidato, decide la nota de QEDU del mismo
curso (QEDU da la final de 2025-2026 y 2024-2025, redondeada a dos decimales) o las plazas. Sin unión segura, la
fila se guarda sin título y no se publica en ninguna ficha.

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
    return [z for z in re.split(r"\s*(?:\s-\s|(?<=[A-Za-záéíóúñ.])-(?=[A-ZÁÉÍÓÚ])|/|\s\+\s)\s*", base) if z.strip()]


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
    "madrid": (leer_madrid, lambda d: d.get("formato") == "pdf", CITA_MADRID),
    "murcia": (leer_murcia, lambda d: d.get("formato") == "csv" and "datos.um.es" in d["url"],
               "Universidad de Murcia, datos abiertos: nota de corte de grado"),
    "cataluna": (leer_cataluna, lambda d: "/resource/usyn-hngc" in d["url"],
                 "Generalitat de Catalunya, datos abiertos: notas de corte de acceso a los estudios universitarios"),
}


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
                    if clave not in docs or str(f) > docs[clave][0]:
                        docs[clave] = (str(f), {**d, "capturado": d.get("capturado") or x.get("capturado")})
    filas = []
    for (distrito, _), (_, d) in sorted(docs.items()):
        if distrito not in LECTORES:
            continue
        leer, vale, cita = LECTORES[distrito]
        if not vale(d):
            continue
        for fila in leer(d["muestra"]):
            fila["fuente"] = {"cita": cita, "url": d["url"], "sha256": d["sha256"], "capturado": d.get("capturado")}
            filas.append(fila)
    # un mismo curso puede venir en dos documentos (el PDF ordinario y el de la extraordinaria): gana el último
    unicas: dict[tuple, dict] = {}
    for x in filas:
        unicas[(x["distrito"], x["curso"], x.get("universidad"), x["codigo_local"], x["cupo"], x.get("convocatoria"),
                x["titulacion"])] = x
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


def puntuar(nombre: str, x0: dict, xs: list[dict], cs: list[dict]) -> list[tuple[float, dict, str]]:
    """Puntuación de cada candidato: parecido del nombre (grado entero, grado con variante o los dos grados de un
    doble), pistas de centro y, si el distrito publica la nota final, la nota de QEDU del mismo curso."""
    ca = x0["distrito"] == "cataluna"
    trozos = partes(nombre)
    pist = [sin_acentos(z) for z in pistas(nombre)] + [sin_acentos(z) for z in trozos[1:] if _es_pista(z, cs)]
    if x0.get("municipio"):
        pist.append(sin_acentos(x0["municipio"]).replace("l'", "").strip())
    trozos = [z for z in trozos if not _es_pista(z, cs)] or trozos
    entero = palabras(" ".join(trozos), ca)
    idioma = any(re.search(r"ingl|angl|bilingu|english", z) for z in pist)
    de_doble = len(trozos) >= 2 or bool(re.search(r"(?i)doble|simultane|programa conjunto|pceo", nombre))
    # «Economía-Derecho»: cada parte es un grado de la universidad → es un doble, no «Economía» con una variante
    grados = [c["palabras"] for c in cs if c["clase"] == "grado"]
    solo_doble = len(trozos) >= 2 and all(any(_parecido(palabras(z, ca), g) >= 0.75 for g in grados) for z in trozos)
    solo_doble = solo_doble or bool(re.search(r"(?i)simultane", nombre))  # «(simultaneïtat)»: doble en Cataluña
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
        if idioma and (c["idioma"] or "").startswith("Sí"):
            extra += 0.1
        if x0["lista"] == "final" and any(
                y.get("nota") and y["nota"] > 5 and igual_a_qedu(c["notas_qedu"].get(y["curso"]), y["nota"])
                for y in xs if y["cupo"] == "general" and y.get("convocatoria") in (None, "ordinaria")):
            extra += 0.2
        salida.append((s + extra, c, variante or ("idioma" if idioma else "")))
    return sorted(salida, key=lambda z: -z[0])


def unir(filas: list[dict], cands: dict[str, list[dict]]) -> Counter:
    """Pone `codigo_titulo` y `codigo_centro` (y cómo se unió) a cada fila que se puede unir con seguridad: el mejor
    candidato con parecido de al menos 0,8 y sin otro título a menos de 0,05."""
    resumen: Counter = Counter()
    por_oferta: dict[tuple, list[dict]] = defaultdict(list)
    for x in filas:
        por_oferta[(x["distrito"], x.get("universidad"), x["codigo_local"], x["titulacion"])].append(x)
    for (distrito, univ, _, nombre), xs in por_oferta.items():
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
        cerca = [(s, c, v) for s, c, v in puntos if s >= mejor - 0.05]
        if len({c["codigo"] for _, c, _ in cerca}) != 1 or mejor < 0.8:
            resumen["ambigua" if len({c["codigo"] for _, c, _ in cerca}) > 1 else "parecido_bajo"] += 1
            continue
        centros = {c["centro"] for _, c, _ in cerca}
        if len(centros) > 1 and not pistas(nombre):
            # sin campus ni centro en el nombre, el título se refiere a su centro propio (los adscritos se nombran)
            propios = [z for z in cerca if z[1]["propio"]]
            if len({z[1]["centro"] for z in propios}) == 1:
                cerca, centros = propios, {propios[0][1]["centro"]}
        _, c, variante = cerca[0]
        for x in xs:
            x["codigo_titulo"] = c["codigo"]
            x["codigo_centro"] = c["centro"] if len(centros) == 1 else None
            x["union"] = {"metodo": "nombre", "puntuacion": round(mejor, 2), "nombre_catalogo": c["nombre"],
                          "variante": variante or None}
        resumen["nombre" if len(centros) == 1 else "nombre_sin_centro"] += 1
    # el mismo código del distrito en otro curso, con un nombre parecido (renombrado, abreviado), es la misma oferta
    por_codigo: dict[tuple, list[list[dict]]] = defaultdict(list)
    for (distrito, univ, codigo, _), xs in por_oferta.items():
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
                "plazas": sum(x["plazas"] for x in xs) if all(x.get("plazas") for x in xs) else None}
            for k, xs in por.items()}


def historico(filas: list[dict], cands: dict[str, list[dict]]) -> list[dict]:
    """Por título y centro: la nota de corte del cupo general por curso (la menor de sus ofertas, como QEDU) y el
    contraste con QEDU en los cursos que se solapan. Si en alguno no coincide (con una nota por encima de 5,000, que
    es «entraron todos»), el histórico de ese título y centro no se publica (`publicable`: false). Si la nota no es
    la final (Cataluña da la de la primera asignación, que no se puede contrastar con la de QEDU), solo se publica
    si las plazas del distrito y las de QEDU coinciden en el mismo curso, y con su tipo de lista."""
    por_cod = {(c["codigo"], c["centro"]): c for cs in cands.values() for c in cs}
    por: dict[tuple, dict] = defaultdict(dict)
    for (tit, cen, curso), v in nota_del_titulo(filas).items():
        por[(tit, cen)][curso] = v
    salida = []
    for (tit, cen), cursos in sorted(por.items()):
        c = por_cod.get((tit, cen)) or {"notas_qedu": {}}
        contraste = Counter()
        for curso, v in cursos.items():
            q = c["notas_qedu"].get(curso)
            if q is not None and v["nota"] > 5 and v["lista"] == "final":
                contraste["igual" if igual_a_qedu(q, v["nota"]) else "distinta"] += 1
        finales = all(v["lista"] == "final" for v in cursos.values())
        # sin nota final que contrastar (Cataluña): vale si las plazas del distrito coinciden con las de QEDU en el
        # mismo curso, señal de que la oferta unida por el nombre es la misma
        plazas_iguales = [curso for curso, v in cursos.items() if v.get("plazas") is not None
                          and c.get("plazas_qedu", {}).get(curso) is not None
                          and abs(c["plazas_qedu"][curso] - v["plazas"]) < 0.5]
        if plazas_iguales:
            contraste["plazas_iguales"] = len(plazas_iguales)
        salida.append({"codigo_titulo": tit, "codigo_centro": cen, "distrito": next(iter(cursos.values()))["distrito"],
                       "cursos": {k: {"nota": v["nota"], "ofertas": v["ofertas"], "lista": v["lista"],
                                      "fuente": v["fuente"]} for k, v in sorted(cursos.items())},
                       "contraste_qedu": dict(contraste),
                       # una nota de primera asignación (Cataluña) no se puede contrastar con la final de QEDU: no se
                       # publica hasta tener otra comprobación
                       "publicable": not contraste.get("distinta") and (finales or bool(plazas_iguales)),
                       "lista": "final" if finales else next(iter(cursos.values()))["lista"]})
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
        igual = igual_a_qedu(c["notas_qedu"][curso], v["nota"])
        salida[v["distrito"]]["igual" if igual else "distinta"] += 1
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
