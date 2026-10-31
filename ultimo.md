# Vigilancia 31/10 03:43 (Madrid)

- Ejecuciones revisadas (últimas 6 h): 156
- Fallos: 2; pendientes: 1; relanzados ahora: 0
- Colas de más de 30 minutos: 0
- Flujos programados parados: ninguno
- Almacén S3: ok
- Programaciones que GitHub no disparó y se lanzaron a mano: ninguna
- Programaciones que GitHub disparó tarde y repetían la del día (canceladas): ninguna
- Latido (relanza al vigilante cada ~25 min mientras GitHub no dispare programaciones): en marcha
- Ficheros de la rama datos de más de 80 MB (GitHub rechaza más de 100): ninguno
- Avisos de fuentes: 0

## Motor de datos · 31/10 02:20 · PENDIENTE
https://github.com/alvarorm931/education/actions/runs/41146163155 (intento 2, workflow_dispatch, 94424c2, pasajero: False)
- motor · pasos: Avisar si hay huecos o errores · ejecutor: GitHub Actions 1000001423
      [36;1mh = json.load(open("salida/datos/boe/huecos.json"))[0m
      [36;1mproblemas = {k: v for k, v in h.items() if k in ("numeros_de_diario_que_faltan", "dias_sin_procesar", "dias_con_error") and v}[0m
      [36;1mif problemas:[0m
      [36;1m    print("::error::Huecos en el BOE: " + json.dumps(problemas, ensure_ascii=False)[:500])[0m
      [36;1m    sys.exit(1)[0m
      [36;1mprint("Sin huecos en el BOE. Anuncios sin texto:", h.get("anuncios_sin_texto"))[0m
      [36;1mEOF[0m
      ##[error]Huecos en el BOE: {"dias_con_error": ["2026-10-31"]}

## Estudios por tramos · 31/10 02:57 · superado
https://github.com/alvarorm931/education/actions/runs/41140514779 (intento 1, workflow_dispatch, 0e7f07e, pasajero: False)
- tramo (leer --portadas entrada/masters-estado/entradas/portadas/portadas_ub.jsonl --navegador --p... · pasos: Chromium para las páginas que solo se pintan con JavaScript (extracción con --navegador), Subir este tramo a sondas (por_tramo=si) · ejecutor: motor-espana
      HEAD is now at 814ab3c699 CLAUDE.md: pytest en verde antes de subir, también con MOTOR_ORIGINALES=s3
      Deleted branch main (was 814ab3c699).
      Removing motor.egg-info/
      Removing motor/__pycache__/
      Removing motor/autonomicos/__pycache__/
      Removing motor/boe/__pycache__/
      HEAD is now at 814ab3c699 CLAUDE.md: pytest en verde antes de subir, también con MOTOR_ORIGINALES=s3
      ##[error]error: Could not read cc3ceda89f6183a93e20fff3392f1bca9ed4c0af

