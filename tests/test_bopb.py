"""BOPB (Barcelona) con páginas reales del 28/10/2026, 12/10/2026 (festivo), 25/10/2026 (domingo) y 04/01/2022."""
from datetime import date
from pathlib import Path

from motor.archivo import Archivo
from motor.extraccion.plazas import extraer_plazas
from motor.extraccion.plazo import extraer_plazo
from motor.http import Respuesta
from motor.provinciales import bopb, bopt, diba

F = Path(__file__).parent / "fixtures"


def _leer(n):
    return (F / n).read_text(encoding="utf-8")


def test_dia_paginado_y_seleccion():
    p1 = bopb.parsear_dia(_leer("bopb_personal_20261028_p1.html"))
    p2 = bopb.parsear_dia(_leer("bopb_personal_20261028_p2.html"))
    assert (p1["fecha"], p1["total"], len(p1["anuncios"]), len(p2["anuncios"])) == ("2026-10-28", 27, 20, 7)
    x = next(a for a in p1["anuncios"] if a["cve"] == "202610159101")
    assert x["anunciante"] == "Ajuntament de Bigues i Riells del Fai" and x["fecha"] == "2026-10-28"
    assert x["url_pdf"] == "https://bop.diba.cat/anunci/descarrega-pdf/4007221" and x["id"] == "BOPB-202610159101"
    sel = {s["cve"]: s for s in bopb.seleccionar(p1["anuncios"] + p2["anuncios"])}
    s = sel["202610159101"]
    assert (s["tipo_acto"], s["ambito"], s["convocante"]["tipo"], s["convocante"]["nombre"], s["convocante"]["provincia"]) \
        == ("convocatoria", "local", "Ayuntamiento", "Bigues i Riells del Fai", "Barcelona")
    tipos = {s["tipo_acto"] for s in sel.values()}
    assert {"admitidos", "nombramiento", "convocatoria"} <= tipos
    # El juez de paz cae en «Personal» pero no es empleo público
    assert not any("jutge" in s["titulo"].lower() for s in sel.values())


def test_festivo_domingo_y_2022():
    assert bopb.parsear_dia(_leer("bopb_festivo_20261012.html")) == {"fecha": "2026-10-12", "total": 0, "anuncios": []}
    assert len(bopb.parsear_dia(_leer("bopb_personal_20220104.html"))["anuncios"]) == 6


def test_procesar_dia_con_paginas_y_domingo(tmp_path, monkeypatch):
    paginas = {bopb.url_dia(date(2026, 10, 28), 1): _leer("bopb_personal_20261028_p1.html"),
               bopb.url_dia(date(2026, 10, 28), 2): _leer("bopb_personal_20261028_p2.html")}

    def falso(url, **kw):
        if url in paginas:
            return Respuesta(url, 200, paginas[url].encode(), {})
        return Respuesta(url, 500, _leer("bopb_domingo_20261025.html").encode(), {})

    monkeypatch.setattr(diba, "obtener", falso)
    a = Archivo(tmp_path / "archivo", indice_por_fuente=True, solo_huella=True)
    inf = bopb.procesar_dia(date(2026, 10, 28), tmp_path, a, pausa=0)
    assert (inf["resultado"], inf["paginas"], inf["disposiciones"]) == ("ok", 2, 27) and not inf["alertas"]
    assert bopb.procesar_dia(date(2026, 10, 25), tmp_path, a, pausa=0)["resultado"] == "sin_boletin"
    assert bopb.procesar_dia(date(2026, 10, 27), tmp_path, a, pausa=0)["resultado"] == "error_http"


def test_texto_de_bases_en_catalan():
    # Texto real del PDF del anuncio 202610159101, ya extraído
    t = ("ANUNCI\nHavent-se aprovat per Resolució d’Alcaldia, les Bases reguladores i la convocatòria de les proves\n"
         "selectives per a la provisió en propietat d’una plaça de caporal/a de la policia local , es fa públic el\n"
         "present anunci i s’obre el termini de presentació de sol·licituds, que serà de 20 dies hàbils comptats a\n"
         "partir de l’endemà de la publicació d’aquest anunci en el Diari Oficial de la Generalitat de Catalunya:\n"
         "Butlletí Oficial de la Província de Barcelona\nData 28-10-2026\nCVE 202610159101\nPàg. 2-27\n")
    from motor.limpieza import limpiar_texto
    limpio = limpiar_texto(t, bopb.RE_CABECERA_PDF)["texto"]
    assert "CVE" not in limpio and "Pàg." not in limpio
    p = extraer_plazo(limpio, "2026-10-28", bopb.NOMBRES)
    assert p["dias"] == 20 and p["cuenta_desde"] == "Diari Oficial de la Generalitat de Catalunya"
    pl = extraer_plazas(limpio)
    assert pl["total"] == 1 and pl["plazas"][0]["denominacion"] == "caporal/a de la policia local"


def test_tarragona_misma_plataforma():
    # Página del día sin filtro (55 anuncios): misma estructura; registro con guion y anunciante en mayúsculas
    s = diba.parsear_dia(bopt.BOLETIN, _leer("bopt_20261028_todo.html"))
    assert (s["fecha"], s["total"], len(s["anuncios"])) == ("2026-10-28", 55, 20)
    x = s["anuncios"][0]
    assert x["id"] == "BOPT-2026-09775" and x["url_pdf"] == "https://www.dipta.cat/bopt/web/anunci/descarrega-pdf/365595"
    assert x["url_html"].startswith("https://www.dipta.cat/bopt/web/anunci/365595/")
    assert bopt.BOLETIN.url_dia(date(2026, 10, 28), 2) == \
        "https://www.dipta.cat/bopt/web/anteriors/2026-10-28/2?bopb_dia%5BtipusAnunci%5D=23"
    from motor.autonomicos.comun import convocante_de_organismo
    assert convocante_de_organismo("AJUNTAMENT ALDEA, L'")["nombre"] == "L'Aldea"
    assert convocante_de_organismo("AJUNTAMENT VENDRELL, EL")["nombre"] == "El Vendrell"


def test_canal_rss_de_datos_abiertos(tmp_path, monkeypatch):
    # robots.txt prohíbe /anteriors/ y los PDF; el canal de datos abiertos del día está permitido.
    from motor.archivo import Archivo
    from motor.http import Respuesta
    from motor.provinciales import bopb, diba

    import json
    from pathlib import Path
    FIX = Path(__file__).parent / "fixtures"
    cuerpo = (FIX / "bopb_feed_20261030.xml").read_bytes()
    monkeypatch.setattr(diba, "obtener", lambda url, **k: Respuesta(url, 200, cuerpo, {}))
    inf = diba.procesar_feed(bopb.BOLETIN, tmp_path, Archivo(tmp_path / "archivo"))
    assert (inf["resultado"], inf["fecha"], inf["disposiciones"], inf["anuncios_personal"]) == ("ok", "2026-10-30", 159, 39)
    filas = [json.loads(l) for l in (tmp_path / "datos/provinciales/bopb/oposiciones/2026/10/30.jsonl").read_text().splitlines()]
    garriga = [f for f in filas if f["anunciante"] == "Ajuntament de la Garriga"][0]
    assert garriga["url_html"] == "https://bop.diba.cat/anunci/" + garriga["numero_anuncio"]
    assert garriga["tipo_anuncio"].startswith("Personal | Convocatòries")
    assert garriga["convocante"]["nombre"] == "La Garriga"


def test_un_dia_raro_no_para_la_carga(tmp_path, monkeypatch, capsys):
    """Una excepción al leer un día queda como error_formato de ese día y la carga sigue con el anterior."""
    import json
    vistos = []

    def falso(b, d, raiz, archivo, pausa=1.0):
        vistos.append(d)
        if d == date(2025, 7, 26):
            raise TypeError("unsupported operand type(s) for /: 'NoneType' and 'int'")
        return {"fecha": d.isoformat(), "resultado": "ok", "alertas": []}

    monkeypatch.setattr(diba, "procesar_dia", falso)
    monkeypatch.setattr(diba.time, "sleep", lambda s: None)
    bopb.main(["--desde", "2025-07-24", "--hasta", "2025-07-27", "--salida", str(tmp_path), "--pausa", "0"])
    assert vistos == [date(2025, 7, 27), date(2025, 7, 26), date(2025, 7, 25), date(2025, 7, 24)]
    raro = json.loads((tmp_path / "datos" / "provinciales" / "bopb" / "dias" / "2025" / "07" / "26.json").read_text())
    assert raro["resultado"] == "error_formato" and "TypeError" in raro["alertas"][0]


def test_dias_viejos_con_error_no_paran_la_carga(tmp_path, monkeypatch):
    """Ocho días viejos con HTTP 500 permanente, repartidos por el año, se reintentan pero no cuentan para el freno:
    la carga llega a los días nuevos."""
    import json
    base = tmp_path / "datos" / "provinciales" / "bopb" / "dias"
    malos = [date(2025, 9, d) for d in (1, 3, 5, 8, 10, 12, 15, 17, 19, 22)]
    for d in malos:
        r = base / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.json"
        r.parent.mkdir(parents=True, exist_ok=True)
        r.write_text(json.dumps({"fecha": d.isoformat(), "resultado": "error_http"}))
    nuevos = []

    def falso(b, d, raiz, archivo, pausa=1.0):
        if d in malos:
            return {"fecha": d.isoformat(), "resultado": "error_http", "alertas": ["HTTP 500"]}
        nuevos.append(d)
        return {"fecha": d.isoformat(), "resultado": "ok", "alertas": []}

    def hecho(d):
        r = base / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.json"
        r.parent.mkdir(parents=True, exist_ok=True)
        r.write_text(json.dumps({"fecha": d.isoformat(), "resultado": "ok"}))

    for k in range(1, 31):
        if date(2025, 9, k) not in malos:
            hecho(date(2025, 9, k))
    monkeypatch.setattr(diba, "procesar_dia", falso)
    monkeypatch.setattr(diba.time, "sleep", lambda s: None)
    bopb.main(["--desde", "2025-08-28", "--hasta", "2025-09-30", "--salida", str(tmp_path), "--pausa", "0"])
    assert date(2025, 8, 28) in nuevos


def test_freno_cuenta_solo_lo_nuevo():
    from motor.autonomicos.comun import Freno
    f = Freno(max_seguidos=3)
    assert not any(f.anotar({"resultado": "error_http"}, reintento=True) for _ in range(10))
    assert not f.anotar({"resultado": "error_http"}) and not f.anotar({"resultado": "error_http"})
    assert f.anotar({"resultado": "error_http"})
