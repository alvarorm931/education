# Proyecto education

Portal abierto, en un solo dominio .es, con dos secciones: estudios (carreras, másters, FP, notas de corte con calculadora) y oposiciones (todas las convocatorias de España). Información siempre abierta: nunca se pide registro ni correo para ver nada. El correo es opcional y solo para avisos.

La guía completa está en `docs/guia.html` y la ley SEO en `docs/ley-seo.md`.
Contexto para conversaciones nuevas: `docs/contexto-proyecto.md`. Encargos en paralelo: `docs/encargo-*.md`
(cada encargo trabaja en su propia carpeta de `motor/` y no toca las de otros sin acuerdo).

## La ley del proyecto (obligatoria)

Todo está enfocado a tráfico orgánico desde Google y desde buscadores con IA.

- Lo que penaliza en Google o en las IA se descarta siempre, aunque sea cómodo o dé dinero.
- Lo que favorece se aplica como norma en todas las páginas.
- Cada regla sale de documentación oficial (Google Search Central, Bing, OpenAI, Anthropic), nunca de mitos del sector.
- Ninguna página se publica sin pasar el control automático descrito en `docs/ley-seo.md`.

Antes de proponer o programar cualquier cosa que llegue a una página pública (plantillas, anuncios, avisos, scripts, nuevas secciones), comprobar `docs/ley-seo.md`.
El control está programado en `motor/seo/` (`python -m motor.seo.control`); el contrato que tiene que cumplir el generador de páginas, en `docs/encargo-seo.md`.

## Reglas de datos

- Cada dato publicado lleva fuente, URL y fecha de captura. La fecha solo cambia si cambia el dato.
- Los originales descargados se guardan intactos con su huella sha256 y no se borran.
- Nunca se guardan ni publican datos personales de las listas de admitidos o aprobados: solo se cuentan.
- Licencia BOE: citar "Fuente: Agencia Estatal Boletín Oficial del Estado", indicar fecha de actualización y no aparentar carácter oficial.
- Peticiones a las fuentes moderadas, identificadas y solo de lo nuevo.

## Entorno

- El espacio de trabajo de Claude no tiene acceso a boe.es ni a los boletines. El motor se ejecuta en GitHub Actions (y más adelante en un servidor propio). Las pruebas locales usan ficheros de ejemplo en `tests/fixtures/`.
- Python 3.12+. Dependencias mínimas (`pyproject.toml`).
- Claves y tokens solo como secretos de GitHub, nunca en el código ni en el chat.

## Estructura

- `motor/` código del motor (conectores, archivo de originales, extracción).
- `fuentes/registro.yaml` registro de fuentes: dirección, método, frecuencia, licencia, respaldo y estado.
- `tests/` pruebas.
- Rama `datos`: resultados del motor en la fase de pruebas. Originales completos: almacén S3 privado (ver abajo).
- Rama `vigilancia`: estado de la infraestructura cada 30 minutos (`ultimo.md`, `ultimo.json`), escrito por `vigilante.yml`.

## Infraestructura e incidencias (obligatorio para todas las conversaciones)

- La infraestructura (AWS, servidor `motor-espana`, almacén S3, permisos, secretos y ajustes de GitHub) la lleva
  la conversación de estado. Está descrita en el documento del proyecto `claude/infraestructura.md`: léelo antes de
  usar AWS, el servidor o el almacén.
- Si algo de infraestructura falla, **no lo arregles por tu cuenta ni se lo pidas a Álvaro**: apúntalo en el buzón
  `claude/incidencias.md` del proyecto (léelo justo antes de escribir y conserva lo que haya), con el error literal,
  el enlace a la ejecución y lo que ya probaste. La conversación de estado lo revisa y anota la solución.
- Antes de reintentar algo que falló, mira el buzón y `git show origin/vigilancia:ultimo.md`: puede estar ya
  resuelto o relanzado. El vigilante relanza una vez los fallos pasajeros (red, tiempo agotado, choque al subir).
- GitHub no está disparando las programaciones (`schedule`) de este repositorio: el vigilante lanza a mano las diarias.
  Una programación nueva tiene que ser diaria («M H * * *») y el flujo tener `workflow_dispatch` con entradas por defecto.
- Los fallos de tu propio módulo los arreglas tú, como siempre.
