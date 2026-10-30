# Vigilancia 30/10 16:13 (Madrid)

- Ejecuciones revisadas (últimas 6 h): 221
- Fallos: 2; pendientes: 0; relanzados ahora: 1
- Colas de más de 30 minutos: 6
- Flujos programados parados: ninguno
- Almacén S3: ok
- Programaciones que GitHub no disparó y se lanzaron a mano: ninguna
- Latido (relanza al vigilante cada ~25 min mientras GitHub no dispare programaciones): en marcha
- Avisos de fuentes: 0

## Motor de datos · 30/10 16:11 · relanzado
https://github.com/alvarorm931/education/actions/runs/41074279763 (intento 1, workflow_dispatch, 17caa6c, pasajero: True)
- motor · pasos: BOE, textos de anuncios de oposiciones · ejecutor: GitHub Actions 1000001013
       ! [rejected]              datos -> datos (fetch first)
      error: failed to push some refs to 'https://github.com/alvarorm931/education'
      hint: Updates were rejected because the remote contains work that you do not
      hint: have locally. This is usually caused by another repository pushing to
      hint: the same ref. If you want to integrate the remote changes, use
      hint: 'git pull' before pushing again.
      hint: See the 'Note about fast-forwards' in 'git push --help' for details.
      ##[error]Process completed with exit code 1.

## Latido · 30/10 15:28 · otra ejecución en curso: https://github.com/alvarorm931/education/actions/runs/41074901194
https://github.com/alvarorm931/education/actions/runs/41068408931 (intento 1, workflow_dispatch, b727abc, pasajero: False)
- latido · pasos: Lanzar al vigilante y el siguiente latido · ejecutor: GitHub Actions 1000000965
      [36;1mn=$(gh api "repos/$GITHUB_REPOSITORY/actions/workflows/vigilante.yml/runs?event=schedule&per_page=1&created=>=$desde" --jq .total_count || echo 0)[0m
      [36;1mif [ "${n:-0}" -gt 0 ]; then[0m
      [36;1m  echo "::notice title=Latido::GitHub ya dispara las programaciones; el latido se detiene."[0m
      [36;1m  exit 0[0m
      [36;1mfi[0m
      [36;1mgh workflow run latido.yml -R "$GITHUB_REPOSITORY" --ref main[0m
      could not create workflow dispatch event: HTTP 500 (https://api.github.com/repos/alvarorm931/education/actions/workflows/401287485/dispatches)
      ##[error]Process completed with exit code 1.

- En cola 98 min: Estudios por tramos https://github.com/alvarorm931/education/actions/runs/41064537986
- En cola 111 min: Boletines autonómicos https://github.com/alvarorm931/education/actions/runs/41062712067
- En cola 120 min: Sonda de fuentes https://github.com/alvarorm931/education/actions/runs/41061393230
- En cola 121 min: Boletines autonómicos https://github.com/alvarorm931/education/actions/runs/41061253358
- En cola 123 min: Grados por tramos https://github.com/alvarorm931/education/actions/runs/41061047455
- En cola 124 min: Boletines autonómicos https://github.com/alvarorm931/education/actions/runs/41060907312
