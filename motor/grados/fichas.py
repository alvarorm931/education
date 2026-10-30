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
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from motor.grados.asignaturas import comparar
from motor.grados.catalogo import clave, clave_union, nombre_corto
from motor.grados.generico import nombre_base
from motor.grados.precios import de_comunidad, precio_doble, precio_por_rama, precio_unico
from motor.grados.web_privadas import SEDES, palabras_url, sede_ajena, titulo_contradice

FUENTE_QEDU = "Ministerio de Ciencia, Innovación y Universidades. QEDU"
URL_QEDU = "https://www.ciencia.gob.es/qedu.html"
FUENTE_SIIU = "Ministerio de Ciencia, Innovación y Universidades. SIIU"
FUENTE_BOE = "Agencia Estatal Boletín Oficial del Estado"


def _leer(ruta: Path) -> list[dict]:
    return [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines() if x.strip()]


def _num(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


# Nombres de universidad del BOE que no se parecen al del catálogo
ALIAS_UNIVERSIDAD = {"valencia": "valencia estudi general", "valencia estudi general": "valencia estudi general"}


def clave_universidad(nombre: str | None) -> str:
    """«Universidad Complutense de Madrid» y «Complutense de Madrid» → «complutense madrid»; «Universidad de las
    Illes Balears» → «illes balears»; «Universidad de Vic-Universidad Central de Catalunya» → «vic central
    catalunya»; «Universitat de València» → «valencia estudi general» (el nombre del catálogo)."""
    u = clave(nombre)
    u = re.sub(r"^(universidad|universitat|universidade|unibertsitatea)( de| d| del| da| dels)? ", "", u)
    u = " ".join(w for w in u.split() if w not in {"de", "del", "la", "las", "los", "el", "les", "l", "i", "y",
                                                     "universidad", "universitat"})
    return ALIAS_UNIVERSIDAD.get(u, u)


# --------------------------------------------------------------------------------- precios de privadas

FUENTE_WEB = "Web oficial de la universidad"
# Importe por tipo que se acepta como precio (€); fuera de esto no es un precio de grado
RANGO_PRECIO = {"credito": (40, 450), "curso": (2500, 30000), "total": (8000, 160000), "mensual": (200, 3500),
                "reserva": (100, 3500)}
# Varios importes «por curso» en la misma página que se separan más de esto: no se sabe cuál es (otro grado,
# otra modalidad, con o sin descuento) y no se publica un precio, solo los candidatos
MAX_RAZON_CURSO = 1.6


# métodos cuyo precio por curso es el precio del crédito × 60: el total del grado es el crédito × sus créditos
METODOS_POR_CREDITO = {"curso_igual_a_credito_por_60", "credito_por_60_mas_matricula", "credito_por_60_de_la_tabla"}


def precio_por_cuentas(valores: list[float]) -> dict | None:
    """Precio por curso cuando los importes de la misma página o fila cuadran entre sí, sin fiarse de su rótulo:
      - un importe es el crédito × 60 de otro (curso = 60 créditos): «172 € | 10.320 €»;
      - un importe es el crédito × 60 más otro (la matrícula o reserva): «130 € | 700 € | 8.500 €» → 7.800 € de
        enseñanza más 700 € de matrícula;
      - un importe es otro (reserva) más entre 8 y 12 cuotas iguales de un tercero: «1.500 € | 1.047 € | 11.970 €».
    Con varias soluciones (modalidades, idiomas) se da la menor («desde»)."""
    v = sorted({round(float(x), 2) for x in valores})
    creditos = [x for x in v if RANGO_PRECIO["credito"][0] <= x <= RANGO_PRECIO["credito"][1]]
    cursos = [x for x in v if RANGO_PRECIO["curso"][0] <= x <= RANGO_PRECIO["curso"][1]]
    pequenos = [x for x in v if 100 <= x <= 3500]
    cerca = lambda a, b: abs(a - b) <= max(1.0, 0.001 * b)  # noqa: E731
    a = sorted({k for k in cursos for c in creditos if cerca(c * 60, k)})
    if a:
        return {"precio_curso": a[0], "metodo": "curso_igual_a_credito_por_60", "soluciones": len(a)}
    b = sorted({(round(c * 60, 2), k, r) for c in creditos for r in pequenos for k in cursos if cerca(c * 60 + r, k)})
    if b:
        return {"precio_curso": b[0][0], "metodo": "credito_por_60_mas_matricula", "matricula_o_reserva": b[0][2],
                "primer_curso_con_matricula": b[0][1], "soluciones": len(b)}
    c = sorted({k for k in cursos for r in pequenos for m in pequenos if m != r
                for n in range(8, 13) if abs(r + n * m - k) <= 2})
    if c:
        return {"precio_curso": c[0], "metodo": "reserva_mas_cuotas", "soluciones": len(c)}
    # el total anual es la reserva más la matrícula más 8 a 12 cuotas iguales (Alfonso X: «24.250 € | 3.000 € |
    # 1.350 € | 10 | 1.990 €»): el precio del curso es ese total, que se paga cada año
    d = sorted({k for k in cursos for r in pequenos for m in pequenos for q in pequenos if len({r, m, q}) == 3
                for n in range(8, 13) if abs(r + m + n * q - k) <= 2})
    if d:
        return {"precio_curso": d[0], "metodo": "reserva_matricula_y_cuotas", "soluciones": len(d)}
    return None


def precio_por_cuentas_con_miles(valores: list[float], alternativas: list[tuple[float, float]]) -> dict | None:
    """Como precio_por_cuentas, y si no cuadra, con la otra lectura de un importe escrito con el espacio normal entre
    miles («1 100 €», que se lee 100): solo una cifra a la vez, la otra lectura no puede ser el precio que sale y
    tiene que haber una sola solución entre todas las sustituciones (Alfonso X: «11.730 € | 800 € | 1 100 € | 10 983
    €» → 800 + 1.100 + 10 × 983 = 11.730)."""
    directo = precio_por_cuentas(valores)
    if directo or not alternativas:
        return directo
    halladas = {}
    for corto, largo in alternativas:
        resto = list(valores)
        if corto not in resto:
            continue
        resto[resto.index(corto)] = largo
        c = precio_por_cuentas(resto)
        if c and abs(c["precio_curso"] - largo) > 0.01:
            halladas[c["precio_curso"]] = {**c, "metodo": c["metodo"] + "_con_miles_separados_por_espacio",
                                           "importe_releido": {"leido": corto, "como": largo}}
    return next(iter(halladas.values())) if len(halladas) == 1 else None


def precio_web(f: dict) -> dict | None:
    """Precio de un grado privado desde su página: importes por tipo y un precio por curso orientativo.

    Orden (gana lo más comprobado; un curso a tiempo completo son 60 créditos, RD 822/2021 art. 5):
      1. un importe por curso que coincide (±2 %) con el precio del crédito × 60 de la misma página;
      2. el precio de los datos estructurados (schema.org «offers») si el texto no da otro importe por curso;
      3. los importes por curso del texto si no se separan más de MAX_RAZON_CURSO («desde» el menor) y no
         contradicen a los datos estructurados;
    Un único precio por crédito sin otra cifra que lo confirme no se publica (queda entre los candidatos).
    Si los datos estructurados y el texto no coinciden, no se publica precio (solo los candidatos)."""
    por_tipo: dict[str, set] = defaultdict(set)
    desde = [i for i in f.get("importes") or [] if i.get("desde")]
    for i in f.get("importes") or []:
        if i.get("verosimil") and i.get("tipo") in RANGO_PRECIO and not i.get("desde"):
            por_tipo[i["tipo"]].add(round(float(i["valor"]), 2))
    if desde and not por_tipo:
        return {"precio_curso": None, "metodo": None, "url": f.get("url"), "precio_jsonld": None,
                "importes": {}, "nota": "la página solo da un importe «desde» (mínimo o promoción): no se publica precio"}
    ld = f.get("precio_jsonld") or {}
    ld_valor = _num(ld.get("precio")) if (ld.get("moneda") or "EUR").upper() == "EUR" else None
    if ld_valor and not RANGO_PRECIO["curso"][0] <= ld_valor <= RANGO_PRECIO["curso"][1]:
        ld_valor = None
    cursos = sorted(por_tipo.get("curso") or ())
    creditos = sorted(por_tipo.get("credito") or ())
    curso, metodo, nota = None, None, None
    cruzados = [c for c in cursos for k in creditos if abs(c - k * 60) <= 0.02 * c]
    cuentas = precio_por_cuentas([i["valor"] for i in f.get("importes") or [] if i.get("tipo") != "sueldo"])
    if cruzados:
        curso, metodo = min(cruzados), "curso_igual_a_credito_por_60"
    elif cuentas and (not ld_valor or abs(ld_valor - cuentas["precio_curso"]) <= 0.5):
        curso, metodo = cuentas["precio_curso"], cuentas["metodo"]
    elif ld_valor and ld_valor in cursos:
        # los datos estructurados valen si la página muestra ese mismo importe: solos no (verificación del 30/10:
        # una página con «Precio: Consultar» llevaba en sus datos estructurados un «desde» de promoción)
        curso, metodo = ld_valor, "datos_estructurados"
    elif ld_valor and not cursos:
        nota = "solo los datos estructurados de la página dan un importe y su texto no lo muestra: no se publica precio"
    elif cursos and not ld_valor and cursos[-1] / cursos[0] <= MAX_RAZON_CURSO:
        curso, metodo = cursos[0], "texto_por_curso"
        if len(cursos) > 1:
            nota = f"la página muestra {len(cursos)} importes por curso; se toma el menor («desde»)"
    elif not cursos and not ld_valor and len(creditos) == 1:
        # un precio por crédito suelto, sin otra cifra que lo confirme: no se publica. Medido el 30/10/2026: 2 de
        # 7 eran otra cosa (350 € de una reserva leídos como crédito, 21.000 € al año en vez de unos 6.000)
        nota = "solo un precio por crédito, sin otra cifra de la página que lo confirme: no se publica precio"
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
                salida[cod] = {**p, "fuente": FUENTE_WEB, "universidad": d.get("universidad"), "capturado": fecha,
                               "_titulo": fi.get("titulo"), "centro": d.get("centro"),
                               "centro_adscrito": bool(d.get("centro_adscrito"))}
            elif cod in salida and salida[cod]["url"] != fi.get("url"):
                del salida[cod]  # el rastreo nuevo lleva a otra página sin precio: el viejo ya no vale
    return salida


def indexar_paginas_privadas(carpeta: Path | None) -> dict[str, dict]:
    """código → página del grado en la web de su universidad privada, con lo que pide su formulario. Sirve para
    decir un hecho verdadero cuando no hay precio: «la universidad no publica el precio en la página del grado;
    su formulario pide correo y teléfono» (docs/estrategia-informacion-cerrada.md §2.6)."""
    salida: dict[str, dict] = {}
    if not carpeta:
        return salida
    for f in sorted(carpeta.rglob("web_privadas/[0-9]*.json"), key=lambda x: str(x)):
        d = json.loads(f.read_text(encoding="utf-8"))
        m = re.search(r"(\d{4})(\d{2})(\d{2})T\d{6}", str(f))
        fecha = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None
        for cod, fi in (d.get("fichas") or {}).items():
            if fi.get("estado") == 200:
                salida[cod] = {"url": fi.get("url"), "formulario_pide_correo": bool(fi.get("formulario_pide_correo")),
                               "formulario_pide_telefono": bool(fi.get("formulario_pide_telefono")),
                               "da_algun_importe": any(i.get("verosimil") for i in fi.get("importes") or []),
                               "capturado": fecha, "_titulo": fi.get("titulo")}
    return salida


def indexar_tarifas(carpeta: Path | None) -> dict[str, dict]:
    """código → precio leído en los PDF o páginas de precios de su universidad (tarifas_grado.py). Entre varios
    documentos gana el del curso más reciente que dé un precio por curso."""
    candidatos: dict[str, list] = defaultdict(list)
    if not carpeta:
        return {}
    from motor.grados.tarifas_grado import CURSO_CONOCIDO as cursos_conocidos
    from motor.grados.tarifas_grado import LECTURA_CONOCIDA as lecturas  # capturas anteriores a la regla
    for f in sorted(carpeta.rglob("tarifas_grado/tarifas.jsonl"), key=lambda x: str(x)):
        m = re.search(r"(\d{4})(\d{2})(\d{2})T\d{6}", str(f))
        fecha = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None
        carpeta_f = m.group(0) if m else ""
        for doc in _leer(f):
            for cod, importes in (doc.get("grados") or {}).items():
                # en las listas de precios el rótulo de cada cifra no es fiable: solo vale si las cifras de un mismo
                # bloque (la línea del grado y las de solo cifras que la siguen) cuadran entre sí; entre bloques,
                # la menor
                por_bloque: dict = defaultdict(list)
                miles: dict = defaultdict(list)
                for i in importes:
                    if i.get("tipo") != "sueldo":
                        por_bloque[i.get("bloque", i.get("linea_sha256"))].append(i["valor"])
                        if i.get("miles_con_espacio"):
                            miles[i.get("bloque", i.get("linea_sha256"))].append((i["valor"], i["miles_con_espacio"]))
                soluciones = [c for c in (precio_por_cuentas_con_miles(v, miles.get(b) or [])
                                          for b, v in por_bloque.items()) if c]
                cuentas = min(soluciones, key=lambda c: c["precio_curso"]) if soluciones else None
                releido = (cuentas or {}).get("importe_releido")
                p = cuentas and {**cuentas, "url": doc["url"],
                                 "nota": releido and (f"el documento escribe los miles con un espacio; "
                                                      f"{releido['leido']:,.0f} € se lee {releido['como']:,.0f} € porque solo "
                                                      f"así cuadran las cifras del grado").replace(",", "."),
                                 "importes": sorted({i["valor"] for i in importes}), "precio_jsonld": None}
                if not p and (doc.get("lectura") or lecturas.get(doc["url"])) == "importe_anual_mayor_de_la_linea":
                    # documento comprobado a mano (tarifas_grado.LECTURA_CONOCIDA): cada grado da en su línea el
                    # importe anual o de 60 créditos, el único de su línea en el rango de un curso (con dos, como
                    # presencial y semipresencial, no se sabe cuál es cuál: no se publica)
                    anual = {i["valor"] for i in importes if i.get("tipo") != "sueldo"
                             and RANGO_PRECIO["curso"][0] <= i["valor"] <= RANGO_PRECIO["curso"][1]}
                    p = len(anual) == 1 and {"precio_curso": anual.pop(), "metodo": "importe_anual_del_documento", "nota": None,
                                   "url": doc["url"], "importes": sorted({i["valor"] for i in importes}),
                                   "precio_jsonld": None}
                if not p and (doc.get("lectura") or lecturas.get(doc["url"])) == "credito_anual_de_la_tabla":
                    # tabla comprobada a mano con el precio del crédito de cada titulación y nada más: un curso son
                    # 60 créditos (RD 822/2021)
                    cred = {i["valor"] for i in importes if i.get("tipo") != "sueldo"
                            and RANGO_PRECIO["credito"][0] <= i["valor"] <= RANGO_PRECIO["credito"][1]}
                    p = len(cred) == 1 and {"precio_curso": round(next(iter(cred)) * 60, 2),
                                            "metodo": "credito_por_60_de_la_tabla", "nota": None, "url": doc["url"],
                                            "importes": sorted({i["valor"] for i in importes}), "precio_jsonld": None}
                if not p and doc.get("formato") == "html" and len(doc.get("grados") or {}) == 1:
                    # página de precios de un solo grado: valen las reglas de la página del grado (tipo por contexto)
                    p = precio_web({"url": doc["url"], "importes": importes})
                    p = p if p and p["precio_curso"] else None
                if p:
                    conocido = cursos_conocidos.get(doc["url"]) or {}
                    if conocido.get("nota"):
                        p = {**p, "nota": conocido["nota"]}
                    candidatos[cod].append({**p, "_carpeta": carpeta_f, "fuente": "Tarifas publicadas por la universidad",
                                            "formato": doc.get("formato") or "pdf",
                                            "curso_documento": conocido.get("curso") or doc.get("curso_documento"),
                                            "universidad": doc.get("universidad"), "capturado": fecha,
                                            **({"centro": doc["centro"], "centro_adscrito": bool(doc.get("centro_adscrito"))}
                                               if doc.get("centro") else {})})
    salida = {}
    for cod, ps in candidatos.items():
        # el curso más reciente; a igualdad, la lectura más reciente (las reglas de lectura mejoran)
        ps.sort(key=lambda p: (p["precio_curso"] is not None, p.get("curso_documento") or "", p.get("_carpeta") or ""),
                reverse=True)
        salida[cod] = {k: v for k, v in ps[0].items() if k != "_carpeta"}
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
        "fuente": {"cita": FUENTE_QEDU, "url": URL_QEDU,
                   "capturado": ((d or {}).get("fuente") or t.get("fuente") or {}).get("capturado")},
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
                    fu = x.get("fuente") or {}
                    salida[(cu, ambito)][k] = {"valor": round(x["valor"], 2), "curso": x["Periodo"],
                                               "indicador": x["Indicador"], "url": fu.get("url"),
                                               "capturado": fu.get("capturado")}
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


def indexar_planes(carpeta: Path | None, conocidas: set[str] | None = None) -> dict[tuple[str, str], list[dict]]:
    """(universidad, grado) normalizados → planes del BOE leídos, del más reciente al más antiguo. La universidad
    del BOE se resuelve contra las del catálogo («pais vasco» → «pais vasco euskal herriko unibertsitatea»)."""
    from motor.grados.planes import resolver_universidad

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
            # en las resoluciones con varios planes el título sale de cada anexo (boe_grados.separar_planes)
            titulo = p.get("titulo_grado") or (a or {}).get("titulo_grado")
            if not a or not titulo or not a.get("universidad"):
                continue
            k = (resolver_universidad(clave_universidad(a["universidad"]), conocidas or set()),
                 clave_union(nombre_base(nombre_corto(titulo))))
            salida[k].append({**p, "fecha": a.get("fecha"), "universidad_boe": a["universidad"]})
    for k in salida:
        salida[k].sort(key=lambda p: p.get("fecha") or "", reverse=True)
    return salida


def planes_por_identificador(carpeta: Path | None) -> dict[str, list[dict]]:
    """Identificador del BOE → planes leídos (varios si la resolución trae varios planes)."""
    salida: dict[str, list[dict]] = defaultdict(list)
    if not carpeta:
        return salida
    for f in carpeta.rglob("boe_planes.jsonl"):
        for p in _leer(f):
            salida[p["identificador"]].append(p)
    return salida


# ------------------------------------------------------------------------------------------------ RUCT

FUENTE_RUCT = "Ministerio de Ciencia, Innovación y Universidades. Registro de Universidades, Centros y Títulos (RUCT)"


def indexar_ruct(carpeta: Path | None) -> dict[str, dict]:
    """Código del título → ficha del RUCT (créditos por tipo, verificación, acreditaciones, BOE del plan).
    Con varias capturas gana la más reciente."""
    salida: dict[str, dict] = {}
    if not carpeta:
        return salida
    for f in sorted(carpeta.rglob("ruct/[0-9]*.json"), key=lambda x: str(x)):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("codigo"):
            salida[str(d["codigo"])] = d
    return salida


def resumen_ruct(d: dict | None) -> dict | None:
    if not d:
        return None
    cr = d.get("creditos") or {}
    otros = [cr.get(k) for k in ("obligatorios", "optativos", "practicas_externas", "tfm")]
    basica = round(cr["total"] - sum(x or 0 for x in otros), 1) if cr.get("total") and any(otros) else None
    acred = sorted(d.get("acreditaciones") or [], key=lambda a: a.get("fecha") or "")
    return {
        "creditos": {**{{"tfm": "tfg"}.get(k, k): v for k, v in cr.items() if v is not None},  # en grado es el TFG
                     **({"formacion_basica_calculada": basica} if basica and basica > 0 else {})},
        "fecha_verificacion": d.get("fecha_verificacion"),
        "curso_inicio": d.get("curso_inicio"),
        "ultima_acreditacion": acred[-1] if acred else None,
        "extincion": d.get("extincion") or [],
        "boe_plan": ((d.get("boe") or {}).get("plan") or {}).get("identificador"),
        "fuente": {"cita": FUENTE_RUCT, "url": (d.get("fuente") or {}).get("url"),
                   "capturado": (d.get("fuente") or {}).get("capturado")},
    }


PAREJAS_DIST = {"obligatorias": ("obligatorios", "obligatoria"), "optativas": ("optativos", None),
                "practicas_externas": ("practicas_externas", "practicas"), "tfg": ("tfg", "tfg")}


def corregir_distribucion(plan: dict | None, ruct: dict | None) -> dict | None:
    """Errata del cuadro de créditos del BOE (Medicina, CEU: TFG 6 y optativas 8 en el cuadro, 8 y 6 en las filas
    del mismo BOE y en el RUCT): si los tipos en que el cuadro y el RUCT discrepan suman lo mismo en los dos y las
    filas del plan dan lo del RUCT en cada uno que se puede contar (todos menos optativas), vale el reparto del RUCT y
    el del BOE queda aparte con la explicación. Si no, no se toca nada."""
    d, cr = (plan or {}).get("distribucion") or {}, ((ruct or {}).get("creditos") or {})
    if not d or not cr:
        return plan
    distintos = [k for k, (kr, _) in PAREJAS_DIST.items() if d.get(k) is not None and cr.get(kr) is not None
                 and abs(d[k] - cr[kr]) > 0.5]
    if not distintos or abs(sum(d[k] for k in distintos) - sum(cr[PAREJAS_DIST[k][0]] for k in distintos)) > 0.5:
        return plan
    filas = plan.get("asignaturas") or []
    for k in distintos:
        tipo = PAREJAS_DIST[k][1]
        if tipo and abs(sum(a.get("creditos") or 0 for a in filas if a.get("tipo") == tipo)
                        - cr[PAREJAS_DIST[k][0]]) > 0.5:
            return plan
    return {**plan, "distribucion": {**d, **{k: cr[PAREJAS_DIST[k][0]] for k in distintos}}, "distribucion_boe": d,
            "nota_distribucion": "el cuadro de créditos del BOE no cuadra con las filas del propio plan; vale el "
                                 "reparto del RUCT, que sí cuadra con ellas"}


def en_extincion(t: dict, r: dict | None) -> list[dict] | None:
    """Las extinciones del RUCT del título si cubren todas sus universidades (en un título conjunto, la de una sola
    no lo cierra); None si no hay."""
    ext = [e for e in (r or {}).get("extincion") or [] if e.get("universidad")]
    if not ext:
        return None
    cerradas = {clave_universidad(e["universidad"]) for e in ext}
    suyas = {clave_universidad(u["nombre"]) for u in t.get("universidades") or []}
    cubiertas = all(any(s in c or c in s for c in cerradas) for s in suyas) if suyas else False
    return ext if cubiertas else None


def plan_casi_entero(p: dict) -> bool:
    """Un plan o modificación del BOE que trae (casi) todas sus asignaturas fijas: lo que suman sin optativas llega
    al 80 % de lo que dice su tabla de créditos. Una modificación de unas pocas asignaturas no lo es."""
    esperado = p.get("esperado_sin_optativas")
    return bool(esperado) and (p.get("suma_sin_optativas") or 0) >= 0.8 * esperado


def plan_comprobado(p: dict) -> bool:
    """El listado cuadra con la tabla de créditos por tipo del propio plan: entero (básicas + obligatorias +
    prácticas + TFG) o en básicas y obligatorias (el núcleo del plan), o con los créditos por tipo del RUCT."""
    if p.get("comprobacion"):
        return True
    esp = p.get("esperado_sin_optativas")
    return bool(esp) and abs((p.get("suma_sin_optativas") or 0) - esp) <= 0.5


def comprobar_con_ruct(p: dict, r: dict) -> dict:
    """Comprobación cruzada del plan del BOE con los créditos por tipo de la ficha del RUCT (otra fuente oficial):
    básicas + obligatorias + prácticas + TFG del listado = total − optativos del RUCT."""
    cr = (r or {}).get("creditos") or {}
    if not cr.get("total") or cr.get("optativos") is None:
        return p
    filas = p.get("plan") or []
    base = [f for f in filas if f.get("nivel") == "asignatura"] or filas
    fijos = sum(f.get("creditos") or 0 for f in base if f.get("tipo") in ("basica", "obligatoria", "practicas", "tfg"))
    esperado = cr["total"] - cr["optativos"]
    if fijos and abs(fijos - esperado) <= 0.5:
        return {**p, "comprobacion": "con_creditos_del_ruct"}
    return p


HUECO_OPTATIVO = re.compile(r"^(?:asignaturas? )?(?:optativ[ao]s?|optatividad|cr[ée]ditos optativos)"
                            r"(?:\s+(?:[IVX]+|\d+(?:\s*[-–]\s*\d+)?|\(\d+\)))?$", re.I)


def nivel_plan(filas: list[dict]) -> str | None:
    """«asignatura» si el plan del BOE lista asignaturas; «materia» si solo publica materias (o módulos)."""
    if not filas:
        return None
    asig = sum(1 for f in filas if f.get("nivel") == "asignatura")
    return "asignatura" if asig >= 0.5 * len(filas) else "materia"


def sin_niveles_repetidos(filas: list[dict]) -> list[dict]:
    """Planes por materias que además listan las asignaturas de un tipo (las básicas, sobre todo): las mismas
    créditos dos veces. Si las asignaturas de un tipo suman lo mismo que sus materias, quedan las asignaturas (el
    desglose) y salen las materias de ese tipo; si no suman lo mismo, no se toca nada."""
    suma: dict = defaultdict(float)
    for f in filas:
        if f.get("tipo") and f.get("nivel") in ("materia", "asignatura"):
            suma[(f["tipo"], f["nivel"])] += f.get("creditos") or 0
    fuera = {tipo for (tipo, nivel), v in suma.items() if nivel == "materia" and v
             and abs(suma.get((tipo, "asignatura"), 0) - v) <= 0.5}
    return [f for f in filas if not (f.get("nivel") == "materia" and f.get("tipo") in fuera)]


def resumen_plan(p: dict) -> dict:
    filas = sin_niveles_repetidos(p.get("plan") or [])
    return {
        "boe": p["identificador"],
        "fecha": p.get("fecha"),
        "tipo": p.get("tipo"),
        "comprobado": plan_comprobado(p),
        "comprobacion": p.get("comprobacion") or ("completo" if plan_comprobado(p) else None),
        "lectura": p.get("interpretacion") or "directa",
        "cuadra_por_tipo": bool(p.get("cuadra_por_tipo")),
        # «materia» cuando el plan solo cuadra contando sus materias (lista por asignaturas solo una parte)
        "nivel_comprobado": (p.get("nivel_comprobado") or nivel_plan(filas)) if plan_comprobado(p) else None,
        "enlazado_por_ruct": bool(p.get("enlazado_por_ruct")),
        "parte": p.get("parte"),
        "distribucion": p.get("distribucion"),
        "nivel": nivel_plan(filas),
        # «Optativa I», «Optativas 2-7», «Créditos optativos»: hueco del plan para optativas, no una asignatura
        "asignaturas": [{**{k: f.get(k) for k in ("nombre", "modulo", "tipo", "creditos", "curso", "semestre", "nivel")},
                         "hueco": bool(HUECO_OPTATIVO.match((f.get("nombre") or "").strip(" .")))}
                        for f in filas],
        "menciones": p.get("menciones") or [],
        "fuente": {"cita": FUENTE_BOE, "url": f"https://www.boe.es/diario_boe/txt.php?id={p['identificador']}"}
        if p.get("identificador") else None,
    }


TIPO_MEMORIA = {"basica": "basica", "obligatoria": "obligatoria", "optativa": "optativa",
                "practicas externas": "practicas", "practicas": "practicas", "trabajo fin de grado": "tfg",
                "trabajo fin de grado / master": "tfg", "trabajo fin de grado/master": "tfg"}


def _tipo_memoria(caracter: str | None) -> str | None:
    c = unicodedata.normalize("NFKD", (caracter or "").lower())
    c = re.sub(r"\s+", " ", "".join(x for x in c if not unicodedata.combining(x))).strip()
    return TIPO_MEMORIA.get(c) or ("tfg" if c.startswith("trabajo fin") else None)


def plan_de_memoria(r: dict | None) -> dict | None:
    """Plan de la memoria vigente del RUCT (módulos, materias y asignaturas con carácter, ECTS y semestre) con la
    misma forma que un plan del BOE. Se comprueba con los créditos por tipo de la ficha del propio RUCT: básicas +
    obligatorias + prácticas + TFG de las asignaturas = total − optativos. Si alguna asignatura no tiene carácter o
    créditos, o la memoria avisa de páginas que no se pudieron leer, no se da por comprobado."""
    m = (r or {}).get("memoria") or {}
    if not m.get("plan") or m.get("error"):
        return None
    filas, incompleto = [], bool([a for a in m.get("avisos") or [] if "estado" in a or "límite" in a])
    for b in m["plan"]:
        for x in b.get("materias") or []:
            for a in x.get("asignaturas") or []:
                tipo = _tipo_memoria(a.get("caracter"))
                sem = sorted(int(k) for k, v in (a.get("despliegue") or {}).items() if str(k).isdigit() and v)
                incompleto = incompleto or not tipo or not a.get("ects")
                filas.append({"nombre": a.get("nombre"), "modulo": b.get("nombre"), "materia": x.get("nombre"),
                              "tipo": tipo, "creditos": a.get("ects"),
                              "curso": (sem[0] + 1) // 2 if sem else None, "semestre": sem[0] if sem else None,
                              "nivel": "asignatura"})
    if not filas:
        return None
    cr = (r or {}).get("creditos") or {}
    fijos = sum(f["creditos"] or 0 for f in filas if f["tipo"] in ("basica", "obligatoria", "practicas", "tfg"))
    esperado = cr["total"] - cr["optativos"] if cr.get("total") and cr.get("optativos") is not None else None
    cuadra = bool(esperado) and not incompleto and abs(fijos - esperado) <= 0.5
    fuente = (r.get("fuente") or {})
    return {"identificador": None, "origen": "memoria_ruct", "memoria": m.get("cod"), "fecha": r.get("fecha_verificacion"),
            "plan": filas, "comprobacion": "con_creditos_del_ruct" if cuadra else None,
            # incompleta (páginas sin leer, asignaturas sin carácter): sin cifra esperada, así no cuenta como comprobada
            "esperado_sin_optativas": None if incompleto else esperado, "suma_sin_optativas": fijos, "incompleta": incompleto,
            "fuente": {"cita": FUENTE_RUCT + ", memoria de verificación vigente", "url": fuente.get("url"),
                       "capturado": fuente.get("capturado")}}


# -------------------------------------------------------------------------------------------- fichas


def construir(catalogo: list[dict], genericos: list[dict], tarjetas: dict, detalles: dict,
              planes: dict, ind: dict | None = None, web: dict | None = None, ruct: dict | None = None,
              planes_id: dict | None = None, tarifas: dict | None = None,
              paginas: dict | None = None) -> tuple[list[dict], list[dict]]:
    gen_de = {c: g for g in genericos for c in g["titulos"]}
    por_ambito = Counter((clave_universidad(t["universidades"][0]["nombre"]), t.get("ambito")) for t in catalogo
                         if t["situacion"] == "Activo" and t["clase"] == "grado")
    qedu_por_titulo: dict[str, list] = defaultdict(list)
    for (tit, cen), t in tarjetas.items():
        qedu_por_titulo[tit].append(centro_qedu(t, detalles.get((tit, cen))))
    fichas = []
    rama_de = {t["codigo"]: (t.get("rama"), t["nombre"]) for t in catalogo if t.get("clase") == "grado"}
    descartadas: dict[str, str] = {}
    for t in catalogo:
        if t["situacion"] != "Activo" or t["clase"] not in ("grado", "doble"):
            continue
        g = gen_de.get(t["codigo"])
        centros = sorted(qedu_por_titulo.get(t["codigo"], []), key=lambda c: c["codigo"])
        # plan del BOE: el más reciente comprobado de esa universidad y ese grado; si no hay, el más reciente
        plan = None
        r = (ruct or {}).get(t["codigo"])
        if t["clase"] == "grado":
            candidatos = []
            for u in t["universidades"]:
                candidatos += planes.get((clave_universidad(u["nombre"]), clave_union(nombre_base(t["nombre"]))), [])
            # el plan que enlaza el RUCT para este código (si la resolución trae varios, el de su nombre)
            ident = ((r or {}).get("boe") or {}).get("plan", {}).get("identificador") if r else None
            for p in (planes_id or {}).get(ident or "", []):
                if not p.get("titulo_grado") or clave_union(nombre_base(nombre_corto(p["titulo_grado"]))) == \
                        clave_union(nombre_base(t["nombre"])):
                    candidatos.append({**p, "fecha": p.get("fecha") or ((r.get("boe") or {}).get("plan") or {}).get("fecha"),
                                       "enlazado_por_ruct": True})
            # un plan cuyo texto declara el código de otro título (el plan nuevo de un título que sustituye a este,
            # con el mismo nombre) no es de este
            candidatos = [p for p in candidatos if not p.get("codigos_en_texto") or t["codigo"] in p["codigos_en_texto"]]
            candidatos.sort(key=lambda p: p.get("fecha") or "", reverse=True)
            if candidatos and not any(plan_comprobado(p) for p in candidatos) and r:
                # sin tabla de créditos que cuadre en el BOE: se comprueba contra los créditos por tipo del RUCT
                candidatos = [comprobar_con_ruct(p, r) for p in candidatos]
            if candidatos:
                # el plan vigente es el más reciente que trae el plan entero o casi (verificación del 30/10: la
                # modificación de 2026 de Historia de la URJC, sin cuadrar por una errata, y la ficha enseñaba el
                # plan de 2020); si ese no cuadra, la ficha no tiene plan comprobado, aunque uno anterior cuadre
                vigente = next((p for p in candidatos if plan_comprobado(p) or plan_casi_entero(p)), candidatos[0])
                anterior = next((p for p in candidatos if plan_comprobado(p)), None)
                plan = corregir_distribucion(resumen_plan(vigente), resumen_ruct(r))
                if anterior is not None and anterior is not vigente:
                    plan["plan_anterior_comprobado"] = {"boe": anterior["identificador"], "fecha": anterior.get("fecha"),
                                                        "nota": "hay una modificación posterior del plan que no cuadra"
                                                                " con su tabla de créditos: el plan anterior no se usa"}
        if not (plan and plan["comprobado"]):
            # sin plan del BOE que cuadre: el de la memoria vigente del RUCT, si cuadra con sus créditos por tipo
            pm = plan_de_memoria(r)
            if pm and (plan_comprobado(pm) or not plan):
                plan = {**resumen_plan({**pm, "identificador": None}), "boe": None, "origen": "memoria_ruct",
                        "memoria": pm["memoria"], "fuente": pm["fuente"]}
        notas = [c["nota_corte"] for c in centros if c["nota_corte"] is not None]
        precios = [c["precio_credito"] for c in centros if c["precio_credito"]]
        creditos = next((c["creditos"] for c in centros if c["creditos"]), None)
        motivos = []
        if not (plan and plan["comprobado"]):
            motivos.append("sin asignaturas comprobadas" if not plan else "plan sin cuadrar con su tabla de créditos")
        pweb = (web or {}).get(t["codigo"])
        if pweb and t["universidad_tipo"] != "Privada" and not (pweb.get("centro_adscrito") and not precios):
            pweb = None  # en una pública solo vale la web de su centro adscrito, y solo si QEDU no da precio
        # la dirección casaba con el grado, pero el título de la página dice que es de otro estudio (un doble, una
        # FP, otro grado): esa página no vale para este grado
        pag = (paginas or {}).get(t["codigo"]) if t["universidad_tipo"] == "Privada" else None
        if pweb and titulo_contradice(t, pweb.get("_titulo")):
            pweb, descartadas[t["codigo"]] = None, "precio"
        if pweb and sede_ajena(t, pweb.get("url")):
            pweb, descartadas[t["codigo"]] = None, "precio_de_otra_sede"  # la dirección nombra otra sede
        if pag and (titulo_contradice(t, pag.get("_titulo")) or sede_ajena(t, pag.get("url"))):
            pag, descartadas[t["codigo"]] = None, descartadas.get(t["codigo"], "pagina")
        pweb = {k: v for k, v in pweb.items() if k != "_titulo"} if pweb else None
        pag = {k: v for k, v in pag.items() if k != "_titulo"} if pag else None
        ptar = (tarifas or {}).get(t["codigo"])
        if ptar and t["universidad_tipo"] != "Privada" and not (ptar.get("centro_adscrito") and not precios):
            ptar = None  # en una pública, como con la web: solo la lista de su centro adscrito y sin precio en QEDU
        if ptar and sede_ajena(t, ptar.get("url")):
            ptar = None  # lista de precios de otro campus («…/campus-elche.pdf» para un grado de Valencia)
        if ptar and ptar["precio_curso"] and not (pweb and pweb["precio_curso"]):
            pweb = ptar  # la página del grado no da precio y el documento de precios de la universidad sí
        if not creditos and r and (r.get("creditos") or {}).get("total"):
            creditos = r["creditos"]["total"]
        if not creditos and plan and plan["comprobado"]:
            creditos = (plan.get("distribucion") or {}).get("total") or (plan.get("distribucion") or {}).get("total_calculado")
        if pweb and pweb.get("url"):
            # un grado en centros de varias provincias con la página de una sede: el precio es solo de esa sede
            provincias = {str(i["unidad_codigo"])[:2] for i in t["imparticiones"]
                          if i.get("situacion") == "Activo" and i.get("unidad_codigo")}
            sedes = sorted(palabras_url(pweb["url"]) & SEDES)
            if sedes and len(provincias) > 1:
                pweb = {**pweb, "solo_sede": sedes}
            # la página de una modalidad («…/psicologia-a-distancia») de un grado que también es presencial: el
            # precio es solo de esa modalidad (verificación del 30/10: UCAM, 6.000 € online frente a 6.250 €)
            modalidad = palabras_url(pweb["url"]) & {"online", "distancia", "semipresencial", "virtual"}
            presencial = any("presencial" in (i.get("presencialidad") or "").lower()
                             and "no presencial" not in (i.get("presencialidad") or "").lower()
                             or "varias" in (i.get("presencialidad") or "").lower()
                             for i in t["imparticiones"] if i.get("situacion") == "Activo")
            if modalidad and presencial:
                pweb = {**pweb, "solo_modalidad": "semipresencial" if "semipresencial" in modalidad else "a distancia"}
        por_credito = (pweb or {}).get("metodo") in METODOS_POR_CREDITO
        if pweb and pweb["precio_curso"] and creditos and (t["clase"] != "doble" or por_credito):
            # todo el grado al precio de hoy: un curso son 60 créditos (RD 822/2021 art. 5); sin subidas futuras
            pweb = {**pweb, "precio_total_estimado": round(pweb["precio_curso"] * creditos / 60, 2),
                    "creditos": creditos}
        elif pweb and pweb["precio_curso"] and creditos:
            # un doble grado tiene cursos de más de 60 créditos (72, 78…) y la página da el precio de un curso: sin el
            # precio del crédito no se sabe el total (calcularlo con 60 créditos por curso lo inflaría)
            pweb = {**pweb, "precio_total_estimado": None, "creditos": creditos,
                    "nota_total": "precio de un curso del doble grado; el total depende de los créditos de cada curso"}
        # pública sin precio en QEDU (los dobles nunca lo traen): si su comunidad fija un precio único para todos
        # los grados, ese es el suyo en los centros propios (los adscritos fijan el suyo); con niveles, no se deduce
        precio_norma = None
        if not precios and creditos and t["universidad_tipo"] == "Pública" \
                and not re.search(r"\bjoint\b|conjunto internacional", t.get("nombre_oficial") or "", re.I):
            propio = any(c.get("tipo_centro") == "Propio" for c in centros) if centros else any(
                i.get("unidad_modalidad") == "Centro propio" and i.get("situacion") == "Activo"
                for i in t.get("imparticiones") or [])
            comunidad = t["universidades"][0].get("comunidad")
            pu = precio_unico(comunidad) if propio else None
            if propio and not pu:
                # precio por rama: la del grado o, en un doble, la de los dos grados que lo forman (mismo precio)
                if t["clase"] == "grado":
                    titulos = [(t.get("rama"), t["nombre"])]
                else:
                    comp = [rama_de.get(c.get("codigo") or "") for c in t.get("componentes") or []]
                    titulos = comp if len(comp) >= 2 and all(comp) else []
                pu = precio_por_rama(comunidad, titulos)
            if pu:
                precio_norma = {**pu, "centros": "propios", "creditos": creditos}
        if not notas and not precios and not precio_norma and not (pweb and pweb["precio_curso"]):
            motivos.append("sin nota de corte ni precio")
        # título en extinción según el RUCT en todas sus universidades (no admite alumnos nuevos): no se indexa
        # (verificación del 30/10: ADE de Zaragoza, extinción desde 2026-2027, se publicaba como abierto)
        extincion = en_extincion(t, r)
        if extincion:
            motivos.append("título en extinción: no admite alumnos nuevos")
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
            "precio_primera_matricula": round(min(precios) * creditos, 2) if precios and creditos
            else round(precio_norma["precio_credito"] * creditos, 2) if precio_norma else None,
            # de dónde sale el precio cuando no es de QEDU: la norma de precios de la comunidad
            "precio_credito_norma": precio_norma,
            "precio_web": pweb,
            # privada sin precio: su página del grado y lo que pide su formulario (hecho medido, sin juicio)
            # la página que casaba por la dirección y su título dice que es de otro estudio (no se usa)
            "pagina_web_descartada_por_titulo": descartadas.get(t["codigo"]),
            "pagina_privada_sin_precio": pag
            if t["universidad_tipo"] == "Privada" and not (pweb and pweb.get("precio_curso")) else None,
            "bonificacion": de_comunidad(t["universidades"][0].get("comunidad")) if t["universidad_tipo"] == "Pública" else None,
            "plan": plan,
            "en_extincion": extincion,
            "ruct": resumen_ruct(r),
            "indicadores": indicadores_de(t, ind or {}, por_ambito) if t["clase"] == "grado" else None,
            "indexable": not motivos,
            "motivos_noindex": motivos,
            "fuente_catalogo": {"cita": FUENTE_SIIU, **{k: t["fuente"].get(k) for k in ("url", "curso", "capturado")}},
        })
    # dobles grados: no tienen plan propio en el BOE; se cursan las asignaturas de sus dos grados (con los
    # reconocimientos que fije cada universidad). Si los dos grados que lo forman tienen su plan comprobado, la
    # ficha del doble los enlaza y ese requisito queda cubierto.
    por_codigo_f = {f["codigo"]: f for f in fichas}
    for f in fichas:
        if f["clase"] != "doble":
            continue
        comp = [por_codigo_f.get(c.get("codigo")) for c in f["componentes"]]
        f["planes_componentes"] = [{"codigo": c["codigo"], "nombre": c["nombre"],
                                    "boe": (c.get("plan") or {}).get("boe"),
                                    "comprobado": bool(c.get("plan") and c["plan"]["comprobado"]),
                                    "nivel": (c.get("plan") or {}).get("nivel")} for c in comp if c]
        # precio del doble de pública que no trae QEDU: el nivel que le da el anexo de la norma de su comunidad o la
        # regla de la norma (o de su universidad) sobre los precios de sus dos grados (centros propios de la misma
        # universidad; si un grado tiene dos precios distintos, no se deduce)
        if f["universidad_tipo"] == "Pública" and not f["precio_primera_matricula"] \
                and any(x.get("tipo_centro") == "Propio" for x in f["centros"]):
            precios = []
            for c in comp if len(comp) >= 2 and all(comp) else []:
                propios = {x["precio_credito"] for x in c["centros"] if x.get("precio_credito")
                           and x.get("tipo_centro") == "Propio"}
                precios.append(propios.pop() if len(propios) == 1 else None)
            creditos = next((x["creditos"] for x in f["centros"] if x.get("creditos")), None)
            u0 = f["universidades"][0]
            pd = precio_doble(u0.get("comunidad"), precios, u0.get("nombre"), f["codigo"]) if creditos else None
            if pd:
                f["precio_credito_norma"] = {**pd, "centros": "propios", "creditos": creditos}
                f["precio_primera_matricula"] = round(pd["precio_credito"] * creditos, 2)
                f["motivos_noindex"] = [m for m in f["motivos_noindex"] if m != "sin nota de corte ni precio"]
                f["indexable"] = not f["motivos_noindex"]
        if len(f["planes_componentes"]) >= 2 and all(x["comprobado"] for x in f["planes_componentes"]):
            f["motivos_noindex"] = [m for m in f["motivos_noindex"] if m != "sin asignaturas comprobadas"]
            f["indexable"] = not f["motivos_noindex"]
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
                     if f["generico"] and f["generico"]["id"] == gid and f["plan"] and f["plan"]["comprobado"]
                     and f["plan"].get("nivel_comprobado") == "asignatura"}  # materias y asignaturas no se comparan
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
        "con_precio_de_la_norma_autonomica": sum(1 for f in fichas if f.get("precio_credito_norma")),
        "privadas": sum(1 for f in fichas if f["universidad_tipo"] == "Privada"),
        "privadas_con_pagina_y_algun_importe": sum(1 for f in fichas if f.get("precio_web")
                                                   and f["universidad_tipo"] == "Privada"),
        "privadas_con_precio_por_curso": sum(1 for f in fichas if (f.get("precio_web") or {}).get("precio_curso")
                                             and f["universidad_tipo"] == "Privada"),
        "privadas_con_precio_total_estimado": sum(1 for f in fichas if f["universidad_tipo"] == "Privada"
                                                  and (f.get("precio_web") or {}).get("precio_total_estimado")),
        "adscritos_de_publicas_con_precio_de_su_web": sum(1 for f in fichas if f["universidad_tipo"] != "Privada"
                                                          and (f.get("precio_web") or {}).get("precio_curso")),
        "privadas_sin_precio_con_pagina_leida": sum(1 for f in fichas if f.get("pagina_privada_sin_precio")),
        "privadas_paginas_descartadas_por_titulo": sum(1 for f in fichas if f.get("pagina_web_descartada_por_titulo")),
        "privadas_sin_precio_que_piden_correo": sum(1 for f in fichas if (f.get("pagina_privada_sin_precio") or {})
                                                    .get("formulario_pide_correo")),
        "privadas_precio_por_fuente": dict(Counter((f.get("precio_web") or {}).get("fuente") for f in fichas
                                                   if (f.get("precio_web") or {}).get("precio_curso"))),
        "privadas_precio_por_metodo": dict(Counter((f.get("precio_web") or {}).get("metodo") for f in fichas
                                                   if (f.get("precio_web") or {}).get("precio_curso"))),
        "con_bonificacion_o_ayuda": sum(1 for f in fichas if f.get("bonificacion")),
        "con_insercion": sum(1 for f in fichas if any(c.get("insercion") for c in f["centros"])),
        "con_indicadores_siiu": sum(1 for f in fichas if f.get("indicadores")),
        "indicadores_solo_de_ese_grado": sum(1 for f in fichas if f.get("indicadores")
                                            and f["indicadores"]["grados_de_la_universidad_en_el_ambito"] == 1),
        "con_ficha_ruct": sum(1 for f in fichas if f.get("ruct")),
        "con_creditos_por_tipo_ruct": sum(1 for f in fichas if (f.get("ruct") or {}).get("creditos")),
        "con_plan_boe": sum(1 for f in fichas if f["plan"]),
        "con_plan_comprobado": sum(1 for f in fichas if f["plan"] and f["plan"]["comprobado"]),
        "dobles_con_los_dos_planes_comprobados": sum(1 for f in fichas if f["clase"] == "doble"
                                                     and len(f.get("planes_componentes") or []) >= 2
                                                     and all(x["comprobado"] for x in f["planes_componentes"])),
        "con_plan_comprobado_de_asignaturas": sum(1 for f in fichas if f["plan"] and f["plan"]["comprobado"]
                                                 and f["plan"].get("nivel_comprobado") == "asignatura"),
        "indexables": sum(1 for f in fichas if f["indexable"]),
        "motivos_noindex": dict(Counter(m for f in fichas for m in f["motivos_noindex"])),
        "comparativas": len(comparativa),
        "comparativas_con_asignaturas": sum(1 for c in comparativa if c.get("asignaturas")),
        "filas_comparativa": sum(len(c["filas"]) for c in comparativa),
    }


FUENTE_BOE = "Fuente: Agencia Estatal Boletín Oficial del Estado"


def fichas_proximas(altas: list[dict], catalogo: list[dict], planes: dict, ruct: dict | None = None) -> list[dict]:
    """Grados con carácter oficial por acuerdo del Consejo de Ministros (BOE) que aún no están en el catálogo del
    SIIU: los que empiezan en los próximos cursos. La ficha lleva el acuerdo, la universidad y, si ya está
    publicado, su plan del BOE. Sin nota de corte ni precio todavía: no se indexan hasta tenerlos."""
    from motor.grados.planes import resolver_universidad

    en_catalogo = {t["codigo"] for t in catalogo}
    universidades = {clave_universidad(u["nombre"]): u for t in catalogo for u in t["universidades"]}
    tipo_de = {clave_universidad(u["nombre"]): t["universidad_tipo"] for t in catalogo for u in t["universidades"]}
    salida = []
    for a in altas:
        cod = a.get("codigo_ruct")
        if not cod or cod in en_catalogo:
            continue
        ku = resolver_universidad(clave_universidad(a.get("universidad")), set(universidades))
        u = universidades.get(ku)
        nombre = nombre_corto(a.get("nombre") or "")
        candidatos = sorted((p for p in planes.get((ku, clave_union(nombre_base(nombre))), [])
                             if not p.get("codigos_en_texto") or cod in p["codigos_en_texto"]),
                            key=lambda p: p.get("fecha") or "", reverse=True)
        plan = resumen_plan(next((p for p in candidatos if plan_comprobado(p)), candidatos[0])) if candidatos else None
        salida.append({
            "codigo": cod, "clase": "grado", "estado": "nuevo", "nombre": nombre, "nombre_oficial": a.get("nombre"),
            "universidades": [u] if u else [{"nombre": a.get("universidad")}],
            "universidad_tipo": tipo_de.get(ku),
            "alta": {"boe": a.get("boe"), "url": f"https://www.boe.es/diario_boe/txt.php?id={a.get('boe')}",
                     "cita": FUENTE_BOE},
            "plan": plan, "ruct": resumen_ruct((ruct or {}).get(cod)),
            "indexable": False, "motivos_noindex": ["grado nuevo: todavía sin nota de corte ni precio"],
        })
    return salida


CURSO_RECIENTE = "2021-2022"


def anadir_historico(fichas: list[dict], historico: list[dict]) -> dict:
    """Pone en cada centro de cada ficha su histórico de notas de corte del cupo general (notas_corte.py), solo el
    publicable: nota final de su distrito que coincide con QEDU en los cursos que se solapan. Cada curso lleva su
    fuente (documento del distrito, huella y fecha de captura). Una ficha sin nota de QEDU ni precio que tenga la de su
    distrito desde 2021-2022 deja de tener ese motivo para no indexarse."""
    por = {(h["codigo_titulo"], h["codigo_centro"]): h for h in historico if h.get("publicable")}
    from motor.grados.notas_corte import CUPOS_RESERVA, igual_a_qedu

    fichas_con, centros_con, cinco, indexables_por_historico, centros_con_cupos = set(), 0, 0, set(), 0
    notas_qedu_sustituidas = 0
    for f in fichas:
        for c in f.get("centros") or []:
            h = por.get((f["codigo"], c.get("codigo")))
            if not h:
                continue
            c["notas_historicas"] = {"cupo": "general", "distrito": h["distrito"], "cursos": h["cursos"],
                                     "contraste_qedu": h["contraste_qedu"],
                                     "nota": "la menor de las ofertas del título en el centro, como QEDU; 5,000 = "
                                             "entraron todos los que lo pidieron; «tipo_ultimo_admitido», lo que "
                                             "dice el documento del último admitido, literal"}
            if h.get("otros_cupos"):
                # cupos de reserva: misma fila del mismo documento que la del cupo general, ya contrastada con QEDU
                c["notas_historicas"]["otros_cupos"] = {
                    cupo: {"rotulo": CUPOS_RESERVA[cupo], "cursos": cursos}
                    for cupo, cursos in h["otros_cupos"].items() if cupo in CUPOS_RESERVA}
                c["notas_historicas"]["nota_otros_cupos"] = (
                    "cada cupo de reserva tiene su propia prueba o baremo y sus notas no se comparan con las del cupo "
                    "general; 5,000 = se admitió a todos los que lo pidieron por ese cupo")
                centros_con_cupos += 1
            # la nota de QEDU de un curso que el distrito publica distinta (QEDU con 5,000 porque al final quedaron
            # plazas, o tomada en otro llamamiento): no se enseñan dos notas para el mismo curso; vale la del
            # distrito, que es la lista final con su documento, y la de QEDU queda aparte
            for campo, campo_curso in (("nota_corte", "curso"), ("nota_corte_anterior", "curso_anterior")):
                q, d = c.get(campo), h["cursos"].get(c.get(campo_curso) or "")
                if q is not None and d and d.get("lista") == "final" and not igual_a_qedu(q, d["nota"]):
                    c[f"{campo}_qedu_no_usada"] = {"nota": q, "curso": c.get(campo_curso), "nota_distrito": d["nota"],
                                                   "motivo": "el distrito publica otra nota final para ese curso"}
                    c[campo] = None
                    notas_qedu_sustituidas += 1
            fichas_con.add(f["codigo"])
            centros_con += 1
            cinco += len(h["cursos"]) >= 5
            # una nota de corte publicada por su distrito en los últimos cursos es nota de corte para indexar
            if any(k >= CURSO_RECIENTE for k in h["cursos"]) \
                    and "sin nota de corte ni precio" in (f.get("motivos_noindex") or []):
                f["motivos_noindex"] = [m for m in f["motivos_noindex"] if m != "sin nota de corte ni precio"]
                f["indexable"] = not f["motivos_noindex"]
                indexables_por_historico.add(f["codigo"])
    return {"fichas_con_notas_historicas": len(fichas_con), "centros_con_notas_historicas": centros_con,
            "centros_con_cinco_cursos_o_mas": cinco, "centros_con_cupos_de_reserva": centros_con_cupos,
            "notas_de_qedu_sustituidas_por_la_del_distrito": notas_qedu_sustituidas,
            "fichas_con_nota_solo_por_el_historico": len(indexables_por_historico)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--catalogo", required=True)
    p.add_argument("--genericos", required=True)
    p.add_argument("--qedu", help="carpeta con qedu_tarjetas_*.jsonl y qedu_detalles_*.jsonl")
    p.add_argument("--boe", help="carpeta con boe_actos.jsonl y boe_planes.jsonl")
    p.add_argument("--indicadores", help="carpeta con los indicadores del SIIU (abandono.jsonl, …)")
    p.add_argument("--web-privadas", help="carpeta con los rastreos de webs privadas (…/web_privadas/{código}.json)")
    p.add_argument("--ruct", help="carpeta con las fichas del RUCT (…/ruct/{código}.json)")
    p.add_argument("--tarifas", help="carpeta con los precios de PDF y páginas de precios (…/tarifas_grado/tarifas.jsonl)")
    p.add_argument("--notas", help="historico.jsonl de notas_corte.py (notas de corte de cada distrito por curso)")
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    tarjetas, detalles = indexar_qedu(Path(a.qedu) if a.qedu else None)
    catalogo = _leer(Path(a.catalogo))
    conocidas = {clave_universidad(u["nombre"]) for t in catalogo for u in t["universidades"]}
    fichas, comparativa = construir(catalogo, _leer(Path(a.genericos)), tarjetas, detalles,
                                    indexar_planes(Path(a.boe) if a.boe else None, conocidas),
                                    indexar_indicadores(Path(a.indicadores) if a.indicadores else None),
                                    indexar_web_privadas(Path(a.web_privadas) if a.web_privadas else None),
                                    indexar_ruct(Path(a.ruct) if a.ruct else None),
                                    planes_por_identificador(Path(a.boe) if a.boe else None),
                                    indexar_tarifas(Path(a.tarifas) if a.tarifas else None),
                                    indexar_paginas_privadas(Path(a.web_privadas) if a.web_privadas else None))
    hist = anadir_historico(fichas, _leer(Path(a.notas))) if a.notas else {}
    altas_f = Path(a.boe) / "boe_altas.jsonl" if a.boe else None
    proximas = fichas_proximas(_leer(altas_f), catalogo, indexar_planes(Path(a.boe), conocidas),
                               indexar_ruct(Path(a.ruct) if a.ruct else None)) if altas_f and altas_f.exists() else []
    destino = Path(a.salida) / "datos" / "estudios" / "grados"
    destino.mkdir(parents=True, exist_ok=True)
    for nombre, datos in (("fichas.jsonl", fichas), ("comparativa.jsonl", comparativa),
                          ("fichas_proximas.jsonl", proximas)):
        with (destino / nombre).open("w", encoding="utf-8") as f:
            for x in datos:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
    res = resumen(fichas, comparativa)
    res.update(hist)
    res["proximas"] = len(proximas)
    res["proximas_con_plan_del_boe"] = sum(1 for x in proximas if x["plan"])
    (destino / "fichas_resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
