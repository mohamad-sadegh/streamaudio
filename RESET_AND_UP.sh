#!/usr/bin/env sh
# Full reset + rebuild (wipes DB volume — use on first successful bring-up)
set -e
cd "$(dirname "$0")"

echo "==> Stopping stack"
docker compose down

echo "==> Removing Postgres volume (resets DB password/data)"
docker volume rm streamaudio_postgres_data 2>/dev/null || true

echo "==> Rebuilding API with no cache"
docker compose build --no-cache api

echo "==> Starting"
docker compose up -d --build --force-recreate

echo "==> Waiting 5s…"
sleep 5

echo "==> Status"
docker compose ps

echo "==> API logs (last 80 lines)"
docker compose logs --tail=80 api
