# PeopleGraph Docker Deployment

This guide deploys PeopleGraph as four containers:

- `nginx` - public reverse proxy on port `80`
- `frontend` - Next.js standalone server on port `3000` inside Docker
- `backend` - Django served by Gunicorn on port `8000` inside Docker
- `db` - PostgreSQL with a persistent named Docker volume

Only Nginx is published to the host. PostgreSQL, Django, and Next.js stay on the Docker network.

## 1. Server Prerequisites

Install Docker Engine and the Docker Compose plugin on the production server.

Verify:

```bash
docker --version
docker compose version
```

Open firewall ports:

- `80/tcp` for HTTP and reverse-proxy health checks
- `443/tcp` for HTTPS

## 2. DNS and Turnstile

Recommended domain layout:

```text
peoplegraph.co      -> production frontend/reverse proxy
www.peoplegraph.co  -> production frontend/reverse proxy
```

In Cloudflare Turnstile:

1. Create a widget for production.
2. Add the exact frontend hostnames, for example `peoplegraph.co` and `www.peoplegraph.co`.
3. Copy the public sitekey.
4. Copy the secret key.

The frontend refuses placeholder and Cloudflare test sitekeys. Django also rejects Cloudflare test secret keys when `DJANGO_DEBUG=False`.

## 3. Create Production Environment

On the server:

```bash
cp .env.production.example .env.production
chmod 600 .env.production
```

Edit `.env.production`.

Minimum required changes:

```text
NEXT_PUBLIC_API_BASE_URL=https://peoplegraph.co
NEXT_PUBLIC_TURNSTILE_SITE_KEY=<real-cloudflare-sitekey>

DJANGO_SECRET_KEY=<long-random-secret>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=peoplegraph.co,www.peoplegraph.co
DJANGO_CORS_ALLOWED_ORIGINS=https://peoplegraph.co,https://www.peoplegraph.co
DJANGO_CSRF_TRUSTED_ORIGINS=https://peoplegraph.co,https://www.peoplegraph.co
DJANGO_ADMIN_URL_PATH=<private-admin-path>/

POSTGRES_PASSWORD=<strong-db-password>

CALLLOOM_API_KEY=<real-callloom-key>
TCPA_BLACKLIST_API_KEY=<real-tcpa-key>
TURNSTILE_SECRET_KEY=<real-cloudflare-secret-key>
```

Generate a Django secret:

```bash
python3 - <<'PY'
from secrets import token_urlsafe
print(token_urlsafe(64))
PY
```

If this server is directly internet-facing and Nginx terminates TLS itself, configure TLS before enabling `DJANGO_SECURE_SSL_REDIRECT=True`. If TLS terminates at Cloudflare or another trusted load balancer, ensure that proxy sends `X-Forwarded-Proto: https`.

## 4. Align Nginx Admin Route

The Nginx config routes this path to Django:

```text
/admin/
```

If you change `DJANGO_ADMIN_URL_PATH`, update `deploy/nginx/default.conf` to match.

## 5. Build Images

From the repository root:

```bash
docker compose --env-file .env.production build
```

The frontend public env variables are compiled into the Next.js build. If `NEXT_PUBLIC_API_BASE_URL` or `NEXT_PUBLIC_TURNSTILE_SITE_KEY` changes, rebuild the frontend image.

## 6. Start Services

```bash
docker compose --env-file .env.production up -d
```

The backend entrypoint waits for PostgreSQL, runs migrations, collects static files, then starts Gunicorn.

Check status:

```bash
docker compose --env-file .env.production ps
docker compose --env-file .env.production logs -f nginx backend frontend
```

To validate the compose file against the example env without creating `.env.production`:

```bash
APP_ENV_FILE=.env.production.example docker compose --env-file .env.production.example config
```

Health checks:

```bash
curl -i http://127.0.0.1/api/health/
curl -i http://127.0.0.1/lookup
```

## 7. Issue Let's Encrypt Certificate

Make sure DNS points to this server before running Certbot.

First start the stack with the default HTTP Nginx config:

```bash
APP_ENV_FILE=.env.production docker compose --env-file .env.production up -d
```

Issue the certificate. Replace the email and domains:

```bash
APP_ENV_FILE=.env.production docker compose --env-file .env.production run --rm certbot \
  certonly \
  --webroot \
  --webroot-path /var/www/certbot \
  --email admin@peoplegraph.co \
  --agree-tos \
  --no-eff-email \
  -d peoplegraph.co \
  -d www.peoplegraph.co
```

If the command succeeds, copy the SSL config into place:

```bash
cp deploy/nginx/ssl.conf.example deploy/nginx/default.conf
```

Edit `deploy/nginx/default.conf` and verify:

- `server_name` contains your real domains.
- `ssl_certificate` uses the primary domain Certbot created, for example `/etc/letsencrypt/live/peoplegraph.co/fullchain.pem`.
- `ssl_certificate_key` uses the same primary domain.
- `/admin/` routes to Django and matches `DJANGO_ADMIN_URL_PATH`.
- `/admininstration/login` routes to the Next.js administration login page.

Restart Nginx:

```bash
APP_ENV_FILE=.env.production docker compose --env-file .env.production restart nginx
```

Verify HTTPS:

```bash
curl -I https://peoplegraph.co
curl -I https://peoplegraph.co/api/health/
```

After HTTPS works, set these in `.env.production` if they are not already enabled:

```text
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_TRUST_PROXY_HEADERS=True
DJANGO_TRUST_X_FORWARDED_FOR=True
```

Then recreate backend:

```bash
APP_ENV_FILE=.env.production docker compose --env-file .env.production up -d backend nginx
```

## 8. Certificate Renewal

Test renewal:

```bash
APP_ENV_FILE=.env.production docker compose --env-file .env.production run --rm certbot renew --dry-run
```

Add this host cron entry for automatic renewal:

```cron
0 3 * * * cd /srv/peoplegraph/PeopleGraph && APP_ENV_FILE=.env.production docker compose --env-file .env.production run --rm certbot renew --quiet && APP_ENV_FILE=.env.production docker compose --env-file .env.production exec nginx nginx -s reload
```

Adjust `/srv/peoplegraph/PeopleGraph` if your project path is different.

With DNS/TLS configured:

```bash
curl -i https://peoplegraph.co/api/health/
curl -i https://peoplegraph.co/lookup
```

## 9. Production Security Checks

Run before launch:

```bash
docker compose --env-file .env.production run --rm backend python manage.py check --deploy
docker compose --env-file .env.production run --rm frontend npm audit --omit=dev
```

Expected:

```text
System check identified no issues
found 0 vulnerabilities
```

Direct API calls without Turnstile should fail:

```bash
curl -i -X POST https://peoplegraph.co/api/v1/lookups/phone/ \
  -H "Content-Type: application/json" \
  -d '{"phone_number":"6175412753"}'
```

Expected HTTP status: `403`.

## 10. Update Deployment

Pull or copy the new source to the server, then:

```bash
docker compose --env-file .env.production build
docker compose --env-file .env.production up -d
docker compose --env-file .env.production ps
```

Remove old unused image layers periodically:

```bash
docker image prune
```

## 11. Database Backup and Restore

Backup:

```bash
docker compose --env-file .env.production exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > peoplegraph-$(date +%F).sql
```

Restore into an empty database:

```bash
docker compose --env-file .env.production exec -T db \
  sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"' < peoplegraph-YYYY-MM-DD.sql
```

Keep backups off-server as well. The Docker volume is persistent, but it is not a backup.

## 12. Operational Notes

- Do not commit `.env.production`.
- Do not expose PostgreSQL to the public internet.
- Keep `DJANGO_DEBUG=False` in production.
- Keep `DJANGO_ADMIN_URL_PATH` non-default.
- Keep Turnstile hostnames aligned with the real frontend domain.
- Add authentication before exposing sensitive lookup data to real users.
