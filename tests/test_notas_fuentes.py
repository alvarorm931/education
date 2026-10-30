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
