# Vigilancia 30/10 17:01 (Madrid)

- Ejecuciones revisadas (últimas 6 h): 245
- Fallos: 2; pendientes: 0; relanzados ahora: 1
- Colas de más de 30 minutos: 2
- Flujos programados parados: ninguno
- Almacén S3: ok
- Programaciones que GitHub no disparó y se lanzaron a mano: ninguna
- Latido (relanza al vigilante cada ~25 min mientras GitHub no dispare programaciones): no hace falta: GitHub ya dispara las programaciones
- Avisos de fuentes: 0

## Motor de datos · 30/10 17:01 · relanzado
https://github.com/alvarorm931/education/actions/runs/41079079352 (intento 1, workflow_dispatch, dfa06eb, pasajero: True)
- motor · pasos: Avisar si hay huecos o errores · ejecutor: GitHub Actions 1000001125
      [36;1mh = json.load(open("salida/datos/boe/huecos.json"))[0m
      [36;1mproblemas = {k: v for k, v in h.items() if k in ("numeros_de_diario_que_faltan", "dias_sin_procesar", "dias_con_error") and v}[0m
      [36;1mif problemas:[0m
      [36;1m    print("::error::Huecos en el BOE: " + json.dumps(problemas, ensure_ascii=False)[:500])[0m
      [36;1m    sys.exit(1)[0m
      [36;1mprint("Sin huecos en el BOE. Anuncios sin texto:", h.get("anuncios_sin_texto"))[0m
      [36;1mEOF[0m
      ##[error]Huecos en el BOE: {"dias_con_error": ["2026-10-29", "2026-10-30"]}

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

- En cola 146 min: Estudios por tramos https://github.com/alvarorm931/education/actions/runs/41064537986
- En cola 159 min: Boletines autonómicos https://github.com/alvarorm931/education/actions/runs/41062712067
