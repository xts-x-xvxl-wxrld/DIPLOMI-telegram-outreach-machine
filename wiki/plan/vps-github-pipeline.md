# VPS GitHub Pipeline Plan

## Goal

Prepare the repository for GitHub upload and establish a safe two-way workflow:

- local and VPS coding agents can push branches to GitHub
- CI validates branch consistency
- staging VPS deploys only from `main`
- secrets and local runtime files stay out of Git and Docker images

## Decisions

- Add GitHub Actions CI for Ruff, pytest, and Docker build.
- Add a separate deploy workflow that connects to the VPS over SSH.
- Require pinned SSH known-hosts data instead of disabling host-key checks.
- Keep application secrets in VPS `.env`, not in GitHub Actions secrets.
- Use a reset-only deploy checkout and branch-only agent workspaces.
- Add `.dockerignore` so ignored local files are not accidentally copied into image builds.
- Require agents to commit and push after every completed wiki/codebase change slice.
- Require agents to inspect `git status` before staging so unrelated dirty work is not bundled.
- Bind staging Postgres to localhost only; public clients must not be able to reach port 5432.

## Acceptance Criteria

- `.env` remains ignored and untracked.
- CI runs on all branch pushes and pull requests.
- Deploy runs only after successful CI on `main` or by manual dispatch.
- VPS deploy resets to the selected ref before rebuilding.
- Server-side agent edits happen on `agent/*` branches outside the deploy checkout.
- Completed agent change slices are committed and pushed promptly to keep GitHub fresh.
- Wiki index, architecture, deployment spec, and log describe the workflow.
- Postgres is reachable through Docker networking and optional SSH tunnels, not through a public
  `0.0.0.0:5432` bind.
