"""Lectura de una página generada: lo que el control necesita saber de ella, tal como la recibe un robot que no
ejecuta JavaScript.

Contrato con el generador (detalle en `docs/encargo-seo.md`):
- un solo `<main>` con el contenido principal;
- cada dato clave en un elemento con `data-dato="clave"`; el valor, en el propio elemento o en un hijo con
  `data-valor`; la fuente, en un enlace `<a data-fuente href="…">` dentro del elemento o en una nota a la que
  apunta `data-fuente="id-de-la-nota"`; la fecha, en un `<time datetime="AAAA-MM-DD">` del elemento o de la nota;
- migas de pan en `<nav aria-label="Migas de pan">` (una por camino);
- toda ventana o diálogo sale en el HTML con el atributo `hidden` y solo se abre si el usuario lo pide.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import lxml.html
from lxml import etree

ESPACIOS = re.compile(r"\s+")
NO_VISIBLE = {"script", "style", "template", "noscript", "head", "title", "meta", "link"}
OCULTO_ESTILO = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden", re.I)


def limpiar(texto: str | None) -> str:
    return ESPACIOS.sub(" ", texto or "").strip()


def oculto(el) -> bool:
    """El elemento o algún antecesor no se ve sin CSS externo ni JavaScript."""
    while el is not None:
        if not isinstance(el.tag, str):
            el = el.getparent()
            continue
        if el.tag in NO_VISIBLE or el.get("hidden") is not None or el.get("aria-hidden") == "true":
            return True
        if OCULTO_ESTILO.search(el.get("style") or ""):
            return True
        el = el.getparent()
    return False


def texto_visible(el) -> str:
    """Texto que se ve del elemento (sin scripts, plantillas ni elementos ocultos)."""
    if el is None:
        return ""
    partes: list[str] = []

    def recorrer(nodo):
        if not isinstance(nodo.tag, str):  # comentarios, instrucciones
            if nodo.tail:
                partes.append(nodo.tail)
            return
        visible = not (nodo.tag in NO_VISIBLE or nodo.get("hidden") is not None
                       or OCULTO_ESTILO.search(nodo.get("style") or ""))
        if visible:
            if nodo.text:
                partes.append(nodo.text)
            for hijo in nodo:
                recorrer(hijo)
        if nodo.tail:
            partes.append(nodo.tail)

    if el.text and not oculto(el):
        partes.append(el.text)
    for hijo in el:
        recorrer(hijo)
    return limpiar(" ".join(partes))


@dataclass
class Dato:
    clave: str
    valor: str
    fuente: str | None
    fecha: str | None
    visible: bool
    fuente_visible: bool
    fecha_visible: bool
    sin_fragmento: bool = False


@dataclass
class Enlace:
    href: str
    texto: str
    rel: str
    en_main: bool


@dataclass
class Marcado:
    texto: str
    datos: object | None
    error: str | None


@dataclass
class Pagina:
    ruta: str
    archivo: Path
    titulos: list[str]
    descripciones: list[str]
    canonicas: list[str]
    robots: list[str]
    viewport: bool
    lang: str
    mains: int
    texto_main: str
    texto: str
    enlaces: list[Enlace]
    sin_href: int
    datos: list[Dato]
    marcados: list[Marcado]
    imagenes: list[dict]
    ventanas: list[str]
    migas: list[list[str]]
    ids: set[str]
    hreflang: int
    bytes: int = 0
    iconos: list[str] = field(default_factory=list)
    recursos: list[str] = field(default_factory=list)  # CSS, JS e imágenes que carga
    actualizado: str | None = None  # fecha del elemento data-actualizado
    texto_huella: str = ""  # texto de <main> sin la fecha de «actualizado»
    tipo_html: str | None = None  # <main data-tipo>
    arbol: object = field(repr=False, default=None)  # solo si se pide (con 100.000 páginas no cabe en memoria)

    @property
    def directivas(self) -> set[str]:
        return {d.strip().lower() for r in self.robots for d in r.split(",") if d.strip()}

    @property
    def indexable(self) -> bool:
        return not ({"noindex", "none"} & self.directivas)


def _ruta_de(archivo: Path, raiz: Path) -> str:
    rel = archivo.relative_to(raiz).as_posix()
    if rel == "index.html":
        return "/"
    if rel.endswith("/index.html"):
        return "/" + rel[: -len("index.html")]
    return "/" + rel


def _fuente_y_fecha(el, por_id) -> tuple[str | None, str | None, bool, bool]:
    enlace = el.xpath(".//a[@data-fuente][@href]")
    tiempo = el.xpath(".//time[@datetime]")
    nota = por_id.get((el.get("data-fuente") or "").lstrip("#"))
    if nota is not None:
        enlace = enlace or nota.xpath(".//a[@href]")
        tiempo = tiempo or nota.xpath(".//time[@datetime]")
    fuente = enlace[0].get("href") if enlace else None
    fecha = tiempo[0].get("datetime") if tiempo else None
    return (fuente, fecha, bool(enlace) and not oculto(enlace[0]), bool(tiempo) and not oculto(tiempo[0]))


def leer(archivo: Path, raiz: Path, conservar_arbol: bool = False) -> Pagina:
    contenido = archivo.read_bytes()
    arbol = lxml.html.document_fromstring(contenido)
    head = arbol.find("head")
    metas = head.findall("meta") if head is not None else []
    # Google respeta las metaetiquetas de robots también en el cuerpo (desde marzo de 2026): se leen todas.
    metas_robots = arbol.xpath("//meta[@name]")

    def meta(nombre: str, todas: bool = False) -> list[str]:
        return [m.get("content", "") for m in (metas_robots if todas else metas)
                if (m.get("name") or "").lower() == nombre]

    por_id = {e.get("id"): e for e in arbol.xpath("//*[@id]")}
    mains = arbol.xpath("//main")
    main = mains[0] if mains else None
    body = arbol.find("body")

    enlaces = []
    for a in arbol.xpath("//a[@href]"):
        en_main = main is not None and any(x is main for x in a.iterancestors())
        enlaces.append(Enlace(a.get("href").strip(), limpiar(a.text_content()), (a.get("rel") or "").lower(),
                              en_main))
    sin_href = len(arbol.xpath("//a[not(@href)][@onclick] | //*[not(self::a) and not(self::button)][@onclick]"
                               "[contains(@onclick,'location')]"))

    datos = []
    for el in arbol.xpath("//*[@data-dato]"):
        valor_el = el.xpath(".//*[@data-valor]")
        valor = texto_visible(valor_el[0]) if valor_el else texto_visible(el)
        fuente, fecha, f_vis, t_vis = _fuente_y_fecha(el, por_id)
        sin_fragmento = bool(el.xpath("ancestor-or-self::*[@data-nosnippet]"))
        datos.append(Dato(el.get("data-dato"), valor, fuente, fecha, not oculto(el), f_vis, t_vis, sin_fragmento))

    marcados = []
    for s in arbol.xpath("//script[@type='application/ld+json']"):
        texto = s.text or ""
        try:
            marcados.append(Marcado(texto, json.loads(texto), None))
        except json.JSONDecodeError as e:
            marcados.append(Marcado(texto, None, f"JSON no válido: {e.msg} (línea {e.lineno})"))

    ventanas = []
    for el in arbol.xpath("//dialog[@open] | //*[@aria-modal='true'] | //*[@role='dialog' or @role='alertdialog']"):
        if el.get("hidden") is None and not (el.tag == "dialog" and el.get("open") is None):
            ventanas.append(f"<{el.tag}> {etree.tostring(el, encoding=str)[:80]}")

    migas = []
    for nav in arbol.xpath("//nav[@aria-label]"):
        if re.search(r"miga|breadcrumb", nav.get("aria-label"), re.I):
            migas.append([limpiar(a.text_content()) for a in nav.xpath(".//a")])

    actualizado = arbol.xpath("//*[@data-actualizado]//time[@datetime] | //time[@data-actualizado][@datetime]")
    texto_huella = ""
    if main is not None:
        copia = copy.deepcopy(main)
        for el in copia.xpath(".//*[@data-actualizado]"):
            el.drop_tree()  # conserva el texto que le sigue
        texto_huella = texto_visible(copia)

    html = arbol.getroottree().getroot()
    return Pagina(
        ruta=_ruta_de(archivo, raiz),
        archivo=archivo,
        titulos=[limpiar(t.text_content()) for t in arbol.xpath("//title")],
        descripciones=[limpiar(d) for d in meta("description")],
        canonicas=[(l.get("href") or "").strip() for l in arbol.xpath("//link[@rel]")
                   if "canonical" in (l.get("rel") or "").lower().split()],
        robots=meta("robots", True) + meta("googlebot", True),
        viewport=bool(meta("viewport")),
        lang=(html.get("lang") or "").lower(),
        mains=len(mains),
        texto_main=texto_visible(main),
        texto=texto_visible(body),
        enlaces=enlaces,
        sin_href=sin_href,
        datos=datos,
        marcados=marcados,
        imagenes=[dict(i.attrib) for i in arbol.xpath("//img")],
        ventanas=ventanas,
        migas=migas,
        ids=set(por_id),
        hreflang=len(arbol.xpath("//link[@hreflang]")),
        bytes=len(contenido),
        recursos=[u for u in arbol.xpath("//link[@rel='stylesheet']/@href | //script/@src | //img/@src")],
        actualizado=actualizado[0].get("datetime")[:10] if actualizado else None,
        texto_huella=texto_huella,
        tipo_html=main.get("data-tipo") if main is not None else None,
        iconos=[l.get("href", "") for l in arbol.xpath("//link[@rel]")
                if {"icon", "shortcut"} & set((l.get("rel") or "").lower().split())],
        arbol=arbol if conservar_arbol else None,
    )
