# PeopleGraph

PeopleGraph is a production-focused people lookup portal. The project includes a polished Next.js frontend with a public landing page and lookup workspace, plus a Django backend scaffold prepared for API development.

## Current Scope

- Public landing page at `/`
- Lookup workspace at `/lookup`
- Search modes for phone number and name/address
- Phone lookup wired to the Django API
- Name and address lookup wired to the Django API
- Database-backed phone result cache to avoid repeated upstream API calls
- Database-backed name/address result cache keyed by normalized first name, last name, and exact zip/address input
- Database-backed TCPA blacklist cache for phone risk status
- Phone lookup audit trail with timestamp, cache-source flags, and request IP
- Loading, empty, error, and results states
- Dark teal responsive UI using Tailwind CSS and shadcn-style components
- JavaScript interactions on the landing page, including scroll reveals, counters, and an interactive product preview
- Django backend project with a `lookups` app for search APIs
- DRF and CORS configured for frontend/backend integration

## Tech Stack

- Next.js App Router
- React
- TypeScript
- Tailwind CSS
- shadcn/ui-style local primitives
- lucide-react icons

- Django
- Django REST Framework
- django-cors-headers

## Project Structure

```text
PeopleGraph/
  backend/
    config/             # Django project settings and root URLs
    lookups/            # Lookup app for future API endpoints
    requirements.txt    # Backend Python dependencies
  frontend/
    app/
      page.tsx          # Landing page
      lookup/page.tsx   # Lookup portal prototype
      globals.css       # Global theme and utilities
    components/ui/      # Local UI primitives
    lib/                # Shared frontend utilities
```

## Frontend Setup

Install frontend dependencies:

```bash
cd frontend
npm install
```

Run the development server:

```bash
npm run dev
```

Optional frontend environment:

```bash
cp .env.example .env.local
```

```text
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_TURNSTILE_SITE_KEY=replace-with-real-cloudflare-sitekey
```

Open:

```text
http://localhost:3000
```

Build for production:

```bash
npm run build
```

## Backend Setup

Create and activate a virtual environment:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

Install backend dependencies:

```bash
pip install -r requirements.txt
```

Copy the environment template and update the database credentials:

```bash
cp .env.example .env
```

The backend is configured to use PostgreSQL by default:

```text
POSTGRES_DB=peoplegraph
POSTGRES_USER=admin
POSTGRES_PASSWORD=peoplegraph43211234
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

Configure the upstream phone lookup provider:

```text
CALLLOOM_API_KEY=replace-me
CALLLOOM_PHONE_LOOKUP_URL=https://api.callloom.com/api/people-lookup/get-phone-lookup/
CALLLOOM_NAME_ADDR_LOOKUP_URL=https://api.callloom.com/api/people-lookup/get-phone-lookup/
CALLLOOM_TIMEOUT_SECONDS=20
```

Configure Cloudflare Turnstile:

```text
TURNSTILE_SECRET_KEY=replace-with-real-cloudflare-secret-key
TURNSTILE_SITEVERIFY_URL=https://challenges.cloudflare.com/turnstile/v0/siteverify
TURNSTILE_TIMEOUT_SECONDS=10
```

Use dashboard-generated Cloudflare keys for staging and production testing. The application intentionally ignores Cloudflare test sitekeys in the browser and rejects Cloudflare test secret keys when `DJANGO_DEBUG=False`.

Configure the TCPA blacklist provider:

```text
TCPA_BLACKLIST_API_KEY=replace-me
TCPA_BLACKLIST_LOOKUP_URL=https://api.tcpablacklist.com/api/phone-lookup/
TCPA_BLACKLIST_TIMEOUT_SECONDS=20
```

Create the local PostgreSQL role and database with an admin user:

```bash
psql -U postgres -d postgres -f sql/create_peoplegraph_db.sql
```

If your PostgreSQL install uses peer authentication for the `postgres` user, run it through the OS postgres account instead:

```bash
sudo -u postgres psql -d postgres -f sql/create_peoplegraph_db.sql
```

Run migrations:

```bash
python manage.py migrate
```

Start the Django development server:

```bash
python manage.py runserver 8000
```

Health check:

```text
http://localhost:8000/api/health/
```

Run backend tests without requiring PostgreSQL:

```bash
DJANGO_DATABASE_ENGINE=sqlite python manage.py test
```

## Routes

Frontend:

- `/` - Public PeopleGraph landing page
- `/lookup` - Interactive people lookup workspace

Backend:

- `/api/health/` - Backend health check
- `/api/v1/lookups/phone/` - Phone lookup endpoint with Turnstile validation, people-result caching, and TCPA blacklist caching
- `/api/v1/lookups/name-address/` - Name/address lookup endpoint with Turnstile validation and database result caching

## Cloudflare Turnstile Setup

1. Log in to the Cloudflare dashboard.
2. Open **Turnstile** and create a new widget.
3. Name it clearly, for example `PeopleGraph Lookup`.
4. Add the hostnames that will render the lookup page, for example `peoplegraph.co`, `www.peoplegraph.co`, or `staging.peoplegraph.co`.
5. Choose a managed/visible widget mode unless you have a specific reason to use invisible.
6. Copy the public **sitekey** into `frontend/.env.local` as `NEXT_PUBLIC_TURNSTILE_SITE_KEY`.
7. Copy the private **secret key** into `backend/.env` as `TURNSTILE_SECRET_KEY`.
8. Restart both dev servers after changing environment variables.

For production-like testing, run the app through a real hostname included in the Turnstile widget. The lookup page will not render a mock captcha or Cloudflare's public testing key.

Turnstile tokens are generated in the browser and validated by Django before either lookup endpoint runs. Tokens expire after five minutes and are single-use, so the frontend resets the widget after each lookup attempt.

## Production Security Checklist

Set these backend values before running with `DJANGO_DEBUG=False`:

```text
DJANGO_SECRET_KEY=generate-a-long-random-secret
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=api.peoplegraph.co
DJANGO_CORS_ALLOWED_ORIGINS=https://peoplegraph.co,https://www.peoplegraph.co
DJANGO_CSRF_TRUSTED_ORIGINS=https://peoplegraph.co,https://www.peoplegraph.co
DJANGO_ADMIN_URL_PATH=private-admin-path/
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SECURE_HSTS_SECONDS=31536000
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=True
DJANGO_SECURE_HSTS_PRELOAD=True
LOOKUP_THROTTLE_RATE=30/min
```

If the backend is behind a trusted reverse proxy or load balancer, enable proxy headers only at that edge:

```text
DJANGO_TRUST_PROXY_HEADERS=True
DJANGO_TRUST_X_FORWARDED_FOR=True
```

Do not enable forwarded-header trust if clients can reach Django directly.

Production checks:

```bash
DJANGO_DEBUG=False python manage.py check --deploy
cd frontend && npm audit --omit=dev
cd backend && python -m pip_audit -r requirements.txt
```

The frontend sets security headers in `next.config.ts`, including CSP allowances for Cloudflare Turnstile. Keep `NEXT_PUBLIC_API_BASE_URL` pointed at the production API origin before building the production frontend.

## Docker Deployment

Production Docker assets are included:

- `docker-compose.yml` - PostgreSQL, Django/Gunicorn, Next.js standalone, and Nginx
- `.env.production.example` - production environment template
- `backend/Dockerfile` - Django runtime image
- `frontend/Dockerfile` - Next.js standalone image
- `deploy/nginx/default.conf` - reverse proxy routes

Deployment procedure:

```bash
cp .env.production.example .env.production
chmod 600 .env.production
docker compose --env-file .env.production build
docker compose --env-file .env.production up -d
```

Read the full deployment guide before production launch:

```text
docs/DEPLOYMENT.md
```

## Notes

Phone search includes people-result caching, TCPA blacklist caching, and audit logging. Name/address search uses the same CallLoom result layout and caches exact normalized name plus zip/address queries for fast repeat searches.
