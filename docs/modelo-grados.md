# Módulo de grados (carreras): universo, fuentes medidas y ficha

Versión 30/10/2026 (noche). Lo mantiene la conversación de grados. Todas las cifras salen de datos reales capturados el
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

**Tercera revisión independiente (30/10/2026 por la noche).** Un revisor sin acceso al código comparó 12 fichas
publicables al azar (5 grados de públicas, 4 de privadas con precio, 2 dobles y 1 con cupos de reserva) con sus
fuentes (informe local en `trabajo/verificacion/informe.md`). QEDU coincidía campo a campo en los 16 centros, los
precios de las públicas cuadraban en las 7 fichas y el histórico de Madrid cuadraba en todo. Errores comprobados en
9 de las 12, todos corregidos:

| Error | Corrección |
|---|---|
| Celda del carácter combinada en varias filas (Salamanca, Ciencia Política): 19 asignaturas con el nombre de la primera fila del bloque y sin tipo | `boe_grados._encajar`: si por la izquierda el nombre sería el de la fila anterior y poniendo la celda que falta en la columna del carácter la fila conserva el suyo, vale eso. Menciones escritas «Ob.Mención X» |
| «Taller de Trabajo Fin de Grado» (Obligatoria) contado como TFG (Nebrija) | el TFG y el practicum por nombre solo pasan a su tipo sin pasar de la tabla de créditos, salvo que el nombre sea el propio TFG o practicum (varios practicum de itinerario); la misma asignatura repetida en otra tabla no cuenta dos veces |
| Sin curso: tablas «Primer semestre \| Segundo semestre» … «Séptimo \| Octavo» y párrafos «Curso 1.º» (Nebrija, URJC) | ordinales hasta «duodécimo»; «Curso 1.º» y «1.º Curso» como encabezado; semestres 1 y 2 de primero si otra tabla del plan numera por encima de 2 |
| Plan de otro título con el mismo nombre (USAL, Información y Documentación: el plan nuevo 1500661 en la ficha del 2500163) | `boe_grados.codigos_en_texto` («Código Titulación: 1500661»): un plan que declara el código de otro título no se usa |
| Básicas listadas por materia y por asignatura, sumadas dos veces (Economía, Filología Hispánica de Granada) | `fichas.sin_niveles_repetidos`: si las asignaturas de un tipo suman lo mismo que sus materias, quedan las asignaturas |
| Errata del cuadro de créditos del BOE (Medicina, CEU: TFG 6 y optativas 8; las filas del mismo BOE y el RUCT, 8 y 6) | `fichas.corregir_distribucion`: vale el reparto del RUCT si las filas lo confirman; el del BOE queda en `distribucion_boe` con la nota |
| Dos notas para el mismo curso: QEDU 5,00 y el distrito 8,032 (Economía, Granada; la UGR confirma 8,032) | la nota de QEDU que el distrito publica distinta como final queda aparte (`nota_corte_anterior_qedu_no_usada`): 341 centros |
| Precio solo de los datos estructurados de la página, con «Precio: Consultar» a la vista (Hespérides) | los datos estructurados valen solo si el texto muestra el mismo importe; los importes «desde» / «a partir de» no son precio del curso |
| Comparación de asignaturas: nombres bilingües («Dermatología/Dermatology») sin emparejar; optativas sin tipo contadas como fijas | `asignaturas.sin_traduccion` y solo tipos fijos (básica, obligatoria, prácticas, TFG) |

Encontrado aparte en la misma revisión de privadas: la página de ADE de ESIC **Zaragoza** daba precio a la ADE de
**Pozuelo**. `web_privadas.sede_ajena`: una página o lista de precios cuya dirección nombra una sede de otra provincia
que las de los centros del grado no vale para él; si el grado está en varias provincias y la página es de una,
el precio lleva `solo_sede`.

Efecto en los planes del BOE (misma entrada, código anterior frente al nuevo): 16 planes y modificaciones más
comprobados, 11 más que cuadran tipo a tipo, ninguno menos; 29 planes y 46 modificaciones más con curso. Quedan
sin corregir (leves): el curso de dos materias «3 y 4» de Estudios Ingleses (Granada) y las alternativas de
«Lengua Clásica» que el BOE da junto a «Lengua Latina I». Aviso para el generador: `generico.id` es una clave
interna («doble-estudio-inglese-…»); la dirección pública es la de `identificadores.json`
(`/grado/estudios-ingleses-y-filologia-hispanica/`). `precio_primera_matricula` es el de todos los créditos del
grado, no el de un curso. El precio de la UPSA sale de su lista de Salamanca y Nutrición tiene también un centro
en Madrid (Salus Infirmorum) que esa lista no nombra: sin comprobar para Madrid.

**Cuarta revisión independiente (30/10/2026 por la noche).** Otro revisor, otras 12 fichas al azar (sin repetir las
anteriores). QEDU, los precios de las públicas y los históricos contrastados (Huelva 8 cursos, Granada 3, Salamanca
1) cuadran; los precios de CEU Fernando III y Francisco de Vitoria, también. Errores comprobados y corrección:

| Error | Corrección |
|---|---|
| Plan desactualizado: Historia (URJC) con el plan de 2020 cuando hay una modificación de 2026 con otro plan, que no cuadra por una errata del BOE («OB/FB» en la columna de créditos) | `fichas.plan_casi_entero`: el plan vigente es el más reciente que trae el plan entero o casi (lo que suma sin optativas llega al 80 % de su tabla); si no cuadra, la ficha no tiene plan comprobado aunque uno anterior cuadre (`plan_anterior_comprobado` lo dice). Afecta a 91 grados, que pasan a las memorias del RUCT |
| Tabla de optativas de ADE (Zaragoza) leída con una columna desplazada: la cabecera «Curso/Duración» va sobre dos columnas del cuerpo («4.º \| S1») | `boe_grados.normalizar_tablas` parte esa celda en «Curso» y «Semestre» cuando casi todas las filas traen una celda más |
| ADE de Zaragoza en extinción desde 2026-2027 publicada como abierta | `fichas.en_extincion`: con extinción en el RUCT en todas sus universidades, la ficha lo dice y no se indexa (55 títulos) |
| Psicología (UCAM): el precio era el de la modalidad a distancia | `solo_modalidad` cuando la dirección de la página es de una modalidad («online», «a distancia», «semipresencial») y el grado también es presencial (11 fichas) |

Quedan sin corregir y se dicen: 7 optativas sin tipo en Economía (URJC; el BOE no da su carácter en la tabla y la
ficha las deja sin tipo), tres asignaturas anuales de Educación Primaria (UFV) leídas como de primer semestre, el
curso que el BOE da y la ficha no en León (Marketing) y Extremadura (Periodismo) y las 5 menciones de Educación
Primaria (UFV). En Hespérides, ADE y otro grado, el RUCT registra modificaciones posteriores al BOE leído sin BOE
nuevo: riesgo de plan desactualizado, sin confirmar (las memorias del RUCT lo resolverán).

Resultado con todo lo leído (30/10/2026, 22:30, hora de España, tras las dos revisiones de la noche):

| | Leídos | Con asignaturas | Con curso | Comprobados | Y además tipo a tipo |
|---|---|---|---|---|---|
| Planes nuevos | 3.532 | 2.591 | 2.331 | 2.145 (61 %) | 1.841 |
| Modificaciones | 2.226 | 1.596 | 1.104 | 1.318 (59 %) | 1.165 |
| Cambios de denominación | 20 | 16 | 15 | 12 | 11 |
| Correcciones de errores | 402 | 144 | 106 | 55 | 40 |

De los 1.400 planes nuevos que no cuadraban a las 08:00 (hoy son 1.387): publicados solo por materias, sin asignaturas (418); tablas sin carácter
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
(165 grados sin plan, 441 publicados solo por materias y 409 que no cuadran), en 170 tramos de 6, 4 a la vez
(cancelado: el RUCT dejó de responder a GitHub; desde el servidor de España responde, ver §5). Los
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
  reserva más 8 a 12 cuotas iguales, o reserva más matrícula más las cuotas (si nada cuadra al euro, se admite la
  cuota redondeada al euro, medio euro por cuota: Francisco de Vitoria, 1.500 € + 10 × 932 € frente a 10.815 €); el
  precio anual de la enseñanza en 8 a 12 cuotas iguales de otra cifra de la fila, solo si sale una única solución
  (CEU San Pablo: 9 × 533,33 € = 4.800 €; la ficha dice que la reserva y la matrícula se pagan aparte), y si la fila
  trae además un total que es esa enseñanza más la reserva, la matrícula y otros pagos de la fila, vale ese total
  (Cardenal Herrera: 4.740 + 400 + 700 + 675 = 6.515 €); el precio de los datos estructurados (schema.org) solo si el
  texto de la página muestra el mismo importe; un único importe por curso. Un importe «desde» o «a partir de» no es
  el precio del curso, y tampoco el de una fila o un texto con beca o descuento («Becas Marqués de Lozoya», «con la
  beca…»; «sin descuento» sí vale). Un precio del crédito suelto, sin otra cifra de la página que lo confirme, no se
  publica: revisados a mano los 7 que había, 2 eran una reserva de 350 € leída como crédito (Mediterrani, 21.000 €
  al año en lugar de unos 6.000). En las listas de precios solo valen cifras que cuadran entre sí dentro del bloque
  de cada grado; si la lista da varios precios para el mismo título (campus, modalidad, idioma), se publica el menor
  como «desde» y la ficha lo dice con todos los precios (`precios_de_la_lista`). Con datos estructurados y texto en
  desacuerdo, no se publica precio. Qué es cada cifra: `precio_curso` es lo que la fuente da como pagado en el
  primer curso (en una lista, la enseñanza más la reserva, la matrícula y los cargos de la misma fila si la fila trae
  ese total: Cardenal Herrera, 6.420 € de enseñanza y 9.020 € con 700 de reserva, 1.500 de inscripción y 400 de
  apertura); `ensenanza` es la enseñanza de un curso cuando se puede separar. Total del grado estimado: la enseñanza
  (o, si no se separa, el precio del curso) × créditos / 60, al precio de hoy, y la ficha dice que la matrícula y los
  cargos van aparte (pueden ser solo del primer año); en un doble grado solo si el precio sale del precio del crédito
  (sus cursos pasan de 60 créditos, 72 o 78, y con el precio de un curso el total no se sabe: `nota_total`).

  Lectura de las listas (`tarifas_grado.extraer`, 30/10 por la noche): las tablas HTML se leen con un lector de HTML
  (Deusto omite los cierres de celda y de fila, que el estándar permite); las celdas sin «€» valen si la cabecera
  rotula columnas de dinero («MATRÍCULA», «8 PLAZOS ENSEÑANZA», «TOTAL») y la cifra lleva céntimos; una fila sin
  grado («Concepto | Importe») no tapa el nombre del grado de encima; en las fichas de precios con título, rótulo y
  cifra (San Jorge) la cifra es del grado del título si está como mucho 12 líneas más arriba; y una cifra que el texto
  del PDF parte en dos («1. 100 €», Alfonso X) se toma entera solo si así cuadran las cifras de su fila, con nota (23
  fichas). Una página de precios sin ningún importe leído guarda un diagnóstico sin texto (tablas, filas, cifras a
  la vista y en scripts, forma de sus líneas y direcciones de datos que carga aparte), y una línea con importe que no
  se une con ningún grado, su forma (letras como «a», dígitos como «9»): así se vio que la tabla de Deusto sí estaba
  en el HTML y que Nebrija carga sus precios de grado aparte. Nebrija usa Gatsby, que sirve los datos de cada página
  en un JSON público («/page-data/…/page-data.json», en su dominio de recursos `assets.griddo.nebrija.com`): se lee
  como una página más (`tarifas_grado.lineas_json`, 26 grados con precio de 2026-2027).

  Resultado (31/10, 07:20, con las reglas nuevas, la relectura de las listas de las 45 privadas y sus centros y la
  de sus páginas de grado): **551 de 1.410 grados y dobles de privadas con precio por curso** (183 de su página y
  368 de sus listas de precios), de 28 universidades (antes de estas reglas, 358 de 27). Entran sobre todo San
  Pablo-CEU (74), Nebrija (26 más, de los datos de su página de precios), Francisco de Vitoria (53), Deusto (32),
  Comillas (28), San Jorge (27) y Alfonso X (22). 51 llevan varios precios de la lista («desde»). De los 113 dobles
  con precio, 10 tienen total estimado (los demás, el precio de un curso). Y 15 grados de centros adscritos de
  públicas con el precio de su web.

  **Comillas (31/10 de madrugada).** El RUCT da su web antigua (`www.upcomillas.es`, que responde 421 a GitHub) y el
  rastreo no salía de ese dominio: `web_privadas.WEB_ACTUAL` le pone la actual (`www.comillas.edu`), con 29 sitemaps
  y 31 páginas de grado leídas. Además su servidor dice Latin-1 y sirve UTF-8, y el «€» llegaba como «â‚¬»:
  `tarifas_grado.texto_bien_decodificado` lo detecta y vuelve a leer en UTF-8. Cada página da matrícula, mensualidad
  y total (Derecho: 1.657,80 € + 9 × 1.576,80 € = 15.849 €, comprobado en la página); no dice el curso (la fecha de
  inicio es el 01/09/2027), y la ficha no lo pone.

  **Quinta revisión independiente (30/10, 23:30, antes de sumar Nebrija).** Un revisor sin acceso al código comparó 12 precios nuevos con su
  fuente (Deusto, San Pablo-CEU, Cardenal Herrera, Alfonso X y Mare Nostrum, San Jorge, Francisco de Vitoria; informe
  local en `trabajo/verificacion3/informe.md`): 7 correctos, 1 error y 4 sin poder abrir la fuente desde su entorno
  (Deusto 2027-2028 y San Jorge). El error: Cardenal Herrera publicaba solo la enseñanza (6.420 €) de una fila cuyo
  total es 9.020 € con reserva, inscripción y apertura, mientras el doble del mismo PDF sí daba el total: corregido
  con la regla de arriba (40 fichas pasan al total de su fila). Observado y no corregible con lo publicado: Alfonso X
  tiene versión en inglés y en línea del mismo título con otro precio (la en línea de 2026-2027 no está publicada);
  San Pablo-CEU da la enseñanza sin la matrícula anual (la ficha lo dice).

  Control del título de la página: si la
  dirección casa con el grado pero el título dice que es de otro estudio (un doble para un grado simple, una FP,
  otro grado, o un doble con otros grados), la página no vale para ese grado (`web_privadas.titulo_contradice`);
  un título genérico («Admisión») no contradice nada. Descartó 29 uniones, 4 con precio (por ejemplo, un doble de
  Economía con Finanzas tomado por el de Economía y ADE). De las 477 privadas sin precio cuya página se leyó, 196
  tienen un formulario que pide el correo: la ficha lo dice como hecho medido («la universidad no publica el
  precio en la página del grado; su formulario pide correo»), sin juicio (`pagina_privada_sin_precio`). Sin
  ninguna página leída: Navarra (sin sitemap; su portada no enlaza los grados; su lista de precios sí se lee), UOC (403) y Ramón Llull (sus grados están en las webs de sus centros).

- **Listas oficiales de precios halladas a mano (30/10 por la tarde)**, para las privadas sin precio: una búsqueda
  dirigida en el dominio de cada universidad (sin copias de terceros), en `tarifas_grado.URLS_CONOCIDAS`. Leídas:
  Pontificia de Salamanca (2026-2027, 14 grados), IE (tasa anual 2027-2028, 15), Cardenal Herrera (Valencia,
  Elche y Castellón; la dirección fija ya sirve el curso 2027-2028), Alfonso X (online 2025-2026 y Mare Nostrum
  2026-2027) y Mondragon (patrón por grado). Dos lecturas nuevas: el total anual como reserva + matrícula + 8 a 12
  cuotas iguales (`fichas.precio_por_cuentas`, «reserva_matricula_y_cuotas»), y las listas cuyo formato se comprobó
  a mano con un único importe anual por grado (`tarifas_grado.LECTURA_CONOCIDA`; con dos importes en la fila, como
  presencial y semipresencial, no se publica). Sin leer: la Europea (sus PDF de 2025-2026 dan 404 también desde el
  servidor de España, así que ya no están; la tabla 2026-2027 solo aparece en copias de terceros, que no son
  fuente) y Católica de Valencia (publica su tabla de honorarios de grado 2026-2027 en PDF, pero su robots.txt
  prohíbe esa ruta: no se pide). Deusto, que no se leía, ya se lee (su tabla omite los cierres de celda). No publican tabla de precios en su web (búsqueda del 30/10): VIU, UOC (remite al decreto), UDIMA (solo el
  precio a efectos de beca, que no es el de venta), CUNEF y otras; ver `docs/estrategia-informacion-cerrada.md` §3.4.
- **Segunda búsqueda dirigida (30/10 por la noche)**, 20 privadas con pocos precios, solo en su dominio:
  - Leídas y añadidas a `URLS_CONOCIDAS`: Camilo José Cela (tarifario de grados 2026-2027 y las fichas de precio
    de Salud, cada una con su curso; los PDF de un solo grado se atribuyen por el nombre del fichero,
    `tarifas_grado.grado_de_fichero`), Alfonso X (Villanueva, honorarios 2026-2027), Mondragon (página de precio de
    cada grado: «previsión para el curso 2027-28», que la ficha dice con su nota, `CURSO_CONOCIDO`; su tabla central
    no cuadra con esas páginas, 8.520 € frente a 143 €/ECTS × 60 = 8.580 €, y no se usa), Euneiz, Intercontinental
    de la Empresa (UIE, página de cada grado), Abat Oliba CEU y Comillas (dos fichas de ejemplo; el resto, con el
    rastreo de su web, que responde 421 a GitHub y se pide desde el servidor de España).
  - Resultado: Camilo José Cela 18 de 81 grados con precio, Alfonso X 5 de 46, Mondragon 8 de 19, UIE 6 de 6,
    Euneiz 5 de 11 (tabla del precio del crédito por titulación, comprobada a mano: `LECTURA_CONOCIDA`,
    «credito_por_60_de_la_tabla»), Abat Oliba 2 de 15. Alfonso X: el texto del PDF parte
    «1.100 €» en «1.» y «100 €»; desde el 30/10 por la noche se toma entera solo si así cuadra la fila (23 grados de
    Alfonso X y Mare Nostrum con precio).
  - No publican precio: UNIR («consulta precios con tu asesor»), Villanueva («consultar precio»), UEMC, Europea del
    Atlántico, Fernando Pessoa-Canarias, Atlántico Medio y UTAMED.
  - Publican, pero no se puede usar: Católica de Valencia (su robots.txt prohíbe la ruta del PDF), IQS (un precio
    por crédito para todos los grados, sin grado por línea; sus fichas, prohibidas por robots.txt), Esade (un único
    importe de primer curso para todos los grados, sin curso), UCAV (precio por crédito por tramos de créditos, no
    por grado), La Salle, Blanquerna y UVic (páginas en inglés cuyos nombres no casan con los del catálogo), Isabel I
    (el importe se carga con JavaScript) y la Europea (2025-2026 retirado, 404). Nebrija, que no se leía, ya se lee
    de los datos de su página de precios. San Jorge, que daba error,
    ya se lee (27 grados con precio).

- **Por qué no responde una dirección** (`tarifas_grado.pedir_con_motivo`, desde el 30/10): cada dirección sin
  respuesta lleva `motivo` (robots.txt que lo prohíbe, robots.txt que no responde —entonces no se rastrea—, límite
  de peticiones al servidor o el error de conexión). En la prueba del 30/10 (GitHub), de las 235 direcciones de
  Common Crawl que nunca habían respondido, 3 respondieron (Centro Superior de Diseño de Moda de la UPM: una tarifa
  de 2023-2024 sin importes unidos a un grado) y las otras 232 son de robots.txt: 62 prohibidas (ETSI Aeronáutica
  y del Espacio de la UPM) y 170 de servidores cuyo robots.txt no contesta (UPM, Salamanca, Vigo, Barcelona,
  Manresa). Las 2 de Católica de Valencia, también prohibidas por su robots.txt. Ninguna es un fallo nuestro. `--solo CÓDIGO` limita una ejecución a una universidad o centro.

### Lo que falta por medir

- Notas de corte de cinco cursos o más por cupo (decisión de Álvaro: dentro de grados): Madrid, Andalucía,
  Cataluña, UPV/EHU (hasta 2021-2022), Cantabria, Murcia y Salamanca hechos; el resto de distritos, ver «Notas de
  corte históricas» abajo.
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
  - **Cupos de reserva** (`notas_corte.notas_de_otros_cupos`, desde el 30/10 por la noche): titulados, mayores de
    25, 40 y 45, convocatoria ordinaria, la menor de las ofertas. Salen de la misma fila del mismo documento que la
    del cupo general, así que van con su histórico solo si este es publicable (`otros_cupos` en
    `centros[].notas_historicas`, con su rótulo). Cada cupo tiene su propia prueba o baremo: sus notas no se comparan
    con las del general (en Andalucía y la UPV/EHU, mayores de 40 pasa de 10). Un 5,000 se publica como «se admitió a
    todos los que lo pidieron por ese cupo»; una casilla vacía (sin plazas o sin cupo) no sale.
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
    2022-2023 (imágenes), Comunitat Valenciana (solo la primera adjudicación de 2026-2027), Galicia y Asturias
    (su robots.txt no responde ni desde GitHub ni desde el servidor de España: no se pide nada), ULPGC y Extremadura
    (403 desde los dos), La Rioja (429) y Zaragoza (licencia).

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
31/10/2026 a las 07:20:

| | Fichas |
|---|---|
| Fichas activas | 4.296 (3.265 grados y 1.031 dobles) |
| Con sus centros en QEDU | 4.265 |
| Ofertas de QEDU con detalle (plazas, precio, inserción) | 5.486 de 5.486 |
| Con nota de corte | 2.532 |
| Con precio de primera matrícula (públicas) | 2.113 de 2.239 grados y 498 de 647 dobles de públicas |
| De ellos, con el precio de la norma de su comunidad (QEDU no lo da) | 508 |
| Privadas con precio por curso | 551 de 1.410 (y 15 centros adscritos de públicas con el precio de su web) |
| Con histórico de notas de corte comprobado | 1.430 (1.569 centros; 963 con cinco cursos o más; 1.030 con los cupos de reserva) |
| Con inserción laboral | 1.703 |
| Con indicadores de rendimiento del SIIU | 3.125 |
| Con ficha del RUCT | 3.265 |
| Grados con plan del BOE | 3.095 de 3.265 |
| Grados con plan comprobado | 2.145 (1.536 por asignaturas, el resto por materias) |
| Dobles con los planes de sus dos grados comprobados | 557 |
| **Indexables** con los datos mínimos decididos | **2.181** (1.766 grados y 415 dobles; 1.775 de públicas y 406 de privadas) |

El resto va con `noindex` y su motivo: 950 con plan que no
cuadra, 644 sin plan (o doble sin los dos planes comprobados) y
857 sin nota ni precio (casi todas, privadas que no publican el precio); una
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
  cada una es común y cuáles solo tiene ella (153 genéricos con al menos dos
  planes comparables).
- **Buscar por asignatura** (`asignaturas_indice.jsonl`): 34.865 asignaturas distintas
  (nombre normalizado, sin numeración), 7.908 en dos títulos o más, cada una
  con dónde se estudia, su tipo y su curso. TFG, optativas, prácticas y practicum van marcados como huecos del plan
  (19), sin página propia.
- **Carreras parecidas** (`relaciones.jsonl`): por campo ISCED-F, ámbito, área y rama del SIIU, nombre, dobles
  grados que las combinan y asignaturas básicas y obligatorias en común; cada relación lleva sus motivos.
  244 de los 245 genéricos de grado con página tienen alguna
  (1.378 relaciones apoyadas en asignaturas comunes); la que no tiene nada cercano queda
  vacía.
- **Dobles grados que incluyen cada carrera** y los grados que forman cada doble; la ficha del doble enlaza los
  planes de sus dos grados.
- **Universidades** (`universidades.jsonl`): grados, ramas, modalidades, plazas, nota de corte mediana, indicadores
  del conjunto y horquilla de precios (públicas: grado completo; privadas: por curso).

## 5. Siguientes pasos

1. **Decisiones** (Álvaro las dejó a criterio de Claude el 31/10 a las 15:14; se pueden revertir):
   - Excepción del RUCT (§2): **se mantiene**. Las memorias solo están en el RUCT (el catálogo abierto del SIIU no
     las trae), el RUCT es público por norma y el robots.txt se vuelve a mirar en cada ejecución.
   - Zaragoza: **sus datos abiertos de notas de corte siguen fuera** (CC BY-NC choca con una web con anuncios, y
     tomar las mismas cifras de sus PDF sería saltarse esa licencia). Se pierde poco: QEDU da nota de corte a 71 de
     sus 76 grados por centro y la del curso anterior a 70. Lo que falta (años anteriores y cupos) se pide a la
     universidad cuando el portal tenga dirección pública.
   - Precios de las privadas: **se mantiene el significado** de §2: precio del primer curso tal como lo da la
     fuente, con reserva, matrícula y cargos cuando la fila da ese total, y la enseñanza aparte. El total del grado
     sale de la enseñanza, y en los dobles solo si el precio es por crédito.
2. Planes que no cuadran (sobre todo publicados solo por materias o sin carácter por asignatura): memorias del RUCT
   de los 1.020 grados sin plan comprobado (decidido por Álvaro), solo las páginas del plan. Desde las 11:30 del 30/10 el RUCT no responde a GitHub (tiempo agotado en cada petición; 5 de 6 memorias del primer
   tramo vacías), así que se canceló la tanda de 170 tramos. **Desde el servidor de España sí responde** (prueba de
   las 13:30: la memoria de Ingeniería en Sistemas de Información, 63 páginas en unos siete minutos, 37 asignaturas,
   plan comprobado con los créditos del RUCT, 186 = 186). Ese servidor lo comparten todas las conversaciones y el
   buzón de incidencias pide una sola lectura del RUCT a la vez en todo el proyecto: la noche del 30/10 leyó
   másters; las de grados (los 164 grados sin ningún plan y los 88 cuyo plan vigente no cuadra, 42 tandas de 6 de
   una en una; los 1.020 serían unas 170; lista en `trabajo/memorias_prioridad_v2.txt`) **corren desde las 11:10
   del 31/10** (ejecución 41188372738). A las 15:24, 2 tandas terminadas y la tercera en curso: cada una tarda de
   46 a 51 minutos, más las esperas cuando los boletines diarios ocupan el servidor, así que acabará el 2/11. Las
   tandas van de una en una aunque el servidor gane ejecutores: más a la vez serían varias lecturas del RUCT. El
   RUCT va lento (238 y 290 peticiones por tanda, unos 10 segundos cada una), así que una tanda no siempre lee sus
   6 memorias antes de su límite de 42 minutos: la primera leyó 3 y la segunda 5. Los códigos que quedan sin leer se apuntan en
   `trabajo/memorias_pendientes.txt` y se relanzan al final. El lector ya está en las fichas
   (`fichas.plan_de_memoria`: el plan de la memoria entra si el del BOE no cuadra y él sí cuadra con los créditos
   por tipo del RUCT; con una página sin leer no cuenta como comprobado).
3. Privadas sin precio (859): la Europea retiró sus PDF de 2025-2026 (404 también desde el
   servidor de España, 30/10) y la tabla 2026-2027 solo aparece en copias de terceros, que no son fuente; Católica de
   Valencia publica su tabla 2026-2027 en una ruta que su robots.txt prohíbe (no se pide); UNIR, VIU, UDIMA, CUNEF y la Europea no publican tabla; lo que no esté
   publicado, peticiones a cada universidad cuando el portal tenga dirección pública
   (`docs/estrategia-informacion-cerrada.md` §3.4). El índice de Common Crawl de los dominios de centros dio 710
   direcciones más y solo 3 grados con importe: esa vía está agotada.
4. Dobles de públicas sin precio (149): resoluciones de cada programa en Salamanca; UPV y UPV/EHU, de su web.
5. Notas de corte del resto de distritos. Tampoco responden desde el servidor de España (prueba de las 13:29): CiUG
   de Galicia y Universidad de Oviedo (su robots.txt no contesta, así que no se pide nada), ULPGC y Extremadura
   (403), La Rioja (429); la Comunitat Valenciana solo deja la primera adjudicación de 2026-2027 de la UV.
   Ilegibles: Burgos, UCLM y UPV/EHU desde 2022-2023. Pública de Navarra: sin lista final. Los cupos de reserva (titulados,
   mayores de 25, 40 y 45) ya van en las fichas junto al histórico publicable del cupo general
   (1.030 centros: Madrid, Andalucía y UPV/EHU); la convocatoria extraordinaria de Madrid y Cantabria, todavía no.
6. Mantenerlo al día: BOE diario (planes y modificaciones nuevos), QEDU y SIIU cada curso, RUCT semanal
   (acreditaciones y extinciones), webs de privadas en primavera-verano, notas de corte en cada adjudicación.
7. Generador de páginas de grado con el diseño «Noche en blanco» y el control de la ley SEO.

Límite conocido: 8 parejas de grados activos con el mismo nombre en la misma universidad (un título del RD
1393/2007 que se extingue y su sucesor del RD 822/2021) pueden compartir el plan más reciente, salvo que el texto
del BOE declare el código del título («Código Titulación: …»), que desde el 30/10 se respeta.

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
- **Másters (precios de privadas):** cuatro reglas de la tercera revisión de grados que valen igual para másters:
  los datos estructurados de una página solo valen si su texto muestra el mismo importe; un importe «desde» no es
  el precio; una página o lista cuya dirección nombra otra sede (`web_privadas.sede_ajena`) no vale para el
  centro; y `tarifas_grado.pedir_con_motivo` dice por qué no respondió cada dirección (robots.txt, límite, error).
- **Másters (planes del BOE):** `boe_grados.codigos_en_texto` lee el «Código Titulación» que declara el texto: un
  plan con el código de otro título no es de este.
- **Másters (listas de precios):** `tarifas_grado.lineas_html` lee las tablas con un lector de HTML (cierres de celda
  omitidos), `tarifas_grado.diagnostico_html` dice sin texto por qué una página de precios no dio importes, y
  `fichas.precio_por_cuentas` admite ya la cuota redondeada al euro, la enseñanza en cuotas iguales sin la matrícula
  y el total de la fila con reserva y matrícula; las filas con beca no son precio.
