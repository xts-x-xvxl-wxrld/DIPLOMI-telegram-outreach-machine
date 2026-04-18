# VPS Agent Ops Context Plan

## Goal

Give VPS coding agents enough shared operational context to understand staging, production, logs,
health checks, and deployment paths without granting direct access to runtime secret files.

## Decisions

- Keep runtime secrets in `/etc/tg-outreach/*.env` and readable only by deployment/runtime users.
- Publish a redacted VPS map at `/srv/tg-outreach/AGENT_CONTEXT.md` for all agent users.
- Install non-secret helper commands under `/srv/tg-outreach/bin`:
  - `tg-outreach-status` for Git, container, health, and port visibility.
  - `tg-outreach-logs` for bounded Docker log reads by environment/service.
  - `tg-outreach-deploy` for validated staging/production deploy invocations.
- Let GitHub Actions deploy staging automatically after CI on `main`.
- Let GitHub Actions deploy staging or production manually through separate GitHub environments.
- Keep production deployment gated by GitHub protected environments or a deliberately installed
  release sudoers group; ordinary coding agents should not direct-deploy production.
- Make Docker host bindings configurable through env vars so staging and production can coexist on
  the same VPS without colliding on host ports.

## Acceptance Criteria

- Agents can read a single VPS context document that explains paths, users, groups, rules, and safe
  commands.
- Agents can inspect status and logs without reading `.env`.
- Staging deploys can be invoked by GitHub Actions or authorized agents through a wrapper.
- Production deploys can be invoked by GitHub Actions with the `production` environment or by an
  explicit release group wrapper installation.
- GitHub deployment logic calls the repo deploy script instead of duplicating the deployment recipe.
- The deployment spec, README, wiki index, and log describe the staging/production model.
