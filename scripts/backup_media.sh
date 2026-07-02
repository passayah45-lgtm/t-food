#!/usr/bin/env sh
set -eu

usage() {
  printf '%s\n' \
'Usage: scripts/backup_media.sh [--backup-dir DIR] [--public-only|--private-only]' \
'' \
'Creates timestamped archives for T-Food public and private media Docker volumes.' \
'' \
'Public media:' \
'  restaurant images, menu/product images, approved review photos.' \
'' \
'Private media:' \
'  verification documents, pending/rejected/hidden review photos, private uploads.' \
'' \
'Environment:' \
'  COMPOSE_PROJECT_NAME  Compose project prefix, default: current directory name' \
'  BACKUP_DIR            Output directory, default: backups'
}

BACKUP_DIR="${BACKUP_DIR:-backups}"
include_public="True"
include_private="True"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --backup-dir)
      BACKUP_DIR="${2:-}"
      shift 2
      ;;
    --public-only)
      include_private="False"
      shift
      ;;
    --private-only)
      include_public="False"
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

if [ -z "$BACKUP_DIR" ]; then
  echo "Backup directory cannot be empty." >&2
  exit 2
fi

mkdir -p "$BACKUP_DIR"
timestamp="$(date +%Y%m%d-%H%M%S)"
project_name="${COMPOSE_PROJECT_NAME:-${PWD##*/}}"

docker_host_pwd() {
  if command -v pwd >/dev/null 2>&1 && pwd -W >/dev/null 2>&1; then
    pwd -W
  else
    pwd
  fi
}

host_pwd="$(docker_host_pwd)"

backup_volume() {
  volume_name="$1"
  label="$2"
  output="/backups/tfood-${label}-media-${timestamp}.tar.gz"
  echo "Creating ${label} media backup from volume ${volume_name}: ${BACKUP_DIR}/${output##*/}"
  MSYS_NO_PATHCONV=1 docker run --rm \
    -v "${volume_name}:/media:ro" \
    -v "${host_pwd}/${BACKUP_DIR}:/backups" \
    alpine \
    tar -czf "$output" -C /media .
}

if [ "$include_public" = "True" ]; then
  backup_volume "${project_name}_media_data" "public"
fi

if [ "$include_private" = "True" ]; then
  backup_volume "${project_name}_private_media_data" "private"
fi

echo "Media backup complete."
