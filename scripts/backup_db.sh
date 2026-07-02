#!/usr/bin/env sh
set -eu

usage() {
  printf '%s\n' \
'Usage: scripts/backup_db.sh [--backup-dir DIR]' \
'' \
'Creates a timestamped PostgreSQL/PostGIS custom-format dump using Docker Compose.' \
'' \
'Environment:' \
'  POSTGRES_USER  Database user, default: tfood' \
'  POSTGRES_DB    Database name, default: tfood' \
'  BACKUP_DIR     Output directory, default: backups' \
'' \
'Examples:' \
'  scripts/backup_db.sh' \
'  BACKUP_DIR=/secure/backups scripts/backup_db.sh'
}

BACKUP_DIR="${BACKUP_DIR:-backups}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --backup-dir)
      BACKUP_DIR="${2:-}"
      shift 2
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

if [ -z "$BACKUP_DIR" ]; then
  echo "Backup directory cannot be empty." >&2
  exit 2
fi

mkdir -p "$BACKUP_DIR"
timestamp="$(date +%Y%m%d-%H%M%S)"
postgres_user="${POSTGRES_USER:-tfood}"
postgres_db="${POSTGRES_DB:-tfood}"
output="$BACKUP_DIR/tfood-db-$timestamp.dump"

echo "Creating PostgreSQL backup: $output"
docker compose exec -T db pg_dump \
  -U "$postgres_user" \
  -d "$postgres_db" \
  --format=custom \
  --no-owner \
  --no-privileges \
  > "$output"

if [ ! -s "$output" ]; then
  echo "Backup failed or produced an empty file: $output" >&2
  exit 1
fi

echo "Backup complete: $output"
