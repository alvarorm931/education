# Fichas de grado (conversación de grados)

Salida de `motor/grados/fichas.py`, `relaciones.py` y `universidades.py` con lo capturado hasta la fecha de la
carpeta. Solo hechos con su fuente, URL y fecha de captura; ningún texto de terceros ni dato personal.

| Fichero | Qué es |
|---|---|
| `fichas.jsonl` | una ficha por grado o doble grado activo (título × universidad): centros con nota de corte, plazas, precio e inserción (QEDU); precio de la norma de su comunidad donde QEDU no lo da y la norma no depende del título (`precio_credito_norma`), plan del BOE con su comprobación, ficha del RUCT, indicadores del SIIU, precio de las privadas (su web o su lista de precios), bonificaciones de la comunidad, `indexable` y `motivos_noindex` |
| `comparativa.jsonl` | por grado genérico con página: una fila por título × centro con las columnas del comparador y las asignaturas comunes |
| `relaciones.jsonl` | por genérico: carreras parecidas (con motivos), dobles grados que lo incluyen y grados que forman cada doble |
| `asignaturas_indice.jsonl` | buscador por asignatura: dónde se estudia cada una (solo planes comprobados, nivel asignatura) |
| `universidades.jsonl` | datos de cada universidad para su página |
| `*_resumen.json` | recuentos |

Modelo y reglas: `docs/modelo-grados.md` (rama `main`).
