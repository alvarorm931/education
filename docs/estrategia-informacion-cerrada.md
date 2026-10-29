# Estrategia: conseguir y mantener al día lo que hoy se da solo al registrarse

Versión 29/10/2026. Complementa `docs/modelo-masters.md`. Aplica a cada máster, oficial o no.

## 1. El problema, medido

Lo que más valor tiene para quien elige un máster es justo lo que se esconde tras un formulario: precio
total y forma de pago, folleto y plan de estudios, guía docente, metodología, evaluación, becas, horario,
plazas y fechas de admisión.

Medido el 29/10/2026 en 3.679 fichas de programa de 1.332 centros no universitarios verificados en su web
(barrido de 10.955 candidatos; en una revisión a mano, el 77 % de los que pasan los filtros son
proveedores reales) y, aparte, en 779 fichas de las webs de universidades y centros oficiales:

| Qué | No universitarios | Universidades y centros oficiales |
|---|---|---|
| Formulario que pide el correo | 51 % | 37 % |
| Formulario que pide el teléfono | 34 % | 30 % |
| Pide el correo y no da ningún importe | 31 % | — |
| Habla de precio | 76 % | 82 % |
| Da un importe en euros | 36 % | 31 % |
| Precio en los datos estructurados (Schema.org) | 12 % | 6 % |
| Menciona asignaturas o módulos | 66 % | 57 % |
| Menciona becas o descuentos | 60 % | 62 % |
| Menciona metodología | 52 % | 39 % |
| Menciona evaluación | 37 % | 29 % |
| Menciona plazas | 23 % | 33 % |
| Menciona horario o calendario | 43 % | — |
| Guía o folleto en PDF enlazado sin formulario | 9 % | 19 % |

«Menciona» no es «da el dato»: la cifra exacta por campo sale de la extracción (`extraer.py`). Una primera
medición en 348 páginas daba cifras más altas (60 % pide el correo, 50 % da importe): era el primer cuarto
de la lista, los centros más grandes, y además el rastreador leía mal las páginas sin codificación en la
cabecera (corregido).

## 2. Reglas que no se tocan

1. **Solo lo publicado o lo facilitado a sabiendas.** Nunca identidades falsas, nunca hacerse pasar por
   alumno, nunca rellenar formularios para sacar un folleto, nunca buscar rutas ocultas a documentos que
   el centro reserva tras un formulario.
2. **Robots y reserva de minería.** Se respetan `robots.txt` de cada servidor y la reserva expresa de
   minería de textos y datos (cabecera o meta `tdm-reservation`, fichero `/.well-known/tdmrep.json`). La
   excepción de minería está en el art. 67 del Real Decreto-ley 24/2021 (no en el TRLPI): solo sobre
   contenido accesible de forma legítima y salvo reserva expresa «por medios adecuados» (Directiva
   2019/790, art. 4.3 y considerando 18). Por prudencia, una prohibición en `robots.txt` se trata también
   como reserva. Un centro con reserva no se procesa con IA, solo se enlaza.
3. **Hechos, no textos.** Se publican datos (precio, créditos, fechas, asignaturas) con su fuente y fecha;
   nunca descripciones copiadas ni folletos. La minería permite analizar, no republicar. Los agregadores no
   son fuente: además de no ser primarios, sus bases de datos tienen protección propia (TRLPI, arts.
   133-135) y sus condiciones prohíben reproducirlas.
4. **Copias privadas.** Las páginas descargadas se guardan solo en el archivo privado; en la rama pública
   del repositorio queda únicamente su URL, fecha y huella. (El 29/10/2026 se retiraron de esa rama 101
   copias de páginas de centros que había subido una prueba; siguen en el historial de la rama y conviene
   purgarlo.)
5. **Sin datos de personas.** No se guardan nombres de profesores ni de contactos comerciales.
6. **Decir lo que no sabemos.** Si el centro no publica un dato, la ficha lo dice así: «el centro no
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
| Precio del crédito y plazas de másteres oficiales | QEDU (Ministerio, a partir del RUCT y del SIIU; lista descargable en XLSX o CSV) | según su ayuda, solo de universidades públicas: no resuelve el precio de las privadas; conector pendiente como control de los decretos |
| Si el título es oficial o propio | obligación de informar (LOSU, art. 7.4) | la ficha lo dice siempre; se comprueba que la web del centro lo diga |
| Becas generales | BOE y Base de Datos Nacional de Subvenciones | pendiente |
| Convenios de títulos propios con empresas | portales de transparencia de las públicas | pendiente |

Guías vetadas a robots: UCAM y Deusto prohíben todo rastreo en el servidor de sus guías (`Disallow: /`).
Para esos casos la vía es pedir permiso por escrito a la universidad o la petición formal (§3.7), nunca
saltarse el veto.

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

Estudio del 29/10/2026 (fuentes en `docs/fuentes-legales-informacion.md`).

- **Ninguna norma estatal obliga a enseñar el precio antes de pedir el correo.** Obligan a darlo antes del
  contrato y, si se contrata en línea, justo antes del pedido (TRLGDCU, arts. 60, 97.1.e y 98.2; Ley
  17/2009, art. 22). Si la web habla de precios, debe darlos claros y con impuestos (LSSI, art. 10.1.f).
  El formulario para captar contactos es lícito.
- **Algunas comunidades sí obligan a las escuelas no universitarias a ponerlo en la web** cuando venden a
  distancia: Andalucía (Decreto 625/2019: documento informativo con el precio final completo en la web
  junto a la oferta, arts. 6.1, 7.1 y 7.3, también para centros de fuera que venden allí, art. 2.1) y
  Castilla-La Mancha (Decreto 40/2026, arts. 7.1 y 8.2). La Comunidad de Madrid lo pide para los cursos por
  internet (Decreto 84/2004, según su ficha oficial; el texto del BOCM no se ha leído). Aragón (Decreto
  82/2003) y el País Vasco (Decreto 182/1997, en reforma) tienen normas propias sin requisito web
  verificado; en las demás no se ha localizado norma o no se ha verificado. Estas normas excluyen las
  enseñanzas del sistema educativo, y la universitaria está en él: los títulos propios de universidades
  quedan probablemente fuera (interpretación por confirmar con Consumo).
- **Universidades:** guía docente antes de la matrícula en los oficiales (RD 822/2021, art. 9.3); deber de
  decir si el título es oficial o propio y de no inducir a confusión (LOSU, art. 7.4; RD 822/2021, art. 36).
  El Tribunal Supremo anuló el RD 905/2025, que modificaba el RD 822/2021 (STS de 6/10/2026, según la
  copia publicada; no contrastada en el CENDOJ): el modelo usa la redacción del RD 822/2021 que esté
  vigente y se comprueba antes de publicar.

Uso en el portal: la ficha dice el hecho («el centro no publica el precio en su web»), nunca un juicio de
legalidad; la norma se cita en la petición al centro cuando le afecta (§3.4). Denunciar ante Consumo es
decisión de Álvaro, no del motor.

### 3.4 Petición directa y transparente al centro

Lo que no está publicado se pide, como medio, con identidad real:

- Cuenta de correo genérica del portal (la crea Álvaro; Claude no crea cuentas ni rellena formularios con
  datos). Pedir con identidad corporativa real y diciendo que somos un portal no está prohibido; el centro
  trata ese contacto profesional por interés legítimo (LOPDGDD, art. 19). Las identidades ficticias, en
  cambio, suponen tratar datos de terceros sin base legal, riesgo penal si se usa la identidad de otro
  (CP, art. 401) y coste real para el centro (paga por cada contacto que le llega de un agregador).
- **Cuándo empezar:** cuando el portal tenga dirección pública y fichas publicadas. Antes, decir «estamos
  publicando la ficha» no sería verdad.
- Mensaje identificado como portal informativo, no como alumno (plantilla en el anexo), al correo de
  admisiones o por el formulario de contacto institucional, nunca por el de «solicita información» que
  alimenta su embudo comercial.
- Se piden los datos de la ficha, no el folleto: precio total, reserva, forma de pago, plan de estudios
  con créditos, metodología, evaluación, horario, plazas, fechas de admisión y becas.
- Registro de cada petición: fecha, canal, respuesta y fecha de la respuesta. Recordatorio a los 15 días.
- En la ficha: «dato facilitado por el centro a [portal] el [fecha]».
- Una vez al año, antes de la preinscripción, se pide la actualización.

### 3.5 Ficha verificada por el centro

Es el modelo de Studyportals (datos de la web oficial de cada universidad, cuenta gratuita para corregir,
revisión por su equipo, al menos una vez al año, y avisos de error de los usuarios). Emagister y Educaweb,
en cambio, publican lo que da el centro y lo hacen responsable de sus precios. Lo nuestro: dato de la fuente
oficial o de la web del centro primero; lo que aporte el centro, marcado y cotejado.

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

- **Universidades públicas, por la Ley 19/2013** (art. 2.1.d): derecho de acceso sin motivar, respuesta en
  un mes ampliable a dos (arts. 12, 17.3 y 20.1). Qué pedir: precio de títulos propios, convenios con
  entidades que los imparten o venden (que además deben publicar: art. 8.1.b), guías docentes en formato
  reutilizable.
- **Universidades privadas:** no están sujetas a esa ley (CTBG, R/1116/2024). Lo que tengan el Ministerio,
  la comunidad o la agencia de calidad sobre ellas se pide a esas administraciones.
- **Ministerio y comunidades, por la Ley 37/2007** (reutilización, veinte días ampliables a cuarenta): datos
  del RUCT y del SIIU, precio por título, afiliación por título, QEDU, autorizaciones de centros y precios
  públicos. Esta ley no sirve con las universidades: excluye los documentos de las instituciones educativas
  que no sean datos de investigación (art. 3.3.g).

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

## 5. Estado de cada campo de cada máster e indicador de transparencia

Para cada máster y cada campo esencial el motor guarda de dónde sale el dato y cuándo se volverá a mirar.
Es lo que decide qué hacer a continuación con ese máster (leer una fuente, pedirlo al centro, esperar).
Programado en `motor/estudios/seguimiento.py`: junta hechos extraídos, medición de la página, fuentes
oficiales y respuestas de los centros, y saca por página el estado de cada campo, el siguiente paso, la
fecha de la próxima comprobación, la lista de campos que hay que pedir al centro y el indicador.

```json
{"oferta": "of-…", "campo": "precio_total",
 "estado": "publicado_ficha | documento_publico | fuente_oficial | facilitado_centro | solo_con_registro | no_publicado | sin_comprobar",
 "valor": 9900, "fuente_url": "…", "cita": "…", "capturado": "2026-10-29",
 "comprobado": "2026-10-29", "proxima_comprobacion": "2026-11-05", "motivo_frecuencia": "admision_abierta"}
```

- `solo_con_registro`: la página tiene el formulario y no da el dato; `no_publicado`: ni formulario ni dato.
- Siguiente paso por estado: `sin_comprobar` → extraer; `solo_con_registro` o `no_publicado` → buscar
  documento público del centro, luego fuente oficial, luego petición al centro (§3.4); `facilitado_centro`
  → pedir actualización antes de la siguiente admisión.
- **Indicador de transparencia** (dato propio que nadie da): qué parte de lo esencial (precio total, plan de
  estudios con créditos, metodología, evaluación, horario, plazas, fechas de admisión, becas, tipo de título
  y quién lo expide) se ve sin dar datos. Se publica con su metodología y fecha, como hecho medido, sin
  juicios. Explica al alumno qué esperar y empuja a los centros a publicar.

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

Solo para escuelas no universitarias que venden a distancia en Andalucía o Castilla-La Mancha, se puede
añadir: «Os lo pedimos también porque la normativa autonómica prevé que esta información figure en la web
junto a la oferta (Decreto 625/2019 de Andalucía; Decreto 40/2026 de Castilla-La Mancha).»

## 9. Estado del barrido (29/10/2026)

**Webs oficiales (340 dominios del RUCT: universidades, centros propios y adscritos, extranjeros
autorizados, otros centros de nivel universitario y Defensa)**, barrido a fondo:

- Responden 293; 47 no responden (webs antiguas del RUCT, institutos del CSIC con tiempo agotado).
- **Vetan nuestro agente en `robots.txt`: Universidad de Sevilla, Universidad de Córdoba**, ico.gencat.cat,
  iesg.es y unibarcelona.com. **La UOC responde 403 a todo**. No se fuerza: se pide permiso (§3.4) y,
  mientras, sus másters salen solo de fuentes oficiales.
- 232 con páginas de programa: 55.899 URL de programa, 36.902 con fecha de última modificación en el
  sitemap (sirven para no volver a descargar lo que no cambia) y 4.698 con el nombre del máster en el
  enlace. 170 verificadas con fichas medidas. Ninguna reserva expresa de minería (TDM).
- En 779 fichas de máster de esas webs: formulario que pide el correo 37 %, teléfono 30 %, importe en
  euros 31 % (habla de precio el 82 %), precio en Schema.org 6 %, asignaturas o módulos 57 %, becas 62 %,
  metodología 39 %, evaluación 29 %, plazas 33 %, guía o folleto en PDF enlazado 19 %.
- **Cada máster oficial con su página**: de 4.347 activos, 1.447 unidos, 628 dudosos (varios centros o
  páginas: revisar) y 2.272 sin página. Faltan sobre todo las grandes públicas con miles de páginas (UB,
  UPM, UC3M, UPV, UAM) y las que vetan el rastreo. En marcha: todas las URL de programa de esos dominios
  en Common Crawl.

**Centros no oficiales, primer barrido** (10.955 candidatos del último índice de Common Crawl): 1.466
con fichas de programa y señal de España, 1.332 tras los filtros de precisión. De 60 revisados a mano al
azar, 47 pasan los filtros y de esos el 77 % (36) son proveedores reales (escuelas de negocio, academias en línea, institutos sanitarios, colegios
profesionales, escuelas de arte y diseño). Estimación: unos 1.000 proveedores reales no oficiales (entre 850 y 1.200 con el margen de una muestra de 47),
con unas 90.000 URL de programa. Lo que se cuela: agregadores y blogs con fichas copiadas, sedes de otros
países y productos con «master» en el nombre. 35 vetan nuestro agente en `robots.txt` y 5 reservan la
minería de datos (TDM): solo se enlazan.

**Segundo barrido, en marcha** (10.462 objetivos): 7.187 candidatos nuevos del índice anterior de Common
Crawl (CC-MAIN-2026-39), 1.589 centros enlazados desde páginas de «colaboradores» de universidades y
escuelas, y los 1.686 verificados del primero con las reglas nuevas.

**Cobertura frente a listas independientes** (53 proveedores conocidos): 49 en el censo y 40 verificados.
Faltan CEF, ThePowerMBA y ESH, que no aparecen en ninguno de los dos índices de Common Crawl: hará falta
una lista de semillas mantenida a mano para los que el índice no ve.

**Fallos encontrados al revisar el barrido y corregidos el mismo día**: se rastreaba el dominio desnudo
(«ub.es») en vez de la web real; las redirecciones a otro dominio (uab.es → uab.cat, ehu.es → ehu.eus)
dejaban sin programas a universidades enteras; `robots.txt` se leía solo del servidor principal; las
páginas sin codificación en la cabecera se leían mal («MÃ¡ster»), lo que rebajaba las cifras de la §1; y
una prueba subió 101 copias de páginas de centros a la rama pública (retiradas; queda purgar el historial).
