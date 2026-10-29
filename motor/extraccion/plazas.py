"""Plazas convocadas a partir del texto de una convocatoria (Estado, comunidades y universidades).

Formas verificadas en convocatorias reales del BOE (2025-2026):
  «2.1 Se convoca proceso selectivo para cubrir cincuenta plazas del Cuerpo Especial de Instituciones
   Penitenciarias, Subgrupo A2 (Código 0913) por el sistema general de acceso libre.»
  «1.1 Se convocan pruebas selectivas para cubrir, por el sistema de concurso-oposición libre, doce plazas de
   funcionario de carrera en la Escala Auxiliar Técnica de la Universidad de Almería (Subgrupo C2).»
  «2.2 En concreto, se convoca proceso selectivo para cubrir 68 plazas de acceso libre, 4 en la categoría de
   Albañil, 5 en la categoría de Calefactor/a, ...»
  «1.1 Se convoca proceso selectivo para proveer una plaza de personal laboral en la categoría de Técnico
   Especialista (Gestión de Datos) de la Universidad de Córdoba, Grupo III, ...»

Devuelve el total, el desglose por categoría si lo hay, y la denominación (cuerpo, escala o categoría) con su
grupo cuando el texto lo dice. La frase se guarda como cita. Si no hay frase clara, no se devuelve nada.
"""

from __future__ import annotations

import re

from motor.boe.clasificar import normalizar
from motor.catalogo.puestos import grupo, normalizar_puesto
from motor.extraccion.plazo import frases
from motor.extraccion.texto_es import numero

VERSION = "plazas_general_v2"

L = "a-záéíóúñàèòïüç·"
RE_PLAZAS = re.compile(
    r"\b(?:convoca\w*|convoqu\w*|cubrir|cobrir|proveer|proveir|provisió\s+(?:en\s+propietat\s+)?(?:de|d['’])|"
    rf"cobertura\s+(?:definitiva\s+)?(?:de|d['’])|selecció\s+de)[^.;]{{0,140}}?\b(?P<n>\d{{1,4}}|[{L}]+"
    rf"(?:-i-[{L}]+)?(?:\s+[ye]\s+[{L}]+)?)\s+(?:\(\d{{1,4}}\)\s+)?(?:plazas?|places|pla[çc]a|prazas?)\b"
    r"(?P<resto>[^;]{0,400})", re.IGNORECASE)
# Denominación en convocatorias locales: «una plaça de caporal/a de la Policia Local», «dos plazas de Auxiliar»
RE_DENOMINACION_LOCAL = re.compile(
    r"^\s*(?:vacants?\s+|vacantes?\s+)?(?:de\s+|d['’]\s*)(?P<den>[^,;.(]{3,120}?)(?=,|;|\.|\(|\s+mitjan[çc]ant|"
    r"\s+mediante|\s+per\s|\s+pel\s|\s+por\s|\s+en\s+r[èe]gim|\s+vacants?\b|\s+del\s+grup|\s+grupo?\b|\s+subgrupo?\b|"
    r"\s+de\s+l['’]escala|\s+de\s+la\s+escala|\s+de\s+la\s+plantilla|\s+incl[oò]s|\s+enquadrad|\s+encuadrad|"
    r"\s+pertanyent|\s+perteneciente|\s+de\s+la\s+subescala|$)", re.IGNORECASE)
RE_OBJETO = re.compile(
    r"(?:del|de\s+la|en\s+el|en\s+la|de)\s+(?P<obj>(?:Cuerpo|Escala|Subescala|categor[ií]a(?:\s+profesional)?(?:\s+de)?)\s+"
    r"[^,(;]{3,160})", re.IGNORECASE)
RE_DESGLOSE = re.compile(
    r"(?P<n>\d{1,4})\s+(?:plazas?\s+)?en\s+la\s+categor[ií]a\s+de\s+(?P<cat>[^,;.]+?)(?=,|;|\.|\s+y\s+\d|$)",
    re.IGNORECASE)
RE_CORTE_OBJETO = re.compile(
    r"\s+(?:por\s+el\s+sistema|mediante|c[oó]digo|en\s+r[eé]gimen|para\s+la\s+sede|con\s+destino|y\s+con|en\s+la\s+"
    r"localidad|de\s+acceso\s+libre)\b.*$", re.IGNORECASE)
RE_COLA_DENOMINACION = re.compile(
    r"\s+(?:que\s+(?:se|figura|figuran|consta)|en\s+el\s+anexo|del\s+anexo|de\s+l['’]annex|de\s+esta\s+universidad|"
    r"de\s+la\s+presente|d['’]aquest).*$", re.IGNORECASE)
RE_NO_DENOMINACION = re.compile(
    r"(?:acceso|acc[eé]s|turno|torn|nuevo ingreso|personal|funcionari|car[aá]cter|naturaleza|igual|promoci|diversas|"
    r"distintas|varias|diferentes|diverses|la\s|el\s|les\s|los\s|las\s)", re.IGNORECASE)
EXCLUIR = ("se convoco", "convocado", "convocada", "han superado", "superado el proceso", "relacion de personas",
           "se publica", "nombramiento", "han superat", "nomenament", "nomeamento")


def _turno(f: str) -> str | None:
    n = normalizar(f)
    if "promocion interna" in n and "acceso libre" not in n and "turno libre" not in n:
        return "promocion_interna"
    if "acceso libre" in n or "turno libre" in n or "oposicion libre" in n:
        return "libre"
    return None


def extraer_plazas(texto: str) -> dict | None:
    for f in frases(texto)[:400]:
        n_f = normalizar(f)
        if not any(p in n_f for p in ("plaza", "placa", "places", "praza")) or any(x in n_f for x in EXCLUIR):
            continue
        m = RE_PLAZAS.search(f)
        if not m:
            continue
        total = numero(m.group("n"))
        if not total:
            continue
        resto = m.group("resto")
        res: dict = {"total": total, "cita": f, "metodo": VERSION, "turno": _turno(f)}
        desglose = [(numero(d.group("n")), " ".join(d.group("cat").split())) for d in RE_DESGLOSE.finditer(resto)]
        desglose = [(n, c) for n, c in desglose if n]
        if desglose:
            res["plazas"] = [_plaza(n, c, f) for n, c in desglose]
            return res
        o = RE_OBJETO.search(resto)
        if o:
            obj = RE_CORTE_OBJETO.sub("", " ".join(o.group("obj").split())).strip(" .")
            obj = re.sub(r"(?i)^categor[ií]a(?:\s+profesional)?(?:\s+de)?\s+", "", obj)
            res["plazas"] = [_plaza(total, obj, f)]
        else:
            d = RE_DENOMINACION_LOCAL.match(resto)
            den = " ".join(d.group("den").split()).strip(" .") if d else ""
            den = RE_COLA_DENOMINACION.sub("", den).strip(" .")
            if den and not RE_NO_DENOMINACION.match(den) and not re.search(r"(?i)\b(?:plazas|places|prazas)\b", den):
                res["plazas"] = [_plaza(total, den, f)]
        return res
    return None


RE_DE_LA_UNIVERSIDAD = re.compile(r"\s+de\s+la\s+(?:Universidad|Universitat)\b.*$", re.IGNORECASE)


def _plaza(n: int, denominacion: str, frase: str) -> dict:
    norm = normalizar_puesto(RE_DE_LA_UNIVERSIDAD.sub("", denominacion) or denominacion)
    g, g_fuente = grupo(frase, None, None)
    return {"numero": n, "denominacion": denominacion, "puesto_clave": norm["clave"], "puesto": norm["nombre"],
            "especialidad": norm["especialidad"], "grupo": g, "grupo_fuente": g_fuente, "turno": _turno(frase)}
