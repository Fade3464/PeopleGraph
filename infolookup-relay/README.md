# InfoLookup Relay

A narrow authenticated FastAPI relay intended to run on the Pakistani origin. It performs InfoLookup phone and name/state requests from that server's public IP, then returns only compact person fields.

It is not a general HTTP proxy and does not accept caller-controlled URLs or headers.

## Public contract

`POST /v1/lookups/phone`

```json
{"phone_number":"2025550123"}
```

`POST /v1/lookups/name`

```json
{"first_name":"Jane","last_name":"Doe","state":"NY"}
```

The name route accepts a two-letter US state code only. It deliberately rejects ZIP codes and all extra fields. PeopleGraph should call this route only when its address input is a state; a name-plus-ZIP lookup must stop after the primary provider.

Required application header for both routes:

```text
Authorization: Bearer <RELAY_API_TOKEN>
```

`GET /health` reports only local application health. Cloudflare Tunnel connector health is available from `http://127.0.0.1:2000/ready` on the Pakistani host.

## Complete Pakistani-server setup

### 1. Prepare the service

Copy this directory to the Pakistani server, then run:

```bash
cd /srv/infolookup-relay
cp .env.example .env
chmod 600 .env
openssl rand -hex 32
```

Put the generated value in `.env` as `RELAY_API_TOKEN`. Save the same value in a password manager; PeopleGraph will need it later. Do not commit `.env`. No Cloudflare account or tunnel token is required for this automatic Quick Tunnel mode.

### 2. Start the relay and automatic tunnel

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
./status.sh
```

At every Cloudflared container start, Compose automatically requests a new `trycloudflare.com` hostname. The manager detects the hostname and atomically writes this host-visible file:

```text
tunnel-state/current-tunnel.env
```

Its contents have this form:

```dotenv
TUNNEL_STATUS=ready
UPDATED_AT=2026-08-14T00:00:00+00:00
TUNNEL_BASE_URL=https://random-name.trycloudflare.com
PHONE_RELAY_ENDPOINT=https://random-name.trycloudflare.com/v1/lookups/phone
NAME_RELAY_ENDPOINT=https://random-name.trycloudflare.com/v1/lookups/name
```

Wait until `TUNNEL_STATUS=ready`, then assign the two endpoint values to the corresponding PeopleGraph server configuration. The hostname is temporary and can change whenever the tunnel container is recreated or reconnects, so always use the latest file. The generated file is ignored by Git.

Neither FastAPI port `8000` nor the tunnel origin is published directly to the Internet. Port `2000` is bound only to `127.0.0.1` for local Cloudflared readiness and Prometheus metrics. Anyone who discovers the Quick Tunnel URL can reach the relay, but every lookup remains protected by the required high-entropy `RELAY_API_TOKEN`.

### 3. Test locally on the Pakistani server

```bash
docker compose exec -T relay sh -lc 'curl -sS \
  -H "Authorization: Bearer $RELAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  --data "{\"phone_number\":\"2025550123\"}" \
  http://127.0.0.1:8000/v1/lookups/phone'
```

Use a test number you are authorized to process.

Test the name/state route locally with:

```bash
docker compose exec -T relay sh -lc 'curl -sS \
  -H "Authorization: Bearer $RELAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  --data "{\"first_name\":\"Jane\",\"last_name\":\"Doe\",\"state\":\"NY\"}" \
  http://127.0.0.1:8000/v1/lookups/name'
```

### 4. Test through the current tunnel

From the German server:

```bash
source tunnel-state/current-tunnel.env
curl -sS \
  -H "Authorization: Bearer $RELAY_API_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"phone_number":"2025550123"}' \
  "$PHONE_RELAY_ENDPOINT"
```

Copy `current-tunnel.env` to the German server first, or manually set the endpoint from the file on the Pakistani server. For a name/state lookup, use the same bearer header and send the name payload to `$NAME_RELAY_ENDPOINT`.

Expected outcomes:

- `200` with `status: success`: compact records were returned.
- `200` with `status: not_found`: InfoLookup returned no records.
- `401`: relay bearer token is absent or incorrect.
- `429`: the relay rate limit was exceeded.
- `502`: InfoLookup was unavailable, rejected the Pakistani connection, returned invalid data, or required Turnstile.

## Operations and tunnel tracking

Run:

```bash
./status.sh
docker compose logs --since=30m relay cloudflared
```

Cloudflared's local readiness endpoint returns `200` only while it has an active Cloudflare connection. Its Prometheus metrics include active connections, request counts, and tunnel request errors. `./status.sh` also prints the exact current endpoint file.

Rotate credentials independently:

- Rotate `RELAY_API_TOKEN` by changing it on both relay and PeopleGraph, then recreating the relay container.
- After Cloudflared restarts, check `tunnel-state/current-tunnel.env` and update PeopleGraph if the hostname changed.

Back up no cookies or InfoLookup tokens. They are temporary and generated per request.
