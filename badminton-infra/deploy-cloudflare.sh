#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"

TOKEN="${CLOUDFLARED_TOKEN:-${CLOUDFLARE_TUNNEL_TOKEN:-}}"

if [ -z "$TOKEN" ] && [ -f .env ]; then
  TOKEN="$(sed -n 's/^CLOUDFLARED_TOKEN=//p' .env | tail -n 1)"
fi

if [ -z "$TOKEN" ]; then
  printf '%s\n' "CLOUDFLARED_TOKEN is required."
  printf '%s\n' "Set it in the remote shell or Codex Cloud secret environment, then rerun:"
  printf '%s\n' "  CLOUDFLARED_TOKEN=... ./deploy-cloudflare.sh"
  exit 1
fi

umask 077
printf 'CLOUDFLARED_TOKEN=%s\n' "$TOKEN" > .env

docker compose -f docker-compose.app.yml -f docker-compose.cloudflare.yml up --build -d --remove-orphans
