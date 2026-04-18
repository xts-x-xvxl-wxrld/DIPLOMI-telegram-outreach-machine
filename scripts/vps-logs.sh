#!/usr/bin/env bash
set -euo pipefail

env_name="${1:-}"
service="${2:-}"
lines="${3:-120}"

if [ -z "$env_name" ] || [ -z "$service" ]; then
  echo "Usage: vps-logs.sh staging|production api|worker|bot|postgres|redis [lines]" >&2
  exit 2
fi

case "$env_name" in
  staging|production) ;;
  *)
    echo "Unknown environment: $env_name" >&2
    exit 2
    ;;
esac

case "$service" in
  api|worker|bot|postgres|redis) ;;
  *)
    echo "Unknown service: $service" >&2
    exit 2
    ;;
esac

case "$lines" in
  ''|*[!0-9]*)
    echo "lines must be a positive integer" >&2
    exit 2
    ;;
esac

container="${env_name}-tg-outreach-${service}-1"
docker logs --tail "$lines" "$container"
