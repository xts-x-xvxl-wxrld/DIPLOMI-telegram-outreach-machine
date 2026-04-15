from __future__ import annotations

from backend.api.app import create_app


def test_create_app_registers_core_routes() -> None:
    app = create_app()
    paths = {route.path for route in app.routes}

    assert "/health" in paths
    assert "/ready" in paths
    assert "/api/briefs" in paths

