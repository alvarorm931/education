# Vigilancia 30/10 10:58 (Madrid)

- Ejecuciones revisadas (últimas 6 h): 162
- Fallos: 2; pendientes: 1; relanzados ahora: 1
- Colas de más de 30 minutos: 0
- Flujos programados parados: ninguno
- Almacén S3: ok
- Programaciones que GitHub no disparó y se lanzaron a mano: ninguna
- Latido (relanza al vigilante cada ~25 min mientras GitHub no dispare programaciones): no hace falta: GitHub ya dispara las programaciones
- Avisos de fuentes: 0

## Motor de datos · 30/10 10:58 · relanzado
https://github.com/alvarorm931/education/actions/runs/41019168283 (intento 1, workflow_dispatch, d142273, pasajero: True)
- motor · pasos: Extraer actos y comprobar huecos · ejecutor: GitHub Actions 1000000616
      remote: error: See https://gh.io/lfs for more information.        
      remote: error: File datos/oposiciones/procesos.jsonl is 174.17 MB; this exceeds GitHub's file size limit of 100.00 MB        
      remote: error: GH001: Large files detected. You may want to try Git Large File Storage - https://git-lfs.github.com.        
      To https://github.com/alvarorm931/education
       ! [remote rejected]       datos -> datos (pre-receive hook declined)
      error: failed to push some refs to 'https://github.com/alvarorm931/education'
      ##[warning]Actos y control de huecos: no se pudo subir
      ##[error]Process completed with exit code 1.

## Motor de datos · 30/10 08:07 · PENDIENTE
https://github.com/alvarorm931/education/actions/runs/41018014171 (intento 1, workflow_dispatch, 54bb117, pasajero: False)
- motor · pasos: Instalar y probar · ejecutor: GitHub Actions 1000000611
      E       KeyError: 'solo_huella'
      
      tests/test_privacidad.py:33: KeyError
      =========================== short test summary info ============================
      FAILED tests/test_boe.py::test_archivo_guarda_una_vez_y_registra - AttributeError: 'NoneType' object has no attribute 'endswith'
      FAILED tests/test_privacidad.py::test_originales_solo_huella - KeyError: 'solo_huella'
      2 failed, 586 passed, 1 skipped in 50.77s
      ##[error]Process completed with exit code 1.

