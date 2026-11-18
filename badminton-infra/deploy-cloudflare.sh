#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"

TOKEN="${CLOUDFLARED_TOKEN:-${CLOUDFLARE_TUNNEL_TOKEN:-}}"

SAVED_TOKEN=""
if [ -f .env ]; then
  SAVED_TOKEN="$(sed -n 's/^CLOUDFLARED_TOKEN=//p' .env | tail -n 1)"
fi
TOKEN="${TOKEN:-$SAVED_TOKEN}"

if [ -z "$TOKEN" ]; then
  printf '%s\n' "CLOUDFLARED_TOKEN is required."
  printf '%s\n' "Set it in the remote shell or Codex Cloud secret environment, then rerun:"
  printf '%s\n' "  CLOUDFLARED_TOKEN=... ./deploy-cloudflare.sh"
  exit 1
fi

if [ "$TOKEN" != "$SAVED_TOKEN" ]; then
  umask 077
  ENV_TMP="$(mktemp .env.XXXXXX)"
  trap 'rm -f "$ENV_TMP"' EXIT
  if [ -f .env ]; then
    sed '/^CLOUDFLARED_TOKEN=/d' .env > "$ENV_TMP"
  fi
  printf 'CLOUDFLARED_TOKEN=%s\n' "$TOKEN" >> "$ENV_TMP"
  mv "$ENV_TMP" .env
fi

docker compose -f docker-compose.app.yml -f docker-compose.cloudflare.yml up --build -d --remove-orphans
