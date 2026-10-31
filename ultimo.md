# Vigilancia 31/10 04:08 (Madrid)

- Ejecuciones revisadas (últimas 6 h): 140
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
      ##[error]Huecos en el BOE: {"dias_con_error": ["2026-10-31"]}
      ##[error]Process completed with exit code 1.
      ...
      ##[error]Huecos en el BOE: {"dias_con_error": ["2026-10-31"]}
      ##[error]Process completed with exit code 1.

## Estudios por tramos · 31/10 02:57 · superado
https://github.com/alvarorm931/education/actions/runs/41140514779 (intento 1, workflow_dispatch, 0e7f07e, pasajero: False)
- tramo (leer --portadas entrada/masters-estado/entradas/portadas/portadas_ub.jsonl --navegador --p... · pasos: Chromium para las páginas que solo se pintan con JavaScript (extracción con --navegador), Subir este tramo a sondas (por_tramo=si) · ejecutor: motor-espana
      Switching to root user to install dependencies...
      sudo: a terminal is required to read the password; either use the -S option to read from standard input or configure an askpass helper
      sudo: a password is required
      Failed to install browsers
      Error: Installation process exited with code: 1
      ##[error]Process completed with exit code 1.
      cp: cannot stat 'out/.': No such file or directory
      ##[error]Process completed with exit code 1.

