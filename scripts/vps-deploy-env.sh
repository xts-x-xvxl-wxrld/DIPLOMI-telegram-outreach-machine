#!/usr/bin/env bash
set -euo pipefail

env_name="${1:-}"
deploy_ref="${2:-origin/main}"

is_commit_sha() {
  case "$1" in
    ''|*[!0-9a-f]*) return 1 ;;
    *) [ "${#1}" -ge 7 ] && [ "${#1}" -le 40 ] ;;
  esac
}

case "$deploy_ref" in
  *[!A-Za-z0-9._/@-]*)
    echo "Ref contains unsupported characters: $deploy_ref" >&2
    exit 2
    ;;
esac

if [ -z "$env_name" ]; then
  echo "Usage: vps-deploy-env.sh staging|production [ref]" >&2
  exit 2
fi

case "$env_name" in
  staging)
    deploy_path="${TG_OUTREACH_STAGING_PATH:-/srv/tg-outreach/staging}"
    case "$deploy_ref" in
      origin/main|main|refs/heads/main|origin/agent/*|agent/*|refs/heads/agent/*)
        ;;
      *)
        if ! is_commit_sha "$deploy_ref"; then
          echo "Ref is not allowed for staging deploys: $deploy_ref" >&2
          exit 2
        fi
        ;;
    esac
    ;;
  production)
    deploy_path="${TG_OUTREACH_PRODUCTION_PATH:-/srv/tg-outreach/production}"
    case "$deploy_ref" in
      origin/main|main|refs/heads/main|refs/tags/v*|v*)
        ;;
      *)
        if ! is_commit_sha "$deploy_ref"; then
          echo "Ref is not allowed for production deploys: $deploy_ref" >&2
          exit 2
        fi
        ;;
    esac
    ;;
  *)
    echo "Usage: vps-deploy-env.sh staging|production [ref]" >&2
    exit 2
    ;;
esac

if [ ! -d "$deploy_path" ]; then
  echo "Deploy path does not exist: $deploy_path" >&2
  exit 1
fi
if [ ! -d "$deploy_path/.git" ]; then
  echo "Deploy path is not a Git checkout: $deploy_path" >&2
  exit 1
fi
if [ ! -f "$deploy_path/.env" ]; then
  echo "Missing .env for $env_name at $deploy_path/.env" >&2
  exit 1
fi

echo "Deploying $env_name from $deploy_ref"
cd "$deploy_path"
exec bash scripts/vps-deploy.sh "$deploy_ref"
