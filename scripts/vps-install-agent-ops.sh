#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
target_root="${TG_OUTREACH_ROOT:-/srv/tg-outreach}"
target_bin="$target_root/bin"

mkdir -p "$target_bin"

install -m 0644 "$repo_root/ops/vps/AGENT_CONTEXT.md" "$target_root/AGENT_CONTEXT.md"
install -m 0755 "$repo_root/scripts/vps-status.sh" "$target_bin/tg-outreach-status"
install -m 0755 "$repo_root/scripts/vps-logs.sh" "$target_bin/tg-outreach-logs"
install -m 0755 "$repo_root/scripts/vps-diagnostics.sh" "$target_bin/tg-outreach-diagnostics"
install -m 0755 "$repo_root/scripts/vps-deploy-env.sh" "$target_bin/tg-outreach-deploy"

echo "Installed agent ops context:"
echo "  $target_root/AGENT_CONTEXT.md"
echo "  $target_bin/tg-outreach-status"
echo "  $target_bin/tg-outreach-logs"
echo "  $target_bin/tg-outreach-diagnostics"
echo "  $target_bin/tg-outreach-deploy"

cat <<'TXT'

Optional sudoers model:

  %tg-outreach-dev ALL=(deploy) NOPASSWD: /srv/tg-outreach/bin/tg-outreach-status *
  %tg-outreach-dev ALL=(deploy) NOPASSWD: /srv/tg-outreach/bin/tg-outreach-logs *
  %tg-outreach-dev ALL=(deploy) NOPASSWD: /srv/tg-outreach/bin/tg-outreach-diagnostics *
  %tg-outreach-dev ALL=(deploy) NOPASSWD: /srv/tg-outreach/bin/tg-outreach-deploy staging *

Use the status/log rules when coding agents should observe Docker state without joining the docker
group. Use the staging deploy rule only if coding agents may direct-deploy staging.
Production deploy sudoers are intentionally omitted until production is an active target.
TXT
