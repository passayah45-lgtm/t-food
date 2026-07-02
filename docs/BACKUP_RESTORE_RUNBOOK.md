# T-Food Backup and Restore Runbook

This runbook is mandatory before the Guinea pilot. Backups must protect the
database, public media, and private media. Redis is operational acceleration,
not the source of truth.

## What Must Be Backed Up

PostgreSQL/PostGIS is the source of truth for:

- users and authentication records
- customers, merchants, branches, riders, and staff
- orders, payments, refunds, payouts, and ledger records
- notifications and preferences
- verification metadata and document references
- operations access profiles and audit data
- visual search events and review photo records

Public media volume `media_data` contains:

- restaurant cover images
- menu/product images
- approved review photos
- public category or marketplace assets

Private media volume `private_media_data` contains:

- merchant verification documents
- partner verification documents
- staff verification documents
- pending, rejected, or hidden review photos
- future private operations uploads

Private media must never be restored into the public media volume.

## Backup Schedule

- PostgreSQL/PostGIS: daily and before every deployment.
- Public media: daily and before every deployment.
- Private media: daily and before every deployment.
- Redis: optional snapshot for operational recovery; daily during pilot is fine.
- VPS or disk snapshot: daily if the provider supports it.
- Off-server copy: after every backup job.

For launch, keep at least:

- 7 daily backups
- 4 weekly backups
- 3 monthly backups after the pilot stabilizes

## Backup Commands

Create the backup directory outside any public web root:

```bash
mkdir -p backups
```

Database:

```bash
scripts/backup_db.sh
```

Public and private media:

```bash
scripts/backup_media.sh
```

Public media only:

```bash
scripts/backup_media.sh --public-only
```

Private media only:

```bash
scripts/backup_media.sh --private-only
```

Redis snapshot:

```bash
docker compose exec -T redis redis-cli BGSAVE
```

Copy backups off the VPS:

```bash
rsync -avz ./backups/ operator@backup-host:/secure/tfood-backups/
```

## Restore Procedure

Run restores only during a planned maintenance window or on an isolated restore
drill host. Do not restore directly onto production without a verified rollback
plan.

Stop writers:

```bash
docker compose stop backend dispatch_worker celery_worker celery_beat
```

Restore the database into a clean database:

```bash
scripts/restore_db.sh --file backups/tfood-db-YYYYMMDD-HHMMSS.dump --confirm-restore
```

Restore media:

```bash
scripts/restore_media.sh \
  --public-file backups/tfood-public-media-YYYYMMDD-HHMMSS.tar.gz \
  --private-file backups/tfood-private-media-YYYYMMDD-HHMMSS.tar.gz \
  --confirm-restore
```

Run migrations after restore:

```bash
docker compose run --rm backend python manage.py migrate
```

Restart runtime services:

```bash
docker compose up -d backend dispatch_worker celery_worker celery_beat frontend
```

## Restore Verification Checklist

After restore, verify:

- `docker compose ps` shows backend, frontend, db, and redis healthy.
- `http://127.0.0.1:8088/` returns 200.
- `/api/v1/health/` returns 200.
- users can log in.
- orders, payments, ledger entries, notifications, branches, merchant staff, and operations profiles exist.
- approved review photos and restaurant/menu images render publicly.
- pending/rejected/hidden review photos are not public.
- verification documents are accessible only through authenticated private endpoints.
- ledger audit views show no financial integrity regression.
- customer, merchant, partner, and operations smoke flows still work.

## Redis Recovery

Redis stores cache, rate-limit counters, Channels state, Celery broker data, and
Celery result data. Redis is not the source of truth for orders, payments,
ledger, dispatch claims, verification decisions, or customer records.

If Redis is lost:

- restart Redis and application services.
- expect cache misses and rebuilt dashboard summaries.
- expect websocket clients to reconnect.
- inspect Celery queues because in-flight tasks may be lost.
- run scheduled maintenance tasks again if needed.
- do not restore stale Redis data if it could reintroduce old Celery broker
  messages.

Redis data loss is acceptable only when no critical Celery tasks are pending, or
after operators confirm those tasks can be safely retried from database state.

## Security Requirements

- Never commit backups.
- Never store backups under `/media`, `/static`, frontend public assets, or any
  public web root.
- Private media backups must be protected like identity documents.
- Backup filenames must not include credentials or customer names.
- Production backups should be encrypted before leaving the server.
- Restrict backup directory permissions to the deployment operator.

## Future Object Storage Plan

Before multi-server deployment, move media to object storage:

- public media bucket for CDN-safe approved assets
- private media bucket with blocked public access
- signed URLs or authenticated proxy endpoints for private media
- bucket versioning and lifecycle policies
- encrypted backup/export bucket

The database remains the source of truth for media metadata and moderation
state.
