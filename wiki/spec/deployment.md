# Deployment Spec

## Goal

Deploy the app to a VPS without letting production runtime state, server-only secrets, or coding
agent work-in-progress create Git conflicts or inconsistent Docker builds.

## Repository Roles

Use separate checkouts on the VPS:

| Checkout | Purpose | Allowed writes |
|---|---|---|
| `/srv/telegram-outreach/deploy` | production Docker Compose checkout | `.env` only |
| `/srv/telegram-outreach/agent-work` or worktrees | coding-agent edits | feature branches only |

The deploy checkout is reset-only. No human or agent should edit application source there.

## Git Flow

```text
local dev or VPS agent branch
  -> push branch to GitHub
  -> CI: ruff, pytest, Docker build
  -> merge to main
  -> deploy workflow resets VPS deploy checkout to origin/main
  -> Docker Compose rebuilds and restarts services
```

Agents on the VPS must create branches named `agent/<short-task>` and push them to GitHub. They must
not commit directly to `main` from the VPS.

Every completed agent change slice that modifies the wiki or codebase must be committed and pushed
to the current branch. Agents must inspect `git status` before staging and commit only the files that
belong to their slice unless the worktree is intentionally dedicated to that task. `git ci` is safe
only in a clean task branch because it stages all changes with `git add -A`.

## CI

GitHub Actions runs on every branch push and pull request:

- install Python 3.12 dependencies with development extras
- run `ruff check .`
- run `pytest -q`
- build the Docker image

The Docker build is a consistency check only. Runtime secrets are not available to CI.

## Deployment

Deployment is triggered by successful CI completion on `main` or by manual workflow dispatch. The
CI-triggered deploy uses the exact commit SHA that passed CI. The deployment process:

1. Connects to the VPS over SSH with strict host-key checking.
2. Changes into the deploy checkout.
3. Requires a local `.env` file to exist.
4. Fetches `origin`.
5. Runs `git reset --hard origin/main`.
6. Runs `git clean -ffdx` with explicit exclusions for `.env` and local runtime directories.
7. Builds the app images.
8. Starts Postgres and Redis.
9. Waits for Postgres readiness.
10. Runs `alembic upgrade head` inside the API container.
11. Runs `docker compose up -d --remove-orphans`.

This makes the source tree deterministic while preserving server-only secrets and Docker volume
mount directories.

## Secrets

Application secrets live only in `.env` on the VPS and local developer machines. `.env` must never
be committed or sent in Docker build context.

GitHub deployment secrets are limited to SSH deployment metadata:

- `VPS_HOST`
- `VPS_USER`
- `VPS_SSH_PORT`
- `VPS_SSH_KEY`
- `VPS_SSH_KNOWN_HOSTS`
- `VPS_DEPLOY_PATH`

The deploy workflow must not contain app runtime secrets such as Telegram, OpenAI, database, or bot
tokens.

## Docker Build Context

`.dockerignore` excludes Git metadata, GitHub workflow files, local env files, Python caches, logs,
virtual environments, and local data directories from Docker build context.

## Rollback

Rollback is done by dispatching the deploy workflow against a known-good commit or by manually
running the deploy script with a commit SHA:

```bash
bash scripts/vps-deploy.sh <commit-sha>
```

Database migrations are not automatically rolled back. Schema rollback requires a separate explicit
database plan.
