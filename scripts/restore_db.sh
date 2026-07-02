#!/usr/bin/env sh
set -eu

usage() {
  printf '%s\n' \
'Usage: scripts/restore_db.sh --file FILE --confirm-restore' \
'' \
'Restores a PostgreSQL/PostGIS custom-format dump into a clean Docker Compose DB.' \
'This is destructive: it drops and recreates POSTGRES_DB.' \
'' \
'Environment:' \
'  POSTGRES_USER  Database user, default: tfood' \
'  POSTGRES_DB    Database name, default: tfood' \
'' \
'Example:' \
'  scripts/restore_db.sh --file backups/tfood-db-YYYYMMDD-HHMMSS.dump --confirm-restore'
}

backup_file=""
confirmed="False"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --file)
      backup_file="${2:-}"
      shift 2
      ;;
    --confirm-restore)
      confirmed="True"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ "$confirmed" != "True" ]; then
  echo "Refusing destructive restore without --confirm-restore." >&2
  exit 2
fi

if [ -z "$backup_file" ] || [ ! -f "$backup_file" ]; then
  echo "Backup file does not exist: $backup_file" >&2
  exit 2
fi

postgres_user="${POSTGRES_USER:-tfood}"
postgres_db="${POSTGRES_DB:-tfood}"

echo "Stopping application writers before database restore..."
docker compose stop backend dispatch_worker celery_worker celery_beat

echo "Dropping and recreating database: $postgres_db"
docker compose exec -T db dropdb -U "$postgres_user" --if-exists "$postgres_db"
docker compose exec -T db createdb -U "$postgres_user" "$postgres_db"

echo "Restoring database from: $backup_file"
docker compose exec -T db pg_restore \
  -U "$postgres_user" \
  -d "$postgres_db" \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  < "$backup_file"

echo "Database restore complete. Run migrations and smoke checks before reopening traffic."
