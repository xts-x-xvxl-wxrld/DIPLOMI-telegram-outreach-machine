#!/usr/bin/env bash
set -euo pipefail

deploy_ref="${1:-origin/main}"

print_lock_context() {
  local state_file="$1"

  if [ ! -f "$state_file" ]; then
    return
  fi

  echo "Current deploy lock state:" >&2
  sed 's/^/  /' "$state_file" >&2
}

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "vps-deploy.sh must be run inside the deploy Git checkout." >&2
  exit 1
fi

repo_root="$(git rev-parse --show-toplevel)"
lock_file="$(git rev-parse --git-path vps-deploy.lock)"
lock_state_file="$(git rev-parse --git-path vps-deploy.lock.info)"
lock_wait_seconds="${TG_OUTREACH_DEPLOY_LOCK_WAIT_SECONDS:-900}"
cd "$repo_root"

if [ ! -f .env ]; then
  echo "Missing .env in $repo_root. Create it from .env.example before deploying." >&2
  exit 1
fi

case "$lock_wait_seconds" in
  ''|*[!0-9]*)
    echo "TG_OUTREACH_DEPLOY_LOCK_WAIT_SECONDS must be a non-negative integer." >&2
    exit 2
    ;;
esac

if ! command -v flock >/dev/null 2>&1; then
  echo "Missing required command: flock" >&2
  exit 1
fi

mkdir -p "$(dirname "$lock_file")"

exec 9>"$lock_file"

if ! flock -n 9; then
  echo "Another deploy is already running for $repo_root; waiting up to ${lock_wait_seconds}s." >&2
  print_lock_context "$lock_state_file"

  if ! flock -w "$lock_wait_seconds" 9; then
    echo "Timed out waiting for the deploy lock after ${lock_wait_seconds}s." >&2
    print_lock_context "$lock_state_file"
    exit 1
  fi
fi

cat >"$lock_state_file" <<EOF
repo_root=$repo_root
deploy_ref=$deploy_ref
user=$(id -un)
host=$(hostname -f 2>/dev/null || hostname)
pid=$$
started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF
trap 'rm -f "$lock_state_file"' EXIT

origin_url="$(git remote get-url origin)"
case "$origin_url" in
  git@github.com:*)
    https_origin="https://github.com/${origin_url#git@github.com:}"
    git remote set-url origin "$https_origin"
    echo "Normalized origin remote to HTTPS: $https_origin"
    ;;
  ssh://git@github.com/*)
    https_origin="https://github.com/${origin_url#ssh://git@github.com/}"
    git remote set-url origin "$https_origin"
    echo "Normalized origin remote to HTTPS: $https_origin"
    ;;
esac

git fetch --prune origin
git reset --hard "$deploy_ref"
git clean -ffdx \
  -e .env \
  -e .env.local \
  -e sessions/ \
  -e telegram_sessions/ \
  -e postgres_data/ \
  -e redis_data/

docker compose build api worker bot
docker compose up -d postgres redis

for attempt in $(seq 1 30); do
  if docker compose exec -T postgres pg_isready -U postgres -d telegram_outreach; then
    break
  fi

  if [ "$attempt" -eq 30 ]; then
    echo "Postgres did not become ready in time." >&2
    exit 1
  fi

  sleep 2
done

docker compose run --rm api alembic upgrade head
docker compose up -d --remove-orphans
docker compose ps

api_port="$(docker compose port api 8000 2>/dev/null | tail -n 1 | awk -F: '{print $NF}')"
if [ -n "$api_port" ]; then
  curl -fsS "http://127.0.0.1:${api_port}/ready" || true
  echo
fi
