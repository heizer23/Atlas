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

## RunningTracker native API (AtlasPhone sync) - tailnet-only mount

The phone syncs runs to `/api/runningtracker/native/*` over the tailnet. This path is **never** served through the
public Cloudflare route: the shell nginx answers 404 for it (`location ^~ /api/runningtracker/native`), and the
backend rejects any native request that carries a `CF-Connecting-IP` header. Tailscale is the private transport, not
authentication: every native call also needs the device token created by pairing.

Design: `03_Application/RunningTracker/Sprint01_RecordAndSync/10_architecture.json` (D1, E1). The backend container
listens on `127.0.0.1:8029` only.

### Operator steps (human; NOT automated, NOT executed by the implementation)
1. Tailnet admin console: enable **HTTPS certificates** and **MagicDNS**. Note: the machine's MagicDNS name then
   appears in public Certificate Transparency logs (reachability is unchanged). Accept this or stop here.
2. Confirm the host is logged in (`make tailscale-status`; it must show the tailnet, not "Logged out") and port 8443
   is free on the host's tailnet address.
3. Mount only the native path: `make runningtracker-tailnet-up`
   (= `sudo tailscale serve --bg --https=8443 --set-path=/api/runningtracker/native http://127.0.0.1:8029/api/runningtracker/native`;
   syntax checked against `tailscale serve --help` of 1.104.5. `--set-path` mounts the URL path and the mount path is
   not forwarded, so the target carries the same path).
4. Set the non-secret `RUNNINGTRACKER_NATIVE_BASE_URL=https://<host>.<tailnet>.ts.net:8443` in `01_System/config.env`
   and recreate the backend: `make runningtracker-reboot`. The pairing page then encodes it in the QR code.
5. Optional hardening: a tailnet ACL that lets only the phone reach this host on port 8443.

### Verify
- `make runningtracker-tailnet-status` shows only the path-limited mount on 8443 and **Funnel off**. Never run
  `tailscale funnel` for this app.
- From the phone (Tailscale on): `https://<host>.<tailnet>.ts.net:8443/api/runningtracker/native/prepared-runs`
  answers `401` (no token) with a publicly trusted certificate.
- Any other path on that name (e.g. `/api/runningtracker/runs`) answers `404`.
- Outside the tailnet the name is unreachable; through the public hostname
  `/api/runningtracker/native/*` answers `404`.

Remove the mount: `make runningtracker-tailnet-down`.
