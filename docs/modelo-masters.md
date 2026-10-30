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
15.089 páginas.

**Títulos propios en las webs oficiales.** Las escuelas adscritas y las universidades venden másters propios
que no están en el RUCT (Máster en Finanzas de ESIC, Máster Executive en Recursos Humanos del Centro
Garrigues, los del IEB): ni la unión oficial ni la lista de no oficiales los recogía. `extraer.py
lista-propios-oficiales` toma las fichas de máster de esas webs que no son la página de un oficial unido:
34.131 fichas candidatas en 220 webs; primera tanda, 5.254 (hasta 40 por web).

### Fallos de proceso encontrados esta noche

1. La clave normalizada de la unión se usaba como dirección (arriba).
2. Al juntar tramos, los ficheros con el mismo nombre se pisaban: de la tanda 1 no oficial solo llegó a la
   rama un tramo de tres. Recuperados con `recoger.yml` (cada tramo en su carpeta); la extracción y la
   clasificación escriben ya cada tramo aparte y `estudios.yml` numera cualquier otro choque.
3. El 5 % de las clasificaciones devolvía JSON ilegible (comillas de la portada dentro de la cita): con la
   salida estructurada, 0 de 28 en el reintento.
4. Un oficial unido a un listado o a la portada hacía que todo el sitio pareciera «ya unido» y se perdían
   los propios (Centro Garrigues): ahora solo cuenta la misma ficha o sus subpáginas.

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
3. **Memorias del RUCT** (plazas verificadas, plan con asignaturas, evaluación ponderada) para los oficiales,
   en el servidor de España, repartidas en noches.
4. **Oficiales que siguen sin página** (1.876): Sevilla y Córdoba vetan el rastreo y la UOC da 403 (pedir
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
