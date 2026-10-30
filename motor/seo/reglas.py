"""Catálogo de comprobaciones del control SEO: qué se mira, qué pasa si falla y de dónde sale la regla.

Es la traducción a código de la tabla «Control automático de cada página» de `docs/ley-seo.md`. Si cambia la ley,
se cambia aquí y en la comprobación, y se vuelve a pasar el control a todas las páginas.

Consecuencias (columna «Si falla» de la ley):
- `no_publicar`: la publicación se para hasta corregir el generador.
- `noindex`: la página sale con `<meta name="robots" content="noindex">`; el control lo pone él mismo con
  `--aplicar` si el generador no lo ha hecho.
- `sin_marcado`: la página sale sin ese bloque de datos estructurados; con `--aplicar` el control lo quita.
- `plantilla`: no se publica ninguna página de esa plantilla.
- `aviso`: no para nada; se revisa a mano. Se usa para lo que la documentación oficial recomienda sin exigir.
"""

from __future__ import annotations

from dataclasses import dataclass

GOOGLE = "https://developers.google.com/search/docs"


@dataclass(frozen=True)
class Regla:
    id: str
    que: str
    consecuencia: str
    fuente: str


_LISTA = [
    # Tabla de la ley
    Regla("datos_minimos", "Datos mínimos de su tipo; si no los tiene, noindex", "noindex",
          f"{GOOGLE}/fundamentals/creating-helpful-content"),
    Regla("similitud", "Texto casi igual al de otra página indexable del sitio", "no_publicar",
          f"{GOOGLE}/essentials/spam-policies#doorway-abuse"),
    Regla("contenido_html", "Contenido principal en el HTML servido, sin depender de JavaScript", "no_publicar",
          f"{GOOGLE}/crawling-indexing/javascript/javascript-seo-basics"),
    Regla("fuente_fecha", "Cada dato clave con su fuente y su fecha visibles", "no_publicar",
          f"{GOOGLE}/fundamentals/creating-helpful-content"),
    Regla("titulo", "Título presente, único en el sitio y sin huecos de plantilla", "no_publicar",
          f"{GOOGLE}/appearance/title-link"),
    Regla("descripcion", "Descripción presente, única en el sitio y sin huecos de plantilla", "no_publicar",
          f"{GOOGLE}/appearance/snippet"),
    Regla("canonica", "Una canónica absoluta, en HTTPS, del dominio y a sí misma", "no_publicar",
          f"{GOOGLE}/crawling-indexing/consolidate-duplicate-urls"),
    Regla("enlace_entrante", "Al menos un enlace interno entrante desde otra página", "no_publicar",
          f"{GOOGLE}/crawling-indexing/links-crawlable"),
    Regla("enlaces", "Enlaces internos que existen, como <a href> con ruta real y sin almohadillas", "no_publicar",
          f"{GOOGLE}/crawling-indexing/links-crawlable"),
    Regla("datos_estructurados", "Datos estructurados válidos y con lo mismo que se ve en la página", "sin_marcado",
          f"{GOOGLE}/appearance/structured-data/sd-policies"),
    Regla("jobposting", "JobPosting solo en la ficha de un proceso con plazo abierto y una sola convocatoria",
          "sin_marcado", f"{GOOGLE}/appearance/structured-data/job-posting"),
    Regla("ventanas", "Ninguna ventana se abre al cargar", "no_publicar",
          f"{GOOGLE}/appearance/avoid-intrusive-interstitials"),
    Regla("ia_revisada", "Texto escrito con IA aprobado en revisión", "no_publicar",
          f"{GOOGLE}/fundamentals/using-gen-ai-content"),
    Regla("velocidad", "Velocidad de la plantilla en laboratorio: LCP ≤ 2,5 s y CLS ≤ 0,1", "plantilla",
          "https://web.dev/articles/vitals"),
    # Reglas de oro que también se pueden comprobar en el HTML
    Regla("indexacion", "Directivas de robots coherentes: sin nosnippet en páginas indexables, noindex solo en el "
          "HTML original", "no_publicar", f"{GOOGLE}/crawling-indexing/robots-meta-tag"),
    Regla("direccion", "Dirección en minúsculas, con guiones, sin códigos y terminada en barra", "no_publicar",
          f"{GOOGLE}/crawling-indexing/url-structure"),
    Regla("tamano_html", "HTML de 2 MB como máximo sin comprimir: Googlebot no lee lo que pasa de ahí", "no_publicar",
          f"{GOOGLE}/crawling-indexing/googlebot"),
    Regla("movil", "Etiqueta viewport para móvil", "no_publicar",
          f"{GOOGLE}/crawling-indexing/mobile/mobile-sites-mobile-first-indexing"),
    Regla("imagenes", "Imágenes con texto alternativo y con ancho y alto", "aviso",
          f"{GOOGLE}/appearance/google-images"),
    Regla("migas", "Migas de pan visibles con los dos caminos (ficha)", "aviso",
          f"{GOOGLE}/appearance/structured-data/breadcrumb"),
    # Comprobaciones del sitio entero
    Regla("robots_txt", "robots.txt permite a todos los robots de búsqueda, de IA y de entrenamiento", "no_publicar",
          f"{GOOGLE}/crawling-indexing/robots/robots_txt"),
    Regla("sitemaps", "Sitemaps por sección, ≤ 50.000 URL y ≤ 50 MB, solo páginas indexables, sin changefreq ni "
          "priority", "no_publicar", f"{GOOGLE}/crawling-indexing/sitemaps/build-sitemap"),
    Regla("lastmod", "La fecha solo cambia si cambia el dato (y cambia cuando cambia)", "no_publicar",
          f"{GOOGLE}/crawling-indexing/sitemaps/build-sitemap"),
    Regla("redirecciones", "Redirecciones permanentes, sin cadenas ni bucles y a páginas que existen", "no_publicar",
          f"{GOOGLE}/crawling-indexing/301-redirects"),
    Regla("cabeceras", "Ninguna cabecera X-Robots-Tag que quite del índice páginas indexables", "no_publicar",
          f"{GOOGLE}/crawling-indexing/robots-meta-tag"),
    Regla("metodologia", "Página de metodología publicada, indexable y enlazada", "no_publicar",
          f"{GOOGLE}/fundamentals/creating-helpful-content"),
    Regla("portada", "Portada con nombre del sitio (WebSite) e icono en un formato que Google admite", "aviso",
          f"{GOOGLE}/appearance/site-names"),
    Regla("rastreo", "Presupuesto de rastreo: pocas páginas noindex y títulos que no son pura plantilla", "aviso",
          "https://developers.google.com/crawling/docs/crawl-budget"),
    Regla("pagina_404", "Página 404 propia que responde 404 (sin respuestas 200 para direcciones que no existen)",
          "no_publicar", f"{GOOGLE}/crawling-indexing/http-network-errors"),
]

REGLAS: dict[str, Regla] = {r.id: r for r in _LISTA}
assert len(REGLAS) == len(_LISTA), "identificadores repetidos"

# Datos mínimos por tipo de página (tabla de la ley). Cada requisito es una lista de claves `data-dato`
# alternativas: basta una. Los tipos sin requisitos se declaran con lista vacía; un tipo que no esté aquí es un
# error del generador (cada módulo declara los suyos antes de publicar).
DATOS_MINIMOS: dict[str, list[list[str]]] = {
    "proceso": [["convocante"], ["plazas"], ["plazo"]],
    "lugar": [],  # al menos un enlace a una ficha de proceso: se comprueba con los enlaces
    "master": [["asignaturas"], ["precio_total", "precio_credito"]],
    # Sin requisitos de datos: no son fichas
    "inicio": [],
    "listado": [],
    "metodologia": [],
    "legal": [],
    "herramienta": [],
}

# Tipos que exigen enlaces a fichas de otro tipo para tener datos propios.
ENLACES_MINIMOS: dict[str, tuple[str, int]] = {
    "lugar": ("proceso", 1),
}

# Robots que robots.txt tiene que dejar pasar (ley, reglas 15 y 16). Se comprueban con sus nombres de agente.
# Lista revisada el 30/10/2026 en la documentación de cada empresa (docs/ley-seo.md, regla 15).
ROBOTS_PERMITIDOS = [
    # Buscadores (Brave no tiene agente propio: sigue las reglas de Googlebot)
    "Googlebot", "Googlebot-Image", "Bingbot", "Applebot", "DuckDuckBot",
    # Buscadores y respuestas con IA
    "OAI-SearchBot", "Claude-SearchBot", "PerplexityBot", "DuckAssistBot", "Meta-WebIndexer", "Amzn-SearchBot",
    "MistralAI-Index",
    # Agentes que leen una página porque un usuario lo pide (varios no respetan robots.txt; se comprueba igual)
    "ChatGPT-User", "Claude-User", "Perplexity-User", "MistralAI-User",
    # Entrenamiento y anclaje (Google-Extended también decide si Gemini puede citar la página)
    "Google-Extended", "GPTBot", "ClaudeBot", "Applebot-Extended", "Meta-ExternalAgent", "Amazonbot", "CCBot",
]

# Tipos de datos estructurados que ya no dan resultado enriquecido en Google (galería de 16/10/2026 y registro de
# cambios de Search Central). No penalizan, pero no aportan: aviso.
MARCADO_SIN_EFECTO = {
    "FAQPage": "las preguntas frecuentes dejaron de mostrarse el 7/5/2026",
    "HowTo": "retirado en 2023",
    "Course": "la información de cursos se retiró en 2025 y la lista de cursos solo existe en inglés",
    "Occupation": "el sueldo estimado se retiró en 2025",
    "ClaimReview": "Google lo está retirando",
    "Dataset": "solo lo usa Dataset Search, no la búsqueda de Google (usarlo solo en /datos/)",
}
