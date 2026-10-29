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
- Los originales se guardan intactos con huella sha256 (hoy en la rama `datos`; pasarán a un almacén externo).
- Nunca se guardan ni publican datos de personas (listas de admitidos, aprobados): solo recuentos. Ver `motor/limpieza.py`.
- Peticiones a las fuentes moderadas (alrededor de una por segundo), identificadas y solo de lo nuevo.
- Licencias: citar la fuente (BOE, ministerios, CC BY de comunidades) e indicar fecha de actualización.

## Estado técnico

- Repositorio privado `alvarorm931/education`. Código en `motor/`, pruebas en `tests/`, documentación en `docs/`.
- Datos en la rama `datos` (no mezclar con `main`). Pruebas de conectores y sondas en la rama `sondas`.
- Ejecución en GitHub Actions: `motor.yml` dos veces al día; `prueba.yml` y `sonda.yml` bajo demanda.
  GitHub Free: 2.000 minutos al mes en repositorios privados. Vigilar el consumo.
- El espacio de trabajo de Claude no llega a las webs de las fuentes: todo se prueba desde GitHub (sondas y pruebas).
- 16 boletines bloquean a GitHub (servidores fuera de España). Se está creando un servidor en AWS región España
  (Lightsail) como ejecutor de GitHub (`infra/arranque-servidor.sh`).
- Hecho: BOE 2022-2026 completo (1.525 boletines, 341.298 disposiciones, 51.855 anuncios de oposiciones),
  textos de anuncios en descarga, extractor de anuncios locales, conector BOJA (Andalucía), registro de 62 boletines.

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
