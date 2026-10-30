"""Unión de los actos posteriores (admitidos, tribunal, examen, aprobados, nombramiento, correcciones...) con el
proceso al que pertenecen. Sigue el modelo de oposiciones (docs/modelo-oposiciones.md, «Unión de actos con su
proceso»), por este orden y solo cuando el candidato es único:

  1. referencia explícita: el acto cita el identificador del BOE de la convocatoria o de otro acto ya unido, o su
     texto cita el boletín y la fecha en que salieron las bases o la convocatoria (motor/extraccion/citas.py);
  2. cita de la convocatoria en el título: «convocado por Resolución de 15 de julio de 2026» (u «Orden
     HFP/123/2026») del mismo órgano convocante; si hay varias de ese día, la del mismo puesto;
  3. número de expediente o de proceso («proceso selectivo 154CO/22») del mismo convocante;
  4. convocante + puesto (+ turno, si consta), con la convocatoria anterior al acto y de los tres años previos;
     sin puesto en el título, la única convocatoria del convocante en el año anterior (listas, tribunal, examen y
     resultados).

Lo que no se une con seguridad va a la cola de huérfanos con el motivo; nunca se descarta. Cada unión guarda cómo
se ha hecho («motivo»), para poder revisarla y rehacerla.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date

from motor.boe.clasificar import normalizar
from motor.catalogo.puestos import normalizar_puesto
from motor.extraccion.texto_es import MESES

POSTERIORES = {"admitidos", "tribunal", "examen", "aprobados", "nombramiento", "desierta", "anulacion",
               "correccion", "modificacion", "otro"}
# Fase del proceso que marca cada tipo de acto (el estado sale del último acto conocido)
FASE = {"admitidos": "admitidos", "tribunal": "tribunal", "examen": "examen_convocado", "aprobados": "aprobados",
        "nombramiento": "nombramiento", "desierta": "desierto", "anulacion": "anulado"}
ORDEN_FASES = ["admitidos_provisional", "admitidos_definitivo", "admitidos", "tribunal", "examen_convocado",
               "aprobados", "nombramiento", "desierto", "anulado"]

_TIPO = r"(?:resoluci[oó]n|resolucio|resolucion|orden|orde|ordre|decreto|decret|acuerdo|acord|anuncio|edicto|decreto de alcald[ií]a)"
_COD = r"(?:[A-Z]{2,6}/\d{1,5}/\d{4}|\d{1,4}/\d{1,6}/\d{4}|\d{1,5}/\d{4})"
_FECHA = r"(?P<d>\d{1,2})\s+(?:de\s+|d')(?P<m>[a-záéíóúç]+)(?:\s+(?:de\s+|del\s+)?(?P<a>\d{4}))?"
RE_DISPOSICION = re.compile(rf"^\s*(?P<tipo>{_TIPO})\s*(?P<cod>{_COD})?,?\s+de\s+{_FECHA}", re.IGNORECASE)
RE_CITA = re.compile(rf"convoca(?:d[oa]s?|t(?:s|es)?|dos?|das?)\s+(?:por|mediante|en|per|pola|polo)\s+(?:la\s+|el\s+|l')?"
                     rf"(?P<tipo>{_TIPO})\s*(?P<cod>{_COD})?,?\s*(?:[^,;.]{{0,90}}?\s)?de\s+{_FECHA}", re.IGNORECASE)
RE_ORGANO = re.compile(rf"^\s*{_TIPO}\s*(?:{_COD})?,?\s+de\s+\d{{1,2}}\s+de\s+\w+(?:\s+de\s+\d{{4}})?,\s+"
                       r"(?:de la |del |de los |de las |de l'|de )(?P<org>[^,]{3,120}),", re.IGNORECASE)
RE_EXPEDIENTE = re.compile(r"\b(?:expediente|expedient|exp\.|proceso selectivo|procés selectiu|proceso)\s*"
                           r"(?:n[º°o.]*\s*|n[úu]m(?:ero)?\.?\s*)?(?P<e>\d{1,4}[A-Z]{1,6}/\d{2,4}|\d{4}/[A-Z0-9_]+/\d{3,8}|"
                           r"[A-Z]{1,6}[-/]\d{1,5}[-/]\d{2,4})\b", re.IGNORECASE)
RE_PUESTO = re.compile(r"\b(?P<k>plazas?|puestos?|categor[ií]as?|cuerpos?|escalas?|places?|prazas?|llocs?|bolsas? de trabajo|"
                       r"bolsas? de empleo|borsas? de treball|listas? de reserva|bolsas?)\s+(?:de\s+|d'\s*|del\s+|da\s+|do\s+)?"
                       r"(?:(?:una|un|dos|tres|\d+)\s+(?:plazas?\s+de\s+)?)?(?P<p>[^,.;:()]{3,90})", re.IGNORECASE)
# Otras formas de nombrar el puesto en un título: entre paréntesis tras el acto, tras «funcionario de carrera»,
# «selección de un…», «cobertura de una plaza de…»
RE_PUESTO_2 = re.compile(r"(?:funcionari[oa]s?|personal funcionario|personal laboral(?: fijo)?|laboral fij[oa]|interin[oa]s?)"
                         r"(?:\s+de\s+carrera|\s+en\s+pr[aá]cticas|\s+interin[oa])?\s+(?:de\s+(?:la\s+)?|del\s+|en\s+(?:la\s+)?)?"
                         r"(?:plaza\s+de\s+|categor[ií]a\s+de\s+)?(?P<p>[A-ZÁÉÍÓÚÑa-záéíóúñ][^,.;:()]{3,80})"
                         r"|(?:selecci[oó]n|cobertura|provisi[oó]n|contrataci[oó]n)\s+(?:de|d')\s+(?:un|una|dos|tres|\d+)\s+"
                         r"(?:plazas?\s+de\s+)?(?P<q>[^,.;:()]{3,80})"
                         r"|\((?P<r>[A-ZÁÉÍÓÚÑa-záéíóúñ][^()]{3,80})\)", re.IGNORECASE)
RE_NO_PUESTO = re.compile(r"^(?:\d|expte|exp\b|bop|boe|cr\.|oep|turno|libre|promoci|estabiliz|discapacidad|reserva|"
                          r"provisional|definitiv|a1|a2|c1|c2|subgrupo|grupo|jaen|jaén|ja[eé]n|[a-z]{1,3}$)", re.IGNORECASE)
RE_CORTE_PUESTO = re.compile(r"\s+(?:por|mediante|en|para|del|de la|de las|de los|con|vacantes?|incluid[ao]s?|"
                             r"turno|sistema|grupo|subgrupo|escala|subescala|clase|oferta|oep|correspondient\w*|"
                             r"pertenecient\w*|y fecha|i data|e data|y se|personal funcionario|personal laboral)\b.*$",
                             re.IGNORECASE)
RE_PROMOCION = re.compile(r"promoci[oó]n interna|promoció interna|promoción interna|promoci[oó]n horizontal")
RE_LIBRE = re.compile(r"\b(?:turno libre|acceso libre|torn lliure|acc[eé]s lliure|quenda libre)\b")
RE_PROVISIONAL = re.compile(r"\bprovisional")
RE_DEFINITIVA = re.compile(r"\bdefinitiv")
VENTANA_DIAS = 3 * 366
UNICO_TIPOS = {"admitidos", "tribunal", "examen", "aprobados"}
RE_BOLSA = re.compile(r"\b(?:bolsa|borsa|lista de reserva|listaxe|interin)")


def fecha_iso(d: str, m: str, a: str | None, cod: str | None, ref: str) -> str | None:
    mes = MESES.get(normalizar(m))
    if not mes:
        return None
    anio = int(a) if a else None
    if not anio and cod:
        c = re.search(r"(\d{4})$", cod)
        anio = int(c.group(1)) if c else None
    if not anio:  # «de 21 de julio» sin año: el del acto, o el anterior si esa fecha cae después
        anio = int(ref[:4])
        if f"{anio}-{mes:02d}-{int(d):02d}" > ref:
            anio -= 1
    try:
        return date(anio, mes, int(d)).isoformat()
    except ValueError:
        return None


def disposicion(titulo: str | None, fecha_acto: str) -> tuple[str | None, str | None]:
    """(fecha de la disposición, código) de un título que empieza «Resolución de 15 de julio de 2026, …»."""
    m = RE_DISPOSICION.search(titulo or "")
    if not m:
        return None, None
    return fecha_iso(m.group("d"), m.group("m"), m.group("a"), m.group("cod"), fecha_acto), m.group("cod")


def cita_convocatoria(titulo: str | None, fecha_acto: str) -> tuple[str | None, str | None]:
    """(fecha, código) de la convocatoria que cita un acto posterior: «… convocado por Resolución de 15 de julio»."""
    m = RE_CITA.search(titulo or "")
    if not m:
        return None, None
    return fecha_iso(m.group("d"), m.group("m"), m.group("a"), m.group("cod"), fecha_acto), m.group("cod")


def organo(titulo: str | None) -> str | None:
    m = RE_ORGANO.search(titulo or "")
    return re.sub(r"[^a-z0-9ñ]+", " ", normalizar(m.group("org"))).strip() if m else None


def expediente(titulo: str | None) -> str | None:
    m = RE_EXPEDIENTE.search(titulo or "")
    return m.group("e").upper() if m else None


RE_CORTE_CUERPO = re.compile(r"\s+(?:por|mediante|en|para|con|vacantes?|turno|sistema|grupo|subgrupo|oferta|oep|"
                             r"correspondient\w*|y fecha|i data|e data|y se)\b.*$", re.IGNORECASE)


GENERICOS = {"vacantes", "varias", "diversas", "diversos", "distintas", "plantilla", "estructural", "estructurales",
             "naturaleza", "personal", "plazas", "puestos", "empleo", "trabajo", "temporal", "fijo", "fija",
             "funcionario", "funcionaria", "laboral", "carrera", "practicas", "interino", "interina", "general",
             "i", "y", "e", "de", "del", "la", "el", "los", "las"}


def _clave_puesto(p: str, cuerpo: bool = False) -> str | None:
    from motor.catalogo.territorio import provincia
    p = (RE_CORTE_CUERPO if cuerpo else RE_CORTE_PUESTO).sub("", p).strip(" -")
    if provincia(p) or set(normalizar(p).split()) <= GENERICOS:  # «(Córdoba)», «plazas vacantes»
        return None
    if len(p) < 3 or RE_NO_PUESTO.match(normalizar(p)) or \
            normalizar(p).startswith(("trabajo", "empleo", "personal", "funcionari", "laboral", "carrera", "practicas")):
        return None
    clave = normalizar_puesto(p)["clave"]
    return clave if clave and len(clave) >= 3 else None


def puesto(titulo: str | None) -> str | None:
    """Clave del puesto que nombra un título («… una plaza de Auxiliar Administrativo, …» -> auxiliar-administrativo;
    «Nombramiento de funcionaria de carrera (Técnica de Exacciones y Rentas)»; «selección de un Notificador»)."""
    for m in RE_PUESTO.finditer(titulo or ""):
        if (c := _clave_puesto(m.group("p"), normalizar(m.group("k")).startswith(("cuerpo", "escala")))):
            return c
    for m in RE_PUESTO_2.finditer(titulo or ""):
        if (c := _clave_puesto(m.group("p") or m.group("q") or m.group("r"))):
            return c
    return None


def puesto_en_texto(texto: str | None) -> str | None:
    """Puesto del principio del texto de un acto cuyo título no lo nombra («Nombramiento de funcionario de carrera»:
    «… ha sido nombrado funcionario de carrera en la plaza de Agente de Policía Local …»). Solo la clave del puesto;
    nada más del texto (que puede llevar nombres)."""
    cabeza = re.sub(r"\s+", " ", (texto or "")[:2000])
    for frase in re.split(r"(?<=[.;:])\s+", cabeza):
        if (q := puesto(frase)):
            return q
    return None


def turno(titulo: str | None) -> str | None:
    t = normalizar(titulo or "")
    if RE_PROMOCION.search(t):
        return "promocion_interna"
    if RE_LIBRE.search(t):
        return "libre"
    return None


RE_EXAMEN = re.compile(rf"(?:ejercicio|examen|prueba|exercici|exame|proba)\w*[^.;]{{0,80}}?(?:el\s+|o\s+|del\s+)?"
                       rf"(?:d[ií]a\s+)?(?:\w+,?\s+)?{_FECHA}", re.IGNORECASE)


def fecha_examen(titulo: str | None, fecha_acto: str) -> str | None:
    """Fecha de un ejercicio que da el propio título («… y fecha del primer ejercicio el 15 de noviembre de 2026»),
    si es posterior a la publicación."""
    m = RE_EXAMEN.search(titulo or "")
    if not m:
        return None
    f = fecha_iso(m.group("d"), m.group("m"), m.group("a"), None, fecha_acto)
    if f and f < fecha_acto:  # sin año explícito: «el 15 de enero» publicado en diciembre es del año siguiente
        f = fecha_iso(m.group("d"), m.group("m"), m.group("a") or str(int(fecha_acto[:4]) + 1), None, fecha_acto)
    return f if f and f >= fecha_acto else None


def fase_de(acto: dict) -> str | None:
    f = FASE.get(acto.get("tipo_acto") or acto.get("tipo"))
    if f == "admitidos":
        t = normalizar(acto.get("titulo") or "")
        if RE_DEFINITIVA.search(t):
            return "admitidos_definitivo"
        if RE_PROVISIONAL.search(t):
            return "admitidos_provisional"
    return f


def unir(procesos: list[dict], origenes: dict[str, dict], actos: list[dict], clave_convocante) -> tuple[Counter, list[dict]]:
    """Une a los procesos los actos posteriores que aún no estén en ninguno. Modifica los procesos (añade a
    «actos» y «uniones») y devuelve (recuento por motivo, huérfanos).

    origenes: id de proceso -> acto de origen (para sus claves). clave_convocante(acto) -> lista de claves del
    convocante (código INE, nombre normalizado u órgano).
    """
    por_acto: dict[str, dict] = {}
    por_fecha: dict[str, list[dict]] = defaultdict(list)
    por_codigo: dict[str, list[dict]] = defaultdict(list)
    por_expediente: dict[tuple[str, str], list[dict]] = defaultdict(list)
    por_puesto: dict[tuple[str, str], list[dict]] = defaultdict(list)
    from motor.procesos import clave_organo, fuente_de_boletin
    por_publicacion: dict[tuple[str, str], list[dict]] = defaultdict(list)  # (boletín, fecha) -> procesos
    por_convocante: dict[str, list[dict]] = defaultdict(list)
    claves_proc: dict[str, set[str]] = {}
    puestos_proc: dict[str, set[str]] = {}
    for p in procesos:
        o = origenes.get(p["id"]) or {}
        for a in p.get("actos") or []:
            por_acto[a["id"]] = p
        for a in p.get("otras_publicaciones") or []:
            por_acto.setdefault(a["id"], p)
        for a in (p.get("actos") or [])[:1] + (p.get("otras_publicaciones") or []):
            if a.get("fecha"):
                por_publicacion[(a.get("fuente") or "BOE", a["fecha"])].append(p)
        conv = set(clave_convocante(o)) if o else set()
        org = organo(p.get("titulo"))
        if org:
            conv.add("org:" + clave_organo(org, o.get("fuente") or (p.get("fuentes") or ["BOE"])[0]))
        claves_proc[p["id"]] = conv
        f, cod = disposicion(p.get("titulo"), p.get("apertura_plazo") or "9999")
        if f:
            por_fecha[f].append(p)
        if cod:
            por_codigo[cod.upper()].append(p)
        pu = {x.get("puesto_clave") for x in p.get("plazas") or [] if x.get("puesto_clave")}
        for tit in [p.get("titulo")] + [o.get("titulo") for o in p.get("otras_publicaciones") or []]:
            if (q := puesto(tit)):
                pu.add(q)
        puestos_proc[p["id"]] = pu
        e = expediente(p.get("titulo"))
        for k in conv:
            por_convocante[k].append(p)
            if e:
                por_expediente[(k, e)].append(p)
            for q in pu:
                por_puesto[(k, q)].append(p)

    def mismo_convocante(cands: list[dict], claves: set[str]) -> list[dict]:
        return [c for c in cands if claves_proc.get(c["id"]) & claves]

    def por_puesto_y_turno(cands: list[dict], q: str | None, t: str | None) -> list[dict]:
        if len(cands) > 1 and q:
            cands = [c for c in cands if q in puestos_proc.get(c["id"], set())] or cands
        if len(cands) > 1 and t:
            cands = [c for c in cands if turno(c.get("titulo")) in (t, None)] or cands
        return cands

    recuento, huerfanos = Counter(), []
    for x in sorted(actos, key=lambda a: (a.get("fecha") or "", a["id"])):
        if x["id"] in por_acto or (x.get("tipo_acto") not in POSTERIORES) or x.get("alcance") not in (None, "acceso"):
            continue
        fecha = x.get("fecha") or ""
        claves = set(clave_convocante(x))
        if (org := organo(x.get("titulo"))):
            claves.add("org:" + clave_organo(org, x.get("fuente")))
        q, t = puesto(x.get("titulo")) or x.get("puesto_texto"), turno(x.get("titulo"))
        elegido, motivo = None, None
        # 1. referencia explícita (identificador del BOE de la convocatoria o de otro acto ya unido)
        refs = {por_acto[r]["id"]: por_acto[r] for r in x.get("refiere_a") or [] if r in por_acto}
        if len(refs) == 1:
            elegido, motivo = next(iter(refs.values())), "referencia"
        # 1b. cita en el texto del boletín, número y fecha donde salieron las bases o la convocatoria
        if not elegido:
            vistos: dict[str, dict] = {}
            for c in (x.get("citas") or []) + (x.get("boletines_citados") or []):
                b = c.get("boletin") or ""
                fuente = "BOE" if re.sub(r"[.\s]", "", b).upper() == "BOE" or "del estado" in normalizar(b) else \
                    fuente_de_boletin(b) or (x.get("fuente") if re.sub(r"[.\s]", "", b).upper().startswith("BOP") else None)
                if not fuente or not c.get("fecha") or c["fecha"] > fecha:
                    continue
                for cand in mismo_convocante(por_publicacion.get((fuente, c["fecha"]), []), claves):
                    vistos[cand["id"]] = cand
            cands = por_puesto_y_turno(list(vistos.values()), q, t)
            if len(cands) == 1:
                elegido, motivo = cands[0], "cita_boletin"
        # 2. cita de la convocatoria en el título
        if not elegido:
            fc, cod = cita_convocatoria(x.get("titulo"), fecha)
            cands = por_codigo.get(cod.upper(), []) if cod else []
            if not cands and fc:
                cands = mismo_convocante(por_fecha.get(fc, []), claves)
            cands = por_puesto_y_turno([c for c in cands if (c.get("apertura_plazo") or "") <= fecha], q, t)
            if len(cands) == 1:
                elegido, motivo = cands[0], "cita_convocatoria"
        # 3. expediente del mismo convocante
        if not elegido and (e := expediente(x.get("titulo"))):
            cands = {c["id"]: c for k in claves for c in por_expediente.get((k, e), [])}
            if len(cands) == 1:
                elegido, motivo = next(iter(cands.values())), "expediente"
        # 4. convocante + puesto (+ turno), convocatoria anterior y de los tres años previos
        if not elegido and q and claves:
            cands = {c["id"]: c for k in claves for c in por_puesto.get((k, q), [])
                     if (c.get("apertura_plazo") or "") <= fecha and _dias(c.get("apertura_plazo"), fecha) <= VENTANA_DIAS}
            cands = por_puesto_y_turno(list(cands.values()), None, t)
            cands = _por_rasgos(cands, x.get("titulo"))
            if len(cands) == 1:
                elegido, motivo = cands[0], "convocante_puesto"
            elif len(cands) > 1 and (r := _mas_reciente_clara(cands, fecha, x.get("tipo_acto"))):
                elegido, motivo = r, "convocante_puesto_reciente"
            elif len(cands) > 1:
                motivo = f"varios_candidatos:{len(cands)}"
        # 4b. mismo convocante, puesto parecido («operarios servicios múltiples» y «servicios múltiples»)
        if not elegido and not motivo and q and claves:
            cands = {c["id"]: c for k in claves for c in por_convocante.get(k, [])
                     if (c.get("apertura_plazo") or "") <= fecha and _dias(c.get("apertura_plazo"), fecha) <= VENTANA_DIAS}
            mejores = _parecidos(list(cands.values()), q, puestos_proc)
            mejores = _por_rasgos(por_puesto_y_turno(mejores, None, t), x.get("titulo"))
            if len(mejores) == 1:
                elegido, motivo = mejores[0], "convocante_puesto_parecido"
        # 4b'. sin puesto en el título: si el convocante tiene una sola convocatoria en el año anterior al acto, y el
        # acto es de los que siguen pronto a la convocatoria (listas, tribunal, examen, resultados)
        if not elegido and not motivo and not q and claves and x.get("tipo_acto") in UNICO_TIPOS:
            cands = {c["id"]: c for k in claves for c in por_convocante.get(k, [])
                     if (c.get("apertura_plazo") or "") <= fecha and _dias(c.get("apertura_plazo"), fecha) <= 366}
            if len(cands) == 1:
                c = next(iter(cands.values()))
                tit_c = " ".join([c.get("titulo") or ""] + [o.get("titulo") or "" for o in c.get("otras_publicaciones") or []])
                bolsa_x = bool(RE_BOLSA.search(normalizar(x.get("titulo") or "")))
                # La única convocatoria tiene que ser del mismo tipo: estabilización o no, bolsa o plaza
                if _rasgos(x.get("titulo"))[0] == _rasgos(tit_c)[0] and (not bolsa_x or c.get("temporal")) and \
                        (bolsa_x or not c.get("temporal") or not RE_BOLSA.search(normalizar(c.get("titulo") or ""))):
                    elegido, motivo = c, "convocante_unico"
        # 4c. estabilización (Ley 20/2021): una sola convocatoria de estabilización del convocante, sin puestos
        # conocidos, en los dos años anteriores
        if not elegido and not (motivo or "").startswith("varios") and claves and _rasgos(x.get("titulo"))[0]:
            cands = {c["id"]: c for k in claves for c in por_convocante.get(k, [])
                     if (c.get("apertura_plazo") or "") <= fecha and _dias(c.get("apertura_plazo"), fecha) <= 2 * 366
                     and _rasgos(" ".join([c.get("titulo") or ""] + [o.get("titulo") or "" for o in
                                                                     c.get("otras_publicaciones") or []]))[0]}
            sin_puesto = [c for c in cands.values() if not puestos_proc.get(c["id"])]
            if len(cands) == 1 and sin_puesto:
                elegido, motivo = sin_puesto[0], "convocante_estabilizacion"
        if elegido:
            elegido.setdefault("uniones", Counter())[motivo] += 1
            elegido["actos"].append({"id": x["id"], "fecha": fecha, "tipo": x.get("tipo_acto"),
                                     "fuente": x.get("fuente") or "BOE", "url": x.get("url"), "union": motivo,
                                     **({"fase": fase_de(x)} if fase_de(x) else {}),
                                     **({"personas_en_listas": x["personas_en_listas"]}
                                        if x.get("personas_en_listas") is not None else {}),
                                     **({"fecha_examen": fe} if (fe := fecha_examen(x.get("titulo"), fecha)) else {})})
            por_acto[x["id"]] = elegido
            recuento[motivo] += 1
        else:
            m = motivo or ("sin_puesto_ni_cita" if not q else "sin_candidato")
            recuento["huerfano:" + m.split(":")[0]] += 1
            huerfanos.append({"id": x["id"], "fecha": fecha, "fuente": x.get("fuente") or "BOE",
                              "tipo": x.get("tipo_acto"), "titulo": x.get("titulo"), "url": x.get("url"),
                              "convocante": sorted(k for k in claves if not k.startswith("org:"))[:2],
                              "puesto": q, "motivo": m})
    for p in procesos:
        if "uniones" in p:
            p["uniones"] = dict(p["uniones"])
            p["actos"].sort(key=lambda a: (a.get("fecha") or "", a["id"]))
    return recuento, huerfanos


RE_ESTABILIZACION = re.compile(r"estabiliz|consolidaci[oó]n de empleo|disposicion adicional (?:sexta|octava)|"
                               r"ley 20/2021|excepcional")
RE_NUM_PLAZAS = re.compile(r"\b(\d{1,3}|una|un|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s+(?:plazas?|places|prazas)\b")
NUMEROS = {"un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
           "nueve": 9, "diez": 10}


def _rasgos(titulo: str | None) -> tuple[bool, int | None]:
    t = normalizar(titulo or "")
    m = RE_NUM_PLAZAS.search(t)
    n = (int(m.group(1)) if m.group(1).isdigit() else NUMEROS.get(m.group(1))) if m else None
    return bool(RE_ESTABILIZACION.search(t)), n


def _por_rasgos(cands: list[dict], titulo: str | None) -> list[dict]:
    """Entre varias convocatorias del mismo puesto: la de estabilización si el acto lo es (o al revés) y la del
    mismo número de plazas, si consta en los dos."""
    if len(cands) <= 1:
        return cands
    estab, n = _rasgos(titulo)
    mismos = [c for c in cands if _rasgos(" ".join([c.get("titulo") or ""] + [o.get("titulo") or "" for o in
                                                   c.get("otras_publicaciones") or []]))[0] == estab]
    cands = mismos or cands
    if n and len(cands) > 1:
        cands = [c for c in cands if c.get("total_plazas") in (n, None)] or cands
    return cands


def _mas_reciente_clara(cands: list[dict], fecha: str, tipo: str | None) -> dict | None:
    """La convocatoria más reciente anterior al acto, si la siguiente es claramente más antigua (un año o más) y
    el acto llega en un tiempo normal para su fase (admitidos o tribunal, hasta un año; el resto, hasta dos)."""
    orden = sorted(cands, key=lambda c: c.get("apertura_plazo") or "", reverse=True)
    a, b = orden[0], orden[1]
    margen = _dias(b.get("apertura_plazo"), a.get("apertura_plazo") or fecha)
    limite = 366 if tipo in ("admitidos", "tribunal") else 2 * 366
    if margen >= 366 and _dias(a.get("apertura_plazo"), fecha) <= limite:
        return a
    return None


def _palabras(clave: str) -> set[str]:
    return {w for w in clave.split("-") if w not in GENERICOS and len(w) > 2}


def _parecidos(cands: list[dict], q: str, puestos_proc: dict[str, set[str]]) -> list[dict]:
    """Convocatorias cuyo puesto comparte la mayor parte de las palabras con el del acto (similitud de Jaccard de
    0,6 o más); solo las de la mejor similitud."""
    pq = _palabras(q)
    if not pq:
        return []
    puntos = []
    for c in cands:
        mejor = max((len(pq & _palabras(k)) / len(pq | _palabras(k)) for k in puestos_proc.get(c["id"], ()) if
                     _palabras(k)), default=0)
        if mejor >= 0.6:
            puntos.append((mejor, c))
    if not puntos:
        return []
    tope = max(p for p, _ in puntos)
    return [c for p, c in puntos if p == tope]


def _dias(desde: str | None, hasta: str) -> int:
    try:
        return (date.fromisoformat(hasta[:10]) - date.fromisoformat((desde or hasta)[:10])).days
    except ValueError:
        return 10 ** 6


def resultados(p: dict) -> list[dict]:
    """Cifras agregadas de cada fase, contadas en las listas publicadas (líneas con documento de identidad); nunca
    nombres. «personas» cuenta a todas las de la lista: en las de admitidos, admitidas y excluidas juntas."""
    out = []
    for a in p.get("actos") or []:
        n = a.get("personas_en_listas")
        f = a.get("fase") or fase_de(a)
        if n and f in ("admitidos_provisional", "admitidos_definitivo", "admitidos", "aprobados", "nombramiento"):
            out.append({"fase": f, "fecha": a.get("fecha"), "personas": n, "acto": a["id"], "fuente": a.get("fuente"),
                        "como": "líneas de la lista con documento de identidad (sin guardar ningún dato personal)"})
    return out


def fase_y_estado(p: dict, hoy: date) -> None:
    """Fase del último acto posterior conocido; si hay alguno posterior al fin de plazo, es el estado. Añade los
    resultados agregados que se conozcan."""
    if (r := resultados(p)):
        p["resultados"] = r
    examenes = sorted({a["fecha_examen"] for a in p.get("actos") or [] if a.get("fecha_examen")})
    if examenes:
        p["fechas_examen"] = examenes
    fases = [(a.get("fecha") or "", a.get("fase") or fase_de(a)) for a in p.get("actos") or []]
    fases = [(f, x) for f, x in fases if x]
    if not fases:
        return
    fecha, fase = max(fases, key=lambda fx: (fx[0], ORDEN_FASES.index(fx[1]) if fx[1] in ORDEN_FASES else -1))
    p["fase"], p["fase_fecha"] = fase, fecha
    if p.get("estado") == "anulado":
        return
    if p.get("estado") == "plazo_abierto" and fase not in ("anulado", "desierto"):
        return  # sigue abierto el plazo (p. ej., la lista de admitidos de otra convocatoria del mismo puesto)
    p["estado"] = fase
