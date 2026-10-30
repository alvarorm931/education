from motor.grados import notas_fuentes as nf


def test_enlaces_solo_a_documentos_de_notas():
    html = ('<a href="/doc/dum-notas-de-corte-2024-2025.pdf">Notas 2024-25</a>'
            '<a href="/doc/calendario.pdf">Calendario</a>'
            '<a href="https://x.es/files/abc">Notas de corte definitivas</a>'
            '<a href="/grado/medicina">Medicina</a>')
    us = [u for u, _ in nf.enlaces(html, "https://u.es/admision/")]
    assert us == ["https://u.es/doc/dum-notas-de-corte-2024-2025.pdf", "https://x.es/files/abc"]


def test_formularios_con_sus_listas():
    html = ('<form action="consulta.php" method="POST"><select name="curso"><option value="2024">2024-25</option>'
            '<option value="2023">2023-24</option></select><input type="hidden" name="d" value="x"></form>')
    f = nf.formularios(html, "https://j.es/sguit/")[0]
    assert f["accion"] == "https://j.es/sguit/consulta.php" and f["metodo"] == "post"
    assert f["listas"]["curso"] == [("2024", "2024-25"), ("2023", "2023-24")] and f["campos"] == ["d"]


def test_medir_csv_y_cursos():
    csv = "Curso;Titulación;Centro;Nota\n2024-2025;Medicina;Facultad;13,456\n2024-2025;Derecho;Facultad;5,000\n"
    m = nf.medir(csv.encode(), "csv")
    assert m["filas_con_nota"] == 2 and m["cursos_que_cita"] == ["2024-2025"]
    assert nf.formato_de(b"%PDF-1.7", "", "x") == "pdf" and nf.formato_de(b'[{"a":1}]', "", "x") == "json"


def test_patrones_por_curso():
    us = nf.cursos_patron("https://u.es/notas_{a}_{b}_{c}.pdf")
    assert us[0] == "https://u.es/notas_2021_22_2021-2022.pdf" and len(us) == len(nf.CURSOS)


def test_nota_no_confunde_fechas_ni_enteros():
    assert nf.NOTA.findall("Medicina 13,456 plazas 180 el 15.07.2026") == ["13,456"]


def test_nunca_listas_de_personas():
    html = ('<a href="/sede/tablon-electronico/AdmisionGrado2026/07-15/Lista_1_2026_admision_publicar.report.pdf">'
            'Lista 1</a><a href="/notas_corte/2026/NOTASDECORTE2026-15julio.pdf">Notas de corte</a>'
            '<a href="/x/Lista_1_2026_espera_publicar.pdf">Lista de espera</a>')
    assert [u for u, _ in nf.enlaces(html, "https://u.es/")] == ["https://u.es/notas_corte/2026/NOTASDECORTE2026-15julio.pdf"]
    assert nf.DNI.search("GARCÍA LÓPEZ, ANA ***1234** 9,876") and not nf.DNI.search("Medicina 0051 13,456")


def test_consulta_post_de_formulario(monkeypatch, tmp_path):
    from motor import http
    from motor.archivo import Archivo

    class R:
        status = 200
        contenido = "<table><tr><td>Medicina</td><td>Granada</td><td>13,512</td></tr></table>".encode()
        cabeceras = {"Content-Type": "text/html"}

    pedidos = []
    monkeypatch.setattr(http, "obtener", lambda url, **k: pedidos.append((url, k["formulario"])) or R())
    monkeypatch.setattr(nf.time, "sleep", lambda s: None)
    doc = nf.consultar({"url": "https://j.es/sguit/?q=grados", "campos": {"anio": "2024", "univpet": ""}},
                       Archivo(tmp_path / "a", indice_por_fuente=True, solo_huella=True), 1000)
    assert pedidos == [("https://j.es/sguit/?q=grados", {"anio": "2024", "univpet": ""})]
    assert doc["estado"] == 200 and doc["formato"] == "html" and doc["filas_con_nota"] == 1
    assert doc["url"].endswith("anio=2024&univpet=")


def test_funcion_del_boton_se_busca_en_los_js_del_sitio():
    from motor.grados import notas_fuentes as nf

    html = ('<form action="?q=a" method="post"><select name="anio"><option value="2024">x</option></select>'
            '<button type="button" onclick="BuscarPeticiones(\'csv\')"></button></form>'
            '<script src="/js/consulta.js"></script><script src="https://otro.es/x.js"></script>')
    js = "var a=1; function BuscarPeticiones(f){ if(f){ $.post('ajax/notas.php', {anio: x}); } else { y(); } } z();"

    class R:
        status_code = 200
        content = js.encode()
        text = js

    pedidas = []

    def pedir(u):
        pedidas.append(u)
        return R()

    f = nf.funciones_de_envio(html, "https://www.ejemplo.es/sguit/", pedir)
    assert pedidas == ["https://www.ejemplo.es/js/consulta.js"]
    assert f[0]["funcion"] == "BuscarPeticiones" and f[0]["codigo"].endswith("y(); } }")
    assert f[0]["direcciones"] == ["ajax/notas.php"]
