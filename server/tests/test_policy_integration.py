"""Integration tests for the full policy→control→rule chain."""

import uuid

from fastapi.testclient import TestClient


def _create_agent(client: TestClient, name: str | None = None) -> tuple[str, str]:
    """Helper: Create an agent and return (agent_id, agent_name)."""
    agent_id = str(uuid.uuid4())
    agent_name = name or f"agent-{uuid.uuid4()}"
    payload = {
        "agent": {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "agent_description": "test",
            "agent_version": "1.0",
            "agent_metadata": {},
        },
        "tools": [],
    }
    resp = client.post("/api/v1/agents/initAgent", json=payload)
    assert resp.status_code == 200
    return agent_id, agent_name


def _create_policy(client: TestClient, name: str | None = None) -> int:
    """Helper: Create a policy and return policy_id."""
    policy_name = name or f"policy-{uuid.uuid4()}"
    resp = client.put("/api/v1/policies", json={"name": policy_name})
    assert resp.status_code == 200
    return resp.json()["policy_id"]


def _create_control(client: TestClient, name: str | None = None) -> int:
    """Helper: Create a control and return control_id."""
    control_name = name or f"control-{uuid.uuid4()}"
    resp = client.put("/api/v1/controls", json={"name": control_name})
    assert resp.status_code == 200
    return resp.json()["control_id"]


from .utils import VALID_RULE_PAYLOAD

def _create_rule(client: TestClient, name: str | None = None, data: dict | None = None) -> int:
    """Helper: Create a rule and return rule_id."""
    rule_name = name or f"rule-{uuid.uuid4()}"
    resp = client.put("/api/v1/rules", json={"name": rule_name})
    assert resp.status_code == 200
    rule_id = resp.json()["rule_id"]
    
    # Always set valid data, using name/data in description for traceability
    payload = VALID_RULE_PAYLOAD.copy()
    payload["description"] = f"Name: {rule_name}, Data: {data}"
    
    resp = client.put(f"/api/v1/rules/{rule_id}/data", json={"data": payload})
    assert resp.status_code == 200
    
    return rule_id


def test_agent_gets_rules_from_multiple_controls(client: TestClient) -> None:
    """Agent should see all rules from all controls in its policy."""
    # Given: Agent with policy containing 3 controls, each with 2 rules
    agent_id, _ = _create_agent(client)
    policy_id = _create_policy(client)
    
    # Create 3 controls, each with 2 unique rules
    rule_data_by_control = {}
    for i in range(3):
        control_id = _create_control(client, f"control-{i}")
        rules = []
        for j in range(2):
            rule_data = {"control": i, "rule": j, "level": i * 10 + j}
            rule_id = _create_rule(client, f"rule-{i}-{j}", rule_data)
            rules.append((rule_id, rule_data))
            # Associate rule with control
            resp = client.post(f"/api/v1/controls/{control_id}/rules/{rule_id}")
            assert resp.status_code == 200
        rule_data_by_control[control_id] = rules
        # Associate control with policy
        resp = client.post(f"/api/v1/policies/{policy_id}/controls/{control_id}")
        assert resp.status_code == 200
    
    # Assign policy to agent
    resp = client.post(f"/api/v1/agents/{agent_id}/policy/{policy_id}")
    assert resp.status_code == 200
    
    # When: Get agent's rules
    resp = client.get(f"/api/v1/agents/{agent_id}/rules")
    assert resp.status_code == 200
    rules = resp.json()["rules"]
    
    # Then: Agent sees all 6 rules (3 controls × 2 rules)
    assert len(rules) == 6
    
    # Verify all rule IDs are present
    received_ids = {r["id"] for r in rules}
    expected_ids = set()
    for control_rules in rule_data_by_control.values():
        for rid, _ in control_rules:
            expected_ids.add(rid)
    assert received_ids == expected_ids


def test_agent_gets_no_duplicate_rules_from_shared_rule(client: TestClient) -> None:
    """When same rule is in multiple controls, agent should see it only once."""
    # Given: Policy with 2 controls sharing the same rule
    agent_id, _ = _create_agent(client)
    policy_id = _create_policy(client)
    control_1_id = _create_control(client, "control-1")
    control_2_id = _create_control(client, "control-2")
    
    # Create a shared rule and a unique rule per control
    shared_rule_data = {"type": "shared", "value": 42}
    shared_rule_id = _create_rule(client, "shared-rule", shared_rule_data)
    
    unique_rule_1_data = {"type": "unique-1", "value": 1}
    unique_rule_1_id = _create_rule(client, "unique-1", unique_rule_1_data)
    
    unique_rule_2_data = {"type": "unique-2", "value": 2}
    unique_rule_2_id = _create_rule(client, "unique-2", unique_rule_2_data)
    
    # Add shared rule to both controls
    client.post(f"/api/v1/controls/{control_1_id}/rules/{shared_rule_id}")
    client.post(f"/api/v1/controls/{control_2_id}/rules/{shared_rule_id}")
    
    # Add unique rules
    client.post(f"/api/v1/controls/{control_1_id}/rules/{unique_rule_1_id}")
    client.post(f"/api/v1/controls/{control_2_id}/rules/{unique_rule_2_id}")
    
    # Associate controls with policy
    client.post(f"/api/v1/policies/{policy_id}/controls/{control_1_id}")
    client.post(f"/api/v1/policies/{policy_id}/controls/{control_2_id}")
    
    # Assign policy to agent
    client.post(f"/api/v1/agents/{agent_id}/policy/{policy_id}")
    
    # When: Get agent's rules
    resp = client.get(f"/api/v1/agents/{agent_id}/rules")
    assert resp.status_code == 200
    rules = resp.json()["rules"]
    
    # Then: Agent sees 3 unique rules (not 4)
    assert len(rules) == 3
    
    # Verify IDs
    received_ids = {r["id"] for r in rules}
    assert shared_rule_id in received_ids
    assert unique_rule_1_id in received_ids
    assert unique_rule_2_id in received_ids


def test_agent_rules_update_when_control_added_to_policy(client: TestClient) -> None:
    """Adding a control to policy should add its rules to the agent."""
    # Given: Agent with policy that has 1 control with 2 rules
    agent_id, _ = _create_agent(client)
    policy_id = _create_policy(client)
    control_1_id = _create_control(client, "control-1")
    
    rule_1_id = _create_rule(client, "rule-1", {"id": 1})
    rule_2_id = _create_rule(client, "rule-2", {"id": 2})
    
    client.post(f"/api/v1/controls/{control_1_id}/rules/{rule_1_id}")
    client.post(f"/api/v1/controls/{control_1_id}/rules/{rule_2_id}")
    client.post(f"/api/v1/policies/{policy_id}/controls/{control_1_id}")
    client.post(f"/api/v1/agents/{agent_id}/policy/{policy_id}")
    
    # Verify initial state: 2 rules
    resp = client.get(f"/api/v1/agents/{agent_id}/rules")
    assert len(resp.json()["rules"]) == 2
    
    # When: Add another control with 3 rules to the policy
    control_2_id = _create_control(client, "control-2")
    rule_3_id = _create_rule(client, "rule-3", {"id": 3})
    rule_4_id = _create_rule(client, "rule-4", {"id": 4})
    rule_5_id = _create_rule(client, "rule-5", {"id": 5})
    
    client.post(f"/api/v1/controls/{control_2_id}/rules/{rule_3_id}")
    client.post(f"/api/v1/controls/{control_2_id}/rules/{rule_4_id}")
    client.post(f"/api/v1/controls/{control_2_id}/rules/{rule_5_id}")
    client.post(f"/api/v1/policies/{policy_id}/controls/{control_2_id}")
    
    # Then: Agent now sees 5 rules total
    resp = client.get(f"/api/v1/agents/{agent_id}/rules")
    rules = resp.json()["rules"]
    assert len(rules) == 5
    
    rule_ids = {r["id"] for r in rules}
    assert rule_ids == {rule_1_id, rule_2_id, rule_3_id, rule_4_id, rule_5_id}


def test_agent_rules_update_when_rule_added_to_control(client: TestClient) -> None:
    """Adding a rule to control should make it visible to agents via policy."""
    # Given: Agent → Policy → Control → 2 rules
    agent_id, _ = _create_agent(client)
    policy_id = _create_policy(client)
    control_id = _create_control(client)
    
    rule_1_id = _create_rule(client, "rule-1", {"id": 1})
    rule_2_id = _create_rule(client, "rule-2", {"id": 2})
    
    client.post(f"/api/v1/controls/{control_id}/rules/{rule_1_id}")
    client.post(f"/api/v1/controls/{control_id}/rules/{rule_2_id}")
    client.post(f"/api/v1/policies/{policy_id}/controls/{control_id}")
    client.post(f"/api/v1/agents/{agent_id}/policy/{policy_id}")
    
    # Verify initial state: 2 rules
    resp = client.get(f"/api/v1/agents/{agent_id}/rules")
    assert len(resp.json()["rules"]) == 2
    
    # When: Add new rule to the control
    rule_3_id = _create_rule(client, "rule-3", {"id": 3})
    resp = client.post(f"/api/v1/controls/{control_id}/rules/{rule_3_id}")
    assert resp.status_code == 200
    
    # Then: Agent immediately sees 3 rules
    resp = client.get(f"/api/v1/agents/{agent_id}/rules")
    rules = resp.json()["rules"]
    assert len(rules) == 3
    
    rule_ids = {r["id"] for r in rules}
    assert rule_ids == {rule_1_id, rule_2_id, rule_3_id}


def test_switching_agent_policy_changes_rules(client: TestClient) -> None:
    """Switching agent's policy should completely change its rules."""
    # Given: Two policies with different control/rule sets
    agent_id, _ = _create_agent(client)
    
    # Policy A with rules {1, 2}
    policy_a_id = _create_policy(client, "policy-a")
    control_a_id = _create_control(client, "control-a")
    rule_1_id = _create_rule(client, "rule-1", {"policy": "A", "id": 1})
    rule_2_id = _create_rule(client, "rule-2", {"policy": "A", "id": 2})
    client.post(f"/api/v1/controls/{control_a_id}/rules/{rule_1_id}")
    client.post(f"/api/v1/controls/{control_a_id}/rules/{rule_2_id}")
    client.post(f"/api/v1/policies/{policy_a_id}/controls/{control_a_id}")
    
    # Policy B with rules {3, 4}
    policy_b_id = _create_policy(client, "policy-b")
    control_b_id = _create_control(client, "control-b")
    rule_3_id = _create_rule(client, "rule-3", {"policy": "B", "id": 3})
    rule_4_id = _create_rule(client, "rule-4", {"policy": "B", "id": 4})
    client.post(f"/api/v1/controls/{control_b_id}/rules/{rule_3_id}")
    client.post(f"/api/v1/controls/{control_b_id}/rules/{rule_4_id}")
    client.post(f"/api/v1/policies/{policy_b_id}/controls/{control_b_id}")
    
    # Assign policy A to agent
    client.post(f"/api/v1/agents/{agent_id}/policy/{policy_a_id}")
    resp = client.get(f"/api/v1/agents/{agent_id}/rules")
    rules_a = resp.json()["rules"]
    assert len(rules_a) == 2
    assert {r["id"] for r in rules_a} == {rule_1_id, rule_2_id}
    
    # When: Switch to policy B
    resp = client.post(f"/api/v1/agents/{agent_id}/policy/{policy_b_id}")
    assert resp.status_code == 200
    
    # Then: Agent's rules change completely
    resp = client.get(f"/api/v1/agents/{agent_id}/rules")
    rules_b = resp.json()["rules"]
    assert len(rules_b) == 2
    assert {r["id"] for r in rules_b} == {rule_3_id, rule_4_id}


def test_removing_agent_policy_clears_rules(client: TestClient) -> None:
    """Removing policy from agent should result in empty rules list."""
    # Given: Agent with policy that has rules
    agent_id, _ = _create_agent(client)
    policy_id = _create_policy(client)
    control_id = _create_control(client)
    rule_id = _create_rule(client, "rule-1", {"id": 1})
    
    client.post(f"/api/v1/controls/{control_id}/rules/{rule_id}")
    client.post(f"/api/v1/policies/{policy_id}/controls/{control_id}")
    client.post(f"/api/v1/agents/{agent_id}/policy/{policy_id}")
    
    # Verify agent has rules
    resp = client.get(f"/api/v1/agents/{agent_id}/rules")
    assert len(resp.json()["rules"]) > 0
    
    # When: Remove policy from agent
    resp = client.delete(f"/api/v1/agents/{agent_id}/policy")
    assert resp.status_code == 200
    
    # Then: Agent returns empty rules list
    resp = client.get(f"/api/v1/agents/{agent_id}/rules")
    assert resp.status_code == 200
    assert resp.json()["rules"] == []


def test_removing_control_from_policy_removes_its_rules_from_agent(
    client: TestClient,
) -> None:
    """Removing control from policy should remove its rules from agent."""
    # Given: Agent → Policy → 2 controls (A, B) each with rules
    agent_id, _ = _create_agent(client)
    policy_id = _create_policy(client)
    
    # Control A with rules {1, 2}
    control_a_id = _create_control(client, "control-a")
    rule_1_id = _create_rule(client, "rule-1", {"control": "A", "id": 1})
    rule_2_id = _create_rule(client, "rule-2", {"control": "A", "id": 2})
    client.post(f"/api/v1/controls/{control_a_id}/rules/{rule_1_id}")
    client.post(f"/api/v1/controls/{control_a_id}/rules/{rule_2_id}")
    
    # Control B with rules {3, 4}
    control_b_id = _create_control(client, "control-b")
    rule_3_id = _create_rule(client, "rule-3", {"control": "B", "id": 3})
    rule_4_id = _create_rule(client, "rule-4", {"control": "B", "id": 4})
    client.post(f"/api/v1/controls/{control_b_id}/rules/{rule_3_id}")
    client.post(f"/api/v1/controls/{control_b_id}/rules/{rule_4_id}")
    
    # Add both controls to policy
    client.post(f"/api/v1/policies/{policy_id}/controls/{control_a_id}")
    client.post(f"/api/v1/policies/{policy_id}/controls/{control_b_id}")
    client.post(f"/api/v1/agents/{agent_id}/policy/{policy_id}")
    
    # Verify initial state: 4 rules
    resp = client.get(f"/api/v1/agents/{agent_id}/rules")
    assert len(resp.json()["rules"]) == 4
    
    # When: Remove control A from policy
    resp = client.delete(f"/api/v1/policies/{policy_id}/controls/{control_a_id}")
    assert resp.status_code == 200
    
    # Then: Agent only sees rules from control B
    resp = client.get(f"/api/v1/agents/{agent_id}/rules")
    rules = resp.json()["rules"]
    assert len(rules) == 2
    assert {r["id"] for r in rules} == {rule_3_id, rule_4_id}


def test_removing_rule_from_control_removes_from_agent(client: TestClient) -> None:
    """Removing rule from control should remove it from agent."""
    # Given: Agent → Policy → Control → 3 rules
    agent_id, _ = _create_agent(client)
    policy_id = _create_policy(client)
    control_id = _create_control(client)
    
    rule_1_id = _create_rule(client, "rule-1", {"id": 1})
    rule_2_id = _create_rule(client, "rule-2", {"id": 2})
    rule_3_id = _create_rule(client, "rule-3", {"id": 3})
    
    client.post(f"/api/v1/controls/{control_id}/rules/{rule_1_id}")
    client.post(f"/api/v1/controls/{control_id}/rules/{rule_2_id}")
    client.post(f"/api/v1/controls/{control_id}/rules/{rule_3_id}")
    client.post(f"/api/v1/policies/{policy_id}/controls/{control_id}")
    client.post(f"/api/v1/agents/{agent_id}/policy/{policy_id}")
    
    # Verify initial state: 3 rules
    resp = client.get(f"/api/v1/agents/{agent_id}/rules")
    assert len(resp.json()["rules"]) == 3
    
    # When: Remove 1 rule from control
    resp = client.delete(f"/api/v1/controls/{control_id}/rules/{rule_2_id}")
    assert resp.status_code == 200
    
    # Then: Agent sees 2 rules
    resp = client.get(f"/api/v1/agents/{agent_id}/rules")
    rules = resp.json()["rules"]
    assert len(rules) == 2
    assert {r["id"] for r in rules} == {rule_1_id, rule_3_id}


def test_multiple_agents_same_policy(client: TestClient) -> None:
    """Multiple agents with same policy should all see the same rules."""
    # Given: 2 agents assigned to same policy
    agent_1_id, _ = _create_agent(client, "agent-1")
    agent_2_id, _ = _create_agent(client, "agent-2")
    
    policy_id = _create_policy(client)
    control_id = _create_control(client)
    
    rule_1_id = _create_rule(client, "rule-1", {"id": 1})
    rule_2_id = _create_rule(client, "rule-2", {"id": 2})
    
    client.post(f"/api/v1/controls/{control_id}/rules/{rule_1_id}")
    client.post(f"/api/v1/controls/{control_id}/rules/{rule_2_id}")
    client.post(f"/api/v1/policies/{policy_id}/controls/{control_id}")
    
    # Assign same policy to both agents
    client.post(f"/api/v1/agents/{agent_1_id}/policy/{policy_id}")
    client.post(f"/api/v1/agents/{agent_2_id}/policy/{policy_id}")
    
    # Verify both see same rules initially
    resp_1 = client.get(f"/api/v1/agents/{agent_1_id}/rules")
    resp_2 = client.get(f"/api/v1/agents/{agent_2_id}/rules")
    assert len(resp_1.json()["rules"]) == 2
    assert len(resp_2.json()["rules"]) == 2
    
    # When: Add new rule to policy's control
    rule_3_id = _create_rule(client, "rule-3", {"id": 3})
    client.post(f"/api/v1/controls/{control_id}/rules/{rule_3_id}")
    
    # Then: Both agents see the new rule
    resp_1 = client.get(f"/api/v1/agents/{agent_1_id}/rules")
    resp_2 = client.get(f"/api/v1/agents/{agent_2_id}/rules")
    
    rules_1 = resp_1.json()["rules"]
    rules_2 = resp_2.json()["rules"]
    
    assert len(rules_1) == 3
    assert len(rules_2) == 3
    expected = {rule_1_id, rule_2_id, rule_3_id}
    assert {r["id"] for r in rules_1} == expected
    assert {r["id"] for r in rules_2} == expected
