"""BORM con respuestas reales de sus servicios: sumarios del 29/10/2026 y del 3/1/2022 y un anuncio en texto."""

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from motor.autonomicos import borm

FIX = Path(__file__).parent / "fixtures"


def test_sumarios_y_seleccion():
    s = borm.parsear_sumario((FIX / "borm_sumario_20261029.xml").read_bytes())
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == ("250", "29-10-2026", 21)
    emp = borm.seleccionar(s["anuncios"])
    titulos = [e["titulo"] for e in emp]
    assert "Edicto de aprobación de oferta de empleo público 2026." in titulos
    assert not any("licitación" in t or "subvenciones a clubes" in t for t in titulos)
    torre = next(e for e in emp if e["organismo"] == "Torre Pacheco")
    assert torre["convocante"] == {"tipo": "Ayuntamiento", "nombre": "Torre Pacheco", "provincia": "Murcia",
                                   "organismo": "Torre Pacheco"}
    s22 = borm.parsear_sumario((FIX / "borm_sumario_20220103.xml").read_bytes())
    emp22 = borm.seleccionar(s22["anuncios"])
    assert sum(1 for e in emp22 if e["organismo"] == "Lorca") == 4   # categoría «Oposiciones - Convocatoria»


def test_dia_sin_boletin(tmp_path, monkeypatch):
    monkeypatch.setattr(borm, "obtener", lambda url, accept=None: SimpleNamespace(
        status=404, contenido=b"boletin.alerts.danger.errorBusqueda", cabeceras={}, url=url))
    assert borm.procesar_dia(date(2026, 10, 25), tmp_path, borm.Archivo(tmp_path / "a"))["resultado"] == "sin_boletin"


def test_texto_con_tablas():
    t = borm.texto_disposicion((FIX / "borm_anuncio_845983.txt").read_bytes())
    assert "se ha aprobado la oferta de empleo público correspondiente al año 2026" in t["texto"]
    assert any(x.get("contenido", [[]])[0][:2] == ["GRUPO", "SUBGRUPO"] for x in t["tablas"])
    lista = ("DNI\tApellidos y nombre\tSituación\n***1234**\tPérez Gómez, Ana\tAdmitida\n").encode()
    t = borm.texto_disposicion(lista)
    assert t["tablas"] == [{"filas": 1, "cabecera": ["DNI", "Apellidos y nombre", "Situación"], "datos_personales": True}]
    assert "Pérez" not in t["texto"]
