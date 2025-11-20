"""Test utilities for server tests."""
import uuid
from typing import Any
from fastapi.testclient import TestClient


VALID_RULE_PAYLOAD = {
    "description": "Valid Rule",
    "enabled": True,
    "applies_to": "llm_call",
    "check_stage": "pre",
    "selector": {"path": "input"},
    "evaluator": {"type": "regex", "config": {"pattern": "x"}},
    "action": {"decision": "deny"}
}

def create_and_assign_policy(client: TestClient, rule_config: dict[str, Any] | None = None, agent_name: str = "MyTestAgent") -> tuple[uuid.UUID, str]:
    """Helper to setup Agent -> Policy -> Control -> Rule hierarchy.
    
    Args:
        rule_config: Optional rule configuration. If None, uses VALID_RULE_PAYLOAD.
    
    Returns:
        tuple: (agent_uuid, rule_name)
    """
    if rule_config is None:
        rule_config = VALID_RULE_PAYLOAD.copy()
    rule_name = f"rule-{uuid.uuid4()}"
    resp = client.put("/api/v1/rules", json={"name": rule_name})
    assert resp.status_code == 200
    rule_id = resp.json()["rule_id"]

    # 1.1 Configure Rule
    resp = client.put(f"/api/v1/rules/{rule_id}/data", json={"data": rule_config})
    assert resp.status_code == 200

    # 2. Create Control
    control_name = f"control-{uuid.uuid4()}"
    resp = client.put("/api/v1/controls", json={"name": control_name})
    assert resp.status_code == 200
    control_id = resp.json()["control_id"]
    
    client.post(f"/api/v1/controls/{control_id}/rules/{rule_id}")

    # 3. Create Policy
    policy_name = f"policy-{uuid.uuid4()}"
    resp = client.put("/api/v1/policies", json={"name": policy_name})
    assert resp.status_code == 200
    policy_id = resp.json()["policy_id"]
    
    client.post(f"/api/v1/policies/{policy_id}/controls/{control_id}")

    # 4. Register Agent
    agent_uuid = uuid.uuid4()
    resp = client.post("/api/v1/agents/initAgent", json={
        "agent": {
            "agent_id": str(agent_uuid),
            "agent_name": agent_name
        },
        "tools": []
    })
    assert resp.status_code == 200

    # 5. Assign Policy
    client.post(f"/api/v1/agents/{str(agent_uuid)}/policy/{policy_id}")
    
    return agent_uuid, rule_name
