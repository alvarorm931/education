"""Comprobaciones que solo se ven con un navegador (Chromium, con Playwright).

Para una muestra de páginas de cada plantilla:
1. **Contenido que añade JavaScript.** Se compara el texto de `<main>` del HTML servido con el que queda tras
   ejecutar JavaScript. Si el JavaScript añade contenido, un robot que no lo ejecuta no lo ve (los de IA no
   ejecutan JavaScript; Google lo hace más tarde y no siempre): no se publica.
2. **Directivas cambiadas con JavaScript.** `noindex` o canónica distintos tras ejecutar JavaScript: no se publica
   (Google: «don't use JavaScript to change the robots meta tag»; ley, regla 10).
3. **Ventanas al cargar.** Elementos fijos que tapan más de una cuarta parte de la pantalla del móvil tres segundos
   después de cargar: no se publica (ventanas intrusivas).
4. **Velocidad de la plantilla en laboratorio**, en condiciones de móvil lento como las de Lighthouse (red de
   150 ms de latencia y 1,6 Mbit/s, procesador 4 veces más lento, pantalla de 412 × 823): LCP ≤ 2,5 s y CLS ≤ 0,1
   en la mediana de las páginas medidas. Si falla, no se publica ninguna página de la plantilla.

En laboratorio no hay interacción del usuario, así que el CLS cuenta todos los desplazamientos: Chromium marca
como «con interacción reciente» (y la API los descarta) los de los primeros 500 ms tras una navegación iniciada por
Playwright, y sin esto un anuncio que empuja el contenido al cargar pasaría el control.

INP no se puede medir en laboratorio sin interacciones reales; se vigila con los datos reales de CrUX
(`motor/seo/vigilancia.py`).

Los recursos de terceros no se cargan (la prueba es hermética) y se anotan como aviso: cada uno cuesta velocidad
y, si pone cookies, obliga a pedir consentimiento.
"""

from __future__ import annotations

import mimetypes
import re
import statistics
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

PALABRA = re.compile(r"\w+", re.UNICODE)
LCP_MAX, CLS_MAX = 2500, 0.1
PORCION_VENTANA = 0.25
MOVIL = {"viewport": {"width": 412, "height": 823}, "device_scale_factor": 1.75, "is_mobile": True,
         "has_touch": True,
         "user_agent": "Mozilla/5.0 (Linux; Android 11; moto g power (2022)) AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/137.0.0.0 Mobile Safari/537.36"}
RED_LENTA = {"offline": False, "latency": 150, "downloadThroughput": 1.6 * 1024 * 1024 / 8,
             "uploadThroughput": 750 * 1024 / 8}

MEDIDOR = """
window.__cwv = {lcp: 0, cls: 0};
new PerformanceObserver(l => { for (const e of l.getEntries()) window.__cwv.lcp = e.renderTime || e.loadTime || e.startTime; })
  .observe({type: 'largest-contentful-paint', buffered: true});
let sv = 0, ini = 0, ult = 0;
new PerformanceObserver(l => { for (const e of l.getEntries()) {
    if (sv && e.startTime - ult < 1000 && e.startTime - ini < 5000) { sv += e.value; } else { sv = e.value; ini = e.startTime; }
    ult = e.startTime; window.__cwv.cls = Math.max(window.__cwv.cls, sv);
  } }).observe({type: 'layout-shift', buffered: true});
"""

VENTANAS = """() => {
  const vw = innerWidth, vh = innerHeight, out = [];
  for (const el of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(el);
    const abierto = el.tagName === 'DIALOG' && el.open;
    if (!abierto && cs.position !== 'fixed' && cs.position !== 'sticky') continue;
    if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) continue;
    const r = el.getBoundingClientRect();
    const w = Math.max(0, Math.min(r.right, vw) - Math.max(r.left, 0));
    const h = Math.max(0, Math.min(r.bottom, vh) - Math.max(r.top, 0));
    const p = w * h / (vw * vh);
    if (p > %s) out.push(`<${el.tagName.toLowerCase()}${el.id ? ' id=' + el.id : ''}> tapa el ${Math.round(p * 100)} %% de la pantalla`);
  }
  return out;
}""" % PORCION_VENTANA

DIRECTIVAS = """() => ({
  robots: [...document.querySelectorAll('meta[name=robots i], meta[name=googlebot i]')].map(m => m.content.toLowerCase()).sort().join('|'),
  canonica: [...document.querySelectorAll('link[rel~=canonical]')].map(l => l.getAttribute('href')).join('|'),
  main: document.querySelector('main') ? document.querySelector('main').innerText : ''
})"""


class _Silencioso(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def _servidor(sitio: Path) -> tuple[ThreadingHTTPServer, str]:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(_Silencioso, directory=str(sitio)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def muestra_por_plantilla(control, por_plantilla: int) -> dict[str, list[str]]:
    grupos: dict[str, list[str]] = {}
    for r, p in sorted(control.paginas.items()):
        plantilla = control.manifiesto.get(r, {}).get("plantilla") or control.tipo(p) or "sin-plantilla"
        grupos.setdefault(plantilla, []).append(r)
    # Repartidas a lo largo de la lista, no las primeras: en orden alfabético se parecen demasiado.
    return {k: v[:: max(1, len(v) // por_plantilla)][:por_plantilla] for k, v in grupos.items()}


def comprobar_con_navegador(sitio: Path, control, por_plantilla: int = 3, medir_velocidad: bool = True):
    from playwright.sync_api import sync_playwright

    from motor.seo.control import Fallo

    fallos: list[Fallo] = []
    srv, local = _servidor(sitio)
    externos: dict[str, set[str]] = {}
    try:
        with sync_playwright() as pw:
            nav = pw.chromium.launch()
            for plantilla, rutas in muestra_por_plantilla(control, por_plantilla).items():
                lcps, clss = [], []
                for ruta in rutas:
                    crudo = control.paginas[ruta]
                    ctx = nav.new_context(**MOVIL)
                    pagina = ctx.new_page()

                    def encaminar(route, plantilla=plantilla):
                        u = urlparse(route.request.url)
                        if f"{u.scheme}://{u.netloc}" == local:
                            return route.continue_()
                        if u.netloc == control.host:  # recurso propio con dirección absoluta: del disco
                            archivo = sitio / (u.path.lstrip("/") + ("index.html" if u.path.endswith("/") else ""))
                            if archivo.is_file():
                                return route.fulfill(body=archivo.read_bytes(),
                                                     content_type=mimetypes.guess_type(archivo.name)[0] or "")
                        externos.setdefault(plantilla, set()).add(u.netloc)
                        return route.abort()

                    pagina.route("**/*", encaminar)
                    cdp = ctx.new_cdp_session(pagina)
                    if medir_velocidad:
                        cdp.send("Network.enable")
                        cdp.send("Network.emulateNetworkConditions", RED_LENTA)
                        cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
                        pagina.add_init_script(MEDIDOR)
                    pagina.goto(local + ruta, wait_until="load", timeout=60_000)
                    pagina.wait_for_timeout(3000)
                    dom = pagina.evaluate(DIRECTIVAS)

                    palabras_html = set(PALABRA.findall(crudo.texto_main.lower()))
                    nuevas = set(PALABRA.findall(dom["main"].lower())) - palabras_html
                    if len(nuevas) > max(30, 0.05 * len(palabras_html)):
                        fallos.append(Fallo("contenido_html", ruta, f"JavaScript añade {len(nuevas)} palabras al "
                                            f"contenido principal (por ejemplo: {', '.join(sorted(nuevas)[:8])})"))
                    robots_html = "|".join(sorted(x.lower() for x in crudo.robots))
                    if dom["robots"] != robots_html:
                        fallos.append(Fallo("indexacion", ruta, f"JavaScript cambia las directivas de robots: "
                                            f"«{robots_html}» → «{dom['robots']}»"))
                    if dom["canonica"] != "|".join(crudo.canonicas):
                        fallos.append(Fallo("canonica", ruta, f"JavaScript cambia la canónica: "
                                            f"«{'|'.join(crudo.canonicas)}» → «{dom['canonica']}»"))
                    for v in pagina.evaluate(VENTANAS):
                        fallos.append(Fallo("ventanas", ruta, f"ventana al cargar: {v}"))
                    if medir_velocidad:
                        cwv = pagina.evaluate("window.__cwv")
                        lcps.append(cwv["lcp"])
                        clss.append(cwv["cls"])
                    ctx.close()
                if medir_velocidad and lcps:
                    lcp, cls = statistics.median(lcps), statistics.median(clss)
                    if lcp > LCP_MAX or cls > CLS_MAX:
                        fallos.append(Fallo("velocidad", rutas[0], f"plantilla «{plantilla}»: LCP {lcp / 1000:.2f} s "
                                            f"y CLS {cls:.3f} en laboratorio (mediana de {len(lcps)} páginas; "
                                            f"máximo 2,5 s y 0,1)"))
            nav.close()
    finally:
        srv.shutdown()
    for plantilla, hosts in sorted(externos.items()):
        fallos.append(Fallo("velocidad", plantilla, f"la plantilla «{plantilla}» carga recursos de terceros: "
                            f"{', '.join(sorted(hosts))}", "aviso"))
    return fallos
