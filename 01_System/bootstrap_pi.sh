#!/usr/bin/env bash
set -euo pipefail

# Atlas/System bootstrap for Raspberry Pi host
# Installs docker + basic tools, prepares user permissions,
# and mounts external platform storage at /mnt/data.

sudo apt update
sudo apt -y install git curl ca-certificates util-linux

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi

# Ensure docker compose is available (comes with modern docker installs)
docker compose version >/dev/null 2>&1 || true

# Add current user to docker group (takes effect after re-login)
sudo usermod -aG docker "$USER"

# ---- External data disk mount (Atlas platform storage) ----
# This script assumes the external partition is labeled "data"
DATA_LABEL="data"
MOUNT_POINT="/mnt/data"

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
  sudo mount -a

  # Verify mount
  if ! mountpoint -q "${MOUNT_POINT}"; then
    echo "ERROR: ${MOUNT_POINT} is not mounted after mount -a. Aborting."
    exit 1
  fi

  # Create platform folders
  sudo mkdir -p "${MOUNT_POINT}/postgres" "${MOUNT_POINT}/weaviate" "${MOUNT_POINT}/files"

  # Postgres container runs as uid/gid 999 by default
  sudo chown -R 999:999 "${MOUNT_POINT}/postgres"

  echo "External disk mounted at ${MOUNT_POINT} and folders prepared."
fi
# ----------------------------------------------------------

echo ""
echo "Bootstrap complete."
echo "IMPORTANT: Re-login (or run: newgrp docker) so docker group membership applies."
