#!/usr/bin/env bash
# Post-deploy checks for StreamAudio behind an existing or compose Caddy.
set -euo pipefail

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
DOMAIN="${DOMAIN:-st.fifa2012.ir}"

ok=0
fail=0

pass() { echo "OK   $1"; ok=$((ok + 1)); }
fail_msg() { echo "FAIL $1"; fail=$((fail + 1)); }

echo "== localhost (compose ports) =="
if curl -fsS http://127.0.0.1:3000/api/health 2>/dev/null | grep -q '"ok":true'; then
  pass "api :3000/api/health"
else
  fail_msg "api :3000/api/health"
fi

if curl -fsS -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/ 2>/dev/null | grep -q '^200$'; then
  pass "admin :8080"
else
  fail_msg "admin :8080"
fi

if (echo >/dev/tcp/127.0.0.1/8889) >/dev/null 2>&1; then
  pass "mediamtx :8889 port open"
else
  fail_msg "mediamtx :8889 not reachable"
fi

echo
echo "== public https://$DOMAIN =="
code=$(curl -sS -o /tmp/sa-health.json -w '%{http_code}' "https://$DOMAIN/api/health" || echo "000")
if [[ "$code" == "200" ]] && grep -q '"ok":true' /tmp/sa-health.json 2>/dev/null; then
  pass "https://$DOMAIN/api/health → 200"
else
  fail_msg "https://$DOMAIN/api/health → $code (proxy must hit streamaudio-api:3000 or 127.0.0.1:3000)"
fi

root=$(curl -sS -o /dev/null -w '%{http_code}' "https://$DOMAIN/" || echo "000")
if [[ "$root" == "200" ]]; then
  pass "https://$DOMAIN/ → 200"
else
  fail_msg "https://$DOMAIN/ → $root"
fi

echo
echo "== compose =="
docker compose ps 2>/dev/null || true

echo
echo "Result: $ok ok, $fail failed"
[[ "$fail" -eq 0 ]]
