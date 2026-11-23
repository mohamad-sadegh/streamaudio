#!/usr/bin/env bash
# Attach an existing Caddy container to StreamAudio's Docker network so it
# can resolve streamaudio-api / streamaudio-admin / streamaudio-mediamtx.
#
# Usage:
#   ./deploy/wire-existing-caddy.sh [caddy-container] [network]
# Example:
#   ./deploy/wire-existing-caddy.sh server-caddy-1 streamaudio_internal
set -euo pipefail

CADDY_CONTAINER="${1:-server-caddy-1}"
NETWORK="${2:-streamaudio_internal}"

if ! docker inspect "$CADDY_CONTAINER" >/dev/null 2>&1; then
  echo "error: container not found: $CADDY_CONTAINER" >&2
  exit 1
fi

if ! docker network inspect "$NETWORK" >/dev/null 2>&1; then
  echo "error: network not found: $NETWORK (run docker compose up -d first)" >&2
  exit 1
fi

if docker inspect -f '{{json .NetworkSettings.Networks}}' "$CADDY_CONTAINER" | grep -q "\"$NETWORK\""; then
  echo "already on network $NETWORK: $CADDY_CONTAINER"
else
  docker network connect "$NETWORK" "$CADDY_CONTAINER"
  echo "connected $CADDY_CONTAINER → $NETWORK"
fi

echo
echo "Next:"
echo "  1. Point that Caddy's site block at aliases (see deploy/existing-docker-caddy.Caddyfile)"
echo "       reverse_proxy streamaudio-api:3000"
echo "       reverse_proxy streamaudio-mediamtx:8889"
echo "       reverse_proxy streamaudio-admin:80"
echo "  2. Ensure the host Caddyfile path is a FILE (not a missing path / directory)"
echo "  3. docker restart $CADDY_CONTAINER"
echo "  4. ./deploy/verify.sh"
