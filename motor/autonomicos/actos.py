"""Actos de oposiciones de los boletines autonómicos y provinciales, con el mismo esquema que los del BOE.

Uso:
  python -m motor.autonomicos.actos --salida ruta/

Lee datos/autonomicos/{fuente}/oposiciones (o datos/provinciales/{fuente}/ para los boletines de provincia) y sus
textos y regenera datos/autonomicos/actos/{fuente}/AAAA/MM.jsonl.
Es reproducible: si mejora la extracción, se vuelve a ejecutar sobre todo el histórico.

Cada acto lleva: identificador con la fuente («bocyl:BOCYL-D-28102026-209-5»), fecha, boletín, título, organismo,
ámbito, convocante, tipo de acto, alcance, modalidad, plazo (si el texto lo fija) y lo que queda pendiente.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from motor.autonomicos.comun import clasificar, convocante_de_organismo, escribir_jsonl, leer_jsonl
from motor.boe.clasificar import normalizar
from motor.boe.extraer import aplicar_plazas
from motor.boe.clasificar import alcance_vigente
from motor.catalogo.territorio import comunidad_codigo
from motor.union import POSTERIORES, puesto, puesto_en_texto
from motor.extraccion.citas import citas, sedes
from motor.extraccion.plazo import VERSION as VERSION_PLAZO, extraer_plazo

# fuente -> (siglas, nombres con los que el propio boletín se cita en los textos)
FUENTES: dict[str, tuple[str, tuple[str, ...]]] = {
    "boja": ("BOJA", ("Boletín Oficial de la Junta de Andalucía",)),
    "bocm": ("BOCM", ("Boletín Oficial de la Comunidad de Madrid",)),
    "bocyl": ("BOCYL", ("Boletín Oficial de Castilla y León",)),
    "dogv": ("DOGV", ("Diari Oficial de la Generalitat Valenciana", "Diario Oficial de la Generalitat Valenciana",
                      "Diari Oficial de la Comunitat Valenciana", "Diario Oficial de la Comunitat Valenciana")),
    "dog": ("DOG", ("Diario Oficial de Galicia",)),
    "boa": ("BOA", ("Boletín Oficial de Aragón",)),
    "doe": ("DOE", ("Diario Oficial de Extremadura",)),
    "borm": ("BORM", ("Boletín Oficial de la Región de Murcia",)),
    "boc": ("BOC", ("Boletín Oficial de Canarias",)),
    "docm": ("DOCM", ("Diario Oficial de Castilla-La Mancha",)),
    "bome": ("BOME", ("Boletín Oficial de la Ciudad de Melilla", "Boletín Oficial de la Ciudad Autónoma de Melilla",
                      "BOME")),
    "bocce": ("BOCCE", ("Boletín Oficial de la Ciudad de Ceuta", "Boletín Oficial de la Ciudad Autónoma de Ceuta",
                        "BOCCE")),
    "bopv": ("BOPV", ("Boletín Oficial del País Vasco", "Boletín Oficial del Pais Vasco")),
    "boib": ("BOIB", ("Butlletí Oficial de les Illes Balears", "Boletín Oficial de las Illes Balears",
                      "Boletín Oficial de las Islas Baleares")),
    "bopa": ("BOPA", ("Boletín Oficial del Principado de Asturias",)),
    "bon": ("BON", ("Boletín Oficial de Navarra",)),
    "bocant": ("BOC-CANT", ("Boletín Oficial de Cantabria",)),
    "bor": ("BOR", ("Boletín Oficial de La Rioja",)),
    "dogc": ("DOGC", ("Diari Oficial de la Generalitat de Catalunya", "Diario Oficial de la Generalitat de Cataluña",
                      "Diario Oficial de la Generalidad de Cataluña")),
    "bopb": ("BOPB", ("Butlletí Oficial de la Província de Barcelona", "Boletín Oficial de la Provincia de Barcelona",
                      "BOPB")),
    "bopalicante": ("BOP-ALICANTE", ("Boletín Oficial de la Provincia de Alicante",
                                     "Butlletí Oficial de la Província d'Alacant",
                                     "Butlletí Oficial de la Província d’Alacant")),
    "bopvalencia": ("BOP-VALENCIA", ("Butlletí Oficial de la Província de València",
                                     "Boletín Oficial de la Provincia de Valencia")),
    "bopt": ("BOPT", ("Butlletí Oficial de la Província de Tarragona", "Boletín Oficial de la Provincia de Tarragona",
                      "BOPT")),
    "bopciudadreal": ("BOP-CIUDADREAL", ("Boletín Oficial de la Provincia de Ciudad Real",)),
    "bopgranada": ("BOP-GRANADA", ("Boletín Oficial de la Provincia de Granada",)),
    "bopsevilla": ("BOP-SEVILLA", ("Boletín Oficial de la Provincia de Sevilla",)),
    "bophuesca": ("BOP-HUESCA", ("Boletín Oficial de la Provincia de Huesca",)),
    "boptenerife": ("BOP-TENERIFE", ("Boletín Oficial de la Provincia de Santa Cruz de Tenerife",)),
    "bopcordoba": ("BOP-CORDOBA", ("Boletín Oficial de la Provincia de Córdoba",)),
    "boppontevedra": ("BOP-PONTEVEDRA", ("Boletín Oficial de la Provincia de Pontevedra",)),
    "bopcoruna": ("BOP-CORUNA", ("Boletín Oficial de la Provincia de A Coruña", "Boletín Oficial da Provincia da Coruña")),
    "bopavila": ("BOP-AVILA", ("Boletín Oficial de la Provincia de Ávila",)),
    "bopbadajoz": ("BOP-BADAJOZ", ("Boletín Oficial de la Provincia de Badajoz",)),
    "bopzamora": ("BOP-ZAMORA", ("Boletín Oficial de la Provincia de Zamora",)),
    "boptoledo": ("BOP-TOLEDO", ("Boletín Oficial de la Provincia de Toledo",)),
    "bopburgos": ("BOP-BURGOS", ("Boletín Oficial de la Provincia de Burgos",)),
    "bopalava": ("BOTHA", ("Boletín Oficial del Territorio Histórico de Álava",)),
    "bopsalamanca": ("BOP-SALAMANCA", ("Boletín Oficial de la Provincia de Salamanca",)),
    "bopalbacete": ("BOP-ALBACETE", ("Boletín Oficial de la Provincia de Albacete",)),
    "bopjaen": ("BOP-JAEN", ("Boletín Oficial de la Provincia de Jaén",)),
    "bopzaragoza": ("BOP-ZARAGOZA", ("Boletín Oficial de la Provincia de Zaragoza",)),
    "bopgipuzkoa": ("BOG", ("Boletín Oficial de Gipuzkoa",)),
    "bopbizkaia": ("BOB", ("Boletín Oficial de Bizkaia",)),
    "boplugo": ("BOP-LUGO", ("Boletín Oficial de la Provincia de Lugo",)),
    "bophuelva": ("BOP-HUELVA", ("Boletín Oficial de la Provincia de Huelva",)),
    "boplaspalmas": ("BOP-LASPALMAS", ("Boletín Oficial de la Provincia de Las Palmas",)),
    "bopvalladolid": ("BOP-VALLADOLID", ("Boletín Oficial de la Provincia de Valladolid",)),
    "bopcaceres": ("BOP-CACERES", ("Boletín Oficial de la Provincia de Cáceres",)),
    "bopguadalajara": ("BOP-GUADALAJARA", ("Boletín Oficial de la Provincia de Guadalajara",)),
    "bopgirona": ("BOP-GIRONA", ("Boletín Oficial de la Provincia de Girona",)),
    "bopourense": ("BOP-OURENSE", ("Boletín Oficial de la Provincia de Ourense",)),
    "boplleida": ("BOP-LLEIDA", ("Boletín Oficial de la Provincia de Lleida",)),
    "boppalencia": ("BOP-PALENCIA", ("Boletín Oficial de la Provincia de Palencia",)),
    "bopsoria": ("BOP-SORIA", ("Boletín Oficial de la Provincia de Soria",)),
    "bopteruel": ("BOP-TERUEL", ("Boletín Oficial de la Provincia de Teruel",)),
    "bopcastellon": ("BOP-CASTELLON", ("Boletín Oficial de la Provincia de Castellón",)),
    "bopleon": ("BOP-LEON", ("Boletín Oficial de la Provincia de León",)),
    "bopcadiz": ("BOP-CADIZ", ("Boletín Oficial de la Provincia de Cádiz",)),
}
PROVINCIALES = {"bopb", "bopalicante", "bopvalencia", "bopt", "bopciudadreal", "bopgranada", "bopsevilla", "bophuesca",
                "boptenerife", "bopcordoba", "bopcoruna", "boppontevedra", "bopavila", "bopbadajoz", "bopzamora", "boptoledo", "bopburgos", "bopalava", "bopsalamanca", "bopalbacete", "bopjaen", "bopzaragoza", "bopgipuzkoa", "bopbizkaia", "boplugo", "bophuelva", "boplaspalmas", "bopvalladolid", "bopcaceres", "bopguadalajara", "bopgirona", "bopourense", "boplleida", "boppalencia", "bopsoria", "bopteruel", "bopcastellon", "bopleon", "bopcadiz"}
CON_PLAZO = {"convocatoria", "bases", "modificacion", "correccion", "otro", None}


def _base(raiz: Path, fuente: str) -> Path:
    return raiz / "datos" / ("provinciales" if fuente in PROVINCIALES else "autonomicos") / fuente


def ruta_texto(raiz: Path, fuente: str, x: dict) -> Path:
    return _base(raiz, fuente) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"


def _guardado(raiz: Path, fuente: str, x: dict) -> dict:
    """El fichero de texto guardado del anuncio; {} si no está o está vacío o roto (un fichero de 0 bytes de
    bopsevilla, 30/10/2026, paraba todo el paso de actos): se trata como sin texto y se vuelve a pedir."""
    r = ruta_texto(raiz, fuente, x)
    try:
        return json.loads(r.read_text(encoding="utf-8")) if r.exists() else {}
    except (ValueError, UnicodeDecodeError):
        print(f"Aviso: texto guardado ilegible, se ignora: {r}", file=sys.stderr)
        return {}


def texto_de(raiz: Path, fuente: str, x: dict) -> str | None:
    if x.get("texto") is not None:  # BOJA trae el texto en el propio registro
        return x["texto"]
    return _guardado(raiz, fuente, x).get("texto")


def recuento_de(raiz: Path, fuente: str, x: dict) -> int | None:
    """En las listas de personas solo se guarda cuántas líneas traen un documento de identidad."""
    return _guardado(raiz, fuente, x).get("lineas_con_documento_de_identidad")


def citas_guardadas(raiz: Path, fuente: str, x: dict) -> list[dict] | None:
    """Citas a boletines guardadas al descargar una lista de personas (de su texto no se guarda nada más)."""
    return _guardado(raiz, fuente, x).get("citas")


def convocante_local(x: dict) -> dict | None:
    """Convocante de lo local cuando el conector no lo ha guardado (BOCM: «Griñón. Personal. Convocatoria…», con el
    municipio en el organismo o al principio del título y «AYUNTAMIENTOS» en la sección)."""
    if x.get("ambito") != "local":
        return None
    nombre = x.get("organismo") or (x.get("titulo") or "").split(". ")[0]
    if not nombre or len(nombre) > 60 or len(nombre.split()) > 7:
        return None
    sec = normalizar(" ".join(str(x.get(k) or "") for k in ("seccion", "subseccion", "apartado")))
    if "ayuntamiento" in sec or "concello" in sec or "ajuntament" in sec:
        return convocante_de_organismo(f"AYUNTAMIENTO DE {nombre}")
    return convocante_de_organismo(nombre)


# Títulos que no dicen qué es el anuncio («Getafe. Ofertas de empleo. Proceso selectivo», «… Convocatoria proceso
# selectivo»: unos 6.600 del BOCM desde 2022). Todos salían como convocatoria, y uno de cada cuatro con texto es una
# lista, un tribunal o unos aprobados: un proceso de más y un acto sin unir a su convocatoria. El tipo sale entonces
# del comienzo del texto, tras el título (31/10/2026).
RE_TITULO_GENERICO = re.compile(
    r"(?i)\bOfertas de empleo\.\s*(?:Convocatorias?\s+)?(?:procesos?\s+selectivos?|convocatorias?)\.?\s*$")


def tipo_por_texto(titulo: str, texto: str) -> str | None:
    """Tipo de acto que dice el comienzo del texto de un anuncio con título genérico, si es de los posteriores a la
    convocatoria (listas, tribunal, aprobados, nombramientos…); None si no lo dice o es una convocatoria."""
    plano = " ".join((texto or "").split())
    i = plano.find(titulo)
    resto = plano[i + len(titulo):] if i >= 0 else plano
    tipo = clasificar(resto[:350])["tipo_acto"] if resto.strip() else None
    inicio = resto[:250]
    # Solo lo que el comienzo dice con claridad (muestra del BOCM, 31/10/2026): «aprobadas las bases», «se convocan
    # cuatro plazas… aprobado» o «bolsa para la contratación o nombramiento de interinos» no son aprobados ni
    # nombramientos, y unas bases que hablan de su corrección más abajo no son una corrección
    if tipo == "aprobados" and not RE_APROBADOS.search(inicio):
        return None
    if tipo == "nombramiento" and (not RE_NOMBRA.search(inicio) or re.search(r"(?i)\bbolsa\b", inicio)):
        return None
    if tipo in ("correccion", "modificacion") and not re.search(r"(?i)correcci|rectificaci|modific", resto[:150]):
        return None
    if tipo in ("desierta",) and re.search(r"(?i)\bbases\b", inicio):
        return None
    return tipo if tipo in POSTERIORES and tipo != "otro" else None


RE_APROBADOS = re.compile(r"(?i)(?:relaci[oó]n|lista|listado)\s+(?:definitiva\s+|provisional\s+)?de\s+(?:las\s+)?(?:personas\s+)?"
                          r"(?:aspirantes\s+)?aprobad|han\s+superado|propuesta\s+de\s+nombramiento|puntuaci[oó]n(?:es)?\s+final")
RE_NOMBRA = re.compile(r"(?i)\bse\s+nombra\b|\bnombrar\s+(?:a|como)\b|nombramiento\s+(?:como|de)\s+(?:personal\s+)?funcionari|"
                       r"\bha\s+sido\s+nombrad|\btoma\s+de\s+posesi")


def construir_acto(fuente: str, x: dict, texto: str | None, recuento: int | None = None) -> dict:
    siglas, nombres = FUENTES[fuente]
    acto = {
        "id": f"{fuente}:{x['id']}",
        "fecha": x["fecha"],
        "fuente": siglas,
        "boletin": x.get("boletin"),
        "url": x.get("url_html") or x.get("url_pdf"),
        "url_pdf": x.get("url_pdf"),
        "titulo": x.get("titulo"),
        # «entidad» en los provinciales (BOB: «Departamento de Administración Pública…»): sin ella, lo foral o
        # provincial no tenía clave de convocante y no se unía a nada
        "organismo": x.get("organismo") or (x.get("entidad") if not x.get("convocante") else None),
        "seccion": " / ".join(p for p in (x.get("seccion"), x.get("subseccion") or x.get("apartado")) if p) or None,
        "ambito": x.get("ambito"),
        "convocante": x.get("convocante") or convocante_local(x),
        # Con las reglas vigentes (motor/boe/clasificar.py), no con las del día de la captura: así una mejora de
        # las reglas se aplica a todo el histórico sin volver a seleccionar
        "tipo_acto": clasificar(x.get("titulo") or "")["tipo_acto"] if x.get("titulo") else x.get("tipo_acto"),
        "alcance": x.get("alcance"),
        "modalidad": x.get("modalidad"),
        "tiene_texto": texto is not None,
        "extraccion": "titulo",
        "pendiente": [],
    }
    if (texto and acto["tipo_acto"] in ("convocatoria", "otro") and RE_TITULO_GENERICO.search(acto["titulo"] or "")
            and (t := tipo_por_texto(acto["titulo"], texto))):
        acto["tipo_acto"], acto["tipo_por_texto"] = t, True
    acto["alcance"] = alcance_vigente(acto["titulo"], acto["tipo_acto"], acto["modalidad"], acto["alcance"])
    if recuento is not None:
        acto["personas_en_listas"] = recuento
        return acto
    if texto is not None and (c := citas(texto)):
        acto["citas"] = c
    if texto is not None and (s := sedes(texto)):
        acto["sedes"] = s
    if texto is None:
        acto["pendiente"].append("texto")
        return acto
    if acto["tipo_acto"] in POSTERIORES and not puesto(acto["titulo"]) and (q := puesto_en_texto(texto)):
        acto["puesto_texto"] = q  # para unirlo a su proceso (motor/union.py)
    if acto["tipo_acto"] in CON_PLAZO:
        plazo = extraer_plazo(texto, x["fecha"], nombres, comunidad_codigo(acto["convocante"], siglas, nombres))
        if plazo:
            acto["plazo"] = plazo
            acto["extraccion"] = VERSION_PLAZO
        if not plazo or not plazo.get("fin_estimado"):
            acto["pendiente"].append("plazo")
        aplicar_plazas(acto, texto)
    acto["pendiente"].append("extraccion_ia")
    return acto


def actos_de_fuente(raiz: Path, fuente: str) -> list[dict]:
    actos = []
    for f in sorted((_base(raiz, fuente) / "oposiciones").rglob("*.jsonl")):
        for x in leer_jsonl(f):
            if x.get("id") and x.get("fecha"):
                acto = construir_acto(fuente, x, texto_de(raiz, fuente, x), recuento_de(raiz, fuente, x))
                if "personas_en_listas" in acto and (c := citas_guardadas(raiz, fuente, x)):
                    acto["citas"] = c
                actos.append(acto)
    return actos


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    a = p.parse_args(argv)
    for fuente in FUENTES:
        actos = actos_de_fuente(a.salida, fuente)
        if not actos:
            continue
        por_mes: dict[str, list[dict]] = defaultdict(list)
        for x in actos:
            por_mes[x["fecha"][:7]].append(x)
        destino = a.salida / "datos" / "autonomicos" / "actos" / fuente
        escritos = set()
        for mes, lista in sorted(por_mes.items()):
            ruta = destino / mes[:4] / f"{mes[5:]}.jsonl"
            escribir_jsonl(ruta, sorted(lista, key=lambda x: (x["fecha"], x["id"])))
            escritos.add(ruta)
        # Los actos son derivados: un mes que ya no tiene anuncios (el «8202» de Lugo, movido a su fecha) se borra
        for viejo in destino.glob("*/*.jsonl"):
            if viejo not in escritos:
                viejo.unlink()
        for carpeta in destino.iterdir():
            if carpeta.is_dir() and not any(carpeta.iterdir()):
                carpeta.rmdir()
        c = Counter(x["extraccion"] for x in actos)
        con_fin = sum(1 for x in actos if (x.get("plazo") or {}).get("fin_estimado"))
        print(f"{FUENTES[fuente][0]}: {len(actos)} actos, {sum(x['tiene_texto'] for x in actos)} con texto, "
              f"{con_fin} con fecha de fin de plazo; {dict(c)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
