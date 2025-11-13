from typing import Any

from fastapi.testclient import TestClient
from fastapi import FastAPI


def test_init_agent_route_exists(app: FastAPI) -> None:
    paths = {getattr(route, "path", None) for route in app.router.routes}
    assert "/initAgent" in paths


def test_init_agent_invocation_returns_not_implemented(client: TestClient) -> None:
    payload: dict[str, Any] = {
        "agent": {
            "agent_id": "test-agent-id",
            "agent_name": "Test Agent",
        }
    }

    resp = client.post("/initAgent", json=payload)
    # Endpoint is defined but not implemented yet
    assert resp.status_code == 500
