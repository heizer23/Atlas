#!/bin/sh
# Generates /etc/nginx/.htpasswd from env vars at container start, so the
# password lives only in secrets.env (gitignored) — never in a built image
# layer or a versioned file.
set -e

: "${FAMILYATLAS_USER:?FAMILYATLAS_USER must be set}"
: "${FAMILYATLAS_PASSWORD:?FAMILYATLAS_PASSWORD must be set}"

htpasswd -Bbc /etc/nginx/.htpasswd "$FAMILYATLAS_USER" "$FAMILYATLAS_PASSWORD"
