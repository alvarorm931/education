"""Ficha de cada grado y comparativa por grado genérico, desde lo capturado (sin pedir nada a ninguna fuente).

Entradas (todas opcionales salvo el catálogo):
  - catálogo SIIU (catalogo.jsonl)                     → identidad, centros, modalidad, idioma, rama, área;
  - grados genéricos (genericos.jsonl)                 → a qué genérico pertenece cada título;
  - QEDU: tarjetas y detalles (qedu_*.jsonl)           → nota de corte, plazas, precio, inserción por centro;
  - BOE: actos y planes (boe_actos.jsonl, boe_planes.jsonl) → plan de estudios con su comprobación de créditos;
  - webs de las universidades privadas (web_privadas/{código}.json) → precio publicado por la propia universidad.

Salidas:
  - fichas.jsonl: una por grado o doble grado activo (título × universidad), con sus centros dentro;
  - comparativa.jsonl: por genérico con página, una fila por título × centro con las columnas del comparador;
  - fichas_resumen.json: cuántas fichas cumplen los datos mínimos para indexar y por qué no las demás.

Datos mínimos para indexar (propuesta, docs/modelo-grados.md §3): asignaturas comprobadas y al menos nota de corte
o precio. Lo que no los cumple se genera igual, con «indexable: false» y sus motivos.

Uso:
  python -m motor.grados.fichas --catalogo … --genericos … [--qedu carpeta] [--boe carpeta] --salida ruta/
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from motor.grados.asignaturas import comparar
from motor.grados.catalogo import clave, clave_union, nombre_corto
from motor.grados.generico import nombre_base
from motor.grados.precios import de_comunidad

FUENTE_QEDU = "Ministerio de Ciencia, Innovación y Universidades. QEDU"
FUENTE_SIIU = "Ministerio de Ciencia, Innovación y Universidades. SIIU"
FUENTE_BOE = "Agencia Estatal Boletín Oficial del Estado"


def _leer(ruta: Path) -> list[dict]:
    return [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines() if x.strip()]


def _num(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def clave_universidad(nombre: str | None) -> str:
    """«Universidad Complutense de Madrid» y «Complutense de Madrid» → «complutense madrid»."""
    u = clave(nombre)
    u = re.sub(r"^(universidad|universitat|universidade|unibertsitatea)( de| d| del| da| dels)? ", "", u)
    return " ".join(w for w in u.split() if w not in {"de", "del", "la", "les", "i", "y"})


# --------------------------------------------------------------------------------- precios de privadas

FUENTE_WEB = "Web oficial de la universidad"
# Importe por tipo que se acepta como precio (€); fuera de esto no es un precio de grado
RANGO_PRECIO = {"credito": (40, 450), "curso": (2500, 30000), "total": (8000, 160000), "mensual": (200, 3500),
                "reserva": (100, 3500)}
# Varios importes «por curso» en la misma página que se separan más de esto: no se sabe cuál es (otro grado,
# otra modalidad, con o sin descuento) y no se publica un precio, solo los candidatos
MAX_RAZON_CURSO = 1.6


def precio_web(f: dict) -> dict | None:
    """Precio de un grado privado desde su página: importes por tipo y un precio por curso orientativo.

    Orden (gana lo más comprobado; un curso a tiempo completo son 60 créditos, RD 822/2021 art. 5):
      1. un importe por curso que coincide (±2 %) con el precio del crédito × 60 de la misma página;
      2. el precio de los datos estructurados (schema.org «offers») si el texto no da otro importe por curso;
      3. los importes por curso del texto si no se separan más de MAX_RAZON_CURSO («desde» el menor) y no
         contradicen a los datos estructurados;
      4. un único precio por crédito × 60.
    Si los datos estructurados y el texto no coinciden, no se publica precio (solo los candidatos)."""
    por_tipo: dict[str, set] = defaultdict(set)
    for i in f.get("importes") or []:
        if i.get("verosimil") and i.get("tipo") in RANGO_PRECIO:
            por_tipo[i["tipo"]].add(round(float(i["valor"]), 2))
    ld = f.get("precio_jsonld") or {}
    ld_valor = _num(ld.get("precio")) if (ld.get("moneda") or "EUR").upper() == "EUR" else None
    if ld_valor and not RANGO_PRECIO["curso"][0] <= ld_valor <= RANGO_PRECIO["curso"][1]:
        ld_valor = None
    cursos = sorted(por_tipo.get("curso") or ())
    creditos = sorted(por_tipo.get("credito") or ())
    curso, metodo, nota = None, None, None
    cruzados = [c for c in cursos for k in creditos if abs(c - k * 60) <= 0.02 * c]
    if cruzados:
        curso, metodo = min(cruzados), "curso_igual_a_credito_por_60"
    elif ld_valor and (not cursos or ld_valor in cursos):
        curso, metodo = ld_valor, "datos_estructurados"
    elif cursos and not ld_valor and cursos[-1] / cursos[0] <= MAX_RAZON_CURSO:
        curso, metodo = cursos[0], "texto_por_curso"
        if len(cursos) > 1:
            nota = f"la página muestra {len(cursos)} importes por curso; se toma el menor («desde»)"
    elif not cursos and not ld_valor and len(creditos) == 1:
        curso, metodo = round(creditos[0] * 60, 2), "credito_por_60"
    elif ld_valor and cursos:
        nota = "los datos estructurados y el texto de la página dan importes distintos: no se publica precio"
    if not curso and not por_tipo and not ld_valor:
        return None
    return {
        "precio_curso": curso,
        "metodo": metodo,
        "nota": nota,
        "importes": {k: sorted(v) for k, v in sorted(por_tipo.items())},
        "precio_jsonld": ld_valor,
        "url": f.get("url"),
    }


def indexar_web_privadas(carpeta: Path | None) -> dict[str, dict]:
    """código → precio de la web de su universidad privada. Con varios rastreos gana el más reciente (las
    carpetas de sondas empiezan por la fecha); la fecha de captura es la del rastreo."""
    salida: dict[str, dict] = {}
    if not carpeta:
        return salida
    for f in sorted(carpeta.rglob("web_privadas/[0-9]*.json"), key=lambda x: str(x)):
        d = json.loads(f.read_text(encoding="utf-8"))
        m = re.search(r"(\d{4})(\d{2})(\d{2})T\d{6}", str(f))
        fecha = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None
        for cod, fi in (d.get("fichas") or {}).items():
            p = precio_web(fi)
            if p:
                salida[cod] = {**p, "fuente": FUENTE_WEB, "universidad": d.get("universidad"), "capturado": fecha}
            elif cod in salida and salida[cod]["url"] != fi.get("url"):
                del salida[cod]  # el rastreo nuevo lleva a otra página sin precio: el viejo ya no vale
    return salida


# --------------------------------------------------------------------------------------------- QEDU


def indexar_qedu(carpeta: Path | None) -> tuple[dict, dict]:
    """(título, centro) → tarjeta y (título, centro) → detalle."""
    tarjetas, detalles = {}, {}
    if not carpeta:
        return tarjetas, detalles
    for f in sorted(carpeta.rglob("qedu_tarjetas_*.jsonl")):
        for t in _leer(f):
            tarjetas[(t["codTitula"], t["codCentro"])] = t
    for f in sorted(carpeta.rglob("qedu_detalles_*.jsonl")):
        for d in _leer(f):
            detalles[(d["codTitula"], d["codCentro"])] = d
    return tarjetas, detalles


def centro_qedu(t: dict, d: dict | None) -> dict:
    det = (d or {}).get("detalle") or {}
    ins = (d or {}).get("insercion") or {}
    nota = det.get("nota_corte") if det else _num(t.get("notaCorte"))
    return {
        "codigo": t["codCentro"],
        "centro": t.get("nombreCentro"),
        "tipo_centro": t.get("tipoCentro"),
        "provincia": t.get("provincia"),
        "nota_corte": nota,
        "nota_corte_anterior": det.get("nota_corte_anterior"),
        "nota_media_admision": det.get("nota_media_admision"),
        "curso": det.get("curso") or t.get("anio"),
        "curso_anterior": det.get("curso_anterior"),
        "plazas": det.get("plazas"),
        "precio_credito": det.get("precio_credito"),
        "creditos": det.get("creditos"),
        "modalidad": det.get("modalidad"),
        "insercion": {k: v for k, v in ins.items() if v is not None} or None,
        "fuente": {"cita": FUENTE_QEDU, "capturado": ((d or {}).get("fuente") or t.get("fuente") or {}).get("capturado")},
    }


# ------------------------------------------------------------------------------------- indicadores SIIU

# Indicador del SIIU → clave de la ficha. Se publica el último curso con dato y la media de España en el ámbito.
INDICADORES = {
    "Tasa global de abandono": "abandono",
    "Tasa de abandono el 1º año": "abandono_primer_ano",
    "Tasa global de cambio": "cambio_de_estudio",
    "Tasa global de abandono del SUE": "abandono_universidad",
    "Tasa de graduación en grados de 4 años": "graduacion",
    "Tasa de graduación en grados de 5 años": "graduacion",
    "Tasa de rendimiento": "rendimiento",
    "Tasa de éxito": "exito",
    "Nota media": "nota_media_expediente",
    "Duración media en estudios de Grado de 4 años": "duracion_media",
    "Duración media de estudios de Grado de 5 años": "duracion_media",
    "Tasa de transición Grado Máster": "transicion_master",
}
FICHEROS_INDICADORES = ("abandono", "cambio", "abandono_sistema", "graduacion", "rendimiento", "nota_expediente",
                        "duracion", "transicion_master")


def indexar_indicadores(carpeta: Path | None) -> dict[tuple[str, str], dict]:
    """(universidad, ámbito) → {clave: {valor, curso, indicador}} con el último curso que tiene dato.
    La clave («todas», ámbito) guarda la media de todas las universidades para comparar."""
    salida: dict[tuple[str, str], dict] = defaultdict(dict)
    if not carpeta:
        return salida
    for nombre in FICHEROS_INDICADORES:
        for f in carpeta.rglob(f"{nombre}.jsonl"):
            for x in _leer(f):
                k = INDICADORES.get(x.get("Indicador"))
                if not k or x.get("valor") is None:
                    continue
                if nombre == "eficiencia" and k == "exito":
                    continue  # el éxito de egresados no se mezcla con el de matriculados
                u = x.get("Universidad") or x.get("Universidades") or ""  # el nombre cambia según la tabla
                cu = "todas" if u in ("Todas las universidades", "Total") else clave_universidad(u)  # según la tabla
                ambito = x.get("Ámbito de estudio")
                actual = salida[(cu, ambito)].get(k)
                if actual is None or (x["Periodo"], x["Indicador"]) > (actual["curso"], actual["indicador"]):
                    salida[(cu, ambito)][k] = {"valor": round(x["valor"], 2), "curso": x["Periodo"],
                                               "indicador": x["Indicador"]}
    return salida


def indicadores_de(t: dict, ind: dict, por_ambito: Counter) -> dict | None:
    if not ind:
        return None
    u = clave_universidad(t["universidades"][0]["nombre"])
    datos = ind.get((u, t.get("ambito")))
    if not datos:
        return None
    espana = ind.get(("todas", t.get("ambito")), {})
    return {
        "ambito": t.get("ambito"),
        "grados_de_la_universidad_en_el_ambito": por_ambito[(u, t.get("ambito"))],
        "valores": {k: {**v, "media_espana_ambito": (espana.get(k) or {}).get("valor")} for k, v in datos.items()},
        "fuente": {"cita": "Ministerio de Ciencia, Innovación y Universidades. Indicadores de rendimiento académico (SIIU)"},
    }


# ---------------------------------------------------------------------------------------------- BOE


def indexar_planes(carpeta: Path | None) -> dict[tuple[str, str], list[dict]]:
    """(universidad, grado) normalizados → planes del BOE leídos, del más reciente al más antiguo."""
    if not carpeta:
        return {}
    actos = {}
    for f in carpeta.rglob("boe_actos.jsonl"):
        for a in _leer(f):
            actos[a["identificador"]] = a
    salida: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for f in carpeta.rglob("boe_planes.jsonl"):
        for p in _leer(f):
            a = actos.get(p["identificador"])
            if not a or not a.get("titulo_grado") or not a.get("universidad"):
                continue
            k = (clave_universidad(a["universidad"]), clave_union(nombre_base(nombre_corto(a["titulo_grado"]))))
            salida[k].append({**p, "fecha": a.get("fecha"), "universidad_boe": a["universidad"]})
    for k in salida:
        salida[k].sort(key=lambda p: p.get("fecha") or "", reverse=True)
    return salida


def plan_comprobado(p: dict) -> bool:
    esp = p.get("esperado_sin_optativas")
    return bool(esp) and abs((p.get("suma_sin_optativas") or 0) - esp) <= 0.5


def resumen_plan(p: dict) -> dict:
    filas = p.get("plan") or []
    return {
        "boe": p["identificador"],
        "fecha": p.get("fecha"),
        "tipo": p.get("tipo"),
        "comprobado": plan_comprobado(p),
        "distribucion": p.get("distribucion"),
        "asignaturas": [{k: f.get(k) for k in ("nombre", "modulo", "tipo", "creditos", "curso", "semestre")}
                        for f in filas],
        "menciones": p.get("menciones") or [],
        "fuente": {"cita": FUENTE_BOE, "url": f"https://www.boe.es/diario_boe/txt.php?id={p['identificador']}"},
    }


# -------------------------------------------------------------------------------------------- fichas


def construir(catalogo: list[dict], genericos: list[dict], tarjetas: dict, detalles: dict,
              planes: dict, ind: dict | None = None, web: dict | None = None) -> tuple[list[dict], list[dict]]:
    gen_de = {c: g for g in genericos for c in g["titulos"]}
    por_ambito = Counter((clave_universidad(t["universidades"][0]["nombre"]), t.get("ambito")) for t in catalogo
                         if t["situacion"] == "Activo" and t["clase"] == "grado")
    qedu_por_titulo: dict[str, list] = defaultdict(list)
    for (tit, cen), t in tarjetas.items():
        qedu_por_titulo[tit].append(centro_qedu(t, detalles.get((tit, cen))))
    fichas = []
    for t in catalogo:
        if t["situacion"] != "Activo" or t["clase"] not in ("grado", "doble"):
            continue
        g = gen_de.get(t["codigo"])
        centros = sorted(qedu_por_titulo.get(t["codigo"], []), key=lambda c: c["codigo"])
        # plan del BOE: el más reciente comprobado de esa universidad y ese grado; si no hay, el más reciente
        plan = None
        if t["clase"] == "grado":
            candidatos = []
            for u in t["universidades"]:
                candidatos += planes.get((clave_universidad(u["nombre"]), clave_union(nombre_base(t["nombre"]))), [])
            if candidatos:
                plan = resumen_plan(next((p for p in candidatos if plan_comprobado(p)), candidatos[0]))
        notas = [c["nota_corte"] for c in centros if c["nota_corte"] is not None]
        precios = [c["precio_credito"] for c in centros if c["precio_credito"]]
        creditos = next((c["creditos"] for c in centros if c["creditos"]), None)
        motivos = []
        if not (plan and plan["comprobado"]):
            motivos.append("sin asignaturas comprobadas" if not plan else "plan sin cuadrar con su tabla de créditos")
        pweb = (web or {}).get(t["codigo"]) if t["universidad_tipo"] == "Privada" else None
        if not notas and not precios and not (pweb and pweb["precio_curso"]):
            motivos.append("sin nota de corte ni precio")
        fichas.append({
            "codigo": t["codigo"],
            "clase": t["clase"],
            "nombre": t["nombre"],
            "nombre_oficial": t["nombre_oficial"],
            "universidades": t["universidades"],
            "universidad_tipo": t["universidad_tipo"],
            "rama": t["rama"],
            "area": t["campo"],
            "generico": g and {"id": g["id"], "nombre": g["nombre"], "pagina_propia": g["pagina_propia"]},
            "componentes": t.get("componentes") or [],
            "modalidades": sorted({i["presencialidad"] for i in t["imparticiones"] if i["situacion"] == "Activo"} - {None}),
            "idioma_extranjero": sorted({i["idioma_extranjero"] for i in t["imparticiones"]
                                         if (i["idioma_extranjero"] or "").startswith("Sí")}),
            "centros": centros,
            "precio_primera_matricula": round(min(precios) * creditos, 2) if precios and creditos else None,
            "precio_web": pweb,
            "bonificacion": de_comunidad(t["universidades"][0].get("comunidad")) if t["universidad_tipo"] == "Pública" else None,
            "plan": plan,
            "indicadores": indicadores_de(t, ind or {}, por_ambito) if t["clase"] == "grado" else None,
            "indexable": not motivos,
            "motivos_noindex": motivos,
            "fuente_catalogo": {"cita": FUENTE_SIIU, **{k: t["fuente"].get(k) for k in ("url", "curso", "capturado")}},
        })
    # comparativa por genérico con página
    por_gen: dict[str, list] = defaultdict(list)
    for f in fichas:
        if f["generico"] and f["generico"]["pagina_propia"]:
            for c in f["centros"] or [{}]:
                por_gen[f["generico"]["id"]].append({
                    "codigo": f["codigo"], "universidad": f["universidades"][0]["nombre"],
                    "tipo": f["universidad_tipo"], "centro": c.get("centro"), "provincia": c.get("provincia"),
                    "nota_corte": c.get("nota_corte"), "nota_corte_anterior": c.get("nota_corte_anterior"),
                    "plazas": c.get("plazas"), "precio_credito": c.get("precio_credito"),
                    "precio_curso_web": (f.get("precio_web") or {}).get("precio_curso"),
                    "afiliacion": (c.get("insercion") or {}).get("tasa_afiliacion"),
                    "base_media_cotizacion": (c.get("insercion") or {}).get("base_media_cotizacion"),
                    "practicas_externas": ((f["plan"] or {}).get("distribucion") or {}).get("practicas_externas"),
                    "optativas": ((f["plan"] or {}).get("distribucion") or {}).get("optativas"),
                    "modalidades": f["modalidades"],
                    "abandono": (((f.get("indicadores") or {}).get("valores") or {}).get("abandono") or {}).get("valor"),
                    "graduacion": (((f.get("indicadores") or {}).get("valores") or {}).get("graduacion") or {}).get("valor"),
                })
    comparativa = []
    nombres = {g["id"]: g["nombre"] for g in genericos}
    por_codigo = {f["codigo"]: f for f in fichas}
    for gid, filas in por_gen.items():
        filas.sort(key=lambda x: (x["nota_corte"] is None, -(x["nota_corte"] or 0)))
        # asignaturas comparadas: solo con planes comprobados (la suma cuadra con su tabla de créditos)
        planes_ok = {f["codigo"]: f["plan"]["asignaturas"] for f in fichas
                     if f["generico"] and f["generico"]["id"] == gid and f["plan"] and f["plan"]["comprobado"]}
        cuadro = comparar(planes_ok) if len(planes_ok) >= 2 else None
        if cuadro:
            for c, v in cuadro["por_titulo"].items():
                por_codigo[c]["asignaturas_comparadas"] = {**v, "planes_comparados": cuadro["planes_comparados"]}
        comparativa.append({"generico": gid, "nombre": nombres.get(gid), "filas": filas,
                            "universidades": len({x["universidad"] for x in filas}),
                            "asignaturas": cuadro and {"planes_comparados": cuadro["planes_comparados"],
                                                       "comunes": cuadro["asignaturas_comunes"][:60]}})
    comparativa.sort(key=lambda x: -len(x["filas"]))
    return fichas, comparativa


def resumen(fichas: list[dict], comparativa: list[dict]) -> dict:
    return {
        "fichas": len(fichas),
        "por_clase": dict(Counter(f["clase"] for f in fichas)),
        "con_centros_qedu": sum(1 for f in fichas if f["centros"]),
        "con_nota_de_corte": sum(1 for f in fichas if any(c["nota_corte"] is not None for c in f["centros"])),
        "con_precio": sum(1 for f in fichas if f["precio_primera_matricula"]),
        "privadas": sum(1 for f in fichas if f["universidad_tipo"] == "Privada"),
        "privadas_con_pagina_y_algun_importe": sum(1 for f in fichas if f.get("precio_web")),
        "privadas_con_precio_por_curso": sum(1 for f in fichas if (f.get("precio_web") or {}).get("precio_curso")),
        "privadas_precio_por_metodo": dict(Counter((f.get("precio_web") or {}).get("metodo") for f in fichas
                                                   if (f.get("precio_web") or {}).get("precio_curso"))),
        "con_bonificacion_o_ayuda": sum(1 for f in fichas if f.get("bonificacion")),
        "con_insercion": sum(1 for f in fichas if any(c.get("insercion") for c in f["centros"])),
        "con_indicadores_siiu": sum(1 for f in fichas if f.get("indicadores")),
        "indicadores_solo_de_ese_grado": sum(1 for f in fichas if f.get("indicadores")
                                            and f["indicadores"]["grados_de_la_universidad_en_el_ambito"] == 1),
        "con_plan_boe": sum(1 for f in fichas if f["plan"]),
        "con_plan_comprobado": sum(1 for f in fichas if f["plan"] and f["plan"]["comprobado"]),
        "indexables": sum(1 for f in fichas if f["indexable"]),
        "motivos_noindex": dict(Counter(m for f in fichas for m in f["motivos_noindex"])),
        "comparativas": len(comparativa),
        "comparativas_con_asignaturas": sum(1 for c in comparativa if c.get("asignaturas")),
        "filas_comparativa": sum(len(c["filas"]) for c in comparativa),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--catalogo", required=True)
    p.add_argument("--genericos", required=True)
    p.add_argument("--qedu", help="carpeta con qedu_tarjetas_*.jsonl y qedu_detalles_*.jsonl")
    p.add_argument("--boe", help="carpeta con boe_actos.jsonl y boe_planes.jsonl")
    p.add_argument("--indicadores", help="carpeta con los indicadores del SIIU (abandono.jsonl, …)")
    p.add_argument("--web-privadas", help="carpeta con los rastreos de webs privadas (…/web_privadas/{código}.json)")
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    tarjetas, detalles = indexar_qedu(Path(a.qedu) if a.qedu else None)
    fichas, comparativa = construir(_leer(Path(a.catalogo)), _leer(Path(a.genericos)), tarjetas, detalles,
                                    indexar_planes(Path(a.boe) if a.boe else None),
                                    indexar_indicadores(Path(a.indicadores) if a.indicadores else None),
                                    indexar_web_privadas(Path(a.web_privadas) if a.web_privadas else None))
    destino = Path(a.salida) / "datos" / "estudios" / "grados"
    destino.mkdir(parents=True, exist_ok=True)
    for nombre, datos in (("fichas.jsonl", fichas), ("comparativa.jsonl", comparativa)):
        with (destino / nombre).open("w", encoding="utf-8") as f:
            for x in datos:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
    res = resumen(fichas, comparativa)
    (destino / "fichas_resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
