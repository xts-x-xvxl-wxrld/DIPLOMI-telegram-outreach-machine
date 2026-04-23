#!/usr/bin/env bash
set -euo pipefail

env_name="${1:-staging}"
lines="${2:-300}"
diag_root="${TG_OUTREACH_DIAGNOSTICS_DIR:-/srv/tg-outreach/diagnostics}"

case "$env_name" in
  staging|production) ;;
  *)
    echo "Usage: vps-diagnostics.sh staging|production [lines]" >&2
    exit 2
    ;;
esac

case "$lines" in
  ''|*[!0-9]*)
    echo "lines must be a positive integer" >&2
    exit 2
    ;;
esac

if [ "$lines" -lt 1 ] || [ "$lines" -gt 5000 ]; then
  echo "lines must be between 1 and 5000" >&2
  exit 2
fi

services=(api worker scheduler bot postgres redis)
project_prefix="${env_name}-tg-outreach"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"

umask 022
mkdir -p "$diag_root"
work_dir="$(mktemp -d "$diag_root/${env_name}-diagnostics-${stamp}.XXXXXX")"
archive="$work_dir.tar.gz"

run_status() {
  if [ -x "$script_dir/tg-outreach-status" ]; then
    "$script_dir/tg-outreach-status" "$env_name"
  else
    "$script_dir/vps-status.sh" "$env_name"
  fi
}

{
  echo "environment=$env_name"
  echo "created_at_utc=$stamp"
  echo "lines=$lines"
  echo "host=$(hostname)"
  echo "user=$(id -un)"
} > "$work_dir/manifest.txt"

run_status > "$work_dir/status.txt" 2>&1 || true
docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' > "$work_dir/docker-ps.txt" 2>&1 || true

for service_name in "${services[@]}"; do
  container="${project_prefix}-${service_name}-1"
  docker inspect \
    --format '{{.Name}} {{.State.Status}} started={{.State.StartedAt}} finished={{.State.FinishedAt}} exit={{.State.ExitCode}} oom={{.State.OOMKilled}}' \
    "$container" > "$work_dir/${service_name}-inspect.txt" 2>&1 || true
  docker logs --timestamps --tail "$lines" "$container" > "$work_dir/${service_name}.log" 2>&1 || true
done

tar -C "$diag_root" -czf "$archive" "$(basename "$work_dir")"
rm -rf "$work_dir"
chmod 0644 "$archive"

echo "$archive"
