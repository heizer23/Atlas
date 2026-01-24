#!/usr/bin/env bash
set -euo pipefail

# Atlas/System bootstrap for Raspberry Pi host
# Installs docker + basic tools and prepares user permissions.

sudo apt update
sudo apt -y install git curl ca-certificates

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi

# Ensure docker compose is available (comes with modern docker installs)
docker compose version >/dev/null 2>&1 || true

# Add current user to docker group
sudo usermod -aG docker "$USER"

echo ""
echo "Bootstrap complete."
echo "IMPORTANT: Re-login (or run: newgrp docker) so group membership applies."
