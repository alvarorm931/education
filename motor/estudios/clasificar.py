"""Clasificación de los proveedores verificados del censo de másters: ¿centro que imparte, agregador, medio...?

El rastreo verifica que un dominio tiene fichas de programa en España, pero no distingue quién es: una escuela
que vende sus másters, un portal que lista los de otros (Emagister, Educaweb...), un blog o un sitio de otro país.
Con la portada de cada sitio (título, descripción, encabezados, textos de menú y el principio del texto) y los
títulos de las fichas que encontró el rastreador, Claude Haiku clasifica el sitio en lote. El nombre del centro
solo se acepta si su cita literal está en la portada (misma regla que la extracción).

Para el censo solo cuentan los «centro» con ámbito España o internacional: los agregadores se guardan aparte
y no se usan como fuente (sus datos no son de primera mano y su base de datos está protegida).

Privacidad y derechos: la portada se pide con el lector cortés (robots.txt, reserva TDM); su original y lo
enviado a la API van solo al almacén privado; lo público lleva la clasificación, el motivo en palabras de la IA
(≤20) y las huellas.

Uso:
  python -m motor.estudios.clasificar entrada --censo proveedores.jsonl --rastreo carpeta [--rastreo …] --salida e.jsonl
  python -m motor.estudios.clasificar lote --entrada e.jsonl --salida ruta/ [--esperar-min 40]   # ANTHROPIC_API_KEY
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import html as html_lib
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

from motor.estudios import extraer

CATEGORIAS = {"centro", "agregador", "medio", "otro"}
TIPOS = {"universidad", "centro_adscrito", "escuela_negocios", "escuela_formacion", "academia",
         "colegio_profesional", "fundacion_o_asociacion", "empresa", "otro"}
AMBITOS = {"espana", "otro_pais", "internacional"}

SISTEMA = (
    "Clasificas sitios web para un censo de centros que imparten másters en España. Recibes la portada de un "
    "sitio y títulos de páginas suyas que parecen programas. Devuelves un objeto JSON con categoria, tipo_centro, "
    "ambito, vende_masters, nombre, cita_nombre, confianza y motivo. "
    "categoria: «centro» si imparte y vende sus propios programas (universidad, centro adscrito, escuela de "
    "negocios, escuela de formación, academia, colegio o asociación profesional, fundación, empresa de formación, "
    "hospital o sociedad científica que forma); «agregador» si lista, compara o vende programas de otros centros "
    "(buscador, directorio, comparador, marketplace, intermediario de matrícula); «medio» si es noticias, blog, "
    "ranking, guía o revista sin programas propios; «otro» si no es un sitio de formación (tienda, empresa de otro "
    "sector, sitio personal). "
    "tipo_centro, si categoria es centro: universidad | centro_adscrito | escuela_negocios | escuela_formacion "
    "| academia | colegio_profesional | fundacion_o_asociacion | empresa | otro; si no es centro, ninguno. "
    "ambito: espana (sede o público principal en España) | otro_pais | internacional (varios países, España "
    "incluida). vende_masters: true si hay másters (máster propio, executive máster, MBA, máster universitario) que "
    "este sitio imparte o vende como suyos. nombre: nombre del centro u organización; cita_nombre: una frase copiada "
    "exactamente de la portada que lo contiene (3 a 15 palabras); si no aparece, los dos vacíos. motivo: 20 palabras "
    "como máximo, tuyas. Solo lo que se ve en el texto; si dudas, confianza baja."
)
MAX_TOKENS = 800
# Salida estructurada (output_config.format, json_schema): la API garantiza JSON válido con estos campos. Sin ella,
# el 5 % de las respuestas no se podía leer (comillas de la portada dentro de la cita, sin escapar).
ESQUEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["categoria", "tipo_centro", "ambito", "vende_masters", "nombre", "cita_nombre", "confianza", "motivo"],
    "properties": {
        "categoria": {"type": "string", "enum": sorted(CATEGORIAS)},
        "tipo_centro": {"type": "string", "enum": sorted(TIPOS | {"ninguno"})},
        "ambito": {"type": "string", "enum": sorted(AMBITOS)},
        "vende_masters": {"type": "boolean"},
        "nombre": {"type": "string", "description": "vacío si no aparece"},
        "cita_nombre": {"type": "string", "description": "frase copiada de la portada que contiene el nombre; vacía si no"},
        "confianza": {"type": "string", "enum": ["alta", "media", "baja"]},
        "motivo": {"type": "string", "description": "20 palabras como máximo"},
    },
}

RE_TITULO = re.compile(r"(?is)<title[^>]*>(.*?)</title>")
RE_META = re.compile(r'(?is)<meta\s+[^>]*(?:name|property)=["\'](description|og:site_name|og:title)["\'][^>]*>')
RE_CONTENT = re.compile(r'(?is)content=["\'](.*?)["\']')
RE_ENCAB = re.compile(r"(?is)<h([12])\b[^>]*>(.*?)</h\1>")
RE_ENLACE = re.compile(r"(?is)<a\b[^>]*>(.*?)</a>")
RE_ETIQUETA = re.compile(r"(?s)<[^>]+>")


def _limpio(s: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(RE_ETIQUETA.sub(" ", s or ""))).strip()


def texto_portada(html: str, max_cuerpo: int = 1500) -> str:
    """Lo que dice quién es el sitio: título, metadatos, encabezados, textos de menú y principio del texto."""
    lineas = []
    m = RE_TITULO.search(html)
    if m:
        lineas.append("Título: " + _limpio(m.group(1))[:200])
    for mm in RE_META.finditer(html):
        c = RE_CONTENT.search(mm.group(0))
        if c and _limpio(c.group(1)):
            lineas.append(f"{mm.group(1)}: {_limpio(c.group(1))[:300]}")
    encab = list(dict.fromkeys(_limpio(x.group(2))[:120] for x in RE_ENCAB.finditer(html)))
    encab = [e for e in encab if e][:12]
    if encab:
        lineas.append("Encabezados: " + " · ".join(encab))
    menu = list(dict.fromkeys(t for t in (_limpio(x.group(1)) for x in RE_ENLACE.finditer(html)) if 2 < len(t) <= 40))
    if menu:
        lineas.append("Enlaces: " + " · ".join(menu[:80]))
    cuerpo = extraer.texto_de_pagina(html)[:max_cuerpo]
    if cuerpo:
        lineas.append("Texto: " + cuerpo)
    return "\n".join(lineas)


def _muestra(r: dict) -> list:
    m = r.get("muestra") or []
    if isinstance(m, str):  # algunos rastreos antiguos la guardaron como texto de Python
        try:
            m = ast.literal_eval(m)
        except (ValueError, SyntaxError):
            m = []
    return m


def entrada(censo: Path, rastreos: list[Path], salida: Path, estados: tuple[str, ...] = ("verificado",)) -> dict:
    """Une a cada proveedor del censo su último rastreo: web final, nº de fichas y títulos de su muestra."""
    provs = {}
    for l in censo.read_text(encoding="utf-8").split("\n"):
        if l.strip():
            p = json.loads(l)
            if p["estado"] in estados:
                provs[p["id"]] = p
                for i in p.get("ids_unidos", []):
                    provs.setdefault(i, p)
    ultimo: dict[str, dict] = {}
    for c in rastreos:  # de más antiguo a más reciente: gana el último
        for f in sorted(c.rglob("oferta_web/*.json")):
            r = json.loads(f.read_text(encoding="utf-8"))
            cen = r.get("centro") or {}
            if isinstance(cen, str):
                try:
                    cen = ast.literal_eval(cen)
                except (ValueError, SyntaxError):
                    cen = {}
            if cen.get("id") in provs:
                ultimo[provs[cen["id"]]["id"]] = r
    filas = []
    for i, p in provs.items():
        if i != p["id"]:
            continue
        r = ultimo.get(i, {})
        muestra = _muestra(r)
        titulos = [{"titulo": (m.get("titulo") or "")[:160], "ruta": urlparse(m.get("url", "")).path[:120],
                    "es_programa": bool(m.get("es_programa"))} for m in muestra if m.get("url")][:8]
        web = r.get("base_final") or r.get("base") or (p.get("webs") or [f"https://{p['dominio']}"])[0]
        filas.append({"id": i, "dominio": p["dominio"], "web": web, "urls_programa": r.get("urls_programa"),
                      "paginas_programa_validas": r.get("paginas_programa_validas"), "titulos": titulos,
                      "tipos_censo": p.get("tipos", []), "fuentes": p.get("fuentes", [])})
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in filas), encoding="utf-8")
    return {"proveedores": len(filas), "con_rastreo": sum(1 for f in filas if f["urls_programa"] is not None)}


def mensaje(fila: dict, portada: str | None) -> str:
    partes = [f"Dominio: {fila['dominio']}", f"Portada ({fila['web']}):", portada or "(no se pudo leer la portada)"]
    if fila.get("titulos"):
        partes.append(f"Páginas que parecen programas ({fila.get('urls_programa') or 0} en total). Muestra:")
        partes += [f"- {t['titulo']} [{t['ruta']}]" for t in fila["titulos"]]
    return "\n".join(partes)[:12_000]


def peticion(cid: str, texto: str) -> dict:
    return {"custom_id": cid, "params": {
        "model": extraer.MODELO, "max_tokens": MAX_TOKENS,
        "system": [{"type": "text", "text": SISTEMA, "cache_control": {"type": "ephemeral"}}],
        "thinking": extraer.PENSAMIENTO,
        "output_config": {"effort": extraer.ESFUERZO, "format": {"type": "json_schema", "schema": ESQUEMA}},
        "messages": [{"role": "user", "content": texto}]}}


def normalizar(datos: dict, portada: str | None) -> dict:
    """Valores dentro de las listas cerradas; el nombre solo con su cita literal en la portada."""
    out = {"categoria": datos.get("categoria") if datos.get("categoria") in CATEGORIAS else None,
           "tipo_centro": datos.get("tipo_centro") if datos.get("tipo_centro") in TIPOS else None,
           "ambito": datos.get("ambito") if datos.get("ambito") in AMBITOS else None,
           "vende_masters": datos.get("vende_masters") if isinstance(datos.get("vende_masters"), bool) else None,
           "confianza": datos.get("confianza") if datos.get("confianza") in {"alta", "media", "baja"} else None,
           "motivo": " ".join(str(datos.get("motivo") or "").split()[:20]) or None}
    if datos.get("tipo_centro") == "ninguno" or out["categoria"] != "centro":
        out["tipo_centro"] = None
    n = datos.get("nombre") if isinstance(datos.get("nombre"), dict) else \
        {"v": datos.get("nombre"), "c": datos.get("cita_nombre")}  # salida estructurada: dos campos planos
    v, c = str(n.get("v") or "").strip(), str(n.get("c") or "").strip()
    if v and c and portada:
        t = extraer._norma(portada)
        out["nombre"] = v[:150] if extraer._norma(c) in t and extraer._norma(v) in t else None
        out["nombre_propuesto"] = None if out["nombre"] else v[:150]
    return out


def apto_para_censo(c: dict) -> bool:
    return c.get("categoria") == "centro" and c.get("ambito") in {"espana", "internacional"} \
        and c.get("vende_masters") is not False


def lote(entrada_: Path, salida: Path, esperar_min: float = 40, max_minutos: float = 52, hilos: int = 16,
         guarda: extraer.Guarda | None = None) -> dict:
    t0 = time.time()
    guarda = guarda if guarda is not None else extraer.Guarda()
    filas = [json.loads(l) for l in entrada_.read_text(encoding="utf-8").split("\n") if l.strip()]
    capt = {c["url"]: c for c in extraer.capturar([f["web"] for f in filas], hilos=hilos, guarda=guarda,
                                                   fin=t0 + (max_minutos - 15) * 60, procesar=texto_portada)}
    salida.mkdir(parents=True, exist_ok=True)
    peticiones, por_id, enviado, cuentas = [], {}, [], Counter()
    for f in filas:
        c = capt.get(f["web"], {})
        cuentas["portada_leida" if c.get("texto") else "portada_" + (c.get("motivo") or ("reserva_tdm" if c.get("reserva_tdm") else "sin_texto"))] += 1
        if c.get("reserva_tdm"):
            continue  # el titular reserva la minería: no se envía nada suyo
        texto = mensaje(f, c.get("texto"))
        cid = "c" + hashlib.sha256(f["id"].encode()).hexdigest()[:20]
        por_id[cid] = (f, c)
        peticiones.append(peticion(cid, texto))
        enviado.append({"custom_id": cid, "id": f["id"], "texto": texto})
    if not peticiones:
        return dict(cuentas)
    r = requests.post(extraer.API, headers=extraer._cabeceras(), json={"requests": peticiones}, timeout=300)
    if r.status_code >= 400:
        return {**cuentas, "error_api": r.status_code, "detalle": r.text[:500]}
    b = r.json()
    privado = {"enviado": guarda.jsonl(extraer.FUENTE_EXTRACCION, enviado, "clasificar-enviado.jsonl",
                                       f"anthropic-batch:{b['id']}/clasificar-enviado")}
    (salida / "lote.json").write_text(json.dumps({"id": b["id"], "peticiones": len(peticiones), "modelo": extraer.MODELO,
                                                  "clave_enviado": privado["enviado"]}), encoding="utf-8")
    fin = min(t0 + max_minutos * 60, time.time() + esperar_min * 60)
    while b.get("processing_status") != "ended" and time.time() < fin:
        time.sleep(30)
        b = requests.get(f"{extraer.API}/{b['id']}", headers=extraer._cabeceras(), timeout=60).json()
    if b.get("processing_status") != "ended":
        res = {**cuentas, "estado_lote": b.get("processing_status"), "id": b["id"]}
        (salida / "resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        return res
    res = requests.get(b["results_url"], headers=extraer._cabeceras(), timeout=600)
    if guarda.activa:
        privado["resultados"] = guarda.original(extraer.FUENTE_EXTRACCION, res.content, "clasificar-resultados.jsonl",
                                                f"anthropic-batch:{b['id']}/clasificar-resultados").get("clave")
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    dolares, cat = 0.0, Counter()
    with (salida / "clasificacion.jsonl").open("w", encoding="utf-8") as fo:
        for linea in res.text.split("\n"):
            if not linea.strip():
                continue
            x = json.loads(linea)
            if x["result"]["type"] != "succeeded" or x["custom_id"] not in por_id:
                cuentas["resultado_" + x["result"]["type"]] += 1
                continue
            msg = x["result"]["message"]
            dolares += extraer.coste(msg.get("usage", {}))
            f, c = por_id[x["custom_id"]]
            datos = extraer._json_de("".join(k.get("text", "") for k in msg["content"] if k.get("type") == "text"))
            if not datos:
                cuentas["json_ilegible"] += 1
            n = normalizar(datos, c.get("texto"))
            n.update({"id": f["id"], "dominio": f["dominio"], "web": f["web"], "portada_sha256": c.get("sha256"),
                      "portada_clave": c.get("clave"), "portada_leida": bool(c.get("texto")),
                      "urls_programa": f.get("urls_programa"), "apto_censo": apto_para_censo(n),
                      "clasificado": ahora, "modelo": extraer.MODELO, "lote": b["id"],
                      "json_legible": bool(datos), "parada": msg.get("stop_reason"),
                      "tokens_salida": (msg.get("usage") or {}).get("output_tokens")})
            fo.write(json.dumps(n, ensure_ascii=False) + "\n")
            cat[(n["categoria"], n["ambito"])] += 1
            cuentas["apto_censo"] += n["apto_censo"]
            cuentas["clasificados"] += 1
    resumen = {**cuentas, "id": b["id"], "coste_usd": round(dolares, 6),
               "por_categoria_y_ambito": {f"{a}/{m}": v for (a, m), v in cat.most_common()},
               "almacen": {**dict(guarda.cuentas), "claves_privadas": privado}}
    (salida / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    return resumen


def aplicar(censo: Path, clasificaciones: list[Path], salida: Path) -> dict:
    """Censo con la clasificación: los verificados que no son centro (o no son de España) pasan a «descartado»
    con su motivo; los agregadores se listan aparte y no se usan como fuente.
    Si un proveedor se clasificó varias veces, vale la última clasificación legible."""
    ultima: dict[str, dict] = {}
    for f in clasificaciones:  # de más antigua a más reciente
        for l in f.read_text(encoding="utf-8").split("\n"):
            if l.strip():
                c = json.loads(l)
                if c.get("categoria") or c["id"] not in ultima:
                    ultima[c["id"]] = c
    cuentas, agregadores, filas = Counter(), [], []
    for l in censo.read_text(encoding="utf-8").split("\n"):
        if not l.strip():
            continue
        p = json.loads(l)
        c = ultima.get(p["id"])
        if p["estado"] == "verificado" and c:
            p["clasificacion"] = {k: c.get(k) for k in ("categoria", "tipo_centro", "ambito", "vende_masters",
                                                        "confianza", "nombre", "clasificado", "modelo", "lote")}
            if c.get("nombre") and c["nombre"] not in p.get("nombres", []):
                p["nombres"] = p.get("nombres", []) + [c["nombre"]]
            if not c.get("categoria"):
                p["motivo"] = "sin_clasificar"
            elif c["categoria"] != "centro":
                p["estado"], p["motivo"] = "descartado", c["categoria"]
            elif c.get("ambito") == "otro_pais":
                p["estado"], p["motivo"] = "descartado", "otro_pais"
            elif c.get("vende_masters") is False:
                p["estado"], p["motivo"] = "descartado", "sin_masters_propios"
            if c.get("categoria") == "agregador":
                agregadores.append({"id": p["id"], "dominio": p["dominio"], "ambito": c.get("ambito"),
                                    "urls_programa": c.get("urls_programa")})
        cuentas[(p["estado"], p.get("motivo"))] += 1
        filas.append(p)
    destino = salida / "datos" / "estudios" / "censo"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "proveedores.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in filas),
                                               encoding="utf-8")
    (destino / "agregadores.jsonl").write_text("".join(json.dumps(a, ensure_ascii=False) + "\n" for a in agregadores),
                                               encoding="utf-8")
    return {f"{e}/{m}": n for (e, m), n in cuentas.most_common()}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("orden", choices=["entrada", "lote", "aplicar"])
    p.add_argument("--clasificacion", action="append", default=[])
    p.add_argument("--censo")
    p.add_argument("--rastreo", action="append", default=[])
    p.add_argument("--entrada")
    p.add_argument("--esperar-min", type=float, default=40)
    p.add_argument("--max-minutos", type=float, default=52)
    p.add_argument("--hilos", type=int, default=16)
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    if a.orden == "aplicar":
        res = aplicar(Path(a.censo), [Path(x) for x in a.clasificacion], Path(a.salida))
    elif a.orden == "entrada":
        res = entrada(Path(a.censo), [Path(x) for x in a.rastreo], Path(a.salida))
    else:
        res = lote(Path(a.entrada), Path(a.salida) / "datos" / "estudios" / "clasificacion" / Path(a.entrada).stem, a.esperar_min,
                   a.max_minutos, a.hilos)
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
