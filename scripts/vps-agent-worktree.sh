#!/usr/bin/env bash
set -euo pipefail

branch_name="${1:-}"
base_ref="${2:-origin/main}"

if [ -z "$branch_name" ]; then
  echo "Usage: scripts/vps-agent-worktree.sh agent/branch-name [base-ref]" >&2
  exit 1
fi

case "$branch_name" in
  agent/*) ;;
  *)
    echo "Agent branch names must start with agent/." >&2
    exit 1
    ;;
esac

repo_root="$(git rev-parse --show-toplevel)"
worktree_root="$(dirname "$repo_root")/agent-worktrees"
worktree_path="$worktree_root/${branch_name#agent/}"

mkdir -p "$worktree_root"
git fetch --prune origin
git worktree add -B "$branch_name" "$worktree_path" "$base_ref"

echo "Created agent worktree: $worktree_path"
echo "Push with: git -C '$worktree_path' push -u origin '$branch_name'"
