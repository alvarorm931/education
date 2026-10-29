# Encargo: módulo de másters

Para la conversación que diseña y construye el módulo de másters en paralelo. Leer antes `docs/contexto-proyecto.md`,
`docs/ley-seo.md` y la sección de másters de `docs/guia.html`.

## Qué está decidido (no reabrir sin motivo)

- **El valor del máster es no tener que registrarse** para saber lo que hoy se esconde tras un formulario.
- Cada ficha (máster × universidad × modalidad) da:
  - asignaturas con créditos y tipo (obligatoria, optativa, prácticas, TFM);
  - **metodología y evaluación** (porcentajes de examen, trabajos, participación);
  - **precio total y por crédito** (y becas);
  - plazas, modalidad (presencial, semipresencial, online), horario y si es compatible con trabajar, idioma;
  - grados que dan acceso y requisitos; plazos de preinscripción;
  - **oficial o título propio**, y si **habilita** para una profesión regulada;
  - empleo de los titulados cuando haya dato.
- **Comparador** por centro y por modalidad (ejemplo de maqueta: máster de profesorado presencial frente a online).
- Estructura de URL con dos padres:
  - `/universidad/{universidad}/master/{master}/` (ficha);
  - `/master/{area}/`, `/master/{area}/{ciudad}/`, `/master/{area}/online/`;
  - `/comparar/master/{area}/{a}-vs-{b}/`.
- Cada ficha recomienda: lo mismo en otros sitios (otra ciudad, online, más barato, público), comparar,
  «¿puedo acceder con mi grado?», «cómo llegar a ser…», becas, guardar en «Mi plan».
- Para carreras se decidió no hacer guías docentes asignatura por asignatura. **En másters sí hace falta la
  metodología y la evaluación**, que solo están en las guías docentes.

## Fuentes verificadas (octubre de 2026)

| Dato | Fuente | Conexión | Estado |
|---|---|---|---|
| Catálogo de títulos y centros | RUCT (Ministerio de Universidades). Código de título de 7 cifras. Ficha: `https://www.educacion.gob.es/ruct/estudio.action?codigoCiclo=SC&codigoTipo=…&CodigoEstudio=…&actual=estudios` | Sin API ni descarga masiva: lectura de la ficha web. Riesgo: cambio de dominio de la sede | Verificada (campos de la ficha por confirmar) |
| Oferta anual de plazas | Excel del Ministerio (`tablaofertaplazas_25_26_ver2.2.xlsx` en ciencia.gob.es) | Descarga anual | Existe; columnas por verificar |
| Asignaturas | Resoluciones del BOE «por la que se publica el plan de estudios de Máster Universitario» (sección III) | Filtro del sumario diario del BOE (ya capturado 2022-2026 en la rama `datos`) | Verificada; detalle heterogéneo, el curso no siempre viene |
| Metodología y evaluación | **Guías docentes**, obligatorias antes de la matrícula (RD 822/2021, art. 9.3). Las memorias de verificación solo traen descripciones generales | Lectura por universidad | Sin fuente central |
| Precio público por crédito | Anuario de precios del Ministerio (XLSX por experimentalidad y comunidad, 2008-09 a 2025-26) y decretos anuales de cada comunidad | Descarga anual + vigilancia de boletines | Verificada. Medias 2024-25: máster habilitante 15,76 €/crédito; no habilitante 30,04 € |
| Precio de privadas | Web de cada universidad (unas 40) | Captura anual | Sin fuente central |
| Plazas, nota, empleo por título | QEDU (exportación CSV/XLSX) | Inestable en la revisión | Por verificar; respaldo SIIU y petición formal |
| Empleo | SIIU afiliación (PC-Axis): por universidad y rama, no por título; cohorte 2019-20 | Descarga | Verificada |
| Habilitantes | Órdenes ministeriales por profesión (profesorado ECI/3858/2007, psicología sanitaria ECD/1070/2013, abogacía, ingenierías CIN/…, arquitectura EDU/2075/2010) y base de profesiones reguladas de la UE | BOE consolidado | Números de orden por verificar en el BOE |
| Datos abiertos de universidades | Murcia (CKAN, 275 datasets), Politécnica de Valencia (ODC-BY), Complutense (Universidata) | Descarga | Verificada |

Notas:
- Los dobles másters no están en el RUCT: necesitan identificador propio.
- Peticiones formales recomendadas (Ley 37/2007): precio por título, afiliación por título y universidad.
- Competencia: Educaweb, Emagister (precio «a consultar», formulario obligatorio), masterMania (cobra unos 25 € por contacto). Nadie enseña metodología y evaluación ni el precio real sin registro.

## Cómo trabajar sin pisar el resto

- Código en `motor/estudios/` (nuevo) y pruebas en `tests/`. No tocar `motor/boe/` ni `motor/autonomicos/` salvo acuerdo.
- Datos en la rama `datos`, bajo `datos/estudios/masters/…`.
- Probar conectores con `prueba.yml` (rama `sondas`). Cuidado con los minutos de GitHub: el motor de oposiciones ya consume.
- Reutilizar: `motor/archivo.py` (originales con huella), `motor/http.py` (descargas educadas), `motor/limpieza.py`
  (sin datos personales), `motor/boe/sumario.py` (el sumario del BOE ya está descargado).
- Catálogo maestro: universidad y centro con código RUCT, título con código RUCT, oferta = título × centro × curso ×
  modalidad con identificador propio, asignaturas con código de la universidad + identificador propio.

## Primer objetivo propuesto

1. Sacar del BOE ya capturado (2022-2026) todas las resoluciones de planes de estudio de máster y medir qué
   proporción trae asignaturas, créditos y curso.
2. Probar la lectura de fichas del RUCT desde GitHub (sonda) y documentar sus campos reales.
3. Elegir 3 universidades piloto (una pública grande, una privada, una con datos abiertos) y medir dónde están la
   metodología, la evaluación y el precio en sus guías y webs.
4. Proponer el esquema de la ficha de máster con la ley SEO aplicada y los datos mínimos para indexar.
