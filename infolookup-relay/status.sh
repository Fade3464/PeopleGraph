#!/bin/sh
set -eu

echo "Compose services"
docker compose ps

echo
echo "Relay health"
docker compose exec -T relay curl --fail --silent http://127.0.0.1:8000/health
echo

echo
echo "Cloudflared readiness"
curl --fail --silent http://127.0.0.1:2000/ready
echo

echo
echo "Current public endpoints"
if [ -f tunnel-state/current-tunnel.env ]; then
  cat tunnel-state/current-tunnel.env
else
  echo "Tunnel state file has not been created yet."
fi

echo
echo "Cloudflared HA connections and request errors"
curl --fail --silent http://127.0.0.1:2000/metrics \
  | grep -E '^(cloudflared_tunnel_ha_connections|cloudflared_tunnel_request_errors)' \
  || true
