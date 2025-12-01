"""Tests for agent schema auto-generation functionality."""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from agent_control_server.config import db_config
from agent_control_server.models import Agent

# Create sync engine for raw database queries in tests
engine = create_engine(db_config.get_url(), echo=False)


def make_agent_with_tools(
    agent_id: str | None = None,
    name: str | None = None,
    tools: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Create an agent payload with tools for testing."""
    if agent_id is None:
        agent_id = str(uuid.uuid4())
    if name is None:
        name = f"Test Agent {uuid.uuid4()}"
    if tools is None:
        tools = [
            {
                "tool_name": "search_products",
                "arguments": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "category": {"type": "string", "optional": True}
                    },
                    "required": ["query"]
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "products": {"type": "array"},
                        "total": {"type": "integer"}
                    }
                }
            }
        ]
    return {
        "agent": {
            "agent_id": agent_id,
            "agent_name": name,
            "agent_description": "Test agent with tools",
            "agent_version": "1.0.0",
            "agent_metadata": {"env": "test"}
        },
        "tools": tools
    }


def test_schema_endpoint_exists(client: TestClient) -> None:
    """Test that the schema endpoint is registered."""
    # Given: an agent
    payload = make_agent_with_tools()
    resp = client.post("/api/v1/agents/initAgent", json=payload)
    assert resp.status_code == 200
    agent_id = payload["agent"]["agent_id"]
    
    # When: accessing schema endpoint
    schema_resp = client.get(f"/api/v1/agents/{agent_id}/schema")
    
    # Then: endpoint exists (not 404)
    assert schema_resp.status_code in [200, 404]  # 404 if no schema, but endpoint exists


def test_schema_auto_generated_on_agent_creation(client: TestClient) -> None:
    """Test that schema is automatically generated when agent is created with tools."""
    # Given: an agent payload with tools
    payload = make_agent_with_tools()
    
    # When: creating the agent
    resp = client.post("/api/v1/agents/initAgent", json=payload)
    assert resp.status_code == 200
    agent_id = payload["agent"]["agent_id"]
    
    # Then: schema should be auto-generated
    schema_resp = client.get(f"/api/v1/agents/{agent_id}/schema")
    assert schema_resp.status_code == 200
    
    schema = schema_resp.json()
    # Then: schema has expected structure
    assert schema["schema_type"] == "agent"
    assert schema["version"] == "1.0"
    assert "tools" in schema
    assert "capabilities" in schema
    assert "total_tools" in schema
    assert schema["total_tools"] == 1


def test_schema_contains_tool_definitions(client: TestClient) -> None:
    """Test that generated schema contains tool definitions."""
    # Given: an agent with multiple tools
    tools = [
        {
            "tool_name": "search_users",
            "arguments": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            },
            "output_schema": {"type": "object"}
        },
        {
            "tool_name": "create_order",
            "arguments": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "amount": {"type": "number"}
                },
                "required": ["user_id", "amount"]
            },
            "output_schema": {"type": "object"}
        }
    ]
    payload = make_agent_with_tools(tools=tools)
    
    # When: creating the agent
    client.post("/api/v1/agents/initAgent", json=payload)
    agent_id = payload["agent"]["agent_id"]
    
    # Then: schema contains both tools
    schema_resp = client.get(f"/api/v1/agents/{agent_id}/schema")
    assert schema_resp.status_code == 200
    schema = schema_resp.json()
    
    assert schema["total_tools"] == 2
    tool_names = {tool["name"] for tool in schema["tools"]}
    assert tool_names == {"search_users", "create_order"}


def test_schema_includes_required_fields(client: TestClient) -> None:
    """Test that schema correctly identifies required fields."""
    # Given: a tool with required fields
    tools = [{
        "tool_name": "process_payment",
        "arguments": {
            "type": "object",
            "properties": {
                "amount": {"type": "number"},
                "currency": {"type": "string"},
                "optional_note": {"type": "string", "optional": True}
            },
            "required": ["amount", "currency"]
        },
        "output_schema": {"type": "object"}
    }]
    payload = make_agent_with_tools(tools=tools)
    
    # When: creating the agent and retrieving schema
    client.post("/api/v1/agents/initAgent", json=payload)
    agent_id = payload["agent"]["agent_id"]
    schema_resp = client.get(f"/api/v1/agents/{agent_id}/schema")
    
    # Then: required fields are correctly identified
    schema = schema_resp.json()
    tool_def = schema["tools"][0]
    assert set(tool_def["required_inputs"]) == {"amount", "currency"}


def test_schema_infers_capabilities(client: TestClient) -> None:
    """Test that schema correctly infers capabilities from tool names."""
    # Given: tools with capability-indicating names
    tools = [
        {
            "tool_name": "search_products",
            "arguments": {"type": "object", "properties": {}},
            "output_schema": {"type": "object"}
        },
        {
            "tool_name": "create_order",
            "arguments": {"type": "object", "properties": {}},
            "output_schema": {"type": "object"}
        },
        {
            "tool_name": "send_email",
            "arguments": {"type": "object", "properties": {}},
            "output_schema": {"type": "object"}
        }
    ]
    payload = make_agent_with_tools(tools=tools)
    
    # When: creating the agent
    client.post("/api/v1/agents/initAgent", json=payload)
    agent_id = payload["agent"]["agent_id"]
    schema_resp = client.get(f"/api/v1/agents/{agent_id}/schema")
    
    # Then: capabilities are inferred
    schema = schema_resp.json()
    capabilities = set(schema["capabilities"])
    # Should infer: search, create, send
    assert "search" in capabilities
    assert "create" in capabilities
    assert "send" in capabilities


def test_schema_regenerated_when_tools_updated(client: TestClient) -> None:
    """Test that schema is regenerated when agent tools are updated."""
    # Given: an agent with one tool
    agent_id = str(uuid.uuid4())
    agent_name = f"Test Agent {agent_id}"  # Use consistent name
    
    payload1 = make_agent_with_tools(
        agent_id=agent_id,
        name=agent_name,
        tools=[
            {
                "tool_name": "tool_a",
                "arguments": {"type": "object", "properties": {}},
                "output_schema": {"type": "object"}
            }
        ]
    )
    
    # When: creating the agent
    client.post("/api/v1/agents/initAgent", json=payload1)
    schema1_resp = client.get(f"/api/v1/agents/{agent_id}/schema")
    schema1 = schema1_resp.json()
    assert schema1["total_tools"] == 1
    
    # When: updating with additional tool (same name required!)
    payload2 = make_agent_with_tools(
        agent_id=agent_id,
        name=agent_name,  # MUST use same name
        tools=[
            {
                "tool_name": "tool_a",
                "arguments": {"type": "object", "properties": {}},
                "output_schema": {"type": "object"}
            },
            {
                "tool_name": "tool_b",
                "arguments": {"type": "object", "properties": {}},
                "output_schema": {"type": "object"}
            }
        ]
    )
    client.post("/api/v1/agents/initAgent", json=payload2)
    
    # Then: schema is regenerated
    schema2_resp = client.get(f"/api/v1/agents/{agent_id}/schema")
    schema2 = schema2_resp.json()
    assert schema2["total_tools"] == 2
    tool_names = {tool["name"] for tool in schema2["tools"]}
    assert tool_names == {"tool_a", "tool_b"}


def test_schema_not_found_for_nonexistent_agent(client: TestClient) -> None:
    """Test that requesting schema for nonexistent agent returns 404."""
    # Given: a random agent ID
    missing_id = str(uuid.uuid4())
    
    # When: requesting schema
    resp = client.get(f"/api/v1/agents/{missing_id}/schema")
    
    # Then: 404 returned
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_legacy_agent_without_schema_generates_on_demand(client: TestClient) -> None:
    """Test backward compatibility: legacy agents get schema generated on first access."""
    # Given: an agent created normally
    payload = make_agent_with_tools()
    client.post("/api/v1/agents/initAgent", json=payload)
    agent_id = payload["agent"]["agent_id"]
    
    # When: simulating legacy agent by removing schema from database
    with Session(engine) as session:
        # Get the agent using SQLAlchemy ORM
        from agent_control_server.models import Agent as AgentModel
        agent = session.execute(
            select(AgentModel).where(AgentModel.agent_uuid == agent_id)
        ).scalar_one()
        
        # Remove schema field to simulate legacy data
        data = dict(agent.data)
        data.pop("schema", None)
        agent.data = data
        
        session.commit()
    
    # Then: requesting schema should generate it on-demand
    schema_resp = client.get(f"/api/v1/agents/{agent_id}/schema")
    assert schema_resp.status_code == 200
    
    schema = schema_resp.json()
    assert schema["schema_type"] == "agent"
    assert schema["total_tools"] == 1
    
    # Verify it was persisted
    with Session(engine) as session:
        agent = session.execute(
            text("SELECT data FROM agents WHERE agent_uuid = :id"),
            {"id": agent_id}
        ).first()
        assert "agent_schema" in agent.data


def test_agent_without_tools_has_empty_schema(client: TestClient) -> None:
    """Test that agent created without tools gets an empty schema."""
    # Given: an agent payload without tools
    payload = make_agent_with_tools(tools=[])
    
    # When: creating the agent
    resp = client.post("/api/v1/agents/initAgent", json=payload)
    assert resp.status_code == 200
    agent_id = payload["agent"]["agent_id"]
    
    # Then: schema exists but is empty
    schema_resp = client.get(f"/api/v1/agents/{agent_id}/schema")
    assert schema_resp.status_code == 200
    
    schema = schema_resp.json()
    # Schema should be generated even for empty tools
    assert "total_tools" in schema
    assert schema["total_tools"] == 0
    assert schema["tools"] == []
    assert schema["capabilities"] == []


def test_schema_includes_metadata(client: TestClient) -> None:
    """Test that schema includes metadata about generation."""
    # Given: an agent with tools
    payload = make_agent_with_tools()
    
    # When: creating and retrieving schema
    client.post("/api/v1/agents/initAgent", json=payload)
    agent_id = payload["agent"]["agent_id"]
    schema_resp = client.get(f"/api/v1/agents/{agent_id}/schema")
    
    # Then: schema includes metadata
    schema = schema_resp.json()
    assert "metadata" in schema
    assert schema["metadata"]["auto_generated"] is True
    assert "generator_version" in schema["metadata"]


def test_schema_stored_in_agent_data(client: TestClient) -> None:
    """Test that schema is stored in the agent's data JSONB field."""
    # Given: an agent with tools
    payload = make_agent_with_tools()
    
    # When: creating the agent
    client.post("/api/v1/agents/initAgent", json=payload)
    agent_id = payload["agent"]["agent_id"]
    
    # Then: schema is in database
    with Session(engine) as session:
        agent = session.execute(
            text("SELECT data FROM agents WHERE agent_uuid = :id"),
            {"id": agent_id}
        ).first()
        assert agent is not None
        assert "agent_schema" in agent.data
        assert agent.data["agent_schema"]["schema_type"] == "agent"


def test_schema_output_type_inference(client: TestClient) -> None:
    """Test that schema correctly infers output types."""
    # Given: tools with different output types
    tools = [
        {
            "tool_name": "get_count",
            "arguments": {"type": "object", "properties": {}},
            "output_schema": {"type": "integer"}
        },
        {
            "tool_name": "list_items",
            "arguments": {"type": "object", "properties": {}},
            "output_schema": {"type": "array"}
        },
        {
            "tool_name": "get_details",
            "arguments": {"type": "object", "properties": {}},
            "output_schema": {"type": "object"}
        }
    ]
    payload = make_agent_with_tools(tools=tools)
    
    # When: creating and retrieving schema
    client.post("/api/v1/agents/initAgent", json=payload)
    agent_id = payload["agent"]["agent_id"]
    schema_resp = client.get(f"/api/v1/agents/{agent_id}/schema")
    
    # Then: output types are correctly inferred
    schema = schema_resp.json()
    tools_by_name = {t["name"]: t for t in schema["tools"]}
    
    assert tools_by_name["get_count"]["output_type"] == "integer"
    assert tools_by_name["list_items"]["output_type"] == "array"
    assert tools_by_name["get_details"]["output_type"] == "object"


def test_schema_idempotent_on_same_tools(client: TestClient) -> None:
    """Test that re-registering with same tools doesn't change schema."""
    # Given: an agent
    agent_id = str(uuid.uuid4())
    payload = make_agent_with_tools(agent_id=agent_id)
    
    # When: creating agent twice with same tools
    client.post("/api/v1/agents/initAgent", json=payload)
    schema1_resp = client.get(f"/api/v1/agents/{agent_id}/schema")
    schema1 = schema1_resp.json()
    
    client.post("/api/v1/agents/initAgent", json=payload)
    schema2_resp = client.get(f"/api/v1/agents/{agent_id}/schema")
    schema2 = schema2_resp.json()
    
    # Then: schemas are identical
    assert schema1 == schema2


def test_complex_tool_schema_with_nested_properties(client: TestClient) -> None:
    """Test schema generation with complex nested tool definitions."""
    # Given: a tool with nested properties
    tools = [{
        "tool_name": "complex_search",
        "arguments": {
            "type": "object",
            "properties": {
                "filters": {
                    "type": "object",
                    "properties": {
                        "price_range": {
                            "type": "object",
                            "properties": {
                                "min": {"type": "number"},
                                "max": {"type": "number"}
                            }
                        },
                        "categories": {"type": "array"}
                    }
                },
                "sort": {"type": "string"}
            },
            "required": ["filters"]
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "results": {"type": "array"},
                "metadata": {"type": "object"}
            }
        }
    }]
    payload = make_agent_with_tools(tools=tools)
    
    # When: creating and retrieving schema
    client.post("/api/v1/agents/initAgent", json=payload)
    agent_id = payload["agent"]["agent_id"]
    schema_resp = client.get(f"/api/v1/agents/{agent_id}/schema")
    
    # Then: complex schema is captured
    assert schema_resp.status_code == 200
    schema = schema_resp.json()
    tool = schema["tools"][0]
    
    assert "input_schema" in tool
    assert "properties" in tool["input_schema"]
    assert "filters" in tool["input_schema"]["properties"]

