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
NO_RELANZAR = re.compile(r"(GH013|push protection|secret|permission denied|not authorized|accessdenied|403 forbidden|"
                         r"a password is required|sudo:|no space left on device)", re.I)

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
    tramo = limpias[:corte]
    # Solo cuentan los pasos con error: cada paso empieza en su cabecera «##[group]Run …». Se juntan los que
    # tienen algún «##[error]», cada uno hasta su último error. Lo de los pasos que terminaron bien no cuenta (un
    # `git push` rechazado y reintentado con éxito hacía pasar por pasajero un fallo real), ni lo de después del
    # último error (pasos de limpieza).
    cabeceras = [i for i, f in enumerate(tramo) if f.startswith("##[group]Run ")]
    if any(f.startswith("##[error]") for f in tramo):
        bloques = []
        limites = (cabeceras or [0]) + [len(tramo)]
        if cabeceras and cabeceras[0] > 0:
            limites = [0] + limites
        for a_, b_ in zip(limites, limites[1:]):
            trozo = tramo[a_:b_]
            errores_trozo = [i for i, f in enumerate(trozo) if f.startswith("##[error]")]
            if errores_trozo:
                bloques += trozo[:errores_trozo[-1] + 1][-12:]
        tramo = bloques
    utiles = [f for f in tramo if not f.startswith(("[command]", "##[group]", "##[endgroup]"))]
    # Fuera los bloques «shell:» / «env:» que GitHub imprime al empezar cada paso.
    sin_ruido, en_env = [], False
    for f in utiles:
        if f.startswith("shell: ") or f == "env:":
            en_env = f == "env:"
            continue
        if en_env and re.match(r"^\s+[A-Za-z_][A-Za-z0-9_]*: ", f):
            continue
        en_env = False
        sin_ruido.append(f)
    utiles = sin_ruido
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
    """Última ejecución terminada bien. «skipped» también cuenta: el flujo corrió y sus trabajos se saltaron a
    propósito (el SEO, mientras no exista la variable SEO_BASE)."""
    try:
        r = api(f"/repos/{repo}/actions/workflows/{flujo}/runs?status=completed&per_page=30")
    except urllib.error.HTTPError:
        return None
    buenas = [x for x in r.get("workflow_runs", []) if x.get("conclusion") in ("success", "skipped")]
    return max((fecha(x.get("updated_at")) for x in buenas), default=None)


CRON_DIARIO = re.compile(r'^\s*-\s*cron:\s*["\']?(\d{1,2})\s+(\d{1,2})\s+\*\s+\*\s+\*["\']?', re.M)
NO_RESPALDAR = {"vigilante.yml", "latido.yml"}
PROGRAMACION_FIABLE = 4   # programaciones del vigilante en 3 horas (tocan 6) para apagar el latido


def respaldo_programaciones(repo: str, runs: list[dict], t0: datetime, lanzar: bool) -> list[dict]:
    """GitHub no siempre dispara las programaciones (en repositorios nuevos puede tardar horas o días). Para cada
    hora diaria «M H * * *» de los flujos, si ya pasaron 10 minutos y no hay ninguna ejecución de ese flujo creada
    desde 10 minutos antes de esa hora (por ningún evento), se lanza a mano (workflow_dispatch, entradas por
    defecto). Solo dentro de las 12 horas siguientes a la hora prevista."""
    salida = []
    carpeta = Path(".github/workflows")
    if not carpeta.is_dir():
        return salida
    for f in sorted(carpeta.glob("*.yml")):
        if f.name in NO_RESPALDAR:
            continue
        texto = f.read_text(encoding="utf-8")
        if "workflow_dispatch" not in texto:
            continue
        for m in CRON_DIARIO.finditer(texto):
            minuto, hora = int(m.group(1)), int(m.group(2))
            prevista = t0.replace(hour=hora, minute=minuto, second=0, microsecond=0)
            if prevista > t0:
                prevista -= timedelta(days=1)
            if not (timedelta(minutes=10) <= t0 - prevista <= timedelta(hours=12)):
                continue
            # Cuenta como hecha la programación si hay una ejecución desde 10 minutos antes de su hora que la
            # sustituye: la de GitHub (schedule) o la que lanzó este vigilante (github-actions[bot]). Las tandas que
            # lanzan las conversaciones a mano (con otras entradas, p. ej. unos pocos conectores) no cuentan.
            desde = (prevista - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
            try:
                candidatas = api(f"/repos/{repo}/actions/workflows/{f.name}/runs?per_page=50&created=>={desde}"
                                 ).get("workflow_runs", [])
            except urllib.error.HTTPError:
                candidatas = [r for r in runs if r.get("path", "").split("/")[-1] == f.name
                              and fecha(r["created_at"]) >= prevista - timedelta(minutes=10)]
            if any(r.get("event") == "schedule" or (r.get("triggering_actor") or {}).get("login") == "github-actions[bot]"
                   for r in candidatas):
                continue
            item = {"flujo": f.name, "prevista": madrid(prevista), "lanzado": False}
            if lanzar:
                try:
                    api(f"/repos/{repo}/actions/workflows/{f.name}/dispatches", metodo="POST", datos={"ref": "main"})
                    item["lanzado"] = True
                except urllib.error.HTTPError as e:
                    item["lanzado"] = f"no se pudo: {e.code}"
            salida.append(item)
    return salida


RETRASO_DUPLICADO = timedelta(minutes=60)


def cancelar_programaciones_tardias(repo: str, t0: datetime, actuar: bool) -> list[dict]:
    """GitHub dispara a veces una programación con horas de retraso (el 30/10, de 5 a 7 horas), cuando el respaldo ya
    lanzó la de ese día. Esa segunda ejecución repite la carga diaria y, en el servidor de España (un solo
    ejecutor), duplica horas de trabajo. Si una ejecución `schedule` sin terminar llega 60 minutos o más tarde que su
    hora, y el vigilante ya lanzó la de esa hora (`github-actions[bot]`, sin fallar ni cancelarse), se cancela.
    Cancelar no borra nada: todo lo que ya subió se queda y la carga es reanudable."""
    salida = []
    carpeta = Path(".github/workflows")
    if not carpeta.is_dir():
        return salida
    desde12 = (t0 - timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for f in sorted(carpeta.glob("*.yml")):
        if f.name in NO_RESPALDAR:
            continue
        horas = [(int(m.group(2)), int(m.group(1))) for m in CRON_DIARIO.finditer(f.read_text(encoding="utf-8"))]
        if not horas:
            continue
        try:
            recientes = api(f"/repos/{repo}/actions/workflows/{f.name}/runs?per_page=100&created=>={desde12}"
                            ).get("workflow_runs", [])
        except urllib.error.HTTPError:
            continue
        for r in recientes:
            if r.get("event") != "schedule" or r.get("status") == "completed":
                continue
            creada = fecha(r["created_at"])
            # La hora programada que le toca: la más reciente anterior a su creación (hoy o ayer).
            candidatas = []
            for h, mi in horas:
                p = creada.replace(hour=h, minute=mi, second=0, microsecond=0)
                if p > creada:
                    p -= timedelta(days=1)
                candidatas.append(p)
            prevista = max(candidatas)
            if creada - prevista < RETRASO_DUPLICADO:
                continue
            rango = (f"{(prevista - timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M:%SZ')}.."
                     f"{creada.strftime('%Y-%m-%dT%H:%M:%SZ')}")
            entre = []
            try:
                for pagina in (1, 2, 3):   # las conversaciones lanzan muchas tandas a mano: hasta 300 en el rango
                    lote = api(f"/repos/{repo}/actions/workflows/{f.name}/runs?event=workflow_dispatch&per_page=100"
                               f"&page={pagina}&created={rango}").get("workflow_runs", [])
                    entre += lote
                    if len(lote) < 100:
                        break
            except urllib.error.HTTPError:
                continue
            lanzada = [o for o in entre if o["id"] != r["id"] and o.get("event") == "workflow_dispatch"
                       and (o.get("triggering_actor") or {}).get("login") == "github-actions[bot]"
                       and prevista - timedelta(minutes=10) <= fecha(o["created_at"]) <= creada
                       and o.get("conclusion") not in ("failure", "cancelled", "timed_out", "startup_failure")]
            if not lanzada:
                continue
            item = {"flujo": f.name, "id": r["id"], "prevista": madrid(prevista), "disparada": madrid(creada),
                    "ya_lanzada": lanzada[0]["html_url"], "cancelada": False}
            if actuar:
                try:
                    api(f"/repos/{repo}/actions/runs/{r['id']}/cancel", metodo="POST", datos={})
                    item["cancelada"] = True
                except urllib.error.HTTPError as e:
                    item["cancelada"] = f"no se pudo: {e.code}"
            salida.append(item)
    return salida


GRUPO_FLUJO = re.compile(r'^concurrency:[ \t]*\n[ \t]+group:[ \t]*["\']?([^"\'\s#]+)', re.M)
VENTANA_DESPLAZADA = timedelta(seconds=90)


def grupos_de_concurrencia(carpeta: Path = Path(".github/workflows")) -> dict[str, str]:
    """Grupo de concurrencia fijo, a nivel de flujo, de cada fichero de flujo (los que llevan expresiones no)."""
    salida = {}
    if carpeta.is_dir():
        for f in sorted(carpeta.glob("*.yml")):
            m = GRUPO_FLUJO.search(f.read_text(encoding="utf-8"))
            if m and "${{" not in m.group(1):
                salida[f.name] = m.group(1)
    return salida


def reponer_desplazadas(repo: str, runs: list[dict], actuar: bool, grupos: dict[str, str] | None = None) -> list[dict]:
    """Con `concurrency` (sin cancel-in-progress), GitHub deja una sola ejecución esperando por grupo: si llega otra,
    cancela la que esperaba, sin que haya empezado. Así, una programación que GitHub dispara tarde (y que luego se
    cancela por repetida) o una del respaldo puede tirar una tanda que una conversación dejó esperando, o al revés.
    Pasó el 31/10 a las 14:03: el motor de las 07:47 disparado tarde tiró un «Mantenimiento de datos» lanzado a mano.

    Se reconoce porque se canceló sin ningún trabajo justo cuando se creó otra ejecución del mismo grupo. Solo se
    miran las lanzadas con workflow_dispatch y en su primer intento. Se relanza una vez, con las mismas entradas,
    salvo que la sustituya otra ejecución posterior del mismo flujo que no se canceló (esté en marcha, esperando o ya
    terminada), que quien la lanzó ya la haya relanzado, o que en el grupo haya otra esperando (la tiraría a ella; se
    vuelve a mirar en la pasada siguiente)."""
    grupos = grupos_de_concurrencia() if grupos is None else grupos
    grupo = lambda r: grupos.get((r.get("path") or "").split("/")[-1])
    actor = lambda r: (r.get("triggering_actor") or {}).get("login")
    salida = []
    for c in runs:
        g = grupo(c)
        if (not g or c.get("event") != "workflow_dispatch" or c.get("status") != "completed"
                or c.get("conclusion") != "cancelled" or (c.get("run_attempt") or 1) != 1):
            continue
        fin, creada = fecha(c.get("updated_at")), fecha(c.get("created_at"))
        quien = [o for o in runs if o["id"] != c["id"] and grupo(o) == g
                 and creada < fecha(o["created_at"]) and fin - VENTANA_DESPLAZADA <= fecha(o["created_at"]) <= fin + timedelta(seconds=5)]
        if not quien:
            continue
        try:
            trabajos = api(f"/repos/{repo}/actions/runs/{c['id']}/jobs?per_page=5").get("jobs", [])
        except Exception:
            continue
        if trabajos:   # llegó a empezar: no la desplazó la espera, la canceló alguien o el tiempo
            continue
        item = {"flujo": c.get("name"), "id": c["id"], "url": c.get("html_url"), "lanzada": madrid(creada),
                "desplazada_por": quien[0].get("html_url"), "relanzada": False}
        # Cualquier ejecución posterior del mismo flujo que no se canceló la sustituye (la que la desplazó o una
        # lanzada después). El 31/10 a las 15:46 se relanzó el motor del respaldo sin ver que ya corría otro motor
        # lanzado a mano después: la conversación tuvo que cancelarlo.
        if any(o["id"] != c["id"] and o.get("path") == c.get("path") and fecha(o["created_at"]) > creada
               and o.get("conclusion") != "cancelled" for o in runs):
            item["relanzada"] = "no hace falta: la sustituye otra del mismo flujo"
        elif any(o["id"] != c["id"] and o.get("path") == c.get("path") and actor(o) == actor(c)
                 and o.get("event") == "workflow_dispatch" and fecha(o["created_at"]) > fin for o in runs):
            item["relanzada"] = "no hace falta: ya la relanzó quien la lanzó"
        elif any(grupo(o) == g and o.get("status") in ("pending", "waiting", "requested") for o in runs):
            item["relanzada"] = "aún no: hay otra esperando en el grupo"
        elif actuar:
            try:
                api(f"/repos/{repo}/actions/runs/{c['id']}/rerun", metodo="POST", datos={})
                item["relanzada"] = True
            except urllib.error.HTTPError as e:
                item["relanzada"] = f"no se pudo: {e.code}"
        salida.append(item)
    return salida


LIMITE_AVISO_FICHERO = 80 * 1024 * 1024   # GitHub rechaza ficheros de más de 100 MB al subir


CARPETAS_AGREGADOS = ("datos", "datos/oposiciones", "datos/oposiciones/procesos", "datos/oposiciones/huerfanos",
                      "datos/boe", "datos/autonomicos", "datos/provinciales")


def ficheros_grandes(repo: str, rama: str = "datos") -> list[dict]:
    """Ficheros de la rama de datos que pasan de 80 MB (GitHub rechaza la subida a partir de 100 MB). Se miran las
    carpetas donde están los ficheros agregados (los que crecen); las de cada día o cada boletín son pequeñas."""
    salida = []
    for carpeta in CARPETAS_AGREGADOS:
        try:
            entradas = api(f"/repos/{repo}/contents/{carpeta}?ref={rama}")
        except urllib.error.HTTPError:
            continue
        for e in entradas if isinstance(entradas, list) else []:
            if e.get("type") == "file" and e.get("size", 0) > LIMITE_AVISO_FICHERO:
                salida.append({"fichero": e["path"], "mb": round(e["size"] / 1048576, 1)})
    return salida


def reanimar_latido(repo: str, t0: datetime, lanzar: bool) -> str:
    """latido.yml es una cadena que se relanza sola cada ~25 min mientras GitHub no dispare las programaciones.
    Si la cadena se cortó (ninguna ejecución en 45 min) y las programaciones siguen sin dispararse, se relanza."""
    if not Path(".github/workflows/latido.yml").exists():
        return "no existe"
    def cuantas(ruta: str) -> int:
        return api(ruta).get("total_count", 0)
    try:
        hace3h = (t0 - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        # El vigilante está programado dos veces por hora: en 3 horas tocan 6. Solo se da por buena la programación
        # de GitHub si llegan al menos 4; el 30/10 llegaban de vez en cuando y con 5 a 7 horas de retraso.
        programadas = cuantas(f"/repos/{repo}/actions/workflows/vigilante.yml/runs?event=schedule&per_page=1&created=>={hace3h}")
        if programadas >= PROGRAMACION_FIABLE:
            return f"no hace falta: GitHub disparó {programadas} programaciones del vigilante en 3 horas"
        hace45 = (t0 - timedelta(minutes=45)).strftime("%Y-%m-%dT%H:%M:%SZ")
        if cuantas(f"/repos/{repo}/actions/workflows/latido.yml/runs?per_page=1&created=>={hace45}"):
            return "en marcha"
        if not lanzar:
            return "cortado (sin relanzar)"
        api(f"/repos/{repo}/actions/workflows/latido.yml/dispatches", metodo="POST", datos={"ref": "main"})
        return "cortado: relanzado"
    except urllib.error.HTTPError as e:
        return f"no se pudo comprobar: {e.code}"


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
        # ¿O una posterior que aún no ha terminado (relanzada a mano o por otra vía)?
        posterior_en_curso = next((o["html_url"] for o in runs if o.get("workflow_id") == r.get("workflow_id")
                                   and o.get("status") != "completed"
                                   and fecha(o["created_at"]) > fecha(r["created_at"])), None)
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
             "superado": posterior_ok, "en_curso": None if posterior_ok else posterior_en_curso,
             "pasajero": pasajero, "detalle": detalle}
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

    respaldos = respaldo_programaciones(repo, runs, t0, a.relanzar)
    tardias = cancelar_programaciones_tardias(repo, t0, a.relanzar)
    desplazadas = reponer_desplazadas(repo, runs, a.relanzar)
    grandes = ficheros_grandes(repo)
    latido = reanimar_latido(repo, t0, a.relanzar)

    estado_fuentes = json_de_rama(repo, "datos/estado.json", "datos") or {}
    boe = json_de_rama(repo, "datos/boe/estado.json", "datos") or {}
    avisos_fuentes = []
    for nombre, e in (estado_fuentes.get("fuentes") or {}).items() if isinstance(estado_fuentes.get("fuentes"), dict) else []:
        if isinstance(e, dict) and (e.get("aviso") or e.get("parada") or e.get("errores")):
            avisos_fuentes.append({"fuente": nombre, **{k: e.get(k) for k in ("aviso", "parada", "errores",
                                                                                 "ultimo_boletin", "dias_habiles_sin_noticias")}})

    pendientes = [f for f in fallos if not f["superado"] and not f.get("relanzado") and not f.get("en_curso")]
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
            "programaciones_lanzadas_a_mano": [r["flujo"] for r in respaldos if r["lanzado"] is True],
            "avisos_de_fuentes": len(avisos_fuentes),
            "almacen": None,
        },
        "fallos": fallos,
        "colas_largas": colas,
        "programados": programados,
        "respaldo_programaciones": respaldos,
        "programaciones_tardias_canceladas": tardias,
        "desplazadas_de_la_espera": desplazadas,
        "ficheros_de_mas_de_80_mb": grandes,
        "latido": latido,
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
          f"- Programaciones que GitHub no disparó y se lanzaron a mano: "
          f"{', '.join(r['flujo'] + ' (' + r['prevista'] + ')' for r in respaldos) or 'ninguna'}",
          f"- Programaciones que GitHub disparó tarde y repetían la del día (canceladas): "
          f"{', '.join(t['flujo'] + ' de las ' + t['prevista'] + ', disparada a las ' + t['disparada'] for t in tardias) or 'ninguna'}",
          f"- Tandas que otra del mismo grupo de concurrencia sacó de la espera: "
          f"{'; '.join(d['flujo'] + ' de las ' + d['lanzada'] + ' (' + ('relanzada' if d['relanzada'] is True else str(d['relanzada'])) + ')' for d in desplazadas if not str(d['relanzada']).startswith('no hace falta')) or 'ninguna'}",
          f"- Latido (relanza al vigilante cada ~25 min mientras GitHub no dispare programaciones): {latido}",
          f"- Ficheros de la rama datos de más de 80 MB (GitHub rechaza más de 100): "
          f"{', '.join(g['fichero'] + ' (' + str(g['mb']) + ' MB)' for g in grandes) or 'ninguno'}",
          f"- Avisos de fuentes: {len(avisos_fuentes)}", ""]
    for f in fallos:
        marca = ("superado" if f["superado"] else "relanzado" if f.get("relanzado") is True
                 else f"otra ejecución en curso: {f['en_curso']}" if f.get("en_curso") else "PENDIENTE")
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
