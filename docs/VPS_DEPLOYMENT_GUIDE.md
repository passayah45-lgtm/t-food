# T-Food VPS Deployment Guide

Target: one small VPS, one founder operator, Docker Compose, domain, HTTPS, backups, and launch smoke tests.

This guide assumes the current production services stay together on one server:

- `frontend`
- `backend`
- `dispatch_worker`
- `celery_worker`
- `celery_beat`
- `db`
- `redis`

Do not remove `dispatch_worker` during this launch phase.

Use the production overlay for launch:

```bash
export COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml
```

The overlay keeps local compatibility in `docker-compose.yml` while production
uses stricter defaults for `APP_ENV`, migrations, static collection, legacy
operations access, public media, and private media.

## 1. VPS Baseline

Recommended starting VPS:

- 2 vCPU minimum.
- 4 GB RAM minimum.
- 60 GB SSD minimum.
- Ubuntu LTS.
- Daily VPS provider snapshots enabled if available.

Create a non-root deploy user:

```bash
adduser deploy
usermod -aG sudo deploy
usermod -aG docker deploy
```

Use SSH keys only. Disable password SSH after confirming key login works.

## 2. Firewall

Open only the public ports needed for launch:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

Do not expose PostgreSQL or Redis publicly. They should remain inside the Docker network.

## 3. Install Runtime

Install Docker Engine and Compose plugin using Docker's official Ubuntu instructions, then verify:

```bash
docker --version
docker compose version
```

Log out and back in after adding the deploy user to the Docker group.

## 4. Cloudflare DNS

In Cloudflare, add:

| Type | Name | Value | Proxy |
|---|---|---|---|
| `A` | `@` | VPS public IPv4 | Proxied or DNS only |
| `A` | `www` | VPS public IPv4 | Proxied or DNS only |

Recommended launch settings:

- SSL/TLS mode: `Full (strict)` after origin certificate works.
- Always Use HTTPS: enabled.
- Automatic HTTPS Rewrites: enabled.
- Minimum TLS Version: TLS 1.2.
- Cache level: standard.
- Do not cache `/api/*`, `/admin/*`, `/media/*` aggressively.

If using Cloudflare proxy, keep your VPS firewall open for ports `80` and `443`.

## 5. HTTPS Options

Use one of these simple options.

### Option A: VPS Nginx + Certbot

Install Nginx and Certbot on the VPS:

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

Create `/etc/nginx/sites-available/tfood`:

```nginx
server {
    listen 80;
    server_name your-domain.example www.your-domain.example;

    location / {
        proxy_pass http://127.0.0.1:8088;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable it:

```bash
sudo ln -s /etc/nginx/sites-available/tfood /etc/nginx/sites-enabled/tfood
sudo nginx -t
sudo systemctl reload nginx
```

Issue the certificate:

```bash
sudo certbot --nginx -d your-domain.example -d www.your-domain.example
```

Then set:

```env
APP_PORT=8088
SECURE_SSL_REDIRECT=True
PUBLIC_APP_URL=https://your-domain.example
```

### Option B: Cloudflare Origin Certificate

Use this if Cloudflare is always in front of the VPS.

1. Cloudflare dashboard -> SSL/TLS -> Origin Server.
2. Create an origin certificate for `your-domain.example` and `*.your-domain.example`.
3. Install the certificate on VPS Nginx.
4. Set Cloudflare SSL/TLS mode to `Full (strict)`.

Use Option A first if you want the fewest moving parts.

## 6. Repository Setup

Clone the repository:

```bash
mkdir -p ~/apps
cd ~/apps
git clone <your-repository-url> t-food
cd t-food/work/T-food-clean
```

Create the environment file:

```bash
cp .env.example .env
nano .env
```

Minimum production values:

```env
DEBUG=False
APP_ENV=production
DJANGO_SECRET_KEY=replace-with-long-random-secret
POSTGRES_DB=tfood
POSTGRES_USER=tfood
POSTGRES_PASSWORD=replace-with-long-random-password
ALLOWED_HOSTS=your-domain.example,www.your-domain.example
CSRF_TRUSTED_ORIGINS=https://your-domain.example,https://www.your-domain.example
CORS_ALLOWED_ORIGINS=https://your-domain.example,https://www.your-domain.example
SECURE_SSL_REDIRECT=True
APP_PORT=8088
PUBLIC_APP_URL=https://your-domain.example
PUBLIC_MEDIA_ROOT=/app/media
PRIVATE_MEDIA_ROOT=/app/private_media
ALLOW_LEGACY_GLOBAL_OPERATIONS_ACCESS=False
RUN_MIGRATIONS=False
RUN_COLLECTSTATIC=False
MONITORING_ENABLED=True
METRICS_ENABLED=True
ERROR_REPORTING_ENABLED=False
SEED_DEMO_DATA=False
NOTIFICATIONS_ASYNC_ENABLED=False
```

Generate secrets on the VPS:

```bash
python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(64))
PY
```

Never commit `.env`.

## 7. First Deploy

Validate production Compose:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet
```

Build and start:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml build backend dispatch_worker celery_worker celery_beat frontend
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d db redis
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backend python manage.py migrate
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backend python manage.py collectstatic --noinput
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d backend dispatch_worker celery_worker celery_beat frontend
docker compose ps
```

If old Docker volumes cause permission errors after the non-root Docker change, do not delete volumes. Run:

```bash
docker compose run --rm --user root --entrypoint sh backend -c "chown -R app:app /app/staticfiles /app/media /app"
docker compose up -d backend dispatch_worker celery_worker celery_beat frontend
```

## 8. Health Checks

Service status:

```bash
docker compose ps
```

Expected:

- `backend` healthy.
- `frontend` running.
- `dispatch_worker` running.
- `celery_worker` running.
- `celery_beat` running.
- `db` healthy.
- `redis` healthy.

Logs:

```bash
docker compose logs --tail=100 backend
docker compose logs --tail=100 dispatch_worker
docker compose logs --tail=100 celery_worker
docker compose logs --tail=100 celery_beat
```

Public URLs:

```bash
curl -I https://your-domain.example/
curl -i https://your-domain.example/api/v1/health/
curl -i https://your-domain.example/api/v1/health/?detail=1
```

Expected:

- Frontend returns `200`.
- Health endpoint returns `{"status":"ok"}`.
- Detailed health reports database, Redis/cache, media storage, channel layer,
  Celery worker, Celery Beat, and dispatch worker readiness.
- Health response includes `X-Correlation-ID`.
- No Celery root-user warning.
- No permission errors.

## 9. Safe Deploy Routine

Before every deploy:

```bash
mkdir -p backups
docker compose exec -T db pg_dump -U ${POSTGRES_USER:-tfood} -d ${POSTGRES_DB:-tfood} --format=custom > backups/tfood-before-deploy-$(date +%Y%m%d-%H%M%S).dump
docker run --rm -v t-food-clean_media_data:/media -v "$PWD/backups:/backups" alpine tar -czf /backups/media-before-deploy-$(date +%Y%m%d-%H%M%S).tar.gz -C /media .
```

Deploy:

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.prod.yml build backend dispatch_worker celery_worker celery_beat frontend
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d db redis
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backend python manage.py migrate
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backend python manage.py collectstatic --noinput
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d backend dispatch_worker celery_worker celery_beat frontend
docker compose ps
```

Then run health checks and the launch smoke test.

## 10. Backups

Create backup directory:

```bash
mkdir -p backups
```

PostgreSQL:

```bash
scripts/backup_db.sh
```

Redis:

```bash
docker compose exec -T redis redis-cli BGSAVE
docker run --rm -v t-food-clean_redis_data:/redis -v "$PWD/backups:/backups" alpine tar -czf /backups/redis-$(date +%Y%m%d-%H%M%S).tar.gz -C /redis .
```

Public and private media:

```bash
scripts/backup_media.sh
```

Copy backups off the VPS:

```bash
rsync -avz deploy@your-vps-ip:~/apps/t-food/work/T-food-clean/backups/ ./tfood-backups/
```

Backup frequency for launch:

- PostgreSQL: daily and before every deploy.
- Public media: daily and before every deploy.
- Private media: daily and before every deploy.
- Redis: daily while Celery and cache data matter.
- VPS snapshot: daily if provider supports it.

## 11. Restore Drill

Run this before public launch on a test VPS or during a planned maintenance window.

Stop writers:

```bash
docker compose stop backend dispatch_worker celery_worker celery_beat
```

Restore PostgreSQL:

```bash
scripts/restore_db.sh --file backups/tfood-db-YYYYMMDD-HHMMSS.dump --confirm-restore
```

Restore media:

```bash
scripts/restore_media.sh --public-file backups/tfood-public-media-YYYYMMDD-HHMMSS.tar.gz --private-file backups/tfood-private-media-YYYYMMDD-HHMMSS.tar.gz --confirm-restore
```

Start services:

```bash
docker compose up -d backend dispatch_worker celery_worker celery_beat frontend
docker compose exec -T backend python manage.py migrate
docker compose ps
```

Restore verification:

```bash
curl -i https://your-domain.example/api/v1/health/
docker compose logs --tail=100 backend
docker compose logs --tail=100 celery_worker
docker compose logs --tail=100 celery_beat
```

Then run the launch smoke test.

## 12. Launch Smoke Test

Run this manually using test accounts or real first-launch accounts:

1. Customer logs in.
2. Customer browses restaurants.
3. Customer opens a restaurant.
4. Customer adds item and options.
5. Customer checks out with COD.
6. Confirm `order.created` outbox event exists.
7. Merchant logs in.
8. Merchant moves order to `PREPARING`.
9. Merchant moves order to `READY_FOR_PICKUP`.
10. Confirm `order.status_changed` events exist.
11. Delivery partner logs in.
12. Partner sees available delivery.
13. Partner claims delivery.
14. Partner marks `PICKED_UP`.
15. Partner marks `ON_THE_WAY`.
16. Partner marks `DELIVERED` with customer handoff code.
17. Customer tracking shows `DELIVERED`.
18. Run outbox relay:

```bash
docker compose exec -T backend python manage.py relay_outbox_events --limit 100
```

19. Confirm order events are published.

Useful database checks:

```bash
docker compose exec -T backend python manage.py shell -c "from events.models import OutboxEvent; print(OutboxEvent.objects.values('event_name','status').order_by('-created_at')[:10])"
```

## 13. Rollback

If a deploy fails before launch traffic:

```bash
docker compose logs --tail=200 backend
docker compose logs --tail=200 celery_worker
docker compose logs --tail=200 celery_beat
git log --oneline -5
```

Return to the previous known-good commit:

```bash
git checkout <previous-good-commit>
docker compose -f docker-compose.yml -f docker-compose.prod.yml build backend dispatch_worker celery_worker celery_beat frontend
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d backend dispatch_worker celery_worker celery_beat frontend
```

Do not blindly reverse database migrations after production traffic. If a
migration must be rolled back, restore the pre-deploy database backup into a
maintenance window or use a tested reversible migration plan.

If Celery alone is failing:

```bash
docker compose stop celery_worker celery_beat
```

Keep `dispatch_worker` running as the compatibility fallback during launch.

## 14. Daily Founder Routine

Morning:

```bash
docker compose ps
curl -i https://your-domain.example/api/v1/health/
docker compose logs --tail=50 backend
docker compose logs --tail=50 celery_worker
docker compose logs --tail=50 celery_beat
```

Evening:

```bash
mkdir -p backups
docker compose exec -T db pg_dump -U ${POSTGRES_USER:-tfood} -d ${POSTGRES_DB:-tfood} --format=custom > backups/tfood-$(date +%Y%m%d-%H%M%S).dump
docker run --rm -v t-food-clean_media_data:/media -v "$PWD/backups:/backups" alpine tar -czf /backups/media-$(date +%Y%m%d-%H%M%S).tar.gz -C /media .
```

Check:

- Any failed orders.
- Any unclaimed deliveries.
- Any merchant complaints.
- Disk usage:

```bash
df -h
docker system df
```

Do not run destructive Docker cleanup commands unless backups are already verified.
