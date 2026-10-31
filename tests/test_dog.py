"""DOG (Galicia) con páginas reales del 29/10/2026: índice del boletín 207, secciones IV y VI y una disposición."""

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from motor.autonomicos import dog

FIX = Path(__file__).parent / "fixtures"
DIA = date(2026, 10, 29)


def _leer(nombre):
    return (FIX / nombre).read_bytes()


def test_indice_real():
    i = dog.parsear_indice(_leer("dog_indice_207.html").decode())
    assert i["numero"] == 207 and i["fecha"] == "2026-10-29"
    assert [s["titulo"] for s in i["secciones"]] == ["III. Otras disposiciones", "IV. Oposiciones y concursos",
                                                     "VI. Anuncios"]


def test_secciones_y_seleccion():
    filas = dog.parsear_seccion(_leer("dog_secciones2_20261029.html").decode(), DIA, 207)
    filas += dog.parsear_seccion(_leer("dog_secciones3_20261029.html").decode(), DIA, 207)
    assert len(filas) == 35
    assert filas[0]["organismo"] == "Consellería de Hacienda y Administración Pública" and filas[0]["pagina"] == "54277"
    emp = dog.seleccionar(filas)
    assert len(emp) == 12
    locales = [e for e in emp if e["ambito"] == "local"]
    assert {e["convocante"]["nombre"] for e in locales} == {"Sarria", "Vigo"}
    # Los anuncios urbanísticos o de biomasa de la sección VI no entran
    assert not any("biomasa" in e["titulo"] or "estudio de detalle" in e["titulo"] for e in emp)


def test_texto_sin_datos_personales():
    t = dog.texto_disposicion(_leer("dog_anuncio_G0597-231026-0002_gl.html"))
    assert t["texto"].startswith("Na sesión que tivo lugar o día 21 de outubro de 2026")
    assert "Xunta de Galicia. Información mantida" not in t["texto"]  # el pie de página no forma parte del texto


def _servidor(monkeypatch, paginas):
    def obtener(url, accept=None):
        if url in paginas:
            return SimpleNamespace(status=200, contenido=paginas[url], cabeceras={}, url=url)
        return SimpleNamespace(status=404, contenido=b"", cabeceras={}, url=url)
    monkeypatch.setattr(dog, "obtener", obtener)
    monkeypatch.setattr(dog.time, "sleep", lambda s: None)


def test_procesar_dia_y_numero_siguiente(tmp_path, monkeypatch):
    _servidor(monkeypatch, {
        dog.url_indice(DIA, 207): _leer("dog_indice_207.html"),
        dog.url_seccion(DIA, 2): _leer("dog_secciones2_20261029.html"),
        dog.url_seccion(DIA, 3): _leer("dog_secciones3_20261029.html"),
    })
    archivo = dog.Archivo(tmp_path / "archivo")
    # Se esperaba el 206 (p. ej., hubo un extraordinario): prueba 206 y 207
    inf = dog.procesar_dia(DIA, 206, tmp_path, archivo)
    assert inf["resultado"] == "ok" and inf["numero"] == 207 and inf["probados"] == [[206, 404], [207, 200]]
    assert inf["empleo_publico"] == 12 and len(dog.textos_pendientes(tmp_path)) == 12
    # Un día sin boletín
    inf = dog.procesar_dia(date(2026, 10, 30), 208, tmp_path, archivo)
    assert inf["resultado"] == "sin_boletin"


def test_ultimo_numero_desde_informes(tmp_path):
    dog.escribir_json(dog._ruta(tmp_path, "dias", date(2026, 10, 28), "json"), {"resultado": "ok", "numero": 206})
    assert dog.ultimo_numero(tmp_path, DIA) == (206, date(2026, 10, 28))
    assert dog.ultimo_numero(tmp_path, date(2026, 1, 1)) is None


def test_texto_de_las_paginas_antiguas():
    """Hasta 2023 la página del anuncio no tiene <main> y la navegación inferior es un div (sonda del 31/10/2026)."""
    from motor.autonomicos import dog
    h = ('<div class="dog-cabecera">DOG</div><div class="story"><p class="dog-base-sangria">Convocada la provisión de '
         'un puesto de trabajo.</p></div><div id="navegacionInferior"><a>Ir al siguiente</a></div>'
         '<div id="footer">Xunta de Galicia</div>').encode()
    t = dog.texto_disposicion(h)
    assert t["texto"].startswith("Convocada la provisión") and "siguiente" not in t["texto"]
