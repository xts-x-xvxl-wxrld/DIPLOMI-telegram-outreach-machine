# Deployment Spec

## Goal

Deploy the app to a VPS without letting staging runtime state, server-only secrets, or coding
agent work-in-progress create Git conflicts or inconsistent Docker builds.

## Repository Roles

Use separate checkouts on the VPS:

| Checkout | Purpose | Allowed writes |
|---|---|---|
| `/srv/tg-outreach/staging` | reset-only staging Docker Compose checkout | `.env` symlink/runtime directories only |
| `/srv/tg-outreach/production` | reserved future production Docker Compose checkout | not active yet |
| `/srv/tg-outreach/agent-worktrees` | coding-agent edits | feature branches only |
| `/srv/tg-outreach/AGENT_CONTEXT.md` | redacted VPS map for agents | operator/deploy maintenance only |
| `/srv/tg-outreach/bin` | non-secret status/log/deploy helpers | operator/deploy maintenance only |

Deploy checkouts are reset-only. No human or agent should edit application source there.

## Git Flow

```text
local dev or VPS agent branch
  -> push branch to GitHub
  -> CI: ruff, pytest, Docker build
  -> merge to main
  -> staging deploy workflow resets VPS staging checkout to the CI-tested commit
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

Agents should run the same local gates before committing and pushing code or wiki changes:
`python scripts/check_fragmentation.py`, `ruff check .`, and `pytest -q`. Run `docker build .`
locally when the slice changes packaging, dependencies, runtime startup, or Docker files. If a gate
cannot run locally, record the limitation in the wiki log and handoff instead of sending a surprise
failure to GitHub.

## Deployment

Staging deployment is triggered by successful CI completion on `main` or by manual workflow
dispatch. Production deployment is intentionally not wired into GitHub Actions yet.

The staging workflow calls the checkout-local deploy script:

```bash
bash scripts/vps-deploy.sh <ref-or-commit>
```

The GitHub workflow uses the `staging` GitHub environment, reads that environment's SSH metadata
secrets, connects to `VPS_DEPLOY_PATH`, and runs the script. The CI-triggered staging deploy uses
the exact commit SHA that passed CI.

The deployment process:

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

Manual deploys use the same script through the environment wrapper:

```bash
/srv/tg-outreach/bin/tg-outreach-deploy staging origin/main
```

Agents may inspect status and logs through `/srv/tg-outreach/bin/tg-outreach-status` and
`/srv/tg-outreach/bin/tg-outreach-logs`. If agent users are not in the Docker group, these helpers
should be exposed through narrow sudoers rules that run them as `deploy`. Direct deploy wrapper
access is also controlled by sudoers: ordinary agent users may be granted staging deploy permission.
Production deploy access should remain uninstalled until production is an active target.

## Secrets

Application secrets live only in `.env` on the VPS and local developer machines. `.env` must never
be committed or sent in Docker build context.

GitHub `staging` environment secrets are limited to SSH deployment metadata:

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

## Network Exposure

The API may be published by Docker Compose, but Postgres must not be exposed on a public interface.
Bind Postgres to `127.0.0.1` only so operators can still use local SSH tunnels while internet
clients cannot connect directly to the database container. Host bindings are configured with:

- `API_HOST_BIND`
- `API_HOST_PORT`
- `POSTGRES_HOST_BIND`
- `POSTGRES_HOST_PORT`

Future production must use distinct `COMPOSE_PROJECT_NAME`, API host port, Postgres host port, and
Docker volumes if it runs on the same VPS.

## Rollback

Rollback is done by dispatching the deploy workflow against a known-good commit or by manually
running the deploy script with a commit SHA:

```bash
bash scripts/vps-deploy.sh <commit-sha>
```

Database migrations are not automatically rolled back. Schema rollback requires a separate explicit
database plan.
