# Estrategia: conseguir y mantener al día lo que hoy se da solo al registrarse

Versión 29/10/2026. Complementa `docs/modelo-masters.md`. Aplica a cada máster, oficial o no.

## 1. El problema, medido

Lo que más valor tiene para quien elige un máster es justo lo que se esconde tras un formulario: precio
total y forma de pago, folleto y plan de estudios, guía docente, metodología, evaluación, becas, horario,
plazas y fechas de admisión.

Medido el 29/10/2026 en 348 páginas de programa de 111 centros no universitarios verificados:

| Qué | Páginas |
|---|---|
| Formulario que pide el correo | 60 % |
| Formulario que pide el teléfono | 32 % |
| Habla de precio | 92 % |
| Da un importe en euros | 50 % |
| Precio en los datos estructurados de la página (Schema.org) | 14 % |
| Menciona asignaturas o módulos | 69 % |
| Menciona becas o descuentos | 65 % |
| Menciona metodología | 58 % |
| Menciona evaluación | 46 % |
| Menciona plazas | 30 % |
| Guía o folleto en PDF enlazado sin formulario | 9 % |

«Menciona» no es «da el dato»: la cifra exacta por campo sale de la extracción (`extraer.py`). Las
universidades se miden en el barrido de sus webs (§9).

## 2. Reglas que no se tocan

1. **Solo lo publicado o lo facilitado a sabiendas.** Nunca identidades falsas, nunca hacerse pasar por
   alumno, nunca rellenar formularios para sacar un folleto, nunca buscar rutas ocultas a documentos que
   el centro reserva tras un formulario.
2. **Robots y reserva de minería.** Se respetan `robots.txt` y la reserva expresa de minería de textos y
   datos (cabecera o meta `tdm-reservation`, fichero `/.well-known/tdmrep.json`). El rastreador ya lo
   comprueba en cada web; un centro con reserva no se procesa con IA, solo se enlaza.
3. **Hechos, no textos.** Se publican datos (precio, créditos, fechas, asignaturas) con su fuente y fecha;
   nunca descripciones copiadas ni folletos. Los agregadores no son fuente.
4. **Sin datos de personas.** No se guardan nombres de profesores ni de contactos comerciales.
5. **Decir lo que no sabemos.** Si el centro no publica un dato, la ficha lo dice así: «el centro no
   publica el precio; lo facilita tras pedir el correo y el teléfono». Es un dato verdadero, útil y nuestro.

## 3. Las palancas, de más fuerte a más débil

### 3.1 Fuentes oficiales que obligan a publicar (máster oficial)

| Dato | Fuente | Estado |
|---|---|---|
| Asignaturas con ECTS, carácter y semestre | RUCT, memoria vigente | conector hecho, 23 de 23 en la muestra |
| Plazas y modalidad por centro, idiomas | RUCT, memoria | hecho, 23 de 23 |
| Criterios de admisión y su peso, complementos | RUCT, memoria | hecho, 23 de 23 |
| Evaluación con ponderación por materia | RUCT (memorias RD 1393/2007) | hecho, 11 de 13 memorias de ese formato |
| Evaluación y metodología por asignatura | guía docente, obligatoria antes de la matrícula (RD 822/2021, art. 9.3) | mapa de plataformas hecho (`docs/fuentes-guias-docentes.md`): SIGMA DOA cubre 12 universidades con un conector; 10 más con URL predecible |
| Plan publicado | BOE | hecho |
| Precio público por crédito | decreto u orden anual de cada comunidad | normas de las 19 administraciones identificadas (`docs/fuentes-precios-publicos.md`); 17 leídas, Navarra y Murcia por verificar |
| Becas generales | BOE y Base de Datos Nacional de Subvenciones | pendiente |
| Convenios de títulos propios con empresas | portales de transparencia de las públicas | pendiente |

### 3.2 Lo que el centro publica pero no enseña en la ficha

- **Tarifas en PDF**: muchas privadas publican tarifas o «honorarios académicos» en PDF aunque la ficha
  pida el teléfono (Universidad Europea, UAX, UFV comprobadas). El rastreador ya recoge de cada web los
  PDF cuyo nombre o enlace habla de tarifas, precios, honorarios o tasas.
- **Datos estructurados**: el 14 % de las páginas lleva el precio en el código (Schema.org `Offer`)
  aunque no siempre se vea.
- **Condiciones generales de contratación y normativa económica**: suelen fijar reserva, plazos de pago y
  devoluciones.
- **Trampa a evitar**: el «precio público por ECTS a efectos de beca» que publican algunas privadas no es
  el precio de venta. Nunca se publica como precio.

### 3.3 Obligaciones de información al consumidor

Pendiente del estudio jurídico en curso (normativa estatal de consumidores y decretos autonómicos sobre
enseñanza no reglada). Si una norma obliga a dar el precio antes de pedir datos, la ficha lo dirá con su
referencia cuando el centro no lo publique.

### 3.4 Petición directa y transparente al centro

Lo que no está publicado se pide, como medio, con identidad real:

- Cuenta de correo del portal (la crea Álvaro; Claude no crea cuentas ni rellena formularios con datos).
- Mensaje identificado como portal informativo, no como alumno (plantilla en el anexo), al correo de
  admisiones o por el formulario de contacto institucional, nunca por el de «solicita información» que
  alimenta su embudo comercial.
- Se piden los datos de la ficha, no el folleto: precio total, reserva, forma de pago, plan de estudios
  con créditos, metodología, evaluación, horario, plazas, fechas de admisión y becas.
- Registro de cada petición: fecha, canal, respuesta y fecha de la respuesta. Recordatorio a los 15 días.
- En la ficha: «dato facilitado por el centro a [portal] el [fecha]».
- Una vez al año, antes de la preinscripción, se pide la actualización.

### 3.5 Ficha verificada por el centro

El centro puede revisar y completar su ficha (alta gratuita):

- Ve la ficha tal como se publica, corrige datos y aporta los que faltan con su documento de respaldo.
- Lo aportado se muestra como «facilitado por el centro» y se coteja con lo público; si contradice una
  fuente oficial, gana la oficial y se avisa.
- Incentivo: la ficha completa sale mejor (más datos propios, mejor posicionamiento) y el indicador de
  transparencia (§5) sube. Es también la puerta del futuro botón voluntario de contacto.

### 3.6 Aportaciones de alumnos

Más adelante: precio pagado, horario real y forma de pago, con justificante revisado a mano y sin datos
personales. Se publica como agregado («3 alumnos indican…») con fecha; nunca el documento.

### 3.7 Peticiones formales

Por la Ley 19/2013 (transparencia) y la Ley 37/2007 (reutilización), a las universidades públicas: precio de
títulos propios, convenios con entidades que los venden, guías docentes en formato reutilizable. Al
Ministerio: precio por título, afiliación por título y QEDU.

## 4. Mantenerlo al día

| Dato | Cuándo cambia | Cómo se detecta | Frecuencia |
|---|---|---|---|
| Altas, cambios y extinciones de títulos oficiales | todo el año | BOE diario (acuerdos y planes) | diaria |
| Memoria del RUCT | con cada modificación | histórico de incidencias de la ficha | semanal |
| Precio público | junio-agosto | boletines autonómicos | diaria en esos meses |
| Tarifas privadas | primavera-verano | PDF de tarifas: huella distinta | semanal en temporada, mensual fuera |
| Ficha web del programa | cualquier momento | `lastmod` del sitemap, cabeceras `ETag`/`Last-Modified` y huella del texto limpio | semanal con admisión abierta, mensual el resto |
| Guías docentes | antes de la matrícula | huella del documento | mensual de junio a octubre |
| Plazos de admisión | por edición | extracción de la ficha | semanal con admisión abierta |
| Datos pedidos al centro | por edición | petición anual | anual, antes de la preinscripción |

Reglas:

- Solo se vuelve a extraer lo que ha cambiado (huella distinta); la fecha del dato solo cambia si cambia el
  dato (ley SEO).
- Cada dato tiene vigencia esperada; pasada sin confirmación, la ficha dice «sin novedades desde
  [fecha]; consulta [fuente]» en vez de darlo por vigente.
- Alerta si un dato desaparece de la web (por ejemplo, el precio deja de publicarse) o cambia de golpe.

## 5. Indicador de transparencia de cada máster

Dato propio que nadie da: qué parte de lo esencial publica el centro sin pedir datos.

- Campos esenciales: precio total, plan de estudios con créditos, metodología, evaluación, horario,
  plazas, fechas de admisión, becas, tipo de título y quién lo expide.
- Para cada campo, la mejor fuente disponible: publicado en la ficha, documento público del centro,
  fuente oficial, facilitado por el centro a petición, o no disponible sin registro.
- Se publica con su metodología y fecha, como hecho medido, sin juicios. Explica al alumno qué esperar y
  empuja a los centros a publicar.

## 6. Quién hace qué

| Tarea | Motor (Claude) | Álvaro o equipo |
|---|---|---|
| Barrido de webs, tarifas, sitemaps, cambios | sí | — |
| Extracción con cita literal y control | sí | revisión de dudosos |
| Fuentes oficiales (RUCT, BOE, decretos, guías) | sí | — |
| Cuenta de correo del portal y envío de peticiones | prepara la lista y el texto | crea la cuenta y envía |
| Altas de centros en «ficha verificada» | prepara el flujo | gestiona la relación |
| Peticiones formales a las administraciones | redacta | firma y presenta |

## 7. Riesgos

- Bloqueo de un centro: peticiones lentas e identificadas; si bloquea, se respeta y la ficha enlaza a su web.
- Reclamación de un centro por un dato: cada dato tiene fuente, fecha y cita; se corrige en el día.
- Derechos de autor y bases de datos: solo hechos, nunca textos ni extracción sustancial de directorios.
- Confusión entre oficial y propio: la ficha siempre dice quién expide el título y si es oficial.

## 8. Anexo: plantilla de petición al centro

Asunto: Datos del [nombre del máster] para [portal]

> Buenos días: escribimos desde [portal], un portal informativo y gratuito sobre estudios en España
> ([dirección web]). Estamos publicando la ficha del [nombre del máster] con datos verificados y enlace a
> vuestra web. ¿Podéis confirmarnos o facilitarnos: precio total y reserva de plaza, forma de pago, plan
> de estudios con créditos, metodología y sistema de evaluación, horario, plazas, fechas de admisión de la
> próxima edición y becas o descuentos? Citaremos que el dato lo facilita el centro y la fecha. No
> cedemos datos ni pedimos información de alumnos. Gracias.

## 9. Estado del barrido (29/10/2026)

En curso: webs de todas las universidades y centros oficiales (352 dominios) y nuevo descubrimiento en
Common Crawl con el patrón ampliado. Las cifras por universidad se añaden al terminar.
