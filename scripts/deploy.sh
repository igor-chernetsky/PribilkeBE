#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/PribilkeBE}"
BRANCH="${BRANCH:-master}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

cd "$APP_DIR"

echo "==> Pulling latest code (${BRANCH})"
git fetch origin "$BRANCH"
git reset --hard "origin/$BRANCH"

echo "==> Building and starting containers"
docker compose -f "$COMPOSE_FILE" up -d --build

echo "==> Pruning old images"
docker image prune -f

echo "==> Health check"
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/health > /dev/null; then
    echo "Deploy successful:"
    curl -s http://127.0.0.1:8000/health
    exit 0
  fi
  sleep 2
done

echo "Health check failed. API logs:"
docker compose -f "$COMPOSE_FILE" logs --tail=80 api
exit 1
