"""BOC (Canarias) con páginas reales: índice anual 2026, boletines 209 y 210 de 2026 y 1 de 2022, y una disposición."""

from pathlib import Path
from types import SimpleNamespace

from motor.autonomicos import boc

FIX = Path(__file__).parent / "fixtures"


def _leer(nombre):
    return (FIX / nombre).read_text(encoding="utf-8")


def test_indice_anual():
    lista = boc.boletines_del_anio(_leer("boc_2026_indice.html"))
    assert len(lista) == 217 and lista[0] == (1, "2026-01-02") and lista[-1] == (217, "2026-10-29")
    assert dict(lista)[210] == "2026-10-21"


def test_boletin_2026_secciones_y_seleccion():
    html = _leer("boc_2026_210.html")
    assert boc.cabecera(html) == (210, "2026-10-21")
    filas = boc.parsear_boletin(html, 2026, 210, "2026-10-21")
    assert len(filas) == 19
    f = filas[0]
    assert f["id"] == "BOC-A-2026-210-3613" and f["seccion"] == "II. Autoridades y personal"
    assert f["subseccion"] == "Nombramientos, situaciones e incidencias"
    assert f["url_html"] == "https://www.gobiernodecanarias.org/boc/2026/210/3613.html"
    assert f["url_pdf"] == "https://sede.gobiernodecanarias.org/boc/boc-a-2026-210-3613.pdf"
    emp = boc.seleccionar(filas)
    assert [e["id"][-4:] for e in emp] == ["3614", "3619", "3620", "3621", "3622"]
    assert next(e for e in emp if e["id"].endswith("3622"))["ambito"] == "universidad"


def test_lo_local_con_isla_y_provincia():
    filas = boc.parsear_boletin(_leer("boc_2026_209.html"), 2026, 209, "2026-10-20")
    emp = boc.seleccionar(filas)
    arona = next(e for e in emp if e["organismo"] == "Ayuntamiento de Arona (Tenerife)")
    assert arona["ambito"] == "local" and arona["tipo_acto"] == "nombramiento"
    assert arona["convocante"]["isla"] == "Tenerife" and arona["convocante"]["provincia"] == "Santa Cruz de Tenerife"
    # Los anuncios locales que no son de empleo (información pública...) no entran
    assert not any("información pública" in e["titulo"] for e in emp)


def test_boletin_2022():
    html = _leer("boc_2022_001.html")
    assert boc.cabecera(html) == (1, "2022-01-03")
    filas = boc.parsear_boletin(html, 2022, 1, "2022-01-03")
    assert len(filas) == 22 and filas[0]["id"] == "BOC-A-2022-001-1"
    assert filas[0]["url_html"].endswith("/boc/2022/001/001.html")
    local = next(f for f in filas if f["bloque"] == "Administración Local")
    assert local["seccion"] == "V. Anuncios" and local["organismo"] == "Ayuntamiento de Arrecife (Lanzarote)"


def test_texto_de_disposicion():
    t = boc.texto_disposicion((FIX / "boc_2026_210_3613.html").read_bytes())
    assert t["titulo"].startswith("Dirección General de la Función Pública.- Resolución de 5 de octubre de 2026")
    assert t["seccion"].startswith("II. Autoridades y personal - Nombramientos")
    assert t["texto"].startswith("A los efectos previstos en los artículos 50, 51, 52 y 53")
    assert "ATENCION. La versión HTML" not in t["texto"] and "Gobierno de Canarias" not in t["texto"][-40:]


def test_procesar_boletin(tmp_path, monkeypatch):
    def obtener(url, accept=None):
        if url == boc.url_boletin(2026, 210):
            return SimpleNamespace(status=200, contenido=(FIX / "boc_2026_210.html").read_bytes(), cabeceras={}, url=url)
        return SimpleNamespace(status=404, contenido=b"", cabeceras={}, url=url)
    monkeypatch.setattr(boc, "obtener", obtener)
    archivo = boc.Archivo(tmp_path / "archivo")
    inf = boc.procesar_boletin(2026, 210, "2026-10-21", tmp_path, archivo)
    assert inf["resultado"] == "ok" and inf["disposiciones"] == 19 and inf["empleo_publico"] == 5
    assert len(boc.textos_pendientes(tmp_path)) == 5
    # Una fecha que no cuadra con la cabecera es un error de formato, no un boletín válido
    assert boc.procesar_boletin(2026, 210, "2026-10-22", tmp_path, archivo)["resultado"] == "error_formato"
    assert boc.procesar_boletin(2026, 211, "2026-10-22", tmp_path, archivo)["resultado"] == "sin_boletin"
