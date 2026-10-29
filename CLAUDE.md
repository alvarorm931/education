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
- Rama `datos`: resultados del motor en la fase de pruebas (se moverán a R2).
