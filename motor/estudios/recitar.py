"""Segunda oportunidad para los datos en revisión porque su cita no estaba en el texto («cita_no_literal»).

En la extracción, el modelo da cada valor con una cita del texto, y solo se acepta si la cita está en el texto
(motor/estudios/extraer.py, verificar). Cuando el valor era bueno pero la cita salió retocada, el dato se pierde.
Aquí se le pide al modelo, para esos campos y sobre el mismo texto exacto que se envió (guardado en el almacén
privado), solo el fragmento literal que dice ese valor, o nada. La comprobación es la misma que en la extracción
(verificar): la cita tiene que estar en el texto y, en los números, el número tiene que salir de ella. El valor
es el que propuso la extracción; aquí no se cambia.

Entrada: una carpeta de extracción ya comprobada (retomado_* de extraer.py retomar), con su lote.json (clave
privada de lo enviado) y su resumen.json (clave privada de los hechos con cita).

Salida (carpeta propia, lista para fichas_masters.py): para cada página con algún dato recuperado, su fila en
paginas_extraidas.jsonl con fecha nueva y todos sus hechos en hechos.jsonl (los que ya estaban y los recuperados,
marcados «recitado»), sin textos ajenos; las citas nuevas, solo al almacén privado.

Uso:
  python -m motor.estudios.recitar --carpeta entrada/…/retomado_XXXX --esperar-min 40 --salida ruta/
  python -m motor.estudios.recitar --retomar entrada/…/recitado_XXXX/lote_recitar.json --salida ruta/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

from motor.estudios import extraer as ex

SISTEMA = (
    "Recibes el texto de una página web de un máster y una lista de campos con el valor que se leyó en ella. Para "
    "cada campo, copia del texto el fragmento exacto que dice ese valor: carácter por carácter, tal como está, sin "
    "cambiar, quitar ni añadir palabras, sin «...» y sin juntar trozos de sitios distintos. Entre 3 y 40 palabras. "
    "Si el texto no dice ese valor, la cita es null. No expliques nada."
)
ESQUEMA = {
    "type": "object",
    "properties": {
        "citas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"campo": {"type": "string"}, "cita": {"type": ["string", "null"]}},
                "required": ["campo", "cita"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["citas"],
    "additionalProperties": False,
}
MAX_TOKENS = 2000
MOTIVOS = {"cita_no_literal"}


def _jsonl(ruta: Path) -> list[dict]:
    return [json.loads(x) for x in ruta.read_text(encoding="utf-8").split("\n") if x.strip()] if ruta.exists() else []


def _valor_texto(v) -> str:
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


def peticion(custom_id: str, url: str, texto: str, pendientes: list[dict]) -> dict:
    lista = "\n".join(f"- {h['campo']}: {_valor_texto(h['valor_propuesto'])[:300]}" for h in pendientes)
    return {
        "custom_id": custom_id,
        "params": {
            "model": ex.MODELO,
            "max_tokens": MAX_TOKENS,
            "thinking": ex.PENSAMIENTO,
            "output_config": {"effort": ex.ESFUERZO, "format": {"type": "json_schema", "schema": ESQUEMA}},
            "system": [{"type": "text", "text": SISTEMA, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": f"URL: {url}\n\nCAMPOS:\n{lista}\n\nTEXTO DE LA PÁGINA:\n{texto}"}],
        },
    }


def preparar(carpeta: Path, guarda: ex.Guarda) -> tuple[list[dict], dict, dict]:
    """Peticiones (una por página con datos por recuperar), textos por custom_id y lo necesario para escribir."""
    info = json.loads((carpeta / "lote.json").read_text(encoding="utf-8"))
    resumen = json.loads((carpeta / "resumen.json").read_text(encoding="utf-8"))
    clave_hechos = ((resumen.get("almacen") or {}).get("claves_privadas") or {}).get("hechos_con_cita")
    if not info.get("clave_enviado") or not clave_hechos:
        sys.exit("La carpeta no tiene en el almacén lo enviado o los hechos con cita")
    extraido = {p["url"]: p["extraido"] for p in _jsonl(carpeta / "paginas_extraidas.jsonl")}
    pendientes: dict[str, list[dict]] = defaultdict(list)
    for h in guarda.leer_jsonl(clave_hechos):
        if h.get("estado") == "revision" and h.get("motivo") in MOTIVOS and extraido.get(h["url"]) == h.get("extraido") \
                and h.get("valor_propuesto") not in (None, "", []):
            pendientes[h["url"]].append(h)
    peticiones, textos = [], {}
    for e in guarda.leer_jsonl(info["clave_enviado"]):
        hs = pendientes.get(e["url"])
        if not hs:
            continue
        cid = hashlib.sha256(f"recitar|{e['custom_id']}".encode()).hexdigest()[:40]
        textos[cid] = {"url": e["url"], "sha256": e["sha256"], "texto": e["texto"], "pendientes": hs}
        peticiones.append(peticion(cid, e["url"], e["texto"], hs))
    return peticiones, textos, {"lote_origen": info["id"], "carpeta": str(carpeta)}


def comprobar(texto: str, pendientes: list[dict], datos: dict) -> dict[str, dict]:
    """campo → hecho recuperado (con su cita), con la misma comprobación que la extracción."""
    nuevas = {c.get("campo"): c.get("cita") for c in (datos.get("citas") or []) if isinstance(c, dict)}
    respuesta = {h["campo"]: {"valor": h["valor_propuesto"], "cita": nuevas.get(h["campo"])}
                 for h in pendientes if nuevas.get(h["campo"])}
    return {h["campo"]: h for h in ex.verificar(respuesta, texto) if h["estado"] == "aceptado"}


def procesar(b: dict, textos: dict, carpeta: Path, salida: Path, guarda: ex.Guarda, cuentas: Counter) -> dict:
    res = requests.get(b["results_url"], headers=ex._cabeceras(), timeout=600)
    privado = {"resultados": guarda.original(ex.FUENTE_EXTRACCION, res.content, "resultados.jsonl",
                                             f"anthropic-batch:{b['id']}/resultados").get("clave") if guarda.activa else None}
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    recuperados: dict[str, dict[str, dict]] = {}
    dolares, por_campo, niveles = 0.0, Counter(), Counter()
    for linea in res.text.split("\n"):
        if not linea.strip():
            continue
        x = json.loads(linea)
        if x["result"]["type"] != "succeeded" or x["custom_id"] not in textos:
            cuentas["resultado_" + x["result"]["type"]] += 1
            continue
        msg = x["result"]["message"]
        dolares += ex.coste(msg.get("usage", {}))
        t = textos[x["custom_id"]]
        datos = ex._json_de("".join(c.get("text", "") for c in msg["content"] if c.get("type") == "text"))
        cuentas["respondidas"] += 1
        if not datos:
            cuentas["json_ilegible"] += 1
            continue
        try:
            ok = comprobar(t["texto"], t["pendientes"], datos)
        except Exception as e:  # noqa: BLE001 - una respuesta rara no tira la tanda ya pagada
            cuentas["error_comprobar_" + type(e).__name__] += 1
            continue
        cuentas["pedidos"] += len(t["pendientes"])
        if ok:
            recuperados[t["url"]] = ok
            for c, h in ok.items():
                por_campo[c] += 1
                niveles[h.get("cita_nivel")] += 1
    # cada página con algo recuperado se escribe entera, con fecha nueva: fichas_masters se queda con la última
    salida.mkdir(parents=True, exist_ok=True)
    paginas = {p["url"]: p for p in _jsonl(carpeta / "paginas_extraidas.jsonl")}
    completos = []
    with (salida / "paginas_extraidas.jsonl").open("w", encoding="utf-8") as fp, \
            (salida / "hechos.jsonl").open("w", encoding="utf-8") as fh:
        for url, p in paginas.items():
            if url in recuperados:
                fp.write(json.dumps({**p, "extraido": ahora, "recitado": b["id"]}, ensure_ascii=False) + "\n")
        for h in _jsonl(carpeta / "hechos.jsonl"):
            ok = recuperados.get(h["url"])
            if ok is None or h.get("extraido") != paginas.get(h["url"], {}).get("extraido"):
                continue
            nuevo = ok.get(h["campo"]) if h.get("estado") == "revision" else None
            if nuevo is not None:
                cita = nuevo.pop("cita", "") or ""
                completos.append({**h, **nuevo, "cita": cita, "extraido": ahora, "recitado": b["id"]})
                h = {**h, **nuevo, "cita_sha256": hashlib.sha256(ex._norma(cita).encode()).hexdigest(),
                     "cita_palabras": len(cita.split()), "recitado": b["id"]}
            fh.write(json.dumps({**h, "extraido": ahora}, ensure_ascii=False) + "\n")
    privado["hechos_con_cita"] = guarda.jsonl(ex.FUENTE_EXTRACCION, completos, "hechos.jsonl",
                                              f"anthropic-batch:{b['id']}/hechos") if completos else None
    resumen = {**cuentas, "id": b["id"], "coste_usd": round(dolares, 6), "paginas_con_recuperados": len(recuperados),
               "recuperados": sum(por_campo.values()), "por_campo": dict(por_campo), "niveles_cita": dict(niveles),
               "almacen": {**dict(guarda.cuentas), "claves_privadas": privado}}
    (salida / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    return resumen


def esperar(b: dict, fin: float) -> dict:
    while b.get("processing_status") != "ended" and time.time() < fin:
        time.sleep(30)
        b = requests.get(f"{ex.API}/{b['id']}", headers=ex._cabeceras(), timeout=60).json()
    return b


def lote(carpeta: Path, salida: Path, esperar_min: float, guarda: ex.Guarda | None = None) -> dict:
    guarda = guarda if guarda is not None else ex.Guarda()
    peticiones, textos, info = preparar(carpeta, guarda)
    cuentas = Counter({"paginas": len(peticiones)})
    salida.mkdir(parents=True, exist_ok=True)
    if not peticiones:
        (salida / "resumen.json").write_text(json.dumps(dict(cuentas)), encoding="utf-8")
        return dict(cuentas)
    r = requests.post(ex.API, headers=ex._cabeceras(), json={"requests": peticiones}, timeout=300)
    if r.status_code >= 400:
        return {**cuentas, "error_api": r.status_code, "detalle": r.text[:500]}
    b = r.json()
    (salida / "lote_recitar.json").write_text(json.dumps({"id": b["id"], **info}, ensure_ascii=False), encoding="utf-8")
    b = esperar(b, time.time() + esperar_min * 60)
    if b.get("processing_status") != "ended":
        res = {**cuentas, "estado_lote": b.get("processing_status"), "id": b["id"],
               "siguiente": "recitar --retomar con lote_recitar.json de esta ejecución"}
        (salida / "resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        return res
    return procesar(b, textos, carpeta, salida, guarda, cuentas)


def retomar(lote_recitar: Path, raiz_entrada: Path, salida: Path, esperar_min: float,
            guarda: ex.Guarda | None = None, carpeta: Path | None = None) -> dict:
    """Recoge un lote ya pagado. Con «carpeta», sobre otra comprobación de la misma extracción (un retomado
    posterior del mismo lote, con la verificación nueva): las respuestas van por página (custom_id estable) y cada
    cita se vuelve a comprobar con verificar, así que solo se recupera lo que sigue pendiente y pasa la comprobación."""
    guarda = guarda if guarda is not None else ex.Guarda()
    info = json.loads(lote_recitar.read_text(encoding="utf-8"))
    if carpeta is None:
        carpeta = Path(info["carpeta"])
        if not carpeta.exists():
            carpeta = raiz_entrada / Path(info["carpeta"]).relative_to("entrada")
    origen = json.loads((carpeta / "lote.json").read_text(encoding="utf-8")).get("id")
    if info.get("lote_origen") and origen != info["lote_origen"]:
        sys.exit(f"La carpeta es de otro lote ({origen}), no del recitado ({info['lote_origen']})")
    _, textos, _ = preparar(carpeta, guarda)
    b = esperar(requests.get(f"{ex.API}/{info['id']}", headers=ex._cabeceras(), timeout=60).json(),
                time.time() + esperar_min * 60)
    if b.get("processing_status") != "ended":
        return {"estado_lote": b.get("processing_status"), "id": b["id"]}
    return procesar(b, textos, carpeta, salida, guarda, Counter({"retomado": 1}))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--carpeta", help="carpeta retomado_* (con lote.json, resumen.json, hechos y páginas); con --retomar, "
                                     "la comprobación sobre la que aplicar el recitado ya pagado")
    p.add_argument("--retomar", help="lote_recitar.json de una ejecución anterior")
    p.add_argument("--esperar-min", type=float, default=40)
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    base = Path(a.salida) / "datos" / "estudios" / "extraccion"
    if a.retomar:
        lr = Path(a.retomar)
        destino = base / ("recitado_" + json.loads(lr.read_text(encoding="utf-8"))["lote_origen"][-16:])
        res = retomar(lr, Path("entrada"), destino, a.esperar_min, carpeta=Path(a.carpeta) if a.carpeta else None)
    elif a.carpeta:
        destino = base / ("recitado_" + Path(a.carpeta).name.replace("retomado_", ""))
        res = lote(Path(a.carpeta), destino, a.esperar_min)
    else:
        sys.exit("Falta --carpeta o --retomar")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
