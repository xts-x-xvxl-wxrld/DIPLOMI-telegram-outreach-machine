from __future__ import annotations

from fastapi import FastAPI

from backend.api.routes import briefs, communities, engagement, health, jobs, search, seeds, telegram_entities


def create_app() -> FastAPI:
    app = FastAPI(title="Telegram Community Discovery API", version="0.1.0")
    app.include_router(health.router)
    app.include_router(briefs.router, prefix="/api", tags=["briefs"])
    app.include_router(communities.router, prefix="/api", tags=["communities"])
    app.include_router(engagement.router, prefix="/api", tags=["engagement"])
    app.include_router(jobs.router, prefix="/api", tags=["jobs"])
    app.include_router(search.router, prefix="/api", tags=["search"])
    app.include_router(seeds.router, prefix="/api", tags=["seeds"])
    app.include_router(telegram_entities.router, prefix="/api", tags=["telegram-entities"])
    return app


app = create_app()
