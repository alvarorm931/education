"""Vigilante: tandas que otra del mismo grupo de concurrencia sacó de la espera (infra/vigilante.py)."""
import importlib.util
from pathlib import Path

import pytest

RUTA = Path(__file__).resolve().parents[1] / "infra" / "vigilante.py"


@pytest.fixture()
def v(monkeypatch):
    spec = importlib.util.spec_from_file_location("vigilante_prueba", RUTA)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    llamadas = []

    def api(ruta, metodo="GET", datos=None, crudo=False):
        llamadas.append((metodo, ruta))
        if ruta.endswith("/jobs?per_page=5"):
            return {"jobs": []}
        return {}

    monkeypatch.setattr(mod, "api", api)
    mod.llamadas = llamadas
    return mod


GRUPOS = {"motor.yml": "rama-datos", "mantenimiento.yml": "rama-datos"}


def run(i, flujo, evento, estado, conclusion, creada, fin, actor="alvarorm931", intento=1):
    return {"id": i, "name": flujo, "path": f".github/workflows/{flujo}", "event": evento, "status": estado,
            "conclusion": conclusion, "created_at": creada, "updated_at": fin, "run_attempt": intento,
            "triggering_actor": {"login": actor}, "html_url": f"https://x/{i}"}


def test_grupo_de_concurrencia_solo_a_nivel_de_flujo(tmp_path, v):
    (tmp_path / "a.yml").write_text("name: A\nconcurrency:\n  group: rama-datos\n  cancel-in-progress: false\n")
    (tmp_path / "b.yml").write_text("name: B\njobs:\n  x:\n    concurrency:\n      group: otro\n")
    (tmp_path / "c.yml").write_text("name: C\nconcurrency:\n  group: g-${{ github.ref }}\n")
    assert v.grupos_de_concurrencia(tmp_path) == {"a.yml": "rama-datos"}


def test_relanza_la_tanda_que_tiro_una_programacion_tardia(v):
    runs = [run(1, "mantenimiento.yml", "workflow_dispatch", "completed", "cancelled",
                "2026-10-31T12:51:50Z", "2026-10-31T13:03:38Z"),
            run(2, "motor.yml", "schedule", "completed", "cancelled", "2026-10-31T13:03:36Z", "2026-10-31T13:04:04Z"),
            run(3, "motor.yml", "workflow_dispatch", "in_progress", None, "2026-10-31T11:18:06Z", "2026-10-31T13:00:00Z")]
    r = v.reponer_desplazadas("o/r", runs, actuar=True, grupos=GRUPOS)
    assert [d["id"] for d in r] == [1] and r[0]["relanzada"] is True
    assert ("POST", "/repos/o/r/actions/runs/1/rerun") in v.llamadas


def test_no_relanza_si_ya_la_relanzo_su_autor(v):
    runs = [run(1, "mantenimiento.yml", "workflow_dispatch", "completed", "cancelled",
                "2026-10-31T12:51:50Z", "2026-10-31T13:03:38Z"),
            run(2, "motor.yml", "schedule", "completed", "cancelled", "2026-10-31T13:03:36Z", "2026-10-31T13:04:04Z"),
            run(4, "mantenimiento.yml", "workflow_dispatch", "in_progress", None, "2026-10-31T13:32:15Z", "2026-10-31T13:32:21Z")]
    r = v.reponer_desplazadas("o/r", runs, actuar=True, grupos=GRUPOS)
    assert r[0]["relanzada"].startswith("no hace falta")
    assert not any(m == "POST" for m, _ in v.llamadas)


def test_no_relanza_si_la_sustituye_otra_del_mismo_flujo(v):
    runs = [run(1, "motor.yml", "workflow_dispatch", "completed", "cancelled", "2026-10-31T13:57:43Z",
                "2026-10-31T14:03:18Z", actor="github-actions[bot]"),
            run(2, "motor.yml", "workflow_dispatch", "pending", None, "2026-10-31T14:03:16Z", "2026-10-31T14:03:16Z")]
    r = v.reponer_desplazadas("o/r", runs, actuar=True, grupos=GRUPOS)
    assert r[0]["relanzada"] == "no hace falta: la sustituye otra del mismo flujo"


def test_espera_si_hay_otra_esperando_en_el_grupo(v):
    runs = [run(1, "mantenimiento.yml", "workflow_dispatch", "completed", "cancelled",
                "2026-10-31T12:51:50Z", "2026-10-31T13:03:38Z"),
            run(2, "motor.yml", "workflow_dispatch", "pending", None, "2026-10-31T13:03:36Z", "2026-10-31T13:03:36Z",
                actor="otra")]
    r = v.reponer_desplazadas("o/r", runs, actuar=True, grupos=GRUPOS)
    assert r[0]["relanzada"] == "aún no: hay otra esperando en el grupo"
    assert not any(m == "POST" for m, _ in v.llamadas)


def test_ignora_las_canceladas_que_llegaron_a_empezar_o_sin_otra_cerca(v, monkeypatch):
    runs = [run(1, "mantenimiento.yml", "workflow_dispatch", "completed", "cancelled",
                "2026-10-31T12:00:00Z", "2026-10-31T12:30:00Z"),
            run(2, "motor.yml", "workflow_dispatch", "in_progress", None, "2026-10-31T13:03:36Z", "2026-10-31T13:03:36Z")]
    assert v.reponer_desplazadas("o/r", runs, actuar=True, grupos=GRUPOS) == []
    runs[1]["created_at"] = "2026-10-31T12:29:50Z"
    monkeypatch.setattr(v, "api", lambda ruta, **k: {"jobs": [{"started_at": "2026-10-31T12:01:00Z"}]})
    assert v.reponer_desplazadas("o/r", runs, actuar=True, grupos=GRUPOS) == []
