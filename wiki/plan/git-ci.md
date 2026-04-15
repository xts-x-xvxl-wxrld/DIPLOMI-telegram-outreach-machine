# Git CI Convenience Plan

## Goal

Add a repo-local `git ci` workflow that stages all changed files and creates a commit with one command.

## Decisions

- Initialize this project as a Git repository if it is not already one.
- Keep the alias local to this repository rather than changing global Git config.
- Implement the behavior in `scripts/git-ci.ps1` because the project is currently operated from PowerShell.
- Keep `.env`, Python caches, virtual environments, logs, and local data volumes out of Git.

## Command Contract

```powershell
git ci "commit message"
```

Behavior:

- stages all tracked, modified, deleted, and untracked files with `git add -A`
- commits with the provided message
- if no message is provided, uses a timestamped default message
- exits successfully without committing when there are no staged changes

## Acceptance Criteria

- `git ci "message"` works from anywhere inside the repository.
- secrets and generated files are ignored by Git.
- local Git identity is configured enough for commits to succeed.
- wiki log records the change.
