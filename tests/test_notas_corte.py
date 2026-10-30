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
    fichas = [{"codigo": "1", "centros": [{"codigo": "C1"}]}, {"codigo": "2", "centros": [{"codigo": "C1"}]}]
    r = anadir_historico(fichas, list(h.values()))
    assert r["centros_con_notas_historicas"] == 1 and "2024-2025" in fichas[0]["centros"][0]["notas_historicas"]["cursos"]
    assert "notas_historicas" not in fichas[1]["centros"][0]


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
