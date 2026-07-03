# T-Food Codespaces Demo Guide

Use this guide to run T-Food in GitHub Codespaces and share a temporary public forwarded URL with trusted demo testers.

This is not production deployment. Codespaces is temporary, can sleep when idle, and should only contain demo/test data.

## Safety Rules

- Do not use production secrets in Codespaces.
- Do not use real payment provider credentials.
- Do not upload sensitive real verification documents.
- Do not invite too many users at once.
- Use demo/test data only.
- Keep COD enabled for testing.
- Keep Razorpay, Wave, Orange Money, MTN Mobile Money, email, SMS, WhatsApp, push, and Telegram inactive unless explicitly configured later for a separate test.

## What Works

- Temporary HTTPS preview through GitHub forwarded ports.
- Customer, merchant, merchant staff, delivery partner, and operations demo flows.
- COD order testing.
- In-app and realtime notifications.
- Visual search using the local mock provider.
- Review photo upload and operations moderation.
- Public/private media boundary testing.

## What Does Not Work

- Codespaces is not a stable public production host.
- The public link can change when the Codespace is recreated.
- Codespaces can stop when idle.
- Email, SMS, WhatsApp, push, and Telegram are architecture-ready but inactive.
- Real Guinea online payment providers are inactive until real credentials exist.

## 1. Open Codespaces

1. Open the T-Food GitHub repository.
2. Click **Code**.
3. Open the **Codespaces** tab.
4. Click **Create codespace on main**.
5. Wait for the workspace to finish starting.

If your terminal opens at the repository root, stay there. If your repository contains the project inside `work/T-food-clean`, run:

```bash
cd work/T-food-clean
```

If `backend`, `frontend`, and `docker-compose.yml` are already visible in the current folder, do not run `cd work/T-food-clean`.

## 2. Create the Demo Environment File

```bash
cp -n .env.codespaces.example .env
```

If `cp -n` shows a portability warning, it is safe. It means the existing `.env` was not overwritten.

Check the file exists:

```bash
ls .env
```

The template is demo-safe and uses:

- `APP_ENV=development`
- `APP_PORT=8088`
- `ALLOW_LEGACY_GLOBAL_OPERATIONS_ACCESS=False`
- `COD_ENABLED=True`
- External payment and notification providers inactive
- Public media and private media stored in separate Docker volumes

## 3. Build the Containers

```bash
docker compose --env-file .env build backend frontend celery_worker celery_beat dispatch_worker
```

## 4. Start Redis and Postgres First

```bash
docker compose --env-file .env up -d db redis
```

Check they are healthy:

```bash
docker compose --env-file .env ps
```

## 5. Start T-Food Services

```bash
docker compose --env-file .env up -d backend frontend celery_worker celery_beat dispatch_worker
```

Check all services:

```bash
docker compose --env-file .env ps
```

Expected:

- `db` healthy
- `redis` healthy
- `backend` healthy
- `frontend` healthy
- `celery_worker` running
- `celery_beat` running
- `dispatch_worker` running

## 6. Run Migrations

The Codespaces env allows the backend entrypoint to run migrations, but run this explicitly before sharing the demo link:

```bash
docker compose --env-file .env exec -T backend python manage.py migrate
```

## 7. Seed Guinea Demo Data

```bash
docker compose --env-file .env exec -T backend python manage.py seed_guinea_demo
```

The command is idempotent. Running it twice should not duplicate demo records:

```bash
docker compose --env-file .env exec -T backend python manage.py seed_guinea_demo
```

To remove only demo records:

```bash
docker compose --env-file .env exec -T backend python manage.py seed_guinea_demo --reset-demo
```

## 8. Open the Local Preview

Inside Codespaces, open:

```text
http://127.0.0.1:8088/
```

Health checks:

```text
http://127.0.0.1:8088/api/v1/health/
http://127.0.0.1:8088/api/v1/health/?detail=1
```

## 9. Make Port 8088 Public

1. Open the **Ports** tab in Codespaces.
2. Find port `8088`.
3. Right-click the port.
4. Choose **Port Visibility**.
5. Select **Public**.
6. Copy the forwarded URL.

It should look like:

```text
https://<codespace-name>-8088.app.github.dev/
```

When a tester opens the link for the first time, GitHub may show a warning that they are accessing a development port. They should continue only if they trust you and understand this is a temporary demo.

## 10. Demo Accounts

All demo accounts use:

```text
DemoPass123!
```

| Actor | Email |
| --- | --- |
| Operations admin | `ops.guinea.demo@t-food.test` |
| Customer | `customer.guinea.demo@t-food.test` |
| Merchant owner | `merchant.guinea.demo@t-food.test` |
| Merchant staff | `staff.guinea.demo@t-food.test` |
| Delivery partner | `rider.guinea.demo@t-food.test` |

Never use these credentials in production.

## 11. Demo Flow

1. Customer logs in.
2. Customer searches for Conakry Grill.
3. Customer adds an item to cart.
4. Customer places a COD order.
5. Merchant owner logs in.
6. Merchant accepts/prepares the order.
7. Merchant marks the order ready for pickup.
8. Delivery partner logs in.
9. Rider claims or receives the delivery.
10. Rider marks pickup, on the way, and delivered.
11. Customer submits a review.
12. Customer uploads a review photo.
13. Operations admin logs in.
14. Operations opens review photo moderation.
15. Operations approves/rejects/hides the photo.
16. Check notifications for each actor.

## 12. Share the Link Safely

Send testers:

- The public Codespaces URL.
- Their assigned demo role.
- The matching demo email.
- The shared demo password.
- A warning not to enter real payment cards, real IDs, or private documents.

Example:

```text
T-Food demo link:
https://<codespace-name>-8088.app.github.dev/

Role: Customer
Email: customer.guinea.demo@t-food.test
Password: DemoPass123!

Use demo data only. Do not upload real private documents.
```

## 13. Stop Services

Stop containers but keep data:

```bash
docker compose --env-file .env stop
```

Start them again:

```bash
docker compose --env-file .env up -d db redis
docker compose --env-file .env up -d backend frontend celery_worker celery_beat dispatch_worker
```

Remove containers but keep volumes:

```bash
docker compose --env-file .env down
```

Remove containers and all local demo data:

```bash
docker compose --env-file .env down -v
```

Use `down -v` only for disposable demo data.

## 14. Troubleshooting

### The link shows 404 or 502

Check containers:

```bash
docker compose --env-file .env ps
```

Restart if needed:

```bash
docker compose --env-file .env up -d db redis
docker compose --env-file .env up -d backend frontend celery_worker celery_beat dispatch_worker
```

Check local frontend:

```bash
curl -I http://localhost:8088/
```

If local `curl` works but the public link does not, check the Codespaces port visibility and make sure port `8088` is public.

### Login or POST requests fail

Confirm `.env` contains:

```env
ALLOWED_HOSTS=localhost,127.0.0.1,.app.github.dev
CSRF_TRUSTED_ORIGINS=https://*.app.github.dev,http://localhost:8088,http://127.0.0.1:8088
SECURE_SSL_REDIRECT=False
```

Restart backend and frontend:

```bash
docker compose --env-file .env up -d backend frontend celery_worker celery_beat dispatch_worker
```

### Services are stopped after closing the terminal

Codespaces can stop containers when the workspace sleeps. Restart with:

```bash
docker compose --env-file .env up -d db redis
docker compose --env-file .env up -d backend frontend celery_worker celery_beat dispatch_worker
```

### Need logs

```bash
docker compose --env-file .env logs --tail=100 backend
docker compose --env-file .env logs --tail=100 frontend
docker compose --env-file .env logs --tail=100 celery_worker
docker compose --env-file .env logs --tail=100 dispatch_worker
```

## 15. Codespaces Readiness Checklist

| Area | Expected |
| --- | --- |
| Docker Compose | `docker compose --env-file .env config --quiet` passes |
| Frontend | Port `8088` maps to frontend container port `80` |
| Backend | `/api/v1/health/` returns healthy response |
| Redis/Postgres | Start before backend and report healthy |
| Workers | Celery worker, Celery beat, dispatch worker are running |
| Demo data | `seed_guinea_demo` runs without duplicates |
| Public media | Served through frontend nginx `/media/` |
| Private media | Stored in `private_media_data`, not directly exposed |
| Payments | COD active; online providers inactive |
| Notifications | In-app/realtime active; external channels inactive |

