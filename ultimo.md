# Vigilancia 31/10 01:41 (Madrid)

- Ejecuciones revisadas (últimas 6 h): 174
- Fallos: 2; pendientes: 0; relanzados ahora: 1
- Colas de más de 30 minutos: 1
- Flujos programados parados: ninguno
- Almacén S3: ok
- Programaciones que GitHub no disparó y se lanzaron a mano: ninguna
- Programaciones que GitHub disparó tarde y repetían la del día (canceladas): ninguna
- Latido (relanza al vigilante cada ~25 min mientras GitHub no dispare programaciones): en marcha
- Avisos de fuentes: 0

## Motor de datos · 31/10 01:41 · relanzado
https://github.com/alvarorm931/education/actions/runs/41146163155 (intento 1, workflow_dispatch, 94424c2, pasajero: True)
- motor · pasos: Avisar si hay huecos o errores · ejecutor: GitHub Actions 1000001408
      [36;1mh = json.load(open("salida/datos/boe/huecos.json"))[0m
      [36;1mproblemas = {k: v for k, v in h.items() if k in ("numeros_de_diario_que_faltan", "dias_sin_procesar", "dias_con_error") and v}[0m
      [36;1mif problemas:[0m
      [36;1m    print("::error::Huecos en el BOE: " + json.dumps(problemas, ensure_ascii=False)[:500])[0m
      [36;1m    sys.exit(1)[0m
      [36;1mprint("Sin huecos en el BOE. Anuncios sin texto:", h.get("anuncios_sin_texto"))[0m
      [36;1mEOF[0m
      ##[error]Huecos en el BOE: {"dias_con_error": ["2026-10-31"]}

## Prueba de conector · 30/10 22:26 · superado
https://github.com/alvarorm931/education/actions/runs/41120449947 (intento 1, workflow_dispatch, 05434bb, pasajero: False)
- prueba · pasos: Subir a la rama sondas · ejecutor: motor-espana
       ! [rejected]          sondas -> sondas (fetch first)
      error: failed to push some refs to 'https://github.com/alvarorm931/education.git'
      hint: Updates were rejected because the remote contains work that you do not
      hint: have locally. This is usually caused by another repository pushing to
      hint: the same ref. If you want to integrate the remote changes, use
      hint: 'git pull' before pushing again.
      hint: See the 'Note about fast-forwards' in 'git push --help' for details.
      ##[error]Process completed with exit code 1.

- En cola 113 min: Estudios por tramos https://github.com/alvarorm931/education/actions/runs/41140514779
