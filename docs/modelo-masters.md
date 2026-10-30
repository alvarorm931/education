# Módulo de másters: universo, fuentes medidas y ficha

Versión 29/10/2026. Complementa `docs/encargo-masters.md`. Todas las cifras de este documento salen de
descargas reales hechas desde GitHub el 29/10/2026; lo que no está medido se dice.

## 1. El universo: cuántos másters hay y dónde está la lista

No hay un registro único de «todos los másters». Hay cuatro capas, cada una con su fuente.

| Capa | Lista completa | Cuántos | Cómo se conecta |
|---|---|---|---|
| Máster universitario oficial | Sí: catálogo SIIU del Ministerio (por centro) + ficha del RUCT | 4.347 títulos activos (4.166 simples y 181 dobles) en 95 universidades, 4.906 imparticiones activas por centro; 4.859 con extinguidos | XLSX anual, `motor/estudios/catalogo.py` |
| Altas nuevas | Sí: acuerdos del Consejo de Ministros en el BOE, con el código RUCT de cada título | 27 acuerdos entre 2022 y 2026 con 1.425 títulos; 387 no están en el catálogo SIIU de febrero de 2026, de ellos 270 aprobados en septiembre y octubre de 2026 | sumario del BOE ya capturado, `motor/estudios/boe_masters.py` |
| Máster de formación permanente (título propio) | No. No consta obligación de inscribirlos en el RUCT (ver §2, títulos propios) | Sin cifra oficial | catálogo web de cada universidad (95) |
| Máster de escuela de negocio o centro no universitario | No. «Máster» sin título universitario detrás | Sin cifra | web de cada escuela; fuera de la primera versión |

Además hay dos familias de máster oficial fuera de las universidades, que el RUCT lista aparte («Centros
autorizados para impartir Enseñanzas Artísticas Superiores» y «Centros dependientes del Ministerio de
Defensa»): los de enseñanzas artísticas superiores (conservatorios y escuelas superiores; 32 disposiciones
de plan en el BOE entre 2022 y 2026, homologadas por orden ministerial) y los de Defensa (por ejemplo, el
Máster en Ingeniería de Armas Navales). Por verificar si el catálogo SIIU los incluye; de momento no se
cuentan.

### Lo que dice el catálogo oficial (curso 2025-2026)

- Pública 2.855 títulos activos, privada 1.311 (31 %).
- Modalidad por impartición: presencial 3.213, a distancia 851, semipresencial 448, varias 394. En los
  másters simples de la privada, el 44 % de las imparticiones es a distancia (603 de 1.375); en la pública,
  el 7 % (248 de 3.326).
- 562 imparticiones con plan en inglés u otro idioma extranjero.
- Por comunidad: Madrid 982, Cataluña 657, Andalucía 571, C. Valenciana 490, Castilla y León 271,
  La Rioja 207 (192 son de UNIR, la universidad con más másters de España).
- Ramas: Ciencias Sociales y Jurídicas 1.763, Ingeniería y Arquitectura 921, Salud 654, Artes y
  Humanidades 468, Ciencias 360.
- 224 imparticiones en centros adscritos (escuelas de negocio adscritas a una universidad, entre otros).
- **Corrección al encargo:** los dobles másters sí tienen código oficial (familia 75xxxxx, «Estudio
  Conjunto de Máster» en el SIIU). Se usa ese código y no uno propio.
- El código del título indica el régimen: 43xxxxx (RD 1393/2007, 3.657 activos), 35xxxxx (RD 822/2021,
  492), 90xxxxx (10, privadas).

## 2. Qué da cada fuente (medido)

### RUCT: ficha y memoria del título

La ficha (una petición) da créditos por tipo (obligatorios, optativos, prácticas, TFM, complementos), rama,
campo, fechas de verificación y de autorización, **el identificador BOE del acuerdo y del plan**, la comunidad
que lo autoriza y su boletín, la extinción, las renovaciones de la acreditación, los centros con código y el
histórico de memorias.

La memoria vigente (de 15 a 150 peticiones) da lo que hoy se esconde detrás de un formulario, también en las
privadas:

- por centro, la modalidad marcada (presencial, semipresencial/híbrida, a distancia) **con sus plazas** y los
  idiomas de impartición (ejemplo: Análisis de Negocio de Comillas y Deusto, 120 plazas presenciales en
  ICADE, 40 semipresenciales en Advantere, 80 presenciales en Deusto);
- universidades participantes en los títulos conjuntos;
- requisitos de acceso, criterios de admisión con su peso y complementos formativos por titulación de
  origen;
- el plan entero: módulos, materias (ECTS, carácter, semestre o cuatrimestre) y asignaturas (ECTS, carácter,
  semestre);
- catálogo de actividades formativas, metodologías y sistemas de evaluación del título;
- **solo en memorias del formato RD 1393/2007**: por materia, horas de cada actividad con su presencialidad
  y la **ponderación mínima y máxima de cada sistema de evaluación** (ejemplo: Finanzas, Murcia, Políticas
  Macroeconómicas: examen 50-70 %, trabajos 30-50 %). Las memorias del formato RD 822/2021 remiten a un
  PDF del apartado 4.1 que el RUCT no publica.

Precauciones medidas:

- Las páginas de la memoria dependen de la sesión. En la exploración libre el servidor llegó a servir
  páginas de un grado dentro de la sesión de un máster. El conector recorre cada memoria en orden y descarta
  toda página cuya cabecera no sea la del título esperado (prueba en `tests/test_ruct.py`).
- El RUCT tuvo caídas desde GitHub el 29/10/2026 (de 17:28 a 17:55 UTC ninguna ficha respondió). El
  conector se para tras tres fichas seguidas sin respuesta.
- Volumen: fichas de todo el catálogo, unas 4.900 peticiones (81 minutos a una por segundo). Memorias de
  todos los títulos activos, unas 235.000 peticiones (unas 88 horas, medido en §4). **No cabe en los 2.000
  minutos de GitHub**: se ejecuta en el servidor de España, repartido en noches.

### BOE: planes de estudios

- 2022-2026: 1.181 resoluciones de plan nuevo y 859 de modificación de plan de máster, más 27 acuerdos de
  carácter oficial.
- Muestra de 100 planes al azar: 95 con tablas de créditos, 46 con nombre de asignatura, 51 con periodo,
  16 sin filas extraíbles. Las tablas usan celdas combinadas y columnas distintas en cada universidad: los
  créditos por asignatura no son fiables sin cotejo.
- Uso: fuente oficial publicada y control del RUCT. La unión es exacta porque la ficha del RUCT da el
  identificador BOE del plan.

### Precio

- Públicas: precio por crédito fijado por cada comunidad (decreto anual) según sea habilitante o no; el
  anuario del Ministerio da la serie. La UCM, por ejemplo, no da el importe en la ficha y remite a un
  simulador.
- Privadas: **publican tarifas en PDF aunque la ficha comercial pida el teléfono**. Comprobado: Universidad
  Europea de Andalucía (9 másters: reserva 1.100 € y docencia de 8.700 € a 9.420 €), Universidad Alfonso X,
  oferta online (unos 33 másters; Abogacía 8.494 €), Universidad Francisco de Vitoria (27 másters, 21 oficiales y 6
  propios; Ingeniería Industrial 14.280 €).
- Trampa: algunas privadas publican el «precio público por ECTS a efectos de beca» (UDIMA: 28 €/ECTS en
  casi todos sus másters). Es la base de cálculo de la beca del Ministerio, no lo que paga el alumno. Nunca
  se publica como precio.

### Títulos propios

- Sin registro central. El RD 905/2025 exige informe previo del sistema de calidad para llamarlo «Máster de
  Formación Permanente» y limita los créditos propios a dos veces los oficiales; en lo leído (hasta su
  artículo 14) no crea registro ni obligación de comunicarlos. Pendiente de leer el resto del texto.
- La UCM los lista por entidad en `ucm.es/estudios/{curso}/titulo-propio?eid={n}` (ejemplo: 20 másters
  de formación permanente de la Escuela de Gobierno, con modalidad). Cada universidad, un conector.

## 3. La ficha

Unidad: máster × universidad × modalidad (una impartición del catálogo). Si el mismo título se da en dos
centros con distinta modalidad o plazas, son dos fichas con su propia dirección; si solo cambia el centro y
todo lo demás coincide, una ficha con los centros dentro (evita páginas casi iguales, ley SEO).

| Bloque | Dato | Fuente principal | Control |
|---|---|---|---|
| Identidad | nombre, código RUCT, universidad, centro, comunidad, municipio | SIIU + RUCT | BOE acuerdo |
| Tipo | oficial o propio; habilita para profesión regulada; doble máster y sus componentes | RUCT | orden ministerial |
| Estructura | créditos por tipo; módulos, materias y asignaturas con ECTS, carácter y semestre | RUCT memoria | BOE plan |
| Modalidad | presencial, semipresencial, a distancia; plazas de cada una; idiomas | RUCT memoria | SIIU |
| Evaluación | sistemas con ponderación mín./máx. por materia (RD 1393/2007) | RUCT memoria | guía docente |
| Metodología | actividades con horas y presencialidad por materia (RD 1393/2007) | RUCT memoria | guía docente |
| Acceso | requisitos, criterios y su peso, complementos según grado de origen | RUCT memoria | web |
| Precio | total y por crédito; reserva; becas | decreto autonómico / tarifa PDF | web |
| Calidad | verificación, acreditaciones renovadas, modificaciones con fecha | RUCT ficha | BOE |
| Calendario | preinscripción y matrícula | web de la universidad | — |
| Empleo | afiliación por universidad y rama | SIIU | — |

Cada dato lleva fuente, URL y fecha de captura; la fecha solo cambia si cambia el dato.

### Datos mínimos para indexar (ley SEO)

La ley fija para el máster «asignaturas y precio». Con lo medido:

- asignaturas (o materias con ECTS cuando la materia es la asignatura): salen del RUCT en 23 de 23
  memorias medidas (§4);
- precio: públicas, del decreto de su comunidad; privadas, solo si hay tarifa publicada.

Consecuencia: un máster privado sin tarifa encontrada se publica con `noindex` aunque tenga asignaturas y
plazas. Es coherente con la ley; si se quiere indexarlo, hay que cambiar la regla, no saltársela.

## 4. Medición en una muestra al azar (29/10/2026)

28 títulos activos elegidos al azar (14 de universidades públicas y 14 de privadas, semilla fija); en los 28
minutos de la ejecución se leyeron 23 memorias completas (14 públicas y 9 privadas), 1.237 peticiones, sin
errores ni páginas de otro título.

| Dato | Públicas (14) | Privadas (9) | Total (23) |
|---|---|---|---|
| Plan con materias y sus ECTS | 14 | 9 | 23 |
| Asignaturas por debajo de la materia (en el resto, la materia es la asignatura) | 9 | 5 | 14 |
| Plazas por centro | 14 | 9 | 23 |
| Modalidad marcada por centro | 14 | 9 | 23 |
| Requisitos y criterios de admisión (más de 300 caracteres) | 14 | 9 | 23 |
| Evaluación con ponderación por materia | 8 | 3 | 11 |
| Identificador BOE del plan en la ficha | 12 | 7 | 19 |

La evaluación ponderada depende del formato de la memoria, no de la universidad: aparece en 11 de las 13
memorias RD 1393/2007 y en ninguna de las 10 RD 822/2021. Ejemplo privado: Trastornos del Comportamiento
Alimentario y Obesidad (Universidad Europea de Madrid), materia de 6 ECTS: pruebas presenciales 50-55 %,
trabajos 15-20 %, caso 15-20 %, portafolio 10-15 %; 35 horas de clase magistral al 100 % presencial.

Ejemplo de plan privado a distancia: Gestión Empresarial en la Industria Musical (UNIR), 300 plazas a
distancia, cinco materias y nueve asignaturas de 6 ECTS con su semestre, TFM de 12 ECTS.

Precaución: las plazas de la memoria son las **verificadas** (el máximo autorizado y la fecha de la
memoria), no la oferta de cada curso. En la ficha se publican como «plazas verificadas en [año]» y la oferta
anual sale de la web o del fichero de oferta del Ministerio cuando exista.

Coste medido: 54 páginas por memoria de media (públicas 62, privadas 38) y 1,35 segundos por petición
contando la espera. Para los 4.347 títulos activos, unas 235.000 peticiones y unas 88 horas.

## 5. Mapa completo de proveedores (oficiales y no oficiales)

El valor diferencial está en lo que hoy se esconde tras un formulario, sobre todo en los títulos propios y
en los centros privados. Por eso el censo no se limita a las universidades: incluye a todo el que vende un
máster en España.

| Grupo | Cómo se enumera | Conector |
|---|---|---|
| Universidades (activas y sin actividad) y sus centros propios y adscritos | RUCT, 109 grupos | `centros_ruct.py` |
| Centros extranjeros autorizados (Madrid, Cataluña, Andalucía, C. Valenciana, País Vasco, Cantabria, Aragón), enseñanzas artísticas superiores, Defensa, otros centros de nivel universitario | RUCT, grupos propios | `centros_ruct.py` |
| Escuelas y empresas que venden másters de formación permanente expedidos por una universidad | descubrimiento web + la propia universidad cuando publica sus colaboradores (la Isabel I sí; UCAM, UNIR, Nebrija, UC3M no) | `commoncrawl.py`, `rastreador.py` |
| Escuelas de negocio y centros que venden «máster» sin título universitario | descubrimiento web | `commoncrawl.py`, `rastreador.py` |

No hay registro oficial de los dos últimos grupos. Se descubren en el índice público de Common Crawl
(metadatos de URL de miles de millones de páginas, sin descargar contenido ajeno): dominios .es, o
genéricos en español, con rutas de programa de posgrado. Después se descartan agregadores, medios y
dominios de otros países y se verifica cada candidato en su propia web.

Los agregadores (Emagister, Educaweb, masterMania…) no se usan como fuente: su base de datos está
protegida y la ley del proyecto prohíbe copiar. Solo se usa la web de cada centro.

### Medido el 29/10/2026

- **Registro oficial (RUCT), completo**: 109 grupos; 99 universidades (50 públicas y 49 privadas, de ellas
  7 de la Iglesia) y 2.157 centros (1.866 propios y 291 adscritos), 1.639 con web. Además, 18 centros
  extranjeros autorizados por las comunidades (EU Business School, TBS, GBSB, ESCP, CESTE, EADE, CESINE,
  Schiller, Saint Louis…), Defensa y 26 «otros centros de nivel universitario». Agrupados por dominio web,
  352 proveedores oficiales.
- **Common Crawl, dos índices completos (CC-MAIN-2026-43 y 2026-39)**: 112.412 dominios con rutas de
  posgrado con el patrón amplio. Se descartan otros países, páginas sueltas, agregadores y dominios sin
  ninguna URL que nombre un programa (12.275 solo en el primero): quedan 17.630 candidatos, más 1.589
  centros enlazados desde páginas de colaboradores de universidades y escuelas.
- **Verificación en su web, dos barridos** (10.955 y 10.462 objetivos): **1.503 proveedores no oficiales
  verificados** con 90.875 URL de programa; precisión medida a mano en 60 al azar, 67 %: unos 1.000 reales
  (800-1.200). 18.401 candidatos descartados con motivo o pendientes. Detalle en
  `docs/estrategia-informacion-cerrada.md` §9. Censo publicado en sondas: `censo-masters/20261030-final/`.
- **Webs oficiales** (340): 293 responden; 232 con fichas (55.899 URL de programa); vetan el rastreo
  Sevilla, Córdoba y otros tres, y la UOC devuelve 403. Cada máster oficial con su página: 1.576 de 4.347
  unidos, 820 dudosos.
- Lo que enseñan las fichas, en `docs/estrategia-informacion-cerrada.md` §1 (3.679 fichas no
  universitarias y 779 oficiales).

`censo.py` une todo en una tabla de proveedores con identificador propio que no cambia
(`prov-` + huella del dominio), tipos, códigos RUCT, fuentes, señales y estado (oficial, candidato,
verificado, descartado con motivo).

## 6. Modelo de datos: capturas, hechos y fichas

Igual que en oposiciones, tres capas que no se mezclan:

1. **Capturas**: cada página, PDF o ficha descargada, intacta, con huella sha256, URL y fecha.
2. **Hechos**: cada dato extraído (precio, créditos, asignatura, modalidad, plazas, evaluación…) con su
   captura de origen y la frase literal de la que sale. Un dato que cambia es un hecho nuevo con fecha; el
   anterior no se borra.
3. **Fichas**: se recalculan desde los hechos vigentes. Si el extractor mejora, se reprocesa desde las
   capturas.

Identificadores propios que no cambian nunca: proveedor (`prov-…`), programa (proveedor + nombre
normalizado + tipo de título), oferta (programa × sede × modalidad × curso), asignatura (programa +
código de la universidad cuando exista). Los códigos oficiales (RUCT de título y de centro) se guardan como
atributos, no como identificador.

### Extracción de la ficha (`extraer.py`)

De cada página de programa, Claude Haiku en lote devuelve los 26 campos de la ficha (tipo de título y
universidad que lo expide, centro, créditos, duración, modalidad, sedes, idioma, inicio, plazos, horario,
plazas, precio total y por crédito, reserva, becas y descuentos, requisitos, admisión, asignaturas,
prácticas, TFM, metodología, evaluación, habilitación y salidas), cada uno con su frase literal. Sin IA se
comprueba que la frase está en la página y, en los datos numéricos, que el número sale de ella: si no, el
valor no se acepta y va a revisión. La clave (`ANTHROPIC_API_KEY`) está como secreto de GitHub y
`estudios.yml` solo se la pasa al módulo de extracción.

**Prueba real del 30/10/2026** (muestra fija de 50 páginas: 30 de centros no oficiales verificados y 20 de
másters oficiales unidos con su página; `extraer.py lote`, que descarga, envía, espera y comprueba en una
sola ejecución sin guardar ninguna página):

| Tanda | Cambio | Respuestas cortadas | Salida por página | Coste | Datos aceptados / a revisión |
|---|---|---|---|---|---|
| 1 | prompt inicial, 3.000 tokens de salida | 31 de 46 | 2.394 tokens | 0,041157 $ | 36 / 0 |
| 2 | salida compacta, 6.000 tokens | 9 de 48 | 3.668 tokens | 0,058291 $ | 355 / 1 |
| 3 | sin pensamiento adaptativo y esfuerzo bajo | 0 de 45 | 874 tokens | 0,023478 $ | 462 / 15 |

- Claude Haiku 5.5 piensa por defecto y ese pensamiento se cobra como salida: era la causa de los cortes.
  Sin él, en 24 páginas comparables coinciden 252 datos, salen 53 más que pensando (29 solo pensando) y
  descarta mejor lo que no es ficha (vídeos, noticias, páginas sin contenido por JavaScript).
- **Coste real: 0,000522 $ por página** (mediana 0,000465 $; máximo 0,001642 $), con 5.946 tokens de entrada
  y 874 de salida de media. 1.000 páginas, unos 0,52 $; las 2.400 páginas de los másters oficiales ya
  unidos, unos 1,25 $; 40.000 fichas no oficiales, unos 21 $. Después solo se extrae lo que cambia.
- Lo que dan las fichas (muestra pequeña, orientativa): en 21 fichas no oficiales, precio 14, metodología 19,
  asignaturas 15, evaluación 11, plazas 7; de las 14 con formulario de correo, 8 dan el precio igualmente.
  En 12 fichas oficiales, créditos 11 y precio 1 (el precio público sale de los decretos).
- De las 20 páginas «unidas» a un máster oficial, 5 no eran la ficha (un evento, una comisión académica, un
  vídeo, una noticia de 2014, una página sin contenido por JavaScript): la extracción lo detecta
  (`no_es_programa`) y devuelve el máster al emparejado.
- Las citas no se publican en la rama pública: queda su huella sha256 y su longitud hasta tener el archivo
  privado.

Límite que se respeta: solo se lee lo publicado. Si un centro da el folleto o el precio únicamente tras un
formulario, no se rellena el formulario ni se buscan rutas ocultas; la ficha dice «el centro no lo
publica» y enlaza a su web.

## 7. Revisión crítica (29/10/2026, noche)

Regla de trabajo: al cerrar cada pieza, preguntarse si se puede hacer mejor, si da lo que queremos y qué
falta. Lo encontrado al revisar el censo:

1. **El descubrimiento perdía centros.** Contra listas de referencia independientes, el primer patrón
   encontraba 15 de 18 centros conocidos, 6 de 17 extranjeros autorizados, 4 de 9 colaboradores de la
   Isabel I y 6 de 9 escuelas de Forbes. Causas medidas en el índice de Common Crawl: guarda pocas páginas
   de cada sitio (EU Business School, 23; ESHI, 10), muchas páginas no tienen idioma detectado, las
   escuelas internacionales publican en inglés y algunas solo nombran el máster en un parámetro o en el
   blog. Corrección: basta cualquier URL del dominio que hable de máster o posgrado (también catalán,
   euskera, gallego e inglés, y acentos codificados), y quién vende de verdad lo decide el rastreador en el
   sitemap completo de cada web. El recuento contra las listas de referencia queda como prueba fija de
   cobertura.
2. **Ruido en la verificación.** Noticias, blogs y webs de otros países pasaban el filtro. Corrección: la
   página de programa exige cuatro señales de ficha y no estar en rutas de noticia; se añade la señal de
   España (€, ECTS, ciudades, +34) para descartar oferta de otros países. Lo que siga dudoso lo
   clasificará Claude Haiku cuando haya clave de la API.
3. **Webs sin sitemap.** Se quedaban sin programas. Corrección: enlaces de programa de la portada y URL vistas
   en Common Crawl.
4. **Catálogo oficial con retraso.** El catálogo SIIU es de febrero de 2026; el BOE ya publica 270 títulos
   aprobados después. El universo oficial es catálogo + altas del BOE.
5. **Minutos de GitHub (corregido).** El repositorio es público y en los repositorios públicos los
   ejecutores estándar de GitHub son gratuitos («The use of standard GitHub-hosted runners is free: In public
   repositories», documentación de facturación de GitHub Actions, consultada el 29/10/2026). Los 1.012
   minutos del 29/10/2026 no consumen cupo. Límites reales: 58 minutos por tramo en `estudios.yml` y el
   número de trabajos a la vez de la cuenta. Lo que sigue faltando es un archivo privado de originales
   (R2 o el servidor de España): la rama del repositorio es pública y no puede guardar páginas ajenas.
6. **Concurrencia entre conversaciones.** Las pruebas encoladas en el grupo «rama-sondas» se cancelan entre
   sí, también las de oposiciones. Másters usa ya `estudios.yml`, que junta resultados sin ese grupo.
7. **Pendiente:** becas; almacén de originales (R2) antes de la extracción masiva; Excel de oferta de
   plazas, QEDU, órdenes de másters habilitantes y profesiones reguladas de la UE. Hechos el 29/10/2026:
   mapa de guías docentes (`docs/fuentes-guias-docentes.md`), normas de precios públicos 2026-2027
   (`docs/fuentes-precios-publicos.md`) y estudio de normas de información (`docs/fuentes-legales-informacion.md`;
   corrige la vía de la Ley 37/2007, que no sirve con universidades).

## 8. Extracción masiva y censo depurado (30/10/2026, madrugada)

Todo con `estudios.yml` en GitHub (gratis en repositorio público), la API de Claude en lote (Claude Haiku
5.5, sin pensamiento, esfuerzo bajo) y el almacén privado de S3 (`motor/almacen.py`, escritura única).

### Qué se guarda y dónde

| Qué | Dónde | Por qué |
|---|---|---|
| Original de cada página leída, intacto | S3 privado, `web-centros/AAAA/MM/DD/{sha256}.html.gz` | regla de originales; nunca en la rama pública |
| Texto enviado a la API, respuestas y hechos con su cita | S3 privado, `extraccion-masters/…` | la cita es texto ajeno; permite reprocesar y retomar lotes |
| URL, huellas, valores extraídos, coste, clasificación | rama `sondas` (pública) | sin textos ajenos: solo hechos, huellas y claves privadas |

La clave de cada objeto lleva la huella del contenido y toda escritura va con `If-None-Match: *`: nada se
sobrescribe. Una página igual a una ya guardada no se vuelve a escribir.

### Censo depurado con Claude (`clasificar.py`)

Los 1.503 verificados (precisión a mano del 67 %) se clasificaron con su portada y los títulos de sus
fichas, con salida estructurada (`output_config.format`, esquema JSON): **983 centros reales** (953 de
España y 30 internacionales con oferta en España), 187 agregadores (se guardan aparte y no se usan como fuente), 109 medios o blogs, 106 de otro sector, 93 centros sin másters propios y 25 de otro
país. Coincide con la estimación a mano (unos 1.000). Tipos: 354 escuelas de formación, 136 fundaciones o
asociaciones, 111 empresas, 96 academias, 92 escuelas de negocio, 49 universidades, 31 centros adscritos, 27
colegios profesionales. Coste: 0,20 $.

Al barrer los 726 candidatos pendientes y cuatro centros de referencia que faltaban salieron 7
verificados más (CEF entre ellos). ESH no responde; Saera y ThePowerMBA no enseñan fichas a un lector
sin JavaScript: siguen fuera.

### Másters oficiales: unión con su página y extracción

**Fallo encontrado y corregido.** La unión devolvía la clave de comparación (con «/» añadida detrás de
`.html`) en vez de la URL real: en la tanda de prueba, 28 de 40 páginas daban 404 o una página vacía.
Además se perdían los programas que solo cambian en la consulta (`uab.cat/…html?param1=…`). Ahora se
devuelve la URL encontrada, se conservan los parámetros que distinguen un programa y con cada ficha van
hasta 6 subpáginas con precio, plan, acceso u horario. Unión nueva: 1.604 unidos y 837 dudosos.

**Extracción** de 2.978 páginas (2.297 fichas principales y 636 subpáginas, más 45 compartidas): 2.799
enviadas, 1,77 $ (0,00063 $ por página), 10 minutos de descarga y 5 de lote, 6 respuestas ilegibles. 30.912
datos aceptados con cita comprobada y 1.407 a revisión (1.260 por cita no literal, 147 porque el número no
está en la cita). El nombre extraído de la página se compara con el del RUCT (`fichas_masters.py`):

| Resultado | Másters |
|---|---|
| nombre del RUCT confirmado en su página | 1.826 |
| casi igual y la página dice que es oficial | 119 |
| casi igual sin decirlo (dobles másters, programas ejecutivos): no se usa | 21 |
| la página no es la ficha | 259 |
| nombre de otro máster | 16 |
| sin nombre en la página | 28 |

**1.945 de los 4.347 másters activos (45 %) tienen ya ficha con datos comprobados**: 1.219 de públicas y
726 de privadas. Lo que dan sus páginas:

| Campo | Públicas | Privadas |
|---|---|---|
| precio total | 18 % | 23 % |
| asignaturas | 51 % | 83 % |
| plazas | 62 % | 57 % |
| metodología | 44 % | 92 % |
| evaluación | 17 % | 57 % |
| horario | 12 % | 35 % |
| plazo de admisión | 20 % | 39 % |
| becas y descuentos | 9 % | 66 % |
| requisitos de acceso | 62 % | 87 % |

En las privadas el precio es el dato que más se esconde (23 %): es la lista de peticiones al centro. En
las públicas el precio sale de los decretos (`docs/fuentes-precios-publicos.md`), no de la página.

**Control independiente de la extracción**: la modalidad sacada de la página coincide con la del catálogo
oficial del Ministerio (presencial, a distancia, semipresencial, varias) en el 93,3 % de 1.970 másters
oficiales con ficha; parte del 6,7 % restante son cambios reales (la web anuncia una modalidad nueva o el
catálogo es de febrero). Es la cifra de referencia para vigilar que la extracción no empeora.

**Segunda vuelta**: para los másters sin ficha comprobada se extraen sus siguientes candidatas (puntuación de
0,5 o más); el nombre extraído hace de verificador, así que una candidata floja no contamina: o confirma el
nombre del RUCT o se descarta. 1.179 páginas para 794 másters.

### Másters no oficiales y títulos propios

**Tanda 1** (hasta 30 fichas por centro real, de máster primero, sin repetir idioma ni modalidad): 13.005
páginas en tres tramos sin servidores compartidos, 12.575 enviadas, 4,97 $ (0,0004 $ por página); 103.936
datos aceptados y 4.282 a revisión. Resultado: 8.465 fichas de
programa (4.110 páginas no eran ficha), **5.928 programas de máster distintos** y 1.663 de otros títulos
(cursos, expertos). Lo que dan:

| Campo | Fichas no oficiales (8.465) |
|---|---|
| precio total | 57 % |
| metodología | 84 % |
| asignaturas | 60 % |
| evaluación | 41 % |
| horario | 37 % |
| becas y descuentos | 43 % |
| plazas | 14 % |

**Tanda 2**, adaptativa: solo los centros cuyas primeras fichas fueron másters de verdad (al menos el 30 % o
tres), hasta 300 fichas más cada uno, y los 28 centros que entraron con los reintentos de clasificación:
15.089 páginas, 14.534 enviadas (el 29 % no eran ficha).

**Títulos propios en las webs oficiales.** Las escuelas adscritas y las universidades venden másters propios
que no están en el RUCT (Máster en Finanzas de ESIC, Máster Executive en Recursos Humanos del Centro
Garrigues, los del IEB): ni la unión oficial ni la lista de no oficiales los recogía. `extraer.py
lista-propios-oficiales` toma las fichas de máster de esas webs que no son la página de un oficial unido:
34.131 fichas candidatas en 220 webs; primera tanda, 5.254 (hasta 40 por web).

Después vinieron la tanda 2 de propios (hasta 300 fichas más por web, solo las webs cuyas primeras fichas
eran másters), la tanda 3 de no oficiales (los 8 centros grandes con másters de verdad: Euroinnova, ISFAP,
Esneca, Formación Continua, INESEM, Structuralia, ISEIE, EOI) y la **tercera vuelta de los oficiales**: las
48 universidades con menos del 70 % de sus másters con ficha (UB, UPM, UPV, UC3M, UAM, Murcia, A Coruña,
UPF…), donde las URL son códigos opacos: se leen sus páginas de programa y la ficha se asigna por el nombre
extraído. También se buscan ya los 387 másters aprobados en el BOE después del catálogo de febrero.

### Resultado de la noche (todas las tandas, comprobadas otra vez con las reglas corregidas)

| | |
|---|---|
| Páginas pedidas / enviadas a la API | 56.275 / 52.439 |
| Datos aceptados con cita literal comprobada / a revisión | 438.934 / 23.150 |
| Coste de la API | 21,18 $ extracción, 0,52 $ tarifas, 0,20 $ clasificación |
| Respuestas ilegibles | menos del 0,1 % |

**Másters oficiales con ficha comprobada: 2.899 de 4.734 (61 %)** (4.347 del catálogo y 387 altas del BOE):
2.191 con el nombre del RUCT en su página unida por URL, 127 casi iguales que la página declara oficiales (y
que no encajan mejor en otro máster de su universidad) y 581 encontrados por el nombre en otras páginas de su
universidad o de su centro adscrito, también en catalán, gallego o valenciano (comparación por raíces). 1.841
de públicas y 1.058 de privadas. 39 páginas que parecían la ficha eran de otro tipo de título (experto, propio,
curso) y no se usan. La cuarta vuelta rastreó los catálogos de 16 universidades con poca cobertura (UB desde
el servidor de España: desde GitHub responde 403); UCLM, Extremadura y Cantabria rechazan también desde España
y no se fuerza.

**Másters no oficiales y títulos propios: 20.555 programas de máster distintos** (proveedor + nombre + tipo):
15.567 de 912 centros no universitarios y 4.988 títulos propios en webs de 177 universidades y centros
adscritos. Además, 3.389 fichas de otros títulos (expertos, cursos).

Lo que publica cada grupo en su ficha (con cita comprobada):

| Dato | Oficial pública (1.841) | Oficial privada (1.058) | Propio en web universitaria (7.428 fichas) | Centro no universitario (17.350 fichas) |
|---|---|---|---|---|
| precio total | 20 % | **24 %** | **35 %** | 66 % |
| asignaturas o módulos | 45 % | 79 % | 50 % | 63 % |
| metodología | 46 % | 90 % | 64 % | 86 % |
| evaluación | 16 % | 54 % | 23 % | 49 % |
| horario | 14 % | 35 % | 32 % | 28 % |
| plazas | 60 % | 45 % | 36 % | 8 % |
| plazo de admisión | 22 % | 35 % | 31 % | 17 % |
| becas y descuentos | 13 % | 63 % | 33 % | 44 % |

Estado por campo de cada máster (`seguimiento.py --fichas`): de 27.677 másters con ficha, la mitad de lo
esencial se ve sin dar datos (indicador de transparencia medio 0,50); el precio se ve en 14.733 (15 de ellos solo
en una tarifa en PDF), está pendiente del decreto en 1.466 públicas y no se publica en 11.478. Peticiones
(`peticiones.py --fichas`): 890 centros con másters sin precio publicado (11.356 fichas; las públicas no
cuentan). Todo en la rama `sondas`, `fichas-masters/20261030-todas/` (fichas en gzip, estado por campo,
peticiones, precios de tarifas unidos y resúmenes).

### Tarifas en PDF (`tarifas.py`)

Common Crawl apenas ve PDF de precios (554 en 76 dominios, casi todos ajenos a másters). La fuente buena son
las propias fichas: de los originales guardados de 47.656 páginas salen 1.782 enlaces a PDF de precios, tarifas,
matrícula o folleto en 225 dominios. Leídos 1.360 (103 de más de 10 MB y 80 vetados o caídos se dejan); 371 son
tarifas o folletos con precio: 2.970 importes aceptados con cita y número comprobados, 554 a revisión, 0,52 $.
Solo 213 se unen sin ambigüedad a una ficha del mismo centro por el nombre (los demás son programas que aún no
tienen ficha o nombres que encajan en varias): rellenan el precio de las fichas que no lo daban, como
documento público, sin pisar nunca el de la página. Lo que no se une es la siguiente pista para crear fichas.

### Almacén y respeto a las webs

53.421 páginas guardadas intactas en el almacén privado (más PDF, lo enviado a la API y las respuestas), con
escritura única; 669 páginas no se leyeron por `robots.txt` o por no responder (1,2 %); ninguna web pidió
reserva de minería (TDM). Una petición por segundo y servidor en todo momento: las tandas que tocaban los
mismos servidores se lanzaron una detrás de otra.

### Fallos de proceso encontrados esta noche

1. La clave normalizada de la unión se usaba como dirección (arriba).
2. Al juntar tramos, los ficheros con el mismo nombre se pisaban: de la tanda 1 no oficial solo llegó a la
   rama un tramo de tres. Recuperados con `recoger.yml` (cada tramo en su carpeta); la extracción y la
   clasificación escriben ya cada tramo aparte y `estudios.yml` numera cualquier otro choque.
3. El 5 % de las clasificaciones devolvía JSON ilegible (comillas de la portada dentro de la cita): con la
   salida estructurada, 0 de 28 en el reintento.
4. Un oficial unido a un listado o a la portada hacía que todo el sitio pareciera «ya unido» y se perdían
   los propios (Centro Garrigues): ahora solo cuenta la misma ficha o sus subpáginas.
5. 38 precios eran texto («no indicado») y pasaban la comprobación: los campos numéricos exigen ya un número.
6. Precios en pesos colombianos de la versión es-CO de una web española: fuera las versiones de otro país, las
   citas con otra moneda y los importes de más de 100.000 €.
7. Una misma página pedida como oficial y como no oficial perdía su unión al máster oficial: manda la oficial.
8. Con varias páginas candidatas para un máster decidía la primera; ahora gana la que confirma el nombre, y un
   nombre parecido no vale si encaja igual en otro máster de la misma universidad.

**Revisión independiente** (otra instancia sin ver el trabajo, solo el código, con pruebas sobre casos difíciles):
11 fallos confirmados y corregidos el mismo día. Los más graves: un «Experto Universitario en X», un «Máster
Propio en X» o un «Curso de X» confirmaban el «Máster Universitario en X»; «título propio (no oficial)»
contaba como oficial porque contiene «oficial»; los números se aceptaban con cualquiera de las dos lecturas del
separador (4.550 por «45,50 €», 9,8 por «9.800 €»); la cita valía dentro de otro número («1.500 €» dentro de
«11.500 €»); «1500,50» rompía una tanda ya pagada; las tarifas no miraban la moneda ni repetían precio por
curso. Todas las tandas de la noche se vuelven a comprobar con las reglas nuevas sin pagar otra vez
(`extraer.py retomar`: el texto enviado está en el almacén y las respuestas del lote siguen en la API 29 días).

## 9. Siguientes pasos

Ordenados por lo que más acerca a tener, para cada máster, lo que hoy se da solo al registrarse
(`docs/estrategia-informacion-cerrada.md`). Estado al 30/10/2026 de madrugada.

1. **Cerrar las tandas en marcha**: no oficiales (tanda 2 adaptativa y la cola de los 22 centros con más de
   330 fichas), propios en webs oficiales (tanda 2 y la cola de las webs con más de 340), tercera vuelta de los
   oficiales (48 universidades por debajo del 70 %) y tarifas en PDF. Después, solo se extrae lo que cambia
   (fecha de última modificación del sitemap o huella distinta).
2. **Precio de las públicas** desde los decretos (`docs/fuentes-precios-publicos.md`): precio por crédito de la
   comunidad × créditos, con la condición de habilitante del RUCT. No se publica un precio calculado sin la
   norma leída y la categoría del título comprobada.
3. **Memorias del RUCT** (plazas verificadas, plan con asignaturas, evaluación ponderada) para los oficiales:
   en marcha desde el 30/10/2026 desde GitHub (§10; el repositorio es público y los ejecutores de GitHub no
   tienen límite de minutos, así que no hace falta el servidor de España, que queda para lo que GitHub no
   alcanza).
4. **Oficiales que siguen sin ficha** (1.835 de 4.734): Sevilla y Córdoba vetan el rastreo y la UOC da 403 (pedir
   permiso); UB, UPM, UPV, UC3M, UAM, Murcia, A Coruña, UPF y otras grandes tienen catálogos con URL opacas o
   que se pintan con JavaScript: la tercera vuelta las lee y las asigna por el nombre; lo que quede, conector
   por universidad o el lector con navegador del servidor de España.
5. **Descubrimiento**: los 187 agregadores podrían señalar centros que el índice no ve, pero su base de datos
   tiene protección propia (derecho «sui generis»): antes de leer ni sus listados hay que valorarlo; ESH, Saera y
   ThePowerMBA necesitan lector con JavaScript.
6. **Peticiones** (`peticiones.py --fichas`): 825 centros con másters sin precio publicado; primero tarifas en
   PDF y memorias, después la petición cuando el portal tenga dirección pública.
7. Másters oficiales que venden centros no universitarios con web propia (642 fichas «máster universitario
   oficial» fuera de las webs del RUCT): ya se asignan por la universidad que dice la página; revisar los que
   no encajan.
8. Becas, Excel de oferta de plazas, másters habilitantes y profesiones reguladas.

## 10. Hasta que solo quede publicar (30/10/2026, desde las 11:15)

Encargo de Álvaro: «tenemos que llegar hasta que no quede nada salvo publicar los datos». Lo que se ha puesto en
marcha y cómo encaja (las cifras finales, en el apartado de resultados de abajo cuando terminen las ejecuciones).

### Fuentes oficiales para todos los oficiales

- **RUCT, ficha y memoria de los 4.734** (`ruct.py`). Orden de lectura en `sondas:ruct-masters/20261030/`: primero
  los 1.835 sin ficha web, después los que no tienen dos de asignaturas, evaluación y plazas, etc. Una ejecución
  de 110 tramos en fila; cada tramo sube lo suyo al terminar (`estudios.yml por_tramo=si`) y el siguiente sigue
  por lo que falte (`--pendientes-de-sondas`: mira los nombres de fichero de la rama). Antes de cada petición,
  robots.txt (excepción de registro público, la misma que grados: solo mientras no se pueda leer). Originales al
  almacén privado. La memoria va a `ruct_memoria/` y trae además la descripción del plan.
  **Medido el 30/10 de día desde GitHub: el RUCT deja de responder tras unas 8 peticiones seguidas a una por
  segundo y vuelve a los 40-50 segundos** (287 fichas en 50 minutos; de noche, grados leyó 24 por minuto). El
  lector se adapta: cada petición sin respuesta duplica la pausa (hasta 12 s) y cada 15 buenas la bajan un 20 %,
  nunca por debajo de un segundo. A unas 10 por minuto, las fichas son unas 8 horas y las memorias (unas 54
  páginas por máster), semanas: por eso se leen por prioridad y las asignaturas salen antes del BOE.
- **Planes de estudios del BOE** (`boe_planes_masters.py`): el identificador del plan viene en la ficha del RUCT
  (unión exacta). Texto HTML del BOE, uno cada dos segundos, leído con el lector de planes de grados (reconoce
  TFM); comprobado si la suma cuadra con su tabla de créditos. En el conjunto va detrás de la memoria.
- **Guías docentes** (`guias.py`): enlaces a guías del propio centro en las páginas de máster oficial ya leídas
  (hasta 12 por máster); evaluación con porcentaje y frase literal comprobada, metodología. Sin nombres de
  profesores. Es la evaluación por asignatura de las memorias RD 822/2021, que no la traen.
- **QEDU de másteres** (`qedu_masters.py`, reutiliza `motor/grados/qedu.py` sin tocarlo): 5.561 imparticiones del
  curso 2025-2026 (4.599 títulos). Por impartición: plazas, precio del crédito (públicas), modalidad, idioma,
  enlace a la web oficial e inserción laboral del título. Es además la lista oficial de qué se imparte este
  curso: de los 1.835 oficiales sin ficha web, 1.578 están en QEDU y 257 no (207 son altas del BOE aún sin
  impartir).
- **Precios públicos**: QEDU da el precio del crédito de cada impartición pública, de la fuente oficial; los
  decretos (`docs/fuentes-precios-publicos.md`) quedan como control y para las condiciones (bonificaciones).

### Lo que faltaba de las webs

- **Citas**: con las reglas de la revisión, 14.206 datos seguían en revisión por «cita no literal». Ahora una
  cita vale también si son las mismas palabras en el mismo orden sin contar tildes ni separadores («Modalidad:
  Online» frente a «Modalidad | Online»), con los signos de fin de frase contando como palabra («No. Incluye»
  no es «No incluye») y sin partir números; o en trozos con «...» de cuatro palabras o más, en orden y cerca.
  Recupera 3.398 datos sin pagar nada (`retomar` de los 28 lotes). Además, una cita literal ya no vale dentro
  de un decimal («1.500» en «1.500,50»). Cada hecho anota `cita_nivel`.
- **Segunda oportunidad** (`recitar.py`): para los que siguen en revisión por la cita, se pide al modelo solo
  el fragmento literal que dice ese valor, sobre el mismo texto exacto; se comprueba igual y el valor no cambia.
- **Páginas que solo se pintan con JavaScript** (1.962 sin texto en el HTML): `extraer.py lote --navegador` las
  pinta con Chromium sin cabeza, con robots.txt en cada petición, sin imágenes ni estilos, tres segundos entre
  páginas del mismo servidor; las verificaciones antibots no se intentan pasar (quedan marcadas). Con ellas se
  reintentan 759 sin respuesta y 109 con error 5xx, y las 118 de la Rioja que dieron 429, a una cada seis
  segundos. No se reintentan los 404 (URL mal deducida: QEDU da la buena), los 403 ni los 202 (verificación).
- **Cuarta tanda**: de las 44.510 fichas únicas de los rastreos de no oficiales quedaban 15.299 sin pedir, pero
  más de la mitad eran lecciones, adjuntos y aulas virtuales (Zenith Sports, Magister, CEIBS) o ediciones de otros
  años del mismo programa; quedan 6.300 programas. De los propios en webs de universidades, los 16.273 restantes
  eran casi todos subpáginas de oficiales, trámites, noticias o un catálogo de EE. UU.; quedan 281 (99 másters
  propios de la UAB). Los servidores que estaban en la recuperación van después, para no pasar de una petición
  por segundo.

### Conjunto final (`conjunto_masters.py`)

Une todo por máster sin pedir nada: catálogo, RUCT (ficha y memoria), QEDU, webs y tarifas. Cada campo con
valor, fuente, URL y fecha de captura; manda la fuente oficial (`PRIORIDAD`) y las demás quedan como
alternativas si dicen otra cosa (plazas: QEDU del curso, con las verificadas de la memoria aparte y lo que dice
la web como alternativa). Lo calculado se dice: precio total = precio del crédito × créditos, solo si no hay uno
publicado; presencialidad = horas presenciales de las actividades de la memoria. **Fecha estable**: con
`--anterior`, el dato que no cambia (ni su fuente) conserva su fecha de captura; la fecha de la pasada va solo en
`resumen.json`, así que un conjunto sin cambios es el mismo fichero. Datos mínimos de la ley SEO (asignaturas y
precio) e `indexable`. Aviso de página web antigua (solo habla de cursos de 2023 o antes).
Privacidad: los textos de la memoria, las guías y las webs (también dentro de listas) pierden los párrafos con
nombres de personas (motor.limpieza; «Dr. Pérez», «Prof.ª Ana Ruiz»; «Coordinación: Nombre Apellido», «a cargo
de…», con nombre de pila; también cuando el PDF parte la mención en dos líneas) y los correos personales
(«[correo]»; los buzones de un servicio, como admisiones@ o master.biologia@, se dejan; master.juan@, no).

### Revisión independiente del conjunto (30/10/2026, tarde)

Un agente que no había visto el trabajo revisó el conjunto con sus propios scripts. Lo corregido:

- **Citas** (`extraer.verificar`): un número en una cita a trozos tiene que estar en un trozo; en una tabla, en
  la celda de su línea («numero_de_otra_celda»); un total por debajo de 300 € no es un precio de máster; un valor
  corto (modalidad, idioma, sí/no) tiene que estar en su cita («valor_no_en_cita», con sinónimos). Las guías,
  igual con el porcentaje. Todas las tandas pagadas se vuelven a comprobar sin pagar (`retomar`) y el recitado se
  aplica a la comprobación nueva (`recitar --retomar … --carpeta`).
- **BOE por nombre**: la universidad tiene que ser la misma con clave exacta («Autónoma de Barcelona» no es
  «Barcelona»; alias del BOE: UPV/EHU, Jaume I, Carlos III, Miguel Hernández, Vic, UDIT…), el nombre el mismo sin
  la traducción tras «/» ni siglas, sin correcciones de errores y nunca un plan publicado antes de que el código
  pudiera existir (35xxxxx desde 2022; 43xxxxx por tramos desde 2008). 2.960 → 4.695 resoluciones unidas; las 377
  que se quitan eran de otra universidad, de otro código o correcciones. Cada documento vale con su última
  medición.
- **Webs de otra universidad**: fuera la ficha web que dice que expide el título otra universidad, la que está en
  el dominio oficial de otra (dominios de los enlaces de QEDU; para los interuniversitarios valen todas las del
  nombre) y la «probable» que no está en un dominio de la suya.
- **Precios**: fuera totales por debajo de 300 € o iguales al precio del crédito y créditos fuera de 5-1.000 €;
  con precio oficial del crédito, si el total de la web no cabe (fuera de la mitad al doble), manda el calculado
  y el de la web queda como alternativa; el calculado dice si sale del precio oficial («primera matrícula», QEDU)
  o del que publica el centro; un precio de un curso de 2023 o antes no cuenta para indexar.
- **Asignaturas**: al menos tres de verdad (sin TFM, prácticas, bloques de optativas u obligatorias ni cabeceras;
  un «Módulo 3. Evaluación y tratamiento» con nombre de contenido sí cuenta); fuera «No se indica» y filas de una
  letra o solo números.
- **Modalidad de QEDU** como la da su detalle (código 2 = «semipresencial o a distancia»; 4 y -1 = «varias»).
- **Guías** con pesos que no caben en el 100 % (sistemas repetidos, convocatoria extraordinaria mezclada), fuera.
- **No oficiales**: fuera las páginas de másters oficiales (tipo oficial o «Máster Universitario» sin «propio»),
  las versiones de otro país y las noticias o blogs; uno por dominio y nombre; el identificador de la pasada
  anterior si alguna de sus páginas ya lo tenía.
- **Altas del BOE** con fuente BOE y fecha de lectura (no la de publicación), universidad por su clave.

### Pasada diaria (`diario_masters.py`, `masters-diario.yml`)

A las 02:17 (Madrid), una séptima parte de todo: las páginas ya extraídas (si su texto no cambió, no se paga), el
detalle de QEDU de las imparticiones del día (y sus tarjetas, una petición) y, desde el 15/11, la ficha del RUCT de
los títulos del día y su memoria si cambió. Después, fichas y conjunto con el conjunto anterior: la fecha de cada
dato solo cambia si cambia el dato. Las carpetas de resultados se buscan por su forma en la rama (también las de
las ejecuciones largas); `sondas:masters-estado/` guarda el manifiesto (entradas fijas) y el conjunto. Sin
manifiesto, el flujo no hace nada.

### Resultado del 30/10/2026 (18:00)

Todo lo que se puede bajar de las fuentes abiertas está bajado y unido, salvo el RUCT (ver abajo). Conjunto de
`sondas:masters-estado/conjunto` rehecho por la pasada diaria (`solo_conjunto`) con el código de `main`.

| | Oficiales (4.734) | No oficiales (20.527) |
|---|---|---|
| Indexables (asignaturas y precio) | 2.605 (públicas 2.327 de 3.113; privadas 278 de 1.606) | 9.023 |
| Asignaturas | 3.701 (BOE 3.273, web 403, memoria 25) | 12.927 |
| Precio total | 2.901 (calculado con QEDU 2.292, web 604, tarifa 5) | 14.079 |
| Precio del crédito | 2.733 (QEDU 2.612) | — |
| Plazas del curso | 4.184 (QEDU 4.096) | — |
| Modalidad | 4.508 (SIIU 4.320) | 17.531 |
| Evaluación | 983 (web 787, guías 169, memoria 27) | — |
| Metodología, acceso, salidas | 1.787, 1.958, 1.939 | 18.425, 13.361, 16.004 |
| Becas y descuentos | 878 | 10.273 |
| Inserción laboral (QEDU) | 923 | — |

Fuentes cerradas el 30/10: QEDU completo (5.561 imparticiones con detalle: plazas en 4.581, precio del crédito
en 3.278); BOE: 4.761 resoluciones de plan medidas (3.861 cuadran con su tabla), plan para 3.389 oficiales;
guías: 1.253 con evaluación comprobada (172 másters); webs: 36 lotes comprobados otra vez (479.024 datos
aceptados) y recitado (6.495 recuperados); desde el servidor de España, 48 páginas que no respondían a GitHub
(386 más tienen un robots.txt que no contesta ni desde allí: no se piden).

**Lo que queda y por qué:**
- **RUCT**: desde GitHub responde a unas 70 fichas por hora (686 oficiales con ficha a las 18:00; quedan unas 4.100, ~40 h,
  en fila). Las memorias (unas 50 páginas cada una) solo son viables desde el servidor de España, que comparten
  todas las conversaciones: lo decide Álvaro (buzón de incidencias). Lo que la memoria añadiría ya lo cubren en
  gran parte el BOE (asignaturas) y QEDU (plazas, modalidad); faltan las plazas verificadas y la evaluación
  ponderada de las memorias.
- **Precio de las privadas**: 1.311 oficiales privados sin precio; en sus páginas solo 19 tenían algún precio.
  No se publica: es la información cerrada (`docs/estrategia-informacion-cerrada.md`), que solo se consigue con
  peticiones.
- **Webs vetadas**: Sevilla y Córdoba prohíben el rastreo y la UOC da 403; UCLM, UNEX y UNICAN bloquean; de las
  escuelas de más reputación, ESADE y EADA responden 403 a nuestro lector (no se salta). Pedir permiso (Álvaro).

### Noche del 30/10/2026 (a fondo)

- **Precio por la norma autonómica** (`PRECIO_NORMA`): en las públicas de Cataluña (Decreto 96/2026, 2026-2027:
  17,69 € habilitante / 19,37 € resto, estudiantes de la UE) y Andalucía (Decreto 98/2023: 12,62 / 13,68, con la
  bonificación del 99 %), si QEDU no da el precio de la impartición. Solo comunidades con precio único; sin la UOC,
  Ingeniería Química ni dobles másteres. Habilitante: el dato de la memoria o el nombre del título.
- **Habilita para una profesión regulada** (`HABILITACIONES`): abogacía y procura (Ley 34/2006, con el examen de
  acceso), profesorado de secundaria (Orden ECI/3858/2007), psicología general sanitaria (Orden ECD/1070/2013),
  ingeniería industrial (CIN/311/2009) y de telecomunicación (CIN/355/2009) y arquitectura (EDU/2075/2010), con el
  enlace a la norma; solo si el nombre del título es el de la profesión. Las demás ingenierías habilitantes
  quedan sin marcar hasta comprobar el enlace de su orden.
- **Catálogos de másteres de cada universidad** (`catalogos_uni.py`): QEDU da para muchos títulos la portada de
  másteres de la universidad, no la ficha. Se leen esas 85 portadas (y hasta 12 listados que cuelgan de cada una;
  pintadas con el navegador si no traen enlaces) y se toma el enlace cuyo texto es el nombre de un máster sin
  página. Primera vuelta: 271 páginas (186 fichas de programa, 2.495 datos). Segunda vuelta con nombres «probables»,
  que la extracción vuelve a comprobar.
- **No oficiales**: fuera las versiones para otro país o en otra lengua (`/es-lat/`, `/en-intl/`, `/it/`…).
- **RUCT**: la lectura lenta desde GitHub se paró (686 oficiales con ficha) y queda una sola, en el servidor de
  España, con los públicos sin asignaturas primero (fichas y memorias ligeras), en cola detrás de los boletines.
- **Pasada diaria**: baja y mide los planes del BOE que dan las fichas nuevas del RUCT (los que no estén ya en la
  rama), así que cada ficha nueva trae su plan al día siguiente.
- **Orden de trabajo por reputación** (`reputacion.py`, petición de Álvaro): primero las universidades del QS 2026
  (UB, UAB, Complutense, UAM, Navarra, UPF, UC3M, UPM, UPC, Granada), después el grupo 1 del U-Ranking 2025 y las
  escuelas de negocio de referencia (IE, Ramon Llull/ESADE, IESE, Comillas, Deusto, CUNEF) y luego el grupo 2.
  Las listas del RUCT de la noche van así: primero los másteres sin asignaturas, de mayor a menor reputación.
- **Nombre en inglés**: los títulos bilingües («Gobernanza / Master in Governance») también se unen a su página
  cuando esta solo da el nombre en inglés (UPF, IE, Comillas…).
- **BOE**: un mismo nombre con código antiguo y nuevo en la misma universidad (título verificado otra vez): el plan
  nuevo es del código más reciente que ya podía existir. La UPC no publica sus planes de máster en el BOE: sus
  asignaturas solo pueden salir de la memoria del RUCT o de su web.

- **Tablas de precios de las universidades** (`tarifas.py lote --tablas`, `conjunto_masters.campos_tabla`): lista
  revisada a mano, en orden de reputación, de las tablas (PDF o página web) con el precio de cada máster oficial
  que publica la propia universidad (Navarra, UAM, Complutense, UPM, UPC, UPV, Francisco de Vitoria, Pontificia de
  Salamanca, UNED, Mondragón, URJC, Málaga, Zaragoza…). Claude Haiku lee la tabla y cada importe se comprueba en
  el texto (cita con las mismas palabras y cifras; las tablas web llegan como «celda | celda»). El precio pasa a
  su máster oficial por el nombre del RUCT aunque el máster no tenga web: mismo nombre (en cualquier idioma del
  título bilingüe, sin especialidad ni abreviaturas como «Bach.» o «F.P.»), ni doble máster ni título propio, de un
  curso no pasado y sin dos precios distintos igual de parecidos. Fuente pública: «Tarifa publicada por el propio
  centro», con la URL de la tabla y su curso; la tabla manda sobre el precio de la página (que a veces es la
  reserva). Las privadas que solo dan el precio por programa o a petición (Ramon Llull, Comillas, Deusto, CUNEF,
  CEU, ESIC) siguen sin tabla; las páginas de IE pintan el precio con JavaScript.
- **Subpáginas enlazadas desde la ficha** (`extraer.py subpaginas`): para los oficiales con ficha a los que les
  faltan asignaturas o precio, se leen los enlaces de su página principal (en el original guardado) que llevan al
  plan de estudios o a precios y admisión, en el mismo servidor, y se extraen como subpáginas de esa ficha. Solo
  cuentan si cuelgan de la ficha por la dirección (`/master-x/plan`, `/master-x-plan`, otra pestaña) o si su
  propio nombre es el del máster: una página general de precios o de admisión no le pone precio a un máster.
- **Nombres en catalán, gallego y valenciano**: además de las raíces, la grafía (ll, tg, ss, ny) y las palabras
  largas a una letra («Ciutadania» / «Ciudadanía», «Cirurgia» / «Cirugía»). Con el ensamblado de la noche: 14
  fichas oficiales más y ninguna perdida.
- **UB**: su web responde 403 a GitHub y su buscador de másteres se pinta con JavaScript; la lectura de sus
  listados con el navegador y la extracción de lo que encuentre van en una sola ejecución en el servidor de España
  (`catalogos_uni.py leer --y-extraer`), en cola detrás del RUCT.
- **Resultado de la noche (00:12 de Madrid, conjunto de `sondas:masters-estado` rehecho con `main`)**: 2.824
  oficiales indexables (públicas 2.482 de 3.113, privadas 342 de 1.606), 114 con precio de la tabla de su
  universidad; Navarra pasa de 3 a 35. Una asignatura repetida en la tabla del plan cuenta ya una vez: 15 másteres
  con dos asignaturas distintas repetidas dejan de ser indexables (9 de la UB).
