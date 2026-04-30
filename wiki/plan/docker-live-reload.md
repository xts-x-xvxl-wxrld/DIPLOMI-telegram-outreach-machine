# Docker Live Reload

## Goal

Make the local Docker Compose stack reflect source edits without rebuilding images for every Python
code change.

## Plan

1. Keep `docker-compose.yml` production-like so staging continues to run rebuilt images.
2. Add `docker-compose.dev.yml` for local development overrides.
3. Bind mount the repository into app containers at `/app` in the dev override so edited source
   files replace the image copy during local development.
4. Run the API with Uvicorn reload scoped to backend code in the dev override.
5. Run worker, scheduler, and bot commands through `watchfiles` in the dev override so long-lived
   Python processes restart when backend or bot modules change.
6. Keep persisted runtime state in the existing Docker volumes for Postgres and Telethon sessions.

## Notes

- Dependency or packaging changes still require rebuilding the image because `pip install -e .`
  runs at image build time.
- Start local reload mode with
  `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build`.
- The reload path is isolated from staging deployment, which remains reset-only and rebuilds images
  from the checked-out commit.
