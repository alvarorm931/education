# convenioslaborales.com por dentro: qué copiamos y qué no

Versión del 31/10/2026. Medido con `motor/seo/anatomia.py` (rama `seo`, `20261031T162447-anatomia/`). Versión para leer: `convenioslaborales_por_dentro.docx` y `convenioslaborales_anatomia_31-10-2026.xlsx`, entregadas a Álvaro.


## Resumen: lo que copiamos y lo que no

convenioslaborales.com es el modelo de referencia del proyecto. Lo hemos medido por dentro hoy, con el mismo motor que usaremos para vigilar nuestra web:

- todos sus sitemaps;
- 450 direcciones rastreadas desde la portada, a una petición por segundo y respetando su robots.txt;
- siete páginas cargadas con Chromium en un móvil lento simulado;
- su registro de dominio y sus capturas en archivos públicos.

**Lo que es.**

- **Nació hace 17 días.** El dominio se dio de alta el 14/10/2026 en IONOS, con los DNS en Cloudflare.
- **Tiene 14.326 direcciones en sus sitemaps, en 38 tipos de página.** Tres de cada cuatro (10.592) son calendarios laborales de un municipio y un año. Les siguen:
   - 2.068 tablas salariales;
   - 1.290 páginas de convenios;
   - 139 artículos del Estatuto de los Trabajadores;
   - 40 sueldos por oficio;
   - 18 calculadoras y escritos;
   - 59 dudas y guías.
- **La firma Gala Worklab.** El pie de página la presenta como una herramienta suya y lleva a un diagnóstico para empresas en galaworklab.com.
- **Las 1.000 visitas diarias no se pueden comprobar con datos públicos.**
   - No aparece en la lista Tranco de los sitios más visitados, que en una web de este tamaño y edad es lo normal.
   - Mide su tráfico con Google Analytics 4 y Cloudflare Web Analytics.
   - En los comentarios de su robots.txt dice que lee sus registros de visitas y que de los asistentes de IA «vienen visitas».

**Por qué funciona.** Publica, con fuente y fecha, datos oficiales recién salidos que se buscan mucho y que nadie tiene ordenados:

- los festivos de 2027 de cada municipio, a medida que cada comunidad los aprueba;
- las tablas salariales de cada convenio.

Cada dato lleva a una herramienta ya rellenada con él: del convenio y la categoría a la calculadora de sueldo neto, de atrasos o de despido. Es el mismo motor que el nuestro: datos de boletín, cola larga por lugar y frescura.

**Lo que copiamos** (detalle en el capítulo 9):

1. Arquitectura plana: todo a dos o tres clics de la portada, con páginas centrales por año, provincia y sector que enlazan a todas sus fichas.
2. Fichas que responden preguntas concretas en secciones fijas, con un bloque de «Qué ha cambiado» y la fecha de revisión visible y coherente con la de los datos estructurados.
3. Páginas que cruzan datos que nadie junta. Su página de sueldo por oficio enlaza de media 101 tablas y 86 convenios. Para nosotros:
   - sueldo por cuerpo;
   - plazas por provincia;
   - nota de corte de un grado en todas las universidades.
4. Del dato a la herramienta, sin dirección nueva: calculadoras ya rellenadas desde la ficha.
5. Fuente oficial enlazada en cada ficha, calendario descargable (.ics) y sitemaps por tipo y comunidad para leer la indexación por trozos.
6. Confianza en un tema sensible: «Orientamos, no asesoramos», ayuda gratuita, y una página de quiénes somos con tres preguntas (de dónde salen los datos, cómo y cada cuánto se revisan, qué no hacemos).

**Lo que no copiamos** (capítulo 10):

1. Fechas de modificación (`lastmod`) anteriores a que existiera la web: desde el 16/06/2025, en un dominio del 14/10/2026.
2. Ninguna respuesta 304: sin ETag ni Last-Modified, cada visita de Googlebot descarga la página entera.
3. Enlaces internos con parámetros: calculadoras con `?convenio=…&categoria=…&salario=…`.
4. Contenido escondido: dos tercios del texto de cada convenio van en desplegables cerrados (de 2.740 palabras se ven 986). Además, marcado que Google ya no muestra (FAQ, HowTo).
5. Desplazamientos al cargar: en laboratorio, CLS de 0,308 en la página de un convenio.
6. Una plantilla municipal muy repetida: el parecido medio (Jaccard de grupos de cinco palabras) entre dos calendarios municipales es 0,535, con un máximo de 0,863.

**Lo que cambia en lo nuestro** (capítulo 11):

- dos precisiones en la ley: el primer `lastmod` de una página es el de su publicación, y las herramientas se rellenan sin dirección nueva;
- un aviso nuevo del control a partir de un parecido de 0,8;
- el bloque «Qué ha cambiado» en todas las fichas;
- calendarios .ics de cada proceso;
- sitemaps por tipo y comunidad.

## Quién es, desde cuándo y cuánto tráfico tiene

### Edad: 17 días

| Señal | Resultado | Fuente |
|---|---|---|
| Alta del dominio | 14/10/2026 a las 07:45 (UTC); último cambio, el 15/10/2026 | RDAP del registro .com |
| Registrador y DNS | IONOS SE; servidores de nombres de Cloudflare | RDAP |
| Capturas anteriores | 8 días con capturas en la Wayback Machine, de abril de 2008 a febrero de 2009 (la primera, su robots.txt) | Wayback Machine (CDX) |
| Fechas de sus propias páginas | `lastmod` de los convenios y tablas entre el 13 y el 23/10/2026; dudas, calculadoras y portada, el 30/10/2026 | sus sitemaps |
| Lista Tranco (sitios más visitados del mundo) | no aparece | API de Tranco |
| Certificados públicos (crt.sh) y Common Crawl | las consultas no devolvieron datos útiles (crt.sh vacío; Common Crawl respondió 404, 502 o 504) | sin conclusión |

**Qué se deduce.**

- **Toda la web se montó en unas dos semanas.** El dominio es del 14/10. Las páginas de convenios y tablas llevan fechas del 13 al 23 de octubre, y la capa de dudas y calculadoras, del 30.
- **El dominio ya existió antes**, con alguna página entre 2008 y 2009, y se ha vuelto a registrar ahora.
   - Con tan pocas capturas, lo que pudiera heredar es poco.
   - Aun así, es justo lo que nuestra ley prohíbe buscar: Google trata como abuso usar un dominio caducado para aprovechar su reputación anterior.

### Quién está detrás

La propia web lo dice en cada página:

- «Revisado por Gala Worklab» y la fecha;
- un enlace en la cabecera, «¿Eres una empresa?», que lleva a un diagnóstico para empresas en galaworklab.com con el parámetro `origen=convenioslaborales`.

Fuera de su web no hay resultados de búsqueda sobre Gala Worklab. Es coherente con un proyecto que acaba de nacer.

### Tráfico: lo que se puede y lo que no se puede comprobar

No hay ninguna fuente pública que dé las visitas reales de una web pequeña y nueva. Lo que hay son señales:

- **No está en la lista Tranco.** Es la lista de popularidad que usan los investigadores, con un millón de dominios. Una web de 17 días y unas 1.000 visitas diarias no tiene por qué estar: la ausencia no desmiente la cifra.
- **Mide su tráfico con dos herramientas**: Google Analytics 4 y Cloudflare Web Analytics, las dos en las 410 páginas analizadas.
- **Su robots.txt cuenta lo que ve en sus registros:**
   - deja pasar a los robots de los asistentes de IA porque «de aquí vienen visitas (no tocar)»;
   - cierra a ocho rastreadores de herramientas SEO, con cifras: 13.000 peticiones inútiles en seis días el 21/10, unas 3.000 a la semana el 22/10 y 2.831 páginas en 7 días el 30/10.
- **Lo más probable es que el tráfico venga de los calendarios.**
   - Son el 74 % de las páginas.
   - Octubre y noviembre es cuando las comunidades y los ayuntamientos aprueban los festivos del año siguiente.
   - Las 3.220 páginas de 2027 se han ido publicando a medida que salía cada norma: Castilla y León (1.821 municipios), Galicia (316), Castilla-La Mancha (313), País Vasco (248), La Rioja (166)…
   - Es una deducción por la estructura, no un dato: sin su Search Console no se puede saber qué búsquedas le traen las visitas.

Si las 1.000 visitas diarias son ciertas, las ha conseguido sin enlaces comprados que se vean y sin historial real: con datos frescos, bien ordenados y en el momento de más demanda.

## Qué páginas tiene

### 14.326 direcciones en 38 tipos

| Tipo de página | Direcciones | Qué es |
|---|---|---|
| `/calendario-laboral/{año}/{provincia}/{municipio}/` | 10.592 | festivos de un municipio: 7.372 de 2026 y 3.220 de 2027 |
| `/tablas/{convenio}/{año}/` | 2.068 | tabla salarial de un convenio y un año (1.069 convenios; de 2014 a 2030) |
| `/convenios/{sector}/{ámbito}/` | 1.014 | ficha de un convenio por sector y ámbito, y páginas de sector y de provincia |
| `/convenios/{sector}/{ámbito}/{código}/` | 276 | ficha de un convenio identificado por su código del registro (REGCON) |
| `/estatuto/{artículo}/` | 139 | artículo del Estatuto de los Trabajadores |
| `/calendario-laboral/{año}/{provincia}/` | 104 | festivos de una provincia (52 por año) |
| `/sueldos/{oficio}/{año}/` | 40 | sueldo de un oficio en todos los convenios, por provincia |
| `/dudas/{tema}/{pregunta}/` | 47 | una pregunta concreta (despido, vacaciones, jornada, renuncia, finiquito, paro, reclamar) |
| Calculadoras, escritos, guías y sus índices | 28 | herramientas, plantillas de escritos y guías largas |
| Centrales y legales | 18 | portada, normativa, índices, quiénes somos, aviso legal, privacidad y cookies |
| **Total** | **14.326** | |

Las cifras de calendario y de convenio salen de sus sitemaps, que declaran 26 archivos:

- uno por tipo;
- el del calendario de 2027, partido por comunidad.

Ningún archivo usa `changefreq` ni `priority`, que Google ignora, y todas las direcciones llevan `lastmod`.

**Corrección a nuestra estrategia del 30/10.** Allí escribimos «unas 32.760 direcciones»:

- era una estimación a partir de 6 de los 26 archivos, y el de 2026 (7.425 direcciones) pesó demasiado;
- la cifra exacta de hoy es 14.326;
- también dijimos «unas 800 palabras» por calendario municipal: el método de entonces juntaba las celdas de las tablas en una sola palabra. Con el de hoy, la mediana es de 1.650 palabras (1.484 en el contenido principal).

### Cómo crece

- **Fichas con un dato propio que cambia cada año**: calendario por municipio y año, tabla por convenio y año. La dirección lleva el año: 2027 no sustituye a 2026, se suma.
- **El calendario del año siguiente aparece por comunidades**, a medida que se aprueban sus festivos:
   - el `lastmod` de cada municipio es la fecha de su norma (Castilla y León, julio de 2026; Castilla-La Mancha, 20 y 22 de octubre);
   - el sitemap de 2027 va por comunidad, así que en Search Console se puede ver qué comunidades se indexan.
- **Capa de preguntas y herramientas encima de los datos**: 47 dudas, 9 calculadoras y 9 escritos. Todas son del 30/10, la última semana.
- **Páginas que cruzan datos**: solo 40 de sueldo por oficio, pero cada una enlaza de media a 101 tablas y 86 convenios.

### Lo que no está en los sitemaps

En el rastreo aparecieron 78 direcciones enlazadas que no están en los sitemaps:

- calculadoras ya rellenadas con parámetros (`/calculadoras/neto/?convenio=metal-a-coruna&categoria=…`), todas con canónica a la calculadora sin parámetros;
- cuatro páginas para insertar calculadoras en otras webs (`/calculadoras/insertar/neto/`), con `noindex, follow` y canónica a la calculadora;
- archivos de calendario (`festivos-2027-asturias-gijon.ics`).

Está bien resuelto, pero los parámetros multiplican lo que Googlebot puede rastrear (capítulo 10).

## Cómo están enlazadas

### Todo a dos o tres clics

Profundidad mínima desde la portada en el rastreo (450 direcciones):

| Desde la portada | Qué se alcanza |
|---|---|
| 1 clic | índices de normativa, convenios, calendario del año, calculadoras, guías y escritos; las 9 calculadoras y los 9 escritos; páginas legales |
| 2 clics | todos los convenios (el índice `/convenios/` enlaza los 1.315 distintos); provincias del calendario y los 100 municipios que enlaza el índice del año; Estatuto; sueldos; dudas |
| 3 clics | el resto de municipios (desde su provincia), tablas salariales, sueldos por oficio y dudas concretas |

Las páginas centrales son grandes:

- el índice de convenios tiene 1.327 elementos de lista y pesa 354 KB de HTML;
- el del calendario de cada año, 238 enlaces (104 provincias y 100 municipios).

Google no fija un máximo de enlaces por página. Lo que importa es que cada ficha esté a pocos clics y enlazada desde una página que tenga sentido.

### Dónde están los enlaces

Media de enlaces internos por página, según la zona donde están:

| Tipo de página | Menú | Contenido | Pie | Adónde llevan los del contenido |
|---|---|---|---|---|
| Convenio por sector y ámbito | 47,1 | 31,0 | 5,0 | 11,8 calculadoras ya rellenadas, 3 escritos, 2,2 tablas, guías de despido, nómina y calendario |
| Convenio por código | 46,1 | 16,4 | 5,0 | 5,4 calculadoras, 3,3 tablas, 2,3 convenios del mismo sector |
| Tabla salarial | 28,3 | 2,3 | 5,0 | su convenio y la tabla de otro año |
| Sueldo por oficio | 24,0 | 203,1 | 5,0 | 101 tablas y 86 convenios |
| Calendario de provincia | 24,0 | 72,6 | 5,0 | 67,6 municipios |
| Calendario de municipio | 24,0 | 13,3 | 5,0 | 6,3 municipios vecinos, su provincia (2), el año, su .ics, un convenio y 2 calculadoras |
| Artículo del Estatuto | 26,0 | 1,3 | 5,0 | el artículo anterior o el siguiente |
| Calculadora | 24,0 | 5,6 | 4,0 | otras calculadoras, la nómina y escritos |
| Duda de despido | 24,0 | 8,5 | 5,0 | 5 dudas del mismo tema, 1,5 artículos del Estatuto, la guía de despido |

Lo que se ve:

1. **Cada ficha enlaza hacia arriba, a los lados y hacia la acción.**
   - El municipio enlaza su provincia, sus vecinos y su calendario descargable.
   - El convenio enlaza sus tablas, otros convenios de su sector y las calculadoras rellenadas con él.
   - Es la «ficha que cuelga de dos padres» de nuestra estrategia, más el paso siguiente.
2. **La página que cruza datos es la que más reparte.** El sueldo por oficio enlaza más de 200 fichas de otros tipos desde el contenido, no desde el menú.
3. **Huecos de enlazado.**
   - Las tablas salariales (2.068 páginas) apenas enlazan nada desde su contenido.
   - Los artículos del Estatuto no enlazan las dudas ni los convenios que los aplican.
   - Las fichas más numerosas después de los calendarios son callejones casi sin salida.
4. **Menú grande en cada página**: de 24 a 47 enlaces. No es malo en sí, pero repite en las 14.326 páginas los mismos enlaces a las mismas herramientas.

### Del dato a la herramienta

Lo más inteligente de su arquitectura es que el dato lleva a la acción.

- Desde la ficha de un convenio, cada categoría enlaza a la calculadora de neto, de atrasos o de «¿cobro lo que dice mi convenio?», ya rellenada con el convenio, la categoría y el sueldo de la tabla:
   - `/calculadoras/neto/?convenio=metal-a-coruna&categoria=grupo-7-peon-ordenanza-portero-y-vigilante`;
   - `/calculadoras/cobro-convenio/?…&salario=25521.62`.
- Las calculadoras tienen una sola canónica (la dirección sin parámetros), así que Google no las cuenta como páginas distintas.
- Los calendarios municipales ofrecen su archivo `.ics` para añadir los festivos al calendario del móvil.
- Las calculadoras se pueden insertar en otras webs («Pon esta calculadora en tu web»), con una página propia para eso que no se indexa.

Para nuestro portal, el equivalente es directo:

- del proceso, «calcula tu sueldo neto en esta plaza», «añade el plazo y el examen a tu calendario» y «avísame cuando salgan los admitidos»;
- del grado, «calcula tu nota de admisión con estas ponderaciones».

Lo que no copiamos es el parámetro en la dirección (capítulo 10).

## Cómo es cada plantilla

Medianas de las páginas analizadas de cada tipo (40 por tipo en los grandes). Palabras sin ejecutar JavaScript.

| Plantilla | Palabras | Del contenido principal | HTML | Tablas | Preguntas marcadas | Datos estructurados |
|---|---|---|---|---|---|---|
| Convenio por sector y ámbito | 3.502 | 3.340 | 134 KB | 3 | 4 | Legislation, BreadcrumbList, FAQPage |
| Convenio por código | 1.808 | 1.646 | 104 KB | 2 | 3 | Legislation, BreadcrumbList, FAQPage |
| Tabla salarial | 1.800 | 1.636 | 122 KB | 1 | 0 | Dataset, BreadcrumbList |
| Sueldo por oficio | 1.324 | 1.156 | 89 KB | 12 | 0 | Dataset, BreadcrumbList |
| Calendario de municipio | 1.650 | 1.484 | 88 KB | 1 | 3 | FAQPage, BreadcrumbList, WebPage |
| Calendario de provincia | 1.460 | 1.294 | 86 KB | 1 | 2 | FAQPage, BreadcrumbList, WebPage |
| Artículo del Estatuto | 674 | 508 | 53 KB | 0 | 0 | Legislation, BreadcrumbList |
| Calculadora | 961 | 795 | 65 KB | 1 | 3 | FAQPage, Service, Offer |
| Duda concreta | 340 a 483 | 162 a 317 | 49 a 52 KB | 0 | 4 | FAQPage, Legislation, BreadcrumbList |

### La ficha de convenio

Ejemplo: `/convenios/metal/estatal/`. Secciones (encabezados), en orden:

1. Título con el año y el nombre oficial completo.
2. Tablas salariales de 2026.
3. Otros convenios aquí.
4. Categorías explicadas: niveles o grupos uno a uno, contratos formativos.
5. Pluses, horas extra y subidas: pluses, horas extra, subidas pactadas, revisión salarial.
6. Permisos pagados.
7. Periodo de prueba y preaviso.
8. **Qué ha cambiado.**
9. Preguntas frecuentes, cuatro concretas: si está vigente, el sueldo más bajo, los días de vacaciones y la duración de la prueba.
10. «¿Te avisamos de cualquier novedad de este convenio?»
11. «Lo que suele venir después».

Datos de la página:

- tres tablas de 13, 5 y 16 filas;
- 324 cifras, 41 importes en euros y 23 fechas;
- «Última actualización: 16 de octubre de 2026» y «Revisado el 16 de octubre de 2026», iguales al `dateModified` de sus datos estructurados;
- un apartado de fuente con el enlace a su boletín: BOE o el boletín de su provincia o comunidad. En las 40 fichas analizadas hay un «Fuente:» visible.

Es la plantilla más rica de la web y la más parecida a la que queremos para un proceso o un máster:

- responde a las preguntas que se buscan con el nombre del convenio;
- dice qué ha cambiado;
- ofrece el aviso.

### La ficha de calendario municipal

Ejemplo: `/calendario-laboral/2027/sevilla/alcala-de-guadaira/`. Secciones, en orden:

1. Título con el municipio y el año.
2. El año 2027 de un vistazo.
3. Tu calendario laboral de empresa, con estas fiestas. Es el gancho para su servicio a empresas.
4. Las 2 fiestas de Alcalá de Guadaíra en 2027. Es el dato propio.
5. Alcalá de Guadaíra, año a año.
6. Lo que más se pregunta: tres preguntas.
7. Festivos de Alcalá de Guadaíra en 2027: tabla de 15 filas.
8. Lo que suele venir después.
9. Fuentes.

Datos de la página:

- 49 fechas en el contenido;
- «Actualizado el 23 de octubre de 2026»;
- enlaces al BOE en las 40 páginas analizadas, y al boletín de su comunidad cuando lo hay (BOJA, DOGC, BOCYL…).

El dato propio son dos días. El resto (festivos nacionales y de la comunidad, preguntas, «de un vistazo») se repite entre municipios. Por eso se parecen tanto (capítulo 6).

### Sueldo por oficio: la página que nadie tiene

Ejemplo: `/sueldos/administrativo/2026/`. Contenido:

- un título y un bloque por provincia o comunidad (A Coruña, Albacete, Alicante…), cada uno con su tabla del sueldo del oficio en cada convenio aplicable;
- de mediana, 12 tablas, 981 cifras y 888 importes en euros.

Es una página derivada: no copia una fuente, junta cientos. Es exactamente el tipo de página que da razones para estar por encima de las demás. En nuestro portal:

- el sueldo de un cuerpo en cada administración;
- las plazas de auxiliar administrativo en cada provincia;
- la nota de corte de Enfermería en cada universidad.

### Calculadoras, dudas y guías

- **Calculadoras.** Cada una explica lo que calcula:
   - la de neto lleva «A dónde va lo que no te llega al bolsillo», el modelo 145 y cómo pedir otra retención, y cinco preguntas;
   - termina con «Pon esta calculadora en tu web»;
   - de las 40 páginas de calculadora analizadas (contando sus variantes ya rellenadas), 18 enlazan a la sede de la Agencia Tributaria y 21 llevan enlaces externos con `nofollow`.
- **Dudas.** Una pregunta por página, con la respuesta arriba, «En detalle», enlaces al artículo del Estatuto que la regula y otras dudas del mismo tema. Son páginas cortas, de 162 a 317 palabras de contenido principal.
- **Guías.** Despido, jubilación y nacimiento y cuidado: de 1.214 a 1.891 palabras, con 1 a 4 tablas.

### Quiénes somos y confianza

`/quienes-somos/` responde a tres preguntas: «De dónde salen los datos», «Cómo y cada cuánto se revisan» y «Qué no hacemos».

En el pie de todas las páginas:

- «Orientamos, no asesoramos»: la web no sustituye a un profesional ni revisa casos;
- recursos gratuitos: sindicatos, turno de oficio del colegio de abogados y servicios de mediación de cada comunidad;
- «Revisado por Gala Worklab» con la fecha.

Para un tema sensible es una buena base. Le falta una persona con nombre y cualificación que revise el contenido legal (capítulo 10).

## Cuánto se parecen sus páginas

Medida con el mismo algoritmo que el control del proyecto (`motor/seo/similitud.py`):

- se compara el texto del contenido principal en grupos de cinco palabras seguidas;
- se calcula el índice de Jaccard entre pares de páginas del mismo tipo (0, nada en común; 1, iguales);
- se mide qué parte del texto es común a todas las páginas analizadas del tipo.

| Tipo | Páginas comparadas | Parecido medio | Parecido máximo | Común a todas |
|---|---|---|---|---|
| Calendario de municipio | 40 | 0,535 | 0,863 | 44,6 % |
| Calendario de provincia | 40 | 0,471 | 0,902 | 44,8 % |
| Duda de despido | 11 | 0,447 | 0,572 | 53,4 % |
| Convenio por sector y ámbito | 40 | 0,160 | 0,251 | 11,5 % |
| Convenio por código | 40 | 0,149 | 0,274 | 7,4 % |
| Tabla salarial | 40 | 0,124 | 0,708 | 5,6 % |
| Sueldo por oficio | 40 | 0,083 | 0,267 | 3,6 % |
| Artículo del Estatuto | 40 | 0,053 | 0,332 | 4,8 % |

**Lectura.**

- **Convenios, tablas, sueldos y Estatuto son páginas de verdad distintas.** Comparten menos del 12 % del texto y el parecido medio no pasa de 0,16: el dato propio domina sobre la plantilla.
- **Los calendarios están en el límite.**
   - Dos municipios se parecen de media 0,535, y el par más parecido llega a 0,863.
   - Dos provincias llegan a 0,902: pasaría nuestro umbral de bloqueo (0,9).
   - Casi la mitad del texto es común a todas.
   - Es lo esperable: el dato propio son dos fiestas, y lo demás es el calendario nacional y autonómico.
   - Google no da una cifra de parecido a partir de la cual deja de indexar, pero sí desaconseja las páginas muy parecidas que existen solo para posicionar por lugar. Aquí cada página tiene un dato distinto y real, así que encajan en lo legítimo. Aun así, el riesgo es que Google no indexe todas.
- **Las dudas cortas del mismo tema se parecen mucho entre sí** (0,447 de media, el 53,4 % común), porque comparten bloque de enlaces y cierre. Con 162 a 317 palabras de contenido principal, el marco pesa casi tanto como la respuesta.

**Para nosotros**:

- el umbral de bloqueo del control se queda en 0,9;
- se añade un aviso a partir de 0,8 para revisar la plantilla antes de que llegue al límite;
- la página de municipio de oposiciones existe solo con oferta real (umbral aprobado: tres procesos o uno abierto). Un municipio con un solo proceso cerrado se parecería a otro aún más que estos calendarios.

## Técnica y velocidad

### Servidor

| Comprobación | Resultado | Valoración |
|---|---|---|
| Una sola versión del dominio | `http://`, `http://www.` y `https://www.` llevan con 301 a `https://convenioslaborales.com/` en un salto | bien |
| Barra final | `/normativa` → 308 → `/normativa/` | bien (308 es permanente) |
| Mayúsculas | `/NORMATIVA/` → 404 | bien: no crea duplicados |
| Dirección que no existe | 404 con `cache-control: no-store` | bien: nada de 404 blandos |
| Canónica | autorreferente en las fichas; las calculadoras con parámetros apuntan a la dirección sin ellos | bien |
| Caché del HTML | `cache-control: public, max-age=0, must-revalidate`; `cf-cache-status: DYNAMIC` (Cloudflare no lo guarda en su caché) | mejorable |
| Respuesta 304 | no hay ETag ni Last-Modified: nunca puede responder 304 | mal (capítulo 10) |
| Compresión y protocolo | gzip; HTTP/3 anunciado | bien |
| robots.txt | todo permitido; asistentes de IA permitidos uno a uno; cerrado a 8 rastreadores de herramientas SEO; sitemap declarado | bien |
| llms.txt | sí (23 líneas) | sin efecto conocido en Google; barato |
| ads.txt | no existe (404) | sin anuncios activos |
| Idioma, `<main>`, una H1 | `lang="es"` en las 410 páginas; `<main>` en 406; una H1 en todas | bien |
| Título y descripción | títulos de 50 a 69 caracteres en el 98 %; descripciones de 120 a 159 en el 98 % | bien |
| Open Graph y Twitter | en 406 de 410 | bien |
| Imágenes | ninguna `<img>`; unos 23 iconos SVG dentro del HTML | rápido; sin presencia en Google Imágenes |
| Tecnología | sin marcas de un gestor conocido (ni WordPress, ni Next, ni Astro); recursos en `/assets/`; HTML generado de antemano | sitio estático, como el nuestro |

### Velocidad en laboratorio

Chromium en un móvil lento simulado: 150 ms de latencia, 1,6 Mbps y CPU cuatro veces más lenta. Es el mismo método que nuestro control. La experiencia real de los usuarios (CrUX) no se pudo leer, porque PageSpeed sin clave respondió 429.

| Página | TTFB | LCP | CLS | Peticiones | Peso |
|---|---|---|---|---|---|
| Portada | 292 ms | 1.464 ms | 0,043 | 17 | 276.583 bytes |
| Calendario de municipio | 164 ms | 1.460 ms | 0,103 | 19 | 284.247 bytes |
| Calendario de provincia | 194 ms | 1.448 ms | 0,088 | 19 | 283.546 bytes |
| Tabla salarial | 116 ms | 1.076 ms | 0,079 | 20 | 294.209 bytes |
| Convenio por sector y ámbito | 132 ms | 1.088 ms | 0,308 | 21 | 295.874 bytes |
| Convenio por código | 255 ms | 1.124 ms | 0,193 | 20 | 291.271 bytes |
| Artículo del Estatuto | 111 ms | 1.012 ms | 0,001 | 18 | 274.824 bytes |

**Lectura.**

- **Carga rapidísima.** LCP entre 1,0 y 1,5 segundos en un móvil lento, muy por debajo de los 2,5 de Google.
- **Peso de unos 280.000 bytes por página:**
   - unos 150.000 de JavaScript, incluida la analítica de Google;
   - 76.837 de cinco archivos de fuentes;
   - unos 30.000 de CSS;
   - entre 18.000 y 31.000 de HTML comprimido.
   - Sin terceros más allá de Google Analytics y Cloudflare Web Analytics.
- **Desplazamientos.**
   - En tres de las siete páginas el CLS de laboratorio pasa de 0,1: la ficha de convenio llega a 0,308.
   - Nuestro laboratorio suma todos los desplazamientos, y los usuarios reales pueden ver menos.
   - La causa probable, sin comprobar, son las cinco fuentes tipográficas o bloques que se pintan después.
- **El JavaScript no añade texto, pero en los convenios se ve muy poco del que hay.** Palabras visibles al cargar (innerText en Chromium) frente a palabras en el HTML:
   - calendario de municipio, 1.608 de 1.649;
   - ficha de convenio por sector, 986 de 2.740 (36 %), con 8 desplegables cerrados;
   - ficha de convenio por código, 563 de 1.776 (32 %), con 7 desplegables cerrados.
   - Dos tercios de lo que dice un convenio están dentro de bloques `<details>` cerrados. Google lee ese texto porque está en el HTML, pero quien entra no lo ve, y Microsoft advierte de que sus sistemas de IA pueden no tenerlo en cuenta.
- **El CSS va dentro de cada página** (unos 40.000 bytes sin comprimir en el calendario). Acelera la primera visita, pero se descarga otra vez en cada página.

## Cómo gana dinero y cómo cuida la confianza

### Dinero: todavía no hay anuncios

- **Anuncios.**
   - La lectura de la portada encontró en la cabecera el identificador de una cuenta de Google AdSense: es lo que pide Google para revisar una web antes de aprobarla.
   - Sin embargo, ninguna de las 410 páginas analizadas carga el código de anuncios y no existe `ads.txt`. Los anuncios no están activos, o están pendientes de aprobación.
- **Captación para un servicio propio a empresas.** Es lo que sí funciona hoy:
   - en la cabecera, «¿Eres una empresa?», con un enlace al diagnóstico de Gala Worklab que lleva la marca de origen;
   - en las fichas, «¿Eres la empresa? Mira cuánto cuesta»;
   - en los calendarios, «Tu calendario laboral de empresa, con estas fiestas».
   - La web informativa es la puerta de entrada al negocio de servicios.
- **Avisos.** «¿Te avisamos de cualquier novedad de este convenio?» en cada convenio: es una lista propia, sin pedir registro para ver nada.
- **Inserción de calculadoras en otras webs.** Da visibilidad y, si el código insertado lleva un enlace a la marca, enlaces.

La lección para nuestro modelo de monetización:

- la información se queda abierta y sin registro;
- el dinero viene de un servicio claramente separado y de los avisos.

Es lo que dice nuestra estrategia de monetización, y aquí se ve funcionar en una web de 17 días.

### Confianza en un tema sensible

Derechos laborales, despido y sueldo son temas de los que Google llama «Your Money or Your Life»: un error daña de verdad. Lo que hace bien:

- fuente oficial enlazada en cada ficha de convenio, tabla y calendario;
- fecha de revisión visible e igual a la de sus datos estructurados;
- «Qué ha cambiado» en los convenios;
- «Orientamos, no asesoramos» y adónde ir gratis: sindicatos, turno de oficio, mediación;
- página de quiénes somos con el origen de los datos, el ritmo de revisión y lo que no hacen.

Lo que le falta:

- **Una persona con nombre y cualificación** (abogado laboralista, graduado social) que firme la revisión del contenido legal. «Revisado por Gala Worklab» es una empresa sin trayectoria pública. Google pide que quede claro quién ha creado el contenido y por qué es de fiar, sobre todo en estos temas.
- **Consentimiento de cookies.**
   - Carga Google Analytics en todas las páginas.
   - No se ha visto un gestor de consentimiento de los conocidos, aunque hay un enlace propio para configurar las cookies.
   - No he comprobado si la analítica espera al consentimiento. En España, la AEPD lo exige para las cookies de analítica de terceros.

## Lo bueno: lo que nos quedamos

| Qué hace | Evidencia | Qué hacemos nosotros | Dónde queda |
|---|---|---|---|
| Publica el dato oficial en cuanto sale, en la página que se busca | calendarios de 2027 por comunidad a medida que se aprueban; `lastmod` de cada municipio con la fecha de su norma | ficha del proceso publicada el mismo día que el boletín; dos publicaciones diarias | plan de ejecución (ya) |
| Arquitectura plana con páginas centrales que enlazan todas sus fichas | todos los convenios a 2 clics; municipios a 2 o 3; la provincia enlaza sus 68 municipios de media | provincia, comunidad, cuerpo y municipio enlazan todas sus fichas; nada a más de 3 clics | fábrica de páginas, semana 2 |
| Ficha enlazada hacia arriba, a los lados y hacia la acción | municipio: su provincia, 6,3 vecinos, su .ics, un convenio y 2 calculadoras | proceso: su cuerpo, su municipio y provincia, otros procesos del mismo cuerpo cerca, calculadora de neto y calendario | plantillas, semanas 1 y 3 |
| Ficha que responde a preguntas concretas en secciones fijas | convenio: tablas, categorías, pluses, permisos, prueba y preaviso, cambios, cuatro preguntas, «lo que suele venir después» | proceso: plazo, requisitos, tasa, temario, ejercicios, historia, aprobados por plaza, «qué viene ahora» | plantillas |
| «Qué ha cambiado» en la ficha | sección propia en cada convenio | bloque de cambios en cada ficha, alimentado por los actos del proceso y los cambios de datos de grados y másters | plantillas; regla nueva (capítulo 11) |
| Fecha de revisión visible e igual a la de sus datos estructurados | «Última actualización», «Revisado el» y `dateModified`, iguales | ya es ley (regla 2) y lo comprueba el control | ley (ya) |
| Fuente oficial enlazada | BOE en los 40 calendarios analizados; boletín de cada convenio | ya es ley: cada dato con fuente, URL y fecha | ley (ya) |
| Páginas que cruzan datos que nadie junta | sueldo por oficio: 203 enlaces de contenido a 101 tablas y 86 convenios | sueldo por cuerpo; plazas por provincia; nota de corte de un grado en todas las universidades; precio de un máster en todas | estrategia (ya); prioridad en la oleada 2 |
| Del dato a la herramienta | 11,8 calculadoras ya rellenadas por convenio | calculadora de neto rellenada con el grupo y la comunidad del proceso; nota de admisión con las ponderaciones del grado | plantillas; sin dirección nueva (capítulo 10) |
| Calendario descargable | `.ics` por municipio | `.ics` por proceso (plazo, examen, listas) y para «Mi plan» | estrategia (ya); plantilla de proceso |
| Sitemaps por tipo y por comunidad | 26 archivos; 2027 por comunidad | sitemaps por tipo y comunidad, para ver en Search Console qué trozo no se indexa | `motor/seo/sitemaps.py` (cambio pequeño) |
| Confianza: «orientamos, no asesoramos», ayuda gratuita, quiénes somos con tres preguntas | en todas las páginas | metodología de la oleada 0 con esas tres preguntas; aviso de que el documento válido es el boletín | oleada 0 |
| Higiene técnica | 301 a un solo dominio, 308 a la barra final, 404 de verdad, canónicas propias, inserciones con `noindex, follow` | ya en la ley y en el control | ley (ya) |
| Rápida y ligera | LCP de 1,0 a 1,5 s en móvil lento; 0 imágenes; 280.000 bytes por página | objetivo igual o mejor: sin fuentes de más, CSS en un archivo con caché | ley (ya) |
| Captación sin tocar la información | servicio a empresas en un enlace aparte; avisos sin registro | monetización separada del dato; avisos por correo opcionales | estrategia de monetización (ya) |
| Calculadoras para insertar en otras webs | página propia con `noindex, follow` y canónica | sí, con un enlace de atribución visible y con la marca. Google considera spam los enlaces con palabras clave, ocultos o de baja calidad metidos en widgets que se reparten por otras webs | después de la oleada 1 |
| Robots de IA dentro y llms.txt | robots.txt explícito para ClaudeBot, GPTBot, OAI-SearchBot, ChatGPT-User, PerplexityBot y Google-Extended | ya es ley (todos permitidos). llms.txt: barato, pero sin efecto documentado en Google; no es prioridad | ley (ya) |
| Cerrar el paso a rastreadores de herramientas SEO | 8 robots cerrados con sus cifras de peticiones | opcional: no afecta a Google y esconde nuestros enlaces a la competencia. Lo decide Álvaro | decisión |

La lista confirma que la mayor parte de lo bueno ya estaba en nuestra ley o en la estrategia. Lo nuevo que nos llevamos es:

- el bloque «Qué ha cambiado»;
- las páginas que cruzan datos como prioridad;
- calculadoras rellenadas desde la ficha;
- sitemaps por comunidad;
- calculadoras para insertar.

## Lo malo: lo que no copiamos

| Qué hace | Evidencia | Por qué no | Qué hacemos nosotros |
|---|---|---|---|
| `lastmod` anterior a que existiera la web | dominio del 14/10/2026; `lastmod` desde el 16/06/2025 (1.065 páginas con el 12/12/2025) | Google usa el `lastmod` solo si es exacto de forma constante y comprobable; es la fecha del último cambio significativo de la página, no la del dato. Una fecha anterior a la página no es verificable y puede hacer que deje de fiarse del de todo el sitio | el primer `lastmod` de una página es el de su primera publicación; después, solo cambia cuando cambia el dato. La fecha del dato va junto al dato |
| Nunca responde 304 | sin ETag ni Last-Modified; `max-age=0` | la guía de Google del presupuesto de rastreo pide responder 304 a lo que no ha cambiado; un sitio de más de 10.000 páginas que cambian a diario entra en esa guía | ya es ley (regla 13); la vigilancia lo comprueba |
| Enlaces internos con parámetros | calculadoras con `?convenio=…&categoria=…&salario=…`; 78 direcciones fuera del sitemap en 450 rastreadas | aunque la canónica las junte, Googlebot puede rastrear cada combinación. Con unos 1.290 convenios y varias categorías, son miles de direcciones más (estimación). Google desaconseja dejar rastrear las combinaciones de filtros que no hacen falta en el buscador | la herramienta se rellena desde la propia ficha, con almohadilla (`#convenio=…`), que no es una dirección nueva. La regla 8 (enlaces sin almohadilla) es para navegar entre páginas, no para esto |
| Dos tercios del convenio en desplegables cerrados | de 2.740 palabras se ven 986; de 1.776, 563 | Microsoft advierte de que sus sistemas de IA pueden no ver el contenido oculto; quien entra no ve la respuesta | ya es ley (regla 7): secciones visibles; el control avisa si JavaScript oculta más del 20 % |
| Marcado que Google ya no muestra | FAQPage en convenios, calendarios, calculadoras y dudas; HowTo; Service y Offer en herramientas gratis | no da resultados enriquecidos; es peso y una ocasión de contradecir lo visible | ya en la estrategia y en el control (marcado sin efecto): solo `JobPosting`, migas, `WebSite`/`Organization` y `Dataset` |
| Desplazamientos al cargar | CLS de laboratorio de 0,308 y 0,193 en las fichas de convenio | Core Web Vitals pide 0,1 o menos en el percentil 75 | fuentes con `size-adjust`, huecos de tamaño fijo; el control mide el CLS por plantilla |
| Plantilla municipal muy repetida | parecido medio de 0,535 y máximo de 0,863 entre municipios; 0,902 entre dos provincias | riesgo de que Google no indexe todas; si el dato propio desaparece, serían páginas puerta | umbrales aprobados para el municipio; aviso nuevo del control desde 0,8 |
| Fecha de publicación que no es la de la página | `datePublished` = 23/10/2015 (la del Estatuto) en una página de octubre de 2026 | `datePublished` es de la página. La fecha de la norma tiene su sitio en los datos de la norma | la fecha de la norma o del boletín va en el dato; la de la página, en la página |
| Dominio con historia anterior | capturas de 2008 y 2009; alta nueva el 14/10/2026 | Google considera spam usar un dominio caducado para aprovechar su reputación | ya es ley; la revisión de questudio.es encontró historia (2010 y 2024) que hay que mirar antes de registrarlo |
| Autoría solo de empresa en temas sensibles | «Revisado por Gala Worklab» | Google pide que quede claro quién crea el contenido y con qué experiencia, sobre todo en temas «Your Money or Your Life» | metodología con personas y cualificación donde aporte; cada dato, con su fuente |
| Tablas y artículos sin enlaces de salida útiles | 2,3 y 1,3 enlaces de contenido por página | callejones sin salida para quien lee y para el rastreo | cada ficha enlaza a sus padres, a sus hermanas y a la acción (capítulo 9) |
| Enlace interno a una dirección que redirige | `/me-han-despedido/` → `/guias/me-han-despedido/` | un salto de más en cada visita; poco, pero se evita | la fábrica enlaza siempre la dirección final, y el control comprueba que cada enlace interno existe |

## Lo que cambia en nuestra ley, el control y el plan

Lo que sale de este análisis y no estaba ya decidido:

| Cambio | Dónde | Por qué |
|---|---|---|
| El primer `lastmod` de una página es el de su primera publicación; nunca anterior. La fecha del dato va junto al dato | ley, regla 2; control: comprobar que ninguna página nueva lleve un `lastmod` anterior a su primera publicación | el modelo lo hace al revés y Google pide exactitud |
| Las herramientas se rellenan desde la ficha con almohadilla (`#…`) o en la propia página, nunca con parámetros en enlaces internos | ley, regla 17, que ya dice que filtrar no crea direcciones (o lo hace con almohadilla); se añaden las herramientas rellenadas, y una aclaración en la regla 8 | evita miles de direcciones rastreables |
| Aviso del control a partir de un parecido de 0,8 entre páginas de la misma plantilla (el bloqueo sigue en 0,9) | `motor/seo/similitud.py` y `control.py` | la plantilla municipal del modelo vive entre 0,5 y 0,9 |
| Bloque «Qué ha cambiado» en todas las fichas, con fecha y fuente de cada cambio | plantillas de la fábrica; contrato del generador | da frescura visible y es nuestra historia del proceso |
| `datePublished` y `dateModified` son de la página; las fechas de normas y boletines, en el dato | ley, regla 22 (datos estructurados) | error del modelo |
| Sitemaps por tipo y comunidad | `motor/seo/sitemaps.py` | leer la indexación por trozos en Search Console |
| Calendarios `.ics` por proceso y para «Mi plan» | plantilla de proceso | el modelo lo ofrece por municipio |
| Corregir el método de contar palabras en la auditoría de competencia (juntaba las celdas de las tablas) | `motor/seo/competencia.py` | el 30/10 dio unas 800 palabras donde hay unas 1.650 |
| Corregir la cifra del modelo en la estrategia: 14.326 direcciones, no 32.760 | `docs/estrategia-seo.md` | era una estimación con una muestra sesgada |

Pendiente de Álvaro, que no tiene que ver con la ley de Google:

- **Cerrar robots.txt a los rastreadores de herramientas SEO** (Ahrefs, Semrush, Majestic y otros). No afecta a Google; reduce lo que la competencia ve de nosotros, y también lo que ven las herramientas que miden nuestra autoridad.
- **Calculadoras para insertar en otras webs**, con un enlace de atribución visible. Propongo hacerlo después de la oleada 1.

Lo hago en la semana 1 del plan, junto con las reglas nuevas del control que ya estaban previstas.

## Límites de este análisis

Al cerrarlo me he preguntado qué no está bien medido y qué falta:

1. **El tráfico no está comprobado.** Las 1.000 visitas diarias son el dato de partida, no una medida nuestra. Tampoco sé qué búsquedas le traen las visitas ni qué parte viene de los asistentes de IA. Solo su Search Console y su analítica lo dicen.
2. **No sé cuántas páginas tiene indexadas Google.** Una consulta `site:` no es fiable y no la usamos. El parecido de los calendarios hace pensar que no todas, pero es una hipótesis.
3. **La velocidad real no está medida.** PageSpeed sin clave respondió 429. El laboratorio dice que es rápida y que se desplaza en los convenios; los usuarios reales pueden ver otra cosa. Con `CRUX_API_KEY` se mediría en el siguiente análisis, si la web tiene tráfico suficiente para aparecer en CrUX.
4. **La muestra de plantillas es de 410 páginas.** Son 40 por tipo grande, elegidas por el rastreo desde la portada. Por eso los municipios analizados son sobre todo de las provincias que se enlazan antes, y los calendarios del año 2027 pesan más que los de 2026.
5. **No he leído el código de inserción de las calculadoras**, así que no sé si su enlace de atribución cumple la política de Google sobre widgets.
6. **No he comprobado si la analítica espera al consentimiento de cookies.**
7. **Lo que vale para ellos no vale entero para nosotros.**
   - Sus datos cambian una vez al año (festivos) o cada pocos años (convenios).
   - Los nuestros cambian cada día (procesos) y cada curso (notas y precios).
   - Su arquitectura sirve de modelo; su ritmo de publicación, no: el nuestro tiene que ser más rápido.

**Repetirlo.** El módulo que se ha usado (`motor/seo/anatomia.py`) queda en el repositorio. Se puede lanzar sobre cualquier dominio con el flujo «SEO, análisis bajo demanda»:

- sobre este mismo dentro de un mes, para ver cómo crece;
- sobre RedOpositor o notasdecorte.es, para tener la misma radiografía de los rivales directos.

## Anexo. Método y fuentes

**Cómo se midió.**

- **Módulo**: `motor/seo/anatomia.py` (commit `f7ecf16`), lanzado desde GitHub con el flujo «SEO, análisis bajo demanda» el 31/10/2026 a las 17:13 de Madrid.
- **Resultado**: rama `seo`, carpeta `20261031T162447-anatomia/`:
   - `anatomia.json`, el resumen;
   - `paginas.jsonl`, 450 páginas;
   - `enlaces.jsonl`, el grafo interno;
   - `sitemap.csv.gz`, las 14.326 direcciones con su tipo y `lastmod`.
- **Respeto a la web**:
   - 501 peticiones en unos once minutos, una por segundo;
   - robots.txt comprobado antes de cada una, con un agente que se identifica («PortalEstudiosOposiciones/0.1»);
   - ninguna dirección prohibida;
   - no se guardan textos de sus páginas, solo medidas, títulos y encabezados.
- **Tipos de página**: plantilla de dirección aprendida de los sitemaps. Una posición es variable si tiene ocho valores distintos o más; los años se marcan aparte.
- **Parecido**: grupos de cinco palabras del contenido principal e índice de Jaccard, el mismo cálculo que el control del proyecto.
- **Laboratorio**: Chromium con 150 ms de latencia, 1,6 Mbps y CPU cuatro veces más lenta, con pantalla de móvil. El CLS suma todos los desplazamientos.
- **Edad**: RDAP (rdap.org), Wayback Machine (CDX), crt.sh, Common Crawl y la API de Tranco. Las consultas a crt.sh y Common Crawl no dieron datos útiles.

**Documentación oficial en la que se apoya cada juicio** (ya citada en `docs/ley-seo.md`, consultada el 30/10/2026):

- Google, sitemaps y `lastmod`: https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap
- Google, presupuesto de rastreo y respuestas 304: https://developers.google.com/crawling/docs/crawl-budget
- Google, navegación por filtros: https://developers.google.com/crawling/docs/faceted-navigation
- Google, políticas de spam (enlaces en widgets, dominios caducados, páginas puerta): https://developers.google.com/search/docs/essentials/spam-policies
- Google, contenido útil y fiable («quién, cómo y por qué»): https://developers.google.com/search/docs/fundamentals/creating-helpful-content
- Google, Core Web Vitals: https://developers.google.com/search/docs/appearance/core-web-vitals
- Microsoft, contenido para respuestas con IA (contenido oculto en pestañas y desplegables): https://about.ads.microsoft.com/en/blog/post/october-2025/optimizing-your-content-for-inclusion-in-ai-search-answers

