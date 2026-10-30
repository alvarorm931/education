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
import sys
from collections import Counter, defaultdict
from pathlib import Path

from motor.autonomicos.comun import escribir_jsonl, leer_jsonl
from motor.boe.extraer import aplicar_plazas
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
}
PROVINCIALES = {"bopb", "bopalicante", "bopvalencia", "bopt", "bopciudadreal", "bopgranada", "bopsevilla", "bophuesca",
                "boptenerife", "bopcordoba", "bopcoruna", "boppontevedra", "bopavila", "bopbadajoz", "bopzamora", "boptoledo", "bopburgos", "bopalava", "bopsalamanca", "bopalbacete", "bopjaen", "bopzaragoza", "bopgipuzkoa", "bopbizkaia", "boplugo"}
CON_PLAZO = {"convocatoria", "bases", "modificacion", "correccion", "otro", None}


def _base(raiz: Path, fuente: str) -> Path:
    return raiz / "datos" / ("provinciales" if fuente in PROVINCIALES else "autonomicos") / fuente


def ruta_texto(raiz: Path, fuente: str, x: dict) -> Path:
    return _base(raiz, fuente) / "textos" / x["fecha"][:4] / x["fecha"][5:7] / f"{x['id']}.json"


def texto_de(raiz: Path, fuente: str, x: dict) -> str | None:
    if x.get("texto") is not None:  # BOJA trae el texto en el propio registro
        return x["texto"]
    r = ruta_texto(raiz, fuente, x)
    if r.exists():
        return json.loads(r.read_text(encoding="utf-8")).get("texto")
    return None


def recuento_de(raiz: Path, fuente: str, x: dict) -> int | None:
    """En las listas de personas solo se guarda cuántas líneas traen un documento de identidad."""
    r = ruta_texto(raiz, fuente, x)
    if r.exists():
        return json.loads(r.read_text(encoding="utf-8")).get("lineas_con_documento_de_identidad")
    return None


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
        "organismo": x.get("organismo"),
        "seccion": " / ".join(p for p in (x.get("seccion"), x.get("subseccion") or x.get("apartado")) if p) or None,
        "ambito": x.get("ambito"),
        "convocante": x.get("convocante"),
        "tipo_acto": x.get("tipo_acto"),
        "alcance": x.get("alcance"),
        "modalidad": x.get("modalidad"),
        "tiene_texto": texto is not None,
        "extraccion": "titulo",
        "pendiente": [],
    }
    if recuento is not None:
        acto["personas_en_listas"] = recuento
        return acto
    if texto is None:
        acto["pendiente"].append("texto")
        return acto
    if acto["tipo_acto"] in CON_PLAZO:
        plazo = extraer_plazo(texto, x["fecha"], nombres)
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
                actos.append(construir_acto(fuente, x, texto_de(raiz, fuente, x), recuento_de(raiz, fuente, x)))
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
        for mes, lista in sorted(por_mes.items()):
            escribir_jsonl(destino / mes[:4] / f"{mes[5:]}.jsonl", sorted(lista, key=lambda x: (x["fecha"], x["id"])))
        c = Counter(x["extraccion"] for x in actos)
        con_fin = sum(1 for x in actos if (x.get("plazo") or {}).get("fin_estimado"))
        print(f"{FUENTES[fuente][0]}: {len(actos)} actos, {sum(x['tiene_texto'] for x in actos)} con texto, "
              f"{con_fin} con fecha de fin de plazo; {dict(c)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
