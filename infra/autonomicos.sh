#!/usr/bin/env bash
# Ejecuta los conectores de boletines autonómicos (y provinciales: bopb) en orden: lo del día primero, luego la carga histórica
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
    boc)
      ejecutar motor.autonomicos.boc --salida "$S"
      ejecutar motor.autonomicos.boc --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOC: boletines"
      ejecutar motor.autonomicos.boc --textos --salida "$S" --max-minutos "$M"
      "$G" "BOC: textos"
      ;;
    bopv)
      ejecutar motor.autonomicos.bopv --salida "$S"
      ejecutar motor.autonomicos.bopv --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOPV: boletines"
      ejecutar motor.autonomicos.bopv --textos --salida "$S" --max-minutos "$M"
      "$G" "BOPV: textos"
      ;;
    docm)
      ejecutar motor.autonomicos.docm --salida "$S"
      ejecutar motor.autonomicos.docm --desde 2022-01-01 --saltar-existentes --salida "$S" --max-minutos "$M"
      "$G" "DOCM: boletines"
      ejecutar motor.autonomicos.docm --textos --salida "$S" --max-minutos "$M"
      "$G" "DOCM: textos"
      ;;
    bome)
      ejecutar motor.autonomicos.bome --salida "$S"
      ejecutar motor.autonomicos.bome --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOME: boletines"
      ejecutar motor.autonomicos.bome --textos --salida "$S" --max-minutos "$M"
      "$G" "BOME: textos"
      ;;
    dogc)
      ejecutar motor.autonomicos.dogc --salida "$S"
      ejecutar motor.autonomicos.dogc --desde 2022-01 --saltar-existentes --salida "$S" --max-minutos "$M"
      "$G" "DOGC: boletines"
      ejecutar motor.autonomicos.dogc --textos --salida "$S" --max-minutos "$M"
      "$G" "DOGC: textos"
      ;;
    bopb)
      # Boletín provincial de Barcelona: se recorre del día más reciente hacia atrás
      ejecutar motor.provinciales.bopb --salida "$S"
      ejecutar motor.provinciales.bopb --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOPB: días"
      ejecutar motor.provinciales.bopb --textos --salida "$S" --max-minutos "$M"
      "$G" "BOPB: textos"
      ;;
    bopalicante)
      ejecutar motor.provinciales.bopalicante --salida "$S"
      ejecutar motor.provinciales.bopalicante --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOP Alicante: días"
      ejecutar motor.provinciales.bopalicante --textos --salida "$S" --max-minutos "$M"
      "$G" "BOP Alicante: textos"
      ;;
    bopvalencia)
      ejecutar motor.provinciales.bopvalencia --salida "$S"
      ejecutar motor.provinciales.bopvalencia --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOP Valencia: días"
      ejecutar motor.provinciales.bopvalencia --textos --salida "$S" --max-minutos "$M"
      "$G" "BOP Valencia: textos"
      ;;
    bopt)
      ejecutar motor.provinciales.bopt --salida "$S"
      ejecutar motor.provinciales.bopt --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOPT: días"
      ejecutar motor.provinciales.bopt --textos --salida "$S" --max-minutos "$M"
      "$G" "BOPT: textos"
      ;;
    bopciudadreal)
      ejecutar motor.provinciales.bopciudadreal --salida "$S"
      ejecutar motor.provinciales.bopciudadreal --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOP Ciudad Real: días"
      ejecutar motor.provinciales.bopciudadreal --textos --salida "$S" --max-minutos "$M"
      "$G" "BOP Ciudad Real: textos"
      ;;
    bopgranada|bopsevilla|bophuesca)
      ejecutar motor.provinciales.$c --salida "$S"
      # Cada boletín empieza donde empieza su portal (Granada, julio de 2024; Sevilla tiene 2023 y antes)
      ejecutar motor.provinciales.$c --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "$c: días"
      ejecutar motor.provinciales.$c --textos --salida "$S" --max-minutos "$M"
      "$G" "$c: textos"
      ;;
    boptenerife)
      # Sin textos por anuncio: el texto solo está en el PDF del boletín completo
      ejecutar motor.provinciales.boptenerife --salida "$S"
      ejecutar motor.provinciales.boptenerife --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOP Tenerife: días"
      ;;
    *)
      echo "::warning::Conector desconocido: $c"
      ;;
  esac
  echo "::endgroup::"
done
