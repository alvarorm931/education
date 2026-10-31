"""Sonda con navegador sin pantalla (Chromium por Playwright) para portales que solo funcionan con JavaScript (BOP de
Almería, aplicación ZK en app.dipalme.org/bop). Abre la página, espera a que cargue, e imprime el texto visible, los
enlaces, los botones y las peticiones que hizo la página (para ver de dónde salen los datos). Opcionalmente pulsa
elementos por su texto, uno tras otro. Se identifica como el motor; lo impreso pasa por el filtro de datos de
personas de las sondas.

Uso (prueba.yml): python -m motor.provinciales.sonda_navegador https://app.dipalme.org/bop/publico.zul
                  [--pulsar Texto_del_boton,Otro_texto] (los guiones bajos son espacios)
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from motor.http import USER_AGENT
from motor.provinciales.sonda_pdf_texto import _seguro


def _instalar() -> None:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "playwright"], check=True)
    subprocess.run([sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"], check=False,
                   capture_output=True)


def _volcar(pagina, titulo: str, caracteres: int) -> None:
    print(f"===== {titulo}: {pagina.url}")
    texto = pagina.inner_text("body")
    print(_seguro(texto)[:caracteres])
    enlaces = pagina.eval_on_selector_all("a[href]", "es => es.map(e => [e.innerText.trim().slice(0, 80), e.href])")
    print("enlaces:", len(enlaces))
    for t, h in enlaces[:80]:
        print("  ", _seguro(t), "->", h)
    botones = pagina.eval_on_selector_all(
        "button, [role=button], .z-button, .z-toolbarbutton, .z-menuitem, .z-listitem, .z-row, .z-treerow, "
        ".z-tab, .z-a",
        "es => es.slice(0, 120).map(e => [e.className.slice(0, 40), e.innerText.trim().slice(0, 80)])")
    print("elementos pulsables:", len(botones))
    for c, t in botones:
        if t:
            print("  ", c, "|", _seguro(t))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("--pulsar", default="", help="textos separados por comas (guion bajo = espacio)")
    p.add_argument("--caracteres", type=int, default=6000)
    p.add_argument("--espera", type=int, default=6000, help="milisegundos tras cargar")
    p.add_argument("--salida", default="sonda")
    a = p.parse_args(argv)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        _instalar()
        from playwright.sync_api import sync_playwright
    peticiones: list[str] = []
    with sync_playwright() as pw:
        try:
            nav = pw.chromium.launch()
        except Exception:  # noqa: BLE001 - falta el navegador
            _instalar()
            nav = pw.chromium.launch()
        ctx = nav.new_context(user_agent=USER_AGENT, locale="es-ES")
        pagina = ctx.new_page()
        pagina.on("request", lambda r: peticiones.append(f"{r.method} {r.url[:200]} {(r.post_data or '')[:300]}"))
        pagina.goto(a.url, wait_until="networkidle", timeout=60000)
        pagina.wait_for_timeout(a.espera)
        _volcar(pagina, "inicio", a.caracteres)
        for texto in [x.replace("_", " ") for x in a.pulsar.split(",") if x]:
            try:
                pagina.get_by_text(texto, exact=False).first.click(timeout=15000)
                pagina.wait_for_load_state("networkidle", timeout=30000)
                pagina.wait_for_timeout(a.espera)
                _volcar(pagina, f"tras pulsar «{texto}»", a.caracteres)
            except Exception as e:  # noqa: BLE001 - se sigue con el siguiente
                print(f"no se pudo pulsar «{texto}»: {type(e).__name__}: {str(e)[:200]}")
        print("===== peticiones de la página:", len(peticiones))
        for r in peticiones[:150]:
            if "/zkau/web/" in r and r.startswith("GET"):
                continue  # recursos estáticos de ZK
            print("  ", _seguro(r))
        nav.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
