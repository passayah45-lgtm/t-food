#!/usr/bin/env sh
set -eu

usage() {
  printf '%s\n' \
'Usage: scripts/restore_media.sh [--public-file FILE] [--private-file FILE] --confirm-restore' \
'' \
'Restores T-Food media archives into Docker Compose media volumes.' \
'This is destructive for each selected media volume.' \
'' \
'Environment:' \
'  COMPOSE_PROJECT_NAME  Compose project prefix, default: current directory name' \
'' \
'Examples:' \
'  scripts/restore_media.sh --public-file backups/tfood-public-media-YYYYMMDD-HHMMSS.tar.gz --confirm-restore' \
'  scripts/restore_media.sh --private-file backups/tfood-private-media-YYYYMMDD-HHMMSS.tar.gz --confirm-restore'
}

public_file=""
private_file=""
confirmed="False"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --public-file)
      public_file="${2:-}"
      shift 2
      ;;
    --private-file)
      private_file="${2:-}"
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

if [ -z "$public_file" ] && [ -z "$private_file" ]; then
  echo "Provide --public-file, --private-file, or both." >&2
  exit 2
fi

project_name="${COMPOSE_PROJECT_NAME:-${PWD##*/}}"

docker_host_pwd() {
  if command -v pwd >/dev/null 2>&1 && pwd -W >/dev/null 2>&1; then
    pwd -W
  else
    pwd
  fi
}

host_pwd="$(docker_host_pwd)"

restore_volume() {
  volume_name="$1"
  archive_file="$2"
  label="$3"

  if [ ! -f "$archive_file" ]; then
    echo "${label} media archive does not exist: $archive_file" >&2
    exit 2
  fi

  archive_dir="${archive_file%/*}"
  archive_base="${archive_file##*/}"
  if [ "$archive_dir" = "$archive_file" ]; then
    archive_dir="."
  fi

  echo "Restoring ${label} media into volume ${volume_name} from ${archive_file}"
  MSYS_NO_PATHCONV=1 docker run --rm \
    -v "${volume_name}:/media" \
    -v "${host_pwd}/${archive_dir}:/backups:ro" \
    alpine \
    sh -c "rm -rf /media/* && tar -xzf /backups/${archive_base} -C /media"
}

if [ -n "$public_file" ]; then
  restore_volume "${project_name}_media_data" "$public_file" "public"
fi

if [ -n "$private_file" ]; then
  restore_volume "${project_name}_private_media_data" "$private_file" "private"
fi

echo "Media restore complete. Restart services and run smoke checks."
