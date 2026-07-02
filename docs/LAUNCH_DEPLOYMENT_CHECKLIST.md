# T-Food Launch Deployment Checklist

Target: single-VPS public launch with Docker Compose.

For the controlled Guinea pilot deployment, use
`docs/GUINEA_PILOT_VPS_DEPLOYMENT.md` as the step-by-step VPS runbook, then use
`docs/GUINEA_PILOT_LAUNCH_CHECKLIST.md` for final go/no-go sign-off.

## 1. Server Prerequisites

- Provision a VPS with enough CPU, RAM, and disk for Docker, PostgreSQL, Redis, media, and backups.
- Install Docker Engine and Docker Compose.
- Create a non-root Linux deploy user with Docker access.
- Configure firewall rules:
  - Allow SSH from trusted IPs.
  - Allow HTTP/HTTPS through the public reverse proxy.
  - Do not expose PostgreSQL or Redis publicly.
- Point DNS records to the VPS public IP.
- Configure TLS at the edge proxy or load balancer.

## 2. Repository and Environment

- Clone or upload the T-Food repository to the VPS.
- Copy `.env.example` to `.env`.
- Replace every placeholder secret.
- Set:
  - `DEBUG=False`
  - `ALLOWED_HOSTS=your-domain.example,www.your-domain.example`
  - `CSRF_TRUSTED_ORIGINS=https://your-domain.example,https://www.your-domain.example`
  - `CORS_ALLOWED_ORIGINS=https://your-domain.example,https://www.your-domain.example`
  - `SECURE_SSL_REDIRECT=True`
  - `PUBLIC_APP_URL=https://your-domain.example`
  - `PUBLIC_MEDIA_ROOT=/app/media`
  - `PRIVATE_MEDIA_ROOT=/app/private_media`
  - `ALLOW_LEGACY_GLOBAL_OPERATIONS_ACCESS=False`
  - `RUN_MIGRATIONS=False`
  - `RUN_COLLECTSTATIC=False`
- Keep `SEED_DEMO_DATA=False` for production.
- Keep `NOTIFICATIONS_ASYNC_ENABLED=False` until async notification delivery is explicitly verified in production.

## 3. Build and Start

Before building on the server, confirm the CI workflow has passed for the
commit being deployed. The workflow must validate backend checks, migration
safety, backend tests, frontend build, Docker Compose config, and
backend/frontend Docker image builds.

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.prod.yml build backend dispatch_worker celery_worker celery_beat frontend
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d db redis
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backend python manage.py migrate
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backend python manage.py collectstatic --noinput
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d backend dispatch_worker celery_worker celery_beat frontend
docker compose ps
```

Expected services:

- `backend`
- `dispatch_worker`
- `celery_worker`
- `celery_beat`
- `frontend`
- `db`
- `redis`

The old `dispatch_worker` must remain running during this launch phase.

## 4. Database and Static Files

Production deployments should set `RUN_MIGRATIONS=False` and
`RUN_COLLECTSTATIC=False`, then run `migrate` and `collectstatic` explicitly as
shown above before restarting runtime services.

Static files are collected into the `static_data` Docker volume and served by the frontend Nginx container from `/static/`.

Public media uploads are stored in the `public_media_data` Docker volume and
served by the frontend Nginx container from `/media/`. Private media uploads are
stored in `private_media_data` and must never be mounted into Nginx or served
directly. Move public/private media to object storage before multi-server
deployment.

## 5. Runtime Checks

```powershell
docker compose ps
docker compose logs --tail=100 backend
docker compose logs --tail=100 dispatch_worker
docker compose logs --tail=100 celery_worker
docker compose logs --tail=100 celery_beat
```

Confirm:

- `backend` is healthy.
- `dispatch_worker` is running.
- `celery_worker` is connected to Redis and consuming queues.
- `celery_beat` is sending scheduled tasks.
- There are no permission errors.
- There is no Celery root-user warning.

## 6. Public URL Checks

```powershell
curl -I https://your-domain.example/
curl -i https://your-domain.example/api/v1/health/
```

Expected:

- Frontend returns `200`.
- Health endpoint returns `{"status":"ok"}`.
- Health response includes `X-Correlation-ID`.

## 7. Launch Smoke Test

For the Guinea pilot, use the final pilot gate in
`docs/GUINEA_PILOT_LAUNCH_CHECKLIST.md` together with the operational smoke
tests in `docs/PILOT_SMOKE_TESTS.md`.

Run through the complete marketplace flow:

1. Customer login.
2. Browse restaurants.
3. Add item and options.
4. Checkout with COD.
5. Confirm `order.created` outbox event exists.
6. Merchant login.
7. Merchant moves order to `PREPARING`.
8. Merchant moves order to `READY_FOR_PICKUP`.
9. Confirm `order.status_changed` outbox events exist.
10. Partner login.
11. Partner sees order in available deliveries.
12. Partner claims delivery.
13. Partner marks `PICKED_UP`.
14. Partner marks `ON_THE_WAY`.
15. Partner marks `DELIVERED` with customer handoff code.
16. Customer order tracking shows `DELIVERED`.
17. Run `relay_outbox_events`.
18. Confirm pending outbox events become `PUBLISHED`.

## 8. Backup Readiness

Before public launch, run and verify:

```powershell
bash scripts/backup_db.sh
docker compose exec -T redis redis-cli BGSAVE
bash scripts/backup_media.sh
```

Do not launch until a restore drill succeeds for the database, public media, and
private media. Private media must remain outside `/media` after restore.

## 9. Go / No-Go

Go only if:

- CI passed for the deployment commit.
- Docker rebuild passes.
- Migrations pass.
- Backend tests pass in the container.
- Public frontend and health URLs pass.
- Celery worker and beat have no errors.
- `dispatch_worker` is still running.
- End-to-end smoke test passes.
- Backup and restore commands have been tested.
