# Tailscale (System Access)

## Purpose
Provide private, device-to-device remote access to the Atlas host without public exposure.
Used for admin access (SSH, maintenance), independent of Cloudflare.

## Security Model
- No router port forwarding.
- Access is limited to devices authenticated into the tailnet.
- SSH stays private; harden with key-only auth.

## Install / Bootstrap
Installed via `01_System/bootstrap_pi.sh` using the official apt repo.
Daemon: `tailscaled` (systemd).

## Operations
- Start/auth (one-time): `make tailscale-up`
- Status/IPs: `make tailscale-status`
- Disconnect: `make tailscale-down`

## Addresses
- Pi Tailscale IPv4: `tailscale ip -4` (changes rarely, treat as runtime state)
- Preferred access from dev machine: VSCode Remote-SSH via `linsepi-ts` host entry.

## Scope
- Tailscale = private admin network
- Cloudflared = public entry (only for explicitly exposed endpoints)

## ssh example
Host linsepi-ts
  HostName 100.114.217.123 # example; check `tailscale ip -4`
  User linse