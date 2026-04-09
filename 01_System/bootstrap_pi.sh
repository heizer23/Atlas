#!/usr/bin/env bash
set -euo pipefail

# Atlas/System bootstrap for Debian host
# - installs base tools
# - installs/configures Tailscale
# - installs/configures Docker
# - prepares Atlas data root on internal storage at /mnt/data
# - creates required folders with expected ownership

DATA_ROOT="/mnt/data"

echo "==> Updating apt + installing base tools"
sudo apt update
sudo apt install -y \
  sudo \
  git \
  curl \
  ca-certificates \
  util-linux \
  ethtool \
  apt-transport-https \
  gnupg \
  lsb-release \
  make \
  tmux

# ---- Tailscale (System access) ----
echo "==> Ensuring Tailscale is installed"
if ! command -v tailscale >/dev/null 2>&1; then
  echo "Installing Tailscale via official apt repo..."
  sudo mkdir -p /etc/apt/keyrings
  CODENAME="$(. /etc/os-release && echo "${VERSION_CODENAME}")"

  curl -fsSL "https://pkgs.tailscale.com/stable/debian/${CODENAME}.noarmor.gpg" \
    | sudo tee /etc/apt/keyrings/tailscale-archive-keyring.gpg >/dev/null

  echo "deb [signed-by=/etc/apt/keyrings/tailscale-archive-keyring.gpg] https://pkgs.tailscale.com/stable/debian ${CODENAME} main" \
    | sudo tee /etc/apt/sources.list.d/tailscale.list >/dev/null

  sudo apt update
  sudo apt install -y tailscale
else
  echo "Tailscale already installed."
fi

echo "==> Ensuring tailscaled is enabled and running"
sudo systemctl enable --now tailscaled
# ----------------------------------

# ---- Docker ----
echo "==> Ensuring Docker is installed"
if ! command -v docker >/dev/null 2>&1; then
  echo "Installing Docker via official convenience script..."
  curl -fsSL https://get.docker.com | sh
else
  echo "Docker already installed."
fi

echo "==> Ensuring Docker daemon is enabled and running"
sudo systemctl enable --now docker

echo "==> Ensuring user '$USER' is in docker group"
sudo usermod -aG docker "$USER"

echo "==> Ensuring atlas-net Docker bridge network exists"
sudo docker network inspect atlas-net >/dev/null 2>&1 || \
  sudo docker network create atlas-net --driver bridge
# ----------------

# ---- Atlas data root on internal disk ----
echo "==> Ensuring Atlas data root exists at ${DATA_ROOT}"
sudo mkdir -p \
  "${DATA_ROOT}/postgres" \
  "${DATA_ROOT}/weaviate" \
  "${DATA_ROOT}/files" \
  "${DATA_ROOT}/workout-tracker/logs" \
  "${DATA_ROOT}/tasktracker/logs" \
  "${DATA_ROOT}/chronos/workspace" \
  "${DATA_ROOT}/chronos/agents" \
  "${DATA_ROOT}/chronos/config" \
  "${DATA_ROOT}/calendar_connector/logs"

echo "==> Setting ownership and permissions"
# Postgres container runs as uid/gid 999 by default
sudo chown -R 999:999 "${DATA_ROOT}/postgres"
sudo chmod 700 "${DATA_ROOT}/postgres"

# Root-owned shared storage
sudo chown -R root:root \
  "${DATA_ROOT}/weaviate" \
  "${DATA_ROOT}/files" \
  "${DATA_ROOT}/workout-tracker" \
  "${DATA_ROOT}/tasktracker" \
  "${DATA_ROOT}/calendar_connector"

# Chronos container runs as uid/gid 1000
sudo chown -R 1000:1000 "${DATA_ROOT}/chronos"
# ---------------------------------------

# ---- Optional: prevent server sleep/network autosuspend surprises ----
echo "==> Disabling suspend targets for server stability"
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target || true

if [[ -e /sys/class/net/eno1/power/control ]]; then
  echo "==> Setting NIC power control to 'on' for eno1"
  echo on | sudo tee /sys/class/net/eno1/power/control >/dev/null
fi
# ---------------------------------------------------------------------

echo
echo "Bootstrap complete."
echo
echo "Re-login required for docker group membership to apply."
echo
echo "Still manual because secrets/auth are not in git:"
echo "  1. sudo tailscale up"
echo "  2. create 01_System/secrets.env"
echo "  3. copy firebase_service_account.json if Notifications are used"