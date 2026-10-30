"""Control SEO del portal: lo que exige `docs/ley-seo.md` comprobado sobre la web generada y sobre la publicada.

- `control.py`: control de cada página antes de publicar (carpeta de la web generada). Ninguna página sale sin
  pasarlo.
- `renderizado.py`: lo que solo se ve con un navegador (contenido que añade JavaScript, ventanas al cargar,
  velocidad por plantilla).
- `vigilancia.py`: comprobaciones diarias del sitio publicado.

Cada comprobación está en `reglas.py` con su fuente oficial y lo que pasa si falla.
"""
