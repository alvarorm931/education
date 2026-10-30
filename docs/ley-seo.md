# La ley del proyecto: SEO y buscadores con IA

Lo que penaliza se descarta. Lo que favorece es norma. Cada regla con su fuente oficial.
Revisión mensual de la documentación oficial; si cambia una regla, se cambia el control (`motor/seo/`) y se aplica a todas las páginas en la siguiente publicación.

Última revisión: 30/10/2026, contra la documentación publicada ese día (cambios respecto al 29/10 al final).
Responsable: la conversación SEO (`docs/encargo-seo.md`).

## Reglas de oro

### Contenido
1. Cada página indexable aporta datos propios que no están juntos en otro sitio. Muchas páginas no hacen mejor un sitio: «a high quantity of pages doesn't make a website higher quality». [Google: contenido útil](https://developers.google.com/search/docs/fundamentals/creating-helpful-content) · [Google: guía de optimización para IA](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide)
2. Cada dato con su fuente y su fecha. La fecha visible y el `lastmod` solo cambian con un cambio significativo: los datos, el contenido principal, los datos estructurados o los enlaces. Google usa el `lastmod` solo si es «consistently and verifiably» exacto, y Bing lo trata como señal clave. [Google: contenido útil](https://developers.google.com/search/docs/fundamentals/creating-helpful-content) · [Google: sitemaps](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap) · [Bing: sitemaps y búsqueda con IA](https://blogs.bing.com/webmaster/2025/7/Keeping-Content-Discoverable-with-Sitemaps-in-AI-Powered-Search/)
3. Página de metodología: quién hace la web, de dónde salen los datos, qué hace la automatización y qué se revisa a mano. Autoría visible (Google la recomienda) y nunca perfiles de autor inventados. [Google: quién, cómo y por qué](https://developers.google.com/search/docs/fundamentals/creating-helpful-content)
4. El texto escrito con IA se revisa antes de publicarse, incluidos títulos, descripciones, datos estructurados y textos alternativos. [Google: contenido con IA](https://developers.google.com/search/docs/fundamentals/using-gen-ai-content)
5. Sin número mínimo de palabras. [Google: contenido útil](https://developers.google.com/search/docs/fundamentals/creating-helpful-content)
6. Títulos que no sean pura plantilla: Google trata como malo un título largo que solo cambia en un dato. Las descripciones generadas desde la base de datos están permitidas, cada una distinta. [Google: títulos](https://developers.google.com/search/docs/appearance/title-link) · [Google: descripciones](https://developers.google.com/search/docs/appearance/snippet)

### Técnica
7. Todo el contenido en el HTML servido; JavaScript solo para herramientas. JavaScript no cambia la canónica ni las directivas de robots. [Google: JavaScript](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics) Las secciones de cada ficha se ven en la página: nada de datos clave en pestañas o paneles cerrados, ni solo en PDF o en imágenes (Microsoft advierte de que sus sistemas de IA pueden no verlos). [Microsoft: contenido para respuestas con IA](https://about.ads.microsoft.com/en/blog/post/october-2025/optimizing-your-content-for-inclusion-in-ai-search-answers)
8. Enlaces como `<a href>` con rutas reales, nunca con almohadillas. [Google: JavaScript](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics)
9. Core Web Vitals en verde en el percentil 75 de los datos reales, en móvil y en ordenador: LCP ≤ 2,5 s, INP ≤ 200 ms, CLS ≤ 0,1 (Search Central escribe «menos de»; web.dev y PageSpeed, «o menos»: el control usa el más estricto donde se puede). [Google: Core Web Vitals](https://developers.google.com/search/docs/appearance/core-web-vitals) · [web.dev](https://web.dev/articles/vitals)
10. Cada página pesa como mucho 2 MB de HTML sin comprimir: Googlebot deja de leer ahí y lo que sigue no se indexa. Los listados largos se parten. [Google: Googlebot](https://developers.google.com/search/docs/crawling-indexing/googlebot)
11. Una sola versión del dominio (https, sin www), canónica en cada página a sí misma, redirección permanente en el servidor (301 o 308) si una dirección cambia, mantenida al menos un año. En Cloudflare, `_redirects` usa 302 si no se escribe el código: se escribe siempre 301. [Google: redirecciones](https://developers.google.com/search/docs/crawling-indexing/301-redirects) · [Google: cambio de dirección](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes) · [Cloudflare: redirecciones](https://developers.cloudflare.com/workers/static-assets/redirects/)
12. Direcciones con los nombres que busca la gente, en minúsculas, con guiones, sin tildes ni códigos, terminadas en barra, y los enlaces internos a esa forma exacta (Cloudflare redirige la otra con un 307). [Google: estructura de URL](https://developers.google.com/search/docs/crawling-indexing/url-structure) · [Cloudflare: HTML y barra final](https://developers.cloudflare.com/workers/static-assets/routing/advanced/html-handling/)
13. Página que se retira: 404 o 410, nunca redirigida a la portada ni respondida con 200 (soft 404). Respuestas 304 a las peticiones condicionales. [Google: presupuesto de rastreo](https://developers.google.com/crawling/docs/crawl-budget)
14. Portada con el marcado `WebSite` (`name` y `url`) para el nombre del sitio en Google, y un icono cuadrado en PNG o ICO (Google no admite SVG), de 48 × 48 o más. [Google: nombre del sitio](https://developers.google.com/search/docs/appearance/site-names) · [Google: icono](https://developers.google.com/search/docs/appearance/favicon-in-search)

### Rastreo e indexación
15. Página sin datos suficientes: `noindex` en el HTML original, nunca con JavaScript. Las páginas `noindex` también gastan rastreo (Google las sigue descargando): si son muchas, no se generan hasta tener datos. El sitio entra en la guía del presupuesto de rastreo (más de 10.000 páginas que cambian a diario). Ojo: Google lee las metaetiquetas de robots también en el cuerpo de la página. [Google: JavaScript](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics) · [Google: presupuesto de rastreo](https://developers.google.com/crawling/docs/crawl-budget) · [Google: robots meta](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag)
16. Sitemaps por sección en la raíz, máximo 50.000 URL o 50 MB cada uno, con `lastmod` real, en un índice (hasta 50.000 sitemaps por índice). `changefreq` y `priority` no se usan (Google y Bing los ignoran). El aviso por «ping» ya no existe: el sitemap se declara en robots.txt y en Search Console. [Google: sitemaps](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap) · [Google: sitemaps grandes](https://developers.google.com/search/docs/crawling-indexing/sitemaps/large-sitemaps)
17. Toda página indexable recibe enlaces internos desde su lugar y su categoría. [Google: funciones de IA](https://developers.google.com/search/docs/appearance/ai-features) Listados largos paginados: cada página con su dirección, su canónica a sí misma (nunca a la primera) y un `<a href>` a la siguiente. Ordenar y filtrar no crea direcciones (o lo hace con almohadilla, que no se rastrea); solo tienen dirección propia las combinaciones con oferta suficiente, y una combinación sin resultados responde 404. [Google: paginación](https://developers.google.com/search/docs/specialty/ecommerce/pagination-and-incremental-page-loading) · [Google: facetas](https://developers.google.com/crawling/docs/faceted-navigation)
18. Search Console y Bing Webmaster Tools desde el primer día (Bing puede importar el sitio desde Search Console, ya verificado). En cada publicación, IndexNow con lo nuevo, lo cambiado y lo retirado (tandas de 10.000 como máximo; clave en la raíz; llega a Bing, Yandex, Seznam, Naver, Yep y Amazon; Google no participa). Para las fichas de procesos con `JobPosting`, la Indexing API de Google (solo admite esas páginas; 200 avisos al día). [Bing: importar](https://blogs.bing.com/webmaster/2019/9/Import-sites-from-Search-Console-to-Bing-Webmaster-Tools/) · [IndexNow](https://www.indexnow.org/documentation) · [Google: Indexing API](https://developers.google.com/search/apis/indexing-api/v3/using-api) Al publicar la sección de oposiciones, pedir a Google por su formulario el carrusel y el filtro de «sitios de empleo» del Espacio Económico Europeo (no necesita marcado). [Google: sitios de empleo](https://developers.google.com/search/docs/appearance/job-sites)

### Buscadores con IA
19. Para AI Overviews y AI Mode no hace falta nada especial: estar indexado y con fragmento. Ni archivos para IA (Google ignora `llms.txt`) ni marcado especial. En Search Console, «Ajustes › IA generativa en la Búsqueda» en «Incluir» (es lo que viene por defecto; con «Excluir» desaparecemos de las respuestas con IA). Nunca `nosnippet`, `max-snippet:0` ni `data-nosnippet` sobre los datos: Google y Bing los aplican también a las respuestas con IA. [Google: funciones de IA](https://developers.google.com/search/docs/appearance/ai-features) · [Google: control de IA generativa](https://support.google.com/webmasters/answer/16908024) · [Bing: data-nosnippet](https://blogs.bing.com/webmaster/October-2025/Bing-Introduces-Support-for-the-data-nosnippet-HTML-Attribute)
20. Permitidos en robots.txt (lista revisada el 30/10/2026; la comprueba el control):
    - buscadores: Googlebot, Bingbot, Applebot, DuckDuckBot (Brave no tiene agente propio: sigue las reglas de Googlebot);
    - buscadores y respuestas con IA: OAI-SearchBot (sin él no salimos en ChatGPT), Claude-SearchBot, PerplexityBot, DuckAssistBot, Meta-WebIndexer, Amzn-SearchBot, MistralAI-Index;
    - agentes que leen una página porque un usuario lo pide: ChatGPT-User, Claude-User, Perplexity-User, MistralAI-User. Varios no respetan robots.txt («robots.txt rules may not apply», OpenAI): lo que importa es no bloquearlos en Cloudflare.
    
    [OpenAI](https://developers.openai.com/api/docs/bots) · [Anthropic](https://support.claude.com/en/articles/8896518) · [Perplexity](https://docs.perplexity.ai/docs/resources/perplexity-crawlers) · [Apple](https://support.apple.com/en-us/119829) · [Brave](https://search.brave.com/help/brave-search-crawler) · [Meta](https://developers.facebook.com/documentation/sharing/webmasters/web-crawlers) · [Amazon](https://developer.amazon.com/amazonbot) · [DuckDuckGo](https://duckduckgo.com/duckduckgo-help-pages/results/duckassistbot) · [Mistral](https://docs.mistral.ai/robots)
21. Robots de entrenamiento y anclaje permitidos: Google-Extended (decide también si Gemini puede usar la página para responder, y no afecta a la búsqueda), GPTBot, ClaudeBot, Applebot-Extended, Meta-ExternalAgent, Amazonbot y CCBot. Bloquearlos no trae tráfico y, en Cloudflare, bloquear el entrenamiento con «Block» bloquea también a Googlebot, Bingbot y Applebot, que son robots de uso mixto. [Google: robots](https://developers.google.com/crawling/docs/crawlers-fetchers/google-common-crawlers) · [Cloudflare, 1/7/2026](https://blog.cloudflare.com/content-independence-day-ai-options) · [Cloudflare, 15/9/2026](https://blog.cloudflare.com/accountable-mixed-use-ai-crawlers)
22. Datos estructurados solo con lo visible en la página. [Google: políticas](https://developers.google.com/search/docs/appearance/structured-data/sd-policies)
    - `JobPosting` solo en la ficha de un proceso con plazo abierto y una única convocatoria, nunca en listados; al cerrarse el plazo se quita el marcado en la siguiente publicación (no hacerlo a tiempo puede traer una acción manual). [Google: JobPosting](https://developers.google.com/search/docs/appearance/structured-data/job-posting)
    - Sí: `JobPosting`, `BreadcrumbList` (Google solo lo enseña en ordenador), `WebSite` y `Organization` en la portada, `Dataset` solo en `/datos/` (solo lo usa Dataset Search).
    - No aportan en Google y no se usan: `FAQPage` (dejó de mostrarse el 7/5/2026), `HowTo`, información de cursos y sueldo estimado (retirados en 2025), lista de cursos (solo en inglés), `ClaimReview`. [Google: galería](https://developers.google.com/search/docs/appearance/structured-data/search-gallery) · [Google: cambios](https://developers.google.com/search/updates)

### Configuración fija de Cloudflare
23. Robots de IA (Seguridad › «AI bot policies»; el antiguo «Block AI bots» se retiró el 15/09/2026): Search, Agent y Training en «Allow». Al dar de alta el dominio, no aceptar el ajuste para webs con anuncios: pone Training en «Disallow AI Training» y Agent en «Block on pages with ads», que deja fuera a ChatGPT-User y Claude-User en esas páginas. Con todo en «Allow», Cloudflare sirve nuestro robots.txt sin tocarlo; con cualquier bloqueo, antepone el suyo (`Content-signal` y `Disallow` a GPTBot, ClaudeBot, Google-Extended…). [Cloudflare: robots de IA](https://developers.cloudflare.com/bots/additional-configurations/block-ai-bots/) · [Cloudflare: robots.txt gestionado](https://developers.cloudflare.com/bots/additional-configurations/managed-robots-txt/) · [Cloudflare, 15/9/2026](https://blog.cloudflare.com/accountable-mixed-use-ai-crawlers)
24. Desactivados: Bot Fight Mode y Super Bot Fight Mode (por precaución: la documentación no dice que desafíen a Googlebot, pero no se pueden saltar con reglas), pago por rastreo, ofuscación de correos (viene activada al darse de alta y mete JavaScript en el HTML), inserción automática de Web Analytics (activada por defecto) y Rocket Loader. Crawler Hints puede quedar activado, pero no sustituye a nuestro aviso de IndexNow. [Cloudflare: Bot Fight Mode](https://developers.cloudflare.com/bots/get-started/bot-fight-mode/) · [Cloudflare: correos](https://developers.cloudflare.com/waf/tools/scrape-shield/email-address-obfuscation/) · [Cloudflare: Web Analytics](https://developers.cloudflare.com/web-analytics/get-started/) · [Cloudflare: Crawler Hints](https://developers.cloudflare.com/cache/advanced-configuration/crawler-hints/)
25. Límites del alojamiento (Workers con archivos estáticos): 100.000 archivos por versión en el plan de pago, 25 MiB por archivo, 2.000 redirecciones fijas y 100 dinámicas en `_redirects`, 100 reglas en `_headers`. Con 500.000 páginas, el sitio se reparte en varios Workers por sección bajo el mismo dominio, y las redirecciones que pasen de 2.000 van en un Worker con su tabla. Respuesta 404 propia (`not_found_handling = "404-page"`), nunca el modo de aplicación de una página. [Cloudflare: límites](https://developers.cloudflare.com/workers/platform/limits/) · [Cloudflare: redirecciones](https://developers.cloudflare.com/workers/static-assets/redirects/)
26. Plan B de alojamiento: Bunny CDN (la web son archivos estáticos; mudanza en un día). Su escudo deja pasar por defecto a los buscadores verificados. [Bunny](https://bunny.net/docs/shield/verified-bots)

## Prohibido siempre

| Práctica | Motivo | Fuente |
|---|---|---|
| Páginas en masa sin valor | Abuso de contenido a escala, «no matter how it's created» | [Spam policies](https://developers.google.com/search/docs/essentials/spam-policies) |
| Páginas casi iguales por pueblo o variante, más cerca de una página de resultados que de una jerarquía navegable | Abuso de páginas puerta (*doorway abuse*) | [Spam policies](https://developers.google.com/search/docs/essentials/spam-policies) |
| Dominio caducado comprado por su historial | Abuso de dominios caducados | [Spam policies](https://developers.google.com/search/docs/essentials/spam-policies) |
| Copiar textos de otras webs | *Scraping* | [Spam policies](https://developers.google.com/search/docs/essentials/spam-policies) |
| Contenido distinto para Google y para el usuario, texto oculto, relleno de palabras clave | Encubrimiento, texto oculto, *keyword stuffing* | [Spam policies](https://developers.google.com/search/docs/essentials/spam-policies) |
| Comprar o intercambiar enlaces | Spam de enlaces | [Spam policies](https://developers.google.com/search/docs/essentials/spam-policies) |
| Secuestrar el botón «atrás» del navegador | Prácticas maliciosas (abril de 2026) | [Spam policies](https://developers.google.com/search/docs/essentials/spam-policies) |
| Cambiar fechas sin cambiar el dato | Google pregunta por ello y deja de fiarse del lastmod | [Contenido útil](https://developers.google.com/search/docs/fundamentals/creating-helpful-content) |
| Ventanas que tapan el contenido al entrar | Ventanas intrusivas | [Interstitials](https://developers.google.com/search/docs/appearance/avoid-intrusive-interstitials) |
| Contenido solo con JavaScript; noindex o canónica con JavaScript | Google puede no verlo; los robots de IA no ejecutan JS | [JavaScript](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics) |
| Bloquear robots de búsqueda o de IA; bloquear el entrenamiento con «Block» en Cloudflare | Desaparecer de Google, ChatGPT o Claude | [Cloudflare](https://blog.cloudflare.com/accountable-mixed-use-ai-crawlers) |
| Perfiles de autor inventados | Señal de baja calidad | [Contenido útil](https://developers.google.com/search/docs/fundamentals/creating-helpful-content) |
| Web de pruebas sin contraseña; copias de la web generada en el repositorio público o en GitHub Pages | Contenido duplicado indexado en otro dominio | — |

## Control automático de cada página

Programado en `motor/seo/control.py` (catálogo en `motor/seo/reglas.py`). Ninguna página se publica sin pasarlo.

| Comprobación | Si falla |
|---|---|
| Datos mínimos de su tipo (proceso: convocante, plazas, plazo y fuente; lugar: al menos un proceso; máster: asignaturas y precio). Cada tipo nuevo declara los suyos antes de publicar | Se publica con `noindex` (lo pone el control) |
| Similitud de texto con otra página indexable del sitio por encima del umbral (0,90 de partida, a calibrar) | `noindex` o fusión: para la publicación hasta decidir |
| Contenido principal presente en el HTML sin ejecutar JavaScript (y JavaScript no añade contenido, comprobado con Chromium) | No se publica |
| Fuente (enlace) y fecha (`<time>`) visibles en cada dato clave | No se publica |
| Título y descripción únicos en el sitio y sin huecos de plantilla | No se publica |
| HTTP 200, canónica a sí misma, al menos un enlace interno entrante desde una página indexable | No se publica |
| Enlaces internos sin rotos, sin almohadillas, sin JavaScript, sin pasar por redirecciones | No se publica |
| Directivas: sin `nosnippet`, `max-snippet:0` ni `data-nosnippet` sobre datos en páginas indexables; las mismas antes y después de JavaScript | No se publica |
| HTML de 2 MB como máximo sin comprimir | No se publica |
| Dirección en minúsculas, con guiones, sin tildes ni códigos y con barra final | No se publica |
| Datos estructurados válidos y coincidentes con lo visible; `JobPosting` solo en procesos con plazo abierto | Se publica sin marcado (lo quita el control) |
| Ninguna ventana al cargar (ni en el HTML sin `hidden` ni en pantalla con Chromium) | No se publica |
| Texto con IA aprobado en revisión (manifiesto de la página y registro de revisiones) | No se publica |
| Velocidad por plantilla en laboratorio (móvil lento): LCP ≤ 2,5 s, CLS ≤ 0,1 | No se publica la plantilla |
| Sitio: robots.txt deja pasar a todos los robots de la regla 20 y 21, y a los recursos que necesita Googlebot; sitemaps válidos y completos; `lastmod` igual a la fecha visible y que solo cambia si cambia el contenido; `_redirects` con 301 y sin cadenas; `_headers` sin `noindex`; 404 propia; metodología enlazada | No se publica |

Avisos que no paran la publicación: imágenes sin texto alternativo o sin medidas, fichas sin los dos caminos de migas, títulos de pura plantilla, más del 20 % de páginas `noindex`, marcado que ya no aporta, portada sin `WebSite` o con icono SVG.

## Comprobaciones diarias

Programadas en `motor/seo/vigilancia.py` (flujo `seo.yml`; se activa al crear la variable `SEO_BASE` con la dirección del sitio):

- una sola versión del dominio (http y www redirigen en un salto permanente);
- el robots.txt servido es el nuestro y deja pasar a todos (Cloudflare no antepone el suyo);
- sitemaps servidos y una muestra diaria de sus páginas: 200, sin `noindex` en cabecera ni en HTML, canónica propia, sin desafíos de Cloudflare, sin código inyectado por Cloudflare, idénticas a las generadas;
- los robots con su nombre reciben lo mismo que una persona;
- 404 de verdad para lo que no existe; 304 a las peticiones condicionales; certificado con más de 14 días;
- con claves: datos reales de velocidad (CrUX), errores de sitemaps y canónica elegida por Google en Search Console, problemas de rastreo en Bing.

Si algo falla, alerta (incidencia de GitHub, que avisa por correo; Telegram cuando exista el bot). Además, a mano cada semana: el informe de rendimiento con IA de Search Console y el de AI Performance de Bing Webmaster Tools.

## Cambios en la revisión del 30/10/2026 (tarde)

- Secciones visibles (regla 7), paginación y facetas (regla 17) y carrusel de sitios de empleo del EEE (regla 18). El control con Chromium avisa si el JavaScript oculta parte del contenido principal.
- Estrategia completa en `docs/estrategia-seo.md`.

## Cambios en la revisión del 30/10/2026

- Fuente oficial para la regla de Cloudflare y Googlebot (antes era un artículo de prensa) y matiz: solo «Block» en entrenamiento bloquea a Googlebot. El interruptor «Block AI bots» ya no existe: nueva regla 23.
- Nuevas: 2 MB por página (10), presupuesto de rastreo y metaetiquetas en el cuerpo (13 y 15), nombre del sitio e icono (14), direcciones (12), títulos de plantilla (6), interruptor de IA de Search Console (19), Indexing API e IndexNow con sus límites (18), límites de Cloudflare (25).
- Lista de robots ampliada con los que publican OpenAI, Anthropic, Perplexity, Apple, Meta, Amazon, DuckDuckGo y Mistral; los agentes de usuario pueden no respetar robots.txt.
- Datos estructurados: lista de lo que sí y lo que ya no aporta.
- Nombres de las políticas de spam al día y nueva práctica prohibida (botón «atrás»). La actualización de las políticas del 28/08/2026 solo tocó la aplicación de la política de reputación del sitio en el Espacio Económico Europeo.
- Core Web Vitals: percentil 75 y umbrales con «o menos».
