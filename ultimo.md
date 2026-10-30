# Vigilancia 30/10 08:56 (Madrid)

- Ejecuciones revisadas (últimas 6 h): 304
- Fallos: 3; pendientes: 0; relanzados ahora: 0
- Colas de más de 30 minutos: 0
- Flujos programados parados: ninguno
- Almacén S3: ok
- Programaciones que GitHub no disparó y se lanzaron a mano: ninguna
- Latido (relanza al vigilante cada ~25 min mientras GitHub no dispare programaciones): en marcha
- Avisos de fuentes: 0

## Motor de datos · 30/10 08:07 · otra ejecución en curso: https://github.com/alvarorm931/education/actions/runs/41019168283
https://github.com/alvarorm931/education/actions/runs/41018014171 (intento 1, workflow_dispatch, 54bb117, pasajero: False)
- motor · pasos: Instalar y probar · ejecutor: GitHub Actions 1000000611
      E       KeyError: 'solo_huella'
      
      tests/test_privacidad.py:33: KeyError
      =========================== short test summary info ============================
      FAILED tests/test_boe.py::test_archivo_guarda_una_vez_y_registra - AttributeError: 'NoneType' object has no attribute 'endswith'
      FAILED tests/test_privacidad.py::test_originales_solo_huella - KeyError: 'solo_huella'
      2 failed, 586 passed, 1 skipped in 50.77s
      ##[error]Process completed with exit code 1.

## Boletines autonómicos · 30/10 04:41 · superado
https://github.com/alvarorm931/education/actions/runs/40995655119 (intento 1, workflow_dispatch, f26c916, pasajero: False)
- (ninguno) · pasos: ? · ejecutor: None
      Falló sin ningún trabajo fallido: error en la definición del flujo (matriz vacía, YAML, permisos de la ejecución). Ver la página.

## Vigilante · 30/10 02:57 · superado
https://github.com/alvarorm931/education/actions/runs/40988823872 (intento 1, push, e1ed9dc, pasajero: False)
- vigilar · pasos: Subir a la rama vigilancia · ejecutor: GitHub Actions 1000000275
      outside of your sparse-checkout definition, so will not be
      updated in the index:
      historial/2026-10.jsonl
      hint: If you intend to update such entries, try one of the following:
      hint: * Use the --sparse option.
      hint: * Disable or modify the sparsity rules.
      hint: Disable this message with "git config set advice.updateSparsePath false"
      ##[error]Process completed with exit code 1.

