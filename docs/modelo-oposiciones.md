# Modelo de datos de oposiciones: no perder nada, del anuncio al resultado

Versión 29/10/2026. Basado en los anuncios reales del BOE de octubre de 2026.

## Principio

Tres capas que nunca se mezclan:

1. **Capturas**: cada documento descargado (sumario, anuncio, PDF de bases, lista, página de sede) se guarda intacto con su sha256, URL y fecha. No se borra nunca.
2. **Actos**: cada publicación sobre un proceso es un acto, con su fuente exacta, los campos extraídos y la frase literal de la que sale cada campo. Los actos no se sobrescriben: una corrección es un acto nuevo.
3. **Procesos**: se construyen uniendo actos. El estado y los datos vigentes se recalculan desde los actos. Si una unión era errónea, se rehace sin perder nada.

Si el extractor mejora, se reprocesa desde las capturas. Nada depende de haberlo leído bien la primera vez.

## Entidades

| Entidad | Qué es | Claves |
|---|---|---|
| Convocante | Ministerio, comunidad, consejería, servicio de salud, diputación, ayuntamiento, consorcio, universidad | DIR3, código INE del municipio, provincia, comunidad, web, sede electrónica, tablón |
| Cuerpo o categoría | Puesto normalizado: «Auxiliar administrativo», grupo C2, titulación exigida | id propio; escala, subescala y clase; grupo; nivel CNED |
| Oferta de empleo | La oferta anual de cada convocante: el aviso más temprano de lo que se va a convocar (hasta tres años antes) | convocante + año |
| Proceso | Una convocatoria concreta | convocante + cuerpo + oferta + sistema + turno |
| Acto | Una publicación sobre un proceso | boletín + número + fecha + identificador o página |
| Resultado | Cifras agregadas de cada fase, nunca nombres | proceso + fase |
| Documento | Bases, temario, examen, plantilla de respuestas | captura sha256 |
| Bolsa | Lista de empleo derivada de un proceso o independiente | convocante + cuerpo + fecha |

## Tipos de acto

Oferta de empleo · bases · extracto en boletín autonómico · apertura de plazo (anuncio en el BOE) · corrección · ampliación o reducción de plazas · admitidos provisional · admitidos definitivo · tribunal · fecha y lugar de examen · plantilla de respuestas · resultados de cada ejercicio · valoración de méritos · aprobados · propuesta de nombramiento · nombramiento y toma de posesión · constitución de bolsa · recurso, suspensión o anulación · plaza desierta.

## Resultados (solo agregados)

Admitidos, excluidos, presentados por ejercicio, aprobados por ejercicio, nota mínima de aprobado, nota del último aprobado, plazas cubiertas y desiertas, personas en bolsa.
Se calculan contando las listas. Los nombres y DNI nunca se guardan en la base de datos ni se publican; el PDF original queda en el archivo privado como prueba.

Con esto se generan datos que nadie da junto: aspirantes por plaza, tasa de presentados, nota de corte histórica por cuerpo y convocante, y tiempo real de cada convocante entre convocatoria, examen y nombramiento.

## Dónde se captura cada acto

| Fuente | Qué aporta |
|---|---|
| BOE (diario) | Todo el proceso del Estado y de las universidades. Apertura de plazo de todos los procesos locales de plaza fija, con la referencia al boletín donde están las bases |
| 19 boletines autonómicos | Todo el proceso de las comunidades (docentes y sanidad incluidos). Extractos de convocatorias locales. Bases locales en las comunidades de una sola provincia |
| 43 boletines provinciales | Bases locales, ofertas de empleo locales, admitidos, tribunales, fechas de examen, a veces aprobados. Interinidades y bolsas |
| Sedes y tablones de los convocantes | Notas de ejercicios y aprobados locales, listas intermedias de consejerías y servicios de salud |
| Punto de Acceso General | Control de cobertura diario |

Sedes y tablones: solo se vigilan los convocantes con un proceso vivo, que conocemos por el BOE. Muchos ayuntamientos pequeños usan plataformas comunes (por ejemplo, las que ofrecen las diputaciones), de modo que un conector puede cubrir muchos municipios. Por verificar plataforma a plataforma.

## Unión de actos con su proceso

1. Referencias explícitas en el texto: «bases publicadas en el Boletín Oficial de la Provincia de Málaga número 40, de 27 de febrero de 2026», «convocado por Resolución de 30 de junio de 2026, BOE número 162».
2. Convocante + cuerpo + año de oferta + turno.
3. Número de expediente cuando aparece.
4. IA solo para desempatar, con su grado de confianza.
5. Lo que no se une con seguridad va a la cola de huérfanos y a revisión. Nunca se descarta.

## Estado del proceso

Oferta → bases → plazo abierto → plazo cerrado → admitidos provisional → admitidos definitivo → examen convocado → resultados por ejercicio → aprobados → nombramiento → terminado. Además: bolsa, suspendido, anulado, desierto.

El estado sale del último acto conocido y su fecha. Si no sabemos algo, la página dice «sin novedades desde [fecha]; consulta [fuente]», nunca un estado inventado.

## Seguimiento activo

Cada estado espera un acto siguiente. El motor vigila la fuente donde debería salir (la que dicen las bases) con una frecuencia según la fase. Si se retrasa más de lo normal para ese convocante, el proceso pasa a «seguimiento pendiente» y se revisa.

## Controles para no perder nada

- Cada anuncio local del BOE debe tener sus bases localizadas en el boletín citado; si no, alerta de cobertura.
- Cada proceso con plazo abierto debe llegar a admitidos; si no llega en el tiempo habitual, seguimiento.
- Recuento diario de actos por fuente frente a lo normal para ese día.
- Comparación diaria con el Punto de Acceso General.
- Numeración correlativa de cada boletín.
- Valores versionados: si una corrección cambia 3 plazas a 4, se guardan ambos y la página muestra el cambio con su fecha.
- Carga histórica desde el 01/01/2022 para unir los actos nuevos con sus procesos y tener series de resultados.

## Orden de construcción

1. Esquema de la base de datos con estas entidades.
2. BOE desde 2022: sumarios, texto de cada anuncio y extracción de actos.
3. Unión de actos en procesos, estados y cálculo de plazos con calendario de festivos.
4. Boletines autonómicos.
5. Boletines provinciales, guiados por las referencias del BOE.
6. Sedes y tablones de procesos vivos.
7. Resultados agregados.
