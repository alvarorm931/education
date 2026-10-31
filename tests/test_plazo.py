"""Plazo de solicitudes con frases literales de convocatorias reales del BOE (2025-2026)."""

from datetime import date

from motor.calendario import fin_de_plazo_meses
from motor.extraccion.plazo import extraer_plazo

BOE = "Boletín Oficial del Estado"


def test_dias_habiles_desde_el_boe():
    t = ("4.6 Las personas interesadas dispondrán de un plazo de presentación de solicitudes de veinte días hábiles "
         "contados a partir del día siguiente al de la fecha de publicación de esta convocatoria en el «Boletín "
         "Oficial del Estado».\n5.1 Expirado el plazo de presentación de solicitudes, el órgano convocante dictará "
         "resolución, en el plazo máximo de un mes, por la que declarará aprobada la lista provisional.")
    p = extraer_plazo(t, "2026-10-20", BOE)
    assert p["dias"] == 20 and p["tipo"] == "habiles" and p["cuenta_desde"] == BOE
    assert p["fin_estimado"] == "2026-11-17" and p["fin_exacto"] is False
    assert p["cita"].startswith("4.6 Las personas interesadas")


def test_dias_naturales_y_quince_siguientes():
    t = ("Las solicitudes para la participación en el concurso se presentarán en el plazo de veinte días naturales, "
         "contados a partir del siguiente al de la publicación del presente concurso en el «Boletín Oficial del Estado».")
    assert extraer_plazo(t, "2026-10-15", BOE)["fin_estimado"] == "2026-11-04"
    t = ("3.2 La presentación de solicitudes se hará en el plazo de los quince días hábiles siguientes a la publicación "
         "de esta convocatoria en el «Boletín Oficial del Estado».")
    p = extraer_plazo(t, "2026-10-16", BOE)
    assert p["dias"] == 15 and p["fin_estimado"] == "2026-11-06"


def test_otro_boletin_no_da_fecha_de_fin():
    t = ("El plazo de presentación de solicitudes será de quince días hábiles computados a partir del día siguiente "
         "al de la publicación de la presente orden en el «Diario Oficial de Galicia».")
    p = extraer_plazo(t, "2026-03-02", BOE)
    assert p["cuenta_desde"] == "Diario Oficial de Galicia" and "fin_estimado" not in p
    # Con el boletín propio sí: el mismo texto leído en el DOG
    assert extraer_plazo(t, "2026-03-02", "Diario Oficial de Galicia")["fin_estimado"] == "2026-03-23"
    # Dos boletines a la vez («BOE o BOJA»): depende del último, sin fecha de fin
    t = ("3.1 El plazo de presentación de solicitudes será de veinte días hábiles contados a partir del siguiente al de "
         "la publicación de la convocatoria en el «Boletín Oficial del Estado» o en el «Boletín Oficial de la Junta de "
         "Andalucía», si esta fuera posterior.")
    assert "fin_estimado" not in extraer_plazo(t, "2026-05-04", BOE)


def test_fechas_escritas_en_el_texto():
    t = ("El plazo para la presentación de solicitudes de participación es del 28 de octubre al 24 de noviembre de "
         "2025, ambos incluidos.")
    p = extraer_plazo(t, "2025-10-27", BOE)
    assert (p["inicio"], p["fin_estimado"], p["fin_exacto"]) == ("2025-10-28", "2025-11-24", True)
    t = ("El plazo de presentación de solicitudes será de diez días hábiles contados desde el día 19 de marzo de 2026, "
         "finalizando, por tanto, el referido plazo, el 1 de abril de 2026.")
    p = extraer_plazo(t, "2026-03-18", BOE)
    assert p["fin_estimado"] == "2026-04-01" and p["fin_exacto"] is True


def test_inicio_explicito():
    t = ("La presentación de solicitudes deberá realizarse en el plazo de veinte días hábiles contados a partir del día "
         "1 de octubre de 2026.")
    p = extraer_plazo(t, "2026-06-15", BOE)
    assert p["inicio"] == "2026-10-01" and p["fin_estimado"] == "2026-10-29"


def test_frases_que_no_son_el_plazo_de_solicitudes():
    for t in (
        "Podrá admitirse la renuncia a la participación en el concurso dentro del plazo de presentación de instancias "
        "y durante los diez días hábiles subsiguientes a la terminación de dicho plazo.",
        "Las personas aspirantes dispondrán de un plazo de diez días hábiles, contados a partir del día siguiente al de "
        "publicación de la relación de aspirantes que han superado la fase de oposición, para presentar la "
        "documentación.",
        "Esta resolución no implica nuevo cómputo ni ampliación de plazo de presentación de solicitudes.",
    ):
        assert extraer_plazo(t, "2026-10-01", BOE) is None


def test_meses():
    assert fin_de_plazo_meses(date(2026, 1, 31), 1) == date(2026, 3, 2)   # 28/02 es sábado
    t = "El plazo de presentación de solicitudes será de un mes a contar desde el día siguiente al de su publicación."
    p = extraer_plazo(t, "2026-10-29", BOE)
    assert p["tipo"] == "meses" and p["cuenta_desde"] == "su publicación" and p["fin_estimado"] == "2026-11-30"


# --- Catalán, valenciano y gallego; boletines sin comillas y por siglas ---------------------------------------
BOPB = ("Butlletí Oficial de la Província de Barcelona", "Boletín Oficial de la Provincia de Barcelona")
DOGC = ("Diari Oficial de la Generalitat de Catalunya", "Diario Oficial de la Generalitat de Cataluña")


def test_catalan_cuenta_desde_otro_boletin_sin_comillas():
    # Literal del BOPB de 28/10/2026 (CVE 202610159101): el plazo cuenta desde el DOGC, no desde el BOPB
    t = ("Havent-se aprovat per Resolució d’Alcaldia núm. 2433, de 14 d’octubre de 2026, les Bases reguladores i la "
         "convocatòria de les proves selectives per a la provisió en propietat d’una plaça de caporal/a de la policia "
         "local, es fa públic el present anunci i s’obre el termini de presentació de sol·licituds, que serà de 20 dies "
         "hàbils comptats a partir de l’endemà de la publicació d’aquest anunci en el Diari Oficial de la Generalitat "
         "de Catalunya:")
    p = extraer_plazo(t, "2026-10-28", BOPB)
    assert (p["dias"], p["tipo"], p["cuenta_desde"]) == (20, "habiles", "Diari Oficial de la Generalitat de Catalunya")
    assert "fin_estimado" not in p
    assert extraer_plazo(t, "2026-10-28", DOGC)["fin_estimado"] == "2026-11-25"


def test_catalan_siglas_y_fechas():
    t = ("El termini de presentació de sol·licituds és de vint dies naturals a comptar de l'endemà de la publicació "
         "d'aquest anunci al BOPB.")
    p = extraer_plazo(t, "2026-10-28", BOPB)
    assert p["cuenta_desde"] == "Butlletí Oficial de la Província de Barcelona" and p["fin_estimado"] == "2026-11-17"
    t = "El termini de presentació de sol·licituds serà del 3 al 24 de novembre de 2026, ambdós inclosos."
    p = extraer_plazo(t, "2026-10-28", BOPB)
    assert (p["inicio"], p["fin_estimado"], p["fin_exacto"]) == ("2026-11-03", "2026-11-24", True)


def test_valenciano_y_gallego():
    t = ("El termini de presentació d'instàncies serà de quinze dies hàbils, a comptar des de l'endemà de la "
         "publicació d'aquest anunci en el Butlletí Oficial de la Província de València.")
    p = extraer_plazo(t, "2026-10-28", ("Butlletí Oficial de la Província de València",
                                        "Boletín Oficial de la Provincia de Valencia"))
    assert p["dias"] == 15 and p["fin_estimado"] == "2026-11-18"
    t = ("O prazo de presentación de solicitudes será de vinte días hábiles contados a partir do día seguinte ao da "
         "publicación desta convocatoria no Diario Oficial de Galicia.")
    p = extraer_plazo(t, "2026-03-02", "Diario Oficial de Galicia")
    assert p["dias"] == 20 and p["fin_estimado"] == "2026-03-30"


def test_castellano_sin_comillas_desde_el_boe():
    # Bases en un boletín provincial: el plazo empieza con el extracto en el BOE (sin comillas en el texto)
    t = ("El plazo de presentación de solicitudes será de veinte días naturales a contar desde el día siguiente al de "
         "la publicación del extracto de la convocatoria en el Boletín Oficial del Estado.")
    p = extraer_plazo(t, "2026-10-28", "Boletín Oficial de la Provincia de Granada")
    assert p["cuenta_desde"] == "Boletín Oficial del Estado" and "fin_estimado" not in p
    # «Recursos Humanos» no es un recurso administrativo: no descarta la frase
    t = ("Las solicitudes se dirigirán a la Subdirección General de Recursos Humanos y se presentarán en el plazo de "
         "quince días hábiles, a contar desde el siguiente al de la publicación de la presente convocatoria en el "
         "«Boletín Oficial del Estado».")
    assert extraer_plazo(t, "2025-11-25", BOE)["fin_estimado"] == "2025-12-17"


def test_frase_partida_tras_una_abreviatura():
    # BOE-A-2026-8173: «Sra. Rectora» partía la frase y la parte del plazo no decía que era de solicitudes
    t = ("Las solicitudes se dirigirán a la Sra. Rectora Magnífica de la Universidad y se presentarán en el plazo de "
         "veinte días hábiles, a contar desde el siguiente al de la publicación de la presente convocatoria en el "
         "«Boletín Oficial del Estado».")
    r = extraer_plazo(t, "2026-04-13", BOE)
    assert r["dias"] == 20 and r["tipo"] == "habiles" and r["fin_estimado"]


def test_numero_entre_parentesis_y_fin_con_fecha():
    t = ("El plazo de presentación de solicitudes será de veinte (20) días naturales contados a partir del día siguiente "
         "al de la publicación de esta resolución en el «Boletín Oficial del Estado».")
    r = extraer_plazo(t, "2026-04-20", BOE)
    assert r["dias"] == 20 and r["tipo"] == "naturales" and r["fin_estimado"] == "2026-05-11"  # el 10 es domingo
    r = extraer_plazo("El plazo de presentación de solicitudes finaliza el día 27 de enero de 2025.", "2025-01-13", BOE)
    assert r["fin_estimado"] == "2025-01-27" and r["fin_exacto"]


def test_exclusion_solo_cerca_del_plazo():
    # CGPJ: la frase sigue con «… de la provisión de plazas de nombramiento discrecional», que no es del plazo
    t = ("Las solicitudes para la participación en el concurso se presentarán en el plazo de veinte días naturales, "
         "contados a partir del siguiente al de la publicación del presente concurso en el «Boletín Oficial del Estado», "
         "y contendrán los requisitos previstos en el artículo 326.2 de la Ley Orgánica del Poder Judicial y concordantes "
         "del Reglamento 1/2010, de 25 de febrero de 2010, que regula la provisión de plazas de nombramiento "
         "discrecional en los órganos judiciales.")
    assert extraer_plazo(t, "2025-01-27", BOE)["fin_estimado"]
    # la subsanación, en cambio, va junto al plazo
    t = ("Las personas excluidas dispondrán de un plazo de diez días hábiles, contados a partir del siguiente al de la "
         "publicación, para subsanar el defecto de su solicitud.")
    assert extraer_plazo(t, "2025-01-27", BOE) is None


def test_boletin_citado_detras_del_plazo():
    dogc = "Diari Oficial de la Generalitat de Catalunya"
    t = ("Les bases s'han publicat íntegrament en el Butlletí Oficial de la Província núm. 85 de 6 de maig de 2026 i el "
         "termini de presentació d'instàncies serà de 20 dies hàbils a partir de l'endemà del present anunci en el DOGC.")
    r = extraer_plazo(t, "2026-05-15", dogc)
    assert r["cuenta_desde"] == dogc and r["fin_estimado"]


def test_la_frase_con_fecha_de_fin_antes_que_la_incompleta():
    t = ("Las instancias se podrán presentar durante el plazo de presentación de solicitudes que se indique. "
         "Ordenar su publicación, concediendo un plazo de 10 días hábiles para presentar las solicitudes, contados a "
         "partir del día siguiente al de la publicación de este anuncio en el Boletín Oficial de la Provincia de Sevilla.")
    r = extraer_plazo(t, "2026-10-15", "Boletín Oficial de la Provincia de Sevilla")
    assert r["dias"] == 10 and r["fin_estimado"]


def test_boletin_propio_con_otro_nombre_o_generico():
    t = ("El plazo de presentación de solicitudes será de diez días hábiles, contados a partir del día siguiente al de la "
         "publicación de esta convocatoria en el Boletín Oficial Cantabria.")
    assert extraer_plazo(t, "2025-05-07", "Boletín Oficial de Cantabria")["fin_estimado"]
    t = ("El plazo de presentación de instancias será de diez días hábiles, a contar desde el siguiente al de la publicación "
         "de este anuncio en el Boletín Oficial de la Provincia.")
    assert extraer_plazo(t, "2026-03-02", "Boletín Oficial de la Provincia de Sevilla")["fin_estimado"]
    # en un boletín autonómico, «el Boletín Oficial de la Provincia» es otro boletín
    r = extraer_plazo(t, "2026-03-02", "Diari Oficial de la Generalitat de Catalunya")
    assert r["dias"] == 10 and not r.get("fin_estimado")


def test_frases_sin_plazo_o_sin_solicitud():
    boib = "Butlletí Oficial de les Illes Balears"
    t = "Plazo\nEl plazo es de quince días hábiles, a contar a partir del día siguiente al de la publicación de la convocatoria en el BOIB."
    assert extraer_plazo(t, "2026-03-02", boib)["dias"] == 15
    t = ("Las personas interesadas en participar en la convocatoria disponen de 15 días naturales para presentar la "
         "solicitud, contados a partir del día siguiente a la publicación de esta resolución en el BOIB.")
    assert extraer_plazo(t, "2026-03-02", boib)["fin_estimado"]
    # lo que no es el plazo de solicitudes, aunque cuente desde una publicación
    for t in ("Las personas relacionadas deberán presentar la documentación en el plazo de 10 días hábiles contados desde "
              "el siguiente al de la publicación de la presente resolución en el BOIB.",
              "La formalización del contrato deberá realizarse en el plazo de un mes a partir del día siguiente de su "
              "publicación en el BOIB.",
              "El presente acuerdo podrá ser recurrido potestativamente en reposición en el plazo de un mes a contar desde "
              "el día siguiente al de su publicación."):
        assert extraer_plazo(t, "2026-03-02", boib) is None, t


def test_correccion_donde_dice_debe_decir():
    t = ("Se realiza la siguiente corrección.\nDonde dice:\nSiendo el plazo de presentación de instancias de veinte días "
         "hábiles contados desde el siguiente al de la publicación de este anuncio en el Boletín Oficial del Estado.\n"
         "Debe decir:\nSiendo el plazo de presentación de instancias de veinte días hábiles contados desde el siguiente "
         "al de la publicación de este anuncio en el Boletín Oficial de la Provincia.")
    r = extraer_plazo(t, "2026-07-15", "Boletín Oficial de la Provincia de Badajoz")
    assert r["cuenta_desde"] == "Boletín Oficial de la Provincia" and r["fin_estimado"]
    t = ("Forma e prazo de presentación de instancias, onde dí: “no prazo de vinte días naturais contados desde o día "
         "seguinte ao da publicación no Boletín Oficial do Estado”, debe dicir: “O prazo de presentación de solicitudes "
         "será de vinte días naturais contados desde o día seguinte ao da publicación no Boletín Oficial da Provincia”.")
    r = extraer_plazo(t, "2026-03-02", "Boletín Oficial da Provincia da Coruña")
    assert r and "Estado" not in r["cuenta_desde"]


def test_tratamiento_al_final_de_linea_y_vigencia():
    t = ("Las instancias solicitando tomar parte en el concurso-oposición, dirigidas al Sr.\nAlcalde-Presidente del "
         "Ayuntamiento, se presentarán en el Registro General durante el plazo de diez días naturales, contados a partir "
         "del siguiente al de la publicación de la convocatoria en el Boletín Oficial de la Provincia.")
    assert extraer_plazo(t, "2026-05-15", "Boletín Oficial de la Provincia de Zamora")["fin_estimado"]
    t = ("Quienes deseen concursar presentarán sus solicitudes en el Registro General, o en la forma establecida en la "
         "Ley 30/1992 –cuya vigencia deriva de la disposición derogatoria única de la Ley 39/2015– en el plazo de veinte "
         "días naturales contados a partir del siguiente al de la publicación del presente acuerdo en el «Boletín Oficial "
         "del Estado».")
    assert extraer_plazo(t, "2025-12-01", "Boletín Oficial del Estado")["fin_estimado"]
    t = "La vigencia de la bolsa será de dos años a contar desde la publicación de la lista en el Boletín Oficial del Estado."
    assert extraer_plazo(t, "2025-12-01", "Boletín Oficial del Estado") is None


def test_nombre_del_boletin_sin_la_frase_siguiente():
    t = ("Se abre el plazo de presentación de solicitudes, que será de veinte días naturales a contar desde el día "
         "siguiente a la publicación de este anuncio en Boletín Oficial de la Provincia de Teruel Se adjuntan las bases "
         "reguladoras que regirán la convocatoria:")
    r = extraer_plazo(t, "2026-02-02", "Boletín Oficial de la Provincia de Teruel")
    assert r["cuenta_desde"] == "Boletín Oficial de la Provincia de Teruel" and r["fin_estimado"]


def test_boletin_en_minusculas_y_diari_de_la_provincia():
    t = ("Mediante el presente anuncio, se inicia el plazo de presentación de solicitudes, que será de DIEZ DÍAS HÁBILES, "
         "contados a partir del siguiente a aquél en el que se publique el presente anuncio en el boletín oficial de la "
         "provincia.")
    r = extraer_plazo(t, "2026-06-01", "Boletín Oficial de la Provincia de Huelva")
    assert r["cuenta_desde"] == "Boletín Oficial de la Provincia" and r["fin_estimado"]
    t = ("PLAZO DE PRESENTACIÓN DE SOLICITUDES: veinte días hábiles a contar desde el día siguiente al de la publicación "
         "de la convocatoria en el boletín oficial del estado.")
    r = extraer_plazo(t, "2026-06-01", "Boletín Oficial de la Provincia de Granada")
    assert r["cuenta_desde"] == "Boletín Oficial del Estado" and not r.get("fin_estimado")
    t = ("Les sol·licituds s'han de presentar dins el termini de 10 dies hàbils, comptats a partir de l'endemà de la "
         "publicació de l'anunci de la convocatòria al Diari Oficial de la Província de Barcelona.")
    bopb = ("Butlletí Oficial de la Província de Barcelona", "Boletín Oficial de la Provincia de Barcelona")
    assert extraer_plazo(t, "2026-06-01", bopb)["fin_estimado"]
