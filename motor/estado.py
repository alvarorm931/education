"""Estado de todas las fuentes: qué se ha capturado, qué falta y qué falla. Para vigilar que nada se pare.

Lee los informes por día o boletín que deja cada conector (datos/autonomicos/{fuente}/ y datos/provinciales/{fuente}/:
dias/, meses/ o boletines/) y escribe datos/estado.json con, por fuente:
  - informes por resultado (ok, sin_boletin, error_http, error_formato, fuente_inaccesible);
  - último día con boletín leído y días hábiles sin noticias desde entonces;
  - anuncios de empleo público, textos guardados y textos pendientes;
  - últimos errores;
  - huecos en la numeración de los boletines leídos (por año, entre el primero y el último leídos): un número que
    falta es un boletín que no se ha leído aunque el día pareciera vacío o festivo.
Alerta (código de salida 1 y aviso en GitHub) si una fuente lleva más de 3 días hábiles sin un boletín leído.

Uso: python -m motor.estado --salida ruta/ [--hoy AAAA-MM-DD]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")
CARPETAS_INFORMES = ("dias", "meses", "boletines")
UMBRAL_DIAS_HABILES = 3


def dias_habiles_entre(desde: date, hasta: date) -> int:
    n, d = 0, desde + timedelta(days=1)
    while d <= hasta:
        n += d.weekday() < 5
        d += timedelta(days=1)
    return n


def _lineas(f: Path) -> int:
    try:
        return sum(1 for l in f.open(encoding="utf-8") if l.strip())
    except OSError:
        return 0


def _numero(inf: dict) -> int | None:
    n = str(inf.get("numero") or "").strip()
    return int(n) if n.isdigit() and 0 < int(n) < 100000 else None


def huecos_numeracion(numeros: dict[str, set[int]]) -> dict:
    """Números que faltan entre el primero y el último leídos de cada año y serie. Hay boletines con dos series
    (BOME: ordinarios 59xx-64xx correlativos de un año a otro y extraordinarios 1, 2, 3… cada año; BOJA:
    ordinarios 1-2xx y extraordinarios 5xx), así que cada serie se mira por separado."""
    huecos = {}
    for anio, ns in sorted(numeros.items()):
        series = ([n for n in ns if n < 500], [n for n in ns if 500 <= n < 1000], [n for n in ns if n >= 1000])
        faltan = []
        for serie in series:
            if len(serie) >= 2:
                serie = sorted(serie)
                faltan += sorted(set(range(serie[0], serie[-1] + 1)) - set(serie))
        if faltan:
            huecos[anio] = faltan
    return huecos


def estado_fuente(carpeta: Path, hoy: date) -> dict:
    resultados, ultimo_ok, errores = Counter(), None, []
    numeros: dict[str, set[int]] = {}
    for sub in CARPETAS_INFORMES:
        for f in (carpeta / sub).rglob("*.json"):
            try:
                inf = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                resultados["ilegible"] += 1
                continue
            r = inf.get("resultado") or "desconocido"
            resultados[r] += 1
            # Informes por mes (BOCYL) llevan el último día con boletín; los de boletín, su fecha
            fecha = inf.get("ultimo_dia") or inf.get("fecha") or (inf.get("mes") and f"{inf['mes']}-01")
            if r == "ok" and fecha and (ultimo_ok is None or fecha > ultimo_ok):
                ultimo_ok = fecha
            if r == "ok" and (n := _numero(inf)) and (anio := str(inf.get("anio") or (fecha or "")[:4])):
                numeros.setdefault(anio, set()).add(n)
            if r not in ("ok", "sin_boletin"):
                errores.append({"fecha": fecha, "resultado": r, "alertas": (inf.get("alertas") or [])[:2]})
    empleo = sum(_lineas(f) for f in (carpeta / "oposiciones").rglob("*.jsonl"))
    textos = sum(1 for _ in (carpeta / "textos").rglob("*.json"))
    sin_noticias = dias_habiles_entre(date.fromisoformat(ultimo_ok[:10]), hoy) if ultimo_ok else None
    errores.sort(key=lambda e: e.get("fecha") or "", reverse=True)
    huecos = huecos_numeracion(numeros)
    return {
        "informes": dict(resultados), "ultimo_boletin_leido": ultimo_ok, "dias_habiles_sin_boletin": sin_noticias,
        "anuncios_empleo": empleo, "textos": textos, "textos_pendientes": max(empleo - textos, 0),
        "ultimos_errores": errores[:5],
        "huecos_numeracion": {k: v[:30] for k, v in huecos.items()},
        "boletines_sin_leer_por_numeracion": sum(len(v) for v in huecos.values()),
        "alerta": sin_noticias is None or sin_noticias > UMBRAL_DIAS_HABILES,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", type=Path, default=Path("."))
    p.add_argument("--hoy", type=date.fromisoformat, default=datetime.now(MADRID).date())
    a = p.parse_args(argv)
    fuentes = {}
    for grupo in ("autonomicos", "provinciales"):
        base = a.salida / "datos" / grupo
        for c in sorted(base.iterdir()) if base.exists() else []:
            if c.is_dir() and c.name != "actos":
                fuentes[c.name] = {"grupo": grupo, **estado_fuente(c, a.hoy)}
    boe = {}
    h = a.salida / "datos" / "boe" / "huecos.json"
    if h.exists():
        boe = json.loads(h.read_text(encoding="utf-8"))
    salida = {"fecha": a.hoy.isoformat(), "boe": boe, "fuentes": fuentes,
              "con_alerta": sorted(k for k, v in fuentes.items() if v["alerta"])}
    destino = a.salida / "datos" / "estado.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in fuentes.items():
        print(f"{k:14} último {v['ultimo_boletin_leido'] or '-':10} sin boletín {v['dias_habiles_sin_boletin']!s:>4} días "
              f"hábiles | empleo {v['anuncios_empleo']:6} | textos {v['textos']:6} | {dict(v['informes'])}")
    if salida["con_alerta"]:
        print(f"::warning title=Fuentes paradas::{', '.join(salida['con_alerta'])} llevan más de "
              f"{UMBRAL_DIAS_HABILES} días hábiles sin un boletín leído")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
