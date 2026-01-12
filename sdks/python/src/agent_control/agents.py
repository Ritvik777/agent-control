"""Agent management operations for Agent Control SDK."""

from typing import Any, cast
from uuid import UUID

from .client import AgentControlClient

# Import models if available
try:
    from agent_control_models import Agent
    MODELS_AVAILABLE = True
except ImportError:
    MODELS_AVAILABLE = False
    Agent = Any  # type: ignore


async def register_agent(
    client: AgentControlClient,
    agent: Agent,
    tools: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """
    Register an agent with the server via /initAgent endpoint.

    Args:
        client: AgentControlClient instance
        agent: Agent instance to register
        tools: Optional list of tools with their schemas

    Returns:
        InitAgentResponse with created flag and controls

    Raises:
        httpx.HTTPError: If request fails

    Example:
        async with AgentControlClient() as client:
            response = await register_agent(client, agent, tools=[...])
            print(f"Created: {response['created']}")
    """
    if tools is None:
        tools = []

    if MODELS_AVAILABLE:
        agent_dict = agent.to_dict()
        # Ensure UUID is converted to string for JSON serialization
        if isinstance(agent_dict.get('agent_id'), UUID):
            agent_dict['agent_id'] = str(agent_dict['agent_id'])
        payload = {
            "agent": agent_dict,
            "tools": tools
        }
    else:
        payload = {
            "agent": {
                "agent_id": str(agent.agent_id),
                "agent_name": agent.agent_name,
                "agent_description": getattr(agent, 'agent_description', None),
                "agent_version": getattr(agent, 'agent_version', None),
                "agent_metadata": getattr(agent, 'agent_metadata', None),
            },
            "tools": tools
        }

    response = await client.http_client.post("/api/v1/agents/initAgent", json=payload)
    response.raise_for_status()
    return cast(dict[str, Any], response.json())


async def get_agent(
    client: AgentControlClient,
    agent_id: str
) -> dict[str, Any]:
    """
    Get agent details by ID from the server.

    Args:
        client: AgentControlClient instance
        agent_id: UUID or string identifier of the agent

    Returns:
        Dictionary containing:
            - agent: Agent metadata
            - tools: List of tools registered with the agent

    Raises:
        httpx.HTTPError: If request fails or agent not found (404)

    Example:
        async with AgentControlClient() as client:
            agent_data = await get_agent(client, "550e8400-e29b-41d4-a716-446655440000")
            print(f"Agent: {agent_data['agent']['agent_name']}")
            print(f"Tools: {len(agent_data['tools'])}")
    """
    response = await client.http_client.get(f"/api/v1/agents/{agent_id}")
    response.raise_for_status()
    return cast(dict[str, Any], response.json())


async def list_agents(
    client: AgentControlClient,
    cursor: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """
    List all registered agents from the server.

    Args:
        client: AgentControlClient instance
        cursor: Optional cursor for pagination (UUID of last agent from previous page)
        limit: Number of results per page (default 20, max 100)

    Returns:
        Dictionary containing:
            - agents: List of agent summaries with agent_id, agent_name,
                      policy_id, created_at, tool_count, evaluator_count
            - pagination: Object with limit, total, next_cursor, has_more

    Raises:
        httpx.HTTPError: If request fails

    Example:
        async with AgentControlClient() as client:
            result = await list_agents(client, limit=10)
            print(f"Total agents: {result['pagination']['total']}")
            for agent in result['agents']:
                print(f"  - {agent['agent_name']} ({agent['agent_id']})")
            # Fetch next page if available
            if result['pagination']['has_more']:
                next_result = await list_agents(
                    client, cursor=result['pagination']['next_cursor']
                )
    """
    params: dict[str, Any] = {"limit": limit}
    if cursor:
        params["cursor"] = cursor
    response = await client.http_client.get("/api/v1/agents", params=params)
    response.raise_for_status()
    return cast(dict[str, Any], response.json())

