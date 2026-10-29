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
- **Verificación en su web, primer índice completo** (10.955 candidatos): 1.332 con fichas de programa y
  señal de España tras los filtros; precisión medida a mano (60 al azar, 47 pasan los filtros): 77 %. Estimación: unos 1.000 (850-1.200 por el margen de la muestra)
  proveedores reales no oficiales y unas 90.000 URL de programa. El segundo barrido (10.462) está en marcha.
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
comprueba que la frase está en la página: si no, el valor no se acepta y va a revisión. Coste estimado con
precios de lote: unos 12 dólares por cada 30.000 páginas. Necesita la clave de la API como secreto de
GitHub (`ANTHROPIC_API_KEY`).

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

## 8. Siguientes pasos

Ordenados por lo que más acerca a tener, para cada máster, lo que hoy se da solo al registrarse
(`docs/estrategia-informacion-cerrada.md`).

1. **Cerrar el censo**: barrido de los 10.955 candidatos de Common Crawl (en marcha el 29/10/2026), segundo
   índice de Common Crawl (en marcha), candidatos enlazados desde páginas de colaboradores y revisión a
   mano de una muestra de verificados para medir la precisión.
2. **Extracción con cita** de las páginas de programa de los proveedores verificados (`extraer.py`, lote de
   Claude Haiku). Necesita la clave `ANTHROPIC_API_KEY` como secreto de GitHub y el archivo privado de
   originales (R2): la rama del repositorio es pública y no guarda páginas ajenas.
3. **Seguimiento por campo** (`seguimiento.py`) sobre lo extraído: qué campos están tras el registro en
   cada máster y lista de peticiones por centro.
4. **Oficiales**: unir cada título del RUCT con su página (texto del enlace; en marcha), fichas y memorias
   del RUCT de los 4.347 activos, precio por crédito de los 19 decretos y QEDU (según su ayuda, precio y
   plazas solo de públicas), guías docentes por plataforma (SIGMA DOA primero).
5. **Peticiones** a centros cuando el portal tenga dirección pública; peticiones formales a universidades
   públicas (Ley 19/2013) y al Ministerio (Ley 37/2007).
6. Becas, Excel de oferta de plazas, másters habilitantes y profesiones reguladas.
