"""BOP de Granada y de Sevilla (plataforma SAGA) con sumarios reales del 29/10/2026."""
from pathlib import Path

from motor.provinciales import bopgranada, bopsevilla, saga

F = Path(__file__).parent / "fixtures"


def test_granada():
    b = bopgranada.BOLETIN
    s = saga.parsear_dia(b, (F / "bopgranada_20261029.html").read_text(encoding="utf-8"))
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == ("210", "2026-10-29", 23)
    assert b.url_dia(__import__("datetime").date(2026, 10, 29)) == \
        "https://bop.dipgra.es/publica/consulta-de-bops/buscador/BOP-29-10-2026/"
    sel = saga.seleccionar(b, s["anuncios"])
    assert all(x["ambito"] == "local" and x["convocante"]["provincia"] == "Granada" for x in sel)
    assert {x["convocante"]["nombre"] for x in sel} >= {"Motril", "La Peza", "Granada", "Picena"}
    # Lo de la Junta (delegaciones territoriales) llega por el BOJA
    assert not any("Delegación" in (x["organismo"] or "") for x in sel)
    d = saga.datos_detalle((F / "bopgranada_detalle.html").read_bytes())
    assert d["pdf"].endswith(".pdf") and d["subsección"] == "CONSORCIOS"


def test_sevilla_municipio_sin_tipo():
    b = bopsevilla.BOLETIN
    s = saga.parsear_dia(b, (F / "bopsevilla_20261029.html").read_text(encoding="utf-8"))
    assert len(s["anuncios"]) == 36
    sel = {x["convocante"]["nombre"]: x for x in saga.seleccionar(b, s["anuncios"])}
    assert sel["Paradas"]["convocante"]["tipo"] == "Ayuntamiento"
    assert "Oferta de empleo público" in next(x["titulo"] for x in saga.seleccionar(b, s["anuncios"])
                                              if x["tipo_acto"] == "oferta_empleo")
    # Subvenciones de la Diputación y empresas de vivienda no son empleo público
    assert not any("subvenciones" in x["titulo"] for x in sel.values())


def test_huesca_paginado(tmp_path, monkeypatch):
    from datetime import date
    from motor.archivo import Archivo
    from motor.http import Respuesta
    from motor.provinciales import bophuesca
    b = bophuesca.BOLETIN
    url = b.url_dia(date(2026, 10, 28))
    paginas = {url: (F / "bophuesca_20261028_p1.html").read_bytes(), url + "?page=2": (F / "bophuesca_20261028_p2.html").read_bytes()}
    monkeypatch.setattr(saga, "obtener", lambda u, **kw: Respuesta(u, 200, paginas[u]))
    monkeypatch.setattr(saga.time, "sleep", lambda s: None)
    inf = saga.procesar_dia(b, date(2026, 10, 28), tmp_path, Archivo(tmp_path / "a", indice_por_fuente=True, solo_huella=True))
    assert (inf["resultado"], inf["disposiciones"]) == ("ok", 24) and not inf["alertas"]
    filas = [l for l in (tmp_path / "datos/provinciales/bophuesca/disposiciones/2026/10/28.jsonl").read_text().splitlines()]
    assert '"BOPH-2026-207001"' in filas[0]
