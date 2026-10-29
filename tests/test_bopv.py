"""BOPV (País Vasco) con páginas reales: sumarios 207/2026 y 1/2022, una disposición y la respuesta a un número
que no existe."""

from pathlib import Path
from types import SimpleNamespace

from motor.autonomicos import bopv

FIX = Path(__file__).parent / "fixtures"


def _html(nombre):
    return bopv._html((FIX / nombre).read_bytes())


def test_url():
    assert bopv.url_boletin(2026, 207).endswith("/p43aBOPVWebWar/VerParalelo.do?cs2026000207")


def test_sumario_2026_columna_castellano():
    html = _html("bopv_2026_207.html")
    assert bopv.cabecera(html) == (207, "2026-10-29")
    filas = bopv.parsear_boletin(html, 207, "2026-10-29")
    assert len(filas) == 18
    assert all("/web01-bopv/es/" in f["url_html"] for f in filas)       # nunca la columna en euskera
    f = filas[0]
    assert f["id"] == "BOPV-2604551" and f["seccion"] == "DISPOSICIONES GENERALES"
    # Las cabeceras vacías repiten la anterior
    upv = [f for f in filas if f["organismo"] == "UNIVERSIDAD DEL PAÍS VASCO"]
    assert len(upv) >= 2 and all(f["subseccion"] == "Nombramientos, situaciones e incidencias" for f in upv)
    emp = bopv.seleccionar(filas)
    assert [e["id"] for e in emp] == ["BOPV-2604557", "BOPV-2604558", "BOPV-2604559"]
    assert {e["subseccion"] for e in emp} == {"Oposiciones y concursos"}


def test_sumario_2022_diputacion_foral():
    html = _html("bopv_2022_001.html")
    assert bopv.cabecera(html) == (1, "2022-01-03")
    emp = bopv.seleccionar(bopv.parsear_boletin(html, 1, "2022-01-03"))
    assert len(emp) == 1
    e = emp[0]
    assert e["ambito"] == "local" and e["convocante"]["tipo"] == "Diputación Foral"
    assert e["convocante"]["provincia"] == "Araba/Álava"


def test_numero_inexistente():
    assert bopv.cabecera(_html("bopv_inexistente.html")) == (None, None)


def test_texto_sin_datos_personales():
    t = bopv.texto_disposicion((FIX / "bopv_2604553.html").read_bytes())
    assert t["seccion"] == "AUTORIDADES Y PERSONAL" and t["organismo"] == "UNIVERSIDAD DEL PAÍS VASCO"
    assert t["titulo"].startswith("RESOLUCIÓN de 14 de octubre de 2026, del rector")
    assert "***3642**" not in t["texto"] and t["parrafos_omitidos_por_datos_personales"] == 1
    assert t["texto"].startswith("El candidato propuesto dispone de 20 días hábiles")


def test_procesar_boletin(tmp_path, monkeypatch):
    paginas = {bopv.url_boletin(2026, 207): (FIX / "bopv_2026_207.html").read_bytes()}

    def obtener(url, accept=None):
        return SimpleNamespace(status=200, contenido=paginas.get(url, (FIX / "bopv_inexistente.html").read_bytes()),
                               cabeceras={}, url=url)
    monkeypatch.setattr(bopv, "obtener", obtener)
    archivo = bopv.Archivo(tmp_path / "archivo")
    inf = bopv.procesar_boletin(2026, 207, tmp_path, archivo)
    assert inf["resultado"] == "ok" and inf["fecha"] == "2026-10-29" and inf["empleo_publico"] == 3
    assert bopv.procesar_boletin(2026, 208, tmp_path, archivo)["resultado"] == "sin_boletin"
    assert len(bopv.textos_pendientes(tmp_path)) == 3


def test_boletin_del_dia_siguiente(tmp_path, monkeypatch):
    """El sumario del día siguiente sale la tarde anterior, pero sus páginas están vacías: no se procesa aún."""
    from datetime import date

    import pytest
    monkeypatch.setattr(bopv, "obtener", lambda url, accept=None: SimpleNamespace(
        status=200, contenido=(FIX / "bopv_2026_207.html").read_bytes(), cabeceras={}, url=url))
    inf = bopv.procesar_boletin(2026, 207, tmp_path, bopv.Archivo(tmp_path / "archivo"), date(2026, 10, 28))
    assert inf["resultado"] == "posterior" and not (tmp_path / "datos").exists()
    with pytest.raises(ValueError):
        bopv.texto_disposicion((FIX / "bopv_2604571_antes_de_publicar.html").read_bytes())
