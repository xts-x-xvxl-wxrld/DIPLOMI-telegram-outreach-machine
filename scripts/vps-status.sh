#!/usr/bin/env bash
set -euo pipefail

env_name="${1:-staging}"

case "$env_name" in
  staging)
    deploy_path="${TG_OUTREACH_STAGING_PATH:-/srv/tg-outreach/staging}"
    default_health_url="${TG_OUTREACH_STAGING_HEALTH_URL:-http://127.0.0.1:8000}"
    ;;
  production)
    deploy_path="${TG_OUTREACH_PRODUCTION_PATH:-/srv/tg-outreach/production}"
    default_health_url="${TG_OUTREACH_PRODUCTION_HEALTH_URL:-http://127.0.0.1:8001}"
    ;;
  *)
    echo "Usage: vps-status.sh staging|production" >&2
    exit 2
    ;;
esac

project_prefix="${env_name}-tg-outreach"

echo "Environment: $env_name"
echo "Path: $deploy_path"
echo

if [ -d "$deploy_path/.git" ]; then
  echo "Git:"
  git -C "$deploy_path" status --short --branch || true
  git -C "$deploy_path" log -1 --oneline --decorate || true
else
  echo "Git: no checkout found at $deploy_path"
fi

echo
if [ -e "$deploy_path/.env" ]; then
  if [ -r "$deploy_path/.env" ]; then
    echo ".env: present and readable by current user"
  else
    echo ".env: present but not readable by current user"
  fi
else
  echo ".env: missing"
fi

echo
echo "Containers:"
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | {
  read -r header || true
  printf '%s\n' "$header"
  grep "^${project_prefix}-" || true
}

echo
echo "Health:"
curl -fsS "$default_health_url/health" || true
echo
curl -fsS "$default_health_url/ready" || true
echo

echo
echo "Published ports:"
for service in api postgres redis worker bot; do
  container="${project_prefix}-${service}-1"
  ports="$(docker port "$container" 2>/dev/null || true)"
  if [ -n "$ports" ]; then
    printf '%s:\n%s\n' "$container" "$ports"
  fi
done
