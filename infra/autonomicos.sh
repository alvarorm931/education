#!/usr/bin/env bash
# Ejecuta los conectores de boletines autonómicos en orden: lo del día primero, luego la carga histórica
# pendiente y por último los textos pendientes, cada parte con su tiempo máximo. Todo es reanudable.
#
# Uso: infra/autonomicos.sh SALIDA MINUTOS "boja bocm bocyl dogv dog dogc" [ORDEN_DE_GUARDADO]
#   SALIDA    carpeta de datos (en GitHub Actions, la copia de la rama «datos»)
#   MINUTOS   minutos máximos por conector para la carga histórica y, aparte, para los textos
#   ORDEN_DE_GUARDADO  programa que guarda y sube lo hecho, con un mensaje (por defecto, no sube nada)
#
# Sirve igual en GitHub Actions que en el servidor propio.

set -u
S="$1"; M="$2"; CONECTORES="$3"; G="${4:-true}"
Y=$(TZ=Europe/Madrid date +%Y)

ejecutar() {
  echo "+ python -m $*"
  python -m "$@" 2>&1 | tail -n 8 || true
}

for c in $CONECTORES; do
  echo "::group::$c"
  case "$c" in
    boja)
      # Originales: solo huella hasta tener almacén externo (R2); la API permite volver a pedirlos.
      ejecutar motor.autonomicos.boja --desde-anio "$Y" --hasta-anio "$Y" --sin-guardar-original --salida "$S" --max-minutos 8
      "$G" "BOJA: año en curso"
      ejecutar motor.autonomicos.boja --desde-anio 2022 --hasta-anio $((Y-1)) --sin-guardar-original --salida "$S" --max-minutos "$M"
      "$G" "BOJA: carga histórica"
      ;;
    bocm)
      ejecutar motor.autonomicos.bocm --salida "$S"
      ejecutar motor.autonomicos.bocm --desde 2022-01-01 --saltar-existentes --salida "$S" --max-minutos "$M"
      "$G" "BOCM: boletines"
      ejecutar motor.autonomicos.bocm --textos --salida "$S" --max-minutos "$M"
      "$G" "BOCM: textos"
      ;;
    bocyl)
      ejecutar motor.autonomicos.bocyl --salida "$S"
      ejecutar motor.autonomicos.bocyl --desde 2022-01 --saltar-existentes --salida "$S" --max-minutos "$M"
      "$G" "BOCYL: boletines"
      ejecutar motor.autonomicos.bocyl --textos --salida "$S" --max-minutos "$M"
      "$G" "BOCYL: textos"
      ;;
    dogv)
      ejecutar motor.autonomicos.dogv --salida "$S"
      ejecutar motor.autonomicos.dogv --desde 2022-01-01 --saltar-existentes --salida "$S" --max-minutos "$M"
      "$G" "DOGV: boletines"
      ejecutar motor.autonomicos.dogv --textos --salida "$S" --max-minutos "$M"
      "$G" "DOGV: textos"
      ;;
    dog)
      # El número de cada boletín se sigue en orden: primero el año en curso hasta hoy, luego los anteriores.
      ejecutar motor.autonomicos.dog --salida "$S" --max-minutos "$((M * 2))"
      ejecutar motor.autonomicos.dog --desde 2022-01-01 --hasta "$((Y - 1))-12-31" --salida "$S" --max-minutos "$M"
      "$G" "DOG: boletines"
      ejecutar motor.autonomicos.dog --textos --salida "$S" --max-minutos "$M"
      "$G" "DOG: textos"
      ;;
    boa)
      ejecutar motor.autonomicos.boa --salida "$S"
      ejecutar motor.autonomicos.boa --desde 2022-01-01 --saltar-existentes --salida "$S" --max-minutos "$M"
      "$G" "BOA: boletines"
      ;;
    doe)
      ejecutar motor.autonomicos.doe --salida "$S"
      ejecutar motor.autonomicos.doe --desde 2022-01-01 --saltar-existentes --salida "$S" --max-minutos "$M"
      "$G" "DOE: boletines"
      ejecutar motor.autonomicos.doe --textos --salida "$S" --max-minutos "$M"
      "$G" "DOE: textos"
      ;;
    boib)
      ejecutar motor.autonomicos.boib --salida "$S" --max-minutos "$((M * 2))"
      ejecutar motor.autonomicos.boib --desde-anio 2022 --hasta-anio "$((Y - 1))" --salida "$S" --max-minutos "$M"
      "$G" "BOIB: boletines"
      ejecutar motor.autonomicos.boib --textos --salida "$S" --max-minutos "$M"
      "$G" "BOIB: textos"
      ;;
    borm)
      ejecutar motor.autonomicos.borm --salida "$S"
      ejecutar motor.autonomicos.borm --desde 2022-01-01 --saltar-existentes --salida "$S" --max-minutos "$M"
      "$G" "BORM: boletines"
      ejecutar motor.autonomicos.borm --textos --salida "$S" --max-minutos "$M"
      "$G" "BORM: textos"
      ;;
    dogc)
      ejecutar motor.autonomicos.dogc --salida "$S"
      ejecutar motor.autonomicos.dogc --desde 2022-01 --saltar-existentes --salida "$S" --max-minutos "$M"
      "$G" "DOGC: boletines"
      ejecutar motor.autonomicos.dogc --textos --salida "$S" --max-minutos "$M"
      "$G" "DOGC: textos"
      ;;
    *)
      echo "::warning::Conector desconocido: $c"
      ;;
  esac
  echo "::endgroup::"
done
