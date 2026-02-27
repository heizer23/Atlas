#!/usr/bin/env bash
set -euo pipefail

# Atlas/System bootstrap for Raspberry Pi host
# Installs docker + basic tools, prepares user permissions,
# mounts external platform storage at /mnt/data,
# and installs Tailscale as a System-layer access component.

echo "==> Updating apt + installing base tools"
sudo apt update
sudo apt -y install git curl ca-certificates util-linux

# ---- Tailscale (System access) ----
echo "==> Ensuring Tailscale is installed"
if ! command -v tailscale >/dev/null 2>&1; then
  echo "Installing Tailscale via official apt repo..."

  sudo mkdir -p /etc/apt/keyrings
  CODENAME="$(. /etc/os-release && echo "${VERSION_CODENAME}")"

  # Add Tailscale signing key (noarmor) + apt repo
  curl -fsSL "https://pkgs.tailscale.com/stable/debian/${CODENAME}.noarmor.gpg" \
    | sudo tee /etc/apt/keyrings/tailscale-archive-keyring.gpg >/dev/null

  echo "deb [signed-by=/etc/apt/keyrings/tailscale-archive-keyring.gpg] https://pkgs.tailscale.com/stable/debian ${CODENAME} main" \
    | sudo tee /etc/apt/sources.list.d/tailscale.list >/dev/null

  sudo apt update
  sudo apt install -y tailscale
else
  echo "Tailscale already installed."
fi

# Ensure daemon is enabled/running (idempotent)
echo "==> Ensuring tailscaled is enabled and running"
sudo systemctl enable --now tailscaled
# ----------------------------------

# ---- Docker ----
echo "==> Ensuring Docker is installed"
if ! command -v docker >/dev/null 2>&1; then
  # Note: remote installer; kept for now because this is your current pattern.
  # Later we can switch to the official Docker apt repo for a fully deterministic bootstrap.
  curl -fsSL https://get.docker.com | sh
else
  echo "Docker already installed."
fi

# Ensure docker compose is available (comes with modern docker installs)
docker compose version >/dev/null 2>&1 || true

# Add current user to docker group (safe to run repeatedly; takes effect after re-login)
echo "==> Ensuring user '$USER' is in docker group"
sudo usermod -aG docker "$USER"
# --------------

# ---- External data disk mount (Atlas platform storage) ----
# This script assumes the external partition is labeled "data"
DATA_LABEL="data"
MOUNT_POINT="/mnt/data"

echo "==> Checking for external disk labeled '${DATA_LABEL}'"
# Resolve device by filesystem label (preferred for stability)
DATA_DEV="$(blkid -L "${DATA_LABEL}" || true)"

if [[ -z "${DATA_DEV}" ]]; then
  echo "WARN: No block device found with label '${DATA_LABEL}'. Skipping external disk mount."
else
  echo "External data disk: ${DATA_DEV} (label=${DATA_LABEL})"

  sudo mkdir -p "${MOUNT_POINT}"

  # Get UUID + FSTYPE for fstab (UUID is more robust than /dev/sdX)
  DATA_UUID="$(blkid -s UUID -o value "${DATA_DEV}")"
  DATA_FSTYPE="$(blkid -s TYPE -o value "${DATA_DEV}")"

  if [[ -z "${DATA_UUID}" || -z "${DATA_FSTYPE}" ]]; then
    echo "ERROR: Could not read UUID/FSTYPE for ${DATA_DEV}. Aborting."
    exit 1
  fi

  # Add fstab entry if missing (idempotent)
  FSTAB_LINE="UUID=${DATA_UUID}  ${MOUNT_POINT}  ${DATA_FSTYPE}  defaults,nofail  0  2"
  if ! grep -qF "UUID=${DATA_UUID}" /etc/fstab; then
    echo "Adding fstab entry for external data disk..."
    sudo cp /etc/fstab "/etc/fstab.bak.$(date +%Y%m%d_%H%M%S)"
    echo "${FSTAB_LINE}" | sudo tee -a /etc/fstab >/dev/null
  else
    echo "fstab already contains entry for UUID=${DATA_UUID}"
  fi

  # Mount (safe even if already mounted)
  echo "==> Mounting all filesystems from fstab"
  sudo mount -a

  # Verify mount
  if ! mountpoint -q "${MOUNT_POINT}"; then
    echo "ERROR: ${MOUNT_POINT} is not mounted after mount -a. Aborting."
    exit 1
  fi

  # Create platform folders
  echo "==> Preparing platform folders on ${MOUNT_POINT}"
  sudo mkdir -p "${MOUNT_POINT}/postgres" "${MOUNT_POINT}/weaviate" "${MOUNT_POINT}/files"

  # Postgres container runs as uid/gid 999 by default
  sudo chown -R 999:999 "${MOUNT_POINT}/postgres"
  sudo chmod 700 "${MOUNT_POINT}/postgres"

  # Keep other folders owned by root (or change to your user if you want)
  sudo chown -R root:root "${MOUNT_POINT}/weaviate" "${MOUNT_POINT}/files"

  echo "External disk mounted at ${MOUNT_POINT} and folders prepared."
fi
# ----------------------------------------------------------

echo ""
echo "Bootstrap complete."
echo "IMPORTANT: Re-login (or run: newgrp docker) so docker group membership applies."
echo ""
echo "NEXT (one-time): run 'sudo tailscale up' to authenticate this Pi into your tailnet."