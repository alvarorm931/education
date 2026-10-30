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
      ejecutar motor.autonomicos.boja --desde-anio "$Y" --hasta-anio "$Y" --sin-guardar-original --salida "$S" --max-minutos 15
      "$G" "BOJA: año en curso"
      ejecutar motor.autonomicos.boja --desde-anio 2022 --hasta-anio $((Y-1)) --sin-guardar-original --salida "$S" --max-minutos "$M"
      "$G" "BOJA: carga histórica"
      ;;
    bocm)
      ejecutar motor.autonomicos.bocm --salida "$S"
      ejecutar motor.autonomicos.bocm --desde 2022-01-01 --saltar-existentes --salida "$S" --max-minutos "$M"
      "$G" "BOCM: boletines"
      ejecutar motor.autonomicos.bocm --huecos --salida "$S" --max-minutos 10
      "$G" "BOCM: números que faltaban"
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
      # robots.txt de caib.es cierra /eboibfront salvo a los buscadores; se lee como boletín oficial (motor/http.py)
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
      # El del día por la portada; los demás por fecha (robots.txt los cierra; se leen como boletín oficial)
      ejecutar motor.autonomicos.docm --salida "$S"
      ejecutar motor.autonomicos.docm --historico --desde 2022-01-01 --saltar-existentes --salida "$S" --max-minutos "$M"
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
    # Solo responden desde España: van en el trabajo del servidor propio (autonomicos.yml, «boletin-espana»)
    bopa)
      ejecutar motor.autonomicos.bopa --salida "$S"
      ejecutar motor.autonomicos.bopa --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOPA: días"
      ejecutar motor.autonomicos.bopa --textos --salida "$S" --max-minutos "$M"
      "$G" "BOPA: textos"
      ;;
    bon)
      ejecutar motor.autonomicos.bon --salida "$S"
      ejecutar motor.autonomicos.bon --desde-anio 2022 --hasta-anio "$((Y - 1))" --salida "$S" --max-minutos "$M"
      "$G" "BON: boletines"
      ejecutar motor.autonomicos.bon --textos --salida "$S" --max-minutos "$M"
      "$G" "BON: textos"
      ;;
    bor)
      ejecutar motor.autonomicos.bor --salida "$S"
      ejecutar motor.autonomicos.bor --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOR: anuncios"
      ejecutar motor.autonomicos.bor --textos --salida "$S" --max-minutos "$M"
      "$G" "BOR: textos"
      ;;
    bocant)
      ejecutar motor.autonomicos.bocant --salida "$S"
      ejecutar motor.autonomicos.bocant --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOC Cantabria: boletines"
      ejecutar motor.autonomicos.bocant --textos --salida "$S" --max-minutos "$M"
      "$G" "BOC Cantabria: textos"
      ;;
    bopavila)
      # Solo el boletín del día, por su canal RSS (sin histórico por ahora)
      ejecutar motor.provinciales.bopavila --salida "$S"
      "$G" "BOP Ávila: boletín del día"
      ;;
    bopbadajoz)
      # Solo el boletín del día, por su canal Atom (sin histórico por ahora)
      ejecutar motor.provinciales.bopbadajoz --salida "$S"
      "$G" "BOP Badajoz: boletín del día"
      ;;
    bopzamora)
      # Los boletines que sigan en la portada (los 8 últimos, unas tres semanas)
      ejecutar motor.provinciales.bopzamora --salida "$S"
      "$G" "BOP Zamora: boletines recientes"
      ;;
    boptoledo)
      # robots.txt cierra todo el servidor: se lee como boletín oficial (motor/http.py)
      ejecutar motor.provinciales.boptoledo --salida "$S"
      ejecutar motor.provinciales.boptoledo --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOP Toledo: días"
      ejecutar motor.provinciales.boptoledo --textos --salida "$S" --max-minutos "$M"
      "$G" "BOP Toledo: textos"
      ;;
    bopburgos)
      ejecutar motor.provinciales.bopburgos --salida "$S"
      ejecutar motor.provinciales.bopburgos --desde-anio 2022 --hasta-anio "$((Y - 1))" --salida "$S" --max-minutos "$M"
      "$G" "BOP Burgos: boletines"
      ;;
    bopalava)
      ejecutar motor.provinciales.bopalava --salida "$S"
      ejecutar motor.provinciales.bopalava --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOTHA: días"
      ;;
    bopb)
      # El del día por el canal de datos abiertos; los anteriores por el listado por días y los textos en PDF (cerrados
      # en robots.txt; se leen como boletín oficial, motor/http.py)
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
      # Los PDF (/bop2/) están cerrados en robots.txt; se leen como boletín oficial (motor/http.py)
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
    bopcordoba)
      ejecutar motor.provinciales.bopcordoba --salida "$S"
      ejecutar motor.provinciales.bopcordoba --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOP Córdoba: días"
      ejecutar motor.provinciales.bopcordoba --textos --salida "$S" --max-minutos "$M"
      "$G" "BOP Córdoba: textos"
      ;;
    boppontevedra)
      # Solo el boletín del día, por la portada: robots.txt prohíbe fichas, descargas y PDF
      ejecutar motor.provinciales.boppontevedra --salida "$S"
      "$G" "BOP Pontevedra: boletín del día"
      ;;
    bopcoruna)
      # Textos: /bopportal/publicado está cerrado en robots.txt; se lee como boletín oficial (motor/http.py)
      ejecutar motor.provinciales.bopcoruna --salida "$S"
      ejecutar motor.provinciales.bopcoruna --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOP A Coruña: días"
      ejecutar motor.provinciales.bopcoruna --textos --salida "$S" --max-minutos "$M"
      "$G" "BOP A Coruña: textos"
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
