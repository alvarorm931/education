# Encargo: SEO, dominio y vigilancia

Para la conversación que se ocupa de que el portal salga el primero que pueda en Google, en Bing y en los buscadores
con IA, y de que siga ahí. Leer antes `docs/contexto-proyecto.md` y `docs/ley-seo.md`.

## Qué es de este encargo

- **La ley** (`docs/ley-seo.md`): se revisa cada mes contra la documentación oficial y siempre que Google anuncie una
  actualización. Si cambia una regla, se cambia el control y se avisa a las demás conversaciones en el proyecto.
- **El control antes de publicar** (`motor/seo/control.py`, `renderizado.py`, `sitemaps.py`): ninguna página sale
  sin pasarlo.
- **Los avisos a los buscadores** en cada publicación (`motor/seo/notificar.py`: IndexNow y la Indexing API de
  Google para los procesos con plazo abierto).
- **La vigilancia diaria** del sitio publicado (`motor/seo/vigilancia.py`, flujo `seo.yml`).
- **El dominio**: revisión de candidatos (`motor/seo/dominio.py`), configuración de Cloudflare (ley, reglas 23 a
  25), alta en Search Console y Bing Webmaster Tools.

No es de este encargo generar las páginas (eso lo hace el generador de cada módulo), pero el generador tiene que
cumplir el contrato de abajo.

## Contrato con el generador de páginas

### La carpeta que se publica (`web/`)
- Cada dirección `/a/b/` es `a/b/index.html`. En la raíz: `robots.txt`, `404.html`, `favicon.png` (o `.ico`),
  la clave de IndexNow (`{clave}.txt`) y, si hacen falta, `_redirects` y `_headers` de Cloudflare.
- Los sitemaps los escribe el control (`--generar-sitemaps`) desde las páginas que quedan indexables.
- Recursos propios con rutas desde la raíz (`/css/web.css`), no con la dirección completa.

### Cada página
- `<title>`, `<meta name="description">`, `<link rel="canonical">` absoluto a sí misma y `<meta name="viewport">`.
- Un solo `<main>`, con `data-tipo="proceso|lugar|master|listado|…"` (o el tipo en el manifiesto).
- Cada dato clave en un elemento `data-dato="clave"`, con su valor (o un hijo `data-valor`), un enlace
  `<a data-fuente href="…">` a la fuente y un `<time datetime="AAAA-MM-DD">`. Si muchos datos comparten fuente,
  el elemento lleva `data-fuente="id"` y apunta a una nota con el enlace y la fecha.
- La fecha de última actualización, en un elemento `data-actualizado` con su `<time datetime>`; tiene que ser la
  misma que el `lastmod` del manifiesto.
- Migas de pan en `<nav aria-label="Migas de pan…">`, una por cada camino (las fichas tienen dos padres).
- Toda ventana o diálogo, en el HTML con el atributo `hidden`; solo se abre si el usuario lo pide.
- `noindex` solo como `<meta name="robots" content="noindex">` en el HTML; nunca con JavaScript.
- Claves de datos mínimos: ver `DATOS_MINIMOS` en `motor/seo/reglas.py`. Un tipo nuevo se declara ahí antes de
  publicar su primera página.

### El manifiesto (`control/paginas.jsonl`, fuera de la carpeta que se publica)
Una línea por página:
```json
{"ruta": "/oposiciones/auxiliar-administrativo/ayuntamiento-de-villaejemplo/2026/", "tipo": "proceso",
 "plantilla": "proceso", "lastmod": "2026-10-28", "textos_ia": ["texto escrito con IA, tal cual sale"]}
```
Los textos con IA se aprueban en `control/revision_ia.jsonl` (`{"huella": sha256 del texto, "revisado_por": "…",
"fecha": "…"}`); `motor.seo.control.huella_texto()` calcula la huella.

## Orden de una publicación

1. El generador escribe `web/` y el manifiesto.
2. Control: `python -m motor.seo.control --sitio web --base $SEO_BASE --manifiesto control/paginas.jsonl
   --revisiones control/revision_ia.jsonl --estado-anterior estado/seo.json --estado-nuevo estado/seo-nuevo.json
   --aplicar --generar-sitemaps --navegador --informe informe-seo.json`.
   Pone `noindex` a lo que no tiene datos mínimos, quita el marcado que no vale, escribe los sitemaps y comprueba
   todo. Si sale con código 1, no se publica.
3. Se sube `web/`.
4. Avisos: `python -m motor.seo.notificar --base $SEO_BASE --sitio web --estado-anterior estado/seo.json
   --estado-nuevo estado/seo-nuevo.json`; después `seo-nuevo.json` pasa a ser `seo.json`.
5. Cada mañana, la vigilancia sobre lo publicado.

## Lo que necesita a Álvaro (Claude no crea cuentas ni claves)

1. **Nombre y dominio.** Pasarme candidatos y los reviso con `motor.seo.dominio` desde GitHub (historial en la
   Wayback Machine y en Common Crawl, nombre que no aparente carácter oficial). Para registrar un .es hace falta
   vínculo con España y datos veraces (dominios.es).
2. **Cloudflare** al dar de alta el dominio: robots de IA en «Allow» los tres (no aceptar el ajuste para webs con
   anuncios), Bot Fight Mode, ofuscación de correos, Web Analytics automático y Rocket Loader desactivados.
3. **Search Console** (propiedad de dominio) y **Bing Webmaster Tools** (importando desde Search Console) el mismo
   día que el dominio, antes de publicar nada. En Search Console, revisar «Acciones manuales» y «Problemas de
   seguridad» nada más verificar, y dejar «IA generativa en la Búsqueda» en «Incluir».
4. **Secretos de GitHub** para la vigilancia y los avisos: `CRUX_API_KEY` (Google Cloud, gratis),
   `GSC_CREDENCIALES` (cuenta de servicio añadida como propietaria en Search Console; sirve también para la Indexing
   API), `BING_WEBMASTER_KEY`, `INDEXNOW_CLAVE`. Y la variable `SEO_BASE` con la dirección del sitio, que es la que
   enciende la vigilancia diaria.
5. **Web de pruebas** con contraseña (Cloudflare Access) y `noindex` en cabecera: nunca abierta.

## Estado (30/10/2026)

- Hecho: ley revisada; control, renderizado con Chromium, sitemaps, avisos, vigilancia y revisión de dominios
  programados con 31 pruebas sobre una web de ejemplo con errores sembrados.
- Sin probar contra servicios reales, a falta de dominio y claves: API de Search Console, Indexing API, API de
  Bing, IndexNow y CrUX.
- Pendiente de calibrar: el umbral de similitud, con las primeras páginas reales de cada plantilla.
