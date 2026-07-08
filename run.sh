#!/usr/bin/env sh
set -eu

RUNNER_DIR="${RUNNER_DIR:-/home/admin/actions-runner}"
SERVICE_FILE="$RUNNER_DIR/.service"
if [ -z "${SERVICE_NAME:-}" ] && [ -f "$SERVICE_FILE" ]; then
  SERVICE_NAME="$(sed -n '1p' "$SERVICE_FILE")"
else
  SERVICE_NAME="${SERVICE_NAME:-actions.runner.ARNAND1988-badminton.pi5.service}"
fi
REPO_DIR="${REPO_DIR:-$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)}"
INFRA_DIR="${INFRA_DIR:-$REPO_DIR/badminton-infra}"

if [ -x "$RUNNER_DIR/svc.sh" ]; then
  printf '%s\n' "Starting actions runner service from $RUNNER_DIR"

  cd "$RUNNER_DIR"
  if [ "$(id -u)" -eq 0 ]; then
    ./svc.sh start
  elif command -v sudo >/dev/null 2>&1; then
    sudo ./svc.sh start
  else
    printf '%s\n' "sudo is required to start $SERVICE_NAME as a non-root user."
    exit 1
  fi

  exit 0
fi

if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files "$SERVICE_NAME" >/dev/null 2>&1; then
  printf '%s\n' "Starting $SERVICE_NAME"

  if [ "$(id -u)" -eq 0 ]; then
    systemctl daemon-reload
    systemctl restart "$SERVICE_NAME"
    systemctl --no-pager --full status "$SERVICE_NAME"
  elif command -v sudo >/dev/null 2>&1; then
    sudo systemctl daemon-reload
    sudo systemctl restart "$SERVICE_NAME"
    sudo systemctl --no-pager --full status "$SERVICE_NAME"
  else
    printf '%s\n' "sudo is required to start $SERVICE_NAME as a non-root user."
    exit 1
  fi

  exit 0
fi

printf '%s\n' "$SERVICE_NAME is not installed; starting the Docker Compose app stack directly."

cd "$INFRA_DIR"
docker compose -f docker-compose.app.yml -f docker-compose.cloudflare.yml up --build -d --remove-orphans
