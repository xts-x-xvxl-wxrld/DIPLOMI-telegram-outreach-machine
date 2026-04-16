from __future__ import annotations

from backend.api.app import create_app


def test_create_app_registers_core_routes() -> None:
    app = create_app()
    paths = {route.path for route in app.routes}

    assert "/health" in paths
    assert "/ready" in paths
    assert "/api/briefs" in paths
    assert "/api/seed-imports/csv" in paths
    assert "/api/seed-groups" in paths
    assert "/api/seed-groups/{seed_group_id}" in paths
    assert "/api/seed-groups/{seed_group_id}/candidates" in paths
    assert "/api/communities/{community_id}/members" in paths
