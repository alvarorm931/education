"""Orden de trabajo por reputación: primero las universidades y escuelas de más prestigio (petición de Álvaro, 30/10/2026:
«prioriza siempre de mayor a peor reputación»). Solo ordena el trabajo (qué se lee, se recupera o se revisa antes);
no se publica como dato ni cambia ninguna ficha.

Orden: las universidades españolas del QS World University Rankings 2026 por su puesto (las diez primeras, según
la prensa del 19/6/2026), después las del grupo de más rendimiento del U-Ranking 2025 (Fundación BBVA-Ivie) que no
están ya, luego las escuelas de negocio de referencia (con su universidad cuando expiden másters oficiales) y el resto
de universidades del grupo 2 del U-Ranking. Las demás van detrás, con el mismo peso.

Fuentes (consultadas el 30/10/2026):
  - https://lepetitjournal.com/madrid/education/classement-qs-2026-universites-espagnoles-416631
  - https://u-ranking.es/pdf/NP-U-Ranking-2025.pdf
"""

from __future__ import annotations

import re
import unicodedata

# claves sin tildes ni «Universidad de»: se busca cada una dentro del nombre normalizado
ORDEN = [
    # QS WUR 2026 (puestos 160 a 401)
    "barcelona", "autonoma de barcelona", "complutense", "autonoma de madrid", "navarra", "pompeu fabra",
    "carlos iii", "politecnica de madrid", "politecnica de catalunya", "granada",
    # U-Ranking 2025, grupo 1, y escuelas de negocio de referencia
    "politecnica de valencia", "ie universidad", "ramon llull", "esade", "iese",
    "pontificia comillas", "deusto", "cunef",
    # U-Ranking 2025, grupo 2, y las públicas grandes
    "valencia", "santiago de compostela", "rovira i virgili", "girona", "cantabria", "vigo", "sevilla", "salamanca",
    "zaragoza", "pais vasco", "oviedo", "a coruna", "murcia", "alicante", "malaga", "jaume i", "miguel hernandez",
    "valladolid", "rey juan carlos", "alcala", "castilla-la mancha", "esic", "eada", "eae", "francisco de vitoria",
    "san pablo", "nebrija", "europea de madrid", "uned", "nacional de educacion a distancia",
]


def _clave(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9-]+", s))


def posicion(nombre: str | None) -> int:
    """Puesto de trabajo (0 = primero); las que no están en ORDEN, al final y empatadas."""
    k = _clave(nombre)
    # «Autónoma de Barcelona» antes que «Barcelona»: gana la clave más larga que encaje
    mejor = None
    for i, c in enumerate(ORDEN):
        if re.search(rf"(^|\b){re.escape(c)}(\b|$)", k) and (mejor is None or len(c) > len(ORDEN[mejor])):
            mejor = i
    if mejor is None:
        return len(ORDEN)
    # «Politécnica de Valencia» no es «Valencia»; «Pública de Navarra» no es «Navarra»
    if ORDEN[mejor] == "navarra" and "publica" in k:
        return len(ORDEN)
    if ORDEN[mejor] in ("valencia", "barcelona", "madrid") and re.search(r"politecnica|catolica|europea|internacional", k):
        return len(ORDEN)
    return mejor
