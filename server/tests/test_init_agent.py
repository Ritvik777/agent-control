import uuid
import json
import logging
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text, select

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
    # Given: an application router
    paths = {getattr(route, "path", None) for route in app.router.routes}
    # Then: initAgent and agent retrieval endpoints are present
    assert "/agents/initAgent" in paths
    assert "/agents/{agent_id}" in paths


def test_init_agent_creates_and_gets_agent(client: TestClient) -> None:
    # Given: an init payload
    payload = make_agent_payload()
    # When: initializing the agent
    resp = client.post("/agents/initAgent", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    # Then: the agent is created and rules are empty
    assert body["created"] is True
    assert body["rules"] == []

    agent_id = payload["agent"]["agent_id"]
    # When: retrieving the agent by id
    resp2 = client.get(f"/agents/{agent_id}")
    assert resp2.status_code == 200
    data = resp2.json()
    # Then: stored agent fields match the request
    assert data["agent"]["agent_id"] == agent_id
    assert data["agent"]["agent_name"] == payload["agent"]["agent_name"]
    assert {t["tool_name"] for t in data["tools"]} == {payload["tools"][0]["tool_name"]}


def test_init_agent_idempotent_same_tools(client: TestClient) -> None:
    # Given: an init payload
    payload = make_agent_payload()
    # When: initializing the agent the first time
    r1 = client.post("/agents/initAgent", json=payload)
    assert r1.status_code == 200
    # Then: it is created
    assert r1.json()["created"] is True

    # When: initializing the same payload again
    r2 = client.post("/agents/initAgent", json=payload)
    assert r2.status_code == 200
    # Then: it is not created again (idempotent)
    assert r2.json()["created"] is False


def test_init_agent_adds_new_tool(client: TestClient) -> None:
    # Given: an agent id and base payload
    agent_id = str(uuid.uuid4())
    base = make_agent_payload(agent_id=agent_id)
    # When: initializing the agent
    r1 = client.post("/agents/initAgent", json=base)
    assert r1.status_code == 200

    # When: sending an additional tool
    tools = base["tools"] + [
        {
            "tool_name": "tool_b",
            "arguments": {"b": "str"},
            "output_schema": {"ok": "bool"},
        }
    ]
    r2 = client.post("/agents/initAgent", json=make_agent_payload(agent_id=agent_id, tools=tools))
    assert r2.status_code == 200
    # Then: the agent is not newly created
    assert r2.json()["created"] is False

    # When: fetching the agent
    g = client.get(f"/agents/{agent_id}")
    assert g.status_code == 200
    names = {t["tool_name"] for t in g.json()["tools"]}
    # Then: both tools are present
    assert names == {"tool_a", "tool_b"}


def test_init_agent_overwrites_tool_on_signature_change(client: TestClient) -> None:
    # Given: a base payload for an agent
    agent_id = str(uuid.uuid4())
    base = make_agent_payload(agent_id=agent_id)
    # When: initializing the agent
    r1 = client.post("/agents/initAgent", json=base)
    assert r1.status_code == 200

    # When: updating tool_a signature
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
    r2 = client.post("/agents/initAgent", json=changed)
    assert r2.status_code == 200
    # Then: it's an update, not a create
    assert r2.json()["created"] is False

    # Then: verify overwrite in raw JSONB (single entry for tool_a with updated signature)
    with engine.begin() as conn:
        row = conn.execute(text("SELECT data FROM agents WHERE agent_uuid = :id"), {"id": agent_id}).first()
        assert row is not None
        tools = row[0].get("tools", [])
        tool_a_entries = [t for t in tools if t.get("tool", {}).get("tool_name") == "tool_a"]
        assert len(tool_a_entries) == 1
        assert tool_a_entries[0]["tool"]["arguments"] == {"a": "str"}


def test_get_agent_not_found(client: TestClient) -> None:
    # Given: a random (missing) agent id
    missing = str(uuid.uuid4())
    # When: fetching the agent
    resp = client.get(f"/agents/{missing}")
    # Then: a 404 is returned
    assert resp.status_code == 404


def test_init_agent_logs_warning_on_bad_existing_data(client: TestClient, caplog) -> None:
    # Given: an existing agent
    payload = make_agent_payload()
    r1 = client.post("/agents/initAgent", json=payload)
    assert r1.status_code == 200

    # When: corrupting the stored data so parsing fails
    from agent_protect_server.db import SessionLocal
    from agent_protect_server.models import Agent

    with SessionLocal() as session:
        agent = session.execute(
            select(Agent).where(Agent.name == payload["agent"]["agent_name"])
        ).scalar_one()
        agent.data = {"foo": "bar"}
        session.commit()

    # When: re-initializing with the same payload
    logger_name = "agent_protect_server.endpoints.agent"
    with caplog.at_level(logging.WARNING, logger=logger_name):
        r2 = client.post("/agents/initAgent", json=payload)
        assert r2.status_code == 200
        # Then: a warning is logged about parse failure
        messages = [rec.getMessage() for rec in caplog.records]
        assert any("Failed to parse existing agent data" in m for m in messages)
