"""Sonda: ¿QEDU devuelve cursos anteriores si se le pide? (notas de corte históricas con su código de título y
centro). Prueba unos pocos nombres de campo con un solo ámbito y anota qué cursos vuelven. No guarda nada.

Uso: python -m motor.grados.sonda_qedu_anios --salida ruta/
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from motor.grados.qedu import NIVELES, Qedu


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    q = Qedu(None, pausa=2.0)
    base = {"action": "tarjeta", "offset": "0", "consulta": "", "niveles": NIVELES["grado"], "ambitos": "721"}
    pruebas = [{}] + [{k: v} for k in ("anio", "curso", "anioAcademico", "anyo", "year")
                      for v in ("2022-2023", "2022")]
    res = []
    for extra in pruebas:
        try:
            datos, _ = q.post({**base, **extra})
            datos = datos or []
            res.append({"extra": extra, "filas": len(datos), "cursos": sorted({str(t.get("anio")) for t in datos}),
                        "muestra_nota": [t.get("notaCorte") for t in datos[:5]]})
        except Exception as e:  # noqa: BLE001
            res.append({"extra": extra, "error": f"{type(e).__name__}: {str(e)[:120]}"})
    t = None
    try:
        datos, _ = q.post(base)
        t = (datos or [None])[0]
        for extra in [{}, {"anio": "2022-2023"}, {"curso": "2022-2023"}]:
            d, _ = q.post({"action": "detalle", "codTit": t["codTitula"], "codCentro": t["codCentro"],
                           "codUniv": t["codUniv"], **extra})
            res.append({"detalle": extra, "claves": sorted((d or {}).keys())[:60],
                        "anios": [(d or {}).get("anioActual"), (d or {}).get("anioAnterior")],
                        "notas": [(d or {}).get("notaCorte"), (d or {}).get("notaCorteAnterior")]})
    except Exception as e:  # noqa: BLE001
        res.append({"detalle_error": f"{type(e).__name__}: {str(e)[:120]}"})
    d = Path(a.salida) / "datos" / "estudios" / "grados" / "sonda_qedu"
    d.mkdir(parents=True, exist_ok=True)
    (d / "anios.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
