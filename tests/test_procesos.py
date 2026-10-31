from datetime import date

from motor.procesos import construir, resumen


def _acto(i, fecha, tipo, **kw):
    return {"id": i, "fecha": fecha, "tipo_acto": tipo, "ambito": "local", "alcance": "acceso", **kw}


def test_estados_y_enlaces():
    actos = [
        _acto("A1", "2026-10-20", "apertura_plazo", convocante={"tipo": "Ayuntamiento", "nombre": "Mijas", "provincia": "Málaga"},
              plazas=[{"numero": 3, "puesto_clave": "auxiliar-administrativo"}], total_plazas=3,
              plazo={"dias": 20, "tipo": "habiles", "fin_estimado": "2026-11-17"}),
        _acto("A2", "2026-09-01", "apertura_plazo", convocante={"tipo": "Ayuntamiento", "nombre": "Ourense", "provincia": None},
              total_plazas=1, plazo={"dias": 10, "tipo": "habiles", "fin_estimado": "2026-09-15"}),
        _acto("A3", "2026-10-01", "apertura_plazo", total_plazas=2, plazo={"fin_estimado": "2026-11-30"}),
        _acto("C1", "2026-10-25", "correccion", refiere_a=["A1"]),
        _acto("N1", "2026-10-26", "anulacion", refiere_a=["A3"]),
        _acto("P1", "2026-10-01", "apertura_plazo", alcance="promocion_interna", plazo={"fin_estimado": "2026-12-01"}),
    ]
    ps = {p["id"]: p for p in construir(actos, date(2026, 10, 29))}
    assert set(ps) == {"boe:A1", "boe:A2", "boe:A3"}  # la promoción interna no crea proceso público
    assert ps["boe:A1"]["estado"] == "plazo_abierto" and [a["id"] for a in ps["boe:A1"]["actos"]] == ["A1", "C1"]
    assert ps["boe:A1"]["actualizado"] == "2026-10-25"
    assert ps["boe:A2"]["estado"] == "plazo_cerrado" and ps["boe:A2"]["provincia"] == "Ourense"
    assert ps["boe:A3"]["estado"] == "anulado"
    r = resumen(list(ps.values()), date(2026, 10, 29))
    assert r["plazo_abierto"] == {"procesos": 1, "plazas": 3, "por_provincia": {"Málaga": 3},
                                  "procesos_por_comunidad": {"Andalucía": 1},
                                  "por_puesto": {"auxiliar-administrativo": 3}, "por_fuente": {"BOE": 1}}
    assert ps["boe:A1"]["convocante"]["codigo_ine"] == "29070" and ps["boe:A2"]["comunidad"] == "Galicia"


def test_boe_y_boletines_autonomicos():
    titulo = ("Resolución de 5 de octubre de 2026, de la Universidad de Granada, por la que se convoca proceso selectivo "
              "para ingreso en la Escala Auxiliar Administrativa.")
    boe = [
        # La universidad publica en el BOJA y el plazo cuenta desde allí: el BOE no da fecha de fin
        _acto("U1", "2026-10-12", "convocatoria", ambito="universidad", titulo=titulo,
              plazo={"dias": 20, "tipo": "habiles", "cuenta_desde": "Boletín Oficial de la Junta de Andalucía"}),
        # Anuncio local del BOE que cita las bases íntegras publicadas en el BOCYL
        _acto("L1", "2026-10-20", "apertura_plazo", convocante={"tipo": "Ayuntamiento", "nombre": "Miranda de Ebro",
                                                               "provincia": "Burgos"},
              boletines_citados=[{"boletin": "Boletín Oficial de Castilla y León", "numero": "189",
                                  "fecha": "2026-10-02", "papel": "bases"}],
              plazo={"dias": 20, "tipo": "naturales", "fin_estimado": "2026-11-09"}),
    ]
    autonomicos = [
        {"id": "boja:1", "fecha": "2026-10-08", "fuente": "BOJA", "tipo_acto": "convocatoria", "ambito": "universidad",
         "alcance": "acceso", "titulo": titulo.upper(), "tiene_texto": True,
         "plazo": {"dias": 20, "tipo": "habiles", "fin_estimado": "2026-11-05"}},
        {"id": "bocyl:B1", "fecha": "2026-10-02", "fuente": "BOCYL", "tipo_acto": "convocatoria", "ambito": "local",
         "alcance": "acceso", "titulo": "ACUERDO ... bases ...", "convocante": {"nombre": "Miranda de Ebro"}},
        # Convocatoria autonómica que no sale en el BOE: proceso propio
        {"id": "dogv:9", "fecha": "2026-10-27", "fuente": "DOGV", "tipo_acto": "convocatoria", "ambito": "autonomico",
         "alcance": "acceso", "titulo": "RESOLUCIÓN ... por la que se convocan pruebas selectivas",
         "plazo": {"dias": 20, "tipo": "habiles", "fin_estimado": "2026-11-24"}},
    ]
    ps = {p["id"]: p for p in construir(boe, date(2026, 10, 29), autonomicos)}
    assert set(ps) == {"boe:U1", "boe:L1", "dogv:9"}
    u = ps["boe:U1"]
    assert u["estado"] == "plazo_abierto" and u["plazo"]["de_acto"] == "boja:1" and u["fuentes"] == ["BOE", "BOJA"]
    assert [x["id"] for x in ps["boe:L1"]["otras_publicaciones"]] == ["bocyl:B1"]
    assert ps["dogv:9"]["fuente"] == "Diari Oficial de la Generalitat Valenciana"


def test_bases_locales_sin_anuncio_en_el_boe():
    autonomicos = [
        # Bases de carrera en el BOPB: el plazo empezará con el extracto en el BOE, que aún no ha salido
        {"id": "bopb:BOPB-1", "fecha": "2026-10-28", "fuente": "BOPB", "tipo_acto": "convocatoria", "ambito": "local",
         "alcance": "acceso", "titulo": "Bases i convocatòria per proveir una plaça d'enginyer/a municipal",
         "convocante": {"tipo": "Ayuntamiento", "nombre": "Vilafranca del Penedès", "provincia": "Barcelona"},
         "plazo": {"dias": 20, "tipo": "naturales", "cuenta_desde": "Boletín Oficial del Estado"}},
        # Bolsa de trabajo temporal: no va al BOE y el plazo cuenta desde el propio BOP
        {"id": "bopb:BOPB-2", "fecha": "2026-10-28", "fuente": "BOPB", "tipo_acto": "convocatoria", "ambito": "local",
         "alcance": "acceso", "modalidad": "bolsa", "titulo": "Bases de la borsa de treball d'auxiliar administratiu",
         "convocante": {"tipo": "Ayuntamiento", "nombre": "Castelldefels", "provincia": "Barcelona"},
         "plazo": {"dias": 10, "tipo": "naturales", "fin_estimado": "2026-11-07"}},
        # Las bases que sí cita un anuncio del BOE no forman proceso propio
        {"id": "bopb:BOPB-3", "fecha": "2026-10-02", "fuente": "BOPB", "tipo_acto": "convocatoria", "ambito": "local",
         "alcance": "acceso", "titulo": "Bases ... agent de la Policia Local",
         "convocante": {"tipo": "Ayuntamiento", "nombre": "Mataró", "provincia": "Barcelona"}},
    ]
    boe = [_acto("L9", "2026-10-20", "apertura_plazo", convocante={"tipo": "Ayuntamiento", "nombre": "Mataró",
                                                                   "provincia": "Barcelona"},
                 boletines_citados=[{"boletin": "Boletín Oficial de la Provincia de Barcelona", "fecha": "2026-10-02",
                                     "papel": "bases"}],
                 plazo={"dias": 20, "tipo": "naturales", "fin_estimado": "2026-11-09"})]
    ps = {p["id"]: p for p in construir(boe, date(2026, 10, 29), autonomicos)}
    assert set(ps) == {"boe:L9", "bopb:BOPB-1", "bopb:BOPB-2"}
    assert [o["id"] for o in ps["boe:L9"]["otras_publicaciones"]] == ["bopb:BOPB-3"]
    assert ps["boe:L9"]["convocante"]["codigo_ine"] == "08121"
    assert ps["bopb:BOPB-1"]["estado"] == "bases_publicadas_pendiente_boe" and ps["bopb:BOPB-1"]["solo_bases_locales"]
    assert ps["bopb:BOPB-2"]["estado"] == "plazo_abierto" and ps["bopb:BOPB-2"]["temporal"]
    r = resumen(list(ps.values()), date(2026, 10, 29))["enlaces_locales"]
    assert r["con_bases_enlazadas"] == 1 and r["procesos_solo_con_bases_locales"] == {"BOPB": 2}


def test_bases_compartidas_y_diputacion():
    """Tres anuncios del BOE citan el mismo BOP: cada bases va con el de su puesto. La diputación sin tipo en el BOP
    («Diputación Provincial Alicante») es la del BOE («Diputación Provincial» de «Alicante»)."""
    cita = [{"boletin": "Boletín Oficial de la Provincia de Alicante", "numero": "96", "fecha": "2022-05-23",
             "papel": "bases"}]
    benissa = {"tipo": "Ayuntamiento", "nombre": "Benissa", "provincia": "Alicante"}
    boe = [_acto(f"B{i}", "2022-06-10", "apertura_plazo", convocante=benissa, boletines_citados=cita,
                 plazas=[{"numero": 1, "puesto_clave": q}]) for i, q in
           [(1, "profesor-musica"), (2, "profesor-ballet"), (3, "monitor-danza-tradicional")]]
    boe.append(_acto("D1", "2022-06-10", "apertura_plazo", boletines_citados=cita,
                     convocante={"tipo": "Diputación Provincial", "nombre": "Alicante", "provincia": None}))
    loc = lambda i, t, c: {"id": i, "fecha": "2022-05-23", "fuente": "BOP-ALICANTE", "tipo_acto": "bases",
                           "ambito": "local", "alcance": "acceso", "titulo": t, "convocante": c}
    autonomicos = [loc("bop:3", "Bases de una plaza de Monitor de Danzas Tradicionales", benissa),
                   loc("bop:1", "Bases de una plaza de Profesor de Música", benissa),
                   loc("bop:2", "Bases de una plaza de Profesor de Ballet", benissa),
                   loc("bop:9", "Bases para la selección de un Técnico Medio de Gestión Cultural",
                       {"tipo": None, "nombre": "Diputación Provincial Alicante", "provincia": "Alicante"})]
    ps = {p["id"]: p for p in construir(boe, date(2026, 10, 29), autonomicos)}
    assert [o["id"] for o in ps["boe:B1"]["otras_publicaciones"]] == ["bop:1"]
    assert [o["id"] for o in ps["boe:B2"]["otras_publicaciones"]] == ["bop:2"]
    assert [o["id"] for o in ps["boe:B3"]["otras_publicaciones"]] == ["bop:3"]
    assert [o["id"] for o in ps["boe:D1"]["otras_publicaciones"]] == ["bop:9"]


def test_clave_de_organismo_por_boletin():
    from motor.procesos import clave_convocante
    madrid = clave_convocante({"fuente": "BOCM", "ambito": "autonomico", "organismo": "Consejería de Sanidad"})
    cantabria = clave_convocante({"fuente": "BOC-CANT", "ambito": "autonomico", "organismo": "Consejería de Sanidad"})
    assert madrid != cantabria
    # Las universidades convocan en el BOE y publican en su comunidad: la misma clave
    assert clave_convocante({"fuente": "BOE", "ambito": "universidad", "departamento": "Universidad de Salamanca"}) == \
        clave_convocante({"fuente": "BOCYL", "ambito": "universidad", "organismo": "Universidad de Salamanca"})


def test_misma_resolucion_en_el_boe_y_en_su_comunidad_y_melilla():
    """La Universidad de Córdoba publica la misma resolución en el BOE y en el BOJA con otra redacción (y el BOE y el
    BOJA ponen «Universidades» como organismo): un solo proceso. El BOE anuncia Melilla como local y sus bases
    salen en el BOME (autonómico)."""
    boe = [_acto("U1", "2023-04-18", "convocatoria", ambito="universidad", departamento="UNIVERSIDADES",
                 titulo="Resolución de 12 de abril de 2023, de la Universidad de Córdoba, por la que se convoca proceso "
                        "selectivo para la provisión, por el sistema general de acceso libre, de plazas de Técnico "
                        "Especialista de Laboratorio."),
           _acto("U2", "2023-04-20", "convocatoria", ambito="universidad", departamento="UNIVERSIDADES",
                 titulo="Resolución de 12 de abril de 2023, de la Universidad de Sevilla, por la que se convocan "
                        "pruebas selectivas de Técnico Especialista de Laboratorio."),
           _acto("M1", "2026-04-07", "apertura_plazo",
                 convocante={"tipo": "Ayuntamiento", "nombre": "Melilla", "provincia": "Melilla"},
                 boletines_citados=[{"boletin": "Boletín Oficial de la Ciudad de Melilla", "fecha": "2026-02-24",
                                     "papel": "bases"}])]
    autonomicos = [
        {"id": "boja:1", "fecha": "2023-04-18", "fuente": "BOJA", "tipo_acto": "convocatoria", "ambito": "universidad",
         "alcance": "acceso", "organismo": "Universidades",
         "titulo": "Resolución de 12 de abril de 2023, de la Universidad de Córdoba, por la que se convoca proceso "
                   "selectivo para el ingreso, por el sistema general de acceso libre, Grupo C1."},
        {"id": "bome:1", "fecha": "2026-02-24", "fuente": "BOME", "tipo_acto": "convocatoria", "ambito": "autonomico",
         "alcance": "acceso", "titulo": "Orden nº 0543 relativa a convocatoria de dos plazas de Arquitecto"}]
    ps = {p["id"]: p for p in construir(boe, date(2026, 10, 29), autonomicos)}
    assert set(ps) == {"boe:U1", "boe:U2", "boe:M1"}
    assert [o["id"] for o in ps["boe:U1"]["otras_publicaciones"]] == ["boja:1"]
    assert [o["id"] for o in ps["boe:M1"]["otras_publicaciones"]] == ["bome:1"]


def test_bases_sin_cita_del_mismo_ayuntamiento_y_puesto():
    """El DOGC anuncia las bases que publicó el BOPB y el BOE cita solo el BOPB: las del DOGC van con el anuncio del
    BOE del mismo ayuntamiento y puesto de los 180 días siguientes, si es el único; si hay dos, no."""
    conv = {"tipo": "Ayuntamiento", "nombre": "Santa Margarida i els Monjos", "provincia": "Barcelona"}
    boe = [_acto("B1", "2022-09-24", "apertura_plazo", convocante=conv,
                 plazas=[{"numero": 2, "puesto_clave": "policia-local"}],
                 boletines_citados=[{"boletin": "Boletín Oficial de la Provincia de Barcelona", "fecha": "2022-09-12",
                                     "papel": "bases"}])]
    otro = {"tipo": "Ayuntamiento", "nombre": "Artés", "provincia": "Barcelona"}
    boe += [_acto(f"A{i}", "2023-04-24", "apertura_plazo", convocante=otro,
                  plazas=[{"numero": 1, "puesto_clave": "arquitecto"}]) for i in (1, 2)]
    loc = lambda i, f, t, c: {"id": i, "fecha": f, "fuente": "DOGC", "tipo_acto": "convocatoria", "ambito": "local",
                              "alcance": "acceso", "titulo": t, "convocante": c}
    autonomicos = [loc("dogc:1", "2022-09-22", "ANUNCIO sobre publicación en el BOPB de las bases de dos plazas de "
                                               "agente de la policía local", conv),
                   loc("dogc:2", "2023-01-12", "ANUNCIO sobre las bases de una plaza de arquitecto", otro)]
    ps = {p["id"]: p for p in construir(boe, date(2026, 10, 29), autonomicos)}
    assert [o["id"] for o in ps["boe:B1"]["otras_publicaciones"]] == ["dogc:1"]
    assert "dogc:2" in ps and not ps["boe:A1"]["otras_publicaciones"] and not ps["boe:A2"]["otras_publicaciones"]


def test_bases_sin_cita_solo_las_mas_recientes():
    """Dos convocatorias del mismo ayuntamiento y puesto antes de un solo anuncio del BOE: solo la última es suya (y su
    repetición en otro boletín); la anterior queda como proceso aparte."""
    conv = {"tipo": "Ayuntamiento", "nombre": "Santa Margarida i els Monjos", "provincia": "Barcelona"}
    boe = [_acto("B1", "2022-09-24", "apertura_plazo", convocante=conv,
                 plazas=[{"numero": 2, "puesto_clave": "policia-local"}])]
    loc = lambda i, f, fu: {"id": i, "fecha": f, "fuente": fu, "tipo_acto": "convocatoria", "ambito": "local",
                            "alcance": "acceso", "convocante": conv,
                            "titulo": "ANUNCIO sobre las bases de dos plazas de agente de la policía local"}
    autonomicos = [loc("dogc:1", "2022-04-02", "DOGC"), loc("dogc:2", "2022-09-02", "DOGC"),
                   loc("bopb:2", "2022-08-30", "BOPB")]
    ps = {p["id"]: p for p in construir(boe, date(2026, 10, 29), autonomicos)}
    assert sorted(o["id"] for o in ps["boe:B1"]["otras_publicaciones"]) == ["bopb:2", "dogc:2"]
    assert "dogc:1" in ps


def test_datos_de_las_bases_en_el_proceso(tmp_path):
    import json
    from motor.procesos import anadir_datos_de_bases
    f = tmp_path / "2026" / "boe_BOE-A-2026-1.json"
    f.parent.mkdir(parents=True)
    f.write_text(json.dumps({"proceso": "boe:BOE-A-2026-1", "documento": {"id": "x", "url": "u"}, "no_son_bases": False,
                             "campos": {"tasa_euros": {"valor": 15, "cita": "15,00 euros", "nivel": "literal"}}}))
    ps = [{"id": "boe:BOE-A-2026-1"}, {"id": "boe:BOE-A-2026-2"}]
    assert anadir_datos_de_bases(ps, tmp_path) == 1
    assert ps[0]["datos_bases"]["campos"] == {"tasa_euros": {"valor": 15, "cita": "15,00 euros"}} and "datos_bases" not in ps[1]


def test_completar_con_bases():
    from motor.procesos import completar_con_bases
    p = {"id": "x", "total_plazas": None, "grupo": None, "sistema": None,
         "datos_bases": {"campos": {"plazas_total": {"valor": 2}, "grupo": {"valor": "Subgrupo C2"},
                                    "sistema": {"valor": "Concurso-oposición libre"}}}}
    completar_con_bases(p)
    assert (p["total_plazas"], p["grupo"], p["sistema"]) == (2, "C2", "concurso-oposicion")
    assert p["desde_bases"] == ["total_plazas", "grupo", "sistema"]
    q = {"id": "y", "total_plazas": 5, "grupo": "A1", "sistema": "oposicion",
         "datos_bases": {"campos": {"plazas_total": {"valor": 2}, "grupo": {"valor": "E / agrupaciones profesionales"}}}}
    completar_con_bases(q)
    assert (q["total_plazas"], q["grupo"]) == (5, "A1") and "desde_bases" not in q
    r = {"id": "z", "datos_bases": {"campos": {"grupo": {"valor": "Agrupaciones Profesionales"}}}}
    completar_con_bases(r)
    assert r["grupo"] == "AP"


def test_bases_del_bop_y_su_anuncio_en_el_dogc_son_un_proceso():
    from motor.procesos import construir
    bellvei = {"tipo": "Ayuntamiento", "nombre": "Bellvei", "provincia": "Tarragona"}
    bases = _acto("bopt:BOPT-2026-06227", "2026-07-02", "convocatoria", fuente="BOPT", convocante=bellvei,
                  titulo="Borsa de treball d'administratiu/iva. Bases i convocatòria.",
                  plazo={"dias": 20, "tipo": "habiles", "cuenta_desde": "Diari Oficial de la Generalitat de Catalunya"})
    anuncio = _acto("dogc:1049484", "2026-07-10", "convocatoria", fuente="DOGC", convocante=bellvei,
                    titulo="Edicto relativo a la convocatoria para constituir una bolsa de trabajo de administrativo/a",
                    plazo={"dias": 20, "tipo": "habiles", "cuenta_desde": "Diario Oficial de la Generalitat de Cataluña",
                           "fin_estimado": "2026-08-07"})
    otro = _acto("bopt:BOPT-2026-07001", "2026-07-05", "convocatoria", fuente="BOPT",
                 convocante={"tipo": "Ayuntamiento", "nombre": "Cunit", "provincia": "Tarragona"},
                 titulo="Bases de la convocatòria d'una plaça d'arquitecte")
    ps = {p["id"]: p for p in construir([], date(2026, 7, 20), [bases, anuncio, otro])}
    assert set(ps) == {"bopt:BOPT-2026-06227", "bopt:BOPT-2026-07001"}
    p = ps["bopt:BOPT-2026-06227"]
    assert p["estado"] == "plazo_abierto" and p["plazo"]["fin_estimado"] == "2026-08-07"
    # con otra bolsa del mismo ayuntamiento y puesto en esos días, no se sabe cuál es: cada una por su lado
    segunda = {**bases, "id": "bopt:BOPT-2026-06300", "fecha": "2026-07-06"}
    ps = {p["id"] for p in construir([], date(2026, 7, 20), [bases, segunda, anuncio])}
    assert "dogc:1049484" in ps


def test_plazo_de_la_publicacion_local_con_origen_en_el_boe():
    from motor.procesos import _proceso, fuente_de_computo
    assert fuente_de_computo("Boletín Oficial del Estado o Diari Oficial de la Generalitat de Catalunya") is None
    assert fuente_de_computo("Diari Oficial de la Generalitat de Catalunya") == "DOGC"
    boe = _acto("B1", "2026-10-20", "convocatoria", fuente="BOE", convocante={"tipo": "Ayuntamiento", "nombre": "Mijas",
                                                               "provincia": "Málaga"}, plazo={})
    bop = _acto("bopma:1", "2026-09-01", "bases", fuente="BOP-MALAGA",
                plazo={"dias": 20, "tipo": "habiles", "fin_estimado": "2026-09-29",
                       "cuenta_desde": "Boletín Oficial de la Provincia"})
    # el BOE no dice el plazo y las bases del BOP calculan su fin desde el BOP: el plazo corre desde el BOE
    assert _proceso(boe, [], [bop], date(2026, 10, 29), "boe:B1")["estado"] == "sin_datos_de_plazo"
    # si el BOE dice que cuenta desde el BOP, sí
    remite = {**boe, "plazo": {"dias": 20, "tipo": "habiles", "cuenta_desde": "Boletín Oficial de la Provincia de Málaga"}}
    assert _proceso(remite, [], [bop], date(2026, 10, 29), "boe:B1")["plazo"]["de_acto"] == "bopma:1"
    # con origen local (bases del BOP sin plazo), el anuncio en el boletín de la comunidad
    bases = {**bop, "id": "bopma:2", "plazo": {}}
    boja = _acto("boja:3", "2026-09-10", "convocatoria", fuente="BOJA",
                 plazo={"dias": 20, "tipo": "habiles", "fin_estimado": "2026-10-08"})
    assert _proceso(bases, [], [boja], date(2026, 10, 29), "bopma:2")["plazo"]["de_acto"] == "boja:3"


def test_pareja_bop_autonomico_del_mismo_municipio():
    from motor.procesos import pares_bop_autonomico
    plazo = {"dias": 20, "tipo": "habiles", "cuenta_desde": "Diario Oficial de Castilla-La Mancha"}
    anuncio = _acto("docm:1", "2026-07-10", "convocatoria", fuente="DOCM", titulo="Convocatoria de una plaza de peón",
                    convocante={"tipo": "Ayuntamiento", "nombre": "Castejón"})
    de_cuenca = _acto("bopcu:1", "2026-07-01", "bases", fuente="BOPCU", titulo="Bases de una plaza de peón", plazo=plazo,
                      convocante={"tipo": "Ayuntamiento", "nombre": "Castejón", "provincia": "Cuenca"})
    de_navarra = {**de_cuenca, "id": "bon:1", "fuente": "BON",
                  "convocante": {"tipo": "Ayuntamiento", "nombre": "Castejón", "provincia": "Navarra"}}
    assert pares_bop_autonomico([anuncio, de_cuenca])["docm:1"][1]["id"] == "bopcu:1"
    # el mismo nombre en otra comunidad no es el mismo ayuntamiento
    assert pares_bop_autonomico([anuncio, de_navarra]) == {}


def test_plazo_que_aun_no_ha_empezado():
    from motor.procesos import _proceso
    a = _acto("boib:1", "2026-03-10", "convocatoria", fuente="BOIB",
              plazo={"tipo": "fechas", "inicio": "2027-01-04", "fin_estimado": "2027-01-24", "fin_exacto": True})
    assert _proceso(a, [], [], date(2026, 10, 31), "boib:1")["estado"] == "plazo_por_abrir"
    assert _proceso(a, [], [], date(2027, 1, 10), "boib:1")["estado"] == "plazo_abierto"


def test_plazo_desde_la_fecha_del_boletin_que_cita_el_boe():
    from motor.boe.extraer import extraer_local
    from motor.procesos import _proceso
    texto = ("En el «Boletín Oficial de la Provincia de Barcelona», de 11 de marzo de 2026, se han publicado las bases "
             "que han de regir la convocatoria para proveer:\nUna plaza de Técnico/a Medio/a, por el sistema de "
             "concurso-oposición, en turno libre.\nSe ha publicado, asimismo, un extracto de la convocatoria en el «Diari "
             "Oficial de la Generalitat de Catalunya» número 9635, de 30 de marzo de 2026.\nEl plazo de presentación de "
             "solicitudes será de veinte días hábiles a contar desde el siguiente al de la publicación en el «Diari "
             "Oficial de la Generalitat de Catalunya».")
    loc = extraer_local(texto, "2026-04-20")
    assert loc["plazo"]["cuenta_desde"] == "Diari Oficial de la Generalitat de Catalunya"
    a = _acto("BOE-A-2026-8091", "2026-04-20", "apertura_plazo", fuente="BOE", plazo=loc["plazo"],
              boletines_citados=loc["boletines_citados"],
              convocante={"tipo": "Ayuntamiento", "nombre": "Sabadell", "provincia": "Barcelona"})
    p = _proceso(a, [], [], date(2026, 4, 21), "boe:BOE-A-2026-8091")
    assert p["plazo"]["cuenta_desde_fecha"] == "2026-03-30" and p["plazo"]["fin_estimado"] == "2026-04-29"  # Viernes Santo y Lunes de Pascua (Cataluña)
    assert p["estado"] == "plazo_abierto"


def test_plazo_desde_la_publicacion_enlazada_de_ese_boletin():
    from motor.procesos import _proceso
    a = _acto("BOE-A-2026-15714", "2026-08-10", "apertura_plazo", fuente="BOE",
              plazo={"dias": 20, "tipo": "habiles", "cuenta_desde": "Diari Oficial de la Generalitat de Catalunya"},
              convocante={"tipo": "Ayuntamiento", "nombre": "Sabadell", "provincia": "Barcelona"})
    dogc = _acto("dogc:1", "2026-08-03", "convocatoria", fuente="DOGC")  # sin texto: sin plazo propio
    p = _proceso(a, [], [dogc], date(2026, 8, 20), "boe:BOE-A-2026-15714")
    assert p["plazo"]["cuenta_desde_fecha"] == "2026-08-03" and p["estado"] == "plazo_abierto"


def test_boletin_en_gallego_y_por_siglas():
    from motor.procesos import fuente_de_boletin
    assert fuente_de_boletin("Boletín Oficial da Provincia de Pontevedra") == "BOP-PONTEVEDRA"
    assert fuente_de_boletin("BOP de Lugo") == "BOP-LUGO"
    assert fuente_de_boletin("BOP de Barcelona") == "BOPB"


def test_puestos_que_casan_en_castellano_y_catalan():
    from motor.procesos import _puestos_casan
    assert _puestos_casan({"oficial-segona"}, {"oficial-segunda"})
    assert _puestos_casan({"arquitecto-tecnico-como-funcionario-carrera"}, {"arquitecto-tecnico"})
    assert _puestos_casan({"tecnica-administracio-general"}, {"tecnico-administracion-general"})
    assert not _puestos_casan({"administrativo"}, {"auxiliar-administrativo"})
    assert not _puestos_casan({"profesor-adjunto"}, {"profesor-adjunto-percusion"})


def test_convocante_del_titulo_cuando_el_guardado_es_la_seccion():
    from motor.autonomicos.actos import convocante_del_titulo
    g = {"nombre": "Ayuntamientos", "organismo": "Ayuntamientos", "tipo": None, "provincia": None}
    c = convocante_del_titulo({"convocante": g, "titulo": "Anuncio de 15 de mayo de 2026, del Ayuntamiento de Mengíbar, "
                                                          "por el que se aprueban las bases"})
    assert c["tipo"] == "Ayuntamiento" and c["nombre"] == "Mengíbar"
    assert convocante_del_titulo({"convocante": {"nombre": "Utiel"}, "titulo": "del Ayuntamiento de Mengíbar"}) is None
