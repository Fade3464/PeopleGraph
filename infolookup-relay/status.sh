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
echo "Public endpoint"
echo "https://relay.peoplegraph.co"

echo
echo "Cloudflared HA connections and request errors"
curl --fail --silent http://127.0.0.1:2000/metrics \
  | grep -E '^(cloudflared_tunnel_ha_connections|cloudflared_tunnel_request_errors)' \
  || true
