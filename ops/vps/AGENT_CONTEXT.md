# Telegram Outreach VPS Agent Context

This file is the safe, redacted map for coding agents on the VPS. It should be readable by agent
users, but it must not contain secrets.

## Paths

| Purpose | Path |
|---|---|
| Shared VPS root | `/srv/tg-outreach` |
| Staging deploy checkout | `/srv/tg-outreach/staging` |
| Production deploy checkout | `/srv/tg-outreach/production` reserved for future use |
| Shared helper commands | `/srv/tg-outreach/bin` |
| Agent worktrees | `/srv/tg-outreach/agent-worktrees` |
| Staging env file | `/etc/tg-outreach/staging.env` |
| Production env file | `/etc/tg-outreach/production.env` reserved for future use |

Agents must not read or print env files. Runtime secrets stay in `/etc/tg-outreach/*.env`.

## Users And Groups

| Name | Purpose |
|---|---|
| `deploy` | Owns reset-only deployment checkouts and runs Docker Compose deployments. |
| `ravil` | Operator SSH user. |
| `codex-ravil`, `codex-pink`, `claude-ravil` | Coding agent users. |
| `tg-outreach-dev` | Coding-agent group for development worktrees and non-secret context. |
| `tg-outreach-deploy` | Deployment checkout access group. |
| `tg-outreach-staging-config` | Staging secret-file access group. |

Only users that intentionally need runtime secrets should be added to config groups.

## Docker Compose Environments

| Environment | Checkout | Expected project name | Default API URL |
|---|---|---|---|
| `staging` | `/srv/tg-outreach/staging` | `staging-tg-outreach` | `http://127.0.0.1:8000` |
| `production` | `/srv/tg-outreach/production` | reserved | not active |

Future production must use separate `.env` files, Compose project names, host ports, and Docker
volumes. Postgres should bind to localhost only.

## Safe Commands

```bash
/srv/tg-outreach/bin/tg-outreach-status staging
/srv/tg-outreach/bin/tg-outreach-logs staging api
/srv/tg-outreach/bin/tg-outreach-logs staging worker 200
```

If the current user cannot access Docker directly, use the sudoers-gated form after the operator has
installed the narrow rules:

```bash
sudo -u deploy /srv/tg-outreach/bin/tg-outreach-status staging
sudo -u deploy /srv/tg-outreach/bin/tg-outreach-logs staging api
```

If sudoers has been explicitly installed for deploy wrappers:

```bash
sudo -u deploy /srv/tg-outreach/bin/tg-outreach-deploy staging origin/main
```

Production deploys are not wired yet. Do not direct-deploy production from an ordinary coding-agent
session.

## Agent Workflow

1. Read this file before touching VPS deployment behavior.
2. Work in an agent branch or worktree, never in a reset-only deploy checkout.
3. Push branches to GitHub and wait for CI.
4. Merge to `main` only when the change is ready for staging.
5. Use status and log helpers for diagnostics.
6. Do not edit `/srv/tg-outreach/staging` or `/srv/tg-outreach/production` by hand.
7. Do not print secrets, env files, session files, or token-bearing Docker config.

## GitHub Deployment Model

The deploy workflow uses the GitHub `staging` environment:

- `staging`: auto-deploys after CI succeeds on `main`; manual dispatch is also allowed.

The GitHub environment should define:

| Secret | Meaning |
|---|---|
| `VPS_HOST` | VPS hostname or IP. |
| `VPS_USER` | SSH user allowed to deploy, usually `deploy`. |
| `VPS_SSH_PORT` | SSH port, usually `22`. |
| `VPS_SSH_KEY` | Private SSH key for the deploy user. |
| `VPS_SSH_KNOWN_HOSTS` | Pinned host key line. |
| `VPS_DEPLOY_PATH` | Environment checkout path. |

Application runtime secrets are not GitHub Actions secrets. They remain in the VPS env files.
