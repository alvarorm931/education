"""Histórico de los BOP leídos por su portada que tienen dirección por día (Jaén y Salamanca, 03/01/2022)."""

from datetime import date
from pathlib import Path

from motor.archivo import Archivo
from motor.http import Respuesta
from motor.provinciales import bopjaen, bopsalamanca, portadas

FIX = Path(__file__).parent / "fixtures"


def test_direcciones():
    assert bopjaen.PORTADA.url_dia(date(2022, 1, 3)) == "https://bop.dipujaen.es/bop/03-01-2022"
    assert bopsalamanca.PORTADA.url_dia(date(2022, 1, 3)).endswith("/sede/BOP/index.jsp?fechaBoletin=2022-01-03")


def test_historico(tmp_path, monkeypatch):
    paginas = {bopjaen.PORTADA.url_dia(date(2022, 1, 3)): (FIX / "bopjaen_dia_20220103.html").read_bytes(),
               bopsalamanca.PORTADA.url_dia(date(2022, 1, 3)): (FIX / "bopsalamanca_dia_20220103.html").read_bytes()}
    monkeypatch.setattr(portadas, "obtener", lambda url, accept=None: Respuesta(url, 200, paginas[url], {}))
    monkeypatch.setattr("time.sleep", lambda s: None)
    archivo = Archivo(tmp_path / "archivo", solo_huella=True)
    for p, n in ((bopjaen.PORTADA, 12), (bopsalamanca.PORTADA, 19)):
        assert portadas.historico(p, tmp_path, archivo, date(2022, 1, 1), date(2022, 1, 3)) == 0
        dia = portadas._ruta(p, tmp_path, "dias", date(2022, 1, 3), "json").read_text(encoding="utf-8")
        assert '"resultado": "ok"' in dia and f'"disposiciones": {n}' in dia
        assert portadas._ruta(p, tmp_path, "dias", date(2022, 1, 1), "json").exists()  # sábado: sin boletín


def test_zaragoza_por_calendario(tmp_path, monkeypatch):
    from motor.provinciales import bopzaragoza as z
    boletin = (FIX / "bopzaragoza_boletin_226_2026.html").read_bytes()
    assert len(z.ids_del_mes(boletin)) == 26  # el calendario del mes va en la misma página
    pedidas = []

    def obtener(url, accept=None, formulario=None):
        pedidas.append(formulario)
        if formulario["idBoletin"]:
            return Respuesta(url, 200, boletin, {})
        mes = formulario["fechaNueva"]
        return Respuesta(url, 200, b"verboletin(91929)" if mes == "01/10/2026" else b"", {})

    monkeypatch.setattr("motor.http.obtener", obtener)
    monkeypatch.setattr("time.sleep", lambda s: None)
    # el mes de noviembre no trae boletines (aviso y parada): se queda en el de octubre
    z.historico(["--historico", "--salida", str(tmp_path), "--hoy", "2026-10-30"])
    dia = tmp_path / "datos" / "provinciales" / "bopzaragoza" / "dias" / "2026" / "10" / "01.json"
    assert dia.exists() and '"resultado": "ok"' in dia.read_text(encoding="utf-8")
    assert {"idBoletin": "91929", "fechaNueva": "01/10/2026"} in pedidas
