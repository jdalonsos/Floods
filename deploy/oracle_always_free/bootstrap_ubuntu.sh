#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script with sudo or as root."
  exit 1
fi

DEPLOY_MODE="${1:-direct}"
CALLING_USER="${SUDO_USER:-${USER:-ubuntu}}"

if [[ "${DEPLOY_MODE}" != "direct" && "${DEPLOY_MODE}" != "caddy" ]]; then
  echo "Unsupported mode: ${DEPLOY_MODE}. Use 'direct' or 'caddy'."
  exit 1
fi

apt-get update
apt-get install -y ca-certificates curl git gnupg lsb-release ufw

install -m 0755 -d /etc/apt/keyrings
if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
fi

source /etc/os-release
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable --now docker

if id "${CALLING_USER}" >/dev/null 2>&1; then
  usermod -aG docker "${CALLING_USER}" || true
fi

ufw allow 22/tcp
if [[ "${DEPLOY_MODE}" == "caddy" ]]; then
  ufw allow 80/tcp
  ufw allow 443/tcp
else
  ufw allow 8501/tcp
fi

echo
echo "Docker and firewall rules are ready."
echo "If ${CALLING_USER} was added to the docker group, log out and log back in before running docker without sudo."
