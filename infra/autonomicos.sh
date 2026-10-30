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
      # El boletín del día por su canal RSS; el histórico, por el canal propio de cada día
      ejecutar motor.provinciales.bopavila --salida "$S"
      ejecutar motor.provinciales.bopavila --historico --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOP Ávila: boletín del día"
      # Textos: el PDF de cada anuncio de empleo (motor/provinciales/textos.py)
      ejecutar motor.provinciales.textos bopavila --salida "$S" --max-minutos "$M"
      "$G" "BOP Ávila: textos"
      ;;
    bopbadajoz)
      # El boletín del día por su canal Atom; el histórico, por el sumario de cada fecha
      ejecutar motor.provinciales.bopbadajoz --salida "$S"
      ejecutar motor.provinciales.bopbadajoz --historico --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOP Badajoz: boletín del día"
      ejecutar motor.provinciales.bopbadajoz --textos --salida "$S" --max-minutos "$M"
      "$G" "BOP Badajoz: textos"
      ;;
    bopzamora)
      # Los boletines que sigan en la portada (los 8 últimos, unas tres semanas)
      ejecutar motor.provinciales.bopzamora --salida "$S"
      "$G" "BOP Zamora: boletines recientes"
      # Histórico por la lista completa («BOP Total», 20 boletines por página) hasta 2022
      ejecutar motor.provinciales.bopzamora --historico --salida "$S" --max-minutos "$M"
      "$G" "BOP Zamora: histórico"
      # Textos: el PDF de cada anuncio de empleo (motor/provinciales/textos.py)
      ejecutar motor.provinciales.textos bopzamora --salida "$S" --max-minutos "$M"
      "$G" "BOP Zamora: textos"
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
      # Textos: el PDF de cada anuncio de empleo (motor/provinciales/textos.py)
      ejecutar motor.provinciales.textos bopburgos --salida "$S" --max-minutos "$M"
      "$G" "BOP Burgos: textos"
      ;;
    bopalava)
      ejecutar motor.provinciales.bopalava --salida "$S"
      ejecutar motor.provinciales.bopalava --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOTHA: días"
      # Textos: el PDF de cada anuncio de empleo (motor/provinciales/textos.py)
      ejecutar motor.provinciales.textos bopalava --salida "$S" --max-minutos "$M"
      "$G" "BOTHA: textos"
      ;;
    bopsalamanca)
      # Solo el boletín del día, desde la portada
      ejecutar motor.provinciales.bopsalamanca --salida "$S"
      "$G" "BOP Salamanca: boletín del día"
      # Días anteriores por la dirección del boletín de cada día (calendario de la portada)
      ejecutar motor.provinciales.bopsalamanca --historico --salida "$S" --max-minutos "$M"
      "$G" "BOP Salamanca: histórico"
      # Textos: el PDF de cada anuncio de empleo (motor/provinciales/textos.py)
      ejecutar motor.provinciales.textos bopsalamanca --salida "$S" --max-minutos "$M"
      "$G" "BOP Salamanca: textos"
      ;;
    bopalbacete)
      # El boletín del día, desde la portada
      ejecutar motor.provinciales.bopalbacete --salida "$S"
      "$G" "BOP Albacete: boletín del día"
      # Días anteriores por los servicios del calendario de la portada, mes a mes hasta 2022
      ejecutar motor.provinciales.bopalbacete --historico --salida "$S" --max-minutos "$M"
      "$G" "BOP Albacete: histórico"
      # Textos: el anuncio cortado del PDF del boletín completo (enlace leído del sumario original en el almacén)
      ejecutar motor.provinciales.bopalbacete --reparar-boletin --salida "$S"
      ejecutar motor.provinciales.textos bopalbacete --salida "$S" --max-minutos "$M"
      "$G" "BOP Albacete: textos"
      ;;
    bopjaen)
      # El boletín del día, desde la portada
      ejecutar motor.provinciales.bopjaen --salida "$S"
      "$G" "BOP Jaén: boletín del día"
      # Días anteriores por la dirección del boletín de cada día (calendario de la portada)
      ejecutar motor.provinciales.bopjaen --historico --salida "$S" --max-minutos "$M"
      "$G" "BOP Jaén: histórico"
      # Textos: el PDF de cada anuncio de empleo (motor/provinciales/textos.py)
      ejecutar motor.provinciales.textos bopjaen --salida "$S" --max-minutos "$M"
      "$G" "BOP Jaén: textos"
      ;;
    bopzaragoza)
      # El boletín del día, desde la portada
      ejecutar motor.provinciales.bopzaragoza --salida "$S"
      "$G" "BOP Zaragoza: boletín del día"
      # Días anteriores por el calendario de la portada (formulario de portada.do), mes a mes hasta 2022
      ejecutar motor.provinciales.bopzaragoza --historico --salida "$S" --max-minutos "$M"
      "$G" "BOP Zaragoza: histórico"
      # Texto de cada anuncio de empleo (obtenerContenidoEdicto.do); de las listas, solo recuento y citas
      ejecutar motor.provinciales.bopzaragoza --textos --salida "$S" --max-minutos "$M"
      "$G" "BOP Zaragoza: textos"
      ;;
    bopgipuzkoa)
      # Desde el servidor de España: a GitHub deja de responderle tras unos cientos de peticiones
      ejecutar motor.provinciales.bopgipuzkoa --salida "$S"
      ejecutar motor.provinciales.bopgipuzkoa --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOG Gipuzkoa: días"
      ejecutar motor.provinciales.bopgipuzkoa --textos --salida "$S" --max-minutos "$M"
      "$G" "BOG Gipuzkoa: textos"
      ;;
    bopbizkaia)
      # Del último boletín hacia atrás: lo ya leído no se vuelve a pedir
      ejecutar motor.provinciales.bopbizkaia --salida "$S"
      ejecutar motor.provinciales.bopbizkaia --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOB Bizkaia: boletines"
      ejecutar motor.provinciales.bopbizkaia --textos --salida "$S" --max-minutos "$M"
      "$G" "BOB Bizkaia: textos"
      ;;
    boplugo)
      # Canal RSS para el boletín del día; el histórico, por la lista paginada y la página de cada boletín
      ejecutar motor.provinciales.boplugo --salida "$S"
      ejecutar motor.provinciales.boplugo --historico --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOP Lugo: boletines"
      # Textos: el anuncio cortado del PDF del boletín entero (motor/provinciales/textos.py)
      ejecutar motor.provinciales.textos boplugo --salida "$S" --max-minutos "$M"
      "$G" "BOP Lugo: textos"
      ;;
    bophuelva)
      # JSON del día desde s2.diphuelva.es (robots.txt lo cierra: boletín oficial, motor/http.py), desde el servidor de España: a GitHub deja de responderle. Este sistema empieza el 20/06/2023
      ejecutar motor.provinciales.bophuelva --salida "$S"
      ejecutar motor.provinciales.bophuelva --desde 2023-06-20 --salida "$S" --max-minutos "$M"
      "$G" "BOP Huelva: días"
      ejecutar motor.provinciales.bophuelva --textos --salida "$S" --max-minutos "$M"
      "$G" "BOP Huelva: textos"
      ;;
    boplaspalmas)
      # Sumario por fecha en boplaspalmas.net (robots.txt lo cierra: boletín oficial, motor/http.py)
      ejecutar motor.provinciales.boplaspalmas --salida "$S"
      ejecutar motor.provinciales.boplaspalmas --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOP Las Palmas: días"
      # Textos: el anuncio cortado del PDF del boletín entero (motor/provinciales/textos.py)
      ejecutar motor.provinciales.textos boplaspalmas --salida "$S" --max-minutos "$M"
      "$G" "BOP Las Palmas: textos"
      ;;
    bopvalladolid)
      # Desde GitHub no responde: servidor de España. Calendario por mes y boletín por fecha
      ejecutar motor.provinciales.bopvalladolid --salida "$S"
      ejecutar motor.provinciales.bopvalladolid --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOP Valladolid: días"
      ejecutar motor.provinciales.bopvalladolid --textos --salida "$S" --max-minutos "$M"
      "$G" "BOP Valladolid: textos"
      ;;
    bopcaceres)
      # Servicios JSON del portal: calendario por mes y anuncios con su texto por boletín
      ejecutar motor.provinciales.bopcaceres --salida "$S"
      ejecutar motor.provinciales.bopcaceres --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOP Cáceres: boletines"
      ;;
    bopguadalajara)
      # Lista por fecha (categoría General) y ficha del boletín con su sumario
      ejecutar motor.provinciales.bopguadalajara --salida "$S"
      ejecutar motor.provinciales.bopguadalajara --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOP Guadalajara: días"
      ejecutar motor.provinciales.bopguadalajara --textos --salida "$S" --max-minutos "$M"
      "$G" "BOP Guadalajara: textos"
      ;;
    bopgirona)
      # Número a número (robots.txt cierra /bop: boletín oficial, motor/http.py)
      ejecutar motor.provinciales.bopgirona --salida "$S"
      ejecutar motor.provinciales.bopgirona --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOP Girona: boletines"
      ejecutar motor.provinciales.bopgirona --textos --salida "$S" --max-minutos "$M"
      "$G" "BOP Girona: textos"
      ;;
    bopourense)
      # API del portal: boletín por fecha y el texto de cada edicto de empleo (la entidad va en el texto)
      ejecutar motor.provinciales.bopourense --salida "$S"
      ejecutar motor.provinciales.bopourense --reparar --salida "$S" --max-minutos "$M"
      ejecutar motor.provinciales.bopourense --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOP Ourense: días"
      ;;
    boplleida)
      # Misma plataforma que Girona (mostrabop.py). Solo responde desde España
      ejecutar motor.provinciales.boplleida --salida "$S"
      ejecutar motor.provinciales.boplleida --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOP Lleida: boletines"
      ejecutar motor.provinciales.boplleida --textos --salida "$S" --max-minutos "$M"
      "$G" "BOP Lleida: textos"
      ;;
    boppalencia)
      # Sumario de la primera página del PDF de cada boletín (robots.txt cierra PDF y paginación: boletín oficial, motor/http.py)
      ejecutar motor.provinciales.boppalencia --salida "$S"
      ejecutar motor.provinciales.boppalencia --paginas 70 --salida "$S" --max-minutos "$M"
      "$G" "BOP Palencia: boletines"
      # Textos: el anuncio cortado del PDF del boletín entero (motor/provinciales/textos.py)
      ejecutar motor.provinciales.textos boppalencia --salida "$S" --max-minutos "$M"
      "$G" "BOP Palencia: textos"
      ;;
    bopsoria)
      # Boletines del día y sumario de su ficha, con un PDF por anuncio
      ejecutar motor.provinciales.bopsoria --salida "$S"
      ejecutar motor.provinciales.bopsoria --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOP Soria: días"
      ejecutar motor.provinciales.bopsoria --textos --salida "$S" --max-minutos "$M"
      "$G" "BOP Soria: textos"
      ;;
    bopteruel)
      # Solo el boletín del día, por la portada (lo anterior solo está en PDF). Solo responde desde España
      ejecutar motor.provinciales.bopteruel --salida "$S"
      "$G" "BOP Teruel: boletín del día"
      ;;
    bopcastellon)
      # Último boletín y los del carrusel del buscador (unos dos meses y medio, portal JSF con sesión)
      ejecutar motor.provinciales.bopcastellon --salida "$S" --max-minutos "$M"
      "$G" "BOP Castellón: boletines"
      ejecutar motor.provinciales.bopcastellon --textos --salida "$S" --max-minutos "$M"
      "$G" "BOP Castellón: textos"
      # Boletines anteriores al carrusel (motor/provinciales/bopcastellon_antiguos.py): parado el 30/10/2026 hasta
      # leer bien el formato de 2026 (los asuntos salían mal partidos); el de 2022 sí se lee
      ;;
    bopleon)
      # Ficha del boletín de cada día y su sumario en PDF (portal nuevo, desde el 17/02/2025)
      ejecutar motor.provinciales.bopleon --salida "$S"
      ejecutar motor.provinciales.bopleon --desde 2025-02-17 --salida "$S" --max-minutos "$M"
      "$G" "BOP León: boletines"
      # Boletines anteriores al 17/02/2025: lista por fechas y PDF entero (sumario y textos del mismo PDF)
      ejecutar motor.provinciales.bopleon --reprocesar-antiguos --salida "$S"
      ejecutar motor.provinciales.bopleon --antiguos --salida "$S" --max-minutos "$M"
      "$G" "BOP León: boletines anteriores"
      ejecutar motor.provinciales.bopleon --textos --salida "$S" --max-minutos "$M"
      "$G" "BOP León: textos"
      ;;
    bocce)
      # PDF de cada boletín: sumario y textos del propio PDF (solo responde desde España)
      ejecutar motor.autonomicos.bocce --salida "$S"
      ejecutar motor.autonomicos.bocce --desde 2022-01 --salida "$S" --max-minutos "$M"
      "$G" "BOCCE: boletines y textos"
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
      # Granada antes de julio de 2024: «boletines anteriores» por año y mes, PDF entero (sumario y textos)
      if [ "$c" = bopgranada ]; then
        ejecutar motor.provinciales.bopgranada_antiguos --reprocesar --salida "$S"
        ejecutar motor.provinciales.bopgranada_antiguos --salida "$S" --max-minutos "$M"
        "$G" "$c: boletines anteriores"
      fi
      ;;
    bopcordoba)
      ejecutar motor.provinciales.bopcordoba --salida "$S"
      ejecutar motor.provinciales.bopcordoba --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOP Córdoba: días"
      ejecutar motor.provinciales.bopcordoba --textos --salida "$S" --max-minutos "$M"
      "$G" "BOP Córdoba: textos"
      ;;
    boppontevedra)
      # El boletín del día, por la portada
      ejecutar motor.provinciales.boppontevedra --salida "$S"
      "$G" "BOP Pontevedra: boletín del día"
      # Histórico por la ficha de cada día (/detalle/, cerrada en robots.txt; se lee como boletín oficial)
      ejecutar motor.provinciales.boppontevedra --historico --salida "$S" --max-minutos "$M"
      "$G" "BOPPO: histórico"
      ejecutar motor.provinciales.boppontevedra --textos --salida "$S" --max-minutos "$M"
      "$G" "BOPPO: textos"
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
      # Sin PDF por anuncio: los textos se cortan del PDF del boletín completo
      ejecutar motor.provinciales.boptenerife --salida "$S"
      ejecutar motor.provinciales.boptenerife --desde 2022-01-01 --salida "$S" --max-minutos "$M"
      "$G" "BOP Tenerife: días"
      # Textos: el anuncio cortado del PDF del boletín entero (motor/provinciales/textos.py)
      ejecutar motor.provinciales.textos boptenerife --salida "$S" --max-minutos "$M"
      "$G" "BOP Tenerife: textos"
      ;;
    *)
      echo "::warning::Conector desconocido: $c"
      ;;
  esac
  echo "::endgroup::"
done
