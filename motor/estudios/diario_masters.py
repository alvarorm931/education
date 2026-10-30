"""Pasada diaria de másteres: vuelve a mirar una séptima parte de todo cada día y solo paga lo que cambió.

Con lo que ya hay en la rama sondas (su lista está en masters-estado/manifiesto.json):
  1. webs de los centros: las páginas ya extraídas cuyo resumen de URL cae en el día (una de cada siete; cada
     página, una vez por semana). Se vuelven a pedir con el lector cortés; si su texto no ha cambiado no se envía a
     la API (extraer.huellas_previas); las que solo se pintan con JavaScript, con el navegador;
  2. QEDU: las tarjetas del curso (una petición) y el detalle de las imparticiones del día;
  3. RUCT: la ficha de los títulos del día y, si su memoria vigente cambió, la memoria (desde RUCT_DIARIO_DESDE:
     el 30/10 el RUCT dejó de aceptar conexiones desde GitHub y la primera lectura completa sigue en marcha);
  4. fichas_masters con todas las extracciones y conjunto_masters con el conjunto anterior (la fecha de cada dato
     solo cambia si cambia el dato).

Salida: {salida}/{sello}/datos/... (lo nuevo de hoy) y {salida}/masters-estado/ (manifiesto y conjunto, que
sustituyen a los anteriores). El flujo masters-diario.yml lo sube a sondas.

Uso:
  python -m motor.estudios.diario_masters --raiz entrada --dia 3 --sello 20261103T030000 --salida out
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import date
from pathlib import Path

ESTADO = "masters-estado"
DIAS = 7
RUCT_DIARIO_DESDE = date(2026, 11, 15)  # 30/10: el RUCT rechaza las conexiones desde GitHub; revisar antes de activarlo


def del_dia(clave: str, dia: int) -> bool:
    return int(hashlib.sha256(clave.encode()).hexdigest()[:8], 16) % DIAS == dia % DIAS


def manifiesto(raiz: Path) -> dict:
    m = json.loads((raiz / ESTADO / "manifiesto.json").read_text(encoding="utf-8"))
    c = raiz / "carpetas.json"
    if c.exists():  # las carpetas que el flujo encontró en la rama (carpetas_en_arbol)
        m.update(json.loads(c.read_text(encoding="utf-8")))
    return m


TIPOS = {  # clave del manifiesto → cómo se reconoce su carpeta en la rama
    "extracciones": re.compile(r"^([^/]+)/datos/estudios/extraccion/"),
    "ruct": re.compile(r"^([^/]+)/datos/estudios/masters/(?:ruct|ruct_memoria)/\d{7}\.json$"),
    "qedu": re.compile(r"^([^/]+)/datos/estudios/masters/qedu/"),
    "boe": re.compile(r"^([^/]+)/datos/estudios/masters/boe_planes_masters\.jsonl$"),
    "guias": re.compile(r"^([^/]+)/datos/estudios/masters/guias/.+/guias\.jsonl$"),
}
SUBRUTAS = {"extracciones": ["datos/estudios/extraccion"], "ruct": ["datos/estudios/masters/ruct", "datos/estudios/masters/ruct_memoria"],
            "qedu": ["datos/estudios/masters/qedu"], "boe": ["datos/estudios/masters/boe_planes_masters.jsonl"],
            "guias": ["datos/estudios/masters/guias"]}


def carpetas_en_arbol(rutas: list[str], desde: str, desde_por_tipo: dict[str, str] | None = None) -> dict[str, list[str]]:
    """Las carpetas de ejecución de la rama sondas con cada tipo de resultado, desde un sello (o el de su tipo: las
    memorias del RUCT del 29/10 siguen valiendo; las extracciones de antes del sello ya están en las retomadas)."""
    out: dict[str, set] = {k: set() for k in TIPOS}
    for r in rutas:
        for k, patron in TIPOS.items():
            m = patron.match(r)
            if m and m.group(1) >= (desde_por_tipo or {}).get(k, desde) and m.group(1)[:1].isdigit():
                out[k].add(m.group(1))
    return {k: sorted(v) for k, v in out.items()}


def rutas_a_traer(m: dict, carpetas: dict[str, list[str]]) -> list[str]:
    rutas = [ESTADO] + [m[k] for k in ("catalogo", "altas", "clasificacion", "censo", "tarifas") if m.get(k)]
    for k, cs in carpetas.items():
        rutas += [f"{c}/{s}" for c in cs for s in SUBRUTAS[k]]
    return list(dict.fromkeys(rutas))


def _rutas(raiz: Path, lista: list[str]) -> list[Path]:
    return [raiz / x for x in lista if (raiz / x).exists()]


def paginas_del_dia(extracciones: list[Path], dia: int) -> list[dict]:
    """Las páginas ya extraídas (la última extracción de cada una) que tocan hoy, con sus datos de unión."""
    from motor.estudios.extraer import META

    ultima: dict[str, dict] = {}
    for c in extracciones:
        for f in sorted(c.rglob("paginas_extraidas.jsonl")):
            for l in f.read_text(encoding="utf-8").split("\n"):
                if l.strip():
                    p = json.loads(l)
                    if p["url"] not in ultima or p["extraido"] >= ultima[p["url"]]["extraido"]:
                        ultima[p["url"]] = p
    return [{"url": u, **{k: p[k] for k in META if p.get(k) is not None}}
            for u, p in sorted(ultima.items()) if not p.get("no_es_programa") and del_dia(u, dia)]


def ejecutar(raiz: Path, salida: Path, dia: int, sello: str, max_minutos: float = 300, hoy: date | None = None,
             solo_conjunto: bool = False) -> dict:
    from motor.estudios import conjunto_masters, extraer, fichas_masters

    hoy = hoy or date.today()
    fin = time.time() + max_minutos * 60
    m = manifiesto(raiz)
    nuevo = salida / sello
    res: dict = {"dia": dia % DIAS, "sello": sello}
    extracciones = _rutas(raiz, m.get("extracciones", []))

    # 1. webs
    filas = [] if solo_conjunto else paginas_del_dia(extracciones, dia)
    muestra = salida / "trabajo" / "diario.jsonl"
    muestra.parent.mkdir(parents=True, exist_ok=True)
    muestra.write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in filas), encoding="utf-8")
    res["paginas_del_dia"] = len(filas)
    if filas:
        res["webs"] = extraer.lote(muestra, nuevo / "datos" / "estudios" / "extraccion" / "diario", esperar_min=60,
                                   hilos=24, max_minutos=min(180, (fin - time.time()) / 60 - 60),
                                   previas=extraer.huellas_previas(extracciones), navegador=True)

    # 2. QEDU
    from motor.estudios import qedu_masters

    tarjetas = None
    try:
        if solo_conjunto:
            raise LookupError("solo conjunto")
        res["qedu_tarjetas"] = qedu_masters.tarjetas(nuevo)
        tarjetas = nuevo / "datos" / "estudios" / "masters" / "qedu" / "qedu_tarjetas_master.jsonl"
    except LookupError:
        pass
    except Exception as e:  # noqa: BLE001 - sin QEDU hoy, sigue lo demás
        res["qedu_error"] = f"{type(e).__name__}: {str(e)[:200]}"
    if tarjetas and tarjetas.exists():
        todas = [json.loads(l) for l in tarjetas.read_text(encoding="utf-8").split("\n") if l.strip()]
        hoy_q = [t for t in todas if del_dia(t["codTitula"] + t["codCentro"], dia)]
        sub = salida / "trabajo" / "qedu_del_dia.jsonl"
        sub.write_text("".join(json.dumps(t, ensure_ascii=False) + "\n" for t in hoy_q), encoding="utf-8")
        res["qedu_detalles"] = qedu_masters.detalles(nuevo, sub, 0, None, max(5.0, min(60, (fin - time.time()) / 60 - 40)))

    # 3. RUCT
    if hoy >= RUCT_DIARIO_DESDE and not solo_conjunto:
        from motor.estudios import ruct

        previas = conjunto_masters.cargar_ruct(_rutas(raiz, m.get("ruct", [])))
        codigos = sorted(c for c in previas if del_dia(c, dia))
        res["ruct"] = ruct.ejecutar(codigos, nuevo, "ficha", max(5.0, min(30, (fin - time.time()) / 60 - 30)))
        cambiadas = []
        for c in codigos:
            f = nuevo / "datos" / "estudios" / "masters" / "ruct" / f"{c}.json"
            if f.exists():
                nueva = ruct.memoria_vigente(json.loads(f.read_text(encoding="utf-8"))) or {}
                vieja = ruct.memoria_vigente(previas[c]) or {}
                if nueva.get("cod") and nueva.get("cod") != vieja.get("cod"):
                    cambiadas.append(c)
        if cambiadas:
            res["ruct_memorias"] = ruct.ejecutar(cambiadas, nuevo, "memoria", max(5.0, (fin - time.time()) / 60 - 25))

    # 4. fichas y conjunto
    todas_ext = extracciones + ([nuevo] if (nuevo / "datos" / "estudios" / "extraccion").exists() else [])
    trabajo_fichas = salida / "trabajo" / "fichas"

    def opcional(clave: str) -> Path | None:
        return raiz / m[clave] if m.get(clave) and (raiz / m[clave]).exists() else None

    res["fichas"] = fichas_masters.ejecutar(todas_ext, trabajo_fichas, opcional("catalogo"), opcional("clasificacion"),
                                            opcional("censo"), opcional("altas"), opcional("tarifas"))
    fichas = next(trabajo_fichas.rglob("fichas.jsonl"))
    hay_ruct = any((nuevo / "datos" / "estudios" / "masters" / c).exists() for c in ("ruct", "ruct_memoria"))
    ruct_dirs = _rutas(raiz, m.get("ruct", [])) + ([nuevo] if hay_ruct else [])
    qedu_dirs = _rutas(raiz, m.get("qedu", [])) + ([nuevo] if (nuevo / "datos" / "estudios" / "masters" / "qedu").exists() else [])
    res["conjunto"] = {k: v for k, v in conjunto_masters.ejecutar(
        raiz / m["catalogo"], salida / ESTADO / "conjunto", opcional("altas"), ruct_dirs, qedu_dirs, fichas,
        opcional("conjunto"), fecha_catalogo=m.get("fecha_catalogo"), boe=_rutas(raiz, m.get("boe", [])),
        guias=_rutas(raiz, m.get("guias", []))).items()
        if not k.startswith("cobertura")}

    # copia del conjunto en el almacén privado (escritura única por huella: un conjunto igual no se vuelve a guardar)
    guarda = extraer.Guarda()
    if guarda.activa:
        import gzip as _gz

        res["conjunto_almacen"] = {}
        for nombre in ("masters_oficiales.jsonl.gz", "programas_no_oficiales.jsonl.gz"):
            f = salida / ESTADO / "conjunto" / nombre
            if f.exists():
                res["conjunto_almacen"][nombre] = guarda.original(
                    "conjunto-masters", _gz.decompress(f.read_bytes()), "jsonl", f"sondas:{ESTADO}/conjunto/{nombre}")
    # 5. manifiesto nuevo: lo de hoy se añade a sus listas
    m2 = {k: v for k, v in m.items() if k not in TIPOS}  # las carpetas se vuelven a buscar en la rama cada día
    m2["conjunto"] = f"{ESTADO}/conjunto"
    m2["actualizado"] = sello
    (salida / ESTADO).mkdir(parents=True, exist_ok=True)
    (salida / ESTADO / "manifiesto.json").write_text(json.dumps(m2, ensure_ascii=False, indent=1), encoding="utf-8")
    (nuevo / "diario.json").parent.mkdir(parents=True, exist_ok=True)
    (nuevo / "diario.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return res


def main() -> None:
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "carpetas":
        # para el flujo: qué traer de la rama (una ruta por línea) y la lista de carpetas por tipo
        q = argparse.ArgumentParser()
        q.add_argument("orden")
        q.add_argument("--manifiesto", required=True)
        q.add_argument("--arbol", required=True)
        q.add_argument("--salida", required=True)
        a = q.parse_args()
        m = json.loads(Path(a.manifiesto).read_text(encoding="utf-8"))
        cs = carpetas_en_arbol(Path(a.arbol).read_text(encoding="utf-8").split("\n"), m.get("desde", ""),
                               m.get("desde_por_tipo"))
        Path(a.salida).parent.mkdir(parents=True, exist_ok=True)
        Path(a.salida).write_text(json.dumps(cs, ensure_ascii=False, indent=1), encoding="utf-8")
        print("\n".join(rutas_a_traer(m, cs)))
        return
    p = argparse.ArgumentParser()
    p.add_argument("--raiz", required=True, help="carpeta con lo traído de sondas (con masters-estado/manifiesto.json)")
    p.add_argument("--dia", type=int, required=True)
    p.add_argument("--sello", required=True)
    p.add_argument("--max-minutos", type=float, default=300)
    p.add_argument("--solo-conjunto", action="store_true", help="sin pedir nada: solo rehacer fichas y conjunto")
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    print(json.dumps(ejecutar(Path(a.raiz), Path(a.salida), a.dia, a.sello, a.max_minutos,
                              solo_conjunto=a.solo_conjunto), ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
