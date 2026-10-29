#!/bin/bash
# Script de arranque del servidor del motor (AWS Lightsail, región de España, Ubuntu 24.04).
# Se pega en "Script de lanzamiento" al crear la instancia. Lo único que hay que cambiar es el TOKEN,
# que se copia de GitHub: repositorio > Settings > Actions > Runners > New self-hosted runner.
# El token caduca en una hora: crear la instancia justo después de copiarlo.
#
# Qué hace:
#   - actualiza el sistema y activa las actualizaciones de seguridad automáticas;
#   - instala Python, git y utilidades;
#   - crea un usuario sin privilegios "motor";
#   - instala el ejecutor de GitHub Actions como servicio, con las etiquetas "espana" y "motor".
# Desde ese momento los flujos de GitHub con "runs-on: [self-hosted, espana]" se ejecutan en este servidor.

set -euo pipefail

TOKEN="PEGA_AQUI_EL_TOKEN"
REPO_URL="https://github.com/alvarorm931/education"

export DEBIAN_FRONTEND=noninteractive
timedatectl set-timezone Europe/Madrid || true

apt-get update -y
apt-get upgrade -y
apt-get install -y python3 python3-venv python3-pip git curl jq unattended-upgrades
dpkg-reconfigure -f noninteractive unattended-upgrades

# Memoria de intercambio de 2 GB por si un proceso grande se queda sin memoria
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo "/swapfile none swap sw 0 0" >> /etc/fstab
fi

id motor >/dev/null 2>&1 || useradd -m -s /bin/bash motor

cd /home/motor
mkdir -p runner && cd runner
VER=$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest | jq -r .tag_name | sed 's/^v//')
case "$(uname -m)" in aarch64) ARQ=arm64 ;; *) ARQ=x64 ;; esac
curl -fsSL -o runner.tar.gz "https://github.com/actions/runner/releases/download/v${VER}/actions-runner-linux-${ARQ}-${VER}.tar.gz"
tar xzf runner.tar.gz && rm runner.tar.gz
chown -R motor:motor /home/motor
./bin/installdependencies.sh

sudo -u motor ./config.sh --unattended --url "$REPO_URL" --token "$TOKEN" \
  --name motor-espana --labels espana,motor --work _trabajo --replace
./svc.sh install motor
./svc.sh start

echo "Servidor listo: ejecutor de GitHub instalado como servicio" > /home/motor/LISTO.txt
