# Agent Merge To Main Plan

Status: complete

## Goal

Make completed agent branches converge back into `main` instead of leaving finished work stranded on
task branches.

## Scope

- Add an explicit completed-branch merge rule to `AGENTS.md` and `CLAUDE.md`.
- Align the deployment workflow spec with the same expectation.
- Keep the existing local-CI-before-push rule intact.

## Acceptance Criteria

- Repo agent guidance says completed branch-scoped work should be merged into `main` after local
  parity passes unless the user explicitly wants the branch left open.
- Guidance keeps the existing rule that failing or unrun local parity blocks pushes.
- Deployment spec describes `main` as the durable landing branch for completed agent work.
