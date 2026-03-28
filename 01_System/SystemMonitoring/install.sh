#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing Netdata"

TMP_SCRIPT="/tmp/netdata-kickstart.sh"

wget -O "$TMP_SCRIPT" https://get.netdata.cloud/kickstart.sh
chmod +x "$TMP_SCRIPT"

sudo "$TMP_SCRIPT" --stable-channel

echo "==> Netdata installed"