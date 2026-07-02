# T-Food Production Runbook

Target: single-VPS Docker Compose launch.

## Service Map

| Service | Purpose |
|---|---|
| `frontend` | Nginx serving React, `/static/`, `/media/`, and proxying API/admin |
| `backend` | Django REST API and admin via Gunicorn |
| `dispatch_worker` | Existing dispatch/expiry loop kept for compatibility during launch |
| `celery_worker` | Celery task consumer for dispatch, maintenance, notifications, default queues |
| `celery_beat` | Celery scheduler for maintenance and dispatch tasks |
| `db` | PostgreSQL |
| `redis` | Redis cache, Celery broker, Celery results |

## Daily Health Checks

```powershell
docker compose ps
docker compose logs --tail=100 backend
docker compose logs --tail=100 dispatch_worker
docker compose logs --tail=100 celery_worker
docker compose logs --tail=100 celery_beat
curl -i https://your-domain.example/api/v1/health/
```

Healthy signs:

- `backend` is healthy.
- `dispatch_worker` is up.
- `celery_worker` is receiving and completing tasks.
- `celery_beat` is sending scheduled tasks.
- Health endpoint returns `{"status":"ok"}`, dependency checks, and `X-Correlation-ID`.

For readiness details:

```powershell
curl -s https://your-domain.example/api/v1/health/?detail=1
```

The detailed health response includes database, cache, media storage, channel
layer, and worker heartbeat status. It must not include secrets, tokens,
provider credentials, private media paths, or verification document paths.

## Monitoring and Observability

Enable the production observability foundation with environment variables:

| Variable | Default | Purpose |
|---|---:|---|
| `MONITORING_ENABLED` | `True` | Keeps health and heartbeat checks active |
| `METRICS_ENABLED` | `True` | Enables aggregate-only metric snapshots for future exporters |
| `ERROR_REPORTING_ENABLED` | `False` | Reserved for Sentry/OpenTelemetry activation |
| `SLOW_QUERY_THRESHOLD_MS` | `500` | Threshold used by logs and future slow-query reporting |
| `LOG_LEVEL` | `INFO` | Application log level |

Application logs are structured JSON when `DEBUG=False`. Every HTTP request log
should include:

- `timestamp`
- `level`
- `logger`
- `message`
- `correlation_id`
- `request_id`
- `user_id` when authenticated
- `operation`
- `duration_ms`
- `method`
- `path`
- `status_code`

Never log passwords, JWT tokens, provider secrets, private media paths, raw
verification documents, or uploaded file contents.

### Alert Candidates

Critical alerts:

- backend health endpoint unavailable.
- database check fails.
- cache/Redis check fails.
- `celery_worker` heartbeat missing for more than 3 minutes.
- `dispatch_worker` heartbeat missing for more than 3 minutes.

High alerts:

- payment failures spike.
- refund failures spike.
- notification realtime failures spike.
- Celery queue backlog grows.
- database latency or slow queries exceed launch thresholds.

Medium alerts:

- review photo moderation queue grows.
- visual search no-result rate grows.
- upload validation failures spike.

Low alerts:

- cache miss rate rises.
- disk usage grows.
- analytics jobs run longer than expected.

External integrations such as Sentry, OpenTelemetry, Prometheus, and Grafana are
prepared as extension points but are not activated until production credentials
and dashboards are available.

## CI Validation

The launch CI workflow in `.github/workflows/ci.yml` runs on pull requests and
pushes to `main`/`master`. CI validates changes only; it does not deploy to
production.

Merge-blocking checks:

- `python manage.py check`
- `python manage.py makemigrations --check --dry-run`
- `python manage.py test fooddelivery api restaurants verifications notifications orders delivery payments ledger realtime merchant_staff operations_access intelligence user_preferences`
- `npm ci`
- `npm run build`
- `docker compose config --quiet`
- `docker compose build backend frontend`

Required CI environment values are intentionally non-production placeholders:

- `DJANGO_SECRET_KEY`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `CORS_ALLOWED_ORIGINS`
- `REDIS_URL`
- `CHANNEL_REDIS_URL`
- `POSTGRES_PASSWORD` for Docker Compose validation/build

Do not add production payment, notification, database, or media secrets to CI.
Rerun failed checks from the GitHub Actions page after pushing a fix.

## Deploy

Do not deploy a change until CI passes.

Use the production Compose overlay on the VPS:

```powershell
$env:COMPOSE_FILE="docker-compose.yml;docker-compose.prod.yml"
docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet
```

```powershell
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml build backend dispatch_worker celery_worker celery_beat frontend
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d db redis
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backend python manage.py migrate
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backend python manage.py collectstatic --noinput
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d backend dispatch_worker celery_worker celery_beat frontend
docker compose ps
```

Then run the launch smoke checklist from `docs/LAUNCH_DEPLOYMENT_CHECKLIST.md`.

## Backup Commands

Use `docs/BACKUP_RESTORE_RUNBOOK.md` as the source of truth. Create a
`backups` directory first:

```powershell
mkdir backups
```

PostgreSQL custom-format dump:

```powershell
bash scripts/backup_db.sh
```

Redis snapshot:

```powershell
docker compose exec -T redis redis-cli BGSAVE
docker run --rm -v t-food-clean_redis_data:/redis -v ${PWD}/backups:/backups alpine tar -czf /backups/redis-$(Get-Date -Format yyyyMMdd-HHmmss).tar.gz -C /redis .
```

Public and private media uploads:

```powershell
bash scripts/backup_media.sh
```

Static files can be rebuilt with `collectstatic`; public media, private media,
and database backups are critical.

## Restore Commands

Stop application writers before restore:

```powershell
docker compose stop backend dispatch_worker celery_worker celery_beat
```

Restore PostgreSQL from a custom-format dump:

```powershell
bash scripts/restore_db.sh --file backups/tfood-db-YYYYMMDD-HHMMSS.dump --confirm-restore
```

Restore media:

```powershell
bash scripts/restore_media.sh --public-file backups/tfood-public-media-YYYYMMDD-HHMMSS.tar.gz --private-file backups/tfood-private-media-YYYYMMDD-HHMMSS.tar.gz --confirm-restore
```

Start services:

```powershell
docker compose up -d backend dispatch_worker celery_worker celery_beat frontend
docker compose exec -T backend python manage.py migrate
```

Run the launch smoke checklist after every restore.

## Existing Volume Permission Fix

After switching the backend image to a non-root user, existing Docker volumes created by older root containers may be root-owned. Do not delete volumes.

If you see permission errors for `/app/staticfiles`, `/app/media`, or `/app/celerybeat-schedule`, run this one-time ownership fix:

```powershell
docker compose run --rm --user root --entrypoint sh backend -c "chown -R app:app /app/staticfiles /app/media /app"
docker compose up -d backend dispatch_worker celery_worker celery_beat frontend
```

This changes ownership only; it does not delete database, Redis, static, or media data.

## Rollback

If a deployment fails after build but before launch:

```powershell
docker compose logs --tail=200 backend
docker compose logs --tail=200 celery_worker
docker compose logs --tail=200 celery_beat
```

Rollback options:

- Revert the code change and rebuild.
- Prefer application rollback to the previous image/commit before attempting
  database rollback.
- Do not reverse production migrations unless the migration was explicitly
  tested as reversible. Restore the pre-deploy database backup during a
  maintenance window if schema/data rollback is required.
- Stop only `celery_worker` and `celery_beat` if Celery is the issue:

```powershell
docker compose stop celery_worker celery_beat
```

The old `dispatch_worker` remains available as the compatibility fallback.

## Incident Checklist

1. Check `docker compose ps`.
2. Check backend health endpoint.
3. Check detailed readiness with `/api/v1/health/?detail=1`.
4. Check backend logs for request errors using the correlation ID.
5. Check Celery worker logs for task failures.
6. Check Celery beat logs for scheduler errors.
7. Check dispatch worker logs for loop errors.
8. Check PostgreSQL disk space.
9. Check Redis availability.
10. If user uploads are affected, inspect `media_data` and `private_media_data` volumes.
11. If checkout or dispatch is affected, run the launch smoke flow against a test order.

## Production Notes

- Keep `DEBUG=False`.
- Keep `SECURE_SSL_REDIRECT=True` only when TLS is correctly configured and `X-Forwarded-Proto` is passed.
- Keep PostgreSQL and Redis private to the Docker network or VPS.
- Back up PostgreSQL and media before every release.
- Move media to object storage before multi-server scaling.
- Keep real secrets out of the repository.
