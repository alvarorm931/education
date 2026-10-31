# Plan de ejecución SEO del portal

Versión del 31/10/2026. Cómo se lleva a cabo la estrategia (`docs/estrategia-seo.md`) con lo que hay hoy en AWS y en los datos del motor. Versión para leer: `Plan_ejecucion_SEO.docx`, entregada a Álvaro; inventario en `Plan_SEO_inventario_31-10-2026.xlsx`.


## La respuesta en una página

La estrategia es la del documento del 30/10/2026 (qué maximizar y qué evitar). Este documento explica cómo la voy a ejecutar. Parte de un inventario hecho hoy entre las 15:20 y las 15:50 (Madrid) con todo lo que hay guardado: el almacén S3 de AWS, el servidor de España y los datos que el motor ha sacado de esos originales (ramas `datos` y `sondas`). Todas las cifras son recuentos exactos; lo estimado se dice.

**Lo que hay hoy.** En AWS hay 359.635 originales que ocupan 50,90 GiB, y de ellos han salido 168.239 fichas posibles: 139.025 procesos de oposición, 4.296 grados, 4.734 másters oficiales y 20.184 programas de máster no oficiales. De esas fichas, **52.978 cumplen ya los datos mínimos de la ley SEO**. A ellas se suman 7.500 páginas de listado y lugar con oferta real, así que hoy se podrían publicar 60.478 páginas. El 30/10 eran 32.276. El límite no es el inventario, sino cuántas páginas indexa Google en un dominio nuevo.

**Lo que voy a hacer, en ocho pasos**

1. **Una sola fábrica de páginas.** La construyo en `motor/web/` y produce la web entera con el diseño «Noche en blanco» a partir de los datos de oposiciones, grados y másters. Una tabla de direcciones que solo crece asegura que una dirección publicada no cambia nunca. Necesita el acuerdo de Álvaro y de las conversaciones de grados y másters.
2. **Ninguna página sale sin pasar el control** (`motor.seo.control`). Primero añado cuatro reglas que salen de los fallos encontrados hoy:
   - convocante genérico;
   - provincia por código del INE;
   - mismo proceso publicado dos veces;
   - datos mínimos de las notas de corte.
3. **Publicación directa a Cloudflare desde GitHub, dos veces al día.** La web nunca pasa por el repositorio público. En el almacén de AWS se guarda cada página publicada por su huella y el estado de cada dirección. Así se puede volver atrás y demostrar qué se publicó y cuándo, y la fecha de una página solo cambia si cambia su dato. No hace falta ningún permiso nuevo en AWS.
4. **Arreglar antes de la primera página los fallos de datos que cambian el plan.** Los más graves:
   - casi ninguna oposición del Estado, de las comunidades ni de las universidades llega al mínimo, porque su convocante va vacío;
   - 1.781 fichas del BOJA tienen por convocante «Ayuntamientos»;
   - 2.591 combinaciones de convocante, cuerpo, año y turno se repiten.
5. **Cinco oleadas, empezando por las oposiciones vivas.** La oleada 1 son 9.946 páginas: las fichas con plazo abierto o abierto en los últimos doce meses, provincias, comunidades, cuerpos grandes y plazo abierto. Con el arreglo del convocante serían 11.374. Fecha propuesta: a partir del 9 de diciembre de 2026, si el dominio se decide la semana que viene.
6. **No se abre una oleada hasta que la anterior se indexa.** Las fichas no indexadas no se sustituyen por más fichas. La señal la dan Search Console y Bing Webmaster Tools.
7. **Avisos a los buscadores en cada publicación:**
   - IndexNow con lo nuevo, lo cambiado y lo retirado;
   - Indexing API de Google para las fichas con `JobPosting`, empezando por los plazos más cortos;
   - sitemaps con `lastmod` real.
8. **Vigilancia diaria del sitio servido y revisión mensual de la ley** contra la documentación oficial. Mi trabajo de cada día, semana y mes está en el capítulo 8.

**Lo que necesito de Álvaro esta semana.** El anexo C de la estrategia ya está aprobado (31/10, 15:13). Falta esto (detalle en el capítulo 9):

- el nombre y el dominio;
- que la fábrica de páginas sea una sola y la lleve esta conversación;
- la cuenta de Cloudflare con el plan de Workers de pago (5 dólares al mes como mínimo por cuenta) y su clave de despliegue como secreto de GitHub;
- Search Console y Bing Webmaster Tools el mismo día que el dominio.

| Lo que hay hoy | Cifra | Medido |
|---|---|---|
| Originales en el almacén S3 | 359.635 objetos, 50,90 GiB | 31/10, 13:05 |
| Fichas que existen | 168.239 | 31/10, 15:30 |
| Fichas con los datos mínimos | 52.978 | 31/10, 15:30 |
| Páginas de listado y lugar con oferta real | 7.500 | 31/10 (oposiciones) y 30/10 (estudios) |
| Procesos con plazo abierto hoy | 890 (524 publicables; 623 con el arreglo del convocante) | 31/10, 15:30 |
| Fichas de proceso con dos actos o más | 12.728 de 40.684 (31,3 %) | 31/10, 15:30 |

## Lo que tenemos en AWS

En AWS hay dos cosas: el almacén S3 con los originales y el servidor de España, que hace trabajos de cómputo pero no guarda datos. Lo que se puede publicar no está en ninguno de los dos directamente. Sale de los originales y se guarda en las ramas `datos` y `sondas` del repositorio.

### El almacén S3: 50,90 GiB de originales

Medición del flujo «Peso del almacén» (`peso-s3.json`, rama `vigilancia`) del 31/10/2026 a las 13:05 de Madrid. Son las versiones vigentes; el almacén tiene el control de versiones activado y no se borra nada.

| Familia | Objetos | Tamaño | Parte del total | Qué es |
|---|---|---|---|---|
| Boletines provinciales | 141.820 | 43,38 GiB | 85,2 % | PDF y textos de 39 boletines provinciales: boletines enteros y anuncios |
| Másters: webs de centros | 82.377 | 5,99 GiB | 11,8 % | páginas de programas (HTML y versión pintada con navegador), lo enviado a la API de Claude con sus respuestas y el conjunto final |
| Boletines autonómicos | 76.831 | 1,22 GiB | 2,4 % | 19 boletines: las 17 comunidades, Ceuta y Melilla |
| BOE | 37.299 | 269 MB | 0,5 % | sumarios de 2008 a 2021 (planes de estudio) y textos de anuncios |
| QEDU (Ministerio) | 13.157 | 4,9 MB | 0,0 % | plazas, precio del crédito e inserción laboral por grado y máster |
| RUCT | 8.045 | 32 MB | 0,1 % | fichas y memorias de títulos oficiales |
| Notas de corte y SIIU | 103 | 29 MB | 0,1 % | documentos oficiales de notas de corte de los distritos e indicadores del SIIU |
| **Total** | **359.635** | **50,90 GiB** | **100 %** | |

Qué significa para el SEO:

- **Los originales son la prueba de cada dato, no el contenido que se publica.**
   - Cada dato publicado lleva fuente, URL y fecha de captura, y el original guardado con su huella sha256 demuestra lo que decía la fuente ese día.
   - Sirven también para rehacer la extracción cuando mejora el código sin volver a pedir nada a las fuentes.
- **El texto de un boletín no se publica entero.**
   - El BOE permite reutilizarlo citando la fuente.
   - Aun así, una copia del texto sería contenido duplicado, y el original es el del boletín.
   - Lo que posiciona son los hechos con fuente, contados con nuestras palabras y con el enlace al documento oficial. La cita literal se usa solo donde aporta: la frase del plazo o la del requisito.
- **El almacén crece deprisa con la carga histórica de los boletines:**
   - 41,36 GiB a las 11:15 y 50,90 GiB a las 13:05;
   - unos 1,2 dólares al mes de almacenamiento al ritmo de hoy;
   - no afecta al SEO; lo vigila la conversación de estado.

### El servidor de España: cómputo, no datos

`motor-espana` (Lightsail, 2 GB de memoria, 2 vCPU, 60 GB de disco, 12 dólares al mes) es un ejecutor de GitHub. No guarda datos propios: lee las fuentes que no responden a GitHub y deja los resultados en las ramas y en el almacén.

**No lo voy a usar para el SEO**, por tres motivos:

- Solo tiene un ejecutor y está lleno. La carga diaria de boletines ocupa unas 6 horas y media, y la lectura del RUCT de grados lleva 42 tramos en fila hasta el 2/11.
- No tiene las librerías del sistema de Chromium. Las tiene que instalar Álvaro, y el control las necesita para pintar las páginas.
- Mientras el repositorio sea público, los ejecutores de GitHub son gratuitos y tienen más memoria.

Cuando el repositorio pase a privado (plan acordado del 30/10), la fábrica y el control tendrán que ir al servidor. Antes habrá que medir si caben en 2 GB de memoria.

### Lo que sale de esos originales

| Familia | Dónde | Registros | Generado |
|---|---|---|---|
| Procesos de oposición | `datos/oposiciones/procesos/2022.jsonl` a `2026.jsonl` | 139.025 procesos (107.920 locales, 16.508 autonómicos, 11.884 de universidades, 1.241 estatales, 257 forales y 1.215 de otros) | descargado a las 15:25 |
| Datos de las bases con IA (frase literal comprobada) | dentro de cada proceso (`datos_bases`) | 7.524 procesos | mismo |
| Fichas de grado | `sondas:fichas-grados/20261030/` | 4.296 fichas (3.265 grados y 1.031 dobles), 372 comparativas, 13.026 direcciones estables | 31/10, 07:20 |
| Másters oficiales | `sondas:masters-estado/conjunto/` | 4.734 títulos (4.347 del catálogo y 387 altas del BOE) | 31/10, 03:45 |
| Másters no oficiales y títulos propios | mismo | 20.184 programas | mismo |

### Lo que se va a guardar en AWS para el SEO

En el mismo almacén, bajo `seo/`. La política actual (escribir solo si la clave no existe, leer y listar) sirve tal cual. No hace falta ningún cambio de permisos ni de la conversación de estado.

| Prefijo | Qué | Para qué |
|---|---|---|
| `seo/paginas/{sha256}.html.gz` | cada versión publicada de cada página, guardada por su huella | volver atrás, demostrar qué se publicó y cuándo, alimentar el registro de correcciones |
| `seo/estado/AAAA-MM-DD-HHMM.json.gz` | por dirección: huella, `lastmod`, indexable, empleo y la página de la versión | que la fecha solo cambie si cambia el dato; saber qué avisar a los buscadores |
| `seo/informes/…` | control de cada publicación, vigilancia diaria y datos diarios de Search Console y Bing | Search Console guarda solo 16 meses de rendimiento; aquí quedan para siempre |

Las páginas se guardan por huella: una página que no cambia no ocupa nada nuevo. El tamaño real de una página se medirá con el prototipo de la fábrica; con cualquier tamaño razonable, el coste es de céntimos al mes.

## Qué se puede publicar hoy

Los criterios son los datos mínimos de `motor/seo/reglas.py`. Las cifras de oposiciones y de másters son de hoy. Las de listados de estudios (grados, universidades y notas de corte) son del inventario del 30/10, porque sus fuentes no han cambiado desde entonces.

### Fichas

| Sección | Fichas que existen | Con los datos mínimos | Regla | El 30/10 |
|---|---|---|---|---|
| Oposiciones (procesos) | 139.025 | **38.903** (40.684 menos 1.781 con convocante genérico) | convocante + plazas + plazo | 14.230 |
| Grados y dobles grados | 4.296 | **2.181** (1.766 grados y 415 dobles) | asignaturas comprobadas + nota de corte o precio | 2.118 |
| Másters oficiales | 4.734 | **2.961** (2.608 de públicas y 353 de privadas) | asignaturas + precio | 436 |
| Másters no oficiales y títulos propios | 20.184 | **8.933** (de 495 proveedores) | asignaturas + precio | 7.982 |
| **Total** | **168.239** | **52.978 (31,5 %)** | | 24.766 |

Lo que más ha cambiado en un día:

- **Oposiciones**: las fichas publicables se multiplican por 2,7.
   - El 30/10 solo generaban procesos el BOE y 14 boletines autonómicos. Hoy los generan también los provinciales.
   - De las 40.684 que cumplen la regla, por origen: 24.718 del BOE, 9.446 de boletines provinciales y 6.520 de autonómicos.
   - Además, ya hay fichas de 2022 y 2023 (13.626), que el 30/10 casi no había.
- **Másters oficiales**: el precio del crédito de QEDU, las normas autonómicas y las tablas de precios de las universidades las multiplican por 6,8.
- **Oposiciones fuera de lo local**: de las 40.684 que cumplen la regla, 40.618 son locales; solo hay 60 autonómicas y 6 estatales. No es falta de datos, es un hueco en el formato (capítulo 4).

### Páginas de listado y de lugar

Umbrales del anexo C de la estrategia, aprobados por Álvaro el 31/10/2026 a las 15:13. Se aplican sin contar las fichas de convocante genérico.

| Página | Hoy | Criterio |
|---|---|---|
| `/oposiciones/en/{provincia}/` | 52 | al menos una ficha; por el código del INE, no por el nombre (capítulo 4) |
| `/oposiciones/en/{comunidad}/` | 19 | ídem |
| `/oposiciones/{cuerpo}/` | 705 con 10 procesos o más (141 con 50 o más) | antes de unificar sinónimos |
| `/oposiciones/{cuerpo}/{comunidad}/` | 791 con 10 procesos o más | ídem |
| `/oposiciones/en/{municipio}/` | 2.696 (2.668 con 3 procesos o más y 28 con uno abierto) | umbral aprobado; hay que subirlo también en la ley, que hoy pide uno |
| Listados fijos (plazo abierto, por titulación) | 7 | |
| `/grado/{grado}/` | 297 | con una ficha indexable o más (30/10) |
| `/universidad/{universidad}/` | 68 | con algún grado indexable (30/10) |
| `/nota-de-corte/{grado}/{universidad}/` | 732 | con histórico comprobado (30/10); faltan sus datos mínimos en `reglas.py` |
| `/nota-de-corte/{grado}/{comunidad}/` | 205 | tres títulos o más (30/10) |
| `/carreras-con/{asignatura}/` | 1.928 | asignatura en cinco títulos o más (30/10) |
| **Total** | **7.500** | |

Sin contar:

- listados de máster por área y ciudad (los no oficiales no tienen área);
- comparadores de dos grados, solo bajo demanda;
- FP, becas, sueldos y «cómo ser».

### Totales

| | Páginas |
|---|---|
| Publicables hoy (fichas con mínimos + listados) | **60.478** |
| Más las oposiciones no locales cuando su convocante esté relleno | 65.742 |
| Media de páginas indexadas que supone el modelo económico para 2027 (escenario base) | 30.000 |

El inventario ya dobla lo que pide el modelo económico. Por eso el plan no busca más páginas, sino que Google indexe las que hay y que cada una esté por encima de la de la competencia. Eso decide el orden de las oleadas (capítulo 6).

## Lo que he encontrado en los datos y cambia el plan

Diez hallazgos de hoy. Cada uno dice la cifra, por qué importa para posicionar, qué hay que hacer y quién lo hace. Los fallos de datos los arregla el módulo que los produce. Mientras tanto, el control impide que lleguen a una página.

### 1. Las oposiciones grandes no llegan al mínimo

- **Cifra**:
   - de las 40.684 fichas de proceso que cumplen la regla, 40.618 son locales; solo 60 son autonómicas y 6 estatales;
   - en los procesos del Estado, de las comunidades y de las universidades, el campo `convocante` va vacío y el organismo está en `organismo` («MINISTERIO DE TRANSPORTES…», «COMUNIDAD AUTÓNOMA DE CANTABRIA»);
   - si el organismo contara como convocante, entrarían 5.264 fichas más: 2.515 autonómicas, 1.801 de universidades, 466 estatales y 482 de otros tipos. De ellas, 1.428 son de los últimos doce meses y 99 tienen hoy el plazo abierto.
- **Por qué importa**:
   - son las oposiciones con más plazas y más búsquedas: docentes, sanidad, cuerpos generales del Estado, policía y justicia;
   - sin ellas, el portal empieza siendo de oposiciones municipales.
- **Qué hacer**:
   - que el motor rellene `convocante` en todos los ámbitos, con su tipo (ministerio, consejería, universidad) y la comunidad;
   - la regla del control no cambia: pide un convocante, venga del ámbito que venga.
- **Quién**: conversación de oposiciones.
- **Ojo, también**: muchos procesos docentes autonómicos no tienen plazas (van por especialidad en anexos) o no tienen plazo. Ejemplo: la convocatoria de Maestros de Aragón de 2022, con 658 plazas y sin plazo. Las especialidades son la siguiente pieza.

### 2. 1.781 fichas con «Ayuntamientos» como convocante

- **Cifra**:
   - 1.781 fichas que cumplen la regla tienen por convocante la palabra «Ayuntamientos», y todas son del BOJA;
   - el título dice el ayuntamiento real («del Ayuntamiento de Alcaudete», «del Ayuntamiento de El Almendro»), pero se toma el nombre de la sección del boletín;
   - ninguna tiene hoy el plazo abierto.
- **Por qué importa**:
   - se publicarían 1.781 páginas con el convocante mal y se mezclarían todos los ayuntamientos de Andalucía en uno;
   - en un tema sensible (YMYL), un dato mal es peor que un dato que falta.
- **Qué hacer**:
   - regla nueva en el control: un convocante que es un nombre genérico («Ayuntamientos», «Diputaciones», «Universidades», «Entidades locales») bloquea la página;
   - en el motor, tomar el convocante del título.
- **Quién**: yo, el control; la conversación de oposiciones, el motor.

### 3. El mismo proceso dos veces y direcciones que chocan

- **Cifra**:
   - 2.591 combinaciones de convocante, cuerpo, año y turno se repiten, con 7.428 procesos;
   - sin el turno, 2.946 combinaciones con 8.431 procesos;
   - en 701 combinaciones hay dos procesos que abren el plazo el mismo día, y en 501 de ellas también con las mismas plazas. Son duplicados probables, pero no siempre: los de León del ejemplo de abajo abren el mismo día, con las mismas plazas, y son distintos.
- **Seis combinaciones revisadas al azar**:
   - en dos, el mismo proceso publicado en el BOP de Barcelona y en el DOGC;
   - en una, el mismo texto publicado dos veces en el BOP de Castellón;
   - en una, procesos distintos: cuatro de Conserje en León, el mismo día, con destinos distintos;
   - en una, dudoso: dos anuncios del BOE de El Real de Gandia, de marzo y abril de 2025, de una plaza de Técnico de Educación Infantil cada uno; pueden ser dos procesos o el mismo convocado otra vez, y lo dirán las bases;
   - en una, el convocante genérico del hallazgo 2.
- **Por qué importa**:
   - dos fichas del mismo proceso compiten entre sí y Google elige una canónica que puede no ser la nuestra;
   - dos procesos distintos con la misma dirección no se pueden publicar.
- **Qué hacer**:
   - la conversación de oposiciones ya une desde las 12:30 las bases del BOP con su anuncio en el boletín autonómico; esos datos aún no estaban en lo medido;
   - el control marca las fichas con el mismo convocante, cuerpo, fecha de apertura y plazas;
   - solo publica la segunda si algo de sus datos las distingue: destino, especialidad, sistema o turno. Si nada las distingue, la deja fuera y avisa;
   - además, el control de similitud ya bloquea dos páginas casi iguales;
   - las direcciones salen de una tabla estable como la de grados (`motor/grados/identificadores.py`): cada proceso recibe su dirección la primera vez y no la cede nunca;
   - se aplica la regla aprobada el 31/10: turno y, si hace falta, el mes;
   - cuando ni el mes distingue, como en los cuatro de León del mismo día, hace falta una pieza más: el destino o la especialidad («conserje-colegios»). Es lo único de esta regla que pregunto a Álvaro.
- **Quién**: yo, la tabla de direcciones y la regla; la conversación de oposiciones, la unión de duplicados.

### 4. La provincia, escrita de 77 maneras

- **Cifra**:
   - el campo `provincia` tiene 77 valores distintos para 52 provincias: «Barcelona. Direcció dels Serveis de Recursos Humans…», «Ávila.- Recursos Humanos…», «Araba/Álava» y «Álava»;
   - el código del INE (`convocante.provincia_codigo`) está bien: 52 códigos en 37.245 fichas;
   - 1.658 fichas no lo tienen: consejos comarcales, cabildos, mancomunidades.
- **Por qué importa**: con el nombre saldrían páginas de provincia duplicadas o con nombres que no busca nadie.
- **Qué hacer**:
   - las páginas de lugar se hacen solo con el código del INE y el nombre oficial;
   - las 1.658 sin código no van en ninguna provincia hasta tenerlo.
- **Quién**: yo, en la fábrica y en el control.

### 5. Cuerpos con varios nombres

- **Cifra**: en las fichas publicables hay 24.286 claves de puesto distintas, y algunos cuerpos tienen varios nombres:
   - `policia-local` (1.734) y `agente-policia` (37);
   - `operario-servicio-multiple` (837) y `peon-servicio-multiple` (290).
- **Por qué importa**:
   - dos páginas de cuerpo para la misma búsqueda se quitan posiciones la una a la otra;
   - la página del cuerpo es la que más búsquedas puede atraer de la sección: «oposiciones policía local», «auxiliar administrativo».
- **Qué hacer**:
   - una taxonomía de cuerpos con el nombre que se busca y sus variantes, antes de crear ninguna página de cuerpo;
   - los 141 cuerpos con 50 procesos o más, primero.
- **Quién**: la conversación de oposiciones, con mi revisión de los nombres.

### 6. La historia del proceso ya es el diferencial

- **Cifra**:
   - 12.728 de las 40.684 fichas que cumplen la regla tienen dos actos o más (31,3 %);
   - el 30/10, sobre otros datos, eran el 4,2 %;
   - los actos más frecuentes: listas de admitidos (9.100), nombramientos (3.321), correcciones (1.861), aprobados (793), tribunal (671) y examen (197).
- **Por qué importa**:
   - los competidores programáticos publican una página por anuncio;
   - una página por proceso, con su historia, responde a lo que se busca después de la convocatoria: admitidos, fecha de examen, aprobados.
- **Qué hacer**:
   - la plantilla de la ficha pone la línea de tiempo arriba, después del resumen;
   - cada acto nuevo cambia la huella de la ficha, su `lastmod` y el aviso a los buscadores.
- **Quién**: yo, en la plantilla.

### 7. Los datos de las bases están en un tercio de la primera oleada

- **Cifra**:
   - 3.612 de las 9.727 fichas de la oleada 1 tienen ya los datos de sus bases sacados con IA, cada uno con su frase literal comprobada;
   - son requisitos, titulación, tasa, ejercicios, temas y bolsa;
   - faltan 6.115. Al coste medido por la conversación de oposiciones (7,87 dólares por unos 9.300 procesos), completarlos cuesta unos 5 dólares.
- **Por qué importa**:
   - son las respuestas a «requisitos», «temario» y «tasa» de cada oposición;
   - el modelo de la ficha que se cita en las IA es una respuesta corta con hechos y fuente.
- **Qué hacer**: extraer las bases de toda la oleada 1 antes de publicarla, sin esperar a la pasada diaria de 600.
- **Quién**: la conversación de oposiciones (lo decide Álvaro, por el coste).

### 8. Pocas fichas con plazo abierto y un cupo de avisos que no llega el primer día

- **Cifra**:
   - hoy hay 890 procesos con el plazo abierto: 524 publicables y 623 con el arreglo del convocante;
   - 516 de los 890 tienen el grupo (A1, A2, C1…).
- **Por qué importa**:
   - son las fichas con `JobPosting` y las que más rápido traen tráfico;
   - la Indexing API de Google admite 200 avisos al día: en el lanzamiento hacen falta unos tres días para avisar de todas;
   - el plazo es una fecha estimada (festivos de cada comunidad, sin los locales), y la ficha tiene que decirlo.
- **Qué hacer**:
   - en el lanzamiento, avisar primero de las que cierran antes;
   - después, el ritmo diario cabe con holgura en el cupo;
   - `validThrough` con la fecha estimada y el marcado se retira el día siguiente al cierre.
- **Quién**: yo.

### 9. Másters no oficiales: un solo grupo pone el 28,3 % de las fichas

- **Cifra**:
   - de las 8.933 fichas no oficiales con los datos mínimos, 2.525 son de centros del grupo EDUCA EDTECH: Euroinnova 1.884, INESEM 341, INEAF 152 y Red Educa 148;
   - el grupo nombra a esos cuatro como suyos;
   - los diez primeros proveedores suman el 45,1 %;
   - entre ellos hay centros que se presentan como «universidad» o «university» (SEIUM, 521 fichas; GUTEC University, 173) y que hay que comprobar contra el RUCT antes de publicarlos.
- **Por qué importa**:
   - una sección de másters que es sobre todo el catálogo de un grupo de formación en línea parece un escaparate, no una guía;
   - elegir estudios es un tema sensible;
   - Álvaro pidió priorizar siempre de mayor a menor reputación.
- **Qué hacer**:
   - los no oficiales entran en la última oleada;
   - antes: control de similitud entre fichas del mismo proveedor, un tope de fichas por grupo y proveedor (propuesta: 100), el orden de reputación y la comprobación de quién puede llamarse universidad.
- **Quién**: decide Álvaro; la conversación de másters prepara la lista; yo aplico el control.

### 10. Másters oficiales: indexables en las universidades de más reputación

- **Cifra**, por grupo de reputación (`motor/estudios/reputacion.py`):

| Grupo | Másters | Con los datos mínimos | Parte |
|---|---|---|---|
| Diez primeras del QS 2026 | 1.118 | 893 | 80 % |
| Grupo 1 del U-Ranking y escuelas de negocio (IE, Ramon Llull, ESADE, IESE, Comillas, Deusto, CUNEF) | 311 | 76 | 24 % |
| Grupo 2 y públicas grandes | 1.599 | 1.262 | 79 % |
| Resto | 1.706 | 730 | 43 % |

- **Por qué importa**:
   - la oleada de másters puede empezar por las universidades que más se buscan, con datos completos;
   - las escuelas de negocio no publican el precio y quedan fuera mientras no se consiga.
- **Qué hacer**:
   - oleada 4 en ese orden;
   - las fichas sin precio de las privadas son la lista de peticiones a los centros (estrategia de información cerrada).
- **Quién**: yo, el orden; la conversación de másters, los precios.

## Cómo se construye y se publica la web cada día

### La cadena

Una sola cadena, de los datos del día a la web servida. Corre en los ejecutores de GitHub, lee las ramas `datos` y `sondas` y no escribe en ellas. Por eso no compite con la cola de `rama-datos` ni con la de `sondas`.

| Paso | Qué hace | Dónde corre | Qué deja | Si falla |
|---|---|---|---|---|
| 1. Datos del día | Oposiciones, grados y másters publican sus datos con sus flujos de siempre | sus flujos | ramas `datos` y `sondas` | se usa la última versión buena |
| 2. Fábrica de páginas | Genera la web entera con «Noche en blanco» y el manifiesto `control/paginas.jsonl`; da cada dirección desde la tabla estable | ejecutor de GitHub | carpeta `web/` en el disco del ejecutor | no se publica nada; queda la versión anterior |
| 3. Control | `python -m motor.seo.control --aplicar`, con Chromium en tres páginas por plantilla | mismo | informe en la rama `seo` | si algo bloquea, no se publica esa tanda y el aviso sale en el informe |
| 4. Estado y versiones | Compara con el estado anterior: `lastmod` solo cambia si cambia la huella del contenido principal | mismo, con el rol de AWS | `seo/estado/` y `seo/paginas/` en S3 | no se publica |
| 5. Despliegue | Sube a Cloudflare solo lo que cambió, un Worker por sección bajo el mismo dominio | Cloudflare (Workers con archivos estáticos) | versión nueva en Cloudflare | Cloudflare sigue sirviendo la anterior |
| 6. Avisos | IndexNow con lo nuevo, cambiado y retirado (hasta 10.000 por petición); Indexing API para las fichas con `JobPosting` (200 al día); sitemaps con `lastmod` | mismo | registro de avisos en `seo/informes/` | se reintenta en la tanda siguiente |
| 7. Vigilancia | Mira la web servida al día siguiente: robots.txt, sitemaps, cabeceras, HTML idéntico al generado, robots de búsqueda e IA, certificado, Search Console, Bing y CrUX | ejecutor de GitHub (`seo.yml`, ya hecho) | incidencia de GitHub con la etiqueta `vigilancia-seo` | la abro yo y la arreglo o la apunto al módulo que corresponda |

### Cuándo corre

Dos publicaciones al día, con margen sobre lo que tardan hoy las cargas del motor. El de las 08:06 del 31/10 publicó a las 11:05, unas tres horas después.

- **12:23**, después del motor de la mañana (07:47) y con lo que ya hayan dejado los autonómicos (08:17);
- **19:23**, después del motor de la tarde (14:47) y de la extracción de bases (11:41).

La publicación lee siempre la última versión de cada rama, así que no depende de que una carga concreta haya terminado. El aviso «al terminar el motor» (`workflow_run`) no sirve: GitHub no lo dispara cuando la ejecución la lanzó el vigilante, que hoy lanza las diarias.

Las dos siguen la regla del proyecto: programación diaria («M H * * *») y `workflow_dispatch` con entradas por defecto, para que el vigilante las lance si GitHub no las dispara. Una ficha publicada en el BOE de la mañana sale ese mismo día.

### Reglas de la cadena

- **La web nunca pasa por el repositorio público ni por GitHub Pages.** Se genera en el disco del ejecutor y va directa a Cloudflare.
- **Vista previa protegida.** Antes de abrir el dominio, la web se ve en una dirección cerrada con Cloudflare Access. Una copia abierta en otra dirección sería contenido duplicado indexable.
- **Un fallo del control no publica nada de esa tanda.** El sitio sigue con la versión anterior. Para volver atrás se despliega la versión anterior, que está en Cloudflare y en el almacén.
- **La fecha (`lastmod`) solo cambia si cambia el dato.** Lo garantiza la huella del contenido principal, sin cabecera ni pie.
- **Límites del alojamiento** (ley, regla 25):
   - 100.000 archivos por versión en el plan de pago;
   - un Worker por sección desde el primer día;
   - con las 60.478 páginas de hoy cabe todo con margen.
- **Coste:**
   - Cloudflare cobra 5 dólares al mes como mínimo por cuenta en el plan de pago, y las peticiones a archivos estáticos son gratuitas e ilimitadas;
   - GitHub no cuesta nada mientras el repositorio sea público;
   - el almacén, céntimos.

### Lo hecho y lo que falta

| Pieza | Estado |
|---|---|
| Control de cada página y del sitio (`motor/seo/control.py`, `reglas.py`, `pagina.py`, `similitud.py`) | hecho y probado |
| Renderizado con Chromium (`renderizado.py`) | hecho y probado |
| Sitemaps con `lastmod` real (`sitemaps.py`) | hecho y probado |
| Vigilancia diaria (`vigilancia.py`, `seo.yml`) | hecha; se enciende con la variable `SEO_BASE` |
| Avisos a buscadores (`notificar.py`) | hecho; sin probar contra los servicios reales (faltan el dominio y las claves) |
| Revisión de dominios y competencia (`dominio.py`, `competencia.py`) | hecha |
| Inventario diario de páginas publicables | **falta**: lo hago en la semana 1 (`motor/seo/inventario.py`) |
| Reglas nuevas del control: convocante genérico, provincia por código, mismo proceso dos veces, notas de corte | **falta**: semana 1 |
| Tabla de direcciones estable de oposiciones | **falta**: semana 1 |
| Fábrica de páginas (`motor/web/`) | **falta**: semanas 1 a 4 |
| Flujo de publicación (`seo-publicar.yml`) | **falta**: semana 4 |

## Oleadas: qué entra, cuándo y con qué condición

Las cifras son las de hoy. Cada oleada se recalcula el día antes con el inventario diario, y lo que entre de más (procesos nuevos, fichas que llegan al mínimo) va con la oleada en curso.

### Las cinco oleadas

| Oleada | Qué entra | Páginas hoy | Condición para abrirla | Fecha propuesta |
|---|---|---|---|---|
| 0. Dominio | Portada, metodología, quiénes somos y autoría, correcciones, aviso legal, privacidad, datos abiertos y contacto; robots.txt, sitemaps y página 404 | unas 10 | dominio en Cloudflare con la configuración fija; Search Console y Bing verificados | en cuanto exista el dominio (semana del 9/11) |
| 1. Oposiciones vivas | Fichas con plazo abierto o abierto en los últimos doce meses (9.727; 11.155 con el arreglo del convocante); 52 provincias, 19 comunidades, 141 cuerpos con 50 procesos o más, 7 listados fijos; `JobPosting` e Indexing API; petición del carrusel de sitios de empleo | 9.946 (11.374 con el arreglo) | control en verde a escala completa; hallazgos 2, 3, 4 y 5 resueltos; bases extraídas de toda la oleada; visto bueno de Álvaro en la vista previa | a partir del 9/12/2026 |
| 2. Oposiciones completas | Resto de fichas desde 2022 (29.176; 33.012 con el arreglo); 564 cuerpos más con 10 a 49 procesos; 791 cuerpo × comunidad; 2.696 municipios | 33.227 (37.063 con el arreglo) | oleada 1 con el 70 % o más indexado a las seis semanas y ninguna alarma | a partir del 20/01/2027 |
| 3. Grados y notas de corte | 2.181 fichas de grado, 297 grados genéricos, 68 universidades, 732 notas de corte por universidad y 205 por comunidad | 3.483 | la condición de la oleada 1; datos mínimos de nota de corte en `reglas.py` | febrero de 2027 (indexadas antes de marzo: la demanda llega en junio) |
| 4. Másters oficiales | 2.961 fichas en orden de reputación: QS (893), grupo 1 y escuelas de negocio con precio (76), grupo 2 y públicas grandes (1.262), resto (730); listados por área y ciudad | 2.961 y sus listados | la de la oleada 3 | marzo de 2027 (antes de la preinscripción de primavera) |
| 5. Másters no oficiales y asignaturas | De las 8.933, las que pasen el filtro de reputación, el tope por grupo y la similitud; 1.928 páginas de «carreras con» | hasta 10.861 | decisión de Álvaro sobre el criterio; oleadas anteriores con su condición | abril-mayo de 2027 |

Las oleadas están aprobadas (anexo C). Las fechas de las oleadas 3 y 4 son las del calendario de la estrategia. Propongo adelantar la oleada 1 de enero a diciembre, por dos razones:

- el inventario de oposiciones es 2,3 veces el que la estrategia daba por bueno para la oleada 1 (16.977 fichas con los mínimos el 30/10; 38.903 hoy);
- un mes más de rastreo antes del arranque del año.

Si el dominio no está decidido la semana que viene, todo se corre las mismas semanas.

### Cómo se decide abrir la siguiente

El umbral del 70 % a las seis semanas es mío, no de Google: Google no publica una proporción «buena». Sale de los objetivos de la estrategia: más del 80 % a los tres meses y alarma por debajo del 60 %. Se revisará con los datos reales de la oleada 1.

| Señal | Fuente | Abre la siguiente | Para y revisa |
|---|---|---|---|
| Páginas indexadas sobre enviadas, por sitemap de la oleada | Search Console (páginas y sitemaps) | 70 % o más a las seis semanas | menos del 60 %, o una caída de 10 puntos en una semana |
| «Rastreada, sin indexar» y «Descubierta, sin indexar» | Search Console | baja semana a semana | sube dos semanas seguidas |
| Canónica elegida por Google distinta de la nuestra | inspección de URL, muestra diaria | ninguna | cualquiera: suele ser una página casi igual a otra |
| Acciones manuales y problemas de seguridad | Search Console | ninguno | cualquiera: se para todo |
| Impresiones de la oleada | Search Console (rendimiento) | crecen | caen más del 30 % de una semana a otra fuera de festivos |
| Velocidad real (LCP, INP y CLS, percentil 75) | CrUX | en verde | cualquier métrica en ámbar |
| Errores de `JobPosting` | Search Console (mejoras) | ninguno | cualquiera |

### Lo que no se hace en ninguna oleada

- Publicar con `noindex` fichas que no llegan al mínimo: aparecen como fila en sus listados.
- Cambiar una dirección publicada: si algo cambia, va una redirección 301 a la nueva, y la tabla de direcciones está para que no haga falta.
- Mover la fecha de una página sin que cambie su dato.
- Publicar dos veces el mismo proceso.
- Abrir una oleada para compensar que la anterior no se indexa.

## Las próximas cinco semanas, una a una

Es mi trabajo hasta la oleada 1. Cada semana termina con algo que se puede comprobar. El código va con sus pruebas y la batería entera en verde antes de subir a `main`, también con `MOTOR_ORIGINALES=s3`. Hoy pasan las 891 pruebas y 3 se saltan.

| Semana | Qué hago | Cómo se comprueba | Depende de |
|---|---|---|---|
| 1 (2 al 8/11) | Inventario diario (`motor/seo/inventario.py`), con el recuento de este documento reproducible; reglas nuevas del control (convocante genérico, provincia por código del INE, mismo proceso dos veces, datos mínimos de notas de corte); tabla de direcciones estable de oposiciones; esqueleto de `motor/web/` y la ficha de proceso | inventario en la rama `seo` cada día; pruebas de cada regla con casos reales (Alcaudete, León, BOPB y DOGC) | que Álvaro acepte la fábrica única; la regla de notas de corte, que Álvaro apruebe sus mínimos |
| 2 (9 al 15/11) | Listados de oposiciones (provincia, comunidad, cuerpo, plazo abierto), portada y páginas de la oleada 0 (metodología, correcciones, autoría, aviso legal); `JobPosting`; robots.txt, `_headers`, `_redirects` y 404; alta del dominio en Cloudflare con la configuración fija, Search Console y Bing | control en verde sobre 1.000 fichas reales; oleada 0 publicada y vigilancia encendida | dominio, cuenta de Cloudflare, Search Console y Bing (Álvaro) |
| 3 (16 al 22/11) | Plantillas de ficha de grado, nota de corte y máster; enlazado interno (proceso ↔ cuerpo ↔ municipio ↔ provincia; grado ↔ universidad ↔ nota de corte); sitemaps por sección y Worker | control en verde por plantilla; tres páginas por plantilla pintadas con Chromium | código de la maqueta «Noche en blanco» (conversación de diseño) |
| 4 (23 al 29/11) | Flujo `seo-publicar.yml` completo (fábrica → control → almacén → Cloudflare → avisos), contra la vista previa protegida; fábrica a escala completa; velocidad de laboratorio | tiempos y memoria medidos; tamaño de la web; prueba de volver atrás | clave de despliegue de Cloudflare y Cloudflare Access (Álvaro) |
| 5 (30/11 al 6/12) | Vista previa para Álvaro; correcciones; inventario de la oleada 1 con los datos del día; lista de comprobación final | visto bueno de Álvaro; hallazgos 1 a 5 resueltos o fuera de la oleada | arreglos de oposiciones (hallazgos 1, 2, 3 y 5) y bases de la oleada extraídas |

Si un arreglo de otro módulo no llega a tiempo, no se retrasa la oleada. Las fichas afectadas se quedan fuera y entran en la publicación del día en que estén bien:

- sin el arreglo del convocante, la oleada 1 sale con 9.946 páginas en vez de 11.374;
- las 1.781 del BOJA no salen hasta tener su ayuntamiento.

### Lo que pido a las otras conversaciones

Lo dejo apuntado en `claude/estado-seo.md`, que es por donde se coordinan.

| Conversación | Qué | Para cuándo |
|---|---|---|
| Oposiciones | Rellenar `convocante` en todos los ámbitos (hallazgo 1) | antes del 29/11 |
| Oposiciones | Convocante real en las 1.781 fichas del BOJA con «Ayuntamientos» (hallazgo 2) | antes del 29/11 |
| Oposiciones | Unir los duplicados que quedan, con los casos de este documento (hallazgo 3) | antes del 29/11 |
| Oposiciones | Taxonomía de cuerpos: nombre que se busca y variantes, empezando por los 141 grandes (hallazgo 5) | antes del 22/11 |
| Oposiciones | Extraer las bases de las 6.115 fichas de la oleada 1 que no las tienen, unos 5 dólares (hallazgo 7) | antes del 6/12, si Álvaro lo aprueba |
| Grados | Acordar la fábrica única y una ruta fija para las fichas (hoy, una carpeta con fecha: `fichas-grados/20261030/`) | semana 1 |
| Másters | Lista de no oficiales con reputación, grupo empresarial y comprobación de «universidad» contra el RUCT (hallazgo 9) | antes de marzo |
| Diseño | Código de la maqueta «Noche en blanco» con los tres ajustes SEO de la estrategia (secciones visibles, fuentes sin salto, hueco de patrocinio fijo) | semana 3 |
| Estado (infraestructura) | Nada que cambiar. Solo aviso de que el SEO escribe en el almacén bajo `seo/` con el rol de siempre, y de que no usará el servidor de España | — |

## Mi trabajo de cada día, cada semana y cada mes

Desde la oleada 0, el sitio se vigila solo y yo reviso lo que la vigilancia encuentra. Nada de lo que sigue depende de que alguien se acuerde.

| Cada | Qué | Con qué | Qué sale |
|---|---|---|---|
| Publicación (dos al día) | Control de todas las páginas: datos mínimos, fuente y fecha de cada dato, títulos, canónicas, enlaces, marcado, similitud, tamaño y velocidad de laboratorio | `motor.seo.control` en `seo-publicar.yml` | informe en la rama `seo`; lo que bloquea no se publica |
| Día | Vigilancia del sitio servido: una sola versión del dominio, robots.txt servido igual al generado, sitemaps, cabeceras, muestra de páginas (estado, canónica, `noindex`, HTML idéntico al generado), robots de búsqueda e IA, 304, certificado | `motor.seo.vigilancia` en `seo.yml` (06:23) | incidencia `vigilancia-seo` si algo falla |
| Día | Search Console (sitemaps, páginas, rendimiento, IA generativa, inspección de una muestra de direcciones), Bing (rendimiento, rendimiento en IA, rastreo) y CrUX | mismas, con los secretos | copia diaria en `seo/informes/` del almacén |
| Día | Inventario de páginas publicables y de lo que falta para cada una | `motor.seo.inventario` | informe en la rama `seo` |
| Semana | Informe por plantilla: indexadas y enviadas, impresiones, clics, CTR, posición, canónicas elegidas por Google, títulos reescritos, «rastreada, sin indexar» | Search Console y Bing | resumen para Álvaro con lo que cambia y qué hago |
| Semana | Revisión a mano de 20 fichas al azar: cada dato contra su original, lectura de la página como la vería quien busca | almacén S3 y página servida | correcciones (registro público) y fallos para el módulo que corresponda |
| Mes | Ley SEO contra la documentación oficial de Google, Bing, OpenAI, Anthropic y Cloudflare, y después de cada actualización de Google | `docs/ley-seo.md` | cambios en la ley y en el control |
| Mes | Competencia: los 21 dominios medidos el 30/10 | `motor.seo.competencia` | qué hacen distinto y si cambia algo nuestro |
| Oleada | Decisión de abrir la siguiente con las señales del capítulo 6 | Search Console | propuesta a Álvaro |

### Qué hago cuando algo falla

- **Si es de mi módulo** (control, fábrica, vigilancia, avisos), lo arreglo yo.
- **Si es un dato mal de otro módulo:**
   - el control lo deja fuera de la web;
   - lo apunto en `claude/estado-seo.md` para esa conversación, con ejemplos;
   - si ya estaba publicado, la corrección va al registro público.
- **Si es de infraestructura** (AWS, servidor, secretos, ajustes de GitHub), lo apunto en el buzón `claude/incidencias.md`, como pide la regla del proyecto. No lo arreglo yo ni se lo pido a Álvaro.
- **Si Google cambia sus normas o hay una actualización**, primero miro qué plantilla y qué familia de búsquedas se mueven. Nunca se cambia todo a la vez.

## Lo que necesito de Álvaro

Las cuentas, las claves y las decisiones son de Álvaro. Claude no crea cuentas ni maneja contraseñas. Las claves van solo como secretos de GitHub, nunca en el chat.

### Decisiones

Ya aprobado el 31/10/2026 a las 15:13, en la conversación de estado («sí a todo»): todo el anexo C de la estrategia, es decir:

- umbrales de las páginas de categoría;
- no generar fichas por debajo del mínimo;
- regla de direcciones;
- secciones visibles en el diseño;
- lanzamiento por oleadas.

Quedan solo las decisiones que piden una elección concreta:

| Decisión | Mi propuesta | Para cuándo | Qué bloquea |
|---|---|---|---|
| 1. Nombre y dominio | Revisar questudio.es (con historial en 2010 y 2024; el .com es de otra empresa) y dos o tres alternativas con `motor.seo.dominio`, más la marca en la OEPM y la EUIPO | antes del 9/11 | oleada 0, Search Console y Bing, y con ellas todo el calendario |
| 2. Quién hace las páginas | Una sola fábrica (`motor/web/`) a cargo de esta conversación. Los módulos dan los datos y esta conversación hace la web, con un solo enlazado, una sola tabla de direcciones y un solo control | esta semana | semana 1 |
| 3. Un punto de la regla de direcciones | Cuando turno y mes no distinguen dos procesos (cuatro de Conserje en León el mismo día), añadir el destino o la especialidad («conserje-colegios») | antes del 15/11 | tabla de direcciones |
| 4. Datos mínimos de la nota de corte | Nota de corte de al menos dos cursos de la fuente oficial, con plazas o con el documento del distrito | antes del 15/11 | oleada 3 |
| 5. Extraer las bases de la oleada 1 | Sí: 6.115 fichas, unos 5 dólares | antes del 22/11 | contenido de la oleada 1 |
| 6. Criterio de los másters no oficiales | Orden de reputación, tope de 100 fichas por grupo empresarial y proveedor, comprobación de «universidad» contra el RUCT, similitud | antes de marzo de 2027 | oleada 5 |
| 7. Adelantar la oleada 1 | Del calendario de la estrategia (enero de 2027) al 9/12/2026; las demás, como estaban | antes del 29/11 | publicación |

### Cuentas, claves y ajustes

| Qué | Detalle | Para cuándo |
|---|---|---|
| Cloudflare | Alta del dominio; plan de Workers de pago (5 dólares al mes como mínimo por cuenta); robots de búsqueda, de agentes y de entrenamiento en «Allow»; sin Bot Fight Mode, sin ofuscación de correos, sin Web Analytics automático, sin Rocket Loader | con el dominio |
| Secretos de despliegue | `CLOUDFLARE_API_TOKEN` (permiso de edición de Workers) y `CLOUDFLARE_ACCOUNT_ID` | semana 4 |
| Vista previa protegida | Cloudflare Access sobre la dirección de la vista previa, con el correo de Álvaro | semana 4 |
| Search Console y Bing | Propiedad de dominio en Search Console; Bing Webmaster Tools importando desde Search Console, el mismo día | con el dominio |
| Secretos de vigilancia y avisos | `GSC_CREDENCIALES` (cuenta de servicio con acceso a Search Console y a la Indexing API), `BING_WEBMASTER_KEY`, `INDEXNOW_CLAVE`, `CRUX_API_KEY`; variable `SEO_BASE` con la dirección del sitio | con el dominio |
| Opcional: demanda de búsqueda | Una cuenta de Google Ads para el planificador de palabras clave: volumen de búsquedas por cuerpo, municipio, grado y máster | cuando quiera; ver capítulo 10 |

## Riesgos y revisión crítica de este plan

### Riesgos

| Riesgo | Qué haría | Cómo se ve |
|---|---|---|
| Google tarda en confiar en un dominio nuevo y la oleada 1 se indexa poco | No abrir la oleada 2; revisar las plantillas con lo que diga Search Console (canónicas, «rastreada, sin indexar»), no con intuiciones | proporción de indexadas por sitemap |
| Un dato mal publicado en un tema sensible (un plazo, un convocante) | Control antes de publicar, plazo siempre «estimado» cuando lo es, registro público de correcciones, revisión semanal de 20 fichas contra su original | revisión semanal y avisos de usuarios |
| Los arreglos de oposiciones no llegan a tiempo | La oleada sale sin las fichas afectadas; entran el día que estén bien | inventario diario |
| GitHub no dispara las programaciones | El vigilante lanza las diarias; `seo-publicar.yml` sigue el formato que cubre | informe del vigilante |
| El repositorio pasa a privado | La fábrica y el control van al servidor de España: hay que medir si caben en 2 GB y que estén las librerías de Chromium | antes del paso a privado |
| Cloudflare cambia otra vez su política de robots de IA | La vigilancia diaria compara el robots.txt servido con el generado; plan B en la ley (Bunny) | incidencia de vigilancia |
| La web crece por encima de 100.000 archivos por Worker | Un Worker por sección desde el primer día | inventario diario |

### Revisión crítica: lo que se puede hacer mejor y lo que falta

Al cerrar el plan me he preguntado si da lo que queremos y qué se ha quedado fuera:

1. **No sé cuánto se busca cada cosa.** El orden de las oleadas y los umbrales salen de la oferta: procesos, plazas, reputación. No salen de la demanda.
   - Un cuerpo con muchos procesos puede tener pocas búsquedas, y al revés.
   - Arreglo: el planificador de palabras clave de Google Ads (decisión opcional del capítulo 9) antes de la oleada 2, o los datos de Search Console de la oleada 1, que serán los buenos.
2. **No he medido el tamaño de una página ni lo que tarda la fábrica.**
   - Las cifras de coste del almacén y de tiempo son estimaciones; se miden en las semanas 1 a 4.
   - Si la fábrica no cabe en una hora, se pasa a generar solo lo que cambió.
3. **El umbral de la oleada (70 % a las seis semanas) es mío.** Google no da una cifra. Se revisará con los datos de la oleada 1.
4. **No he revisado la calidad de las fichas una a una**, solo cantidades y muestras.
   - La revisión de 20 fichas por semana empieza con la vista previa, no con la oleada.
   - Las fichas de máster no oficial, sobre todo, necesitan lectura antes de publicarlas.
5. **Las cifras de listados de estudios son del 30/10.** El inventario diario las recalculará desde la semana 1.
6. **La autoridad (enlaces, menciones, informes propios) está en la estrategia, pero no en este plan de semanas.** Empieza después de la oleada 1, con el primer informe de plazas por provincia, cuando haya páginas a las que enlazar.
7. **El plan depende de que se decida el dominio esta semana.** Es el único punto que, si se retrasa, mueve todo el calendario.

## Anexo. Cómo se ha medido

| Qué | De dónde | Cuándo |
|---|---|---|
| Almacén S3 por carpeta | `peso-s3.json` de la rama `vigilancia` (flujo «Peso del almacén»: solo lista, no lee contenido) | 31/10/2026, 13:05 de Madrid |
| Procesos de oposición | `datos/oposiciones/procesos/2022.jsonl` a `2026.jsonl` de la rama `datos` (139.025 líneas; `indice.json`) | descargados a las 15:25 |
| Fichas de grado | `sondas:fichas-grados/20261030/` (`fichas_resumen.json`, `fichas.jsonl.gz`, `comparativa.jsonl`, `universidades.jsonl`) | generadas el 31/10 a las 07:20 |
| Másters | `sondas:masters-estado/conjunto/` (`resumen.json`, `masters_oficiales.jsonl.gz`, `programas_no_oficiales.jsonl.gz`) | generado el 31/10 a las 03:45 |
| Listados de estudios | `claude/inventario-paginas.md` del proyecto | 30/10, 13:10 |
| Grupo EDUCA EDTECH | páginas del propio grupo (educaedtech.com), que nombran a Euroinnova, INESEM, INEAF y Red Educa como suyas | consultadas el 31/10 |
| Precio de Cloudflare | documentación de precios de Workers: mínimo de 5 dólares al mes por cuenta; peticiones a archivos estáticos gratuitas e ilimitadas | consultada el 31/10 |

Criterios:

- **Ficha de proceso con los datos mínimos:**
   - `convocante.nombre` no vacío;
   - `total_plazas` mayor que 0;
   - plazo con `fin_estimado` o `dias`;
   - sin contar los convocantes genéricos.
- **Plazo abierto hoy**: `fin_estimado` igual o posterior al 31/10/2026 y apertura igual o anterior.
- **Oleada 1**: plazo abierto hoy, o apertura desde el 01/11/2025.
- **Cuerpo**: `puesto_clave` de las plazas de la ficha, contado una vez por ficha.
- **Municipio**: `convocante.codigo_ine`.
- **Provincia**: `convocante.provincia_codigo`.
- **Grupo de reputación de los másters**: `motor/estudios/reputacion.py`.

Los programas del recuento están fuera del repositorio. En la semana 1 pasan a `motor/seo/inventario.py` con sus pruebas, para que cualquiera pueda repetir estas cifras y para que se repitan solas cada día.

