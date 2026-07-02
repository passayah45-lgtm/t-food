# T-Food Codespaces Demo Guide

Use GitHub Codespaces when you need a temporary public preview link without paying for a VPS. This is useful for friends, merchants, and test users to see the app, but it is not a production pilot host.

## What Works

- Public temporary HTTPS preview URL.
- Customer, merchant, partner, and operations UI testing.
- COD order testing.
- In-app notifications.
- Realtime WebSocket notifications.
- Review photo and visual search testing with small files.

## What Does Not Work Yet

- Email, SMS, WhatsApp, push, and Telegram delivery remain inactive.
- Codespaces may stop when idle.
- The preview URL may change when the Codespace is recreated.
- Do not store real customer data or production private documents in Codespaces.
- Do not treat Codespaces as the Guinea production VPS.

## 1. Push T-Food to GitHub

From your local machine, push the repository to GitHub. The Codespace must be opened from the repository that contains `work/T-food-clean`.

## 2. Open Codespaces

In GitHub:

1. Open your T-Food repository.
2. Click **Code**.
3. Click **Codespaces**.
4. Click **Create codespace on main**.
5. Wait for the container to finish building.

The devcontainer automatically forwards port `8088` and copies `.env.codespaces.example` to `.env` if `.env` does not already exist.

## 3. Start T-Food

In the Codespaces terminal:

```bash
cd work/T-food-clean
cp -n .env.codespaces.example .env
docker compose --env-file .env build backend frontend celery_worker celery_beat dispatch_worker
docker compose --env-file .env up -d db redis
docker compose --env-file .env up -d backend frontend celery_worker celery_beat dispatch_worker
docker compose --env-file .env ps
```

The backend entrypoint runs migrations and collectstatic because the Codespaces `.env` sets:

```env
RUN_MIGRATIONS=True
RUN_COLLECTSTATIC=True
```

## 4. Make the Preview Link Public

In Codespaces:

1. Open the **Ports** tab.
2. Find port `8088`.
3. Right-click the port.
4. Choose **Port Visibility**.
5. Select **Public**.
6. Copy the forwarded URL.

The URL looks similar to:

```text
https://<codespace-name>-8088.app.github.dev/
```

Share that URL with testers.

## 5. Health Checks

Open these URLs using the forwarded Codespaces URL:

```text
https://<codespace-name>-8088.app.github.dev/
https://<codespace-name>-8088.app.github.dev/api/v1/health/
https://<codespace-name>-8088.app.github.dev/api/v1/health/?detail=1
```

Expected:

- `/` returns the T-Food frontend.
- `/api/v1/health/` returns `status: ok`.
- Detailed health reports database, cache, media storage, channel layer, and worker heartbeats.

## 6. Create Test Accounts

Use the UI for normal accounts:

- Customer
- Merchant owner
- Delivery partner

For the first admin/testing operator, use:

```bash
docker compose --env-file .env exec backend python manage.py createsuperuser
```

Keep `ALLOW_LEGACY_GLOBAL_OPERATIONS_ACCESS=False`. Business operations users should have `OperationsStaffProfile` records when testing operations scope.

## 7. Demo Smoke Test

Run this small flow before sharing the link widely:

1. Open the public Codespaces URL.
2. Register/login as a customer.
3. Search restaurants.
4. Create a COD order.
5. Login as merchant owner.
6. Move order to preparing.
7. Move order to ready for pickup.
8. Login as delivery partner.
9. Claim delivery.
10. Mark picked up, on the way, delivered.
11. Confirm customer sees the delivered order.
12. Confirm in-app/realtime notifications appear.
13. Confirm operations dashboard loads for authorized admin.
14. Confirm private media raw URLs are not accessible.

## 8. Stop the Demo

When finished:

```bash
docker compose --env-file .env down
```

To keep volumes but stop containers:

```bash
docker compose --env-file .env stop
```

To remove demo data completely:

```bash
docker compose --env-file .env down -v
```

Only use `down -v` for disposable demo data.

## 9. Troubleshooting

### The page does not load

Check containers:

```bash
docker compose --env-file .env ps
docker compose --env-file .env logs --tail=100 frontend
docker compose --env-file .env logs --tail=100 backend
```

### Health fails

Check dependencies:

```bash
docker compose --env-file .env logs --tail=100 db
docker compose --env-file .env logs --tail=100 redis
docker compose --env-file .env logs --tail=100 celery_worker
docker compose --env-file .env logs --tail=100 dispatch_worker
```

### Login or POST requests fail on Codespaces URL

Confirm `.env` contains:

```env
ALLOWED_HOSTS=localhost,127.0.0.1,.app.github.dev
CSRF_TRUSTED_ORIGINS=https://*.app.github.dev,http://localhost:8088,http://127.0.0.1:8088
SECURE_SSL_REDIRECT=False
```

Restart backend after editing `.env`:

```bash
docker compose --env-file .env up -d backend frontend celery_worker celery_beat dispatch_worker
```

### Codespace is slow

Use a larger Codespaces machine if available, or stop workers temporarily for UI-only demos. For full order/dispatch testing, keep Redis, backend, frontend, Celery worker, Celery beat, and dispatch worker running.

## 10. Upgrade Path

Codespaces is the free demo path. When budget allows, move to:

1. Ubuntu VPS.
2. Docker Compose production overlay.
3. Host Nginx reverse proxy.
4. Let's Encrypt HTTPS.
5. Real backup/restore schedule.

Use `docs/GUINEA_PILOT_VPS_DEPLOYMENT.md` for that path.
