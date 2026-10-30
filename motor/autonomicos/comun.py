"""Piezas comunes de los conectores de boletines autonómicos.

Cada conector conoce el formato de su boletín; lo que es igual para todos vive aquí:
  - clasificación del anuncio (tipo de acto, modalidad, alcance) con las mismas reglas que el BOE;
  - selección de anuncios locales de empleo público por el título;
  - convocante a partir del organismo («AYUNTAMIENTO DE MIRANDA DE EBRO (BURGOS)»);
  - escritura reproducible de ficheros JSON Lines;
  - descarga de textos pendientes con límite de tiempo, pausa entre peticiones y guardado del original.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Iterable
from datetime import date
from pathlib import Path

from motor.archivo import Archivo
from motor.boe.clasificar import REGLAS_ACTO, REGLAS_MODALIDAD, _primera, alcance, normalizar
from motor.http import obtener
from motor.limpieza import titulo_sin_nombres

# Castellano, catalán/valenciano y gallego (texto normalizado: sin tildes y en minúscula). «Plaça» sola no cuenta:
# también es la plaza de un pueblo («plaça de l'Ajuntament»).
RE_EMPLEO_LOCAL = re.compile(
    r"\b(plazas?|convocatoria|bases|seleccion|bolsa|oposicion|concurso|proceso selectivo|personal|funcionari\w*|"
    r"laboral fij\w*|empleo publico|oferta\w* (?:\w+ ){0,3}de empleo|tribunal|aspirantes|"
    r"places|seleccio|borsa|oposicio|concurs|proces selectiu|proces de seleccio|ocupacio publica|"
    r"oferta\w* (?:\w+ ){0,3}d'ocupacio|aspirants|prazas?|persoal|emprego publico|oferta\w* (?:\w+ ){0,3}de emprego)\b")
RE_NO_EMPLEO = re.compile(
    r"\b(subvencion\w*|licencias?|urbanis\w*|ordenanzas? (?:fiscal\w*|reguladora\w*|municipal\w*|general\w*|de)|presupuesto\w*|expropiacion\w*|contratacion de (?:obras|servicios|suministro)\w*|"
    r"licitacion\w*|ayudas?|premios?|becas?|cuenta general|padron|tasas?|impuestos?|proyectos? de obras?|"
    r"ejecucion de (?:las )?obras|remodelacion|relacion de puestos de trabajo|viviendas?|alquiler\w*|"
    r"subvencio\w*|llicencies?|llicencia\b|ordenances? (?:fiscal\w*|reguladora\w*|municipal\w*|general\w*|de)|pressupost\w*|expropiacio\w*|"
    r"contractacio de (?:les )?(?:obres|serveis|subministra)\w*|licitacio\w*|ajuts?|premis?|beques?|compte general|"
    r"padro|taxes|impostos?|projectes? d'obres?|execucio de (?:les )?obres|relacio de llocs de treball|"
    r"habitatges?|lloguer\w*|jutge\w*(?:/\w+)? de pau|(?:juez|jueces)\w*(?:/\w+)? de paz|bonos?|bons|campanas?|campanyes|campanya|"
    r"comercio\w*|comerc|entidad\w* colaborador\w*|entitat\w* col·laborador\w*|fomento del consumo|consum local|"
    r"licenza\w*|orzamento\w*|axudas?|bolsas? de estudos?|vivendas?|xuiz\w* de paz)\b")
# Para boletines con todas las secciones mezcladas (BOP de Alicante, Valencia, Ciudad Real, Tenerife, SAGA) solo hay
# título. Es anuncio de empleo público si (a) trae una expresión inequívoca, o (b) nombra un puesto y un trámite de
# selección («BASES CONVOCATORIA TÉCNICO/A MEDIO/A INDUSTRIAL»), y en ambos casos no es de un asunto ajeno (taxi,
# concursos de fiestas, cargos políticos, plantilla o RPT…). Revisado el 30/10/2026 sobre 55.368 títulos reales de los
# BOP de Alicante y Valencia (tests/test_empleo_estricto.py recoge los casos).
RE_EMPLEO_FUERTE = re.compile(
    r"\b(plazas?|plz|places|placa|prazas?|oposicion\w*|oposicio\w*|concurso[- ]oposicion|concurs[- ]oposicio|"
    r"procesos? selectiv\w*|proces\w* selectiu\w*|proces\w* de seleccio|procesos? de seleccion|"
    r"procedimientos? selectiv\w*|procediment\w* selectiu\w*|"
    r"pruebas selectivas|proves selectives|probas selectivas|proves de seleccio|curso selectivo|curs selectiu|"
    r"bolsas? (?:de )?(?:empleo|trabajo|trabajadores|emprego|traballo)|bors(?:a|es) (?:de treball|d'ocupacio|d'aspirants|de personal)|"
    r"funcionari\w*|personal laboral|laboral (?:fij|temporal)\w*|"
    r"oferta\w* (?:\w+ ){0,3}(?:de |d')?(?:empleo|ocupacio|emprego)|empleo publico|ocupacio publica|emprego publico|oep|"
    r"emplead\w* public\w*|empleats? public\w*|"
    r"estabiliza\w*|estabilitza\w*|consolidacion de empleo|"
    r"tribunal(?:es)? (?:calificador|qualificador|cualificador|de seleccion|seleccionador)|"
    r"(?:composicion|designacion|nombramiento|constitucion|miembros|composicio|designacio)\w* (?:del |de los |dels )?tribunal|"
    r"aspirantes|aspirants|admitid\w+ (?:y|e) excluid\w+|admes\w+ i exclos\w+|admitid[oa]s|excluid[oa]s|"
    r"incluid[oa]s y excluid[oa]s|"
    r"(?:primer|segundo|tercer|unico|1er|2o)\w* ejercicio|ejercicio (?:practico|teorico|unico|de la fase)|"
    r"(?:primer|segon|tercer|unic) exercici|exercici (?:practic|teoric|unic)|"
    r"(?:fecha|lugar|hora|data|lloc)\w* (?:\w+ ){0,4}(?:examen|ejercicio|exercici|prueba|prova|entrevista)|"
    r"nombramiento|nomenament|nomeamento|toma de posesion|presa de possessio|"
    r"puestos? de trabajo|llocs? de treball|postos? de traballo|"
    r"seleccion de personal|seleccio de personal|interin\w*|interi|policia local|agente\w* de (?:la )?policia|"
    r"libre designacion|lliure designacio|comision de servicios?|comissio de serveis|concurso de meritos|concurs de merits|"
    r"concurso\w* (?:\w+ ){0,2}(?:de )?(?:traslados|provision)|mejora de empleo|millora d'ocupacio|promocion interna|"
    r"promocio interna|turno de movilidad|torn de mobilitat|contratacion (?:laboral )?(?:temporal )?de personal|"
    r"contractacio (?:laboral )?(?:temporal )?de personal)\b")
# Un puesto de trabajo con nombre propio (o su escala, grupo o categoría)
RE_PUESTO = re.compile(
    r"\b(tecnic[oa]?s?|tecniques|auxiliar\w*|aux|administrativ\w*|administratiu\w*|adm|conserje\w*|conserge\w*|"
    r"ordenanza\w*|subaltern\w*|peon\w*|peo|operari\w*|oficial\w* (?:de )?(?:primera|segunda|1a|2a|policia|"
    r"mantenimiento|servicios|obras|jardineria|electricista|fontanero|conductor|albanil|pintor|carpintero)|ofic|"
    r"encargad\w*|encarregat\w*|capataz\w*|jardiner\w*|electricista\w*|fontaner\w*|albanil\w*|mecanic[oa]s?|"
    r"conductor\w*|chofer\w*|limpiador\w*|netejador\w*|cocinero\w*|cuiner\w*|monitor\w*|educador\w*|maestr[oa]s?|"
    r"mestres?|profesor\w*|professor\w*|docent\w*|psicolog[oa]s?|trabajador\w* social\w*|treballador\w* social\w*|"
    r"traballador\w* socia\w*|conserxe\w*|axentes?|limpador\w*|condutor\w*|asesor\w* (?:xuridic|juridic)\w*|"
    r"arquitect\w*|aparejador\w*|ingenier\w*|enginyer\w*|delineant\w*|informatic[oa]s?|programador\w*|analista\w*|"
    r"letrad\w*|lletrat\w*|abogad\w*|advocat\w*|tag|tae|secretari[oa]s?|interventor\w*|tesorer[oa]s?|"
    r"tresorer[ae]?s?|recaudador\w*|inspector\w*|intendent\w*|escala\w*|subescala\w*|subgrup\w*|grupo [abce][12]?|"
    r"grup [abce][12]?|agentes?|agent|policias?|bomber\w*|socorrista\w*|vigilant\w*|alguacil\w*|agutzil\w*|"
    r"sepulturer\w*|operador\w*|telefonist\w*|recepcionist\w*|bibliotecari\w*|arxiver\w*|archiver\w*|"
    r"documentalist\w*|animador\w*|dinamitzador\w*|dinamizador\w*|aedl|adl|promotor\w*|orientador\w*|mediador\w*|"
    r"enfermer\w*|infermer\w*|medic[oa]s?|metges?|fisioterapeut\w*|logoped\w*|terapeut\w*|gerocultor\w*|cuidador\w*|"
    r"veterinari\w*|farmaceutic\w*|quimic[oa]s?|biolog[oa]s?|economista\w*|periodista\w*|traductor\w*|"
    r"jefe\w*|cap de (?:servei|seccio|negociat|brigada|area|policia|grup)|coordinador\w*|gestor\w*|gerente\w*|"
    r"director\w* (?:de la |del |de )?(?:escuela|escola|conservatorio|museo|museu|banda|centro|area)|directiv\w*|"
    r"sanitari[oa]s?|bedel\w*|informador\w*|administrador\w*|ayudante\w*|ajudant\w*|volante\w*|personal)\b")
# Un trámite de selección o provisión. Ni «ejercicio» (también es el año presupuestario) ni «calificación» (también
# es urbanística).
RE_TRAMITE = re.compile(
    r"\b(convoca\w*|bases|llista\w*|lista\w*|listado\w*|relacion\w* (?:provisional|definitiva|de aprobados)|"
    r"relacio\w* (?:provisional|definitiva|d'aprovats)|seleccion\w*|seleccio\w*|cubrir|cobertura|provision\w*|"
    r"provisio\w*|bolsa|borsa|borses|tribunal|nombra\w*|nomena\w*|proces\w*|procedimiento|vacante\w*|examen\w*|"
    r"prueba\w*|proves|aprobados|aprovats|baremacion|meritos|merits|contratacion|contractacio)\b")
# Asuntos ajenos al empleo público que también usan «bases», «convocatoria», «concurso» o «nombramiento»
RE_NO_EMPLEO_TITULO = re.compile(
    r"\b(taxis?|auto-?taxi|euro-?taxi|vtc|certamen\w*|carnaval\w*|disfra\w*|reinas?|falleras?|moros y cristianos|"
    r"deportistas?|huerto\w*|concurso\w* (?:\w+ ){0,4}(?:fotograf\w*|cartel\w*|pintura|relato\w*|poesia|literari\w*|"
    r"belen\w*|escaparat\w*|carroza\w*|dibujo\w*|portada\w*|decoracion|calles|gastronom\w*|tapas|cocina|ideas|logotipo|"
    r"paellas?|tarjetas?|creacion|video\w*|cortos?)|"
    r"concurs\w* (?:\w+ ){0,4}(?:fotograf\w*|cartell\w*|pintura|relat\w*|poesia|literari\w*|betlem\w*|aparador\w*|"
    r"carross\w*|dibuix\w*|portada\w*|decoracio|carrers|gastronom\w*|logotip|paell\w*|videos?|curts|difusio)|"
    r"tenientes? de alcald\w*|tinents? d'alcald\w*|tenencias? de (?:la )?alcaldia|tinencies? d'alcaldia|"
    r"alcald\w* accidental|delegacion\w* de (?:competencias|atribuciones|funciones)|"
    r"delegacio\w* de (?:competencies|atribucions|funcions)|"
    r"personal eventual|funcionari\w* eventual|emple\w* eventual|eventual\w* de confianza|cargos? de confianza|"
    r"cap de gabinet|jefe de gabinete|dedicacion (?:exclusiva|parcial)|dedicacio (?:exclusiva|parcial)|"
    r"regimen de dedicacion|cargos? con (?:derecho a )?(?:retribucion|dedicacion)|"
    r"retribucion\w* (?:de )?(?:los )?(?:cargos|miembros|concejal\w*)|indemnizacion\w* por asistencia|"
    r"grupos? politic\w*|grups? politic\w*|carrera profesional|carrera professional|evaluacion del desempeno|"
    r"productividad|productivitat|certificado de capacitacion|certificat d'aptitud|pacto de alcaldes|"
    r"juez\w* de paz|jutges? de pau|declaracion\w* (?:\w+ ){0,3}bienes|declaracio\w* (?:\w+ ){0,3}bens|"
    r"registro de intereses|miembros de la corporacion|corporacion municipal|membres de la corporacio|"
    r"convenios? (?:\w+ )?(?:de )?colaboracion|convenios? interadministrativ\w*|conveni\w* (?:\w+ )?(?:de )?col·laboracio|"
    r"conveni\w* interadministratiu\w*|adhesion|adhesio|acuerdo[- ]marco|acord marc|"
    r"(?:compartir|utilizacion|uso|utilitzacio|us) (?:\w+ ){0,3}(?:bolsas?|borses?|borsa)|objetos perdidos|"
    r"mesa de contratacion|mesa de contractacio|organos? de contratacion|organs? de contractacio|"
    r"unidad tecnica de valoracion|credito\w*|credits?|tresoreria|romanent|remanente\w*|"
    r"plan\w* parcial\w*|plans parcials|planeamiento|planejament|parcel\w*|reparcel\w*|estudio de detalle|"
    r"estudi de detall|modificacion puntual|modificacio puntual|calificacion juridica|qualificacio juridica|"
    r"emplazamiento\w*|juzgado\w*|contencioso\w*|grupos municipales|grups municipals|cargos publicos|carrecs publics|"
    r"amortiza\w*|amortitza\w*|"
    # Subvenciones (Base de Datos Nacional de Subvenciones) y formación para desempleados
    r"bdns|certificados? de profesionalidad|certificats? de professionalitat|certificados? de aptitud profesional|cualificacion inicial de (?:los )?conductores)\b")
# Cambios de organización (reglamentos, plantilla, RPT, catálogo): no son un proceso, salvo que traigan sus bases
RE_ORGANIZACION = re.compile(
    r"\b(reglamento\w*|reglament\w*|ordenanzas?|ordenan(?:ç|c)a|ordenances|complemento especifico|complement especific|"
    r"(?:modificacion|modificacio|aprobacion|aprovacio|valoracion|valoracio|"
    r"actualizacion|actualitzacio|correccion|exposicion|exposicio|creacion|creacio)\w* (?:\w+ ){0,4}(?:plantilla|rpt|"
    r"r\.p\.t|relacion (?:de )?(?:los )?puestos|relacio de llocs|catalogo (?:de )?puestos|puestos? de trabajo|"
    r"llocs? de treball)|catalogo (?:de )?puestos|plantilla (?:de )?personal(?: \w+)? (?:eventual|\d{4}|anualidad))\b")
RE_BASES_DE_PROCESO = re.compile(r"\b(bases|convoca\w*|procesos? selectiv\w*|proces\w* selectiu\w*|estabiliza\w*|"
                                 r"estabilitza\w*|provision|provisio)\b")
# Sin un puesto con nombre, «plazas» o «nombramiento» pueden ser de otra cosa
RE_CONTEXTO_NO_EMPLEO = re.compile(
    r"\b(aparcamiento\w*|garaje\w*|plaza de toros|placa de bous|plaza mayor|placa major|vados?|escoleta\w*|"
    r"guarderia\w*|alumn\w*|matricula\w*|admision\w* de (?:alumnos|ninos)|residencia\w*|centro de dia|centre de dia|"
    r"mercado\w*|mercat\w*|mercadillo\w*|fiestas?|festes|feria\w*|fira|kiosco\w*|quiosco\w*|caseta\w*|nichos?|"
    r"sepultura\w*|usuari\w*|socios?|plazas? (?:libres|disponibles) (?:en|para)|escuela de verano|escola d'estiu|"
    r"campamento\w*|colonias|actividades|activitats|cursos?|talleres?|tallers?|inscripcion\w*|inscripcio\w*|"
    r"representante\w*|consejo\w*|consell\w*|patronato\w*|patronat\w*|junta de gobierno|junta de govern|"
    r"convenio colectivo|conveni col·lectiu|conveni collectiu|mesa general de negociacion|"
    r"concejal\w*|regidor\w*|alcalde\w*|alcaldessa|portavoz\w*|portaveu\w*|exalcald\w*|president\w*|"
    r"vicepresident\w*|calles?|carrers?|espacios publicos|denominacion\w*|honores|honors|medallas?|cronista\w*|"
    r"predilect\w*|adoptiv\w*|organos colegiados|organs col·legiats|organs collegiats|vehiculos?|vehicles?|"
    r"terrass\w*|terrazas?|veladores?|reduccion horaria|reduccio horaria|organismo autonomo|organisme autonom|"
    r"portavoc\w*|aparcament\w*|parquing\w*|parking|organos?|organs?|"
    # Plazas de ganado o de instalaciones («instalación porcina de cebo, ampliación hasta 5212 plazas», BON)
    r"impacto ambiental|autorizacion ambiental|instalacion\w* (?:porcin|ganader|avicol|bovin)\w*|"
    r"explotacion\w* (?:porcin|ganader|avicol|bovin)\w*|ugm|cabezas de ganado)\b")

RE_RESULTADO = re.compile(
    r"\b(funcionari[oa]s? de carrera|personal laboral fijo|proceso selectivo|pruebas selectivas|aspirantes|"
    r"funcionari\w*(?:/\w+)? de carrera|personal laboral fix|proces selectiu|proves selectives|aspirants|"
    r"funcionari[oa]s? de carreira|persoal laboral fixo|probas selectivas)\b")

PARTICULAS = {"de", "del", "la", "las", "los", "el", "y", "e", "en", "a", "o"}

TIPOS_ENTIDAD = (
    ("ayuntamiento de ", "Ayuntamiento"),
    ("diputacion provincial de ", "Diputación Provincial"),
    ("diputacion de ", "Diputación Provincial"),
    ("mancomunidad ", "Mancomunidad"),
    ("comunidad de villa y tierra ", "Comunidad de Villa y Tierra"),
    ("consorcio ", "Consorcio"),
    ("junta vecinal ", "Junta Vecinal"),
    ("entidad local menor ", "Entidad Local Menor"),
    ("entidad local autonoma de ", "Entidad Local Autónoma"),
    ("consejo comarcal ", "Consejo Comarcal"),
    ("comarca ", "Comarca"),
    ("cabildo insular de ", "Cabildo Insular"),
    ("consell insular de ", "Consell Insular"),
    ("patronato ", "Patronato"),
    ("concejo abierto de ", "Concejo Abierto"),  # Cantabria
    ("concejo de ", "Concejo"),  # Navarra
    ("parroquia rural de ", "Parroquia Rural"),  # Asturias
    # Catalán y valenciano
    ("ajuntament del ", "Ayuntamiento", "el "),
    ("ajuntament dels ", "Ayuntamiento", "els "),
    ("ajuntament de ", "Ayuntamiento"),
    ("ajuntament d'", "Ayuntamiento"),
    ("diputacio de ", "Diputación Provincial"),
    ("diputacio provincial de ", "Diputación Provincial"),
    ("consell comarcal del ", "Consejo Comarcal"),
    ("consell comarcal de ", "Consejo Comarcal"),
    ("consell comarcal d'", "Consejo Comarcal"),
    ("mancomunitat ", "Mancomunidad"),
    ("consorci ", "Consorcio"),
    ("entitat municipal descentralitzada de ", "Entidad Local Menor"),
    ("entitat municipal descentralitzada d'", "Entidad Local Menor"),
    ("area metropolitana de ", "Área Metropolitana"),
    ("ajuntament ", "Ayuntamiento"),  # «AJUNTAMENT ALDEA, L'» (BOP de Tarragona)
    # Gallego
    ("concello da ", "Ayuntamiento", "A "),
    ("concello do ", "Ayuntamiento", "O "),
    ("concello das ", "Ayuntamiento", "As "),
    ("concello dos ", "Ayuntamiento", "Os "),
    ("concello de ", "Ayuntamiento"),
    ("deputacion provincial de ", "Diputación Provincial"),
    ("deputacion de ", "Diputación Provincial"),
)


RE_GENERO_TITULO = re.compile(r"/(?:as?|es|os?|da|ra|na|la)\b")


def clasificar(titulo: str, apartado: str | None = None) -> dict:
    """Tipo de acto, modalidad y alcance con las mismas reglas que se aplican al BOE."""
    t = RE_GENERO_TITULO.sub("", normalizar(titulo or ""))  # «admitidos/as y excluidos/as»
    modalidad = _primera(REGLAS_MODALIDAD, t)
    return {"tipo_acto": _primera(REGLAS_ACTO, t) or "otro", "modalidad": modalidad,
            "alcance": alcance(t, modalidad, apartado)}


# Expresiones que solo se usan para procesos de selección o provisión. Mandan sobre las exclusiones por tema
# («técnico de urbanismo», «Consejería de Vivienda», «tasa de reposición», «plaza de ordenanza»): el 30/10/2026 había
# unos 4.900 títulos así descartados entre todas las fuentes. Solo no mandan si el asunto son ayudas, premios o becas
# y no se nombra ningún puesto («entidades admitidas y excluidas de la convocatoria de subvenciones»).
RE_SELECCION_INEQUIVOCA = re.compile(
    r"\b(procesos? selectiv\w*|proces\w* selectiu\w*|procedimientos? selectiv\w*|pruebas selectivas|proves selectives|"
    r"probas selectivas|concurso[- ]oposicion|concurs[- ]oposicio|oposicion (?:libre|por turno)|"
    r"bolsas? de (?:trabajo|empleo)|bors(?:a|es) de treball|bolsas? de emprego|admitid\w+ y excluid\w+|"
    r"admes\w+ i exclos\w+|tribunal (?:calificador|qualificador|cualificador)|"
    r"oferta (?:de empleo|publica de empleo|d'ocupacio|publica d'ocupacio|de emprego|publica de emprego)|"
    r"funcionari\w* de carrer\w*|personal laboral fix\w*|persoal laboral fixo|"
    r"provision (?:\w+ ){0,3}(?:del |de )?puestos? de trabajo|provisio (?:\w+ ){0,3}(?:del |de )?llocs? de treball|"
    r"libre designacion|lliure designacio|libre designacion|concurso (?:especifico )?de meritos|"
    r"concurs (?:especific )?de merits|estabiliza\w* (?:\w+ ){0,3}empleo|estabilitza\w* (?:\w+ ){0,3}ocupacio)\b")
RE_AYUDAS = re.compile(r"\b(subvenci\w*|ayudas?|ajuts?|axudas?|premios?|premis|becas?|beques|licencias? por estudios|"
                       r"entidades|entitats|candidaturas)\b")


# Las tasas por participar en pruebas selectivas son ordenanzas fiscales, no procesos
RE_FISCAL = re.compile(r"\b(ordenan\w* fiscal\w*|ofr|imposicion y ordenacion|tasas? (?:\w+ ){0,4}(?:pruebas|procesos|"
                       r"derechos de examen|examen)|tax\w* (?:\w+ ){0,3}(?:processos|proves|drets d'examen)|"
                       r"derechos de examen)\b")


def _seleccion_inequivoca(t: str) -> bool:
    if not RE_SELECCION_INEQUIVOCA.search(t) or RE_FISCAL.search(t):
        return False
    if RE_AYUDAS.search(t):
        return any(m.group(0) != "personal" for m in RE_PUESTO.finditer(t))
    return True


def es_empleo_por_titulo(titulo: str) -> bool:
    t = normalizar(titulo or "").replace("´", "'")
    if _seleccion_inequivoca(t):
        return True
    return bool(RE_EMPLEO_LOCAL.search(t)) and not RE_NO_EMPLEO.search(t)




# «Administrativo» que no es un puesto: entidades («Junta Administrativa de Anda», concejos de Álava) y trámites
# («autorización administrativa previa», «vía contencioso-administrativa»)
RE_ADMINISTRATIVO_NO_PUESTO = re.compile(
    r"\b(juntas? administrativas?|autorizaci\w+ administrativ\w+|via administrativa|sancion\w* administrativ\w*|"
    r"unidad\w* administrativ\w*|contencioso[- ]administrativ\w*|procedimientos? administrativ\w*|"
    r"expedientes? administrativ\w*|concesion\w* administrativ\w*|silencio administrativo|"
    r"actos? administrativ\w*|resolucion\w* administrativ\w*)\b")


def es_empleo_estricto(titulo: str) -> bool:
    """Selección por título en boletines sin sección de personal (todos los anuncios mezclados)."""
    t = normalizar(titulo or "").replace("_", " ").replace("´", "'").replace("`", "'").replace("’", "'")
    t = RE_GENERO_TITULO.sub("", t)  # «treballador/a social», «técnico/a medio/a»
    t = RE_ADMINISTRATIVO_NO_PUESTO.sub(" ", t)
    if RE_NO_EMPLEO_TITULO.search(t):
        return False
    if _seleccion_inequivoca(t):
        return True
    if RE_ORGANIZACION.search(t) and not RE_BASES_DE_PROCESO.search(t):
        return False
    fuerte = RE_EMPLEO_FUERTE.search(t)
    if fuerte and any(m.group(0) != "personal" for m in RE_PUESTO.finditer(t)) and not (RE_AYUDAS.search(t) or
                                                                                       RE_FISCAL.search(t)):
        return True  # «Nomeamento de funcionario interino administrativo … rexistro-padrón»
    if RE_NO_EMPLEO.search(t):
        return False
    puesto = RE_PUESTO.search(t)
    if RE_EMPLEO_FUERTE.search(t):
        return bool(puesto) or not RE_CONTEXTO_NO_EMPLEO.search(t)
    return bool(puesto and RE_TRAMITE.search(t))


def es_resultado(titulo: str) -> bool:
    return bool(RE_RESULTADO.search(normalizar(titulo or "")))


def nombre_propio(texto: str) -> str:
    """«MIRANDA DE EBRO» -> «Miranda de Ebro». Respeta tildes y partículas. Si ya viene en minúsculas y
    mayúsculas («L'Arboç», «Betxí»), se deja como está."""
    if not texto.isupper():
        return texto
    palabras = []
    for i, w in enumerate(texto.lower().split()):
        if i and w in PARTICULAS:
            palabras.append(w)
        else:
            palabras.append("-".join(p[:1].upper() + p[1:] for p in w.split("-")))
    return " ".join(palabras)


RE_ARTICULO_DETRAS = re.compile(r"^(?P<n>.+?),\s*(?P<a>L['’]|El|La|Els|Les|Los|Las|Es|Sa|Ses|O|A|Os|As)$", re.IGNORECASE)


def articulo_delante(nombre: str) -> str:
    """«Aldea, L'» -> «L'Aldea»; «Masnou, El» -> «El Masnou» (forma del INE con el artículo detrás)."""
    m = RE_ARTICULO_DETRAS.match(nombre or "")
    if not m:
        return nombre
    art = m.group("a")
    art = art[0].upper() + art[1:].lower()
    return f"{art}{m.group('n')}" if art.endswith(("'", "’")) else f"{art} {m.group('n')}"


RE_PARENTESIS = re.compile(r"^(?P<nombre>.+?)\s*\((?P<provincia>[^()]+)\)\s*$")


def convocante_de_organismo(organismo: str, capitales: Iterable[str] = ()) -> dict | None:
    """«AYUNTAMIENTO DE MIRANDA DE EBRO (BURGOS)» -> tipo, nombre y provincia.

    capitales: nombres de municipio que son capital de provincia (el boletín no repite la provincia).
    """
    o = " ".join((organismo or "").split())
    if not o:
        return None
    m = RE_PARENTESIS.match(o)
    base, provincia = (m.group("nombre"), m.group("provincia")) if m else (o, None)
    siglas = None
    if provincia and not _es_provincia(provincia):
        # «Instituto Municipal de Turismo de Córdoba (IMTUR)»: entre paréntesis van las siglas, no la provincia
        siglas, provincia = provincia, None
    n = normalizar(base).replace("’", "'")
    for prefijo, tipo, *articulo in TIPOS_ENTIDAD:
        if n.startswith(prefijo):
            nombre = (articulo[0] if articulo else "") + nombre_propio(base[len(prefijo):].strip())
            nombre = articulo_delante(nombre)
            nombre = nombre[:1].upper() + nombre[1:]  # «Ajuntament de la Garriga» -> «La Garriga»
            if provincia:
                prov = nombre_propio(provincia)
            elif tipo == "Diputación Provincial" or normalizar(nombre) in {normalizar(c) for c in capitales}:
                prov = nombre
            else:
                prov = None
            return {"tipo": tipo, "nombre": nombre, "provincia": prov, "organismo": o}
    return {"tipo": None, "nombre": nombre_propio(base), "provincia": nombre_propio(provincia) if provincia else None,
            "organismo": o, **({"siglas": siglas} if siglas else {})}


def _es_provincia(texto: str) -> bool:
    from motor.catalogo.territorio import provincia  # aquí para no cargar el catálogo al importar
    return provincia(texto) is not None


class Freno:
    """Para la carga si la fuente falla varias veces seguidas (bloqueo, caída, cambio de formato): no se insiste
    contra un servidor que no responde bien y se reintenta en la siguiente ejecución. Los días con error no se dan
    por hechos, así que vuelven a pedirse."""

    FALLOS = {"error_http", "error_formato", "fuente_inaccesible"}

    def __init__(self, max_seguidos: int = 8):
        self.max_seguidos, self.seguidos = max_seguidos, 0

    def anotar(self, informe: dict) -> bool:
        self.seguidos = self.seguidos + 1 if informe.get("resultado") in self.FALLOS else 0
        if self.seguidos >= self.max_seguidos:
            print(f"::warning::{self.seguidos} fallos seguidos ({informe.get('resultado')}: "
                  f"{'; '.join((informe.get('alertas') or [])[:1])}); se para y se reintenta en la próxima ejecución")
            return True
        return False


def escribir_jsonl(ruta: Path, filas: list[dict]) -> None:
    """Escribe las filas; el nombre de una persona en el título (nombramientos, notificaciones) se sustituye."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    filas = [{**f, "titulo": titulo_sin_nombres(f["titulo"])} if f.get("titulo") else f for f in filas]
    ruta.write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in filas), encoding="utf-8")


def leer_jsonl(ruta: Path) -> list[dict]:
    if not ruta.exists():
        return []
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]


def escribir_json(ruta: Path, datos: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


def descargar_textos(pendientes: list[dict], destino: Callable[[dict], Path], url: Callable[[dict], str],
                     extraer: Callable[[bytes], dict], archivo: Archivo, fuente: str, max_minutos: float,
                     pausa: float, accept: str = "application/xml", ext: str = "xml",
                     formulario: Callable[[dict], dict] | None = None, sesion=None,
                     por_registro: bool = False, renovar_sesion: Callable[[], object] | None = None
                     ) -> tuple[int, int]:
    """Descarga y limpia los textos de la lista. Devuelve (hechos, errores). Reanudable: lo hecho queda escrito.

    formulario: para las API que piden el documento por POST, los campos de cada petición.
    por_registro: extraer recibe también el registro (p. ej. para no guardar el texto de una lista de personas).
    renovar_sesion: para portales que caducan la sesión (responden 400): abre otra y repite una vez.
    """
    inicio, hechos, errores = time.monotonic(), 0, 0
    for x in pendientes:
        if max_minutos and (time.monotonic() - inicio) / 60 > max_minutos:
            break
        u = url(x)
        try:
            r = obtener(u, accept=accept, formulario=formulario(x) if formulario else None, sesion=sesion)
            if r.status == 400 and renovar_sesion:
                sesion = renovar_sesion()
                r = obtener(u, accept=accept, formulario=formulario(x) if formulario else None, sesion=sesion)
        except ConnectionError:
            errores += 1
            continue
        if r.status != 200:
            errores += 1
            time.sleep(pausa)
            continue
        try:
            datos = extraer(r.contenido, x) if por_registro else extraer(r.contenido)
        except Exception:  # un documento mal formado no detiene la carga; queda pendiente para revisarlo
            errores += 1
            continue
        captura = archivo.guardar(fuente + "-texto", date.fromisoformat(x["fecha"]), r.contenido, u, ext, r.status,
                                  r.cabeceras)
        escribir_json(destino(x), {"id": x["id"], **datos, "captura_sha256": captura["sha256"],
                                   "capturado": captura["capturado"], "url": u})
        hechos += 1
        time.sleep(pausa)
    return hechos, errores
