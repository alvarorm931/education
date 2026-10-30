# Vigilancia 30/10 13:47 (Madrid)

- Ejecuciones revisadas (últimas 6 h): 144
- Fallos: 2; pendientes: 0; relanzados ahora: 0
- Colas de más de 30 minutos: 4
- Flujos programados parados: ninguno
- Almacén S3: ok
- Programaciones que GitHub no disparó y se lanzaron a mano: ninguna
- Latido (relanza al vigilante cada ~25 min mientras GitHub no dispare programaciones): en marcha
- Avisos de fuentes: 0

## Motor de datos · 30/10 13:30 · otra ejecución en curso: https://github.com/alvarorm931/education/actions/runs/41055944787
https://github.com/alvarorm931/education/actions/runs/41019168283 (intento 2, workflow_dispatch, d142273, pasajero: True)
- motor · pasos: BOE, textos de anuncios de oposiciones · ejecutor: GitHub Actions 1000000677
       ! [rejected]              datos -> datos (fetch first)
      error: failed to push some refs to 'https://github.com/alvarorm931/education'
      hint: Updates were rejected because the remote contains work that you do not
      hint: have locally. This is usually caused by another repository pushing to
      hint: the same ref. If you want to integrate the remote changes, use
      hint: 'git pull' before pushing again.
      hint: See the 'Note about fast-forwards' in 'git push --help' for details.
      ##[error]Process completed with exit code 1.

## Motor de datos · 30/10 08:07 · otra ejecución en curso: https://github.com/alvarorm931/education/actions/runs/41055944787
https://github.com/alvarorm931/education/actions/runs/41018014171 (intento 1, workflow_dispatch, 54bb117, pasajero: False)
- motor · pasos: Instalar y probar · ejecutor: GitHub Actions 1000000611
      E       KeyError: 'solo_huella'
      
      tests/test_privacidad.py:33: KeyError
      =========================== short test summary info ============================
      FAILED tests/test_boe.py::test_archivo_guarda_una_vez_y_registra - AttributeError: 'NoneType' object has no attribute 'endswith'
      FAILED tests/test_privacidad.py::test_originales_solo_huella - KeyError: 'solo_huella'
      2 failed, 586 passed, 1 skipped in 50.77s
      ##[error]Process completed with exit code 1.

- En cola 34 min: Prueba de conector https://github.com/alvarorm931/education/actions/runs/41053708492
- En cola 35 min: Sonda de fuentes https://github.com/alvarorm931/education/actions/runs/41053644182
- En cola 37 min: Boletines autonómicos https://github.com/alvarorm931/education/actions/runs/41053362726
- En cola 316 min: Boletines autonómicos https://github.com/alvarorm931/education/actions/runs/41020598739
