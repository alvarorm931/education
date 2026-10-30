# Vigilancia 30/10 08:06 (Madrid)

- Ejecuciones revisadas (últimas 6 h): 319
- Fallos: 4; pendientes: 0; relanzados ahora: 0
- Colas de más de 30 minutos: 0
- Flujos programados parados: ninguno
- Almacén S3: ok
- Programaciones que GitHub no disparó y se lanzaron a mano: motor.yml (30/10 07:47)
- Latido (relanza al vigilante cada ~25 min mientras GitHub no dispare programaciones): en marcha
- Avisos de fuentes: 0

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

## Boletines autonómicos · 30/10 02:45 · superado
https://github.com/alvarorm931/education/actions/runs/40987648750 (intento 1, workflow_dispatch, 8e7f017, pasajero: False)
- preparar · pasos: Instalar y probar · ejecutor: GitHub Actions 1000000264
      motor/seo/sitemaps.py:18: in <module>
          from lxml import etree
      E   ModuleNotFoundError: No module named 'lxml'
      =========================== short test summary info ============================
      ERROR tests/test_seo.py
      !!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
      1 error in 1.24s
      ##[error]Process completed with exit code 2.

## Prueba del almacén de originales · 30/10 02:19 · superado
https://github.com/alvarorm931/education/actions/runs/40985002326 (intento 1, workflow_dispatch, 86fe8bb, pasajero: False)
- prueba · pasos: Run aws-actions/configure-aws-credentials@v4 · ejecutor: GitHub Actions 1000000242
      Assuming role with OIDC
      Assuming role with OIDC
      Assuming role with OIDC
      Assuming role with OIDC
      Assuming role with OIDC
      Assuming role with OIDC
      Assuming role with OIDC
      ##[error]Could not assume role with OIDC: Not authorized to perform sts:AssumeRoleWithWebIdentity

