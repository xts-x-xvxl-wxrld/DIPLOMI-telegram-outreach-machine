# VPS GitHub Pipeline Plan

## Goal

Prepare the repository for GitHub upload and establish a safe two-way workflow:

- local and VPS coding agents can push branches to GitHub
- CI validates branch consistency
- staging VPS deploys automatically from the CI-tested `main` commit
- production VPS deploys manually through a protected GitHub environment
- secrets and local runtime files stay out of Git and Docker images

## Decisions

- Add GitHub Actions CI for Ruff, pytest, and Docker build.
- Add a separate deploy workflow that connects to the VPS over SSH and calls the checkout-local
  deploy script.
- Require pinned SSH known-hosts data instead of disabling host-key checks.
- Keep application secrets in VPS `.env`, not in GitHub Actions secrets.
- Use a reset-only deploy checkout and branch-only agent workspaces.
- Add `.dockerignore` so ignored local files are not accidentally copied into image builds.
- Require agents to commit and push after every completed wiki/codebase change slice.
- Require agents to inspect `git status` before staging so unrelated dirty work is not bundled.
- Bind staging Postgres to localhost only; public clients must not be able to reach port 5432.
- Use `/srv/tg-outreach/AGENT_CONTEXT.md` and `/srv/tg-outreach/bin` helpers as the non-secret VPS
  visibility layer for coding agents.
- Keep direct production deploys gated behind GitHub protected environments or a deliberately
  installed release group.

## Acceptance Criteria

- `.env` remains ignored and untracked.
- CI runs on all branch pushes and pull requests.
- Staging deploy runs after successful CI on `main` or by manual dispatch.
- Production deploy runs by manual dispatch against the `production` GitHub environment.
- VPS deploy resets to the selected ref before rebuilding.
- Server-side agent edits happen on `agent/*` branches outside the deploy checkout.
- Completed agent change slices are committed and pushed promptly to keep GitHub fresh.
- Wiki index, architecture, deployment spec, and log describe the workflow.
- Postgres is reachable through Docker networking and optional SSH tunnels, not through a public
  `0.0.0.0:5432` bind.
- Agents can inspect status/logs without reading runtime env files.
