"""BOP de Castellón, boletines anteriores al carrusel: lista por fechas y anuncios del cuerpo del PDF entero."""

import json

from motor.provinciales import bopcastellon_antiguos as ca

SUMARIO = "PROVINCIA DE CASTELLÓN\nSUMARI/ SUMARIO\nAjuntaments / Ayuntamientos ____ 4"
P2 = """ B.O.P . DE CASTELLÓN DE LA PLANA
2
Núm. 6.—13 de enero de 2022
CVE: 20220100060045
ADMINISTRACIÓ AUTONÒMICA /
ADMINISTRACIÓN AUTONÓMICA
CONSELLERIA D’ECONOMIA SOSTENIBLE / 
CONSELLERÍA DE ECONOMÍA SOSTENIBLE
00060-2022
SERVEI TERRITORIAL DE TREBALL
Vista el acta de acuerdo de modificación y prórroga del Convenio Colectivo de la empresa FACSA-EDAR para la provincia.
"""
P3 = """ B.O.P . DE CASTELLÓN DE LA PLANANúm. 6.—13 de enero de 2022
3
CVE: 20220100060045
ADMINISTRACIÓ LOCAL / ADMINISTRACIÓN LOCAL
DIPUTACIÓ PROVINCIAL DE CASTELLÓ / DIPUTACIÓN PROVINCIAL DE CASTELLÓN
00089-2022-U
PERSONAL
Aprobar lista provisional aspirantes bolsa INGENIERO AMBIENTAL
Recursos Humanos
Personal
El Ilmo. Sr. Presidente ha resuelto aprobar la lista provisional de aspirantes:
1 PEREZ HERRERO MIRIAM ***0000**
Conceder el plazo de diez días naturales para reclamaciones, según el Boletín Oficial de la Provincia de Castellón núm. 150, de 16 de diciembre de 2021.
"""
P4 = """ B.O.P . DE CASTELLÓN DE LA PLANA
4
Núm. 6.—13 de enero de 2022
AJUNTAMENTS / A YUNTAMIENTOS
00080-2022-U
ALMASSORA
N.º de expediente: 5/2021/GTRIORD
EDICTO
El Pleno de la Corporación del Ayuntamiento de Almassora, en sesión ordinaria celebrada el día 10 de enero de 2022, adoptó entre
otros, los siguientes acuerdos:
PRIMERO.- Aprobar la modificación de la Ordenanza Fiscal.
00081-2022-U
ARTANA
ANUNCIO
Bases de la convocatoria para la provisión en propiedad de una plaza de Auxiliar Administrativo por oposición libre.
Plazo de presentación: veinte días hábiles.
"""


def test_lista():
    x = ('<tr data-ri="0" class="ui-widget-content"><td role="gridcell">6</td><td role="gridcell">13/01/2022</td>'
         '<td role="gridcell">B220113</td><td><a href="https://bop.dipcas.es/PortalBOP/api/descargarBoletin?'
         'idBoletin=17584&amp;idioma=es">x</a></td></tr>')
    assert ca.lista(x) == [{"numero": 6, "fecha": "2022-01-13", "referencia": "B220113",
                            "url_pdf": "https://bop.dipcas.es/PortalBOP/api/descargarBoletin?idBoletin=17584&idioma=es"}]


P_2026 = """                                            Número 27 - 3 de marzo de 2026

          ADMINISTRACIÓ AUTONÒMICA / ADMINISTRACIÓN AUTONÓMICA
VICEPRESIDENCIA PRIMERA Y CONSELLERIA DE VIVIENDA, EMPLEO, JUVENTUD E IGUALDAD /

 00762-2026

                                    SERVICIO TERRITORIAL DE TRABAJO

      Vista la solicitud de inscripción y publicación de las tablas salariales para el año 2026 del convenio
 colectivo del Comercio del Metal de la provincia de Castellón.
"""


def test_formato_de_2026_con_disposicion():
    a = ca.anuncios([SUMARIO, P_2026])
    assert [(x["numero_anuncio"], x["seccion"], x["entidad"]) for x in a] == [
        ("00762-2026", "ADMINISTRACIÓN AUTONÓMICA", "VICEPRESIDENCIA PRIMERA Y CONSELLERIA DE VIVIENDA, EMPLEO, "
                                                     "JUVENTUD E IGUALDAD")]
    assert a[0]["titulo"].startswith("Servicio territorial de trabajo. Vista la solicitud")


def test_anuncios_del_cuerpo():
    a = ca.anuncios([SUMARIO, P2, P3, P4])
    assert [(x["numero_anuncio"], x["seccion"], x["entidad"]) for x in a] == [
        ("00060-2022", "ADMINISTRACIÓN AUTONÓMICA", "CONSELLERÍA DE ECONOMÍA SOSTENIBLE"),
        ("00089-2022-U", "ADMINISTRACIÓN LOCAL", "DIPUTACIÓN PROVINCIAL DE CASTELLÓN"),
        ("00080-2022-U", "AYUNTAMIENTOS", "ALMASSORA"),
        ("00081-2022-U", "AYUNTAMIENTOS", "ARTANA")]
    assert a[1]["titulo"] == "Personal. Aprobar lista provisional aspirantes bolsa INGENIERO AMBIENTAL"
    assert a[2]["titulo"].startswith("El Pleno de la Corporación") and a[2]["titulo"].endswith("acuerdos:")
    assert a[3]["titulo"].startswith("Bases de la convocatoria para la provisión en propiedad de una plaza")


def test_procesar(tmp_path, monkeypatch):
    from motor.archivo import Archivo
    from motor.http import Respuesta
    monkeypatch.setattr(ca, "obtener", lambda url, accept=None, **k: Respuesta(url, 200, b"%PDF-1.4", {}))
    monkeypatch.setattr(ca, "paginas_en_orden", lambda c: [SUMARIO, P2, P3, P4])
    b = {"numero": 6, "fecha": "2022-01-13", "url_pdf": "https://bop.dipcas.es/x"}
    inf = ca.procesar(b, tmp_path, Archivo(tmp_path / "archivo"))
    assert (inf["resultado"], inf["disposiciones"], inf["empleo_publico"]) == ("ok", 4, 2)
    base = tmp_path / "datos" / "provinciales" / "bopcastellon"
    op = [json.loads(l) for l in (base / "oposiciones" / "2022" / "01" / "13-006.jsonl").read_text().splitlines()]
    assert [(x["tipo_acto"], (x["convocante"] or {}).get("nombre")) for x in op] == [
        ("admitidos", "Castellón"), ("convocatoria", "Artana")]
    lista = json.loads((base / "textos" / "2022" / "01" / "BOPCASTELLON-00089-2022-U.json").read_text(encoding="utf-8"))
    assert lista["texto"] is None and "PEREZ" not in json.dumps(lista, ensure_ascii=False)
    assert lista["citas"][0]["fecha"] == "2021-12-16"
