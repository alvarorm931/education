# Contexto del proyecto (para cualquier conversación nueva)

Actualizado: 29/10/2026. Léelo entero antes de proponer nada.

## Quién y qué

- Promotor: Álvaro (finanzas, Madrid). Proyecto personal, al margen de su empresa. Trabaja con Claude como equipo técnico.
- Producto: portal abierto en **un solo dominio .es** (nombre por decidir) con dos secciones:
  - **Estudios**: carreras (todas las asignaturas de cada grado en cada universidad), másters, FP, notas de corte con calculadora.
  - **Oposiciones**: todas las convocatorias de España, del archivero de un pueblo a la Policía, con su historia completa.
- Modelo: SEO programático (miles de páginas, una por búsqueda real) al estilo de convenioslaborales.com por detrás, con aspecto propio. Tráfico orgánico de Google y de buscadores con IA.
- Reglas de producto:
  - **La información siempre abierta.** Nunca se pide registro ni correo para ver nada.
  - El correo es opcional y solo para avisos y para sincronizar «Mi plan». Nunca se cede.
  - Enlace a la web oficial de cada centro desde el primer día; inscripción y contactos voluntarios, más adelante.
  - Cursos propios: futuro lejano, separados de la información.

## La ley del proyecto (obligatoria)

Ver `docs/ley-seo.md`. Lo que penaliza en Google o en las IA se descarta siempre; lo que favorece es norma.
Cada regla sale de documentación oficial. Ninguna página se publica sin pasar el control automático.
Resumen: contenido en el HTML (sin depender de JavaScript), datos propios en cada página indexable, páginas sin
datos con noindex, nada de páginas puerta ni contenido en masa sin valor, fuente y fecha en cada dato, sin
ventanas al entrar, Core Web Vitals en verde, robots de búsqueda y de IA permitidos.

## Reglas de datos

- Cada dato publicado lleva fuente, URL y fecha de captura. La fecha solo cambia si cambia el dato.
- Los originales se guardan intactos con huella sha256. **Mientras el repositorio sea público**, de los originales de
  boletines solo se guarda la huella, la URL, el tamaño y la fecha (`archivo/indices/`), porque traen datos de
  personas; el contenido irá a un almacén privado (R2) cuando exista (`MOTOR_ORIGINALES=completo`).
- Nunca se guardan ni publican datos de personas (listas de admitidos, aprobados, nombramientos): solo recuentos.
  Párrafos con un documento de identidad o con un nombre precedido de tratamiento («don», «D.ª», «Sra.») se retiran
  y se cuentan; en los títulos el nombre se sustituye por «[persona]». Ver `motor/limpieza.py`. Las ramas `datos` y
  `sondas` son públicas: las sondas y pruebas se anonimizan antes de subir (`motor/mantenimiento/anonimizar.py`).
- Peticiones a las fuentes moderadas (alrededor de una por segundo), identificadas y solo de lo nuevo.
- Licencias: citar la fuente (BOE, ministerios, CC BY de comunidades) e indicar fecha de actualización.

## Estado técnico

- Repositorio **público** `alvarorm931/education` (comprobado por la API el 29/10/2026). Código en `motor/`, pruebas
  en `tests/`, documentación en `docs/`.
- Datos en la rama `datos` (no mezclar con `main`). Pruebas de conectores y sondas en la rama `sondas`.
- Ejecución en GitHub Actions: `motor.yml` (BOE, extracción y procesos) dos veces al día; `autonomicos.yml`
  (un trabajo por boletín autonómico o provincial, en paralelo, `infra/autonomicos.sh`) una vez al día;
  `mantenimiento.yml`, `prueba.yml` y `sonda.yml` bajo demanda. `extraccion.yml` es el único flujo que recibe el
  secreto `ANTHROPIC_API_KEY` (solo en el paso que llama a la API): tanda de prueba de la extracción de fichas de
  másters con Claude Haiku en lote (`motor/ia/prueba_extraccion.py`). Haiku 5.5 razona por defecto y ese
  razonamiento cuenta dentro de `max_tokens`: para extraer datos con cita se envía `thinking: {"type": "disabled"}`. En repositorios públicos los ejecutores estándar no
  consumen minutos de pago (docs.github.com, «GitHub Actions billing»); límites: 6 horas por trabajo y 20 trabajos
  a la vez en el plan gratuito.
- robots.txt: `motor/http.py` lee el de cada servidor y no pide lo que prohíbe (RFC 9309, con comodines,
  `motor/robots.py`). Dos excepciones, y solo en sus direcciones: servicios de datos documentados para uso por
  programa, con cita (`EXCEPCIONES_ROBOTS`, Common Crawl), y boletines oficiales (`BOLETINES_OFICIALES`: BOCYL, DOGC,
  BOIB, DOCM y los BOP de Barcelona, Alicante, A Coruña, Pontevedra, Ciudad Real y Toledo), por decisión de Álvaro
  del 30/10/2026: sus actos no son objeto de propiedad intelectual (TRLPI, art. 13) y son reutilizables (Ley
  37/2007, art. 4.1). Las webs de centros de estudios siguen siempre con su robots.txt. Auditoría:
  `motor/robots_auditoria.py` sobre `fuentes/urls_ejemplo.json`. El BOE se lee en HTML (`txt.php`) y el BOCM por su
  boletín completo en HTML, permitidos y equivalentes (`claude/robots-txt-motor.md` en el proyecto).
- El espacio de trabajo de Claude no llega a las webs de las fuentes: todo se prueba desde GitHub (sondas y pruebas;
  `python -m motor.autonomicos.humo` prueba los conectores autonómicos contra las fuentes reales).
- 16 boletines bloquean a GitHub (servidores fuera de España). Se está creando un servidor en AWS región España
  (Lightsail) como ejecutor de GitHub (`infra/arranque-servidor.sh`).
- Hecho: BOE 2022-2026 completo (1.525 boletines, 341.298 disposiciones, 51.855 anuncios de oposiciones),
  textos de anuncios en descarga, registro de 62 boletines.
- Conectores autonómicos (`motor/autonomicos/`, 14): BOJA, BOCM, BOCYL, DOGV, DOG, DOGC, BOA, DOE, BOIB, BORM,
  BOC, BOPV, DOCM y BOME, con piezas comunes en `comun.py`. Faltan Asturias, Navarra, Cantabria, La Rioja y Ceuta
  (bloquean a GitHub). Provinciales (`motor/provinciales/`, 10): Barcelona y Tarragona (plataforma común `diba.py`), Valencia
  (portal JSF con sesión), Alicante (servicio JSON), Ciudad Real, Granada, Sevilla y Huesca (plataforma común
  `saga.py`), Santa Cruz de Tenerife y Córdoba. Siguientes por número de bases citadas en el BOE: Málaga (bloquea a
  GitHub), Badajoz, Bizkaia, A Coruña, Zaragoza, Toledo, Castellón, Pontevedra, Cáceres.
- Selección por título en los BOP sin sección de personal (`es_empleo_estricto` en `motor/autonomicos/comun.py`):
  expresión inequívoca, o puesto con nombre y trámite de selección, menos asuntos ajenos; revisada sobre 55.368
  títulos reales (`tests/test_empleo_estricto.py`). Las expresiones que solo se usan en selección mandan sobre las
  exclusiones por tema («técnico de comercio», «jefe de sección de urbanismo»). Intermedios TLS que faltan en algunos servidores: `motor/certificados/`.
- Vigilancia: `motor/estado.py` escribe `datos/estado.json` (por fuente: último boletín leído, días hábiles sin
  noticias, errores, huecos en la numeración de los boletines) y avisa si una lleva más de 3 días hábiles parada.
  Los huecos de numeración destaparon boletines que no se leían: extraordinarios del BOC, números del BOA y del DOG
  en sábado o domingo, extraordinarios del BOCM (ahora se leen de su boletín completo en HTML). Todos los conectores paran tras 8 fallos
  seguidos y lo reintentan en la siguiente ejecución.
- Catálogo territorial (`motor/catalogo/territorio.py`): 52 provincias y 8.132 municipios del INE (2026); cada
  proceso lleva provincia, comunidad y código INE del convocante cuando es inequívoco.
- Extracción sin IA (`motor/extraccion/`): plazo de solicitudes (`plazo.py`) y plazas (`plazas.py`) en castellano,
  catalán/valenciano y gallego; boletines citados con comillas, sin ellas o por siglas. Plantilla de anuncios locales
  del BOE en `motor/boe/extraer.py`.
- Procesos (`motor/procesos.py`): une BOE y boletines autonómicos y provinciales (misma convocatoria = un proceso;
  bases locales enlazadas al anuncio del BOE que las cita por código INE o nombre; bases locales sin anuncio en el
  BOE, como bolsas y contratos temporales, forman su propio proceso).

## Documentos clave

- `docs/guia.html`: guía completa del proyecto (propósito, alcance, valor, estructura de URL, fuentes, catálogo
  maestro, tecnología y costes, maquetas, fases).
- `docs/ley-seo.md`: reglas SEO y control de cada página.
- `docs/modelo-oposiciones.md`: modelo de datos de oposiciones (capturas, actos, procesos, resultados).
- `fuentes/registro.yaml` y `fuentes/boletines.yaml`: fuentes verificadas y estado de cada boletín.

## Forma de trabajar con Álvaro

- Español. Máximo rigor: verificar antes de afirmar, decir lo que no está verificado, no inventar.
- Quiere valor nuevo y profundo, no ideas repetidas ni triviales.
- Al terminar cada pieza: ¿lo puedo hacer mejor?, ¿aporta el valor que queremos?, ¿puedo aportar más?
- Claude no crea cuentas ni maneja contraseñas o claves: Álvaro las crea y las guarda como secretos de GitHub.
- Commits terminados con las líneas de atribución que indique la sesión.
