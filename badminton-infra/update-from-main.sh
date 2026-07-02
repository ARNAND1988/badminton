#!/usr/bin/env sh
set -eu

REPO_DIR="${REPO_DIR:-/home/admin/git-repo/badminton}"
BRANCH="${BRANCH:-main}"
INFRA_DIR="$REPO_DIR/badminton-infra"
LOCK_DIR="${LOCK_DIR:-/tmp/badminton-deploy.lock}"
FORCE_DEPLOY="${FORCE_DEPLOY:-0}"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  printf '%s\n' "Another deployment is already running."
  exit 0
fi
trap 'rmdir "$LOCK_DIR"' EXIT

cd "$REPO_DIR"

git fetch origin "$BRANCH"

LOCAL_REV="$(git rev-parse HEAD)"
REMOTE_REV="$(git rev-parse "origin/$BRANCH")"

if [ "$LOCAL_REV" = "$REMOTE_REV" ] && [ "$FORCE_DEPLOY" != "1" ]; then
  printf '%s\n' "Already up to date at $LOCAL_REV"
  exit 0
fi

if [ "$LOCAL_REV" = "$REMOTE_REV" ]; then
  printf '%s\n' "Already up to date at $LOCAL_REV; forcing deploy."
else
  printf '%s\n' "Updating $BRANCH from $LOCAL_REV to $REMOTE_REV"
  git pull --ff-only origin "$BRANCH"
fi

cd "$INFRA_DIR"
./deploy-cloudflare.sh
