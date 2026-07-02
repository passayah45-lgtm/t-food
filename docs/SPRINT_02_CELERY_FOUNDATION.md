# Sprint 2: Celery Foundation and Background Jobs

Status: Implemented for verification alongside the existing `dispatch_worker`.

## Goals

- Add Celery worker and beat without changing customer, merchant, partner, or admin APIs.
- Keep the current `dispatch_worker` running until Celery dispatch is verified in Docker.
- Move safe maintenance work into retryable, idempotent Celery tasks.
- Keep notification behavior synchronous by default, with async creation behind a feature flag.

## Queues

| Queue | Purpose |
|---|---|
| `critical` | Reserved for future payment/order-critical jobs |
| `dispatch` | Delivery candidate notification and dispatch maintenance |
| `notifications` | Async notification creation/sending |
| `maintenance` | Expiry, cleanup, and periodic maintenance |
| `default` | Fallback for unclassified tasks |

## Tasks

| Task | Queue | Schedule | Idempotency |
|---|---|---|---|
| `orders.tasks.expire_unpaid_orders_task` | `maintenance` | Every 60 seconds | Locks `PLACED` expired orders and changes each order once |
| `delivery.tasks.notify_pending_delivery_candidates_task` | `dispatch` | Every 15 seconds | Existing notification lookup prevents duplicate pickup notifications |
| `notifications.tasks.create_notification_task` | `notifications` | On demand only | Missing users are ignored safely; default `notify()` remains synchronous |

## Feature Flags

| Setting | Default | Meaning |
|---|---|---|
| `NOTIFICATIONS_ASYNC_ENABLED` | `False` | When true, `notify()` enqueues notification creation after transaction commit |

## Docker Services

Existing:

- `backend`
- `dispatch_worker`
- `frontend`
- `db`
- `redis`

New:

- `celery_worker`
- `celery_beat`

The old `dispatch_worker` remains active during Sprint 2 verification.

## Verification Commands

From `D:\Mister T\t-food\work\T-food-clean`:

```powershell
python manage.py test api markets events orders delivery notifications
python manage.py makemigrations --check --dry-run
npm.cmd run build
```

Docker:

```powershell
$env:DJANGO_SECRET_KEY='local-container-runtime-secret-not-for-production'
$env:POSTGRES_PASSWORD='local-container-runtime-password'
$env:ALLOWED_HOSTS='localhost,127.0.0.1'
$env:CSRF_TRUSTED_ORIGINS='http://localhost:8088,http://127.0.0.1:8088'
$env:CORS_ALLOWED_ORIGINS='http://localhost:8088,http://127.0.0.1:8088'
$env:SECURE_SSL_REDIRECT='False'
$env:APP_PORT='8088'

docker compose build backend dispatch_worker celery_worker celery_beat frontend
docker compose up -d backend dispatch_worker celery_worker celery_beat frontend
docker compose exec -T backend python manage.py migrate
docker compose exec -T backend python manage.py test api markets events orders delivery notifications
docker compose ps
```

Runtime checks:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8088/
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8088/api/v1/health/
docker compose logs --tail=100 celery_worker
docker compose logs --tail=100 celery_beat
```

## Rollback

If Celery causes runtime issues:

1. Stop only `celery_worker` and `celery_beat`.
2. Keep `dispatch_worker` running.
3. Leave code in place; current APIs and synchronous `notify()` behavior remain compatible.

```powershell
docker compose stop celery_worker celery_beat
```

