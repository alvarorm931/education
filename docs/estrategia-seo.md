# Estrategia SEO del portal de estudios y oposiciones

Qué maximizar y qué evitar para salir los primeros en Google y en los buscadores con IA. Versión del 30 de octubre de 2026. Versión para leer: `Estrategia_SEO_portal.docx` (entregada a Álvaro). Responsable: conversación SEO (`docs/encargo-seo.md`).

## Resumen: las decisiones que más pesan

Este documento fija cómo va a ganar posiciones el portal y qué no va a hacer nunca, aunque parezca que da tráfico. Se apoya en tres cosas medidas: los datos que ya ha capturado el motor (38.536 procesos de oposiciones, 4.296 fichas de grado y el censo de másters), la documentación oficial de Google, Bing, OpenAI, Anthropic y Cloudflare consultada el 30/10/2026 y una auditoría técnica de 21 dominios que ocupan hoy nuestras búsquedas. Cada regla técnica está ya en la ley del proyecto (`docs/ley-seo.md`) y en el control automático (`motor/seo/`); aquí está la estrategia que se apoya en ellos.

Nadie puede prometer el primer puesto en todas las búsquedas: Google ordena por relevancia, utilidad y confianza, y la confianza de un dominio nuevo se gana con meses de buenos resultados. Lo que sí se puede asegurar es que nada técnico nos frene, que nada nos penalice y que cada página tenga una razón objetiva para estar por encima de las demás. Esa razón es el dato propio.

**Las doce decisiones**

1. **La unidad que posiciona es el proceso, no el anuncio.** Una sola página por proceso de oposición, que acumula todos sus actos (bases, plazo, admitidos, examen, notas, aprobados). Los competidores programáticos publican una página por anuncio del BOE, con el título literal de la resolución y un código en la dirección; esa fragmentación es su punto débil y nuestra ventaja.
2. **No se publica nada que no esté listo.** Hoy solo el 44,1 % de los procesos (16.977 de 38.536) tiene convocante, plazas y plazo; el 48,9 % de las fichas de grado (2.100 de 4.296) cumple los datos mínimos. Publicar ya llenaría el sitio de páginas sin indexar que Google sigue descargando. Las fichas que no llegan al mínimo no se generan como página: aparecen como fila en sus listados hasta que lo alcanzan.
3. **La historia del proceso es el diferencial y todavía no está.** Solo 1.608 procesos (4,2 %) tienen más de un acto. Sin los boletines provinciales y los tablones, nuestra ficha se parece demasiado a la de los demás. Completar los actos es la prioridad de contenido número uno de oposiciones.
4. **Páginas de categoría solo donde hay oferta real.** De 9.332 claves de puesto, 299 tienen diez procesos o más: esos son los cuerpos con página propia (unificando sinónimos). De 13.020 combinaciones de cuerpo y comunidad, 288 llegan a diez. De los 8.132 municipios, 3.058 han convocado algo desde 2022 y 1.307 tres veces o más. Lo demás no tiene página indexable: sería una página puerta.
5. **Direcciones que no chocan ni cambian.** 1.366 combinaciones de cuerpo, convocante y año se repiten (3.083 procesos). La dirección de la ficha añade el turno (y, si hace falta, el mes) antes de publicar la primera, porque cambiarla después cuesta una redirección por página y meses de señales perdidas.
6. **Frescura de agencia de noticias para lo que tiene plazo.** Ficha publicada en las horas siguientes al boletín, `JobPosting` mientras el plazo está abierto (RedOpositor ya lo usa: no basta para distinguirse, pero sin él se pierde), aviso inmediato a Google con la Indexing API (cupo de 200 al día, suficiente para los unos 30 procesos nuevos por día de publicación) y a Bing con IndexNow.
7. **Entrar en las piezas de empleo de Google.** En el Espacio Económico Europeo, Google muestra un carrusel de «sitios de empleo» y un filtro propio para las búsquedas de trabajo, sin necesidad de marcado; se entra pidiéndolo por su formulario. Es la puerta más corta para la sección de oposiciones.
8. **Escribir para que nos citen las IA.** Cada ficha empieza con una respuesta de pocas frases, cada una un hecho con su fecha y su fuente, y sigue con tablas en HTML. Nada importante escondido en pestañas, PDF o imágenes. Todos los robots de búsqueda y de IA, permitidos, con Bing tan cuidado como Google (alimenta a Copilot, a DuckDuckGo y, según OpenAI, a la búsqueda de ChatGPT).
9. **Confianza de tema sensible.** Las oposiciones y el acceso a la universidad entran en lo que Google llama temas «Your Money or Your Life» (gobierno, sociedad, futuro económico de las personas). Metodología pública, autoría real, fuente y fecha en cada dato, registro de correcciones y ninguna apariencia de web oficial.
10. **Autoridad con datos, no con enlaces comprados.** Informes propios, datos abiertos con atribución, notas semanales de plazas por provincia para medios locales, y la ficha verificada por el centro. Ni intercambio de enlaces con academias, ni artículos patrocinados con enlace que transmita autoridad, ni dominios caducados.
11. **La plantilla elegida («Noche en blanco») necesita tres ajustes SEO**: las ventanas deben ser secciones visibles de una sola página (no paneles ocultos), las fuentes tipográficas propias se cargan sin desplazar el texto y el hueco de patrocinio tiene tamaño fijo y va después de los datos.
12. **Lanzamiento por oleadas.** Primero las páginas con más datos propios (procesos con plazo abierto, cuerpos, provincias, notas de corte), después el resto a medida que la proporción de páginas indexadas sobre enviadas se mantenga alta. Ningún volcado de decenas de miles de páginas el primer día en un dominio nuevo.

**Lo que no haremos nunca** (detalle en el capítulo «Lo que hay que evitar»): páginas por pueblo sin procesos, páginas por variante de filtro sin oferta, textos generados en serie, fechas cambiadas sin cambiar el dato, ventanas al entrar, publicidad con cookies que obligue a un aviso de consentimiento, contenido de terceros publicado como propio, robots bloqueados y copias de la web en el repositorio público.

## El terreno de juego

### Dónde se busca

En España, Google se lleva el 93,81 % de las búsquedas en todos los dispositivos (StatCounter, septiembre de 2026; fuente no oficial, la de referencia del sector). Bing tiene el 3,49 %, pero en ordenador sube al 12,16 %, mientras que en el móvil Google llega al 98,85 %. La consecuencia práctica es doble: el diseño se piensa para el móvil y para Google, y Bing no se descuida porque pesa en ordenador (donde se preparan oposiciones y se comparan másters) y porque alimenta a otros buscadores y asistentes:

- Microsoft Copilot responde con la búsqueda de Bing («web grounding via the Bing search service», documentación de Microsoft).
- DuckDuckGo toma de Bing la mayoría de sus resultados clásicos.
- OpenAI dice que la búsqueda de ChatGPT usa «proveedores de búsqueda de terceros», y su centro de ayuda nombra a Bing como uno de ellos. Para salir en ChatGPT hay que dejar entrar a su robot OAI-SearchBot: según OpenAI, las webs que lo bloquean no se muestran en sus respuestas.
- Perplexity tiene índice propio y su robot PerplexityBot.
- Anthropic no ha publicado qué índice usa la búsqueda de Claude; su robot de búsqueda es Claude-SearchBot.

Google no exige nada especial para salir en AI Overviews o AI Mode: «There are no additional requirements», basta con estar indexado y poder mostrarse con fragmento. Desde 2026, Search Console tiene además un interruptor de «IA generativa en la Búsqueda» (viene en «Incluir»; con «Excluir» la web desaparece de esas respuestas) y un informe de impresiones en AI Overviews y AI Mode abierto a todas las webs desde el 31/08/2026. Bing, por su parte, enseña en Webmaster Tools cuándo nos cita Copilot (informe AI Performance, en vista previa desde febrero de 2026).

### Qué tipo de tema es

Las directrices de los evaluadores de calidad de Google (edición del 11/09/2025) llaman «YMYL Government, Civics & Society» a los temas que afectan a la confianza en las instituciones públicas y a cualquier información sobre gobierno o sociedad que influya en la vida de las personas. Una convocatoria de empleo público, el plazo para presentarse o la nota que da acceso a una carrera son exactamente eso: un error le cuesta a alguien una oportunidad. Los evaluadores no cambian posiciones por sí mismos, pero entrenan a los sistemas que sí lo hacen, y en estos temas Google pide más exactitud, más fuentes y más transparencia sobre quién publica. Para nosotros es una ventaja, porque es justo lo que aporta el modelo de datos del proyecto (fuente, URL y fecha en cada dato), siempre que se vea en la página.

### Qué hay hoy en nuestras búsquedas

Una muestra de búsquedas del 30/10/2026 (hecha con el buscador web de Claude, no con Google; sirve para ver quién publica qué, no para medir posiciones en Google) dibuja el terreno por familias:

| Familia de búsqueda | Quién aparece | Lo que ofrecen | Hueco que deja |
|---|---|---|---|
| Convocatorias concretas («auxiliar administrativo 2026», «policía local convocatorias») | El propio BOE en PDF, RedOpositor, PreparaOposiciones, sindicatos (CSIF), prensa local | Una página por anuncio o por noticia; guías largas de academia con venta de temario | Nadie junta en una página el proceso entero ni da el histórico; los PDF del BOE no son una ficha |
| Plazo abierto por zona («oposiciones ayuntamiento plazo abierto») | RedOpositor con páginas por provincia («plazas abiertas y plazos del BOP», actualizada el 25/10/2026), CSIF Madrid, foros de PreparaOposiciones | Tablas por provincia; entradas de foro por ayuntamiento | Ninguno cubre los 52 boletines provinciales; no hay aviso por municipio sin registro |
| Másters con precio («máster profesorado online precio») | yaq.es (184 másters de profesorado con precio), dondeestudiar.eu («Solicitar precio»), Mastermania, Emagister («Precio a consultar»), Uniscopio, academias | Listados con precio en una parte; formularios en la mayoría | Metodología, evaluación, asignaturas y precio real juntos y sin formulario |
| Notas de corte («nota de corte medicina 2026») | Prensa (Redacción Médica, Galiciapress), páginas oficiales (UCM, Comunidad de Madrid), Tesify (texto con «respuesta rápida» y medias aproximadas) | Un año, una comunidad o medias redondeadas | Cinco cursos por cupo y centro, con calculadora, en una página por grado y universidad |

Dos observaciones concretas, comprobadas en los propios resultados:

- **RedOpositor ya hace oposiciones programáticas** a partir del BOE, con páginas como `/oposiciones/convocatoria/resolucion-de-10-de-agosto-de-2026-del-ayuntamiento-de-sevilla-referen--4c52b4bb/`. La misma resolución del Ayuntamiento de Sevilla aparece en tres direcciones distintas (`…--4c52b4bb/`, `…--7195900e/`, `…--f268e5a4/`) con el mismo título literal del BOE. Es exactamente lo que Google describe como títulos de plantilla y lo que su guía de páginas puerta llama páginas «más cerca de una página de resultados que de una jerarquía navegable». Compite, pero con una estructura que se puede batir.
- **PreparaOposiciones** combina guías largas firmadas (17 minutos de lectura para Auxiliar Administrativo del Estado), entradas por convocatoria de ayuntamiento y hilos de foro que repiten esas mismas convocatorias. Gana por amplitud y por autoría visible, no por datos estructurados.

El capítulo «La competencia, medida» completa esto con la auditoría técnica de cada dominio: robots.txt, tamaño, HTML sin JavaScript y datos estructurados. La velocidad real queda pendiente de la clave de CrUX.

## Lo que dicen nuestros datos

Antes de decidir qué páginas existen, hay que saber cuántas pueden tener datos propios de verdad. Estas cifras salen de lo capturado por el motor hasta el 30/10/2026 (rama `datos`, `datos/oposiciones/procesos.jsonl`, y los documentos de grados y másters del proyecto).

### Oposiciones: 38.536 procesos desde enero de 2022

| Ámbito | Procesos | Peso |
|---|---|---|
| Local (ayuntamientos, diputaciones, mancomunidades) | 15.034 | 39,0 % |
| Autonómico | 13.392 | 34,8 % |
| Universidades | 7.953 | 20,6 % |
| Estatal | 1.547 | 4,0 % |
| Otros | 610 | 1,6 % |

Por año de publicación: 6.398 en 2022, 4.834 en 2023, 10.651 en 2024, 9.099 en 2025 y 7.554 en 2026 hasta el 30 de octubre. En 2025 hubo publicaciones 309 días, con una media de 29,4 procesos por día y un máximo de 86. Hoy hay 394 procesos con plazo abierto y 1.767 plazas. Desde 2022 se han convocado 137.004 plazas; la mediana es de 2 por proceso y el 48,1 % de los procesos ofrece una sola.

**Estacionalidad.** La oferta está repartida a lo largo del año, sin un mes que concentre más de la décima parte. En 2023-2025 los meses con más procesos nuevos fueron diciembre (2.460), mayo (2.372), octubre (2.348) y marzo (2.279); los más flojos, enero (1.438) y agosto (1.519). Para el SEO significa que la sección de oposiciones no tiene temporada baja: es la que puede traer tráfico desde el primer mes, como ya preveía la guía.

**Datos mínimos.** La ley exige a la ficha de proceso convocante, plazas, plazo y fuente. Hoy los cumplen 16.977 procesos (44,1 %): tienen convocante 38.528, plazas 17.564 y plazo 20.197. Lo que falta está identificado por el propio motor: 12.030 procesos con el texto pendiente de descargar, 11.472 pendientes de la extracción con IA, 8.942 sin plazas y 7.411 sin plazo. Es trabajo pendiente, no un límite de las fuentes.

**Historia.** Aquí está el hallazgo más importante para la estrategia: el proceso medio tiene 1,06 actos. Solo 1.608 procesos (4,2 %) tienen dos o más, y 353 tres o más. Por tipo: 24.508 convocatorias, 15.041 aperturas de plazo, 396 listas de admitidos, 322 correcciones, 249 listas de aprobados, 111 nombramientos de tribunal, 99 anulaciones y 3 fechas de examen. Las bases están localizadas en 14.791 procesos (38,4 %), pero los actos siguientes de los procesos locales casi nunca llegan al BOE: salen en el boletín provincial o en el tablón del ayuntamiento. Mientras no se capturen, nuestra ficha aporta poco más que la de un competidor que lee el BOE.

**Plazos.** De los 20.197 plazos, solo 43 tienen fecha de fin exacta; el resto se calcula con los festivos nacionales. Como los festivos autonómicos y locales solo pueden alargar el plazo, la fecha estimada nunca es posterior a la real. Eso la hace segura para el `JobPosting` (la oferta deja de mostrarse como abierta, como mucho, unos días antes de tiempo), pero la ficha tiene que decir siempre «fin estimado» hasta que el plazo se confirme.

### Cuerpos, lugares y combinaciones: cuántas páginas de categoría tienen sentido

| Página de categoría | Universo | Con oferta suficiente | Umbral propuesto |
|---|---|---|---|
| Cuerpo o puesto (`/oposiciones/{oposicion}/`) | 9.332 claves de puesto | 299 con 10 procesos o más (149 con 20, 53 con 50, 25 con 100) | 10 procesos en cinco años, tras unificar sinónimos |
| Cuerpo × comunidad (`/oposiciones/{oposicion}/{comunidad}/`) | 13.020 combinaciones | 288 con 10 o más (689 con 5) | 10 procesos en cinco años |
| Municipio (`/oposiciones/en/{municipio}/`) | 8.132 municipios | 3.058 con algún proceso; 1.307 con tres o más; 217 con plazo abierto hoy | 3 procesos en cinco años o uno con plazo abierto |
| Provincia y comunidad | 52 y 19 | todas con procesos | siempre |

Los diez puestos más convocados reúnen el 23,0 % de los puestos convocados; los cien primeros, el 43,1 %, y los quinientos primeros, el 58,8 %. El 41,2 % restante es cola larga: archivero de un pueblo, auxiliar de biblioteca, monitor de tiempo libre. Esa cola no merece una página de categoría, pero sí que su ficha esté bien enlazada desde el municipio y desde el cuerpo más cercano. Es la búsqueda de alguien de ese pueblo, donde la competencia suele ser menor.

**Sinónimos.** La taxonomía actual parte un mismo cuerpo en varias claves: `policia-local` (1.010 procesos), `agente-policia-local` (131) y `agente-policia` (9); `operario-servicios-multiples` (351) y `peon-servicios-multiples` (103). Para Google son varias páginas que compiten entre sí por la misma búsqueda. Antes de generar las páginas de cuerpo hay que unificarlas en la clave que busca la gente («policía local», no «agente de la policía local») y guardar las variantes como alias.

**Varios puestos en un proceso.** El 20,2 % de los procesos con plazas detalladas (3.335 de 16.531) convoca más de un puesto. Si se genera una ficha por puesto, las fichas hermanas comparten bases, fechas y convocante; el control de similitud decidirá si cada una tiene datos propios suficientes (plazas, grupo, titulación, sistema, temario) o si deben ir juntas en una ficha de la convocatoria con una sección por puesto.

**Choques de dirección.** La dirección prevista para la ficha es `/oposiciones/{oposicion}/{convocante}/{año}/`. Con los datos actuales, 1.366 combinaciones de cuerpo, convocante y año se repiten (3.083 procesos): el mismo ayuntamiento convoca dos veces el mismo puesto en un año, por turno libre y por promoción interna, o por estabilización. La dirección tiene que distinguirlos con palabras (`…/2024/promocion-interna/`, `…/2024/estabilizacion/`) y no con un código, y la regla tiene que estar fijada antes de publicar.

### Estudios

- **Grados**: 4.296 fichas activas (3.265 grados y 1.031 dobles grados). Con los datos mínimos que decidió Álvaro (asignaturas comprobadas y nota de corte o precio) son indexables 2.100, el 48,9 %. Las otras 2.196 no llegan por plan que no cuadra (850), plan no localizado (602) o falta de nota y de precio (1.148; una ficha puede tener varios motivos). Las páginas de grado genérico (`/grado/{grado}/`) son 245, las que reúnen el mismo grado en dos universidades o más; la comparativa tiene 372 genéricos con 4.149 filas. El buscador por asignatura reúne 36.890 asignaturas, 8.250 de ellas presentes en dos títulos o más.
- **Másters**: 4.347 títulos oficiales activos y unas 4.906 imparticiones, a los que se suman los títulos propios y los centros no universitarios (1.503 proveedores verificados en su web, unos 1.000 reales según la revisión a mano). La ley exige asignaturas y precio para indexar. El precio en euros aparece en el 36 % de las fichas de centros no universitarios y en el 31 % de las de universidades y centros oficiales: la mayoría de las fichas de máster saldrán sin indexar mientras no se consiga el precio (tarifas en PDF, decretos de precios públicos, peticiones a los centros).

### Lo que esto significa para el tamaño del sitio

Con los umbrales anteriores, el sitio de lanzamiento no es de 500.000 páginas, sino de unas pocas decenas de miles con datos propios: unas 17.000 fichas de proceso, unas 300 páginas de cuerpo, unas 300 de cuerpo por comunidad, unas 1.400 de municipio, 71 de provincia y comunidad, 2.100 fichas de grado, 245 grados genéricos, las universidades y las fichas de máster con precio. Es una buena noticia: un sitio más pequeño y denso se rastrea antes, se entiende mejor y no despierta las alarmas de contenido a escala. Crecerá a medida que cada ficha alcance sus datos mínimos, no al revés.

## La competencia, medida

El 30/10/2026 se pasó `motor/seo/competencia.py` desde GitHub por 21 dominios: los competidores que aparecen en nuestras búsquedas, dos portales oficiales y el modelo de referencia del proyecto (convenioslaborales.com). De cada uno se leyó el robots.txt, una muestra de sus sitemaps, la portada y tres páginas al azar de sus sitemaps, siempre dentro de lo que su robots.txt permite a nuestro agente y sin guardar textos. Resultado completo en la rama `seo` del repositorio (`20261030T123237-competencia/`).

La velocidad real no se pudo medir: la API pública de PageSpeed Insights respondió 429 (demasiadas peticiones) a todas las consultas sin clave. Se repetirá con la clave de CrUX en cuanto exista.

### Tamaño: cuántas direcciones declaran

Estimación a partir de una muestra de sus archivos de sitemap (media de direcciones por archivo × número de archivos del índice):

| Dominio | Direcciones en sitemaps (estimación) | Con `lastmod` en la muestra | Qué tipo de páginas |
|---|---|---|---|
| aprendemas.com | 356.496 | 0 de 68.557 | cursos por provincia, área y modalidad, en España y México |
| emagister.com | 182.264 | todas | cursos, temáticas y oposiciones por provincia |
| adams.es | 33.497 | 3.928 de 7.178 | academia; el sitemap incluye imágenes |
| convenioslaborales.com | 32.760 | todas | calendario laboral por municipio y año, convenios |
| opositatest.com | 27.117 | todas | calendarios y esquemas por oposición |
| redopositor.com | 21.222 | 16.146 de 17.685 | una página por convocatoria, tienda |
| yaq.es | 20.625 | 406 de 11.250 | grados y másters por universidad |
| mastermania.com | 16.402 | 0 de 16.402 | másters |
| notasdecorte.es | 7.956 | 5.782 de 7.956 | nota de corte por grado y ciudad |
| preparaoposiciones.com | 6.646 | 5.140 de 5.538 | guías, cursos, convocatorias, foro |
| oposiciones.es | 6.012 | 2.515 de 3.006 | convocatorias por comunidad, academias por ciudad |
| tesify.es | 5.806 | 3.595 de 5.806 | artículos |
| uniscopio.com, cef.es, universia.net | entre 3.484 y 4.418 | parcial | — |

Los grandes no lo son por datos, sino por combinaciones. Aprendemas genera páginas por modalidad, provincia y área (por ejemplo, `/es/masters/semi-presencial/lerida/informatica-y-tecnologias/`) y no da fecha de cambio a ninguna de las 68.557 direcciones contadas, así que Google no puede usar su sitemap para saber qué ha cambiado. Mastermania tampoco la da. Nuestro sitio de lanzamiento, de unas decenas de miles de páginas con datos propios y fechas reales, juega en otra liga: menos páginas, cada una con más razones para estar.

### Robots: nadie cierra la puerta a las IA

De los 20 dominios que respondieron, ninguno de los 19 que no son oficiales prohíbe en su robots.txt la entrada a los robots de búsqueda o de IA de la lista (OAI-SearchBot, Claude-SearchBot, PerplexityBot, GPTBot, ClaudeBot, Google-Extended…). Solo oposiciones.es cierra a Bytespider, y preparaoposiciones.com y mastermania.com piden un retardo entre peticiones (`Crawl-delay`), que Google ignora y que frena a los robots que lo respetan. Seis sirven por Cloudflare (RedOpositor, OpositaTest, Adams, yaq.es, notasdecorte.es y convenioslaborales.com), y ninguno lleva en su robots.txt las líneas que Cloudflare antepone cuando bloquea robots de IA.

La conclusión es importante: dejar entrar a los robots de IA no nos distingue, es lo mínimo. Lo que nos puede distinguir en ChatGPT, Copilot o Perplexity es que nuestra página sea la que tiene el dato exacto, con fecha y fuente, en frases que se pueden citar.

El caso aparte es el portal oficial: el robots.txt de administracion.gob.es (Punto de Acceso General, el buscador oficial de empleo público) prohíbe su dirección raíz a todos los robots de la lista, Googlebot incluido. No se comprobaron sus rutas concretas, así que puede que alguna sección sí esté permitida. Pero indica que la fuente oficial de control de cobertura no compite por esas búsquedas en Google.

### Lo que se ve sin JavaScript

Casi todos sirven el contenido en el HTML: las fichas medidas tienen entre unas 270 y 3.600 palabras legibles sin ejecutar nada. La excepción es universia.net, cuya portada y cuyas páginas de empleo del sitemap (con parámetros: `/es/empleo?jobLocation=Comunidad%20Valenciana&dateFrom=all&page=1`) no muestran ni una palabra sin JavaScript. Para los robots de IA, que no lo ejecutan, esas páginas están vacías, y además el sitemap ofrece direcciones con parámetros de filtro, justo lo que Google desaconseja.

### Datos estructurados: mucho marcado que ya no da nada

| Dominio | Marcado en las fichas | Qué le aporta hoy en Google |
|---|---|---|
| redopositor.com | `JobPosting` en las convocatorias, con `GovernmentOrganization`; `Course`, `Product` y `FAQPage` en la tienda | `JobPosting` sí (resultados de empleo); `FAQPage` y `Course` ya no |
| oposiciones.es | `Event` en las páginas de convocatorias por comunidad; `FAQPage` en la portada | `Event` exige eventos que el público pueda reservar: una convocatoria no lo es |
| yaq.es, mastermania.com, uniscopio.com, aprendemas.com, emagister.com | `Course`, `CourseInstance`, `CollegeOrUniversity`, `FAQPage` | la información de cursos se retiró en 2025 y la lista de cursos solo existe en inglés |
| convenioslaborales.com | `FAQPage` en cada calendario | dejó de mostrarse el 7/5/2026 |
| notasdecorte.es, emagister.com (oposiciones por provincia) | ninguno | — |

RedOpositor es el único que ya usa `JobPosting` en las convocatorias. Por tanto, el marcado de empleo no basta para distinguirnos: hay que ganarle en cobertura (todos los boletines, no solo el BOE), en exactitud (plazo con su cómputo) y en estructura (proceso entero frente a anuncio suelto).

### Fechas, formularios y direcciones

- **Fechas visibles.** Las fichas de notasdecorte.es, yaq.es, aprendemas.com, mastermania.com y uniscopio.com y las páginas de oposiciones por provincia de Emagister no muestran ninguna fecha (ni `<time>` ni «actualizado»). En notas de corte y en precios, que cambian cada curso, no saber de cuándo es el dato es un problema de confianza. Nuestra fuente y fecha en cada dato es una ventaja visible desde el primer día.
- **Formularios.** Piden el correo en sus fichas o guías RedOpositor, oposiciones.es, PreparaOposiciones, yaq.es, Mastermania y Uniscopio, y correo y teléfono ya en la portada Adams y oposiciones.es. No es una señal directa de posición, pero define la experiencia que compite con la nuestra: la información abierta sin registro es lo que el usuario no encuentra en otro sitio.
- **Códigos en las direcciones.** Emagister (`oposiciones-palmas-oposprovincia-35.htm`), yaq.es (`/15434-grado-derecho`), Mastermania (`…-1004571_q08.html`) y RedOpositor (`…--4c52b4bb/`) llevan códigos. Las direcciones con nombres no hacen ganar por sí solas, pero se entienden en el resultado, se recuerdan y no cambian cuando cambia la base de datos.
- **Páginas finas por lugar.** Las páginas de oposiciones por provincia de Emagister tienen unas 310 palabras sin datos estructurados ni fechas, y las de notasdecorte.es por grado y ciudad, entre 360 y 430. Son el tipo de página que nuestro umbral evita y que nuestra página de provincia puede superar con la lista completa de procesos de su boletín.

### El modelo de referencia: convenioslaborales.com

Hace exactamente lo que el proyecto quiere copiar «por detrás»: unas 32.760 direcciones, todas con `lastmod`, sin `changefreq` ni `priority`, servidas por Cloudflare, y una página por municipio y año para el calendario laboral (`/calendario-laboral/2026/araba/erriberagoitia/`, unas 800 palabras). Funciona porque cada municipio tiene de verdad un dato distinto: sus fiestas locales. La lección es directa: la página por municipio solo es legítima cuando el municipio aporta un dato propio. En calendario laboral lo aporta siempre; en oposiciones, solo cuando ha convocado (por eso el umbral).

### Lo que se concluye

1. **El hueco no está en lo técnico básico**: todos dejan entrar a los robots y sirven HTML. Está en la calidad del dato y en la estructura: fechas visibles, proceso entero, cobertura de todos los boletines, precio sin formulario, histórico.
2. **El rival directo en oposiciones es RedOpositor**: programático, con `JobPosting`, Astro y Cloudflare, y unas 21.000 direcciones. Su debilidad es la fragmentación (página por anuncio, títulos literales del BOE, códigos en la dirección) y la dependencia del BOE.
3. **En estudios, los grandes lo son por combinaciones sin fecha**. Se les gana con menos páginas, cada una con datos completos y fechados, y sin páginas por filtro.
4. **Todos gastan marcado en tipos que Google ha retirado.** Nosotros no: menos peso y nada que pueda contradecir lo visible.

## Arquitectura: qué páginas existen y cuáles no

La arquitectura decide más posiciones que cualquier otra cosa, porque fija qué búsqueda responde cada página, cuánta autoridad le llega y si Google la ve como útil o como relleno. La regla general es la de la guía: una ficha central con una sola dirección, que cuelga de dos padres, y alrededor solo las páginas que copian búsquedas reales con oferta suficiente.

### Principios

- **Una búsqueda, una página.** Si dos páginas responden a la misma búsqueda, compiten entre sí y ninguna gana. Antes de crear un tipo de página se escribe qué búsqueda responde («oposiciones de policía local en Andalucía») y se comprueba que ningún otro tipo la responde ya.
- **Una página existe si tiene datos propios.** No basta con que la combinación sea posible: tiene que haber oferta detrás. Google pone como ejemplo de páginas puerta las que van dirigidas «a regiones o ciudades concretas» para llevar al usuario a otra página, y las que están «más cerca de una página de resultados que de una jerarquía navegable». Una página de municipio sin procesos o de un máster por ciudad sin másters es eso.
- **Lo que no llega al mínimo no se genera.** La ley permite publicar con `noindex`, pero Google sigue descargando esas páginas y gastan rastreo (su guía del presupuesto de rastreo lo dice expresamente). Con la mitad de las fichas de grado y de oposiciones por debajo del mínimo, la diferencia es enorme. La ficha incompleta aparece como fila en el listado de su universidad o su municipio, con lo que se sabe y lo que falta, y pasa a ser página cuando lo alcanza.
- **La dirección no cambia nunca.** Se decide con los nombres que busca la gente, en minúsculas, con guiones, sin tildes y sin códigos. Cada dirección cambiada exige una redirección permanente mantenida al menos un año, y la autoridad tarda en pasar.
- **Los filtros no crean direcciones.** Ordenar o filtrar un listado (por plazas, por plazo, por grupo) se hace en la propia página, sin dirección nueva. Google recomienda no dejar rastrear las combinaciones de filtros que no hacen falta en el buscador y, si se usan, que una combinación sin resultados responda 404. Las únicas combinaciones con dirección propia son las de la tabla de abajo, con su umbral.

### Mapa de páginas de oposiciones

| Página | Dirección | Responde a | Existe si | Datos propios que la sostienen |
|---|---|---|---|---|
| Ficha de proceso | `/oposiciones/{oposicion}/{convocante}/{año}/` (+ turno o mes si choca) | «auxiliar administrativo ayuntamiento de Chiloeches 2026» | convocante, plazas y plazo | historia completa del proceso, plazo con su cómputo, bases, requisitos, sueldo neto calculado, aspirantes por plaza cuando se publique |
| Cuerpo | `/oposiciones/{oposicion}/` | «oposiciones policía local» | 10 procesos en cinco años | convocatorias abiertas, plazas por año, dónde se convoca más, requisitos por grupo, sueldo, histórico de procesos y de aprobados |
| Cuerpo por comunidad | `/oposiciones/{oposicion}/{comunidad}/` | «oposiciones policía local Andalucía» | 10 procesos en la comunidad | lo mismo filtrado y con normativa autonómica |
| Municipio | `/oposiciones/en/{municipio}/` | «oposiciones Villaejemplo» | 3 procesos en cinco años o uno abierto | todos sus procesos, abiertos y cerrados, con su historia, y los de su provincia |
| Provincia | `/oposiciones/en/{provincia}/` | «oposiciones Jaén plazo abierto» | siempre | procesos abiertos de su boletín provincial y del BOE, calendario de la semana |
| Plazo abierto | `/oposiciones/plazo-abierto/` | «oposiciones plazo abierto» | siempre | todo lo que se puede presentar hoy, con días que quedan |
| Por titulación | `/oposiciones/con-{titulo}/` | «oposiciones con ESO», «oposiciones con bachillerato» | siempre (son cinco o seis niveles) | procesos abiertos y cuerpos por titulación exigida |
| Sueldo | `/sueldo-funcionario/{grupo}/{comunidad}/` | «sueldo funcionario C2 Madrid» | siempre (grupo × comunidad) | neto calculado por nosotros con la norma vigente |

Las combinaciones de tres niveles (cuerpo × comunidad × año, cuerpo × provincia) no tienen dirección: son filtros dentro de la página del nivel superior.

### Mapa de páginas de estudios

| Página | Dirección | Existe si | Notas |
|---|---|---|---|
| Ficha de grado | `/universidad/{u}/grado/{grado}/` | asignaturas comprobadas y nota o precio | las 2.196 que no llegan, como fila en su universidad y su genérico |
| Grado genérico | `/grado/{grado}/` | el mismo grado en dos universidades o más (245) | la comparativa es su dato propio; los 458 de nombre único se enlazan desde su área |
| Universidad | `/universidad/{u}/` | siempre | grados, ramas, plazas, horquilla de precios, indicadores |
| Ficha de máster | `/universidad/{u}/master/{master}/` | asignaturas y precio | una por impartición cuando cambian modalidad o plazas |
| Máster por área | `/master/{area}/` | 5 programas o más (propuesta) | el comparador es el dato propio |
| Máster por área y ciudad u online | `/master/{area}/{ciudad}/`, `/master/{area}/online/` | 5 programas o más; si no, 404 | evita las páginas puerta por ciudad |
| Nota de corte | `/nota-de-corte/{grado}/{universidad}/` | dos cursos o más con nota | el histórico de cinco cursos por cupo es lo que nadie da junto |
| Calculadora | `/calculadora/{grado}/{comunidad}/` | ponderaciones verificadas | herramienta con el contenido explicativo en el HTML |
| Carreras con una asignatura | `/carreras-con/{asignatura}/` | la asignatura está en 5 títulos o más (propuesta) | con menos, la página repite la ficha |
| Cómo llegar a ser | `/como-ser/{profesion}/` | el camino tiene datos (estudios, oposiciones, sueldo) | escrita a mano o revisada, nunca en serie |

### Paginación y tamaño

- **2 MB por página.** Googlebot lee los primeros 2 MB de HTML sin comprimir y descarta el resto (documentación del 03/02/2026). Una página de cuerpo con los 1.625 procesos de auxiliar administrativo no cabe con todo su detalle. Los listados largos se parten por año o por estado (abiertos, últimos doce meses, anteriores), y el control para la publicación si una página pasa de 2 MB.
- **Paginación según Google**: cada página de la serie con su propia dirección y su canonical a sí misma (nunca a la primera página), enlaces `<a href>` de cada página a la siguiente y, si se puede, de todas a la primera. Google ya no usa `rel="next"` ni `rel="prev"`. Nada de páginas numeradas con almohadilla ni de «cargar más» sin enlaces reales detrás.
- **Ordenar y filtrar, sin dirección nueva.** Si alguna vez hace falta guardar el filtro en la dirección para compartirla, se hace con la almohadilla (`#plazo=abierto`), que Google no rastrea, y no con parámetros.

### Enlazado interno

El enlazado reparte la autoridad que llega desde fuera (casi toda, a la portada y a unas pocas páginas) y le dice a Google qué es importante. La guía de Google sobre funciones de IA lo pone como buena práctica: que el contenido se encuentre fácilmente con enlaces internos.

**Cada ficha recibe enlaces de:**

1. sus dos padres, el de categoría (el cuerpo, el grado genérico, el área) y el de lugar (el municipio, la universidad);
2. sus hermanas cercanas, con el mismo cuerpo en la provincia, el mismo convocante con otros puestos y el mismo grado en otras universidades de la comunidad;
3. su propia historia: el mismo cuerpo y convocante en años anteriores, encadenados («convocatoria anterior: 2024, 3 plazas»). Es el enlace que nadie más puede poner y el que convierte el archivo en autoridad;
4. las herramientas del momento, como «¿cumplo los requisitos?», la calculadora o «¿puedo acceder con mi grado?».

**Reglas de los enlaces:**

- **El texto del enlace dice adónde lleva** («Policía local en Jaén, 4 procesos abiertos»), no «ver más». Sin rellenar de palabras clave.
- **Las migas de pan con los dos caminos**, en HTML y con `BreadcrumbList`. Google solo las enseña en ordenador desde enero de 2025, pero siguen siendo navegación y enlaces.
- **La portada enlaza a lo vivo**: procesos con plazo abierto que vencen esta semana, cuerpos con más plazas abiertas, fechas clave del calendario. Cambia cada día y por eso Google la visita cada día.
- **Ni pies de página con cientos de enlaces ni nubes de etiquetas.** Las 52 provincias en el pie sí; los 300 cuerpos, no.
- **Nunca `nofollow` en enlaces internos**: si una página no merece enlace, no debería existir.
- **Ninguna ficha huérfana.** El control ya para la publicación si una página indexable no recibe ningún enlace de otra página indexable.

### Títulos, descripciones y direcciones

Google trata como malo un título largo «que solo cambia en un dato» y permite descripciones generadas desde la base de datos, siempre que cada una sea distinta. La plantilla de título tiene que variar en varios datos a la vez, y en el orden en que se busca:

- Ficha de proceso: «Auxiliar administrativo en Chiloeches (Guadalajara) 2026: 4 plazas, plazo hasta el 5 de noviembre».
- Cuerpo: «Oposiciones de policía local: 23 convocatorias abiertas y 1.010 procesos desde 2022».
- Municipio: «Oposiciones en Villaejemplo: 2 procesos abiertos y 14 convocatorias desde 2022».
- Grado: «Enfermería en la Universidad Ejemplo: nota de corte 11,80 en 2025-26, 120 plazas y plan de estudios».
- Máster: «Máster de Profesorado en la Universidad Ejemplo (online): 6.900 euros, 60 créditos y asignaturas».

La ficha de Chiloeches es un proceso real de nuestros datos; el resto de nombres y cifras son de ejemplo.

La descripción completa lo que el título no dice (requisitos, sistema, fuente y fecha) y nunca repite el título. El control ya para la publicación si un título o una descripción se repiten entre páginas indexables o tienen huecos de plantilla, y avisa de los títulos que son pura plantilla.

## Qué lleva cada plantilla para ganar su búsqueda

Una página gana si responde mejor que las demás a lo que busca quien llega. Cada plantilla tiene que responder a la pregunta en los primeros segundos y después dar lo que nadie más da junto. El orden es siempre el mismo: respuesta, cifras clave, detalle, historia, relacionados y fuentes.

### El bloque de respuesta

Lo primero de cada ficha, en el HTML y antes de cualquier otra cosa, es un bloque de tres a cinco frases cortas. Cada frase es un hecho completo con su fecha, que se entiende aunque se lea suelto:

> El Ayuntamiento de Chiloeches (Guadalajara) convoca 4 plazas de auxiliar administrativo (grupo C2) por concurso-oposición, turno libre. El plazo de solicitudes es de 20 días hábiles desde el 7 de octubre de 2026 y termina, según nuestro cálculo, el 5 de noviembre de 2026. Las bases están en el Boletín Oficial de la Provincia de Guadalajara número 184, de 26 de septiembre de 2025, rectificadas en el número 203. Fuente: BOE-A-2026-19166 y BOE-A-2026-20880.

Es lo que Google extrae para el fragmento y para AI Overviews, y lo que Microsoft recomienda para que Copilot cite una página: respuestas concisas que tengan sentido sacadas de contexto, hechos concretos y medibles en lugar de afirmaciones vagas, y encabezados que digan dónde empieza y acaba cada idea. No hace falta marcado especial: hace falta que la frase sea verdadera, completa y esté en el HTML.

### Ficha de proceso de oposición

1. **Respuesta en 30 segundos** (bloque de arriba) y sellos de estado: plazo abierto (con los días que quedan), cerrado, en curso o resuelto.
2. **Cifras clave**: plazas, grupo, sistema, turno, tasa de examen, fin de plazo (exacto o estimado) y sueldo neto calculado.
3. **«¿Cumplo los requisitos?»**: titulación, edad, nacionalidad y permisos, con la herramienta que contesta sí o no. El texto de los requisitos está en el HTML; la herramienta solo ayuda.
4. **Historia del proceso**: una línea por acto con fecha, boletín y enlace al original (bases, plazo, correcciones, admitidos con su recuento, tribunal, examen, notas, aprobados). Es lo que diferencia la página de la del BOE y de la de los competidores.
5. **Procesos anteriores** del mismo cuerpo y convocante, encadenados, con plazas, aspirantes por plaza y nota de corte cuando existan.
6. **Relacionados**: el mismo cuerpo en la provincia, otros puestos del mismo convocante y el cuerpo en la comunidad.
7. **Fuentes y metodología**: cada dato con su boletín, número y fecha; cómo se calcula el plazo; «esta web no es oficial: el único documento válido es el publicado en el boletín».

Mientras el plazo está abierto, la ficha lleva `JobPosting` con título, descripción, convocante, lugar, fecha de publicación y `validThrough` (el fin estimado, que nunca es posterior al real). Al cerrarse el plazo, el marcado se quita en la siguiente publicación. Google advierte que no hacerlo a tiempo puede traer una acción manual. La página se queda, porque su historia sigue teniendo valor.

### Página de cuerpo

Compite con las guías de academia («Oposiciones auxiliar administrativo 2026: guía completa»). Las academias ganan por amplitud y por autoría; nosotros, por datos vivos y completos:

- qué es el cuerpo, grupo, titulación y funciones (texto propio, breve y revisado);
- convocatorias con plazo abierto ahora, con los días que quedan;
- plazas convocadas por año y por comunidad desde 2022, que salen del propio motor y no las tiene nadie;
- dónde se convoca más (municipios y comunidades), sueldo neto por comunidad, exámenes y temarios oficiales enlazados;
- aspirantes por plaza y notas de corte de los procesos que las publican;
- preguntas frecuentes respondidas en el texto, sin marcado `FAQPage`: Google dejó de mostrarlo el 7/5/2026.

### Municipio y provincia

La página de municipio solo existe con oferta (tres procesos en cinco años o uno abierto). Lleva la lista completa de procesos, abiertos primero, con su historia, el calendario de los próximos plazos y los procesos abiertos de la provincia. Tiene que diferenciarse de verdad de la del pueblo de al lado. Si dos municipios solo se distinguen por el nombre, el control de similitud las detecta y una de ellas no se indexa.

### Ficha de grado

Su dato propio es lo que la guía llamó «asignaturas de cada carrera hechas legibles»: el plan por curso y tipo, la nota de corte de dos cursos (cinco cuando esté el histórico), las plazas por centro, el precio real de primera matrícula con las bonificaciones de su comunidad, la inserción laboral y el rendimiento. El bloque de respuesta da la nota de corte, las plazas y el precio con su curso. La comparación con el mismo grado en otras universidades enlaza al genérico, que es la página con más posibilidades de ganar búsquedas amplias («estudiar enfermería en Madrid»).

### Ficha de máster

La búsqueda típica es «máster X precio» o «máster X online». Gana quien da el precio real y la metodología sin formulario, que es exactamente la propuesta del proyecto. Cuando el centro no publica el precio, la ficha lo dice como hecho («la universidad no publica el precio en la página del máster; su formulario pide correo y teléfono»), pero la ley no permite indexarla sin precio. Esto convierte la búsqueda del precio (tarifas en PDF, decretos y peticiones a los centros) en una tarea de SEO de primer orden: cada precio conseguido es una página más que puede posicionar.

### Notas de corte y calculadora

Es la familia con más estacionalidad: la demanda se concentra entre la selectividad de junio y las adjudicaciones de julio. La página por grado y universidad lleva el histórico por cupo y centro, la nota de la última adjudicación con su fecha y el tipo de lista (primera asignación o final, que no son lo mismo: en Cataluña coinciden con la final de QEDU en un 10 % de los casos). Tiene que estar publicada e indexada antes de marzo de 2027 para posicionar en junio. La calculadora es la herramienta con más enlaces potenciales del portal, y su explicación (fórmula del RD 534/2024 y ponderaciones de cada comunidad) va en el HTML.

### Datos estructurados que sí y que no

| Tipo | Dónde | Por qué |
|---|---|---|
| `JobPosting` | ficha de proceso con plazo abierto y una sola convocatoria | resultados de empleo de Google; se quita al cerrar el plazo |
| `BreadcrumbList` | todas las páginas con migas | navegación (Google solo la enseña en ordenador) |
| `WebSite` y `Organization` | portada | nombre del sitio en los resultados y entidad de la marca |
| `Dataset` | solo en `/datos/` | Dataset Search; Google ya no lo usa en la búsqueda normal |
| `FAQPage`, `HowTo`, `Course`, sueldo estimado | en ninguna | Google los ha retirado; la lista de cursos solo existe en inglés |

Todo marcado tiene que coincidir con lo que se ve en la página. El control lo comprueba y, si no coincide, lo quita.

## Frescura y velocidad de indexación

En oposiciones, quien publica antes y mejor una convocatoria gana su búsqueda durante el plazo, que suele ser de 20 días hábiles (11.855 de los 20.197 plazos medidos) o de 20 naturales (3.609). Una ficha que tarda una semana en indexarse pierde un tercio de su vida útil.

### El circuito diario

1. El motor lee el BOE a las 07:47 y a las 14:47 (hora de Madrid en invierno) y los boletines autonómicos y provinciales a lo largo de la mañana.
2. Generación de las fichas nuevas o cambiadas, control y publicación en la hora siguiente.
3. Avisos:
   - **Indexing API de Google** para cada ficha con `JobPosting`, al publicarla y al cerrarse el plazo. El cupo por defecto es de 200 avisos al día. En 2025 se publicaron de media 29,4 procesos por día con publicación (86 como máximo), y no todos tienen el plazo abierto al publicarse, así que el cupo alcanza con margen. Si un día no llega, primero van las de plazo más corto.
   - **IndexNow** para todo lo nuevo, cambiado o retirado (Bing, Yandex, Seznam, Naver, Yep y Amazon; Google no participa).
   - Para el resto, Google lee los sitemaps con su `lastmod` real.
4. Comprobación en Search Console (inspección de URL de una muestra diaria, 2.000 al día por propiedad) del tiempo que tarda cada ficha en aparecer indexada.

### Fechas que dicen la verdad

Google pregunta en su guía de contenido útil si se cambia la fecha de las páginas «para que parezcan frescas» sin cambiar el contenido; Bing dice que el `lastmod` es una señal clave si refleja el cambio real. Las dos cosas están ya en el control: la fecha visible de «actualizado» y el `lastmod` solo cambian cuando cambian los datos, el contenido principal, los datos estructurados o los enlaces. Eso hace que el `lastmod` sea creíble para los buscadores, que lo usan para decidir qué volver a rastrear.

### Las piezas de empleo de Google

Dos oportunidades propias de la sección de oposiciones:

- **Resultados de empleo con `JobPosting`.** La documentación de Google incluye España entre los países con la experiencia de búsqueda de empleo. No dice en qué idiomas ni menciona expresamente el empleo público, y no lo excluye. Se prueba con las primeras fichas y se mide en Search Console, que tiene filtros de apariencia para las ofertas de empleo en el informe de rendimiento.
- **Carrusel y filtro de «sitios de empleo» en el Espacio Económico Europeo.** Google muestra a los usuarios del EEE que hacen búsquedas de empleo un carrusel con los agregadores de ofertas y un filtro que deja solo sus resultados. No hace falta marcado; las empresas que sirven a usuarios del EEE expresan su interés en un formulario de Google (página actualizada el 09/10/2026). Una web que reúne todas las convocatorias públicas de España es un agregador de ofertas. Hay que pedirlo en cuanto la sección esté publicada.

## Buscadores con IA

### Cómo se entra

No hay atajos. Google lo dice sin rodeos: la optimización para la búsqueda con IA «sigue siendo SEO», no hacen falta archivos especiales (Google ignora `llms.txt`), y «una gran cantidad de páginas no hace un sitio de más calidad». Para cada asistente, la puerta es su índice:

| Asistente | De dónde saca la web | Qué hay que hacer |
|---|---|---|
| Google AI Overviews y AI Mode | índice de Google | estar indexado y con fragmento; dejar «Incluir» en el control de IA de Search Console; nunca `nosnippet` ni `data-nosnippet` sobre datos |
| ChatGPT | robot OAI-SearchBot y buscadores de terceros (Bing, según OpenAI) | permitir OAI-SearchBot; Bing Webmaster Tools al día |
| Microsoft Copilot | índice de Bing | lo mismo que para Bing; informe AI Performance |
| Perplexity | índice propio, robot PerplexityBot | permitirlo |
| Claude | índice no publicado; robot Claude-SearchBot | permitirlo |
| Gemini (app) | Google; Google-Extended decide si puede usar la página para responder | permitir Google-Extended |

### Qué contenido citan

Microsoft es la única empresa que ha publicado recomendaciones concretas (blog del equipo de Bing, 08/10/2025), y coinciden con lo que ya pide la ley:

- títulos, descripciones y encabezados alineados entre sí y en lenguaje natural;
- respuestas cortas a preguntas directas, listas y tablas de comparación en HTML;
- hechos concretos y medibles, con su contexto, en lugar de adjetivos;
- **no esconder las respuestas en pestañas o menús desplegables**, porque los sistemas de IA pueden no mostrarlos; no dejar lo importante solo en PDF o en imágenes.

El tercer punto afecta directamente al diseño elegido. La plantilla «Noche en blanco» organiza la ficha en ventanas (Resumen, Plan, Precio, Entrar…). El documento de diseño dice que sin JavaScript se ve la ficha entera, y eso es correcto para Google. Pero si con JavaScript las ventanas ocultan el resto, un sistema que ejecuta la página verá solo la primera. La solución es mantener todas las secciones visibles en una sola página y que la barra inferior funcione como índice que lleva a cada sección. Se conserva la experiencia de app y no se esconde nada.

### Cómo se mide

- Search Console: informe de rendimiento en AI Overviews y AI Mode (solo impresiones, por página, país, fecha y dispositivo).
- Bing Webmaster Tools: AI Performance, que dice cuándo nos cita Copilot, con intenciones, temas y cuota de citas.
- Analítica sin cookies: visitas que llegan desde chatgpt.com, perplexity.ai, copilot.microsoft.com y gemini.google.com, separadas del resto.

## Confianza: quién está detrás y por qué fiarse

En temas YMYL, la confianza se gana con lo que se ve en la página. Google pide en su guía de contenido útil saber quién ha hecho el contenido, cómo y por qué, y recomienda firmarlo; desaconseja los perfiles de autor inventados y pide decir dónde se usa automatización cuando el lector lo esperaría.

- **Metodología** (`/metodologia/`, enlazada desde todas las páginas): quién hace la web (Álvaro, con nombre real), de dónde sale cada tipo de dato, qué hace la automatización, qué se revisa a mano, cada cuánto se actualiza y qué no tenemos.
- **Registro de correcciones** (`/correcciones/`): cada error corregido con fecha, qué decía y qué dice. En temas YMYL es una señal de seriedad que casi nadie da.
- **Fuente y fecha en cada dato**, visibles y enlazadas al original (ya es regla del control).
- **No aparentar carácter oficial**, como exige además la licencia del BOE: ni colores ni escudos institucionales, y en cada ficha la frase «el único documento válido es el publicado en el boletín oficial».
- **Página «Cómo nos financiamos»** con el pacto con el usuario de la estrategia de monetización: separa con claridad lo que es información de lo que es patrocinado.
- **Contacto real** y aviso legal con el titular (autónomo o sociedad, en cuanto exista).

## Autoridad y marca

Google sigue usando los enlaces de otras webs para descubrir páginas y como una de sus señales, y para un dominio nuevo son la forma más clara de que otros respondan por él. La regla es ganarlos con algo que merezca la cita, y nunca pagarlos ni intercambiarlos: las políticas de spam de Google consideran spam de enlaces los artículos patrocinados con enlaces que transmiten autoridad, los enlaces con texto optimizado en notas de prensa distribuidas, los enlaces de pie de página repartidos por muchas webs y los enlaces con palabras clave dentro de «widgets».

### Lo que genera enlaces de forma natural

1. **Notas semanales por provincia** («Esta semana: 23 plazas con plazo abierto en la provincia de Jaén»). Son datos que la prensa local busca y no tiene. Si citan la fuente, enlazan.
2. **Informes anuales con nuestros datos** (ya previstos en la guía): plazas convocadas por cuerpo y comunidad, notas de corte de cinco cursos, precio real de los másters, qué centros publican sus datos y cuáles no. Son material para medios nacionales y para quienes investigan.
3. **Datos abiertos en `/datos/`** con licencia que exige atribución con enlace. Es la vía por la que universidades, periodistas de datos y otras webs nos citan.
4. **Ficha verificada por el centro**: el centro que revisa y completa su ficha tiene motivos para enlazarla desde su web.
5. **La calculadora de nota y «¿cumplo los requisitos?»**: herramientas que se recomiendan en foros, en clase y en orientación escolar.
6. **Canales de Telegram por provincia y por cuerpo**, y calendario suscrito por proceso. No son enlaces, pero crean búsquedas de marca (gente que busca el nombre del portal) y visitas que no dependen de Google.

### Lo que no se hace

- Comprar enlaces, intercambiarlos con academias o escribir artículos invitados con enlace optimizado.
- Repartir un «widget» con enlaces de palabras clave. Si algún día se ofrece un widget (por ejemplo, el de procesos abiertos de un municipio para su web municipal), lleva el nombre de la marca como texto del enlace y `nofollow`.
- Comprar un dominio caducado por su historial, o redirigir otros dominios al nuestro para heredar enlaces.

### Marca y dominio

- **Nombre de marca, no de palabras clave** (decidido). Corto, sin guiones ni cifras, que no aparente carácter oficial (nada de «boe», «oficial», «gob», «ministerio» o «sepe»).
- **questudio.es** está en revisión con `motor/seo/dominio.py`, que mira su historial en la Wayback Machine y en Common Crawl, y si el nombre aparenta carácter oficial (resultado en el anexo). Antes de registrarlo conviene comprobar también que no hay una marca registrada igual o muy parecida (OEPM y EUIPO) y registrar a la vez el .com para que nadie lo use.
- **Una sola versión** (https y sin www), el marcado `WebSite` con el nombre en la portada para que Google muestre el nombre del sitio, y un icono en PNG o ICO (Google no admite SVG).
- **El mismo nombre en todas partes** (redes, Telegram, notas de prensa), con `Organization` y `sameAs` en la portada.

## Técnica y rendimiento al servicio de la posición

La parte técnica es la base de la ley y está ya en el control automático: contenido en el HTML, canónica, sitemaps, robots, 2 MB por página, Core Web Vitals en verde. Aquí van las decisiones que dependen del diseño elegido y del alojamiento.

### Ajustes a la plantilla «Noche en blanco»

| Elemento del diseño | Riesgo SEO | Ajuste |
|---|---|---|
| Ventanas (Resumen, Plan, Precio, Entrar, Más) | si ocultan contenido con JavaScript, los sistemas de IA pueden no verlo (aviso de Microsoft) y el usuario que llega desde un fragmento no encuentra la respuesta | todas las secciones visibles en una sola página; la barra inferior lleva a cada sección con enlaces a sus anclas |
| Barra superior y barra inferior fijas | si suman mucha altura, tapan contenido y se parecen a una ventana intrusiva | entre las dos, menos de una cuarta parte de la pantalla (el control con Chromium ya lo mide) |
| Tarjetas de cifras que se deslizan | desplazamiento del diseño (CLS) si se cargan después del texto | altura reservada en el CSS; datos en el HTML, no pedidos con JavaScript |
| Bricolage Grotesque y Figtree | LCP y CLS si las fuentes llegan tarde o cambian el ancho del texto | servirlas desde nuestro dominio en woff2, solo los caracteres latinos, precargar las dos que se ven al entrar y ajustar la fuente de reserva para que mida lo mismo (`size-adjust`) |
| Precio grande en la cabecera | es el elemento más grande y el que mide el LCP | texto en el HTML, nunca una imagen |
| Hueco de patrocinio | CLS si aparece después | tamaño fijo reservado desde el primer día, después de los datos, ocupado por autopromoción cuando no hay patrocinio |

La velocidad se comprueba por plantilla en laboratorio (móvil lento, LCP ≤ 2,5 s y CLS ≤ 0,1) antes de publicar, y después con los datos reales de Chrome (CrUX) en cuanto haya tráfico suficiente para que Google los publique.

### Alojamiento y estructura técnica

- **Cloudflare (Workers con archivos estáticos)** admite 100.000 archivos por versión en el plan de pago. El sitio de lanzamiento cabe, pero el completo no. Desde el primer día las secciones se publican en Workers separados bajo el mismo dominio (`/oposiciones/`, `/universidad/` y el resto), para no tener que cambiar nada cuando crezca.
- **Configuración de robots de IA en Cloudflare**: los tres ajustes («Search», «Agent», «Training») en «Allow». Al dar de alta el dominio, Cloudflare propone a las webs con anuncios un ajuste que bloquea a los agentes de usuario (ChatGPT-User, Claude-User) en las páginas con anuncios y antepone su propio robots.txt. No hay que aceptarlo. La vigilancia diaria compara el robots.txt servido con el nuestro.
- **Lo que Cloudflare mete en el HTML**: la ofuscación de correos (activada por defecto al darse de alta), la analítica automática y Rocket Loader cambian la página que ve el robot. Se desactivan y la vigilancia diaria avisa si reaparecen.
- **Páginas que desaparecen**: un proceso no desaparece nunca (su historia vale). Una ficha que deja de existir (un máster que se extingue) responde 404 o 410, o se redirige con 301 a su sucesora real, nunca a la portada. Las direcciones que no existen responden 404 de verdad (nada de respuestas 200 que Google cuenta como «soft 404»).
- **Respuestas 304** a las peticiones condicionales, para que los robots no vuelvan a descargar lo que no ha cambiado. Es una de las recomendaciones de la guía de Google sobre el presupuesto de rastreo, que se aplica a sitios de más de 10.000 páginas que cambian a diario, como será el nuestro.
- **Web de pruebas**, siempre detrás de contraseña y con `noindex` en la cabecera.
- **La web generada nunca se sube al repositorio** ni a GitHub Pages: es público, y Google podría indexar una copia en otro dominio.

## Monetización sin perder posiciones

La propuesta de monetización (pendiente de aprobación) es compatible con el SEO si se cumplen estas condiciones. Lo que penaliza no es ganar dinero, sino que el dinero empeore la página.

| Línea de ingreso | Riesgo SEO | Condición |
|---|---|---|
| Sin publicidad programática con cookies (propuesta) | ninguno; al contrario, ahorra el aviso de consentimiento, que cuenta como ventana al entrar, y el peso de los scripts | mantenerlo así |
| Patrocinio de centros | contenido pagado mezclado con el orden o los datos | hueco fijo después de los datos, rotulado «Patrocinado», enlaces con `rel="sponsored"`, nunca dentro de listados ni comparadores |
| Botón de contacto voluntario | formulario que aparece solo | se abre solo al pulsar; nunca al entrar ni al hacer scroll |
| Radar de convocatorias (B2B) | ninguno, es otro producto | la información de la web sigue abierta; el Radar vende comodidad, no exclusiva |
| Plataforma de exámenes y tests | miles de páginas de preguntas generadas | indexar los bancos por cuerpo y tema, no una página por pregunta; cada pregunta con su artículo de ley y revisada antes de publicarse |
| Mercado de cursos de academias | política de reputación del sitio: Google pone como ejemplo una web educativa que aloja contenido de terceros para aprovechar su autoridad | páginas hechas por nosotros con datos, enlaces de afiliado con `rel="sponsored"`, y ningún texto escrito por la academia publicado como página indexable |
| Afiliación | páginas de afiliado sin valor propio («thin affiliation») | solo dentro de fichas con datos propios; Google pone como buen ejemplo el que añade precio, comparación y navegación |

## Lo que hay que evitar

Cada fila es una práctica que alguien del sector usa o que parece una buena idea, por qué hunde la web y qué hacemos en su lugar.

| Práctica | Por qué hunde la web | En su lugar | Fuente |
|---|---|---|---|
| Una página por anuncio del BOE (corrección, ampliación de plazo, lista de admitidos) | fragmenta el proceso en varias páginas casi iguales con el título literal de la resolución; para Google son páginas de plantilla que compiten entre sí | una ficha por proceso que acumula sus actos | Google: títulos; políticas de spam (páginas puerta) |
| Una página por municipio, aunque no haya convocado nada | páginas puerta dirigidas a ciudades concretas; 5.074 de los 8.132 municipios no han convocado nada desde 2022 | página solo con tres procesos o uno abierto; el resto, en la de su provincia | Google: políticas de spam |
| Una página por cada combinación de filtros (cuerpo × provincia × año, máster × ciudad × modalidad) | rastreo infinito, páginas sin resultados y contenido duplicado | solo las combinaciones con umbral; el resto, filtros en la página o 404 | Google: navegación por facetas |
| Publicar las fichas que no llegan al mínimo con `noindex` en masa | Google sigue descargándolas: más de la mitad del rastreo se gastaría en páginas que no pueden posicionar | no generarlas hasta que lleguen; fila en el listado mientras tanto | Google: presupuesto de rastreo |
| Guías y textos generados en serie con IA («todo sobre la oposición de X», uno por cuerpo) | abuso de contenido a escala, «no matter how it's created» | texto propio y revisado en las páginas de cuerpo, corto, y los datos hacen el resto | Google: políticas de spam; contenido con IA |
| Títulos de plantilla que solo cambian en un dato | Google los trata como malos y reescribe el título | títulos que varían en varios datos (plazas, plazo, lugar, año) | Google: títulos |
| Cambiar la fecha de «actualizado» cada día | Google pregunta por ello en su guía y deja de fiarse del `lastmod` | fecha que solo cambia con el dato (lo controla el control) | Google: contenido útil; Bing: sitemaps |
| Ventanas al entrar (correo, avisos, descarga de la app, notificaciones del navegador) | ventana intrusiva: la página cae en móvil | avisos solo al pulsar «Avisarme» | Google: interstitials |
| Aviso de cookies por publicidad | es una ventana al entrar en cada visita | sin cookies de publicidad ni de analítica | AEPD; estrategia de monetización |
| Esconder datos en pestañas, PDF o imágenes | Google los indexa con menos peso y los sistemas de IA pueden no verlos | secciones visibles en HTML | Microsoft: contenido para respuestas con IA |
| Bloquear robots de IA o de entrenamiento, o aceptar el ajuste de Cloudflare para webs con anuncios | desaparecer de ChatGPT, Copilot o Claude; en Cloudflare, bloquear el entrenamiento con «Block» bloquea también a Googlebot y a Bingbot | todo permitido y vigilado a diario | OpenAI; Cloudflare |
| `nosnippet` o `data-nosnippet` sobre datos | la página no sale en AI Overviews ni en las respuestas de Copilot | sin limitar el fragmento | Google: robots meta; Bing |
| Copiar descripciones de centros, temarios o guías de otras webs | contenido copiado; además, las bases de datos ajenas tienen protección propia | hechos con fuente, con nuestras palabras | Google: políticas de spam (scraping) |
| Alojar contenido de academias o centros escrito por ellos | política de reputación del sitio | contenido nuestro; lo patrocinado, marcado | Google: políticas de spam |
| Comprar o intercambiar enlaces, artículos patrocinados con enlace | spam de enlaces; puede traer una acción manual | autoridad con datos e informes | Google: políticas de spam |
| Comprar un dominio caducado o redirigir dominios para heredar autoridad | abuso de dominios caducados | dominio nuevo con historial revisado | Google: políticas de spam |
| Secuestrar el botón «atrás» (ventanas o redirecciones al volver) | práctica maliciosa desde abril de 2026 | nada que altere la navegación | Google: políticas de spam |
| Parecer una web oficial | engaña al usuario e incumple la licencia del BOE | marca propia y aviso de que el documento válido es el oficial | Licencia BOE; ley del proyecto |
| Publicar todo de golpe en un dominio nuevo | Google valora el sitio en conjunto; decenas de miles de páginas nuevas, muchas sin datos, dan peor señal que pocas y buenas | lanzamiento por oleadas | recomendación propia, con la guía de Google sobre contenido a escala |
| Copias de la web en el repositorio público | contenido duplicado indexado en otro dominio | publicación directa al alojamiento | ley del proyecto |

## Calendario de 18 meses

El calendario cruza las fases de la guía con lo que necesita el SEO y con la estacionalidad de cada búsqueda.

| Cuándo | Qué | Por qué en ese momento |
|---|---|---|
| Noviembre de 2026 | Nombre y dominio revisados; alta en Cloudflare con la configuración fija; Search Console y Bing Webmaster Tools el mismo día; secretos de vigilancia y avisos | sin dominio no hay nada que medir; Search Console tarda días en dar datos |
| Noviembre-diciembre de 2026 | Generador de páginas con el contrato del control; taxonomía de cuerpos unificada; regla de direcciones con turno; textos de metodología, correcciones y aviso legal | lo que no se decide antes de publicar cuesta redirecciones después |
| Diciembre de 2026 | Completar textos y extracción pendientes de oposiciones (12.030 y 11.472 procesos); actos de los boletines provinciales | sube los procesos con datos mínimos del 44,1 % a lo que dé el motor; la historia es el diferencial |
| Enero de 2027 | Oleada 1: procesos con plazo abierto y de los últimos doce meses con datos mínimos, 52 provincias, 19 comunidades, cuerpos con 50 procesos o más, `plazo-abierto`; `JobPosting` e Indexing API; petición del carrusel de sitios de empleo | es la sección que trae tráfico desde el primer mes; sin temporada baja |
| Febrero de 2027 | Oleada 2: resto de procesos con datos, cuerpos con 10 procesos, cuerpo × comunidad, municipios con umbral | solo si la proporción de páginas indexadas de la oleada 1 es alta |
| Febrero-marzo de 2027 | Notas de corte con histórico y calculadora, indexadas como muy tarde en marzo | la demanda llega en junio; Google tarda meses en posicionar páginas nuevas |
| Marzo-mayo de 2027 | Másters con precio (preinscripción en primavera); grados con datos mínimos | llegar antes de las fechas de preinscripción y de la selectividad |
| Junio-julio de 2027 | Notas de corte del curso nuevo el mismo día de cada adjudicación; grados para quien acaba de hacer la selectividad | pico de demanda del año en estudios |
| Julio-septiembre de 2027 | FP antes de la admisión de verano; tests gratuitos de la plataforma | según la secuencia de la guía y de la monetización |
| Cada mes | Revisión de la ley contra la documentación oficial; informe de posiciones por familia | Google cambia sus normas varias veces al año (siete actualizaciones de núcleo, de spam y de Discover en 2026 hasta octubre) |

## Medición y señales de alarma

La vigilancia diaria ya mira lo técnico. Esto es lo que se mira para saber si la estrategia funciona:

| Indicador | Fuente | Objetivo | Alarma |
|---|---|---|---|
| Páginas indexadas sobre enviadas en sitemaps, por sección | Search Console (páginas) | más del 80 % a los tres meses de cada oleada | menos del 60 %, o una caída de 10 puntos en una semana |
| Tiempo hasta indexar una ficha nueva de proceso | inspección de URL de una muestra diaria | menos de 48 horas | más de 5 días |
| Impresiones y clics por sección y por plantilla | Search Console (rendimiento) | crecimiento mes a mes | caída de más del 30 % de una semana a otra fuera de festivos |
| Posición media en un conjunto fijo de 200 búsquedas por familia | Search Console | en el primer resultado en las búsquedas de cola larga (municipio, proceso concreto) en seis meses | caída de varias posiciones a la vez en una familia, que suele indicar una actualización de Google |
| CTR por plantilla | Search Console | por encima de la media de su posición | títulos reescritos por Google (se ve comparando el título enviado con el mostrado) |
| Impresiones en AI Overviews y AI Mode | Search Console (IA generativa) | crecimiento | caída tras un cambio de plantilla |
| Citas en Copilot | Bing Webmaster Tools (AI Performance) | crecimiento | — |
| Canónica elegida por Google distinta de la nuestra | inspección de URL | ninguna | cualquiera: suele ser contenido casi igual a otra página |
| Velocidad real (p75 de LCP, INP y CLS) | CrUX | todo en verde | cualquier métrica en ámbar |
| Búsquedas de marca | Search Console (consultas con el nombre) | crecimiento sostenido | — |
| Dominios que enlazan | Search Console (enlaces) | crecimiento con informes y datos abiertos | enlaces desde webs de spam (se revisan, no se desautorizan sin motivo) |

## Riesgos y qué haría cambiar la estrategia

- **Actualizaciones de Google.** En 2026 ha habido, hasta octubre, actualizaciones de núcleo en marzo y mayo, de spam en marzo, junio, agosto y septiembre, y de Discover en febrero. Un sitio de datos con fuentes y sin trucos es de los que menos sufren, pero puede sufrir. Ante una caída se mira primero qué plantilla y qué familia, nunca se cambia todo a la vez.
- **Respuestas sin clic.** AI Overviews, AI Mode y los resultados de empleo de Google pueden responder con nuestros datos sin que la persona entre. La defensa es que la página siga siendo necesaria (historia, herramientas, avisos, «Mi plan») y tener canales propios: correo de avisos, Telegram, calendario suscrito. La métrica de la monetización, los seguidores activos, mide justo eso.
- **Competidores que copian nuestros datos.** Es probable, porque nuestros datos son la parte valiosa. Defensas: publicar antes (nuestro circuito diario), datos con fecha de captura, la historia del proceso (difícil de copiar entera) y la protección de las bases de datos cuando la copia sea sustancial.
- **Errores en temas YMYL.** Un plazo mal calculado publicado como cierto daña la confianza de Google y de las personas. Por eso el plazo estimado se dice como estimado, el registro de correcciones es público y el control no publica un dato sin fuente.
- **Dependencia de Cloudflare.** Su política sobre robots de IA ha cambiado tres veces en 2025-2026. La vigilancia diaria comprueba el robots.txt servido y el HTML servido; el plan B (Bunny) está en la ley.
- **Qué cambiaría la estrategia**: que Google o Bing publiquen una norma nueva (revisión mensual), que la proporción de páginas indexadas no supere el 60 % tras dos oleadas (señal de que Google no ve valor suficiente) o que una familia de búsquedas no despegue en seis meses (revisar la plantilla con los datos de Search Console, no con intuiciones).

## Anexo A. Inventario de páginas para el lanzamiento

Estimación con los datos del 30/10/2026 y los umbrales propuestos. No es un objetivo de cantidad, sino el techo de páginas con datos propios que hoy se pueden publicar.

| Tipo de página | Universo | Con datos o umbral hoy | Fuente de la cifra |
|---|---|---|---|
| Ficha de proceso de oposición | 38.536 procesos (2022-2026) | 16.977 con convocante, plazas y plazo (44,1 %) | `datos/oposiciones/procesos.jsonl` |
| Ficha con `JobPosting` (plazo abierto) | 394 procesos hoy | 394 (1.767 plazas) | mismo |
| Cuerpo | 9.332 claves de puesto | 299 con 10 procesos o más, antes de unificar sinónimos | mismo |
| Cuerpo × comunidad | 13.020 combinaciones | 288 con 10 procesos o más | mismo |
| Municipio | 8.132 municipios | 1.307 con 3 procesos o más, más los que tengan uno abierto (217 hoy) | mismo y catálogo del INE |
| Provincia y comunidad | 52 y 19 | 71 | — |
| Ficha de grado | 4.296 | 2.100 (48,9 %) | `claude/modelo-grados.md` |
| Grado genérico | 703 | 245 con dos universidades o más | mismo |
| Asignatura (carreras con…) | 36.890 asignaturas | 8.250 en dos títulos o más; con el umbral de 5, menos | mismo |
| Ficha de máster | 4.347 títulos oficiales activos y unos 1.000 proveedores no oficiales | las que tengan asignaturas y precio (el precio aparece hoy en un tercio de las fichas web medidas) | `claude/modelo-masters.md`, `claude/estrategia-informacion-cerrada.md` |

## Anexo B. Cómo se mide y se mantiene esta estrategia

- **Ley del proyecto**: `docs/ley-seo.md`, revisada contra la documentación oficial cada mes y cada vez que Google anuncia una actualización.
- **Control antes de publicar**: `python -m motor.seo.control` (catálogo de reglas en `motor/seo/reglas.py`). Los umbrales de este documento que se aprueben pasan al control como datos mínimos de cada tipo.
- **Vigilancia diaria del sitio publicado**: `motor/seo/vigilancia.py` y el flujo `seo.yml`, que se encienden con la variable `SEO_BASE` en cuanto exista el dominio.
- **Avisos a buscadores**: `motor/seo/notificar.py` (IndexNow e Indexing API).
- **Competencia y dominios**: `motor/seo/competencia.py` y `motor/seo/dominio.py`, ejecutados con el flujo «SEO, análisis bajo demanda».
- **Análisis de los datos de oposiciones de este documento**: reproducible desde `datos/oposiciones/procesos.jsonl` de la rama `datos` (38.536 líneas, versión del 30/10/2026).

## Anexo C. Decisiones que necesitan a Álvaro

1. **Umbrales de las páginas de categoría**: cuerpo con 10 procesos en cinco años, cuerpo por comunidad con 10, municipio con 3 o uno abierto, máster por área y ciudad con 5 programas, asignatura con 5 títulos. Hoy la ley pide para el municipio «al menos un proceso»; la propuesta lo sube.
2. **No generar las fichas por debajo del mínimo** (en lugar de publicarlas con `noindex`), mostrándolas como fila en sus listados.
3. **Regla de direcciones** con el turno y, si hace falta, el mes, para los 1.366 choques actuales.
4. **Ajuste del diseño**: ventanas como secciones visibles de una sola página.
5. **Nombre y dominio**, con la revisión de questudio.es del anexo D.
6. **Lanzamiento por oleadas** y fechas del calendario.
7. **Petición a Google del carrusel de sitios de empleo** cuando la sección de oposiciones esté publicada.

## Anexo D. Revisión del dominio questudio.es

Revisión hecha el 30/10/2026 desde GitHub con `motor/seo/dominio.py` (Wayback Machine, último índice de Common Crawl y DNS). Resultado guardado en la rama `seo` del repositorio (`20261030T122803-dominio/`).

| Dominio | Capturas en la Wayback Machine | Common Crawl (CC-MAIN-2026-43) | Resuelve hoy | Lectura |
|---|---|---|---|---|
| questudio.es | portada capturada en 2010 y en 2024 (última, 2 de agosto de 2024) | ninguna dirección | no | **tuvo uso antes**; hay que ver qué era antes de registrarlo |
| questudio.com | todos los años desde 2003 hasta junio de 2026 | 20 direcciones o más, con un blog sobre Odoo, ERP, PIM, CRM y comercio electrónico | sí | **en uso por otra empresa** de otro sector |
| questudio.net | ninguna | ninguna | no | libre de historial |

Lo que significa:

- **El .es no es un dominio nuevo sin historia.** Que tenga capturas de 2010 y 2024 no lo descarta. Si fue una web normal y lleva años sin uso, Google la trata prácticamente como nueva. Lo que sí lo descartaría es que hubiera sido spam, apuestas, farmacia, contenido para adultos o una red de enlaces (abuso de dominios caducados, en las políticas de Google). Hay que abrir las dos capturas en la Wayback Machine (`web.archive.org/web/2010*/questudio.es` y `web.archive.org/web/2024*/questudio.es`) y mirar qué había. Si se registra, lo primero en Search Console es revisar «Acciones manuales» y «Problemas de seguridad».
- **El .com no se puede tener y otra empresa usa la marca.** Quien busque «questudio» encontrará también esa web, y algunas personas escribirán .com por costumbre. No impide usar el .es, pero hace más difícil ser el único resultado cuando alguien busca la marca, que es justo la búsqueda de quien ya nos conoce y vuelve. Antes de decidir conviene buscar «Questudio» en las bases de marcas de la OEPM y de la EUIPO, para saber si está registrada y en qué clases.
- **El nombre en sí cumple las reglas**: es de marca y no de palabras clave, no lleva guiones ni cifras y no aparenta carácter oficial. Además coincide con una pregunta natural («¿qué estudio?»). Eso ayuda a recordarlo, pero también lo confunde con búsquedas genéricas.

Recomendación: no descartarlo todavía. Antes de registrarlo hay que ver las dos capturas antiguas del .es y comprobar la marca en la OEPM y la EUIPO. Mientras tanto, conviene pasar dos o tres alternativas por la misma revisión, para comparar con datos.

## Anexo E. Fuentes

Consultadas el 30/10/2026. Entre paréntesis, la fecha de última actualización que muestra la página cuando la da.

**Google**

- [Políticas de spam](https://developers.google.com/search/docs/essentials/spam-policies) (28/08/2026)
- [Funciones de IA y tu sitio web](https://developers.google.com/search/docs/appearance/ai-features) (10/12/2025)
- [Guía de optimización para la búsqueda con IA generativa](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide) (10/07/2026)
- [Control de IA generativa en la Búsqueda (Search Console)](https://support.google.com/webmasters/answer/16908024) e [informe de rendimiento con IA generativa](https://support.google.com/webmasters/answer/16984139)
- [Contenido útil, fiable y centrado en las personas](https://developers.google.com/search/docs/fundamentals/creating-helpful-content) y [contenido generado con IA](https://developers.google.com/search/docs/fundamentals/using-gen-ai-content)
- [Títulos](https://developers.google.com/search/docs/appearance/title-link) y [fragmentos y descripciones](https://developers.google.com/search/docs/appearance/snippet)
- [Googlebot: límite de 2 MB](https://developers.google.com/search/docs/crawling-indexing/googlebot) (03/02/2026)
- [Presupuesto de rastreo](https://developers.google.com/crawling/docs/crawl-budget) (22/07/2026)
- [Navegación por facetas](https://developers.google.com/crawling/docs/faceted-navigation) y [paginación](https://developers.google.com/search/docs/specialty/ecommerce/pagination-and-incremental-page-loading)
- [Sitemaps](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap) (08/07/2026)
- [JobPosting](https://developers.google.com/search/docs/appearance/structured-data/job-posting) (08/09/2026), [sitios de empleo en el EEE](https://developers.google.com/search/docs/appearance/job-sites) (09/10/2026) e [Indexing API](https://developers.google.com/search/apis/indexing-api/v3/using-api) (16/10/2026)
- [Galería de datos estructurados](https://developers.google.com/search/docs/appearance/structured-data/search-gallery) (16/10/2026) y [registro de cambios de Search Central](https://developers.google.com/search/updates)
- [Panel de estado de la Búsqueda](https://status.search.google.com/summary)
- [Metaetiquetas de robots](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag), [nombre del sitio](https://developers.google.com/search/docs/appearance/site-names), [icono](https://developers.google.com/search/docs/appearance/favicon-in-search), [redirecciones](https://developers.google.com/search/docs/crawling-indexing/301-redirects), [estructura de URL](https://developers.google.com/search/docs/crawling-indexing/url-structure), [ventanas intrusivas](https://developers.google.com/search/docs/appearance/avoid-intrusive-interstitials) y [Core Web Vitals](https://developers.google.com/search/docs/appearance/core-web-vitals)
- [Límites de las API de Search Console](https://developers.google.com/webmaster-tools/limits)
- [Directrices de los evaluadores de calidad](https://static.googleusercontent.com/media/guidelines.raterhub.com/en//searchqualityevaluatorguidelines.pdf) (edición del 11/09/2025)

**Microsoft y Bing**

- [Optimizar el contenido para las respuestas con IA](https://about.ads.microsoft.com/en/blog/post/october-2025/optimizing-your-content-for-inclusion-in-ai-search-answers) (08/10/2025)
- [Sitemaps en la búsqueda con IA](https://blogs.bing.com/webmaster/2025/7/Keeping-Content-Discoverable-with-Sitemaps-in-AI-Powered-Search/) (31/07/2025)
- [AI Performance en Bing Webmaster Tools](https://blogs.bing.com/webmaster/February-2026/Introducing-AI-Performance-in-Bing-Webmaster-Tools-Public-Preview) (10/02/2026)
- [Copilot y la búsqueda de Bing](https://learn.microsoft.com/en-us/copilot/privacy-and-protections) (24/08/2026)
- [IndexNow](https://www.indexnow.org/documentation)

**Robots de IA**

- [OpenAI](https://developers.openai.com/api/docs/bots) y [búsqueda de ChatGPT](https://help.openai.com/en/articles/9237897-chatgpt-search)
- [Anthropic](https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler) (07/04/2026)
- [Perplexity](https://docs.perplexity.ai/docs/resources/perplexity-crawlers)
- [DuckDuckGo: fuentes de resultados](https://duckduckgo.com/duckduckgo-help-pages/results/sources)

**Cloudflare**

- [Robots de IA](https://developers.cloudflare.com/bots/additional-configurations/block-ai-bots/) (01/07/2026) y [ajustes para dominios nuevos](https://blog.cloudflare.com/accountable-mixed-use-ai-crawlers) (15/09/2026)
- [robots.txt gestionado](https://developers.cloudflare.com/bots/additional-configurations/managed-robots-txt/) (22/10/2026)
- [Límites de Workers](https://developers.cloudflare.com/workers/platform/limits/) (12/10/2026)

**Mercado**

- [StatCounter, cuota de buscadores en España](https://gs.statcounter.com/search-engine-market-share/all/spain) (septiembre de 2026; fuente no oficial)

**Datos propios**

- Rama `datos` del repositorio, `datos/oposiciones/procesos.jsonl` y `resumen.json` (30/10/2026).
- Documentos del proyecto: modelo de grados, modelo de másters, estrategia de información cerrada, diseño de la web y estrategia de monetización.

