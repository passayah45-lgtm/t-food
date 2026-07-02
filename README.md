# T-Food - Food & Grocery Delivery Platform

## Temporary Codespaces Demo

For a free temporary preview link, open the repository in GitHub Codespaces and follow:

- [docs/CODESPACES_DEMO.md](docs/CODESPACES_DEMO.md)

Codespaces is suitable for demos and controlled testing, not production hosting.

## Platform Strategy

The global-scale architecture, product, AI, security, infrastructure and
investor roadmap is maintained in
[docs/NEXT_GENERATION_BLUEPRINT.md](docs/NEXT_GENERATION_BLUEPRINT.md).

The first implementation milestone is specified in
[docs/SPRINT_01_MARKETS_AND_EVENTS_PLAN.md](docs/SPRINT_01_MARKETS_AND_EVENTS_PLAN.md).

The complete 12-part architecture and implementation package is indexed at
[docs/global-platform/README.md](docs/global-platform/README.md).

## Project Structure

```text
T-food/
├── backend/       Django REST API
├── frontend/      React + Vite + Tailwind
└── README.md
```

---

## Getting Started

### 1. Backend Setup

```bash
cd backend
python -m venv venv

# Activate virtual environment:
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 8010
```

Backend runs at: http://localhost:8010
Admin panel:     http://localhost:8010/admin
API base URL:    http://localhost:8010/api/v1/

---

### 2. Frontend Setup

Open a new terminal window and keep the backend running:

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at: http://localhost:5173

---

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| POST | /api/v1/auth/register/ | Create account |
| POST | /api/v1/auth/login/ | Login, get tokens |
| POST | /api/v1/auth/logout/ | Logout, blacklist token |
| POST | /api/v1/auth/refresh/ | Refresh access token |
| GET  | /api/v1/auth/me/ | Get logged-in user |
| GET/PATCH | /api/v1/users/profile/ | Customer profile |
| POST | /api/v1/users/change-password/ | Change password |
| GET | /api/v1/restaurants/ | Browse restaurants |
| GET | /api/v1/restaurants/:id/ | Restaurant menu |
| GET/POST | /api/v1/orders/ | List or create orders |
| GET | /api/v1/orders/:id/ | Order and tracking details |
| POST | /api/v1/payments/orders/:id/ | Confirm simulated payment |
| GET | /api/v1/delivery/partner/ | Partner delivery queue |

---

## Environment Variables

Create a `.env` file inside `backend/` and do not commit it:

```env
DJANGO_SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173
```

---

## Build Phases

- [x] Phase 1 - Auth, profiles, REST API base
- [x] Phase 2 - Restaurant and grocery browsing
- [x] Phase 3 - Cart, checkout and payments
- [x] Phase 4 - Live order tracking
- [x] Phase 5 - Ratings, offers and loyalty
- [x] Phase 6 - Operations admin and deployment packaging

---

## Production Deployment

The production stack uses PostgreSQL, Gunicorn, Django, Nginx, and the compiled
React application. Docker Compose keeps the API, admin, static files, media,
database, and SPA under one origin.

### 1. Configure

Create a root `.env` using `.env.example` and replace every placeholder.
Generate a Django secret with:

```bash
python -c "from secrets import token_urlsafe; print(token_urlsafe(64))"
```

Set `ALLOWED_HOSTS` to hostnames only. Set `CSRF_TRUSTED_ORIGINS` and
`CORS_ALLOWED_ORIGINS` to complete HTTPS origins.

For an initial HTTP-only server test, use `SECURE_SSL_REDIRECT=False`. Change
it to `True` after TLS is active at the load balancer or reverse proxy.

### 2. Start

```bash
docker compose up -d --build
docker compose ps
docker compose exec backend python manage.py createsuperuser
```

Health check:

```bash
curl http://localhost/api/v1/health/
```

The customer app is served at `/` and operations admin at `/admin/`.

For a demonstration deployment, populate the bundled non-sensitive catalog:

```bash
docker compose exec backend python manage.py seed_demo
```

The command is idempotent. Alternatively set `SEED_DEMO_DATA=True` for the
first startup, then return it to `False`.

### 3. Update

```bash
docker compose build
docker compose up -d db redis
docker compose run --rm backend python manage.py migrate --noinput
docker compose run --rm backend python manage.py collectstatic --noinput
docker compose up -d
```

For production, set `RUN_MIGRATIONS=False` and `RUN_COLLECTSTATIC=False` in
`.env`, then run migrations and `collectstatic` deliberately during deployment.
The entrypoint keeps the old automatic behavior enabled by default for local
compatibility.

### 4. Backup

```bash
docker compose exec -T db pg_dump -U tfood tfood > tfood-backup.sql
```

Back up the `media_data` Docker volume separately because it contains customer
uploads. Never commit the root `.env`, database dumps, or media files.

---

## CI/CD Foundation

GitHub Actions runs the validation workflow in
`.github/workflows/ci.yml` on pull requests and pushes to `main`/`master`.

The CI pipeline is validation-only. It does not deploy to production.

Required checks:

- Backend: install dependencies, `python manage.py check`, migration check, and
  the full Django test suite for the Version 1.0 apps.
- Frontend: `npm ci` and `npm run build`.
- Docker: `docker compose config --quiet` and image builds for `backend` and
  `frontend`.

CI uses safe local/test environment values. Production secrets, payment
provider credentials, notification provider credentials, and private media paths
must never be committed or hardcoded into the workflow.

If CI fails, fix the failing check and rerun the workflow from the GitHub
Actions page before merging.
