# Vigilancia 30/10 18:29 (Madrid)

- Ejecuciones revisadas (últimas 6 h): 223
- Fallos: 2; pendientes: 1; relanzados ahora: 0
- Colas de más de 30 minutos: 2
- Flujos programados parados: ninguno
- Almacén S3: ok
- Programaciones que GitHub no disparó y se lanzaron a mano: ninguna
- Latido (relanza al vigilante cada ~25 min mientras GitHub no dispare programaciones): no hace falta: GitHub ya dispara las programaciones
- Avisos de fuentes: 0

## Motor de datos · 30/10 17:32 · PENDIENTE
https://github.com/alvarorm931/education/actions/runs/41079079352 (intento 2, workflow_dispatch, dfa06eb, pasajero: False)
- motor · pasos: Extraer actos y comprobar huecos · ejecutor: GitHub Actions 1000001163
      DOGC: 41022 actos, 9102 con texto, 2606 con fecha de fin de plazo; {'titulo': 37119, 'plazo_general_v3': 3903}
      BOPB: 8450 actos, 3828 con texto, 698 con fecha de fin de plazo; {'titulo': 6235, 'plazo_general_v3': 2215}
      BOP-ALICANTE: 13122 actos, 3511 con texto, 455 con fecha de fin de plazo; {'titulo': 11618, 'plazo_general_v3': 1504}
      BOP-VALENCIA: 11882 actos, 2740 con texto, 406 con fecha de fin de plazo; {'titulo': 10674, 'plazo_general_v3': 1208}
      BOPT: 2916 actos, 331 con texto, 49 con fecha de fin de plazo; {'titulo': 2718, 'plazo_general_v3': 198}
      BOP-CIUDADREAL: 6002 actos, 2143 con texto, 201 con fecha de fin de plazo; {'titulo': 4906, 'plazo_general_v3': 1096}
      BOP-GRANADA: 5211 actos, 1935 con texto, 267 con fecha de fin de plazo; {'titulo': 4305, 'plazo_general_v3': 906}
      ##[error]Process completed with exit code 1.

## Latido · 30/10 15:28 · superado
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

- En cola 31 min: Boletines autonómicos https://github.com/alvarorm931/education/actions/runs/41094703708
- En cola 103 min: Boletines autonómicos https://github.com/alvarorm931/education/actions/runs/41083823389
