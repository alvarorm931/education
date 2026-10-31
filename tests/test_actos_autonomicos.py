"""Actos autonómicos: registro de oposiciones + texto -> acto con plazo calculado desde el propio boletín."""

import json

from motor.autonomicos import actos
from motor.autonomicos.comun import escribir_json, escribir_jsonl


def test_acto_con_plazo_desde_el_propio_boletin(tmp_path):
    x = {"id": "BOCYL-D-28102026-209-2", "fecha": "2026-10-28", "boletin": "209/2026", "titulo": "ORDEN ... convoca",
         "organismo": "CONSEJERÍA DE LA PRESIDENCIA", "ambito": "autonomico", "tipo_acto": "convocatoria",
         "alcance": "acceso", "url_html": "https://bocyl.jcyl.es/html/2026/10/28/html/BOCYL-D-28102026-209-2.do"}
    escribir_jsonl(tmp_path / "datos/autonomicos/bocyl/oposiciones/2026/10.jsonl", [x])
    escribir_json(actos.ruta_texto(tmp_path, "bocyl", x), {"texto": (
        "Las solicitudes se presentarán en el plazo de veinte días hábiles contados a partir del día siguiente al de "
        "la publicación de esta orden en el «Boletín Oficial de Castilla y León».")})
    # Un registro sin texto todavía
    escribir_jsonl(tmp_path / "datos/autonomicos/bocyl/oposiciones/2026/09.jsonl", [{**x, "id": "OTRO", "fecha": "2026-09-01"}])
    assert actos.main(["--salida", str(tmp_path)]) == 0
    salida = [json.loads(l) for l in (tmp_path / "datos/autonomicos/actos/bocyl/2026/10.jsonl").read_text().splitlines()]
    a = salida[0]
    assert a["id"] == "bocyl:BOCYL-D-28102026-209-2" and a["fuente"] == "BOCYL"
    assert a["plazo"]["fin_estimado"] == "2026-11-26" and a["extraccion"] == "plazo_general_v4"  # 2/11 festivo en CyL
    sin = json.loads((tmp_path / "datos/autonomicos/actos/bocyl/2026/09.jsonl").read_text())
    assert sin["pendiente"] == ["texto"]


def test_mes_sin_anuncios_se_borra(tmp_path):
    x = {"id": "BOP-LUGO-2023-1", "fecha": "2023-12-29", "titulo": "Listado provisional de admitidos", "ambito": "local"}
    escribir_jsonl(tmp_path / "datos/provinciales/boplugo/oposiciones/2023/12/29.jsonl", [x])
    viejo = tmp_path / "datos/autonomicos/actos/boplugo/8202/12.jsonl"
    escribir_jsonl(viejo, [{"id": "boplugo:BOP-LUGO-8202-1", "fecha": "8202-12-29"}])
    assert actos.main(["--salida", str(tmp_path)]) == 0
    assert not viejo.exists() and not viejo.parent.exists()
    assert (tmp_path / "datos/autonomicos/actos/boplugo/2023/12.jsonl").exists()
