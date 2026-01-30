"""End-to-end tests for evaluator error handling."""
import json
import uuid
from copy import deepcopy

from fastapi.testclient import TestClient
from sqlalchemy import text
from agent_control_models import EvaluationRequest, Step

from .conftest import engine
from .utils import create_and_assign_policy


def test_evaluation_with_agent_scoped_evaluator_missing(client: TestClient):
    """Test that referencing missing agent evaluator fails at policy assignment.

    Given: A control referencing agent:evaluator that doesn't exist
    When: Attempting to assign policy
    Then: Returns 400 with clear error message
    """
    # Given: Agent without evaluators
    agent_uuid = uuid.uuid4()
    client.post("/api/v1/agents/initAgent", json={
        "agent": {
            "agent_id": str(agent_uuid),
            "agent_name": f"TestAgent-{uuid.uuid4().hex[:8]}"
        },
        "steps": [],
        "evaluators": []
    })

    # And: A control referencing non-existent agent evaluator
    agent_name = f"TestAgent-{uuid.uuid4().hex[:8]}"
    control_data = {
        "description": "Test control",
        "enabled": True,
        "execution": "server",
        "scope": {"step_types": ["llm"], "stages": ["pre"]},
        "selector": {"path": "input"},
        "evaluator": {
            "name": f"{agent_name}:missing-evaluator",
            "config": {}
        },
        "action": {"decision": "deny"}
    }

    # When: Creating control - this should fail at control creation
    control_resp = client.put("/api/v1/controls", json={"name": f"control-{uuid.uuid4().hex[:8]}"})
    assert control_resp.status_code == 200
    control_id = control_resp.json()["control_id"]

    # Then: Setting control data should fail if agent doesn't exist
    set_resp = client.put(f"/api/v1/controls/{control_id}/data", json={"data": control_data})
    # This will fail because the agent doesn't exist yet
    assert set_resp.status_code in [404, 422]


def test_evaluation_control_with_invalid_config_caught_early(client: TestClient):
    """Test that invalid evaluator config is caught at control creation.

    Given: A control with invalid config for an evaluator
    When: Setting control data
    Then: Returns 422 with validation error
    """
    # Given: Create control
    control_resp = client.put("/api/v1/controls", json={"name": f"control-{uuid.uuid4().hex[:8]}"})
    assert control_resp.status_code == 200
    control_id = control_resp.json()["control_id"]

    # When: Setting control data with invalid regex config (missing required 'pattern')
    control_data = {
        "description": "Test control",
        "enabled": True,
        "execution": "server",
        "scope": {"step_types": ["llm"], "stages": ["pre"]},
        "selector": {"path": "input"},
        "evaluator": {
            "name": "regex",
            "config": {}  # Missing required 'pattern' field
        },
        "action": {"decision": "deny"}
    }

    set_resp = client.put(f"/api/v1/controls/{control_id}/data", json={"data": control_data})

    # Then: Should fail with validation error
    assert set_resp.status_code == 422
    assert "pattern" in set_resp.text.lower() or "required" in set_resp.text.lower()


def test_evaluation_errors_field_populated_on_evaluator_failure(
    client: TestClient, monkeypatch
):
    """Test that errors field is populated when evaluator fails at runtime.

    Given: A valid control with an evaluator that crashes during evaluation
    When: Evaluation is requested
    Then: Response has errors field populated and is_safe=False (for deny)
    """
    from unittest.mock import MagicMock, AsyncMock

    # Given: Setup agent with a working control
    control_data = {
        "description": "Test control",
        "enabled": True,
        "execution": "server",
        "scope": {"step_types": ["llm"], "stages": ["pre"]},
        "selector": {"path": "input"},
        "evaluator": {
            "name": "regex",
            "config": {"pattern": "test"}
        },
        "action": {"decision": "deny"}
    }
    agent_uuid, control_name = create_and_assign_policy(client, control_data)

    # Mock get_evaluator_instance to return an evaluator that throws
    mock_evaluator = MagicMock()
    mock_evaluator.evaluate = AsyncMock(side_effect=RuntimeError("Simulated evaluator crash"))
    mock_evaluator.get_timeout_seconds = MagicMock(return_value=30.0)

    # Patch where it's used (in core module), not where it's defined
    import agent_control_engine.core as core_module

    def mock_get_evaluator_instance(config):
        return mock_evaluator

    monkeypatch.setattr(core_module, "get_evaluator_instance", mock_get_evaluator_instance)

    # When: Sending evaluation request
    payload = Step(type="llm", name="test-step", input="test content", output=None)
    req = EvaluationRequest(
        agent_uuid=agent_uuid,
        step=payload,
        stage="pre"
    )
    resp = client.post("/api/v1/evaluation", json=req.model_dump(mode="json"))

    # Then: Response should have errors field populated
    assert resp.status_code == 200
    data = resp.json()

    # is_safe=False because deny control errored (fail closed)
    assert data["is_safe"] is False

    # Confidence should be 0 (no successful evaluations)
    assert data["confidence"] == 0.0

    # Errors field should be populated
    assert data["errors"] is not None
    assert len(data["errors"]) == 1
    assert data["errors"][0]["control_name"] == control_name
    assert "RuntimeError" in data["errors"][0]["result"]["error"]
    assert "Simulated evaluator crash" in data["errors"][0]["result"]["error"]

    # No matches because evaluation failed
    assert data["matches"] is None or len(data["matches"]) == 0


def test_evaluation_engine_value_error_returns_422(client: TestClient, monkeypatch) -> None:
    """Test that evaluation returns 422 when the engine raises a ValueError."""
    # Given: a valid agent with a control assigned
    control_data = {
        "description": "Test control",
        "enabled": True,
        "execution": "server",
        "scope": {"step_types": ["llm"], "stages": ["pre"]},
        "selector": {"path": "input"},
        "evaluator": {"name": "regex", "config": {"pattern": "test"}},
        "action": {"decision": "deny"},
    }
    agent_uuid, _ = create_and_assign_policy(client, control_data)

    # And: the engine raises a ValueError during processing
    import agent_control_engine.core as core_module

    async def raise_value_error(*_args, **_kwargs):
        raise ValueError("bad config")

    monkeypatch.setattr(core_module.ControlEngine, "process", raise_value_error)

    # When: sending an evaluation request
    payload = Step(type="llm", name="test-step", input="test content", output=None)
    req = EvaluationRequest(agent_uuid=agent_uuid, step=payload, stage="pre")
    resp = client.post("/api/v1/evaluation", json=req.model_dump(mode="json"))

    # Then: a validation error is returned
    assert resp.status_code == 422
    body = resp.json()
    assert body["error_code"] == "EVALUATION_FAILED"


def test_evaluation_unknown_agent_returns_404(client: TestClient) -> None:
    # Given: an agent UUID that has not been registered
    missing_agent = uuid.uuid4()
    payload = Step(type="llm", name="test-step", input="content", output=None)
    req = EvaluationRequest(agent_uuid=missing_agent, step=payload, stage="pre")

    # When: submitting an evaluation request
    resp = client.post("/api/v1/evaluation", json=req.model_dump(mode="json"))

    # Then: not found is returned with a clear error code
    assert resp.status_code == 404
    body = resp.json()
    assert body["error_code"] == "AGENT_NOT_FOUND"


def test_evaluation_invalid_step_name_regex_reports_error_and_allows(
    client: TestClient,
) -> None:
    # Given: an agent with a control scoped by step_name_regex
    control_name = f"control-{uuid.uuid4().hex[:8]}"
    control_resp = client.put("/api/v1/controls", json={"name": control_name})
    assert control_resp.status_code == 200
    control_id = control_resp.json()["control_id"]

    control_data = {
        "description": "Step regex control",
        "enabled": True,
        "execution": "server",
        "scope": {
            "step_types": ["tool"],
            "stages": ["pre"],
            "step_name_regex": "^safe_.*",
        },
        "selector": {"path": "input"},
        "evaluator": {"name": "regex", "config": {"pattern": ".*"}},
        "action": {"decision": "deny"},
    }
    set_resp = client.put(f"/api/v1/controls/{control_id}/data", json={"data": control_data})
    assert set_resp.status_code == 200

    policy_resp = client.put("/api/v1/policies", json={"name": f"policy-{uuid.uuid4().hex[:8]}"})
    assert policy_resp.status_code == 200
    policy_id = policy_resp.json()["policy_id"]
    assoc_resp = client.post(f"/api/v1/policies/{policy_id}/controls/{control_id}")
    assert assoc_resp.status_code == 200

    agent_uuid = uuid.uuid4()
    agent_resp = client.post("/api/v1/agents/initAgent", json={
        "agent": {"agent_id": str(agent_uuid), "agent_name": "RegexAgent"},
        "steps": []
    })
    assert agent_resp.status_code == 200
    assign_resp = client.post(f"/api/v1/agents/{str(agent_uuid)}/policy/{policy_id}")
    assert assign_resp.status_code == 200

    # And: the control data is corrupted with an invalid regex
    corrupted_data = deepcopy(control_data)
    corrupted_data["scope"]["step_name_regex"] = "("
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE controls SET data = CAST(:data AS JSONB) WHERE id = :id"),
            {"data": json.dumps(corrupted_data), "id": control_id},
        )

    # When: evaluating a tool step for that agent
    req = EvaluationRequest(
        agent_uuid=agent_uuid,
        step=Step(type="tool", name="safe_tool", input={}, output=None),
        stage="pre",
    )
    resp = client.post("/api/v1/evaluation", json=req.model_dump(mode="json"))

    # Then: evaluation succeeds but surfaces the selector error
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_safe"] is True
    assert body["confidence"] == 0.0
    assert body["errors"] is not None
    assert body["errors"][0]["control_name"] == control_name
    assert "Invalid step_name_regex" in body["errors"][0]["result"]["error"]
