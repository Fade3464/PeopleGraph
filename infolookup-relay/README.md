# InfoLookup Relay

A narrow authenticated FastAPI relay running on the Pakistani origin. It performs InfoLookup phone and name/state requests from that server's public IP and returns compact person fields plus structured addresses (`street`, `city`, `state`, `zip_code`). Address lists preserve provider order, with a limit of 100 addresses per person.

The relay is exposed through the named Cloudflare Tunnel hostname `https://relay.peoplegraph.co`. It is not a general HTTP proxy and does not accept caller-controlled URLs or headers.

## Public contract

`POST /v1/lookups/phone`

```json
{"phone_number":"2025550123"}
```

`POST /v1/lookups/name`

```json
{"first_name":"Jane","last_name":"Doe","state":"NY"}
```

Both lookup routes require:

```text
Authorization: Bearer <RELAY_API_TOKEN>
```

For the structured-address update, rebuild both the relay and the PeopleGraph backend/frontend. No database migration is required: new address lists are stored in the existing lookup cache JSON. Previously cached compact records still contain only the fields originally saved; they keep their state/ZIP display until explicitly refreshed. Do not clear the entire lookup cache to roll out this update.

`GET /health` reports local application health. `POST /v1/diagnostics/upstream` is bearer-authenticated and checks the configured upstream phone and name/state lookups without returning personal records.

## Production architecture

```text
PeopleGraph backend
      |
      | HTTPS + bearer token
      v
https://relay.peoplegraph.co
      |
      v
Cloudflare named tunnel
      |
      v
cloudflared container
      |
      | Docker network
      v
http://relay:8000
```

Port `8000` is not published to the Internet. Cloudflared establishes outbound tunnel connections to Cloudflare. Port `2000` is bound to `127.0.0.1` only for local readiness and metrics.

## Server setup

```bash
cd /srv/infolookup-relay
cp .env.example .env
chmod 600 .env
```

Generate a relay bearer token:

```bash
openssl rand -hex 32
```

Set the resulting value as `RELAY_API_TOKEN` in `.env`. Configure the same value as `SECONDARY_RELAY_API_TOKEN` in the PeopleGraph server's `.env.production`.

Create a remotely managed Cloudflare Tunnel in the Cloudflare dashboard and configure the published application route:

```text
Hostname: relay.peoplegraph.co
Service:  http://relay:8000
```

Copy the Cloudflare tunnel token into the relay server's `.env` as `CLOUDFLARE_TUNNEL_TOKEN`. Treat both tokens as secrets and do not commit `.env`.

Start the stack:

```bash
docker compose config --quiet
docker compose pull cloudflared
docker compose up -d --build
docker compose ps
./status.sh
```

## Test locally

```bash
docker compose exec -T relay sh -lc 'curl -sS \
  -H "Authorization: Bearer $RELAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  --data "{\"phone_number\":\"2025550123\"}" \
  http://127.0.0.1:8000/v1/lookups/phone'
```

Use only test data you are authorized to process.

## Test through Cloudflare

```bash
docker compose exec -T relay sh -lc 'curl -sS \
  -H "Authorization: Bearer $RELAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  --data "{\"phone_number\":\"2025550123\"}" \
  https://relay.peoplegraph.co/v1/lookups/phone'
```

Health check:

```bash
curl -i https://relay.peoplegraph.co/health
```

Expected outcomes:

- `200` with `status: success`: compact records were returned.
- `200` with `status: not_found`: InfoLookup returned no records.
- `401`: the relay bearer token is missing or incorrect.
- `429`: the relay rate limit was exceeded.
- `502`: the upstream provider failed or returned invalid data.

## Persistence and credential rotation

`RELAY_API_TOKEN` lives in `/srv/infolookup-relay/.env`; recreating the relay container reads the same value again. `CLOUDFLARE_TUNNEL_TOKEN` also lives in `.env`, so the named tunnel reconnects with the same tunnel identity after container recreation.

On the PeopleGraph server, enable the backend bootstrap:

```text
ENSURE_SECONDARY_RELAY_CONFIG=True
SECONDARY_RELAY_BASE_URL=https://relay.peoplegraph.co
SECONDARY_RELAY_API_TOKEN=<same RELAY_API_TOKEN>
```

The backend image upserts its singleton relay configuration from these runtime values during startup. This avoids manual Django-admin reconfiguration after backend container recreation while keeping secrets out of the image layers.

To rotate `RELAY_API_TOKEN`, change it on both servers and recreate the affected containers. To rotate the Cloudflare tunnel token, change only `CLOUDFLARE_TUNNEL_TOKEN` on the relay server and recreate `cloudflared`.
