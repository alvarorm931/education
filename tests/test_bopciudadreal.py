"""BOP de Ciudad Real con sumarios reales (28/10/2026 y 04/01/2022)."""
from pathlib import Path

from motor.provinciales import bopciudadreal as c

F = Path(__file__).parent / "fixtures"


def test_sumario_y_seleccion():
    s = c.parsear_dia((F / "bopciudadreal_20261028.html").read_bytes())
    assert (s["fecha"], s["numero"], len(s["anuncios"])) == ("2026-10-28", "208", 14)
    x = s["anuncios"][0]
    assert x["seccion"] == "AYUNTAMIENTOS" and x["organismo"] == "ALCÁZAR DE SAN JUAN"
    assert x["url_pdf"].startswith("https://se1.dipucr.es:4443/SIGEM_BuscadorDocsWeb/getDocument.do?entidad=005&doc=")
    sel = c.seleccionar([{**a, "id": a["numero_anuncio"], "fecha": s["fecha"]} for a in s["anuncios"]])
    titulos = [z["titulo"] for z in sel]
    assert any("oposición libre" in t for t in titulos)
    # Ni presupuestos, ni RPT, ni subvenciones, ni jueces de paz
    assert not any(k in t for t in titulos for k in ("presupuesto", "Relación de Puestos", "subven", "Juez", "Jueces"))
    z = next(z for z in sel if "oposición libre" in z["titulo"])
    assert z["convocante"] == {"tipo": "Ayuntamiento", "nombre": "Pozuelo de Calatrava", "provincia": "Ciudad Real",
                               "organismo": "POZUELO DE CALATRAVA"}


def test_2022():
    s = c.parsear_dia((F / "bopciudadreal_20220104.html").read_bytes())
    assert (s["fecha"], len(s["anuncios"])) == ("2022-01-04", 3)
    sel = c.seleccionar([{**a, "id": a["numero_anuncio"], "fecha": s["fecha"]} for a in s["anuncios"]])
    assert [z["tipo_acto"] for z in sel] == ["nombramiento"]
