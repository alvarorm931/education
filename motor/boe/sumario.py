"""Lectura del sumario diario del BOE en XML.

Estructura documentada (APIsumarioBOE.pdf):
response > status(code, text) > data > sumario > metadatos(publicacion, fecha_publicacion)
  diario[numero] > sumario_diario(identificador, url_pdf)
                 > seccion[codigo, nombre] > departamento[codigo, nombre]
                     > epigrafe[nombre] > item   (secciones 1, 2A, 2B, 3 y 5)
                     > item                      (directamente bajo departamento)
item: identificador, control, titulo, url_pdf[szBytes, szKBytes, pagina_inicial, pagina_final], url_html, url_xml
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date

URL_SUMARIO = "https://boe.es/datosabiertos/api/boe/sumario/{fecha}"
ACCEPT = "application/xml"


def url_sumario(fecha: date) -> str:
    return URL_SUMARIO.format(fecha=f"{fecha:%Y%m%d}")


class ErrorSumario(Exception):
    pass


@dataclass
class Sumario:
    fecha_publicacion: str
    diarios: list[dict] = field(default_factory=list)
    items: list[dict] = field(default_factory=list)


def _texto(nodo: ET.Element | None, etiqueta: str) -> str | None:
    if nodo is None:
        return None
    hijo = nodo.find(etiqueta)
    if hijo is None or hijo.text is None:
        return None
    return " ".join(hijo.text.split())


def _item(nodo: ET.Element, diario: str, seccion: ET.Element, departamento: ET.Element, epigrafe: str | None) -> dict:
    pdf = nodo.find("url_pdf")
    return {
        "identificador": _texto(nodo, "identificador"),
        "control": _texto(nodo, "control"),
        "titulo": _texto(nodo, "titulo"),
        "diario": diario,
        "seccion_codigo": seccion.get("codigo"),
        "seccion": seccion.get("nombre"),
        "departamento_codigo": departamento.get("codigo"),
        "departamento": departamento.get("nombre"),
        "epigrafe": epigrafe,
        "url_pdf": (pdf.text or "").strip() if pdf is not None else None,
        "pagina_inicial": pdf.get("pagina_inicial") if pdf is not None else None,
        "pagina_final": pdf.get("pagina_final") if pdf is not None else None,
        "url_html": _texto(nodo, "url_html"),
        "url_xml": _texto(nodo, "url_xml"),
    }


def parsear(xml: bytes) -> Sumario:
    try:
        raiz = ET.fromstring(xml)
    except ET.ParseError as e:
        raise ErrorSumario(f"XML no válido: {e}") from e

    codigo = _texto(raiz.find("status"), "code")
    if codigo != "200":
        raise ErrorSumario(f"Estado {codigo}: {_texto(raiz.find('status'), 'text')}")

    sumario = raiz.find("data/sumario")
    if sumario is None:
        raise ErrorSumario("Falta data/sumario: posible cambio de formato")

    resultado = Sumario(fecha_publicacion=_texto(sumario.find("metadatos"), "fecha_publicacion") or "")
    for diario in sumario.findall("diario"):
        numero = diario.get("numero") or ""
        resultado.diarios.append({
            "numero": numero,
            "identificador": _texto(diario.find("sumario_diario"), "identificador"),
        })
        for seccion in diario.findall("seccion"):
            for dep in seccion.findall("departamento"):
                for hijo in dep:
                    if hijo.tag == "epigrafe":
                        for it in hijo.findall("item"):
                            resultado.items.append(_item(it, numero, seccion, dep, hijo.get("nombre")))
                    elif hijo.tag == "item":
                        resultado.items.append(_item(hijo, numero, seccion, dep, None))
    return resultado
