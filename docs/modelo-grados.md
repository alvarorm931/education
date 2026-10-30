# Módulo de grados (carreras): universo, fuentes medidas y ficha

Versión 30/10/2026. Lo mantiene la conversación de grados. Todas las cifras salen de datos reales capturados el
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

En curso (30/10/2026): detalle e inserción de las 5.486 ofertas en cinco tramos de GitHub, una petición por
segundo (`grados.yml`, ejecución 40986848234).

### BOE: planes de estudios y altas

Del sumario ya capturado (2022-2026, rama `datos`): 603 planes nuevos, 942 modificaciones, 9 cambios de
denominación con plan actualizado, 66 correcciones de errores y 26 acuerdos de carácter oficial. 72
disposiciones publican varios planes a la vez.

Muestra al azar de 40 planes nuevos y 20 modificaciones (semilla fija; textos en la versión HTML del BOE, que su
robots.txt permite; `sondas/20261030T012640`):

| Dato | Planes nuevos (40) | Modificaciones (20) |
|---|---|---|
| Tabla con asignaturas o materias | 37 | 20 |
| A nivel de asignatura (no solo materia) | 24 | 18 |
| Créditos en casi todas las filas | 36 | 20 |
| Carácter (básica, obligatoria…) | 32 | 17 |
| Curso | 22 | 7 |
| Semestre | 12 | 5 |
| Tabla de créditos por tipo | 39 | 20 |
| **El listado cuadra con esa tabla** (básicas + obligatorias + prácticas + TFG) | **22** | **9** |

La última fila es la comprobación que importa: si la suma de las filas coincide con la tabla de créditos del
propio plan, el listado está completo. En los demás casos falta algo (materias en vez de asignaturas, prácticas y
TFG fuera de la tabla, resoluciones con varios planes) y el dato se completa con otra fuente o va a revisión.

Cobertura: 1.252 de los 3.265 grados activos (38 %) tienen plan o modificación publicados entre 2022 y 2026. El
resto tiene su plan en el BOE de años anteriores. `motor/grados/boe_historico.py` recorre el sumario de 2008 a 2021
con la misma API y guarda solo los planes, modificaciones y acuerdos de grado y de máster (prueba con las dos
últimas semanas de junio de 2010: 15 sumarios, 65 planes de grado). En curso el 30/10/2026 (ejecución
40987508205); después se descargan sus textos con `boe_grados textos`.

Altas: los 26 acuerdos dan 853 grados con código RUCT, nombre y universidad (todos con universidad).

### RUCT: bloqueado por su robots.txt

El lector del RUCT para grados (`motor/grados/ruct_grados.py`) reutiliza los parsers de másters, pero comprueba
robots.txt antes de cada petición. Resultado (30/10/2026): `https://www.educacion.gob.es/robots.txt` no responde,
ni desde GitHub (tiempo agotado) ni desde el servidor de España («Empty reply from server»). Según la RFC 9309
(2.3.1.4), un robots.txt que no se puede leer por error de red equivale a prohibirlo todo, y el motor no pide
nada. La misma RFC permite, si sigue sin poder leerse más de 30 días, tratarlo como inexistente.

El RUCT es un registro público por norma: «tendrá carácter público y de registro administrativo» (RD 1509/2008,
art. 1.1) y «la consulta al RUCT será pública» (art. 7). Leerlo como excepción, igual que los boletines oficiales,
es **decisión de Álvaro**.

Ojo: el lector de másters (`motor/estudios/ruct.py`) abre su propia sesión y no comprueba robots.txt.

Lo que aportaría el RUCT a grados: el identificador BOE del plan vigente de cada grado (también de los anteriores
a 2022) y la memoria con todas las asignaturas, su semestre, las menciones, las plazas por centro y, en las
memorias del RD 1393/2007, la evaluación por materia.

### Precio

- Públicas: QEDU da el precio del crédito en primera matrícula de cada oferta. Las normas de las 17 comunidades y
  la UNED para 2026-2027, con sus niveles, dónde está la lista de títulos y las bonificaciones que cambian el precio
  real, están en `docs/fuentes-precios-grado.md` (14 de 18 abiertas; pendientes Navarra, Murcia, Castilla y León y
  Madrid en parte).
- Privadas: QEDU no da el precio («N/D»). Sale de las tarifas de cada universidad, igual que en másters (PDF de
  tarifas y página del grado), con el mismo extractor con cita literal.

### Lo que falta por medir

- Rendimiento y abandono por título: SIIU (por universidad y rama) y datos abiertos de la Politécnica de Valencia,
  la Complutense y Murcia (por título). Sin medir.
- Notas de corte de cinco cursos o más por cupo: distritos (módulo de notas de corte, fase 2 de la guía).
- Guías docentes de grado: la guía decidió no hacerlas asignatura por asignatura para carreras. La memoria del
  RUCT da metodología y evaluación por materia, que basta para comparar.

## 3. La ficha del grado

Unidad: **grado × universidad** (un código de título). Si el mismo título se imparte en varios centros, la ficha
los lleva dentro, con la nota, las plazas y la modalidad de cada uno; el plan de estudios es el mismo y dos fichas
serían casi iguales (ley SEO). Dirección: `/universidad/{universidad}/grado/{grado}/`.

| Bloque | Dato | Fuente principal | Control |
|---|---|---|---|
| Identidad | nombre, código, universidad, pública o privada, centros, municipio | SIIU | QEDU, BOE |
| Tipo | grado, doble grado (y sus dos grados), régimen, rama, área | SIIU | RUCT |
| Plan | asignaturas con créditos, carácter, curso y semestre; menciones | BOE (plan vigente) | tabla de créditos del plan; RUCT |
| Reparto | créditos por tipo: básica, obligatoria, optativa, prácticas, TFG | BOE | RUCT |
| Acceso | nota de corte de dos cursos y nota media de admisión por centro | QEDU | distrito |
| Plazas | plazas de nuevo ingreso por centro | QEDU | oferta del Ministerio |
| Precio | €/crédito en primera matrícula y total del grado; bonificaciones | QEDU y norma autonómica / tarifa de la privada | anuario del Ministerio |
| Empleo | afiliación, autónomos, indefinidos, cotización adecuada, base media de cotización; comparación con su ámbito | QEDU | SIIU |
| Modalidad | presencial, no presencial, varias; idioma extranjero | SIIU | QEDU |
| Calidad | verificación, acreditaciones, modificaciones con fecha | RUCT (pendiente) | BOE |

Cada dato lleva fuente, URL y fecha de captura; la fecha solo cambia si cambia el dato.

### Datos mínimos para indexar (propuesta)

La ley SEO fija los del máster («asignaturas y precio») pero no los del grado. Propuesta, a decidir:

- **asignaturas** comprobadas (el listado cuadra con la tabla de créditos del plan o viene del RUCT);
- y al menos una cifra propia del grado: **nota de corte o precio**.

Cuando se decida, se declara en `DATOS_MINIMOS` de `motor/seo/reglas.py` (cada módulo declara los suyos; «grado»
ya figura como tipo de ficha en `motor/seo/control.py`): `"grado": [["asignaturas"], ["nota_corte", "precio_total",
"precio_credito"]]`.

Con lo medido, casi todos los grados de públicas lo cumplirán cuando el plan esté capturado. Los de privadas
necesitarán su tarifa, porque QEDU no da precio y casi nunca nota. Sin esos datos, `noindex`, como en másters.

### Cómo se genera (`motor/grados/fichas.py`)

Une catálogo, genérico, QEDU y plan del BOE sin pedir nada a ninguna fuente, y marca cada ficha como indexable o
no, con el motivo. Con lo capturado el 30/10/2026 (QEDU solo con las tarjetas; BOE con la muestra de 60 planes):
4.296 fichas activas (3.265 grados y 1.031 dobles), 4.265 con sus centros en QEDU y 2.662 con nota de corte; 372
comparativas (245 genéricos de grado y 127 de doble grado con página). Precio, plazas e inserción entran al
terminar los detalles de QEDU; las asignaturas, según se capturen los planes.

## 4. Comparar

Lo que hoy no da nadie junto: **el mismo grado en todas las universidades, en una tabla**. Por cada genérico con
página (`/grado/{grado}/`) y en el comparador (`/comparar/grado/{grado}/{a}-vs-{b}/`), las columnas son:

- acceso: nota de corte de los dos cursos y nota media de admisión;
- plazas y modalidad;
- precio de primera matrícula (crédito × créditos) y bonificaciones;
- créditos por tipo, sobre todo prácticas externas y optativas, y menciones;
- inserción: afiliación, cotización adecuada, base media de cotización e indefinidos.

Dos datos propios que salen del plan de estudios:

- **Asignaturas en común**: qué parte del plan de una universidad comparte con las demás del mismo grado y
  cuáles solo están en ella («en Derecho de X hay 4 asignaturas que no tiene ningún otro Derecho»).
- **Qué se estudia en primer curso**, comparado entre universidades (`/grado/{grado}/primer-curso/`).

Esto también hace posible la búsqueda inversa por asignatura (`/carreras-con/{asignatura}/`), pero exige
normalizar nombres de asignatura («Estadística I», «Estadística aplicada a…»). Se diseña cuando haya planes
suficientes.

## 5. Siguientes pasos, por lo que más acerca a la ficha completa

1. **Decisión de Álvaro sobre el RUCT** (§2): con él, el plan vigente de todos los grados y sus memorias.
2. **Planes anteriores a 2022**: selección del sumario 2008-2021 en curso; después, textos de esos planes y
   tablas con la comprobación de créditos (sirve también a másters).
3. **QEDU completo** (en curso) y, después, cruce con el catálogo y primer cuadro por genérico.
4. **Precios**: lista de títulos por nivel de cada comunidad (anexos de `docs/fuentes-precios-grado.md`) para
   comprobar el precio de QEDU, y tarifas de las privadas con el extractor de másters.
5. Rendimiento y abandono por título donde haya datos abiertos; afiliación del SIIU por universidad y rama.
6. Normalización de asignaturas y «asignaturas en común».
7. **Privadas**: sin precio en QEDU y casi sin nota de corte, la mayoría de sus 1.410 grados y dobles activos no
   cumplirá los datos mínimos hasta tener su tarifa. Es el hueco más grande del módulo.

## 6. Avisos para las otras conversaciones

- **Másters:** QEDU da lo mismo para másters (niveles `'MASTER','MASTERD'`): plazas, precio del crédito de las
  públicas, tasa de afiliación e inserción por título y centro (`motor/grados/qedu.py` sirve tal cual con
  `--nivel master`).
- **Másters:** `motor/estudios/ruct.py` no comprueba robots.txt. El robots.txt de `www.educacion.gob.es` no
  responde desde GitHub ni desde España, así que el resto del motor no pide nada a ese servidor. Pendiente de la
  decisión de Álvaro sobre el RUCT (§2).
- **Todas:** el catálogo SIIU y el sumario del BOE ya capturados sirven para grados sin volver a pedirlos
  (`motor/grados/catalogo.py --originales`, `motor/grados/boe_grados.py actos`).
