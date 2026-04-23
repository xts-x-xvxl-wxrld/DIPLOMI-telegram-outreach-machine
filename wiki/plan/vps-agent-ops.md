# VPS Agent Ops Context Plan

## Goal

Give VPS coding agents enough shared operational context to understand staging, reserved production
paths, logs, health checks, and deployment paths without granting direct access to runtime secret
files.

## Decisions

- Keep runtime secrets in `/etc/tg-outreach/*.env` and readable only by deployment/runtime users.
- Publish a redacted VPS map at `/srv/tg-outreach/AGENT_CONTEXT.md` for all agent users.
- Install non-secret helper commands under `/srv/tg-outreach/bin`:
  - `tg-outreach-status` for Git, container, health, and port visibility.
  - `tg-outreach-logs` for bounded Docker log reads by environment/service, including scheduler and
    all-service snapshots; line counts are capped to prevent accidental huge dumps.
  - `tg-outreach-diagnostics` for non-secret status, container state, and bounded log bundles saved
    under `/srv/tg-outreach/diagnostics`.
  - `tg-outreach-deploy` for validated staging deploy invocations.
- Let GitHub Actions deploy staging automatically after CI on `main`.
- Keep production deployment out of GitHub Actions for now; production paths are documented as a
  reserved future target only.
- Make Docker host bindings configurable through env vars so staging and production can coexist on
  the same VPS without colliding on host ports.

## Acceptance Criteria

- Agents can read a single VPS context document that explains paths, users, groups, rules, and safe
  commands.
- Agents can inspect status and logs without reading `.env`.
- Agents can capture a bounded diagnostics bundle during testing without reading `.env`, sessions,
  database dumps, or token-bearing config.
- Staging deploys can be invoked by GitHub Actions or authorized agents through a wrapper.
- Production deploys are not exposed in GitHub Actions yet.
- GitHub deployment logic calls the repo deploy script instead of duplicating the deployment recipe.
- The deployment spec, README, wiki index, and log describe the staging model and reserved
  production path.
