#!/usr/bin/env bash
set -euo pipefail

env_name="${1:-}"
service="${2:-}"
lines="${3:-120}"

if [ -z "$env_name" ] || [ -z "$service" ]; then
  echo "Usage: vps-logs.sh staging|production api|worker|scheduler|bot|postgres|redis|all [lines]" >&2
  exit 2
fi

case "$env_name" in
  staging|production) ;;
  *)
    echo "Unknown environment: $env_name" >&2
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

print_logs() {
  local service_name="$1"
  local container="${env_name}-tg-outreach-${service_name}-1"

  docker logs --timestamps --tail "$lines" "$container"
}

case "$service" in
  api|worker|scheduler|bot|postgres|redis)
    print_logs "$service"
    ;;
  all)
    for service_name in "${services[@]}"; do
      printf '===== %s =====\n' "$service_name"
      print_logs "$service_name" || true
      printf '\n'
    done
    ;;
  *)
    echo "Unknown service: $service" >&2
    exit 2
    ;;
esac
