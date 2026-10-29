# La ley del proyecto: SEO y buscadores con IA

Lo que penaliza se descarta. Lo que favorece es norma. Cada regla con su fuente oficial.
Revisión mensual de la documentación oficial; si cambia una regla, se cambia el control y se aplica a todas las páginas en la siguiente publicación.

Última revisión: 29/10/2026.

## Reglas de oro

### Contenido
1. Cada página indexable aporta datos propios que no están juntos en otro sitio. [Google: contenido útil](https://developers.google.com/search/docs/fundamentals/creating-helpful-content)
2. Cada dato con su fuente y su fecha. La fecha solo cambia si cambia el dato. [Google: contenido útil](https://developers.google.com/search/docs/fundamentals/creating-helpful-content) · [Google: sitemaps](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)
3. Página de metodología: quién hace la web, de dónde salen los datos, qué hace la automatización y qué se revisa a mano. [Google: quién, cómo y por qué](https://developers.google.com/search/docs/fundamentals/creating-helpful-content)
4. El texto escrito con IA se revisa antes de publicarse, incluidos títulos, descripciones, datos estructurados y textos alternativos. [Google: contenido con IA](https://developers.google.com/search/docs/fundamentals/using-gen-ai-content)
5. Sin número mínimo de palabras. [Google: contenido útil](https://developers.google.com/search/docs/fundamentals/creating-helpful-content)

### Técnica
6. Todo el contenido en el HTML servido; JavaScript solo para herramientas. [Google: JavaScript](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics)
7. Enlaces como `<a href>` con rutas reales, nunca con almohadillas. [Google: JavaScript](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics)
8. Core Web Vitals en verde: LCP ≤ 2,5 s, INP < 200 ms, CLS < 0,1. [Google: Core Web Vitals](https://developers.google.com/search/docs/appearance/core-web-vitals)
9. Una sola versión del dominio, HTTPS, canónica en cada página, redirección 301 si una dirección cambia.

### Rastreo e indexación
10. Página sin datos suficientes: `noindex` en el HTML original, nunca con JavaScript. [Google: JavaScript](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics)
11. Sitemaps por sección, máximo 50.000 URL o 50 MB, con `lastmod` real. `changefreq` y `priority` no se usan (Google los ignora). [Google: sitemaps](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)
12. Toda página indexable recibe enlaces internos desde su lugar y su categoría. [Google: funciones de IA](https://developers.google.com/search/docs/appearance/ai-features)
13. Search Console y Bing Webmaster Tools desde el primer día; IndexNow en cada publicación. [Bing: IndexNow](https://blogs.bing.com/webmaster/november-2021/Cloudflare-Supports-IndexNow-via-one-click-Integration)

### Buscadores con IA
14. Para AI Overviews y AI Mode no hace falta nada especial: estar indexado y con fragmento. Ni archivos para IA ni marcado especial. [Google: funciones de IA](https://developers.google.com/search/docs/appearance/ai-features)
15. Permitidos: Googlebot, Bingbot, OAI-SearchBot, Claude-SearchBot y los agentes de usuario (ChatGPT-User, Claude-User). [OpenAI](https://developers.openai.com/docs/gptbot) · [Anthropic](https://support.claude.com/en/articles/8896518)
16. Robots de entrenamiento permitidos: bloquearlos no trae tráfico y en Cloudflare puede bloquear a Googlebot. [Cloudflare y Googlebot](https://searchenginejournal.com/cloudflares-ai-crawler-rules-can-block-googlebot/581385)
17. Datos estructurados solo con lo visible en la página. JobPosting solo en la ficha de un proceso con plazo abierto y una única convocatoria, nunca en listados. [Google: JobPosting](https://developers.google.com/search/docs/appearance/structured-data/job-posting)

### Configuración fija de Cloudflare
18. Buscadores, agentes y entrenamiento: permitidos. "Block AI bots": desactivado. Modos anti-robots: desactivados. IndexNow (Crawler Hints): activado.
19. Plan B de alojamiento: Bunny CDN (la web son archivos estáticos; mudanza en un día).

## Prohibido siempre

| Práctica | Motivo | Fuente |
|---|---|---|
| Páginas en masa sin valor | Abuso de contenido a escala | [Spam policies](https://developers.google.com/search/docs/essentials/spam-policies) |
| Páginas casi iguales por pueblo o variante | Páginas puerta | [Spam policies](https://developers.google.com/search/docs/essentials/spam-policies) |
| Dominio caducado comprado por su historial | Abuso de dominios caducados | [Spam policies](https://developers.google.com/search/docs/essentials/spam-policies) |
| Copiar textos de otras webs | Contenido copiado | [Spam policies](https://developers.google.com/search/docs/essentials/spam-policies) |
| Contenido distinto para Google y para el usuario, texto oculto, relleno de palabras clave | Encubrimiento, texto oculto, keyword stuffing | [Spam policies](https://developers.google.com/search/docs/essentials/spam-policies) |
| Comprar o intercambiar enlaces | Spam de enlaces | [Spam policies](https://developers.google.com/search/docs/essentials/spam-policies) |
| Cambiar fechas sin cambiar el dato | Contenido para buscadores; Google deja de fiarse del lastmod | [Contenido útil](https://developers.google.com/search/docs/fundamentals/creating-helpful-content) |
| Ventanas que tapan el contenido al entrar | Ventanas intrusivas | [Interstitials](https://developers.google.com/search/docs/appearance/avoid-intrusive-interstitials) |
| Contenido solo con JavaScript; noindex con JavaScript | Google puede no verlo; los robots de IA no ejecutan JS | [JavaScript](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics) |
| Bloquear robots de búsqueda; "Block AI bots" | Desaparecer de Google, ChatGPT o Claude | [Cloudflare](https://searchenginejournal.com/cloudflares-ai-crawler-rules-can-block-googlebot/581385) |
| Web de pruebas sin contraseña | Contenido duplicado indexado | — |

## Control automático de cada página

| Comprobación | Si falla |
|---|---|
| Datos mínimos de su tipo (proceso: convocante, plazas, plazo y fuente; lugar: al menos un proceso; máster: asignaturas y precio) | Se publica con `noindex` |
| Similitud de texto con otra página del sitio por encima del umbral (propio, a calibrar) | `noindex` o fusión |
| Contenido principal presente en el HTML sin ejecutar JavaScript | No se publica |
| Fuente y fecha visibles en cada dato clave | No se publica |
| Título y descripción únicos en el sitio y sin huecos de plantilla | No se publica |
| HTTP 200, canónica a sí misma, al menos un enlace interno entrante | No se publica |
| Enlaces internos sin rotos | No se publica |
| Datos estructurados válidos y coincidentes con lo visible | Se publica sin marcado |
| Ninguna ventana al cargar | No se publica |
| Texto con IA aprobado en revisión | No se publica |
| Velocidad por plantilla en laboratorio: LCP ≤ 2,5 s, CLS < 0,1 | No se publica la plantilla |

Comprobaciones diarias: robots.txt y Cloudflare permiten los robots de búsqueda; Search Console y Bing sin errores de rastreo en aumento; datos reales de velocidad en verde. Si algo falla, alerta.
