from __future__ import annotations

from fastapi import FastAPI

from backend.api.routes import briefs, communities, health, jobs


def create_app() -> FastAPI:
    app = FastAPI(title="Telegram Community Discovery API", version="0.1.0")
    app.include_router(health.router)
    app.include_router(briefs.router, prefix="/api", tags=["briefs"])
    app.include_router(communities.router, prefix="/api", tags=["communities"])
    app.include_router(jobs.router, prefix="/api", tags=["jobs"])
    return app


app = create_app()

