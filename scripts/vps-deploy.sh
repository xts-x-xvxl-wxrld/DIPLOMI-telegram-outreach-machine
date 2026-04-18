#!/usr/bin/env bash
set -euo pipefail

deploy_ref="${1:-origin/main}"

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "vps-deploy.sh must be run inside the deploy Git checkout." >&2
  exit 1
fi

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

if [ ! -f .env ]; then
  echo "Missing .env in $repo_root. Create it from .env.example before deploying." >&2
  exit 1
fi

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
