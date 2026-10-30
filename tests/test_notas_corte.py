from motor.grados import notas_corte as nc
from motor.grados.fichas import anadir_historico

CAB_COMPLETA = [
    "                                    UNIVERSIDAD COMPLUTENSE DE MADRID",
    "                                       CURSO 2025/2026",
    " Código   TITULACIONES DE GRADO              Grupo 1        Grupo 2        Grupo 3        Grupo 4        Grupo 5     Grupo 6",
    "                                         Ordinaria Extraord. Ord.   Ext.   Ord.   Ext.   Ord.   Ext.   Ord.   Ext.   Extraord.",
]


def test_madrid_tabla_completa_en_orden_y_con_guion_de_mas():
    filas = nc.leer_madrid(CAB_COMPLETA + [
        "  0054   Medicina                       13,100    -----     9,89   -----  5,030 (3) -----  5,00   -----  5,00   -----  -----",
    ])
    g1 = {(x["grupo"], x["convocatoria"]): x for x in filas}
    assert g1[(1, "ordinaria")]["nota"] == 13.1 and g1[(1, "extraordinaria")]["sin_plazas"]
    assert g1[(3, "ordinaria")]["nota"] == 5.03 and g1[(3, "ordinaria")]["llamada"] == "3"
    assert filas[0]["universidad"] == "Complutense de Madrid" and filas[0]["curso"] == "2025-2026"


def test_madrid_tabla_de_la_autonoma_con_celdas_vacias():
    lineas = [
        "   UNIVERSIDAD AUTÓNOMA DE MADRID",
        "   CURSO 2025/2026",
        " Código    TITULACIONES DE GRADO                       Grupo 1                     Grupo 2              Grupo 6",
        "                                              Ordinaria     Extraord.      Ordinaria     Extraord.     Extraord.",
        "   0218    Arqueología                          5,000                         5,00",
        "   0263    Derecho                              9,837           -----         7,68          -----         -----",
    ]
    filas = nc.leer_madrid(lineas)
    arq = {(x["grupo"], x["convocatoria"]): x["nota"] for x in filas if x["codigo_local"] == "0218"}
    assert arq == {(1, "ordinaria"): 5.0, (2, "ordinaria"): 5.0}  # la celda vacía no corre las demás
    der = {(x["grupo"], x["convocatoria"]): x["nota"] for x in filas if x["codigo_local"] == "0263"}
    assert der[(1, "ordinaria")] == 9.837 and der[(2, "ordinaria")] == 7.68 and (6, "extraordinaria") in der


def test_murcia_trae_los_codigos_del_ministerio():
    csv = ["curso_academico_cod,curso_academico,tipo_centro,centro_cod,centro_cod_mec,centro,ciclo_titulacion_cod,"
           "ciclo_titulacion,titulacion_cod,titulacion_cod_mec,titulacion,especialidad,nota_corte,nota_corte_mujer,"
           "nota_corte_hombre",
           "2024,2024/2025,Centros propios,0E01,30010221,Facultad de Biología,G,Grado,220,2500722,Grado en Biología,"
           "No Aplica,9.422,9.746,9.422"]
    x = nc.leer_murcia(csv)[0]
    assert (x["curso"], x["codigo_titulo"], x["codigo_centro"], x["nota"]) == ("2024-2025", "2500722", "30010221", 9.422)


def _cand(codigo, nombre, centro, municipio, clase="grado", notas=None, propio=True, componentes=None):
    return {"codigo": codigo, "clase": clase, "nombre": nombre, "palabras": nc.palabras(nombre),
            "palabras_componentes": frozenset().union(*(nc.palabras(c) for c in componentes)) if componentes else frozenset(),
            "centro": centro, "unidad": "Facultad", "municipio": municipio, "idioma": "No", "propio": propio,
            "ofertado": True, "notas_qedu": notas or {}}


def _fila(nombre, nota, curso="2025-2026", codigo="0001"):
    return {"distrito": "madrid", "curso": curso, "universidad": "U", "codigo_local": codigo, "titulacion": nombre,
            "cupo": "general", "convocatoria": "ordinaria", "lista": "final", "nota": nota,
            "fuente": {"url": "https://u.es/n.pdf", "sha256": "x", "capturado": "2026-10-30"}}


def test_union_por_nombre_campus_y_doble():
    cands = {"U": [_cand("1", "Economía", "C1", "fuenlabrada"), _cand("2", "Derecho", "C1", "fuenlabrada"),
                   _cand("3", "Economía y Derecho", "C1", "fuenlabrada", "doble", componentes=["Economía", "Derecho"]),
                   _cand("3", "Economía y Derecho", "C2", "mostoles", "doble", componentes=["Economía", "Derecho"]),
                   _cand("4", "Periodismo", "C1", "fuenlabrada"), _cand("4", "Periodismo", "C3", "madrid", propio=False)]}
    filas = [_fila("Economía-Derecho (Móstoles)", 9.5, codigo="0730"), _fila("Periodismo", 8.0, codigo="0800"),
             _fila("Economía", 7.0, codigo="0810")]
    nc.unir(filas, cands)
    assert (filas[0]["codigo_titulo"], filas[0]["codigo_centro"]) == ("3", "C2")  # doble y su campus
    assert (filas[1]["codigo_titulo"], filas[1]["codigo_centro"]) == ("4", "C1")  # sin campus: el centro propio
    assert filas[2]["codigo_titulo"] == "1"


def test_qedu_redondea_o_trunca_y_el_historico_solo_publica_lo_que_cuadra():
    assert nc.igual_a_qedu(10.54, 10.545) and nc.igual_a_qedu(13.27, 13.265) and not nc.igual_a_qedu(9.14, 10.226)
    cands = {"U": [_cand("1", "Derecho", "C1", "madrid", notas={"2025-2026": 9.21}),
                   _cand("2", "Medicina", "C1", "madrid", notas={"2025-2026": 13.0})]}
    filas = [_fila("Derecho", 9.837, codigo="0263"), _fila("Derecho - Mención en Derecho de la energía", 9.214,
             codigo="0273"), _fila("Derecho", 9.9, curso="2024-2025", codigo="0263"),
             _fila("Medicina", 12.5, codigo="0054")]
    nc.unir(filas, cands)
    h = {x["codigo_titulo"]: x for x in nc.historico(filas, cands)}
    assert h["1"]["cursos"]["2025-2026"]["nota"] == 9.214 and h["1"]["cursos"]["2025-2026"]["ofertas"] == 2
    assert h["1"]["publicable"] and not h["2"]["publicable"]  # Medicina no coincide con QEDU
    # diferencias que solo dicen que QEDU toma la nota en otro momento del proceso
    assert nc.tipo_de_contraste(11.72, 11.70) == "lista_posterior_mas_baja"
    assert nc.tipo_de_contraste(5.0, 9.3) == "qedu_con_plazas_libres"
    assert nc.tipo_de_contraste(13.0, 12.5) == "distinta" and nc.tipo_de_contraste(9.0, 9.4) == "distinta"
    fichas = [{"codigo": "1", "centros": [{"codigo": "C1"}]}, {"codigo": "2", "centros": [{"codigo": "C1"}]}]
    r = anadir_historico(fichas, list(h.values()))
    assert r["centros_con_notas_historicas"] == 1 and "2024-2025" in fichas[0]["centros"][0]["notas_historicas"]["cursos"]
    assert "notas_historicas" not in fichas[1]["centros"][0]
    # con la nota de su distrito en un curso reciente, la ficha deja de estar sin nota de corte
    f = [{"codigo": "1", "centros": [{"codigo": "C1"}], "indexable": False,
          "motivos_noindex": ["sin nota de corte ni precio"]}]
    assert anadir_historico(f, list(h.values()))["fichas_con_nota_solo_por_el_historico"] == 1 and f[0]["indexable"]


def test_cataluna_primera_asignacion_no_se_publica_sin_otra_comprobacion():
    lineas = ['[{"curs_acad_mic":"2025-2026","any":"2025","codi_oferta":"837","nom_de_l_oferta":"Medicina",'
              '"tipus_d_estudi":"Grau","sigles_universitat_responsable":"UdG","via_d_acc_s":"Pau/cfgs/FP",'
              '"nota_de_tall":"12.676","municipi":"Girona","nombre_de_places":"92"}',
              ',{"curs_acad_mic":"2025-2026","any":"2025","codi_oferta":"837","nom_de_l_oferta":"Medicina",'
              '"tipus_d_estudi":"Grau","sigles_universitat_responsable":"UdG","via_d_acc_s":"Pau/cfgs/FP",'
              '"nota_de_tall":"12.676","municipi":"Girona","nombre_de_places":"92"}]']
    filas = nc.leer_cataluna(lineas)
    assert len(filas) == 1 and filas[0]["universidad"] == "Girona" and filas[0]["plazas"] == 92
    filas[0]["fuente"] = {}
    cands = {"Girona": [_cand("9", "Medicina", "C9", "girona", notas={"2025-2026": 12.68})]}
    nc.unir(filas, cands)
    assert not nc.historico(filas, cands)[0]["publicable"]  # sin plazas de QEDU con que comprobar
    cands["Girona"][0]["plazas_qedu"] = {"2025-2026": 92.0}
    h = nc.historico(filas, cands)[0]
    assert h["publicable"] and h["lista"] == "primera_asignacion" and h["contraste_qedu"] == {"plazas_iguales": 1}


def test_catalan_doble_por_simultaneidad():
    assert nc.palabras("Administració i Direcció d'Empreses", catalan=True) == nc.palabras("Administración y Dirección de Empresas")
    cands = {"U": [_cand("1", "Criminología", "C", "barcelona"), _cand("2", "Derecho", "C", "barcelona"),
                   _cand("3", "Criminología y Derecho", "C", "barcelona", "doble", componentes=["Criminología", "Derecho"])]}
    x = {**_fila("Criminologia / Dret (simultaneïtat)", 9.0), "distrito": "cataluna", "lista": "primera_asignacion"}
    nc.unir([x], cands)
    assert x["codigo_titulo"] == "3"


def test_salamanca_grupo_general_y_tipo_de_lista():
    lineas = ["NOTAS DE CORTE EN LOS GRADOS DE LA USAL EN EL CURSO 2026-27",
              "correspondientes al último estudiante admitido en cada titulación, según el tercery último   listado.",
              "                                  Biología                                             180          "
              "09.228 (prioritaria ordinaria)            05.000 (ordinaria)",
              "   Antropología-Filosofía                                        10        05.000 (no prioritaria extraord.)",
              "        Administración y Dirección de Empresas-                   30           11.467      (prioritaria ordinaria)"]
    f = nc.leer_usal(lineas)
    assert [(x["titulacion"], x["nota"], x["plazas"], x["todos_admitidos"]) for x in f] == [
        ("Biología", 9.228, 180, False), ("Antropología-Filosofía", 5.0, 10, True)]  # el doble partido, fuera
    assert f[0]["curso"] == "2026-2027" and f[0]["lista"] == "tercer_listado"


def test_ehu_cinco_cupos_con_cifras_pegadas():
    from motor.grados.notas_corte import _trocear_ehu, leer_ehu

    assert _trocear_ehu("*   *8,0836,610   *") == ["*", "*", "8,083", "6,610", "*"]
    assert _trocear_ehu("6,510   8,750   8,380   12,061   8,552") == ["6,510", "8,750", "8,380", "12,061", "8,552"]
    assert _trocear_ehu("*   7,500   5,008,4788,468") == ["*", "7,500", "5,00", "8,478", "8,468"]
    assert _trocear_ehu("8,534   6,267   *E 8,405 *") == ["8,534", "6,267", "*", "E8,405", "*"]
    assert _trocear_ehu("*  *  -E 5,0006,790*") is None  # seis casillas: no se lee
    lineas = [
        "   LÍMITE DE PLAZAS Y NOTA DE CORTE  DE ADMISIÓN PARA EL CURSO 2021-22",
        "   Nº de   M- 25   M- 45Cupo Genérico   Titulados/asExperiencia laboral",
        "   CAMPUS DE BIZKAIA   Plazas   2% de las plazas   1% de las plazas   1% de las plazasBachillerato + FP2% de las plazas",
        "   Grado en Medicina   200   6,694   5,125   -12,8279,380",
        "   Grado en Historia del Arte   60   8,534   6,267   *E 8,405 *",
        "   CAMPUS DE ALAVA   Plazas   2% de las plazas   1% de las plazas   1% de las plazasBachillerato + FP2% de las plazas",
        "   Grado en Administración y Dirección de Empresas   110   *   *   *7,138*",
    ]
    f = leer_ehu(lineas)
    g = {(x["campus"], x["titulacion"]): x for x in f if x["cupo"] == "general"}
    med = g[("BIZKAIA", "Grado en Medicina")]
    assert med["curso"] == "2021-2022" and med["nota"] == 12.827 and med["plazas"] == 200
    assert med["convocatoria"] == "ordinaria" and med["municipios"] == ["leioa", "bilbao"]
    assert [x["nota"] for x in f if x["titulacion"] == "Grado en Medicina"] == [6.694, 5.125, None, 12.827, 9.38]
    assert [x["sin_plazas"] for x in f if x["titulacion"] == "Grado en Medicina"][2] is True
    arte = g[("BIZKAIA", "Grado en Historia del Arte")]
    assert arte["convocatoria"] == "extraordinaria" and arte["nota"] == 8.405
    assert g[("ALAVA", "Grado en Administración y Dirección de Empresas")]["nota"] == 7.138
    assert [x["todos_admitidos"] for x in f if x["campus"] == "ALAVA"] == [True, True, True, False, True]
    assert leer_ehu(["### página 1 (lectura óptica)"] + lineas) == []


def test_un_doble_por_nombre_no_se_une_con_uno_de_sus_grados():
    from motor.grados.notas_corte import palabras, puntuar

    cs = [{"codigo": "1", "clase": "grado", "nombre": "Gestión de Negocios", "palabras": palabras("Gestión de Negocios"),
           "palabras_componentes": frozenset(), "centro": "c", "unidad": "Facultad", "municipio": "bilbao",
           "idioma": None, "propio": True, "ofertado": True, "notas_qedu": {}, "plazas_qedu": {}}]
    x0 = {"distrito": "pais-vasco", "lista": "final"}
    assert puntuar("Doble Grado en Gestión de Negocios + Rel. Lab. y Rec. Hum.", x0, [x0], cs) == []


def test_andalucia_csv_del_distrito_unico():
    lineas = ['ï»¿CURSO;UNIVERSIDAD;PETICION;GRADO;CENTRO;ÁREA;GENERAL;TITULADOS;"MAYORES 25";"MAYORES 40";"MAYORES 45"',
              '2025;ALMERÍA;125504;"ADMINISTRACIÓN Y DIRECCIÓN DE EMPRESAS";"FACULTAD CIENCIAS ECONÓMICAS Y '
              'EMPRESARIALES";SYJ;"5,361 PREF";5,000;"5,000 ONPNA";8,558;5,000',
              '2024;"P. OLAVIDE";1;DERECHO;"FACULTAD DE DERECHO";SYJ;"6,800 N.P.";5,000;"5,000 ONPNA";5,000;5,000']
    f = nc.leer_andalucia(lineas)
    g = [x for x in f if x["cupo"] == "general"]
    assert len(f) == 10 and g[0]["curso"] == "2025-2026" and g[0]["universidad"] == "Almería"
    assert g[0]["nota"] == 5.361 and g[0]["tipo_ultimo_admitido"] == "PREF" and g[0]["codigo_local"] == "125504"
    assert g[0]["centro_nombre"].startswith("FACULTAD CIENCIAS") and g[0]["lista"] == "final"
    assert g[1]["universidad"] == "Pablo de Olavide" and g[1]["todos_admitidos"] is True
    assert [x["nota"] for x in f[:5]] == [5.361, 5.0, 5.0, 8.558, 5.0]
    assert nc.nombre_de_centro("F. CIENCIAS ECONÓMICAS Y EMPRES.").startswith("Facultad CIENCIAS")


def test_nombre_poco_parecido_no_se_une_aunque_el_centro_empuje():
    """«Derecho y Administración de Empresas» (un doble sin «+») no es «Administración de Empresas»."""
    cands = {"U": [_cand("1", "Administración de Empresas", "C1", "getafe")]}
    x = _fila("Derecho y Administración de Empresas (Getafe)", 11.0)
    r = nc.unir([x], cands)
    assert not x.get("codigo_titulo") and r["parecido_de_nombre_bajo"] == 1


def test_cantabria_comparativa_por_posicion():
    def ln(y, *ts):
        return {"y": y, "trozos": [list(t) for t in ts]}

    cab = [(800, "CURSO", 90), (900, "2024/2025", 150), (1200, "CURSO", 90), (1300, "2025/2026", 150)]
    sub = [(820, "JUNIO", 100), (1000, "JULIO", 100), (1220, "JUNIO", 100), (1400, "JULIO", 100)]
    pos = [{"pagina": 1, "ocr": True, "lineas": [
        ln(100, *cab), ln(150, (50, "ESTUDIOS", 120), *sub),
        ln(200, (50, "Grado", 80), (140, "en", 30), (180, "Medicina", 120), (830, "13,066", 80), (1230, "12,727", 80)),
        ln(250, (50, "Grado", 80), (140, "en", 30), (180, "Física", 90), (1030, "11,470", 80)),
        ln(300, (50, "Doble", 80), (140, "Grado", 80), (230, "en", 30), (270, "ADE", 60), (330, "y", 20),
           (830, "12,345", 80), (1230, "11,787", 80)),
        ln(320, (50, "Economía", 110))]}]
    f = nc.leer_cantabria(["### página 1 (lectura óptica)"], pos)
    med = [x for x in f if x["titulacion"] == "Grado en Medicina"]
    assert [(x["curso"], x["convocatoria"], x["nota"]) for x in med] == [("2024-2025", "ordinaria", 13.066),
                                                                       ("2025-2026", "ordinaria", 12.727)]
    fis = [x for x in f if x["titulacion"] == "Grado en Física"][0]
    assert fis["curso"] == "2024-2025" and fis["convocatoria"] == "extraordinaria"
    assert any(x["titulacion"] == "Doble Grado en ADE y Economía" for x in f)
    assert nc.leer_cantabria(["### página 1"], None) == []


def test_burgos_evolucion_por_posicion():
    anios = [(1000 + i * 100, str(2021 + i % 6), 40) for i in range(12)]
    pos = [{"pagina": 1, "ocr": True, "lineas": [
        {"y": 50, "trozos": [[100, "2026/27", 60], [300, "TITULACIÓN", 90]] + [list(a) for a in anios]},
        {"y": 100, "trozos": [[100, "85", 20], [300, "Grado", 50], [360, "en", 20], [390, "Enfermería", 90],
                              [1000, "11,576", 50], [1100, "11,012", 50], [1500, "11,048", 50], [1600, "8,130", 50]]},
        {"y": 120, "trozos": [[100, "95", 20], [300, "Grado", 50], [360, "en", 20], [390, "Derecho", 70],
                              [1000, "7,221", 50], [1046, "*", 8]]}]}]
    f = nc.leer_ubu(["### página 1 (lectura óptica)"], pos)
    enf = [(x["curso"], x["cupo"], x["nota"]) for x in f if x["titulacion"] == "Grado en Enfermería"]
    assert enf == [("2021-2022", "general", 11.576), ("2022-2023", "general", 11.012),
                   ("2026-2027", "general", 11.048), ("2021-2022", "titulados", 8.13)]
    der = [x for x in f if x["titulacion"] == "Grado en Derecho"][0]
    assert der["todos_admitidos"] and der["plazas"] == 95 and der["distrito"] == "burgos"
