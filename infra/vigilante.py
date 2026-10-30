"""Vigilante de la infraestructura: detecta fallos en GitHub Actions y en las fuentes, y relanza lo pasajero.

Se ejecuta cada 30 minutos desde .github/workflows/vigilante.yml, en los servidores de GitHub (repositorio
público: sin coste de minutos). No toca código ni datos: solo lee el estado y, como único arreglo automático,
relanza una vez los trabajos que fallaron por un error pasajero (red, tiempo agotado, choque al subir).

Escribe en la carpeta de salida:
  ultimo.json   estado completo de esta pasada
  ultimo.md     el mismo estado en texto legible
El flujo lo sube a la rama `vigilancia` (y añade una línea por pasada a historial/AAAA-MM.jsonl).

Lo lee la conversación de estado del proyecto, que arregla lo que no es pasajero y lo anota en el buzón de
incidencias del proyecto (claude/incidencias.md).

Uso: python infra/vigilante.py --salida carpeta [--horas 6] [--relanzar]
Necesita GITHUB_TOKEN (o GH_TOKEN) y GITHUB_REPOSITORY.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://api.github.com"

# Fallos que suelen arreglarse solos al repetir. Se buscan en las últimas líneas del registro del trabajo.
PASAJERO = re.compile(
    r"(connection reset|connection aborted|connection refused|remote end closed|timed? ?out|timeout|"
    r"temporary failure in name resolution|name or service not known|"
    r"\b50[234]\b|service unavailable|bad gateway|gateway time|\b429\b|too many requests|"
    r"rpc failed|early eof|unexpected disconnect|could not read from remote|"
    r"\[rejected\]|non-fast-forward|fetch first|failed to push some refs|cannot lock ref|"
    r"lost communication with the server|runner has received a shutdown signal|"
    r"the operation was canceled|internal server error)",
    re.I,
)
# Nunca se relanza aunque parezca pasajero: requiere a una persona.
NO_RELANZAR = re.compile(r"(GH013|push protection|secret|permission denied|not authorized|accessdenied|403 forbidden)", re.I)

# Flujos programados que deben haber terminado bien hace menos de este número de horas.
PROGRAMADOS = {"motor.yml": 26, "autonomicos.yml": 26, "seo.yml": 26}
NO_SE_RELANZAN = {"vigilante.yml"}
MAX_RELANZAMIENTOS = 6


def token() -> str:
    t = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not t:
        sys.exit("Falta GITHUB_TOKEN")
    return t


def api(ruta: str, metodo: str = "GET", datos: dict | None = None, crudo: bool = False):
    url = ruta if ruta.startswith("http") else API + ruta
    cuerpo = json.dumps(datos).encode() if datos is not None else None
    req = urllib.request.Request(url, data=cuerpo, method=metodo, headers={
        "Authorization": "Bearer " + token(),
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "vigilante-education",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        contenido = r.read()
    if crudo:
        return contenido
    return json.loads(contenido) if contenido else {}


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def fecha(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def madrid(d: datetime | None) -> str | None:
    if not d:
        return None
    try:
        from zoneinfo import ZoneInfo
        return d.astimezone(ZoneInfo("Europe/Madrid")).strftime("%d/%m %H:%M")
    except Exception:  # pragma: no cover
        return d.strftime("%d/%m %H:%M UTC")


class _SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: D401 - la redirección se sigue a mano, sin la cabecera
        return None


def final_registro(job_id: int, lineas: int = 25) -> list[str]:
    """Últimas líneas del registro de un trabajo. La API redirige a un almacén que rechaza la cabecera de
    autorización de GitHub (401), así que la redirección se sigue a mano y sin ella."""
    url = f"{API}/repos/{os.environ['GITHUB_REPOSITORY']}/actions/jobs/{job_id}/logs"
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token(),
                                               "Accept": "application/vnd.github+json",
                                               "User-Agent": "vigilante-education"})
    try:
        try:
            urllib.request.build_opener(_SinRedireccion).open(req, timeout=60)
            return ["(registro sin redirección: formato inesperado)"]
        except urllib.error.HTTPError as e:
            if e.code not in (301, 302, 303, 307, 308) or not e.headers.get("Location"):
                raise
            destino = e.headers["Location"]
        with urllib.request.urlopen(urllib.request.Request(destino, headers={"User-Agent": "vigilante-education"}),
                                    timeout=60) as r:
            texto = r.read()
    except Exception as e:  # registro caducado o sin permiso
        return [f"(registro no disponible: {e})"]
    filas = texto.decode("utf-8", "replace").splitlines()
    # Quita la marca de tiempo inicial de cada línea y los grupos vacíos
    limpias = [re.sub(r"^\d{4}-\d\d-\d\dT[\d:.]+Z ", "", f)[:300] for f in filas if f.strip()]
    # Lo que importa está antes de la limpieza final del trabajo («Post job cleanup»)
    corte = next((i for i, f in enumerate(limpias) if f.startswith("Post job cleanup")), len(limpias))
    utiles = [f for f in limpias[:corte] if not f.startswith(("[command]", "##[group]", "##[endgroup]"))]
    errores = [f for f in utiles if "##[error]" in f or re.search(r"(Traceback|Error|FAILED|fatal:)", f)]
    return (errores[-8:] + ["..."] + utiles[-lineas:]) if errores else utiles[-lineas:]


def ejecuciones(repo: str, desde: datetime) -> list[dict]:
    salida, pagina = [], 1
    while pagina <= 5:
        r = api(f"/repos/{repo}/actions/runs?per_page=100&page={pagina}&created=>={desde.strftime('%Y-%m-%dT%H:%M:%SZ')}")
        salida += r.get("workflow_runs", [])
        if len(r.get("workflow_runs", [])) < 100:
            break
        pagina += 1
    return salida


def ultimo_bien(repo: str, flujo: str) -> datetime | None:
    try:
        r = api(f"/repos/{repo}/actions/workflows/{flujo}/runs?status=success&per_page=1")
    except urllib.error.HTTPError:
        return None
    runs = r.get("workflow_runs", [])
    return fecha(runs[0].get("updated_at")) if runs else None


def json_de_rama(repo: str, ruta: str, rama: str) -> dict | None:
    try:
        r = api(f"/repos/{repo}/contents/{ruta}?ref={rama}")
        return json.loads(base64.b64decode(r["content"]))
    except Exception:
        return None


def comprobar_almacen() -> dict:
    """Si el flujo trae credenciales de AWS (OIDC), comprueba que el rol se asume y el almacén responde."""
    if not os.environ.get("AWS_ACCESS_KEY_ID"):
        return {"estado": "sin_comprobar", "motivo": "sin credenciales de AWS en esta ejecución"}
    try:
        ident = subprocess.run(["aws", "sts", "get-caller-identity", "--output", "json"], capture_output=True,
                               text=True, timeout=60)
        cubo = subprocess.run(["aws", "s3api", "head-bucket", "--bucket", "education-originales-finads"],
                              capture_output=True, text=True, timeout=60)
        ok = ident.returncode == 0 and cubo.returncode == 0
        return {"estado": "ok" if ok else "error",
                "detalle": (ident.stderr + cubo.stderr).strip()[:400] or None}
    except Exception as e:
        return {"estado": "error", "detalle": str(e)[:400]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", required=True)
    ap.add_argument("--horas", type=float, default=6)
    ap.add_argument("--relanzar", action="store_true", help="relanza una vez los fallos pasajeros")
    a = ap.parse_args()
    repo = os.environ["GITHUB_REPOSITORY"]
    propio = os.environ.get("GITHUB_RUN_ID")
    t0 = ahora()
    desde = t0 - timedelta(hours=a.horas)

    runs = [r for r in ejecuciones(repo, desde) if str(r["id"]) != propio]
    fallos, relanzados, colas = [], [], []

    for r in runs:
        flujo = r.get("path", "").split("/")[-1]
        if r["status"] == "queued":
            espera = (t0 - fecha(r["created_at"])).total_seconds() / 60
            if espera > 30:
                # Con max-parallel, la ejecución figura «en cola» mientras sus trabajos van de uno en uno:
                # solo es cola de verdad si ningún trabajo ha empezado en los últimos 30 minutos.
                try:
                    trabajos = api(f"/repos/{repo}/actions/runs/{r['id']}/jobs?per_page=100").get("jobs", [])
                except Exception:
                    trabajos = []
                inicios = [fecha(j.get("started_at")) for j in trabajos
                           if j.get("status") in ("in_progress", "completed") and j.get("started_at")]
                avanza = any(i and (t0 - i) < timedelta(minutes=30) for i in inicios) or any(
                    j.get("status") == "in_progress" for j in trabajos)
                if not avanza:
                    colas.append({"flujo": r["name"], "id": r["id"], "en_cola_min": round(espera),
                                  "trabajos_empezados": len(inicios), "url": r["html_url"]})
            continue
        if r["status"] != "completed" or r.get("conclusion") not in ("failure", "timed_out", "startup_failure"):
            continue
        # ¿Ya hay una ejecución posterior del mismo flujo que terminó bien? Entonces está superado.
        posterior_ok = any(o.get("workflow_id") == r.get("workflow_id") and o.get("conclusion") == "success"
                           and fecha(o["created_at"]) > fecha(r["created_at"]) for o in runs)
        try:
            trabajos = api(f"/repos/{repo}/actions/runs/{r['id']}/jobs?per_page=50").get("jobs", [])
        except Exception:
            trabajos = []
        malos = [j for j in trabajos if j.get("conclusion") in ("failure", "timed_out")]
        detalle = []
        for j in malos[:3]:
            pasos = [s["name"] for s in j.get("steps", []) if s.get("conclusion") == "failure"]
            cola = final_registro(j["id"])
            detalle.append({"trabajo": j["name"], "pasos": pasos, "ejecutor": j.get("runner_name"),
                            "etiquetas": j.get("labels"), "final_registro": cola})
        if not malos:
            detalle.append({"trabajo": "(ninguno)", "pasos": [], "ejecutor": None, "etiquetas": None,
                            "final_registro": ["Falló sin ningún trabajo fallido: error en la definición del flujo "
                                               "(matriz vacía, YAML, permisos de la ejecución). Ver la página."]})
        texto = "\n".join(l for d in detalle for l in d["final_registro"])
        pasajero = bool(PASAJERO.search(texto)) and not NO_RELANZAR.search(texto)
        f = {"flujo": r["name"], "fichero": flujo, "id": r["id"], "intento": r.get("run_attempt"),
             "evento": r.get("event"), "rama": r.get("head_branch"), "commit": r.get("head_sha", "")[:7],
             "titulo": r.get("display_title"), "conclusion": r.get("conclusion"),
             "cuando": madrid(fecha(r.get("updated_at"))), "url": r["html_url"],
             "superado": posterior_ok, "pasajero": pasajero, "detalle": detalle}
        if (a.relanzar and pasajero and not posterior_ok and r.get("run_attempt", 1) == 1
                and flujo not in NO_SE_RELANZAN and len(relanzados) < MAX_RELANZAMIENTOS):
            try:
                api(f"/repos/{repo}/actions/runs/{r['id']}/rerun-failed-jobs", metodo="POST", datos={})
                f["relanzado"] = True
                relanzados.append(r["id"])
            except urllib.error.HTTPError as e:
                f["relanzado"] = f"no se pudo: {e.code}"
        fallos.append(f)

    programados = {}
    for flujo, horas in PROGRAMADOS.items():
        ok = ultimo_bien(repo, flujo)
        programados[flujo] = {"ultimo_bien": madrid(ok),
                              "parado": ok is None or (t0 - ok) > timedelta(hours=horas)}

    estado_fuentes = json_de_rama(repo, "datos/estado.json", "datos") or {}
    boe = json_de_rama(repo, "datos/boe/estado.json", "datos") or {}
    avisos_fuentes = []
    for nombre, e in (estado_fuentes.get("fuentes") or {}).items() if isinstance(estado_fuentes.get("fuentes"), dict) else []:
        if isinstance(e, dict) and (e.get("aviso") or e.get("parada") or e.get("errores")):
            avisos_fuentes.append({"fuente": nombre, **{k: e.get(k) for k in ("aviso", "parada", "errores",
                                                                                 "ultimo_boletin", "dias_habiles_sin_noticias")}})

    pendientes = [f for f in fallos if not f["superado"] and not f.get("relanzado")]
    resultado = {
        "fecha": t0.isoformat(timespec="seconds"),
        "fecha_madrid": madrid(t0),
        "ventana_horas": a.horas,
        "resumen": {
            "ejecuciones_revisadas": len(runs),
            "fallos": len(fallos),
            "fallos_pendientes": len(pendientes),
            "relanzados": len(relanzados),
            "colas_largas": len(colas),
            "flujos_programados_parados": [k for k, v in programados.items() if v["parado"]],
            "avisos_de_fuentes": len(avisos_fuentes),
            "almacen": None,
        },
        "fallos": fallos,
        "colas_largas": colas,
        "programados": programados,
        "boe": {k: boe.get(k) for k in ("ultimo_diario", "ultima_ejecucion", "alertas_ultima_ejecucion")},
        "avisos_de_fuentes": avisos_fuentes,
    }
    resultado["almacen"] = comprobar_almacen()
    resultado["resumen"]["almacen"] = resultado["almacen"]["estado"]

    salida = Path(a.salida)
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "ultimo.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")

    md = [f"# Vigilancia {resultado['fecha_madrid']} (Madrid)", "",
          f"- Ejecuciones revisadas (últimas {a.horas:g} h): {len(runs)}",
          f"- Fallos: {len(fallos)}; pendientes: {len(pendientes)}; relanzados ahora: {len(relanzados)}",
          f"- Colas de más de 30 minutos: {len(colas)}",
          f"- Flujos programados parados: {', '.join(resultado['resumen']['flujos_programados_parados']) or 'ninguno'}",
          f"- Almacén S3: {resultado['almacen']['estado']}",
          f"- Avisos de fuentes: {len(avisos_fuentes)}", ""]
    for f in fallos:
        marca = "superado" if f["superado"] else ("relanzado" if f.get("relanzado") is True else "PENDIENTE")
        md.append(f"## {f['flujo']} · {f['cuando']} · {marca}")
        md.append(f"{f['url']} (intento {f['intento']}, {f['evento']}, {f['commit']}, pasajero: {f['pasajero']})")
        for d in f["detalle"]:
            md.append(f"- {d['trabajo']} · pasos: {', '.join(d['pasos']) or '?'} · ejecutor: {d['ejecutor']}")
            md += ["      " + l for l in d["final_registro"][-8:]]
        md.append("")
    for c in colas:
        md.append(f"- En cola {c['en_cola_min']} min: {c['flujo']} {c['url']}")
    (salida / "ultimo.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:9]))
    linea = {"fecha": resultado["fecha"], **resultado["resumen"]}
    print("::notice title=Vigilancia::" + json.dumps(linea, ensure_ascii=False))


if __name__ == "__main__":
    main()
