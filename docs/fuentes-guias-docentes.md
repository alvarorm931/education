# Guías docentes de máster: dónde y cómo las publica cada universidad

Revisado el 29/10/2026 en 29 públicas y 13 privadas. «Sí» = guía de máster abierta y contenido visto.
La guía es obligatoria antes de la matrícula (RD 822/2021, art. 9.3) y es la fuente de metodología y
evaluación por asignatura cuando la memoria del RUCT no la trae (formato RD 822/2021).

## Plataformas

**SIGMA DOA (única plataforma compartida).** UAM, Zaragoza, UPF, Deusto y UCAM verificadas; CEU San Pablo,
CEU Cardenal Herrera, Abat Oliba CEU, Coruña y EUG vistas en búsqueda; Blanquerna probable. Patrón:
`https://{host}/doa/consultaPublica/look[conpub]MostrarPubGuiaDocAs?entradaPublica=true&idiomaPais=es.ES&_anoAcademico={año}&_codAsignatura={código}`;
listado por plan con `BuscarPubGuiaDocAs?...&_centro={c}&_planEstudio={p}`. Carga el contenido con
JavaScript. Zaragoza deja además PDF estáticos (`sia.unizar.es/documentos/doa/guiadocente/{año}/{código}_es.pdf`,
comprobado); en UAM, Deusto y UCAM esa ruta no existe (404, sonda del 29/10/2026). Además, `robots.txt` de
`laurea.ucam.edu` y `gaude.deusto.es` prohíbe todo a cualquier robot (`Disallow: /`): sus guías no se leen
automáticamente sin permiso expreso; la UAM no tiene `robots.txt` en ese servidor.

**Aplicaciones propias con URL predecible (código + curso + idioma):**

| Universidad | Patrón | Contenido verificado |
|---|---|---|
| Valencia | `uv.es/recursos/fatwirepub/guias/{cód}-{CAS/VAL/ANG}-{AAAA-AA}.pdf` | evaluación 50/25/25 % |
| Politécnica de Madrid | `upm.es/comun_gauss/publico/guias/{AAAA-AA}/GA_{plan}_{cód}_ES_{AAAA-AA}.pdf` | evaluación 50/50 % |
| Valladolid | `apps.stic.uva.es/guias_docentes/uploads/{AAAA}/{plan}/{cód}/{n}/Documento.pdf` | evaluación 60/25/15 % |
| UNED | `uned.es/universidad/pdf/GuiasAsignaturasMaster/PDFGuiaPublica?codigoAsignatura=&curso={año fin}&codigoTitulacion=&language=es` | evaluación 45/30/25 % |
| Rey Juan Carlos | `servicios.urjc.es/guiasdocentes/pdfGuia.jsp?txtAsignatura=&txtTitulacion=&txtCursoAcademico={AAAA-AA}` | evaluación 80/20 % |
| Murcia | `api.um.es/aulavirtual/guiasdocentes-api/public/v1/guias/{cód}/P/{AAAA}/E/pdf` (API) | evaluación 60/40 % |
| Politècnica de Catalunya | `upc.edu/estudispdf/guia_docent.php?codi={cód}&lang={ca/es/en}` | evaluación con % |
| Navarra | `asignatura.unav.edu/{SIGLA}-{cód}-{2627}.pdf` | evaluación 70/10/20 % |
| Francisco de Vitoria | `notas.ufv.es/documentos/gd/postgrado/{cód}_{s/p}.pdf` | evaluación por bloques |
| Europea de Madrid | `universidadeuropea.com/myfiles/pr/{programa}{NNN}.pdf` | evaluación 60/15/10/15 % |
| Córdoba, Málaga, Las Palmas, Cádiz | patrones vistos en búsqueda | no verificado |

**Aplicaciones propias en HTML:** Complutense (`{centro}.ucm.es/estudios/{curso}/master-{slug}-plan-{cód}`,
evaluación con %), Carlos III (`aplicaciones.uc3m.es/cpa/generaFicha?...`), UAB
(`apps.uab.cat/guies/public/html/{año}/assignatura/{cód}/es`), Granada (Drupal con PDF firmado), EHU
(Liferay, evaluación en rangos), La Laguna (`ull.es/apps/guias/guias/view_guide/{id}`), UNIR (HTML estático),
Sevilla (PDF de SEVIUS, sin % en la muestra), Alicante (en parte dinámica).

**Con JavaScript (navegador sin interfaz):** Barcelona (`ub.edu/pladocent`), UOC (`apps.uoc.edu/PlaDocent`),
SIGMA DOA y parte de Alicante.

**PDF conjuntos o con nombre libre (rastreo de enlaces):** Salamanca, Oviedo, parte de la Complutense y la
EHU, Santiago, UPF-BSM, VIU, UDIMA, Nebrija. Camilo José Cela, en Blackboard (probablemente con acceso).

## Consecuencias para el conector

- El año se codifica de cuatro maneras (inicio, fin, «AAAA-AA», «2627»).
- La evaluación puede ser fija o en rangos: el modelo guarda mínimo y máximo.
- TFM y prácticas suelen ir sin porcentajes.
- Varias rutas están vetadas en `robots.txt` para algunos agentes (UPC /content/master, Málaga, Córdoba, Las
  Palmas, Castilla-La Mancha, Politècnica de València, Comillas, Deusto, UCAM, Coruña, CEU San Pablo, Vigo).
  Se respeta lo que diga para nuestro agente; donde esté vetado, se pide permiso a la universidad.
- Orden de trabajo: primero SIGMA DOA (12 universidades con un conector), después las de URL predecible.
