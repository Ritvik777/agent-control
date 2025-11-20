import json
import logging
import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from agent_protect_server.config import db_config
from agent_protect_server.models import Agent

# Create sync engine for raw database queries in tests
engine = create_engine(db_config.get_url(), echo=False)


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
    assert "/api/v1/agents/initAgent" in paths
    assert "/api/v1/agents/{agent_id}" in paths


def test_init_agent_creates_and_gets_agent(client: TestClient) -> None:
    # Given: an init payload
    payload = make_agent_payload()
    # When: initializing the agent
    resp = client.post("/api/v1/agents/initAgent", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    # Then: the agent is created and rules are empty
    assert body["created"] is True
    assert body["rules"] == []

    agent_id = payload["agent"]["agent_id"]
    # When: retrieving the agent by id
    resp2 = client.get(f"/api/v1/agents/{agent_id}")
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
    r1 = client.post("/api/v1/agents/initAgent", json=payload)
    assert r1.status_code == 200
    # Then: it is created
    assert r1.json()["created"] is True

    # When: initializing the same payload again
    r2 = client.post("/api/v1/agents/initAgent", json=payload)
    assert r2.status_code == 200
    # Then: it is not created again (idempotent)
    assert r2.json()["created"] is False


def test_init_agent_adds_new_tool(client: TestClient) -> None:
    # Given: an agent id and base payload
    agent_id = str(uuid.uuid4())
    base = make_agent_payload(agent_id=agent_id)
    # When: initializing the agent
    r1 = client.post("/api/v1/agents/initAgent", json=base)
    assert r1.status_code == 200

    # When: sending an additional tool
    tools = base["tools"] + [
        {
            "tool_name": "tool_b",
            "arguments": {"b": "str"},
            "output_schema": {"ok": "bool"},
        }
    ]
    r2 = client.post("/api/v1/agents/initAgent", json=make_agent_payload(agent_id=agent_id, tools=tools))
    assert r2.status_code == 200
    # Then: the agent is not newly created
    assert r2.json()["created"] is False

    # When: fetching the agent
    g = client.get(f"/api/v1/agents/{agent_id}")
    assert g.status_code == 200
    names = {t["tool_name"] for t in g.json()["tools"]}
    # Then: both tools are present
    assert names == {"tool_a", "tool_b"}


def test_init_agent_overwrites_tool_on_signature_change(client: TestClient) -> None:
    # Given: a base payload for an agent
    agent_id = str(uuid.uuid4())
    base = make_agent_payload(agent_id=agent_id)
    # When: initializing the agent
    r1 = client.post("/api/v1/agents/initAgent", json=base)
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
    r2 = client.post("/api/v1/agents/initAgent", json=changed)
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
    resp = client.get(f"/api/v1/agents/{missing}")
    # Then: a 404 is returned
    assert resp.status_code == 404


def test_init_agent_logs_warning_on_bad_existing_data(client: TestClient, caplog) -> None:
    # Given: an existing agent
    payload = make_agent_payload()
    r1 = client.post("/api/v1/agents/initAgent", json=payload)
    assert r1.status_code == 200

    # When: corrupting the stored data so parsing fails
    with Session(engine) as session:
        agent = session.execute(
            select(Agent).where(Agent.name == payload["agent"]["agent_name"])
        ).scalar_one()
        agent.data = {"foo": "bar"}
        session.commit()

    # When: re-initializing with the same payload
    logger_name = "agent_protect_server.endpoints.agent"
    with caplog.at_level(logging.WARNING, logger=logger_name):
        r2 = client.post("/api/v1/agents/initAgent", json=payload)
        assert r2.status_code == 200
        # Then: a warning is logged about parse failure
        messages = [rec.getMessage() for rec in caplog.records]
        assert any("Failed to parse existing agent data" in m for m in messages)


import uuid

def _create_policy(client: TestClient) -> int:
    # Helper: create a policy via API and return id
    name = f"pol-{uuid.uuid4()}"
    resp = client.put("/api/v1/policies", json={"name": name})
    assert resp.status_code == 200
    pid = resp.json()["policy_id"]
    assert isinstance(pid, int)
    return pid


def test_set_agent_policy_first_time(client: TestClient) -> None:
    # Given: a created policy and agent
    policy_id = _create_policy(client)
    payload = make_agent_payload()
    r = client.post("/api/v1/agents/initAgent", json=payload)
    assert r.status_code == 200
    agent_id = payload["agent"]["agent_id"]

    # When: assigning policy the first time
    resp = client.post(f"/api/v1/agents/{agent_id}/policy/{policy_id}")
    # Then: success and no old policy
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["old_policy_id"] is None


def test_get_agent_policy_after_assignment(client: TestClient) -> None:
    # Given: an agent with a policy assigned
    policy_id = _create_policy(client)
    payload = make_agent_payload()
    client.post("/api/v1/agents/initAgent", json=payload)
    agent_id = payload["agent"]["agent_id"]
    client.post(f"/api/v1/agents/{agent_id}/policy/{policy_id}")

    # When: retrieving policy
    resp = client.get(f"/api/v1/agents/{agent_id}/policy")
    # Then: we see the assigned policy id
    assert resp.status_code == 200
    assert resp.json()["policy_id"] == policy_id


def test_reassign_agent_policy_returns_old_id(client: TestClient) -> None:
    # Given: an agent with an existing policy
    first = _create_policy(client)
    second = _create_policy(client)
    payload = make_agent_payload()
    client.post("/api/v1/agents/initAgent", json=payload)
    agent_id = payload["agent"]["agent_id"]
    client.post(f"/api/v1/agents/{agent_id}/policy/{first}")

    # When: reassigning to another policy
    resp = client.post(f"/api/v1/agents/{agent_id}/policy/{second}")
    # Then: success and old_policy_id equals the first policy id
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert resp.json()["old_policy_id"] == first


def test_delete_agent_policy_then_get_404(client: TestClient) -> None:
    # Given: an agent with a policy assigned
    policy_id = _create_policy(client)
    payload = make_agent_payload()
    client.post("/api/v1/agents/initAgent", json=payload)
    agent_id = payload["agent"]["agent_id"]
    client.post(f"/api/v1/agents/{agent_id}/policy/{policy_id}")

    # When: removing the policy association
    del_resp = client.delete(f"/api/v1/agents/{agent_id}/policy")
    # Then: deletion success
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    # When: fetching policy after deletion
    get_resp = client.get(f"/api/v1/agents/{agent_id}/policy")
    # Then: not found
    assert get_resp.status_code == 404


def test_set_policy_agent_not_found_returns_404(client: TestClient) -> None:
    # Given: a policy id and a random agent uuid
    policy_id = _create_policy(client)
    missing_agent = str(uuid.uuid4())

    # When: assigning to missing agent
    resp = client.post(f"/api/v1/agents/{missing_agent}/policy/{policy_id}")
    # Then: 404
    assert resp.status_code == 404


def test_set_policy_not_found_returns_404(client: TestClient) -> None:
    # Given: an agent and a bogus policy id
    payload = make_agent_payload()
    client.post("/api/v1/agents/initAgent", json=payload)
    agent_id = payload["agent"]["agent_id"]
    bogus_policy = "999999999"

    # When: assigning a non-existent policy
    resp = client.post(f"/api/v1/agents/{agent_id}/policy/{bogus_policy}")
    # Then: 404
    assert resp.status_code == 404


def test_list_agent_rules_no_policy_returns_empty(client: TestClient) -> None:
    # Given: an agent without a policy
    payload = make_agent_payload()
    client.post("/api/v1/agents/initAgent", json=payload)
    agent_id = payload["agent"]["agent_id"]

    # When: listing rules
    r = client.get(f"/api/v1/agents/{agent_id}/rules")
    # Then: empty list
    assert r.status_code == 200
    assert r.json()["rules"] == []


def test_list_agent_rules_with_policy(client: TestClient) -> None:
    # Given: an agent with a policy containing one control and one rule
    payload = make_agent_payload()
    client.post("/api/v1/agents/initAgent", json=payload)
    agent_id = payload["agent"]["agent_id"]

    # Create policy, control, rule, and wire them
    pol_name = f"pol-{uuid.uuid4()}"
    pol = client.put("/api/v1/policies", json={"name": pol_name})
    policy_id = pol.json()["policy_id"]

    ctl_name = f"ctl-{uuid.uuid4()}"
    ctl = client.put("/api/v1/controls", json={"name": ctl_name})
    control_id = ctl.json()["control_id"]

    rl_name = f"rule-{uuid.uuid4()}"
    rl = client.put("/api/v1/rules", json={"name": rl_name})
    rule_id = rl.json()["rule_id"]

    # Set rule data
    from .utils import VALID_RULE_PAYLOAD
    data_payload = VALID_RULE_PAYLOAD
    client.put(f"/api/v1/rules/{rule_id}/data", json={"data": data_payload})

    # Associate rule -> control and control -> policy; assign policy to agent
    client.post(f"/api/v1/controls/{control_id}/rules/{rule_id}")
    client.post(f"/api/v1/policies/{policy_id}/controls/{control_id}")
    client.post(f"/api/v1/agents/{agent_id}/policy/{policy_id}")

    # When: listing rules
    r = client.get(f"/api/v1/agents/{agent_id}/rules")
    # Then: contains our rule serialized via API model
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body.get("rules"), list)
    # Verify rule data is present and matches description
    assert any(
        item.get("rule", {}).get("description") == data_payload["description"] 
        for item in body["rules"]
    )


def test_list_agent_rules_agent_not_found_404(client: TestClient) -> None:
    # Given: random agent id
    missing = str(uuid.uuid4())
    # When: requesting
    r = client.get(f"/api/v1/agents/{missing}/rules")
    # Then: 404
    assert r.status_code == 404
