import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from agent_protect_server.db import engine


def make_agent_payload(agent_id: str | None = None, name: str = "Test Agent", tools: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if agent_id is None:
        agent_id = str(uuid.uuid4())
    if tools is None:
        tools = [
            {
                "tool_name": "tool_a",
                "arguments": {"a": "int"},
                "output_schema": {"ok": "bool"},
            }
        ]
    return {
        "agent": {
            "agent_id": agent_id,
            "agent_name": name,
            "agent_description": "desc",
            "agent_version": "1.0",
            "agent_metadata": {"env": "test"},
        },
        "tools": tools,
    }


def test_init_agent_route_exists(app: FastAPI) -> None:
    paths = {getattr(route, "path", None) for route in app.router.routes}
    assert "/initAgent" in paths
    assert "/agents/{agent_id}" in paths


def test_init_agent_creates_and_gets_agent(client: TestClient) -> None:
    payload = make_agent_payload()
    resp = client.post("/initAgent", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] is True
    assert body["rules"] == []

    agent_id = payload["agent"]["agent_id"]
    resp2 = client.get(f"/agents/{agent_id}")
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["agent"]["agent_id"] == agent_id
    assert data["agent"]["agent_name"] == payload["agent"]["agent_name"]
    assert {t["tool_name"] for t in data["tools"]} == {payload["tools"][0]["tool_name"]}


def test_init_agent_idempotent_same_tools(client: TestClient) -> None:
    payload = make_agent_payload()
    r1 = client.post("/initAgent", json=payload)
    assert r1.status_code == 200
    assert r1.json()["created"] is True

    r2 = client.post("/initAgent", json=payload)
    assert r2.status_code == 200
    assert r2.json()["created"] is False


def test_init_agent_adds_new_tool(client: TestClient) -> None:
    agent_id = str(uuid.uuid4())
    base = make_agent_payload(agent_id=agent_id)
    r1 = client.post("/initAgent", json=base)
    assert r1.status_code == 200

    tools = base["tools"] + [
        {
            "tool_name": "tool_b",
            "arguments": {"b": "str"},
            "output_schema": {"ok": "bool"},
        }
    ]
    r2 = client.post("/initAgent", json=make_agent_payload(agent_id=agent_id, tools=tools))
    assert r2.status_code == 200
    assert r2.json()["created"] is False

    g = client.get(f"/agents/{agent_id}")
    assert g.status_code == 200
    names = {t["tool_name"] for t in g.json()["tools"]}
    assert names == {"tool_a", "tool_b"}


def test_init_agent_versions_tool_on_signature_change(client: TestClient) -> None:
    agent_id = str(uuid.uuid4())
    base = make_agent_payload(agent_id=agent_id)
    r1 = client.post("/initAgent", json=base)
    assert r1.status_code == 200

    # change arguments for tool_a
    changed = make_agent_payload(
        agent_id=agent_id,
        tools=[
            {
                "tool_name": "tool_a",
                "arguments": {"a": "str"},  # changed type
                "output_schema": {"ok": "bool"},
            }
        ],
    )
    r2 = client.post("/initAgent", json=changed)
    assert r2.status_code == 200
    assert r2.json()["created"] is False

    # verify versions in raw JSONB
    with engine.begin() as conn:
        row = conn.execute(text("SELECT data FROM agents WHERE agent_uuid = :id"), {"id": agent_id}).first()
        assert row is not None
        tools = row[0].get("tools", [])
        tool_a_versions = [t for t in tools if t.get("tool", {}).get("tool_name") == "tool_a"]
        assert len(tool_a_versions) >= 2
        versions = sorted(v["version"] for v in tool_a_versions)
        assert versions[0] == 0
        assert versions[-1] >= 1


def test_get_agent_not_found(client: TestClient) -> None:
    missing = str(uuid.uuid4())
    resp = client.get(f"/agents/{missing}")
    assert resp.status_code == 404
