"""Sonda del BOP de Almería (aplicación ZK en app.dipalme.org/bop, solo con navegador): estructura de la lista de
anuncios (cabeceras, celdas y miniaturas de cada columna), campos del buscador y adónde lleva cada miniatura de la
primera fila (la descarga que abre). Opcionalmente busca por fecha de publicación. Lo impreso pasa por el filtro de
datos de personas de las sondas; no se descarga ningún PDF.

Uso (prueba.yml): python -m motor.provinciales.sonda_almeria [--fecha 2026-10-29] [--filas 3]
"""

from __future__ import annotations

import argparse
import json
import sys

from motor.http import USER_AGENT
from motor.provinciales.sonda_navegador import _instalar
from motor.provinciales.sonda_pdf_texto import _seguro

URL = "https://app.dipalme.org/bop/publico.zul"

JS_ESTRUCTURA = """() => {
  const txt = e => (e.innerText || '').trim().replace(/\\s+/g, ' ');
  const cab = [...document.querySelectorAll('.z-listheader')].map(txt);
  const entradas = [...document.querySelectorAll('input, select, textarea')].map(e => {
    let p = e, etiqueta = '';
    for (let k = 0; k < 6 && p; k++) { p = p.parentElement; if (p && txt(p).length > 3) { etiqueta = txt(p).slice(0, 80); break; } }
    return {id: e.id, clase: (e.className || '').slice(0, 60), tipo: e.type, valor: e.value, etiqueta};
  });
  const pestanas = [...document.querySelectorAll('.z-tab, .z-menuitem, .z-toolbarbutton, .z-button')].map(txt).filter(Boolean);
  const filas = [...document.querySelectorAll('.z-listitem')].slice(0, 400).map(f => ({
    celdas: [...f.querySelectorAll('.z-listcell')].map(c => ({t: txt(c).slice(0, 200),
      img: [...c.querySelectorAll('img')].map(i => (i.getAttribute('src') || '').slice(0, 160))}))
  }));
  const paginas = [...document.querySelectorAll('.z-paging, .z-paging-info')].map(txt);
  return {cab, entradas, pestanas, total_filas: document.querySelectorAll('.z-listitem').length, filas, paginas};
}"""


def estructura(pagina, filas: int) -> dict:
    d = pagina.evaluate(JS_ESTRUCTURA)
    d["filas_muestra"] = d.pop("filas")[:filas]
    return d


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--fecha", default="", help="fecha de publicación que se busca (AAAA-MM-DD)")
    p.add_argument("--filas", type=int, default=3)
    p.add_argument("--salida", default="sonda")
    a = p.parse_args(argv)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        _instalar()
        from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        try:
            nav = pw.chromium.launch()
        except Exception:  # noqa: BLE001
            _instalar()
            nav = pw.chromium.launch()
        ctx = nav.new_context(user_agent=USER_AGENT, locale="es-ES", accept_downloads=True)
        pagina = ctx.new_page()
        pagina.goto(URL, wait_until="networkidle", timeout=60000)
        pagina.wait_for_timeout(5000)
        d = estructura(pagina, a.filas)
        print("===== portada")
        print(_seguro(json.dumps(d, ensure_ascii=False, indent=1))[:12000])
        # Adónde lleva cada miniatura de la primera fila
        imgs = pagina.locator(".z-listitem").first.locator("img")
        n = imgs.count() if not a.fecha else 0
        print("miniaturas de la primera fila:", n)
        for k in range(n):
            try:
                with pagina.expect_download(timeout=20000) as info:
                    imgs.nth(k).click()
                dl = info.value
                print(f"  miniatura {k}: descarga {dl.url} ({dl.suggested_filename})")
                dl.cancel()
            except Exception as e:  # noqa: BLE001
                print(f"  miniatura {k}: sin descarga ({type(e).__name__}); ventanas: {[pg.url for pg in ctx.pages]}")
            pagina.wait_for_timeout(1500)
        if a.fecha:
            dd = f"{a.fecha[8:10]}/{a.fecha[5:7]}/{a.fecha[:4]}"
            fechas = pagina.locator("input.z-datebox-input")
            print("cajas de fecha:", fechas.count())
            if fechas.count():
                fechas.first.fill(dd)
                fechas.first.press("Tab")  # «Igual»: la segunda caja (hasta) está oculta
                pagina.get_by_text("Buscar", exact=True).first.click()
                pagina.wait_for_load_state("networkidle", timeout=30000)
                pagina.wait_for_timeout(5000)
                d = estructura(pagina, a.filas)
                print(f"===== tras buscar {dd}")
                print(_seguro(json.dumps(d, ensure_ascii=False, indent=1))[:12000])
        nav.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
