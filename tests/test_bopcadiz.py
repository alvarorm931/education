"""BOP de Cádiz: página del boletín (formato del 30/10/2026, sondas de prueba; los nombres de personas se han cambiado
por otros inventados) y corte del PDF por el registro con que acaba cada anuncio."""
import json
from datetime import date
from pathlib import Path

from motor.archivo import Archivo
from motor.http import Respuesta
from motor.provinciales import bopcadiz as c

FIX = Path(__file__).parent / "fixtures"


def test_boletin():
    s = c.parsear_boletin((FIX / "bopcadiz_2026_210.html").read_bytes())
    assert s["fecha"] == "2026-10-30"
    assert s["url_pdf"] == "https://www.bopcadiz.es/.boletines_pdf/2026/10_octubre/BOP210_30-10-26.pdf"
    a = {x["registro"]: x for x in s["anuncios"]}
    b = a["358.235"]
    assert (b["seccion"], b["organismo"], b["pagina"]) == ("ADMINISTRACION LOCAL", "Ayuntamiento de Benalup-Casas Viejas", 25)
    assert b["titulo"].startswith("Bases para la cobertura de 1 plaza de Administrativo/a")
    assert a["357.549"]["seccion"] == "ADMINISTRACION DEL ESTADO"
    sel = c.seleccionar([{**x, "id": x["registro"], "fecha": "2026-10-30"} for x in s["anuncios"]])
    ids = {x["id"] for x in sel}
    assert "358.235" in ids and "357.549" not in ids
    x = next(x for x in sel if x["id"] == "358.235")
    assert x["convocante"]["nombre"] == "Benalup-Casas Viejas" and x["convocante"]["provincia"] == "Cádiz"
    assert c.url_boletin(2026, 1).endswith("/boletin/Boletin-numero-001-del-ano-2026")


PAGINAS = ["Página 1\nSUMARIO\n...",
           "Página 22\nB.O.P. DE CADIZ NUM. 210 30 de octubre de 2026\nCANDIDATOS A JURADO\nNÚMERO TOTAL: 2200\n"
           "Nº 357.549\nJUNTA DE ANDALUCIA\nRESOLUCIÓN sobre una instalación eléctrica.\nNº 347.590",
           "Página 25\n30 de octubre de 2026 B.O.P. DE CADIZ NUM. 210\nAYUNTAMIENTO DE BENALUP-CASAS VIEJAS\n"
           "ANUNCIO\nBASES PARA LA COBERTURA DE 1 PLAZA DE ADMINISTRATIVO/A DE TESORERÍA.\nPrimera. Objeto.\n"
           "Publicado en el BOP Nº 243\nque pudiera estimar más conveniente a su derecho.           Nº 358.235\nAYUNTAMIENTO DE UBRIQUE\nLISTA PROVISIONAL\n1 ***1234** PEREZ GARCIA, JUAN\nNº 358.241"]


def test_texto_por_registro(tmp_path, monkeypatch):
    t = c.textos_por_registro(PAGINAS)
    assert "BASES PARA LA COBERTURA" in t["358.235"] and "UBRIQUE" not in t["358.235"]
    assert "Primera. Objeto." in t["358.235"] and "a su derecho." in t["358.235"] and "243" not in t and "INSTALACIÓN" not in t["358.235"].upper().split("BASES")[0]

    pagina = (FIX / "bopcadiz_2026_210.html").read_bytes()

    def falso(url, accept=None, **kw):
        if url.endswith(".pdf"):
            return Respuesta(url, 200, b"%PDF-1.4 falso", {})
        if "-210-" in url:
            return Respuesta(url, 200, pagina, {})
        return Respuesta(url, 404, b"", {})

    monkeypatch.setattr(c, "obtener", falso)
    monkeypatch.setattr(c, "paginas_pdf", lambda pdf: PAGINAS)
    monkeypatch.setattr(c.time, "sleep", lambda s: None)
    a = Archivo(tmp_path / "a", indice_por_fuente=True, solo_huella=True)
    inf = c.procesar_boletin(2026, 210, tmp_path, a, 0)
    assert inf["resultado"] == "ok" and inf["empleo_publico"] >= 2
    base = tmp_path / "datos" / "provinciales" / "bopcadiz"
    texto = json.loads((base / "textos" / "2026" / "10" / "BOP-CADIZ-2026-358.235.json").read_text())
    assert texto["texto"].startswith("AYUNTAMIENTO DE BENALUP") and "Primera. Objeto." in texto["texto"]
    lista = json.loads((base / "textos" / "2026" / "10" / "BOP-CADIZ-2026-358.241.json").read_text())
    assert lista["texto"] is None and lista["lineas_con_documento_de_identidad"] == 1
    assert "PEREZ" not in json.dumps(lista, ensure_ascii=False)
    assert (base / "oposiciones" / "2026" / "10" / "30-210.jsonl").exists()
    assert c.procesar_boletin(2026, 211, tmp_path, a, 0)["resultado"] == "sin_boletin"
