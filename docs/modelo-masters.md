# Módulo de másters: universo, fuentes medidas y ficha

Versión 29/10/2026. Complementa `docs/encargo-masters.md`. Todas las cifras de este documento salen de
descargas reales hechas desde GitHub el 29/10/2026; lo que no está medido se dice.

## 1. El universo: cuántos másters hay y dónde está la lista

No hay un registro único de «todos los másters». Hay cuatro capas, cada una con su fuente.

| Capa | Lista completa | Cuántos | Cómo se conecta |
|---|---|---|---|
| Máster universitario oficial | Sí: catálogo SIIU del Ministerio (por centro) + ficha del RUCT | 4.347 títulos activos (4.166 simples y 181 dobles) en 95 universidades, 4.906 imparticiones activas por centro; 4.859 con extinguidos | XLSX anual, `motor/estudios/catalogo.py` |
| Altas nuevas | Sí: acuerdos del Consejo de Ministros en el BOE, con el código RUCT de cada título | 27 acuerdos entre 2022 y 2026 | sumario del BOE ya capturado, `motor/estudios/boe_masters.py` |
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

## 5. Siguientes pasos

1. Fichas del RUCT de los 4.859 títulos (una pasada, unos 81 minutos) y unión con el catálogo y el BOE.
2. Memorias de los activos en el servidor de España, por la noche, empezando por los títulos con más
   demanda de búsqueda.
3. Precios públicos: decretos 2026-2027 de las 17 comunidades y anuario del Ministerio.
4. Tarifas de las privadas: registro de URL de tarifa por universidad (40) y captura anual.
5. Títulos propios: conector por universidad, empezando por las de más oferta.
6. Guías docentes solo donde la memoria no da evaluación (formato RD 822/2021).
