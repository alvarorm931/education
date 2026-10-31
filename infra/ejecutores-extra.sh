#!/bin/sh
# Añade ejecutores de GitHub Actions al servidor motor-espana (motor-espana-2, motor-espana-3…), para que el
# servidor haga varios trabajos a la vez. Decisión de Álvaro del 31/10/2026 (claude/incidencias.md, «Capacidad»).
#
# Se ejecuta una vez, como administrador, desde la consola SSH de Lightsail:
#   curl -fsSL -o /tmp/ejecutores.sh https://raw.githubusercontent.com/alvarorm931/education/main/infra/ejecutores-extra.sh
#   sudo sh /tmp/ejecutores.sh 2 3
#
# Pide el código de registro de cada ejecutor. Se saca de GitHub: repositorio > Settings > Actions > Runners >
# New self-hosted runner, y se copia solo lo que va detrás de «--token». Caduca en una hora; si el segundo no
# vale, se recarga esa página y se copia el nuevo. El código no se guarda en ningún fichero ni se muestra.
#
# Cada ejecutor tiene su carpeta (/home/motor/runnerN), su servicio y las mismas etiquetas que el primero
# (espana, motor), con el usuario «motor», sin sudo. Es sh POSIX y se puede repetir: lo ya registrado se salta.

set -eu

REPO_URL="https://github.com/alvarorm931/education"

[ "$(id -u)" = 0 ] || { echo "Ejecútalo con sudo: sudo sh $0 2 3" >&2; exit 1; }
id motor >/dev/null 2>&1 || { echo "No existe el usuario motor: ¿es el servidor motor-espana?" >&2; exit 1; }
[ $# -gt 0 ] || set -- 2 3

for n in "$@"; do
  case "$n" in *[!0-9]*|"") echo "Número de ejecutor no válido: $n" >&2; exit 1 ;; esac
  dir="/home/motor/runner$n"
  nombre="motor-espana-$n"
  if [ -f "$dir/.runner" ]; then
    echo "$nombre ya está registrado: no se toca"
    continue
  fi
  mkdir -p "$dir"
  cd "$dir"
  if [ ! -x ./config.sh ]; then
    VER=$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest | jq -r .tag_name | sed 's/^v//')
    if [ -z "$VER" ] || [ "$VER" = "null" ]; then
      echo "No se pudo saber la última versión del ejecutor de GitHub" >&2
      exit 1
    fi
    case "$(uname -m)" in aarch64) ARQ=arm64 ;; *) ARQ=x64 ;; esac
    curl -fsSL -o runner.tar.gz "https://github.com/actions/runner/releases/download/v${VER}/actions-runner-linux-${ARQ}-${VER}.tar.gz"
    tar xzf runner.tar.gz && rm runner.tar.gz
  fi
  chown -R motor:motor "$dir"

  printf "Código de registro para %s (al pegarlo no se ve; pulsa Intro): " "$nombre"
  stty -echo </dev/tty
  read -r TOKEN </dev/tty || TOKEN=""
  stty echo </dev/tty
  echo
  if [ -z "$TOKEN" ]; then
    echo "Sin código: no se registra $nombre" >&2
    exit 1
  fi
  sudo -u motor ./config.sh --unattended --url "$REPO_URL" --token "$TOKEN" \
    --name "$nombre" --labels espana,motor --work _trabajo --replace
  TOKEN=""
  ./svc.sh install motor || true   # ya instalado: no es un error
  ./svc.sh start
  echo "$nombre registrado y en marcha"
done

echo
echo "Ejecutores de este servidor:"
ls -d /home/motor/runner* 2>/dev/null
echo
free -h
df -h /home | tail -1
