"""Textos que venían vacíos o con relleno (revisión de la rama de datos, 30/10/2026): avisos de «publicado únicamente
en formato pdf» del BOG, textos vacíos de la API del DOGV de 2023, navegación de la página del DOE y cabecera CVE del
BOP de Sevilla."""

import json

from motor.autonomicos import doe, dogv
from motor.limpieza import limpiar_texto
from motor.provinciales import bopgipuzkoa as g
from motor.provinciales.bopsevilla import BOLETIN as SEVILLA


def test_bog_aviso_de_solo_pdf(tmp_path):
    html = ('<html><body><div id="cuerpoAnuncio"><p>Anuncio publicado únicamente en formato pdf.</p></div>'
            '</body></html>').encode("iso-8859-15")
    assert g.texto_disposicion(html, {"tipo_acto": "convocatoria"})["solo_pdf"]
    x = {"id": "BOG-c1", "fecha": "2026-10-20", "url_pdf": "https://x/c1.pdf", "tipo_acto": "convocatoria"}
    op = tmp_path / "datos/provinciales/bopgipuzkoa/oposiciones/2026/10/20.jsonl"
    op.parent.mkdir(parents=True)
    op.write_text(json.dumps(x) + "\n")
    r = g.ruta_texto(tmp_path, x)
    r.parent.mkdir(parents=True)
    r.write_text(json.dumps({"id": "BOG-c1", "texto": "Anuncio publicado únicamente en formato pdf."}))
    assert [y["id"] for y in g.textos_solo_pdf(tmp_path)] == ["BOG-c1"]
    r.write_text(json.dumps({"id": "BOG-c1", "texto": "Bases.", "desde_pdf": True}))
    assert g.textos_solo_pdf(tmp_path) == []


def test_dogv_texto_vacio_se_toma_del_pdf(tmp_path):
    x = {"id": 386613, "fecha": "2023-05-10", "url_pdf": "https://dogv.gva.es/datos/2023/05/10/pdf/x.pdf"}
    op = tmp_path / "datos/autonomicos/dogv/oposiciones/2023/05/10.jsonl"
    op.parent.mkdir(parents=True)
    op.write_text(json.dumps(x) + "\n")
    r = dogv.ruta_texto(tmp_path, x)
    r.parent.mkdir(parents=True)
    r.write_text(json.dumps({"id": "386613", "texto": "", "tablas": [], "parrafos_omitidos_por_datos_personales": 0}))
    assert [y["id"] for y in dogv.textos_vacios(tmp_path)] == [386613]
    assert limpiar_texto("Núm. 9552 / 13.03.2023\nBases de la convocatoria.\n15625\n", dogv.RE_CABECERA_PDF)["texto"] \
        == "Bases de la convocatoria."


def test_doe_sin_navegacion():
    assert doe.sin_navegacion("TEXTO ORIGINAL\nBases.\nSubir ^\nOtras Opciones") == "Bases."


def test_sevilla_cabecera_cve():
    t = limpiar_texto("CVE: BOP-SE-2025-056007 Nº 56 - lunes 24 de marzo de 2025\nBases.\n", SEVILLA.cabecera_pdf)
    assert t["texto"] == "Bases."
