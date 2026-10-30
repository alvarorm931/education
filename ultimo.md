# Vigilancia 30/10 03:03 (Madrid)

- Ejecuciones revisadas (últimas 6 h): 116
- Fallos: 6; pendientes: 1; relanzados ahora: 0
- Colas de más de 30 minutos: 0
- Flujos programados parados: ninguno
- Almacén S3: ok
- Avisos de fuentes: 0

## Vigilante · 30/10 02:57 · superado
https://github.com/alvarorm931/education/actions/runs/40988823872 (intento 1, push, e1ed9dc, pasajero: False)
- vigilar · pasos: Subir a la rama vigilancia · ejecutor: GitHub Actions 1000000275
      [command]/usr/bin/git config --local --name-only --get-regexp http\.https\:\/\/github\.com\/\.extraheader
      http.https://github.com/.extraheader
      [command]/usr/bin/git config --local --unset-all http.https://github.com/.extraheader
      [command]/usr/bin/git submodule foreach --recursive sh -c "git config --local --name-only --get-regexp 'http\.https\:\/\/github\.com\/\.extraheader' && git config --local --unset-all 'http.https://github.com/.extraheader' || :"
      [command]/usr/bin/git config --local --name-only --get-regexp ^includeIf\.gitdir:
      [command]/usr/bin/git submodule foreach --recursive git config --local --show-origin --name-only --get-regexp remote.origin.url
      Cleaning up orphan processes
      ##[warning]Node.js 20 is deprecated. The following actions target Node.js 20 but are being forced to run on Node.js 24: actions/checkout@v4, aws-actions/configure-aws-credentials@v4. For more information see: https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/

## Boletines autonómicos · 30/10 02:45 · PENDIENTE
https://github.com/alvarorm931/education/actions/runs/40987648750 (intento 1, workflow_dispatch, 8e7f017, pasajero: False)
- preparar · pasos: Instalar y probar · ejecutor: GitHub Actions 1000000264
      http.https://github.com/.extraheader
      [command]/usr/bin/git config --local --unset-all http.https://github.com/.extraheader
      [command]/usr/bin/git submodule foreach --recursive sh -c "git config --local --name-only --get-regexp 'http\.https\:\/\/github\.com\/\.extraheader' && git config --local --unset-all 'http.https://github.com/.extraheader' || :"
      [command]/usr/bin/git config --local --name-only --get-regexp ^includeIf\.gitdir:
      [command]/usr/bin/git submodule foreach --recursive git config --local --show-origin --name-only --get-regexp remote.origin.url
      Evaluate and set job outputs
      Cleaning up orphan processes
      ##[warning]Node.js 20 is deprecated. The following actions target Node.js 20 but are being forced to run on Node.js 24: actions/checkout@v4, actions/setup-python@v5. For more information see: https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/

## Prueba del almacén de originales · 30/10 02:19 · superado
https://github.com/alvarorm931/education/actions/runs/40985002326 (intento 1, workflow_dispatch, 86fe8bb, pasajero: False)
- prueba · pasos: Run aws-actions/configure-aws-credentials@v4 · ejecutor: GitHub Actions 1000000242
        LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.15/x64/lib
        AWS_DEFAULT_REGION: eu-south-2
        AWS_REGION: eu-south-2
      ##[endgroup]
      Post job cleanup.
      Post job cleanup.
      Cleaning up orphan processes
      ##[warning]Node.js 20 is deprecated. The following actions target Node.js 20 but are being forced to run on Node.js 24: actions/checkout@v4, actions/setup-python@v5, aws-actions/configure-aws-credentials@v4. For more information see: https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on

## Recoger artefactos de estudios · 30/10 00:31 · superado
https://github.com/alvarorm931/education/actions/runs/40973232716 (intento 1, workflow_dispatch, d865b45, pasajero: False)
- recoger · pasos: Subir a la rama sondas · ejecutor: GitHub Actions 1000000185
      ##[error]push 2: remote: error: GH013: Repository rule violations found for refs/heads/sondas.         remote:  remote: - GITHUB PUSH PROTECTION         remote:   —————————————————————————————————————————         remote:     Resolve the following violations before pushing again         remote:  remo
      ##[error]push 3: remote: error: GH013: Repository rule violations found for refs/heads/sondas.         remote:  remote: - GITHUB PUSH PROTECTION         remote:   —————————————————————————————————————————         remote:     Resolve the following violations before pushing again         remote:  remo
      ##[error]push 4: remote: error: GH013: Repository rule violations found for refs/heads/sondas.         remote:  remote: - GITHUB PUSH PROTECTION         remote:   —————————————————————————————————————————         remote:     Resolve the following violations before pushing again         remote:  remo
      ##[error]push 5: remote: error: GH013: Repository rule violations found for refs/heads/sondas.         remote:  remote: - GITHUB PUSH PROTECTION         remote:   —————————————————————————————————————————         remote:     Resolve the following violations before pushing again         remote:  remo
      ##[error]push 6: remote: error: GH013: Repository rule violations found for refs/heads/sondas.         remote:  remote: - GITHUB PUSH PROTECTION         remote:   —————————————————————————————————————————         remote:     Resolve the following violations before pushing again         remote:  remo
      ##[error]Process completed with exit code 1.
      Cleaning up orphan processes
      ##[warning]Node.js 20 is deprecated. The following actions target Node.js 20 but are being forced to run on Node.js 24: actions/download-artifact@v4. For more information see: https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/

## Recoger artefactos de estudios · 30/10 00:26 · superado
https://github.com/alvarorm931/education/actions/runs/40972663354 (intento 1, workflow_dispatch, 0cb7fa9, pasajero: False)
- recoger · pasos: Subir a la rama sondas · ejecutor: GitHub Actions 1000000183
      remote: 
      remote: 
      To https://github.com/alvarorm931/education.git
       ! [remote rejected]   sondas -> sondas (push declined due to repository rule violations)
      error: failed to push some refs to 'https://github.com/alvarorm931/education.git'
      ##[error]Process completed with exit code 1.
      Cleaning up orphan processes
      ##[warning]Node.js 20 is deprecated. The following actions target Node.js 20 but are being forced to run on Node.js 24: actions/download-artifact@v4. For more information see: https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/

## Estudios por tramos · 30/10 00:19 · superado
https://github.com/alvarorm931/education/actions/runs/40963881714 (intento 2, workflow_dispatch, 9a06824, pasajero: False)
- juntar · pasos: Subir a la rama sondas · ejecutor: GitHub Actions 1000000179
      To https://github.com/alvarorm931/education.git
       ! [remote rejected] sondas -> sondas (push declined due to repository rule violations)
      error: failed to push some refs to 'https://github.com/alvarorm931/education.git'
      error: cannot rebase: You have unstaged changes.
      error: Please commit or stash them.
      ##[error]Process completed with exit code 1.
      Cleaning up orphan processes
      ##[warning]Node.js 20 is deprecated. The following actions target Node.js 20 but are being forced to run on Node.js 24: actions/download-artifact@v4. For more information see: https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/

