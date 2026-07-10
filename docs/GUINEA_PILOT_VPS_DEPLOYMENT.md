# T-Food Guinea Pilot VPS Deployment Guide

This guide prepares the first controlled T-Food pilot deployment in Guinea on a public Ubuntu VPS with Docker Compose, host Nginx, and Let's Encrypt HTTPS.

This is not a full public launch. Keep the pilot controlled, keep COD enabled, and keep Guinea online payment providers inactive until real credentials and operational procedures are ready.

## 1. Deployment Decisions

### Domain

Choose one production pilot domain before provisioning certificates:

| Option | Recommendation |
| --- | --- |
| `pilot.t-food.com` | Best for controlled pilot and future separation from public launch |
| `t-food.com` | Use only if this is the final production brand domain |
| `tfood.app` | Good product domain if already owned |
| `tfood.gu` | Good Guinea-specific domain if available |

Use one canonical domain for launch. Add `www` only if you intend to support it.

### VPS Provider

Recommended providers:

- Hetzner
- DigitalOcean
- Contabo
- Linode
- Vultr

Minimum Guinea pilot VPS:

- Ubuntu 22.04 or 24.04 LTS
- 4 vCPU
- 8 GB RAM
- 80 to 160 GB SSD
- Public IPv4
- Provider snapshots enabled if available

## 2. Production Architecture

Services:

- Host Nginx terminates HTTPS.
- Docker `frontend` serves React, `/static/`, public `/media/`, and proxies `/api/`, `/admin/`, and `/ws/`.
- Docker `backend` serves Django API and authenticated private media endpoints.
- Docker `db` runs PostgreSQL/PostGIS.
- Docker `redis` supports cache, channels, Celery broker/result backend.
- Docker `celery_worker` handles background tasks.
- Docker `celery_beat` handles schedules.
- Docker `dispatch_worker` handles dispatch jobs.
- Public media volume stores public restaurant/menu/approved review media.
- Private media volume stores verification documents and non-public review photos.

Private media must never be mounted into host Nginx or served directly.

## 3. VPS Bootstrap

Run as root or a sudo-capable setup user.

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y ca-certificates curl gnupg git nginx certbot python3-certbot-nginx ufw
```

Install Docker Engine and Compose plugin:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
docker --version
docker compose version
```

Create deploy user:

```bash
sudo adduser deploy
sudo usermod -aG sudo deploy
sudo usermod -aG docker deploy
```

Log in as `deploy` before continuing:

```bash
su - deploy
```

Configure firewall:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

Do not expose PostgreSQL or Redis publicly.

## 4. DNS

Point the selected domain to the VPS public IP.

Example:

| Type | Name | Value |
| --- | --- | --- |
| `A` | `pilot` | VPS public IPv4 |
| `A` | `www.pilot` if used | VPS public IPv4 |

Wait until DNS resolves:

```bash
dig +short pilot.t-food.com
```

## 5. Repository Setup

```bash
mkdir -p ~/apps
cd ~/apps
git clone <your-repository-url> t-food
cd ~/apps/t-food/work/T-food-clean
```

If the repository is already present:

```bash
cd ~/apps/t-food/work/T-food-clean
git pull
```

## 6. Production `.env` Template

Create `.env`:

```bash
cp .env.example .env
nano .env
```

Use this template and replace placeholders:

```env
APP_ENV=production
DEBUG=False
DJANGO_SECRET_KEY=<strong-random-secret>

POSTGRES_DB=tfood
POSTGRES_USER=tfood
POSTGRES_PASSWORD=<strong-db-password>
DATABASE_URL=postgis://tfood:<strong-db-password>@db:5432/tfood

REDIS_URL=redis://redis:6379/0
CHANNEL_REDIS_URL=redis://redis:6379/1

ALLOWED_HOSTS=<domain>,www.<domain>
CSRF_TRUSTED_ORIGINS=https://<domain>,https://www.<domain>
CORS_ALLOWED_ORIGINS=https://<domain>,https://www.<domain>
PUBLIC_APP_URL=https://<domain>
SECURE_SSL_REDIRECT=True

APP_PORT=8088
PUBLIC_MEDIA_ROOT=/app/media
PRIVATE_MEDIA_ROOT=/app/private_media

ALLOW_LEGACY_GLOBAL_OPERATIONS_ACCESS=False
RUN_MIGRATIONS=False
RUN_COLLECTSTATIC=False
SEED_DEMO_DATA=False

MONITORING_ENABLED=True
METRICS_ENABLED=True
ERROR_REPORTING_ENABLED=False
SLOW_QUERY_THRESHOLD_MS=500
LOG_LEVEL=INFO

NOTIFICATIONS_ASYNC_ENABLED=False

# Payments
COD_ENABLED=True
RAZORPAY_ENABLED=False
WAVE_ENABLED=False
ORANGE_MONEY_ENABLED=False
MTN_MONEY_ENABLED=False

# Future external notifications remain inactive for the pilot.
EMAIL_NOTIFICATIONS_ENABLED=False
EMAIL_NOTIFICATION_SUBJECT_PREFIX=[T-Food] 
SMS_NOTIFICATIONS_ENABLED=False
WHATSAPP_NOTIFICATIONS_ENABLED=False
PUSH_NOTIFICATIONS_ENABLED=False
TELEGRAM_NOTIFICATIONS_ENABLED=False
```

To enable email notifications later, configure SMTP credentials in `.env`,
set `EMAIL_NOTIFICATIONS_ENABLED=True`, and keep SMS/WhatsApp disabled until
real providers are selected and tested. Email delivery remains an observer:
failed email sends are logged as delivery attempts and do not block orders,
payments, dispatch, delivery, or ledger workflows.

Generate strong secrets on the VPS:

```bash
python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(64))
PY
```

Never commit `.env`.

## 7. Compose Validation and Build

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.prod.yml build backend frontend celery_worker celery_beat dispatch_worker
```

## 8. First Production Start

Start database and Redis first:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d db redis
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

Run migrations explicitly:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backend python manage.py migrate
```

Collect static explicitly:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backend python manage.py collectstatic --noinput
```

Start application services:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d backend frontend celery_worker celery_beat dispatch_worker
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

Expected services:

- `backend` healthy
- `frontend` healthy
- `db` healthy
- `redis` healthy
- `celery_worker` running
- `celery_beat` running
- `dispatch_worker` running

## 9. Host Nginx Reverse Proxy

Create `/etc/nginx/sites-available/tfood`:

```nginx
server {
    listen 80;
    server_name <domain> www.<domain>;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        proxy_pass http://127.0.0.1:8088;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8088;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

Enable it:

```bash
sudo ln -s /etc/nginx/sites-available/tfood /etc/nginx/sites-enabled/tfood
sudo nginx -t
sudo systemctl reload nginx
```

## 10. Let's Encrypt HTTPS

Issue certificate:

```bash
sudo certbot --nginx -d <domain> -d www.<domain>
```

If you are not using `www`, issue only the canonical domain:

```bash
sudo certbot --nginx -d <domain>
```

Test renewal:

```bash
sudo certbot renew --dry-run
```

After HTTPS works, confirm `.env` has:

```env
SECURE_SSL_REDIRECT=True
PUBLIC_APP_URL=https://<domain>
CSRF_TRUSTED_ORIGINS=https://<domain>,https://www.<domain>
CORS_ALLOWED_ORIGINS=https://<domain>,https://www.<domain>
```

Restart app services after env changes:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d backend frontend celery_worker celery_beat dispatch_worker
```

## 11. Health Verification

```bash
curl -I https://<domain>/
curl -i https://<domain>/api/v1/health/
curl -i 'https://<domain>/api/v1/health/?detail=1'
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

Expected:

- `/` returns HTTP `200`.
- `/api/v1/health/` returns `status: ok`.
- Detailed health reports database, cache, media storage, channel layer, and worker heartbeats.
- No health response exposes secrets or private media paths.

Check logs:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 celery_worker
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 celery_beat
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 dispatch_worker
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 frontend
```

## 12. Create Pilot Accounts

Create accounts through the UI where possible. For emergency bootstrap, create the first superuser inside the backend container:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend python manage.py createsuperuser
```

Pilot accounts to prepare:

- Customer
- Merchant owner
- Merchant staff
- Delivery partner
- Operations admin

Production rule:

- Superuser remains a developer/admin tool.
- Business operations users should use `OperationsStaffProfile`.
- Keep `ALLOW_LEGACY_GLOBAL_OPERATIONS_ACCESS=False`.

## 13. Pilot Smoke Test

Before inviting users, run:

1. Register/login as customer.
2. Browse restaurant/branch.
3. Create COD order.
4. Login as merchant owner.
5. Accept order.
6. Move order to preparing.
7. Move order to ready for pickup.
8. Confirm dispatch worker creates delivery workflow.
9. Login as delivery partner.
10. Claim delivery.
11. Mark picked up.
12. Mark on the way.
13. Mark delivered.
14. Customer sees delivered order.
15. Customer submits review.
16. Customer uploads review photo.
17. Operations moderates review photo.
18. Customer receives notification.
19. Merchant receives order notification.
20. Operations dashboard loads.
21. Private media raw URLs remain inaccessible.

Use the full checklists:

- `docs/GUINEA_PILOT_LAUNCH_CHECKLIST.md`
- `docs/PILOT_SMOKE_TESTS.md`
- `docs/MANUAL_QA_CHECKLIST.md`

## 14. Backup Before Inviting Users

Do not invite pilot users until backups exist.

Run:

```bash
bash scripts/backup_db.sh
bash scripts/backup_media.sh
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T redis redis-cli BGSAVE
```

Confirm files exist:

```bash
ls -lah backups
find backups -maxdepth 2 -type f | sort
```

Backups must not be stored under public web roots.

## 15. Rollback

Before every deploy:

```bash
bash scripts/backup_db.sh
bash scripts/backup_media.sh
git rev-parse HEAD
```

Rollback application image/code:

```bash
cd ~/apps/t-food
git checkout <previous-known-good-commit>
cd work/T-food-clean
docker compose -f docker-compose.yml -f docker-compose.prod.yml build backend frontend celery_worker celery_beat dispatch_worker
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d backend frontend celery_worker celery_beat dispatch_worker
```

Database rollback is more serious. Prefer forward fixes after migrations. If restore is required, follow:

- `docs/BACKUP_RESTORE_RUNBOOK.md`

Stop affected services before a destructive restore.

## 16. Closed Beta Banner

If a config-based banner already exists, set:

```text
T-Food Guinea Pilot. This is a closed beta. Please report issues to support.
```

If no banner is available, document this message for the pilot communication channel and add the UI banner in a later low-risk release. Do not block deployment on this unless the pilot owner requires it.

## 17. First 24 Hours

Monitor:

- Orders
- COD order completion
- Dispatch worker heartbeat
- Celery worker heartbeat
- Redis/Postgres health
- Backend 5xx errors
- Frontend availability
- Support tickets
- Failed notifications
- Private media access denials
- Review photo moderation queue

Useful commands:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=200 backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=200 dispatch_worker
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=200 celery_worker
curl -i 'https://<domain>/api/v1/health/?detail=1'
```

## 18. Go / No-Go

Go only if:

- HTTPS works.
- Backend and frontend are healthy.
- Database and Redis are healthy.
- Celery worker, Celery beat, and dispatch worker are running.
- Migrations completed.
- Static files are served.
- Public/private media boundary is intact.
- Backup files exist.
- COD smoke order passed.
- Dispatch smoke passed.
- Operations dashboard smoke passed.
- Private media smoke passed.

No-Go if:

- Private media is publicly exposed.
- Ledger or payment state is inconsistent.
- Dispatch worker is down.
- Redis is down.
- Database is unhealthy.
- Backups do not exist.
- Health checks fail.
- Operations scope leakage is found.
