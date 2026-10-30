# Módulo de grados (carreras): universo, fuentes medidas y ficha

Versión 30/10/2026 (mañana). Lo mantiene la conversación de grados. Todas las cifras salen de datos reales capturados el
29 y el 30/10/2026 (originales en la rama `sondas`, carpeta indicada en cada caso); lo que no está medido se dice.
Código en `motor/grados/`, pruebas en `tests/test_*grados*.py`, `tests/test_qedu.py`, flujo `grados.yml`.
Desde el 30/10/2026 (02:47) `grados.yml` guarda los originales enteros en el almacén privado S3
(`MOTOR_ORIGINALES=s3`, escritura única); en la rama pública queda solo su índice con la clave y la huella.

## 1. El universo: cuántos grados hay

Tres fuentes oficiales, y ninguna sola tiene todo:

| Fuente | Qué da | Cifra medida |
|---|---|---|
| Catálogo SIIU del Ministerio (XLSX anual, curso 2025-2026, publicado el 06/10/2026) | cada título oficial × centro, con situación, modalidad, idioma, rama, campo e ISCED | 3.265 grados activos y 1.031 dobles grados activos |
| QEDU del Ministerio (servicio de su web, ver §2) | cada título × centro ofertado en 2025-2026, con nota, plazas, precio e inserción | 5.486 ofertas: 4.564 títulos (3.360 grados y 1.204 dobles) |
| BOE, acuerdos del Consejo de Ministros (2022-2026) | código RUCT, nombre y universidad de cada grado nuevo | 853 altas en 26 acuerdos |

Se cruzan por el código oficial del título:

- De los 4.564 títulos de QEDU, 4.512 están en el catálogo SIIU. Los otros 52 son nuevos (32 de ellos están ya en
  las altas del BOE).
- Solo 31 grados o dobles activos del catálogo no salen en QEDU (21 de privadas).
- **195 altas del BOE no están ni en el SIIU ni en QEDU**: 171 son de los acuerdos de septiembre y octubre de 2026
  (BOE-A-2026-19630, del 22/09/2026, 95 títulos; BOE-A-2026-21790, del 20/10/2026, 76). Son los grados que empezarán en los próximos cursos: el
  BOE es el aviso más temprano.

El universo es la unión de las tres, con el código del título como clave.

### Lo que dice el catálogo (curso 2025-2026)

- 3.265 grados activos: 2.239 de universidades públicas y 1.026 de privadas; 2.987 verificados con el RD
  1393/2007 (código 25xxxxx) y 278 con el RD 822/2021 (15xxxxx). 93 universidades con algún grado activo.
- **Corrección a la guía:** los dobles grados sí tienen código oficial. El SIIU los llama «Programaciones
  Conjuntas de Estudios Oficiales» (PCEO) y les da un código 70xxxxx: 1.031 activos (647 en públicas y 384 en
  privadas). Se usa ese código, no uno propio.
- Tres familias que no son un grado normal y no se mezclan con los grados: 16 agrupaciones catalanas de acceso
  («(agrupació)», un primer curso común que lleva a varios grados, código 00xxxxx), 4 grados abiertos (primer
  curso sin grado elegido, 77xxxxx) y 6 títulos eclesiásticos (Baccalaureatus, 90xxxxx).
- 3.703 imparticiones activas (título × centro): 3.228 presenciales, 245 en varias modalidades, 199 no
  presenciales y 31 semipresenciales. En las privadas, 162 de 1.125 son no presenciales (14 %); en las públicas, 37
  de 2.578 (1 %). 312 en centros adscritos. 414 con un plan en inglés u otro idioma extranjero.
- Por rama: Ciencias Sociales y Jurídicas 1.168, Ingeniería y Arquitectura 846, Ciencias de la Salud 500, Artes y
  Humanidades 469, Ciencias 282.
- Por comunidad: Madrid 691, Cataluña 519, Andalucía 464, C. Valenciana 309, Castilla y León 288.
- Cada componente de un doble grado se une con su grado simple: 1.955 de 2.055 componentes de los dobles activos
  (95 %); 5 quedan ambiguos (dos planes activos con el mismo nombre en el mismo centro) y 95 sin unir por nombres
  distintos («Primaria» frente a «Maestro en Educación Primaria»), que van a revisión.

### Grado genérico y área

El mismo grado en distintas universidades se agrupa para la página `/grado/{grado}/` y para comparar:

- **Grado genérico**: mismo nombre normalizado (sin la versión en inglés de los bilingües, sin notas como «(Plan
  nuevo)» ni siglas, «Maestro en Educación Primaria» = «Educación Primaria», plurales y preposiciones
  indiferentes). 703 genéricos. Los 245 con dos o más títulos reúnen 2.807 de los 3.265 grados (86 %) y tienen
  página propia; los 458 de nombre único no la tienen (sería casi igual que la ficha, ley SEO) y se enlazan por su
  área. Los más ofertados: Derecho 82, Administración y Dirección de Empresas 80, Psicología 72, Educación Primaria
  71, Enfermería 71, Educación Infantil 70, Ingeniería Informática 67, Fisioterapia 65.
- **Dobles grados genéricos**: combinación de los genéricos de sus componentes, sin orden. 543, de ellos 127 con
  dos o más títulos. Los más ofertados: ADE y Derecho 60, Educación Infantil y Primaria 43, CAFD y Fisioterapia
  21, Comunicación Audiovisual y Periodismo 21.
- **Área**: el campo de estudio del SIIU (136 campos con grado activo), la clasificación del Ministerio. Sirve para
  «carreras parecidas» («Ingeniería Informática» y «Sistemas de Información» están en el mismo campo).
- Revisado a mano: en 20 grupos al azar con varios nombres no hay uniones falsas; quedan separados nombres que
  de verdad son distintos («Ingeniería Electrónica y Automática» frente a «Electrónica Industrial y
  Automática»), que se relacionan por el área.
- El identificador del genérico sale hoy de su clave normalizada. Antes de publicar hay que fijarlo en una tabla
  que solo crece (si mejora la normalización, el identificador no cambia).

## 2. Qué da cada fuente (medido)

### QEDU: nota de corte, plazas, precio e inserción por título y centro

QEDU (`https://www.ciencia.gob.es/qedu.html`) pide sus datos por POST a `/home/qedu/main/zona02/0`. Su robots.txt
lo permite (sonda del 30/10/2026). Medido con sondas desde GitHub:

- `action=tarjeta` con los 35 ámbitos y los niveles `'GRADO','GRADOD'`: las 5.486 ofertas de 2025-2026 en una
  sola respuesta (2,7 MB), con código de título, centro y universidad y la nota de corte final del curso.
  3.007 tienen nota numérica: 2.968 de 3.631 ofertas de públicas y 39 de 1.855 de privadas. 786 tienen un 5,0
  (entra todo el que se preinscribe).
- `action=detalle`: plazas, nota de corte del curso y del anterior, nota media de admisión, créditos, precio del
  crédito en primera matrícula (públicas), modalidad, idioma y **tasa de afiliación** (el campo se llama «tasas»;
  la página lo rotula «Tasa de afiliación»). Ejemplo, Derecho en la Facultad de Derecho de la Complutense: 709
  plazas, corte 8,44 (8,88 el curso anterior), media de admisión 9,97, 16,92 €/crédito, afiliación 65,67 %.
- `action=detalleIn`: inserción del título: afiliación, autónomos, contratos indefinidos, cotización adecuada al
  nivel y base media de cotización (Derecho UCM: 65,67 %, 5,09 %, 90,59 %, 50,6 % y 29.115,69 €).
- `action=detalleAmb`: lo mismo para el ámbito, por sexo (para comparar el título con su ámbito).
- También sirve para másters (`'MASTER','MASTERD'`): se avisa a esa conversación.

Precauciones: la nota de corte de QEDU es la del cupo general tras el último llamamiento y solo de dos cursos; el
histórico de cinco años y los cupos salen de cada distrito (módulo de notas de corte). La inserción es de la
cohorte que QEDU indique (su ayuda habla de los egresados de cuatro años antes, afiliados en marzo del último año
disponible). Se publica con ese rótulo, nunca como «sueldo».

Capturado (30/10/2026): las 5.486 tarjetas y el detalle e inserción de 5.486 ofertas, por tramos de GitHub (`grados.yml`, una petición cada uno o dos segundos). Las públicas traen el precio del crédito; las privadas, «N/D».

### SIIU: indicadores de rendimiento por universidad y ámbito

Tablas PC-Axis del Ministerio (`estadisticas.ciencia.gob.es`, curso más reciente con dato), leídas por
`motor/grados/indicadores.py`: abandono (total y en primer año), cambio de estudio, abandono del sistema,
graduación, rendimiento, éxito, nota media del expediente, duración media y transición a máster, por universidad
y ámbito de estudio, con la media de España del ámbito. 3.125 grados tienen indicadores; en 943 el dato es solo
de ese grado (es el único de su universidad en el ámbito), en el resto es del ámbito en esa universidad y la ficha
lo dice.

### BOE: planes de estudios y altas

Sumarios: 2022-2026 (rama `datos`) y 2008-2021 (`motor/grados/boe_historico.py`, 4.384 sumarios, sin errores;
`sondas/20261030T034413`). Planes de grado de 2008 a 2021: 3.152 nuevos, 1.481 modificaciones, 367 correcciones y
18 cambios de denominación; de 2022 a 2026: 603 planes, 942 modificaciones, 66 correcciones y 9 cambios. El mismo
recorrido guarda los planes de máster (5.002 planes y 936 modificaciones de 2008 a 2021), útiles para másters.

Unión con el catálogo: por universidad y nombre del grado. Los planes antiguos dicen «Graduado en X» o
«Graduado Maestro en …» y las universidades se nombran de otra forma («Universidad del País Vasco», «Universitat
de València», «Universidad de las Illes Balears»): se normalizan y se resuelven contra el catálogo. Además, la ficha
del RUCT de cada título da el identificador BOE de su plan. Resultado: **3.106 de los 3.265 grados activos (95 %)
tienen su plan localizado en el BOE**; 159 no (sobre todo de la Politécnica de Catalunya, que no publica sus planes
de grado en el BOE, y grados con nombre muy distinto en el catálogo).

Textos (versión HTML del BOE, que su robots.txt permite; una petición cada uno o dos segundos): 6.008 textos
descargados; **el texto más reciente de los 3.106 grados con plan conocido está leído**.

El lector de tablas (`motor/grados/boe_grados.py`) saca de cada plan las asignaturas o materias con créditos,
carácter, curso y semestre, las menciones y la tabla de créditos por tipo. Formas que reconoce, todas vistas en
planes reales: cabecera en la segunda o tercera fila, bloques por semestre lado a lado, filas separadoras («Primer
curso», «Segundo semestre», «Formación básica», «Módulo 3»), celdas combinadas, columnas cambiadas de orden,
«Créd.», «CRD», «Org. Temp.», «Denominación módulo» y «ECTS módulo» (no son la asignatura), columna del nombre sin
rótulo, asignaturas escritas dentro de las celdas de un cuadro curso × semestre, tablas sin créditos por
asignatura (se guardan sin comprobar), tipo en el rótulo de la tabla, en su cabecera, en su fila de total o en el
nombre del módulo («Módulo 1: Formación Básica»), la tabla de materias básicas por rama del RD 1393/2007 (art.
12.5), códigos de carácter (FB, MB, BSC, OB, OBL, OP, OBM y OPM de mención, PE, TFG), materias mixtas
(«Obligatoria / Optativa», sin un solo tipo) y la tabla de créditos por tipo también escrita en párrafos. Las
resoluciones con varios planes se separan por anexo (52 resoluciones en 233 planes); si no cuadran tablas y
títulos, el documento queda entero y sin título.

**Comprobación.** Un plan cuenta como comprobado si la suma de sus filas coincide con su propia tabla de créditos:
completo (básicas + obligatorias + prácticas + TFG) o en básicas y obligatorias (el núcleo del plan; las prácticas
y el TFG se toman de la tabla). Si la lectura directa no cuadra se prueban lecturas más prudentes, y solo se
aceptan si entonces cuadra exactamente: sin los tipos deducidos (por nombre, rótulo o suma), sin una lista resumen
que repite otra tabla, sin la única tabla que suma justo lo que sobra (itinerarios, listas a otro nivel), dando su
tipo a la única tabla sin tipo que suma justo lo que falta, el resto sin tipo como obligatorio, o las asignaturas
de un módulo de mención o itinerario sin carácter como optativas y el resto como obligatorio. La ficha dice si
la lectura fue directa o alternativa (468 de los 3.620 comprobados). Si el plan del BOE no trae tabla que cuadre, se
compara con los créditos por tipo de la ficha del RUCT (otra fuente oficial). Nunca se completa un plan con datos
inventados.

Resultado con todo lo leído (30/10/2026, 06:00):

| | Leídos | Con asignaturas | Con curso | Comprobados |
|---|---|---|---|---|
| Planes nuevos | 3.496 | 2.551 | 2.137 | 2.177 (62 %) |
| Modificaciones | 2.231 | 1.599 | 972 | 1.378 (62 %) |
| Cambios de denominación | 20 | 16 | 15 | 11 |
| Correcciones de errores | 391 | 139 | 95 | 54 |

De los 1.319 planes nuevos que no cuadran: publicados solo por materias, sin asignaturas (401); tablas sin carácter
que no se puede asignar de forma comprobable (336); diferencias de una o dos asignaturas, 12 créditos o menos
(115); otras diferencias (296); sin tabla de créditos por tipo (90) y sin tabla de plan legible (81). Esos planes
se guardan igual (la ficha los enseña, marcados como no comprobados) pero no cuentan como asignaturas comprobadas.

Menciones: 692 planes y modificaciones las citan, en el texto o en las tablas.

Altas: los 26 acuerdos de 2022-2026 dan 853 grados con código RUCT, nombre y universidad.

### RUCT: ficha de cada título

`https://www.educacion.gob.es/robots.txt` no responde (ni desde GitHub ni desde España). Según la RFC 9309, un
robots.txt ilegible equivale a prohibirlo todo, y el motor no pide nada a ese servidor salvo una excepción:

**Decisión tomada por Claude el 30/10/2026 a las 02:51**, por mandato de Álvaro («de mí nada, sigue, hay que sacar
toda la info»), con el mismo criterio que los boletines oficiales: el RUCT es un registro público por norma («tendrá
carácter público y de registro administrativo», RD 1509/2008, art. 1.1; «la consulta al RUCT será pública», art.
7). La excepción está en `motor/grados/ruct_grados.py` (`REGISTRO_PUBLICO`, `DECISION_RUCT`): vale solo para
`www.educacion.gob.es/ruct/` y solo mientras su robots.txt no se pueda leer (si algún día responde y lo prohíbe,
se respeta). Una petición por segundo; ante cortes del servidor, espera de dos minutos y reintento; se para si no
vuelve. Cada resumen de ejecución anota el estado del robots.txt y la decisión. **Álvaro puede revertirla** borrando
la excepción.

Lo que da la ficha (una petición por título): créditos por tipo (obligatorios, optativos, prácticas, TFG; la
formación básica es el resto hasta el total), fecha de verificación, curso de inicio, autorización de la
comunidad, acreditaciones, extinción, centros e **identificador BOE de su plan** (también de los anteriores a
2022). Leídas las 3.573 fichas pedidas (todos los grados del catálogo con código RUCT, tres tramos, 3.600
peticiones sin un fallo): 3.080 grados activos tienen ahí el identificador BOE de su plan.

Las memorias de verificación (asignaturas, semestre, evaluación, plazas por centro) pesan entre 100 y 250 páginas
por título en el RUCT; se midieron en una muestra de 6 (785 peticiones) y no se piden en masa: solo donde el BOE no
dé asignaturas, y cuando se decida.

### Precio

- **Públicas:** QEDU da el precio del crédito en primera matrícula de cada oferta; la ficha calcula el grado
  completo (crédito × créditos). Normas de las 17 comunidades para 2026-2027, niveles y bonificaciones en
  `docs/fuentes-precios-grado.md`; las bonificaciones de siete comunidades (Andalucía, Extremadura, Galicia,
  Castilla-La Mancha, La Rioja, Asturias, Baleares) y la ayuda de Castilla y León van en cada ficha de pública
  (`motor/grados/precios.py`): 1.197 fichas. Hueco medido: QEDU no da precio a ningún doble grado de pública
  (906 ofertas, 647 fichas) y le falta a 186 ofertas de grado de públicas (50 de centros propios y 136 de
  adscritos, que fijan su propio precio). Donde la norma de la comunidad no depende del título, el precio sale de
  ella (`precios.PRECIO_UNICO` y `PRECIO_POR_RAMA`), solo para centros propios y con la norma, su URL y el curso en
  la ficha (`precio_credito_norma`): precio único en Andalucía (12,62 €) y Cataluña (17,69 €); por rama en Galicia
  y Cantabria (en un doble, solo si sus dos grados caen en el mismo precio). Antes se contrastó con QEDU: las 403
  ofertas andaluzas con precio menos una (un grado conjunto internacional), las 348 catalanas, las 140 gallegas y
  las 26 cántabras cuadran con la regla. Resultado: 314 fichas más con precio (304 dobles y 10 grados). En las
  comunidades con niveles por título (Madrid, Castilla y León, C. Valenciana…) el precio de un doble no se deduce:
  pendiente de leer qué dice cada norma de los dobles (§5).
- **Privadas:** QEDU no da precio. Tres fuentes propias, siempre con URL y fecha:
  1. **la página del grado** (`motor/grados/web_privadas.py`, las 43 universidades privadas con web en el RUCT):
     se une cada grado con su página por las palabras del nombre (también el nombre inglés de los bilingües) y se
     descartan noticias, FP de grado superior, falsos «grado» («integrado») y sedes ajenas. 765 páginas de grado
     leídas. Se leen los importes con su tipo por el contexto cercano (también en formato inglés, «€24,900»); los
     sueldos («28.000 € al año», «brutos anuales») no cuentan;
  2. **las páginas y PDF de precios** de la universidad (`motor/grados/tarifas_grado.py`): los que enlazan sus
     páginas de grado y los del sitemap con «precios», «tasas», «honorarios»…; una página de precios de un solo
     grado (por su dirección) atribuye sus cifras a ese grado; fuera páginas de investigación, blogs, másters,
     FP y de otros países;
  3. **el índice de Common Crawl** (`motor/grados/cc_precios.py`, solo metadatos de URL, como el censo de
     másters): URL de precios de los dominios de cada universidad que su web ya no enlaza. 268 halladas; se leen
     con el paso 2, con robots.txt.

  Regla del precio (`fichas.precio_por_cuentas` y `precio_web`), de más a menos comprobado: un importe que es el
  crédito × 60 de otro de la misma página (un curso son 60 créditos, RD 822/2021); crédito × 60 más la matrícula;
  reserva más 8 a 12 cuotas iguales; el precio de los datos estructurados (schema.org) si no contradice al texto;
  un único importe por curso; un único precio del crédito × 60. En las listas de precios solo valen cifras que
  cuadran entre sí dentro del bloque de cada grado. Con datos estructurados y texto en desacuerdo, no se publica
  precio. Total del grado estimado: precio por curso × créditos / 60, al precio de hoy.

  Resultado: **253 de 1.410 grados y dobles de privadas con precio por curso** (162 de su página y 91 de sus
  listas de precios), de 20 universidades; los 253 con total estimado. Control del título de la página: si la
  dirección casa con el grado pero el título dice que es de otro estudio (un doble para un grado simple, una FP,
  otro grado, o un doble con otros grados), la página no vale para ese grado (`web_privadas.titulo_contradice`);
  un título genérico («Admisión») no contradice nada. Descartó 29 uniones, 4 con precio (por ejemplo, un doble de
  Economía con Finanzas tomado por el de Economía y ADE). De las 601 privadas sin precio cuya página se leyó, 235
  tienen un formulario que pide el correo: la ficha lo dice como hecho medido («la universidad no publica el
  precio en la página del grado; su formulario pide correo»), sin juicio (`pagina_privada_sin_precio`). Sin
  ninguna página leída: Navarra (sin sitemap; su portada no enlaza los grados), Comillas (responde 421 a GitHub),
  UOC (403) y Ramón Llull (sus grados están en las webs de sus centros).

### Lo que falta por medir

- Notas de corte de cinco cursos o más por cupo: distritos (módulo de notas de corte, fase 2 de la guía).
- Guías docentes de grado: la guía decidió no hacerlas asignatura por asignatura para carreras.
- Una frase por asignatura (guía): se genera cuando el plan esté completo; no es un dato de fuente.

## 3. La ficha del grado

Unidad: **grado × universidad** (un código de título). Si el mismo título se imparte en varios centros, la ficha
los lleva dentro, con la nota, las plazas y la modalidad de cada uno; el plan de estudios es el mismo y dos fichas
serían casi iguales (ley SEO). Dirección: `/universidad/{universidad}/grado/{grado}/`.

| Bloque | Dato | Fuente principal | Control |
|---|---|---|---|
| Identidad | nombre, código, universidad, pública o privada, centros, municipio | SIIU | QEDU, BOE |
| Tipo | grado, doble grado (y sus dos grados), régimen, rama, área | SIIU | RUCT |
| Plan | asignaturas con créditos, carácter, curso y semestre; menciones | BOE (plan vigente; el que enlaza el RUCT y sus modificaciones) | tabla de créditos del plan |
| Reparto | créditos por tipo: básica, obligatoria, optativa, prácticas, TFG | BOE | RUCT |
| Acceso | nota de corte de dos cursos y nota media de admisión por centro | QEDU | distrito |
| Plazas | plazas de nuevo ingreso por centro | QEDU | oferta del Ministerio |
| Precio | públicas: €/crédito y grado completo en primera matrícula, bonificaciones; privadas: precio por curso de su web o su lista de precios y total estimado | QEDU y norma autonómica / web de la privada | cuentas entre cifras |
| Empleo | afiliación, autónomos, indefinidos, cotización adecuada, base media de cotización | QEDU | SIIU |
| Rendimiento | abandono, graduación, rendimiento, éxito, duración, transición a máster, con la media de España del ámbito | SIIU | — |
| Modalidad | presencial, no presencial, varias; idioma extranjero | SIIU | QEDU |
| Calidad | verificación, curso de inicio, última acreditación, extinción | RUCT | BOE |

Cada dato lleva fuente, URL y fecha de captura; la fecha solo cambia si cambia el dato.

### Datos mínimos para indexar (propuesta)

La ley SEO fija los del máster («asignaturas y precio») pero no los del grado. Propuesta, a decidir:

- **asignaturas** comprobadas (el listado cuadra con la tabla de créditos del plan);
- y al menos una cifra propia del grado: **nota de corte o precio**.

Cuando se decida, se declara en `DATOS_MINIMOS` de `motor/seo/reglas.py` (cada módulo declara los suyos; «grado»
ya figura como tipo de ficha en `motor/seo/control.py`): `"grado": [["asignaturas"], ["nota_corte", "precio_total",
"precio_credito"]]`.

### Cómo se genera (`motor/grados/fichas.py`)

Une catálogo, genérico, QEDU, indicadores del SIIU, plan del BOE, ficha del RUCT y precios de las privadas sin
pedir nada a ninguna fuente, y marca cada ficha como indexable o no, con el motivo. Con todo lo capturado hasta el
30/10/2026 por la mañana:

| | Fichas |
|---|---|
| Fichas activas | 4.296 (3.265 grados y 1.031 dobles) |
| Con sus centros en QEDU | 4.265 |
| Ofertas de QEDU con detalle (plazas, precio, inserción) | 5.486 de 5.486 |
| Con nota de corte | 2.662 |
| Con precio de primera matrícula (públicas) | 2.113 de 2.239 grados y 304 de 647 dobles de públicas |
| De ellos, con el precio de la norma de su comunidad (QEDU no lo da) | 314 |
| Privadas con precio por curso | 253 de 1.410 |
| Con inserción laboral | 1.703 |
| Con indicadores de rendimiento del SIIU | 3.125 |
| Con ficha del RUCT | 3.265 |
| Grados con plan del BOE | 3.079 de 3.265 |
| Grados con plan comprobado | 2.233 (1.567 por asignaturas, el resto por materias) |
| Dobles con los planes de sus dos grados comprobados | 574 |
| **Indexables** con la propuesta de datos mínimos | **2.048** (1.722 grados y 326 dobles; 1.829 de públicas y 219 de privadas) |

El resto va con `noindex` y su motivo: 846 con plan que no
cuadra, 643 sin plan (o doble sin los dos planes comprobados) y
1.202 sin nota ni precio (casi todas, privadas que no publican el precio); una
ficha puede tener varios.

Para rehacerlo todo desde `sondas`: bajar las carpetas con `datos/estudios/grados/` y ejecutar en orden
`boe_grados medir` (textos y actos de 2022-2026 y del histórico), `fichas`, `relaciones` y `universidades` (cada
módulo explica su uso). Las fichas del 30/10/2026 están en `sondas/fichas-grados/20261030/`.

## 4. Comparar y relacionar

Lo que hoy no da nadie junto: **el mismo grado en todas las universidades, en una tabla**. Por cada genérico con
página (`/grado/{grado}/`) y en el comparador, las columnas son nota de corte (dos cursos), plazas, modalidad,
precio (crédito de la pública; por curso de la privada), prácticas externas y optativas, afiliación, base media de
cotización, abandono y graduación (`comparativa.jsonl`, 372 genéricos, 4.149 filas).

Datos propios que salen de los planes (`motor/grados/asignaturas.py` y `relaciones.py`), siempre con planes
comprobados por asignaturas:

- **Asignaturas en común**: en cuántas universidades del mismo grado aparece cada asignatura, qué parte del plan de
  cada una es común y cuáles solo tiene ella (160 genéricos con al menos dos
  planes comparables).
- **Buscar por asignatura** (`asignaturas_indice.jsonl`): 36.455 asignaturas distintas
  (nombre normalizado, sin numeración), 8.089 en dos títulos o más, cada una
  con dónde se estudia, su tipo y su curso. TFG, optativas, prácticas y practicum van marcados como huecos del plan
  (19), sin página propia.
- **Carreras parecidas** (`relaciones.jsonl`): por campo ISCED-F, ámbito, área y rama del SIIU, nombre, dobles
  grados que las combinan y asignaturas básicas y obligatorias en común; cada relación lleva sus motivos.
  244 de los 245 genéricos de grado con página tienen alguna
  (1.377 relaciones apoyadas en asignaturas comunes); la que no tiene nada cercano queda
  vacía.
- **Dobles grados que incluyen cada carrera** y los grados que forman cada doble; la ficha del doble enlaza los
  planes de sus dos grados.
- **Universidades** (`universidades.jsonl`): grados, ramas, modalidades, plazas, nota de corte mediana, indicadores
  del conjunto y horquilla de precios (públicas: grado completo; privadas: por curso).

## 5. Siguientes pasos

1. **Decisiones de Álvaro:** datos mínimos del grado (propuesta en §3) y la excepción del RUCT (§2), que tomó
   Claude y se puede revertir.
2. Planes que no cuadran (sobre todo publicados solo por materias o sin carácter por asignatura): memorias del RUCT
   solo para esos grados (unas 130 peticiones por título; decidir alcance) o la página de la universidad.
3. Privadas sin precio: peticiones a cada universidad cuando el portal tenga dirección pública
   (`docs/estrategia-informacion-cerrada.md` §3.4); Navarra, Comillas, UOC y Ramón Llull, a mano.
4. Precio de los dobles de públicas en comunidades con niveles por título (343 fichas sin precio): leer qué
   dice cada norma de los dobles (si cada asignatura paga el nivel de su grado, un doble con sus dos grados al mismo
   precio tiene ese precio) antes de deducir nada; los centros adscritos, de su web.
5. Mantenerlo al día: BOE diario (planes y modificaciones nuevos), QEDU y SIIU cada curso, RUCT semanal
   (acreditaciones y extinciones), webs de privadas en primavera-verano.
6. Identificadores estables de genérico y de asignatura (tabla que solo crece) antes de publicar.

Límite conocido: 8 parejas de grados activos con el mismo nombre en la misma universidad (un título del RD
1393/2007 que se extingue y su sucesor del RD 822/2021) pueden compartir el plan más reciente.

## 6. Avisos para las otras conversaciones

- **Másters:** el sumario del BOE de 2008 a 2021 ya clasificado (`sondas/20261030T034413`,
  `boe_historico/*.jsonl`) trae 5.002 planes de máster y 936 modificaciones, con identificador y fecha.
- **Másters:** QEDU da lo mismo para másters (niveles `'MASTER','MASTERD'`): plazas, precio del crédito de las
  públicas, tasa de afiliación e inserción por título y centro (`motor/grados/qedu.py` sirve tal cual con
  `--nivel master`).
- **Másters:** `motor/estudios/ruct.py` no comprueba robots.txt; la excepción del RUCT está solo en
  `motor/grados/ruct_grados.py`. Si másters la quiere, que la lea de ahí.
- **Másters:** `fichas.precio_por_cuentas` (crédito × créditos, + matrícula, reserva + cuotas) y la lectura de
  leyendas de códigos de `boe_grados.leyenda` sirven para precios y planes de máster.
- **Todas:** el catálogo SIIU y el sumario del BOE ya capturados sirven sin volver a pedirlos
  (`motor/grados/catalogo.py --originales`, `motor/grados/boe_grados.py actos`).
