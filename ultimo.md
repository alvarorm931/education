# Vigilancia 30/10 17:28 (Madrid)

- Ejecuciones revisadas (últimas 6 h): 247
- Fallos: 1; pendientes: 0; relanzados ahora: 0
- Colas de más de 30 minutos: 2
- Flujos programados parados: ninguno
- Almacén S3: ok
- Programaciones que GitHub no disparó y se lanzaron a mano: ninguna
- Latido (relanza al vigilante cada ~25 min mientras GitHub no dispare programaciones): no hace falta: GitHub ya dispara las programaciones
- Avisos de fuentes: 0

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

- En cola 42 min: Boletines autonómicos https://github.com/alvarorm931/education/actions/runs/41083823389
- En cola 173 min: Estudios por tramos https://github.com/alvarorm931/education/actions/runs/41064537986
