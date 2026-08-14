# PeopleGraph Security Notes

## Lookup request controls

Public lookup requests pass through several independent checks: per-IP throttling, an exact production `Origin` allowlist, `Sec-Fetch-Site` validation when supplied, server-side Turnstile validation (including expected action and hostname), and the Pakistan region gate. Nginx overwrites forwarded client-IP headers before proxying to Django so callers cannot inject a trusted prefix.

Browser headers alone cannot prove that a request was created by the PeopleGraph JavaScript because a custom HTTP client can reproduce them. Turnstile is the primary bot/automation control; the origin checks reduce browser abuse and accidental cross-site calls. Keep the backend reachable only through the supplied Nginx service and do not publish Gunicorn directly.

## Regional decisions

The backend queries IPinfo Lite only when an unexpired database decision does not exist. Pakistan responses are cached for `IPINFO_ALLOWED_CACHE_DAYS`; denied countries are cached for `IPINFO_DENIED_CACHE_HOURS`. Failures are closed: if the public IP or country cannot be verified, the lookup is not sent upstream.

Treat `IPINFO_API_TOKEN` as a secret. Rotate any token pasted into chat, tickets, logs, or shell history before deployment. The token must exist only in the production environment file.

## Relay controls

The relay accepts fixed phone and name/state schemas, never caller-supplied URLs. Lookup and diagnostic endpoints require a high-entropy bearer token, responses have size limits, requests have timeouts, and lookup concurrency/rates are bounded. The relay container uses a read-only filesystem, a small temporary filesystem, and `no-new-privileges`; its application port is not published by Compose.

Quick Tunnel hostnames are public and temporary, so the bearer token remains mandatory. Discord notifications include the endpoints and bearer token in the message body; restrict the channel and treat its history as sensitive.

## Operations

- Keep `.env.production`, the relay `.env`, database backups, and Discord webhook URLs out of Git.
- Use HTTPS only and keep HSTS, secure cookies, and the private Django admin path enabled.
- Rotate Django, upstream, relay, Turnstile, IPinfo, database, and Discord credentials independently.
- Review lookup throttles, denied-region rows, audit source/timing, relay diagnostics, and authentication failures regularly.
- Apply dependency and base-image updates on a regular schedule and rerun the full test/build suite.
