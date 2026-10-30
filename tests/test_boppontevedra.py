"""BOP de Pontevedra: boletín del día desde la portada (robots.txt prohíbe fichas, descargas y PDF)."""

from pathlib import Path

from motor.provinciales import boppontevedra as b

FIX = Path(__file__).parent / "fixtures"


def test_portada():
    s = b.parsear_portada((FIX / "boppontevedra_portada_20261029.html").read_bytes())
    assert (s["numero"], s["fecha"], len(s["anuncios"])) == ("209", "2026-10-29", 22)
    sel = b.seleccionar(s["anuncios"])
    assert [(x["convocante"]["nombre"], x["tipo_acto"]) for x in sel] == [("Pontevedra", "admitidos"), ("Tomiño", "admitidos")]
    assert all(x["url_html"].startswith("https://boppo.depo.gal/web/boppo/detalle/-/boppo/2026/10/29/") for x in sel)


def test_ficha_del_dia(tmp_path, monkeypatch):
    from datetime import date

    from motor.archivo import Archivo
    from motor.http import Respuesta
    contenido = (FIX / "boppontevedra_dia_20220103.html").read_bytes()
    assert b.url_dia(date(2022, 1, 3)) == "https://boppo.depo.gal/detalle/-/boppo/2022/01/03"
    monkeypatch.setattr(b, "obtener", lambda url, accept=None: Respuesta(url, 200, contenido, {}))
    inf = b.procesar_dia(date(2022, 1, 3), tmp_path, Archivo(tmp_path / "archivo", solo_huella=True))
    assert (inf["resultado"], inf["numero"], inf["disposiciones"]) == ("ok", "1", 14)


def test_texto_ficha():
    h = ('<div id="detalle"><div id="contAnuncio"><div><h2>ADMINISTRACI&Oacute;N LOCAL</h2>'
         '<p class="x00-PARRAFO-SUMARIO">BASES PARA A SELECCI&Oacute;N DUNHA PRAZA DE AUXILIAR</p>'
         '<p>Primeira. Obxecto da convocatoria.</p></div></div><div class="boton">pdf</div>').encode()
    t = b.texto_disposicion(h, {"tipo_acto": "bases"})
    assert "BASES PARA A SELECCIÓN DUNHA PRAZA DE AUXILIAR" in t["texto"] and "pdf" not in t["texto"]
    assert b.texto_disposicion(h, {"tipo_acto": "admitidos"})["solo_recuento"] is True
