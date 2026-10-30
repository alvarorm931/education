# Módulo de grados (carreras): universo, fuentes medidas y ficha

Versión 30/10/2026 (tarde). Lo mantiene la conversación de grados. Todas las cifras salen de datos reales capturados el
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
- Cada componente de un doble grado se une con su grado simple: 2.021 de 2.055 componentes de los dobles activos
  (98 %). Primero por el nombre; si no, por el nombre del genérico («Educación Primaria» = «Magisterio de Educación
  Primaria»), y si no, cuando un nombre contiene al otro («Informática» e «Ingeniería Informática», «Criminología» y
  «Criminología y Seguridad»), siempre que en la universidad haya un solo grado activo así. Estas 52 uniones por
  contención quedan marcadas (`union: por_contencion_del_nombre`) para revisarlas. 5 quedan ambiguos (dos planes
  activos con el mismo nombre en el mismo centro) y 29 sin unir.

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
`sondas/20261030T034413`, releído el 30/10 a las 08:00 en `sondas/20261030T0741…-t0` a `-t4`). Planes de grado de
2008 a 2021: 3.155 nuevos, 1.474 modificaciones, 409 correcciones y 18 cambios de denominación; de 2022 a 2026:
603 planes, 942 modificaciones, 66 correcciones y 9 cambios. **Errata del BOE:** en 2010 la Universidad de Alcalá
publicó sus planes con el título «… el plan estudios de Graduado en …» (sin «de»), y el clasificador no los veía:
21 grados de Alcalá quedaban sin plan. Ya se aceptan; la relectura del histórico halló 38 disposiciones más (37
planes de Alcalá), con sus textos descargados: ahora 34 de los 39 grados de Alcalá tienen plan y 28 lo tienen
comprobado. El mismo
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
completo (básicas + obligatorias + prácticas + TFG), sin que ningún tipo pase de lo que dice la tabla (se admite que
las obligatorias pasen justo en lo que falta de prácticas y TFG, porque hay planes que marcan el practicum «OB»); o
en básicas y obligatorias, las dos exactas (el núcleo del plan; las prácticas y el TFG se toman de la tabla). Si la
lectura directa no cuadra se prueban lecturas más prudentes, y solo se aceptan si entonces cuadra: sin los tipos
deducidos (por nombre, rótulo o suma), sin una lista resumen que repite otra tabla, sin la única tabla que suma
justo lo que sobra (itinerarios, listas a otro nivel), dando su tipo a la única tabla sin tipo que suma justo lo que
falta, el resto sin tipo como obligatorio, o las asignaturas de un módulo de mención o itinerario sin carácter como
optativas y el resto como obligatorio. Una lectura que comprueba el plan completo gana a la que solo cuadra en
básicas y obligatorias. La ficha dice si la lectura fue directa o alternativa (457 de los 3.514 comprobados) y si
además cuadra **tipo a tipo** (básicas, obligatorias, prácticas y TFG por separado, `cuadra_por_tipo`): 3.046 de
los 3.514. Los cursos y semestres en números romanos («III-IV», «X») se leen como números, y en los planes con una
tabla por curso cuyo curso solo dice el párrafo de encima («Primer curso», «Segundo curso»…) se toma de ese párrafo
cuando la racha de párrafos y la de tablas casan exactamente (`cursos_por_encabezado`): 89 planes nuevos y 71
modificaciones más con curso. Si el plan del BOE no trae tabla que cuadre, se compara con los créditos por tipo de la ficha del RUCT
(otra fuente oficial). Nunca se completa un plan con datos inventados.

**Dos revisiones independientes (30/10/2026).** Dos revisores que no habían visto el lector compararon fila a fila
16 planes comprobados al azar (7 de lectura alternativa) con sus tablas del BOE.

- La primera encontró: el practicum y el TFG con carácter «Obligatoria» contados como obligatorias aunque la tabla
  de créditos los separa; una fila «Total» leída como asignatura de 240 créditos; semestres 1 y 2 sin curso en
  planes con semestres del 1 al 8; «1 y 2», «7 u 8» o «1.º y 2.º» recortados al primero; llamadas de nota («(1)»,
  «(*)») pegadas al nombre. Corregido: el practicum y el TFG van a su tipo cuando la tabla de créditos los separa,
  las filas de total y las que valen la mitad del grado se descartan, «7 u 8» es cuarto curso sin semestre y «1 y 2»
  queda sin semestre (el literal se guarda), la tabla de módulos toma el curso de la de distribución temporal si es
  único (`curso_de_otra_tabla`) y los huecos de optativas («Optativa I», «Optativas 2-7») van marcados (`hueco`).
- La segunda, ya con eso corregido, encontró el riesgo principal: **errores que se compensan** (un plan con 70
  créditos de obligatorias sin leer y 64 de optativas leídas como obligatorias cuadraba en el total) y filas
  «Créditos totales» leídas como asignaturas. Corregido: ningún tipo puede pasar de su tabla de créditos y, en el
  nivel de básicas y obligatorias, las dos sumas tienen que ser exactas; las filas de totales se descartan.
- También se leía solo el bloque izquierdo de las tablas con dos semestres lado a lado cuando la cabecera traía
  «Tipo de materia» o una llamada de nota (planes de la UOC): corregido, 16 planes comprobados más, tipo a tipo.
- Efecto neto de las dos (antes de sumar los planes de Alcalá): comprobados, de 3.625 a 3.492 (salen los que
  cuadraban por compensación o con los tipos cambiados); de ellos, los que cuadran también tipo a tipo, de 1.960
  (medidos igual antes de corregir) a 3.030.
- Queda abierto (solo afecta a optativas, no a la comprobación): optativas perdidas al descartar una tabla repetida y variantes de nombre («Idioma moderno II» e «Idioma
  moderno II: Inglés II»).

Resultado con todo lo leído (30/10/2026, 08:00, hora de España):

| | Leídos | Con asignaturas | Con curso | Comprobados | Y además tipo a tipo |
|---|---|---|---|---|---|
| Planes nuevos | 3.532 | 2.591 | 2.302 | 2.132 (60 %) | 1.830 |
| Modificaciones | 2.226 | 1.596 | 1.058 | 1.315 (59 %) | 1.165 |
| Cambios de denominación | 20 | 16 | 15 | 12 | 11 |
| Correcciones de errores | 402 | 144 | 106 | 55 | 40 |

De los 1.400 planes nuevos que no cuadran: publicados solo por materias, sin asignaturas (418); tablas sin carácter
que no se puede asignar de forma comprobable (329); diferencias de una o dos asignaturas, 12 créditos o menos
(186); otras diferencias (298); sin tabla de créditos por tipo (92) y sin tabla de plan legible (77). Esos planes
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
por título en el RUCT; se midieron en una muestra de 6 (785 peticiones). Decidido por Álvaro el 30/10/2026: se
piden para los 1.020 grados sin plan comprobado. El RUCT tarda unos 10 segundos por página (medido: 307 peticiones
en 53 minutos, 5 memorias), así que se piden solo las páginas del plan (`ruct_grados.leer_plan_memoria`: módulos,
materias y asignaturas, sin actividades, evaluación, contenidos, acceso, catálogos ni centros), por prioridad
(165 grados sin plan, 441 publicados solo por materias y 409 que no cuadran), en 170 tramos de 6, 4 a la vez. Los
textos largos quedan solo en el almacén privado; en `sondas` va su tamaño y su huella (`ruct_grados.sin_textos`).

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
  las 26 cántabras cuadran con la regla. Resultado: 316 fichas más con precio (306 dobles y 10 grados).
- **Dobles de públicas en comunidades con niveles por título** (`precios.REGLA_DOBLE`, `ANEXO_DOBLE` y
  `REGLA_DOBLE_UNIVERSIDAD`; solo centros propios, con la norma, su URL y el curso en la ficha):
  - **Madrid** (Decreto 43/2022): media aritmética de los precios de sus dos grados (contraste: la UAM publica la
    media exacta). 121 dobles.
  - **Anexo de la norma con el nivel de cada doble** (55): Castilla-La Mancha (Orden 74/2026), Extremadura
    (Decreto 145/2026), Illes Balears (Acuerdo de 3/7/2026), Aragón (Decreto 120/2026), Canarias (Decreto
    177/2022, prorrogado; solo la ULPGC lista dobles) y Asturias (Decreto 45/2026, que trae el código de cada
    PCEO). El cruce de cada denominación del anexo con su doble se hizo por los nombres de sus dos grados y se
    revisó a mano; la ficha guarda la denominación literal. Contraste: en esas seis universidades, todas las
    ofertas de grado de centros propios con precio en QEDU tienen uno de los niveles de su norma (86, 65, 41, 58,
    45 y 53 ofertas).
  - **Reglas de la universidad cuando la norma no dice nada** (16): Valladolid (cada asignatura paga el precio
    de su grado) y Universitat de València (nivel superior; el reglamento no dice si es el de más precio). Con las
    dos solo se deduce cuando los dos grados cuestan lo mismo.
  - No se deduce (149 dobles de públicas siguen sin precio): Salamanca (26, precio de cada programa por
    resolución del rector), UPV (17), UPV/EHU (14, la orden no regula dobles), Murcia (potestativo), Pública de
    Navarra, La Laguna (su anexo no lista dobles), Miguel Hernández, Alicante, Burgos, León…; ni el doble de
    Almendralejo (centro adscrito, aunque el anexo de Extremadura lo cite).
- **Centros adscritos de públicas y centros de privadas con web propia** (Esade, IQS, Tecnocampus…): se rastrea la
  web de cada centro (`web_privadas.py --por-centros`, 124 webs) y sus listas de precios se cruzan con los grados
  de ese centro (`tarifas_grado.grados_por_codigo`). En una pública solo valen las del centro adscrito y solo si
  QEDU no da precio.
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
  un único importe por curso. Un precio del crédito suelto, sin otra cifra de la página que lo confirme, ya no se
  publica: revisados a mano los 7 que había, 2 eran una reserva de 350 € leída como crédito (Mediterrani, 21.000 €
  al año en lugar de unos 6.000). En las listas de precios solo valen cifras que cuadran entre sí dentro del bloque
  de cada grado. Con datos estructurados y texto en desacuerdo, no se publica precio. Total del grado estimado:
  precio por curso × créditos / 60, al precio de hoy.

  Resultado: **307 de 1.410 grados y dobles de privadas con precio por curso** (180 de su página y 127 de sus
  listas de precios, 22 de ellos de la web de su centro), de 24 universidades; los 307 con total estimado. Y 11
  grados de centros adscritos de públicas con el precio de su web. Control del título de la página: si la
  dirección casa con el grado pero el título dice que es de otro estudio (un doble para un grado simple, una FP,
  otro grado, o un doble con otros grados), la página no vale para ese grado (`web_privadas.titulo_contradice`);
  un título genérico («Admisión») no contradice nada. Descartó 29 uniones, 4 con precio (por ejemplo, un doble de
  Economía con Finanzas tomado por el de Economía y ADE). De las 601 privadas sin precio cuya página se leyó, 235
  tienen un formulario que pide el correo: la ficha lo dice como hecho medido («la universidad no publica el
  precio en la página del grado; su formulario pide correo»), sin juicio (`pagina_privada_sin_precio`). Sin
  ninguna página leída: Navarra (sin sitemap; su portada no enlaza los grados), Comillas (responde 421 a GitHub),
  UOC (403) y Ramón Llull (sus grados están en las webs de sus centros).

- **Listas oficiales de precios halladas a mano (30/10 por la tarde)**, para las privadas sin precio: una búsqueda
  dirigida en el dominio de cada universidad (sin copias de terceros), en `tarifas_grado.URLS_CONOCIDAS`. Leídas:
  Pontificia de Salamanca (2026-2027, 14 grados), IE (tasa anual 2027-2028, 15), Cardenal Herrera (Valencia,
  Elche y Castellón; la dirección fija ya sirve el curso 2027-2028), Alfonso X (online 2025-2026 y Mare Nostrum
  2026-2027) y Mondragon (patrón por grado). Dos lecturas nuevas: el total anual como reserva + matrícula + 8 a 12
  cuotas iguales (`fichas.precio_por_cuentas`, «reserva_matricula_y_cuotas»), y las listas cuyo formato se comprobó
  a mano con un único importe anual por grado (`tarifas_grado.LECTURA_CONOCIDA`; con dos importes en la fila, como
  presencial y semipresencial, no se publica). Sin leer: la Europea (sus PDF dan 404 a GitHub: se piden desde el
  servidor de España) y Deusto (su tabla de tasas no sale en el HTML que se descarga; las celdas sin «€» ya se
  leen). No publican tabla de precios en su web (búsqueda del 30/10): Católica de Valencia, VIU, UOC (remite al
  decreto), UDIMA (solo el precio a efectos de beca, que no es el de venta), CUNEF, ESIC y otras; ver
  `docs/estrategia-informacion-cerrada.md` §3.4.

### Lo que falta por medir

- Notas de corte de cinco cursos o más por cupo (decisión de Álvaro: dentro de grados): Madrid, Murcia,
  Cataluña y Salamanca hechos; el resto de distritos, ver «Notas de corte históricas» abajo.
- Guías docentes de grado: la guía decidió no hacerlas asignatura por asignatura para carreras.
- Una frase por asignatura (guía): se genera cuando el plan esté completo; no es un dato de fuente.

### Notas de corte históricas

QEDU da dos cursos (2025-2026 y el anterior) con el código del título y del centro. Para cinco cursos por cupo hay
que ir a cada distrito: fuentes oficiales localizadas el 30/10/2026 en las 17 comunidades; solo Cataluña
(Generalitat, datos abiertos), la Universidad de Murcia y la de Zaragoza las dan en datos abiertos; el resto, PDF o
HTML, y ninguna con el código del título salvo la Universidad de Murcia (código del título y del centro del
Ministerio).

- **Fase 1** (`motor/grados/notas_fuentes.py`): lee las páginas índice y los ficheros oficiales de cada distrito,
  guarda el original en el almacén y mide cada documento (formato, curso, filas con nota) para escribir su lector.
  Nunca pide ni guarda listas de personas (admitidos, espera, excluidos, tablón de la sede) ni documentos con DNI
  o NIE (el 30/10 se colaron 19 listas de la Pública de Navarra en el almacén: corregido en el código y pedido su
  borrado en el buzón de incidencias).
- Medido el 30/10: Madrid (distrito único, un PDF por curso de 2020-2021 a 2026-2027, grupos 1 a 6, ordinaria y
  extraordinaria, unas 600 ofertas por curso); Cataluña (Socrata, cupo general de 2023-2024 a 2026-2027 con
  plazas y 2022-2023 con cuatro cupos, nota al inicio y al final); Universidad de Murcia (CSV de 2021-2022 a
  2024-2025 con código de título y centro, que cuadra con QEDU al redondear a dos decimales); UPV/EHU (PDF de
  texto hasta 2021-2022 y de imagen desde 2022-2023); Salamanca, León, Burgos, Cantabria, Pública de Navarra
  (una lista de notas por adjudicación), Comunitat Valenciana (solo 2026-2027 en la copia de la UV; la web de la
  Generalitat lo cierra por robots.txt), UCLM, Granada, Cádiz. Sin acceso desde GitHub: ULPGC y Extremadura (403),
  CiUG (sin respuesta), La Rioja (429), Valladolid (404 en las direcciones conocidas).
- Lo que da la nota de cada distrito no es siempre lo mismo: la de Cataluña es la de la primera asignación de
  junio (solo coincide con la final de QEDU en un 10 %); Madrid, Murcia y Salamanca, la final. Cada fila lleva el
  tipo de lista y su documento.
- Licencias: Zaragoza publica sus datos abiertos con CC BY-NC (no comercial), que choca con una web con
  anuncios: fuera hasta que Álvaro decida (sus PDF no llevan licencia propia). Murcia: CC0 en su portal y CC BY-SA
  en datos.gob.es.
- QEDU no da cursos anteriores aunque se le pidan (sonda del 30/10: con `anio`, `curso` y otros campos devuelve
  siempre 2025-2026).
- **Fase 2** (`motor/grados/notas_corte.py`): un lector por formato y la unión de cada fila con su título y
  centro.
  - Lectores: Madrid (las dos tablas del PDF: la completa de once columnas y la de la Autónoma, con los grupos 1, 2
    y 6 y celdas vacías; cada cifra a su columna por el orden o por su posición; lo dudoso se descarta),
    Universidad de Murcia (CSV con códigos del Ministerio), Cataluña (Socrata), Salamanca (grupo general con el
    tipo del último admitido), **Andalucía** y **UPV/EHU** (abajo).
  - **Andalucía (Distrito Único Andaluz):** el botón «Descargar» de la consulta de notas de años anteriores envía el
    formulario a `g_not_cor_anteriores_csv.php` (lo dice su función `BuscarPeticiones` en
    `libportal/js/g_funcs_js_nca.js`; `notas_fuentes` ya busca en los .js del sitio la función de cada botón). Un
    CSV por curso, de 2010-2011 a 2025-2026, con las nueve universidades públicas, el código de la petición
    (título y centro), el nombre del centro y cinco cupos (general, titulados, mayores de 25, 40 y 45). Son las
    definitivas de la convocatoria ordinaria (última lista de admitidos, en noviembre, según la propia página).
    Tras la cifra del cupo general puede ir «PREF» o «N.P.» (último admitido preferente o no); se guarda tal cual.
    La página no indica licencia; es información pública de la Junta (Ley 37/2007).
  - **Cantabria:** «Comparativa notas de corte estudios de grado. 5 últimos cursos» (2021-2022 a 2025-2026,
    convocatoria ordinaria y extraordinaria), PDF de imagen: lectura óptica con tesseract y la posición de cada
    palabra (`notas_fuentes --ocr --posiciones`); cada cifra va a la columna cuyo rótulo tiene el centro más cerca
    (las celdas vacías no salen en el texto) y la fila con una cifra lejos de toda columna o dos en la misma no se
    usa. Contraste con QEDU: 33 iguales, 3 de lista posterior y 2 distintas (no se publican) de 38.
  - **UPV/EHU:** un PDF por curso de 2017-2018 a 2021-2022, por campus (Álava, Gipuzkoa, Bizkaia: el campus da los
    municipios para elegir centro), plazas y cinco cupos con su leyenda («*» plazas vacantes, «─» sin acceso, «E»
    nota de la extraordinaria). Las cifras salen pegadas en el texto («*8,0836,610»): se parte cada fila en cinco
    casillas de todas las maneras posibles con notas de 5 a 14 y solo vale si hay una sola. El orden de las
    casillas es el mismo en todos los cursos aunque los rótulos salgan desordenados (comprobado con la cifra que
    publicó la universidad: doble de Física e Ingeniería Electrónica 2020-2021, 13,124). Desde 2022-2023 los PDF
    son imágenes: la lectura óptica (`notas_fuentes --ocr`, tesseract) confunde cifras y bordes de tabla y no se
    usa.
  - Unión: universidad, nombre normalizado (siglas como «ADE», «CC.», «Ing.»; en Cataluña, un diccionario de
    palabras del catalán), dobles escritos «A-B», «A / B» o con «(simultaneïtat)», campus o centro entre paréntesis
    o comillas, municipio, nombre del centro (Andalucía; con sus abreviaturas «E.T.S.», «F.», «CC.»), centro propio
    cuando el nombre no cita ninguno, el título que se oferta frente al que se extingue y, si el distrito da la nota
    final, la nota de QEDU del mismo curso. El mismo código del distrito en otro curso con un nombre parecido es la
    misma oferta.
  - **Corrección del 30/10 por la tarde:** el centro y la universidad empujaban la puntuación y algunos nombres poco
    parecidos se unían mal (un doble sin «+» con uno de sus grados: «Derecho y Administración de Empresas» con
    «Administración de Empresas»; un título ya extinguido de 2010 con el activo más parecido). Ahora el nombre
    tiene que parecerse al menos 0,8 al del catálogo salvo que QEDU confirme la nota, y un nombre que empieza por
    «Doble» nunca se une con uno de sus grados. Se pierden algunas uniones buenas (Traducción e Interpretación por
    idiomas, nombres catalanes mal traducidos: 87 ofertas), que quedan sin publicar.
  - Nota del título en el centro: la menor de sus ofertas (menciones, grupos de idioma, títulos con máster), que es
    como la da QEDU.
  - Contraste con QEDU en los cursos que se solapan (nota por encima de 5,000; QEDU redondea o trunca a dos
    decimales): además de «igual», dos diferencias que no indican una unión equivocada sino que QEDU toma la nota en
    otro momento del proceso: la del distrito es la de la última lista y queda por debajo de la de QEDU (menos de un
    cuarto de punto), o QEDU da 5,000 porque al final quedaron plazas libres. Cualquier otra es «distinta».

    | Distrito | Igual | Lista posterior más baja | QEDU con plazas libres | Distinta |
    |---|---|---|---|---|
    | Andalucía | 513 | 61 | 68 | 6 |
    | Madrid | 606 | 26 | — | 19 |
    | Murcia | 45 | 2 | — | 17 |
    | Salamanca | 29 | 1 | 3 | — |
    | Cantabria (lectura óptica) | 33 | 3 | — | 2 |

    Revisión a mano de 6 notas de 2021-2022 de Madrid al azar contra el PDF oficial: 5 exactas y 1 sin poder
    confirmar; de la UPV/EHU, 6 al azar contra su línea del PDF: las 6 exactas.
  - Se publica (`historico.jsonl`, `publicable`) el histórico de un título y centro sin ninguna «distinta»; si
    ninguna de sus notas es la final (Cataluña), solo si sus plazas coinciden con las de QEDU. Cada curso lleva su
    documento, huella, fecha de captura y tipo de lista. Una ficha sin nota de QEDU ni precio que tenga la de su
    distrito desde 2021-2022 deja de tener ese motivo para no indexarse.
  - Resultado (30/10/2026, tarde): 1.709 títulos y centros con histórico, 1.619 publicables, 1.004 con cinco cursos
    o más; 1.569 centros de 1.430 fichas lo llevan ya (`centros[].notas_historicas`), 963 con cinco cursos o más.
  - Pendiente: Pública de Navarra (una lista por adjudicación, sin lista final declarada), Burgos (tabla acumulada
    2021-2026 con celdas vacías; el PDF escribe cada fila en un solo bloque de texto, así que ni el texto ni la
    posición de los bloques dicen la columna: haría falta leerlo como imagen), León (solo 2025-2026, que ya da
    QEDU), UCLM (la lectura óptica de su tabla sale ilegible), UPV/EHU desde
    2022-2023 (imágenes), Comunitat Valenciana, Galicia, Extremadura, ULPGC, Asturias y La Rioja (sin acceso desde
    GitHub: pedidos desde el servidor de España) y Zaragoza (licencia).

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
| Acceso | nota de corte de dos cursos y nota media de admisión por centro; histórico del distrito (hasta siete cursos) donde está comprobado | QEDU; distrito | QEDU |
| Plazas | plazas de nuevo ingreso por centro | QEDU | oferta del Ministerio |
| Precio | públicas: €/crédito y grado completo en primera matrícula, bonificaciones; privadas: precio por curso de su web o su lista de precios y total estimado | QEDU y norma autonómica / web de la privada | cuentas entre cifras |
| Empleo | afiliación, autónomos, indefinidos, cotización adecuada, base media de cotización | QEDU | SIIU |
| Rendimiento | abandono, graduación, rendimiento, éxito, duración, transición a máster, con la media de España del ámbito | SIIU | — |
| Modalidad | presencial, no presencial, varias; idioma extranjero | SIIU | QEDU |
| Calidad | verificación, curso de inicio, última acreditación, extinción | RUCT | BOE |

Cada dato lleva fuente, URL y fecha de captura; la fecha solo cambia si cambia el dato.

### Datos mínimos para indexar (decidido por Álvaro el 30/10/2026)

- **asignaturas** comprobadas (el listado cuadra con la tabla de créditos del plan; en un doble, las de sus dos
  grados);
- y al menos una cifra propia del grado: **nota de corte o precio**.

Declarado en `DATOS_MINIMOS` de `motor/seo/reglas.py`: `"grado": [["asignaturas"], ["nota_corte", "precio_total",
"precio_credito", "precio_curso"]]`.

### Direcciones estables (`motor/grados/identificadores.py`)

Una tabla que solo crece: cada universidad, genérico, título y asignatura con página recibe su dirección la
primera vez y no la pierde ni la cede (`identificadores.json`, junto a las fichas). Sin códigos en la dirección:
dos títulos con el mismo nombre en la misma universidad se distinguen por ciudad, modalidad, idioma o año del
plan; las fichas próximas (altas del BOE), por el año del alta. 13.026 direcciones el 30/10/2026; una segunda
pasada sobre los mismos datos no crea ninguna.

### Cómo se genera (`motor/grados/fichas.py`)

Une catálogo, genérico, QEDU, indicadores del SIIU, plan del BOE, ficha del RUCT y precios de las privadas sin
pedir nada a ninguna fuente, y marca cada ficha como indexable o no, con el motivo. Con todo lo capturado hasta el
30/10/2026 por la tarde:

| | Fichas |
|---|---|
| Fichas activas | 4.296 (3.265 grados y 1.031 dobles) |
| Con sus centros en QEDU | 4.265 |
| Ofertas de QEDU con detalle (plazas, precio, inserción) | 5.486 de 5.486 |
| Con nota de corte | 2.662 |
| Con precio de primera matrícula (públicas) | 2.113 de 2.239 grados y 498 de 647 dobles de públicas |
| De ellos, con el precio de la norma de su comunidad (QEDU no lo da) | 508 |
| Privadas con precio por curso | 355 de 1.410 (y 12 centros adscritos de públicas con el precio de su web) |
| Con histórico de notas de corte comprobado | 1.430 (1.569 centros; 963 con cinco cursos o más) |
| Con inserción laboral | 1.703 |
| Con indicadores de rendimiento del SIIU | 3.125 |
| Con ficha del RUCT | 3.265 |
| Grados con plan del BOE | 3.098 de 3.265 |
| Grados con plan comprobado | 2.245 (1.595 por asignaturas, el resto por materias) |
| Dobles con los planes de sus dos grados comprobados | 599 |
| **Indexables** con los datos mínimos decididos | **2.160** (1.777 grados y 383 dobles; 1.886 de públicas y 274 de privadas) |

El resto va con `noindex` y su motivo: 853 con plan que no
cuadra, 599 sin plan (o doble sin los dos planes comprobados) y
1.053 sin nota ni precio (casi todas, privadas que no publican el precio); una
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
- **Buscar por asignatura** (`asignaturas_indice.jsonl`): 36.890 asignaturas distintas
  (nombre normalizado, sin numeración), 8.250 en dos títulos o más, cada una
  con dónde se estudia, su tipo y su curso. TFG, optativas, prácticas y practicum van marcados como huecos del plan
  (19), sin página propia.
- **Carreras parecidas** (`relaciones.jsonl`): por campo ISCED-F, ámbito, área y rama del SIIU, nombre, dobles
  grados que las combinan y asignaturas básicas y obligatorias en común; cada relación lleva sus motivos.
  244 de los 245 genéricos de grado con página tienen alguna
  (1.399 relaciones apoyadas en asignaturas comunes); la que no tiene nada cercano queda
  vacía.
- **Dobles grados que incluyen cada carrera** y los grados que forman cada doble; la ficha del doble enlaza los
  planes de sus dos grados.
- **Universidades** (`universidades.jsonl`): grados, ramas, modalidades, plazas, nota de corte mediana, indicadores
  del conjunto y horquilla de precios (públicas: grado completo; privadas: por curso).

## 5. Siguientes pasos

1. **Decisiones de Álvaro:** la excepción del RUCT (§2), que tomó Claude y se puede revertir; Zaragoza (licencia
   no comercial de sus datos abiertos de notas de corte).
2. Planes que no cuadran (sobre todo publicados solo por materias o sin carácter por asignatura): memorias del RUCT
   de los 1.020 grados sin plan comprobado (decidido por Álvaro), solo las páginas del plan. **Parado:** desde
   las 11:30 del 30/10 el RUCT no responde a GitHub (tiempo agotado en cada petición; 5 de 6 memorias del primer
   tramo vacías), así que se canceló la tanda de 170 tramos. Se prueba desde el servidor de España, que comparten
   todas las conversaciones: a unos 10 segundos por página y 70 páginas por grado, los 1.020 serían unas 200 horas
   en un solo servidor; hace falta decidir cuántos y en qué orden. El lector ya está en las fichas
   (`fichas.plan_de_memoria`: el plan de la memoria entra si el del BOE no cuadra y él sí cuadra con los créditos
   por tipo del RUCT; con una página sin leer no cuenta como comprobado).
3. Privadas sin precio: tablas oficiales de honorarios de cada universidad (Europea, Alfonso X, CEU, Pontificia de
   Salamanca… publican PDF que el rastreo no encontró: lista en `tarifas_grado.URLS_CONOCIDAS`); lo que no esté
   publicado, peticiones a cada universidad cuando el portal tenga dirección pública
   (`docs/estrategia-informacion-cerrada.md` §3.4). El índice de Common Crawl de los dominios de centros dio 710
   direcciones más y solo 3 grados con importe: esa vía está agotada.
4. Dobles de públicas sin precio (149): resoluciones de cada programa en Salamanca; UPV y UPV/EHU, de su web.
5. Notas de corte del resto de distritos (Galicia, Comunitat Valenciana, Canarias, Extremadura, Asturias, La Rioja,
   Burgos, León, Cantabria, UCLM, Pública de Navarra, UPV/EHU desde 2022-2023) y la publicación de los cupos
   distintos del general (Madrid, Andalucía y UPV/EHU ya los leen).
6. Mantenerlo al día: BOE diario (planes y modificaciones nuevos), QEDU y SIIU cada curso, RUCT semanal
   (acreditaciones y extinciones), webs de privadas en primavera-verano, notas de corte en cada adjudicación.
7. Generador de páginas de grado con el diseño «Noche en blanco» y el control de la ley SEO.

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
- **SEO:** grados declaró su tipo en `DATOS_MINIMOS` de `motor/seo/reglas.py` (decisión de Álvaro) y, para eso,
  cambió `tests/test_seo.py::test_tipo_sin_declarar`, que usaba «grado» como ejemplo de tipo sin declarar: ahora
  usa «tipo-sin-declarar».
- **Todas las que lean listas oficiales:** `motor/grados/notas_fuentes.PERSONAS` y `DNI` filtran las listas de
  personas antes de pedirlas o guardarlas; sirven para cualquier rastreo que siga enlaces de una sede.
